# Snapshot Multi-Screen Engine — ONE broad TV query + local masking (P1.2)
"""
Collapses up to ~14 per-template upstream TV calls per discovery cycle into
ONE base snapshot query (liquid US equities, SNAPSHOT_COLUMNS + dynamic EMA
columns), then applies each template's filters as local pandas masks via
``TVScreenerSpecialist.evaluate_filters_local``.

Gating (enforced by ``TVScreenEngine.screen_batch``):
- feature flag ``CONFLU_SCREEN_SNAPSHOT_MULTI_SCREEN`` (default OFF)
- circuit breaker auto-fallback when TV call volume exceeds budget

Known, accepted divergence (flag stays OFF until proven): rules tagged with
a non-default timeframe are evaluated against the single snapshot interval
("1D") rather than their own timeframe.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pandas as pd
from tradingview_screener.query import Query

from backend.app.core.logging import get_logger
from backend.app.infrastructure.screener.configs import FilterRule, ScreenConfig
from backend.app.infrastructure.screener.tv_specialist import (
    SNAPSHOT_COLUMNS,
    TVScreenerSpecialist,
    TVDiscoveryResult,
)

log = get_logger("conflu.screener.snapshot_engine")

# Universal liquidity/venue gates applied SERVER-side on the base snapshot.
# Template-specific gates (market-cap floors etc.) stay in each template and
# are re-applied locally, so the base query only prunes obvious noise.
_BASE_GATES: list[FilterRule] = [
    FilterRule(
        category="fundamental",
        indicator="exchange_in",
        params={"exchanges": ["NYSE", "NASDAQ"]},
        timeframe="1D",
    ),
    FilterRule(
        category="fundamental",
        indicator="country_in",
        params={"countries": ["United States"]},
        timeframe="1D",
    ),
    FilterRule(
        category="fundamental",
        indicator="close_above",
        params={"threshold": 5.0},
        timeframe="1D",
    ),
    FilterRule(
        category="volume",
        indicator="avg_volume_gt",
        params={"threshold": 500_000},
        timeframe="1D",
    ),
]

# Indicators whose filter params reference parameterised EMA columns.
_EMA_PERIOD_INDICATORS: dict[str, tuple[str, ...]] = {
    "price_above_ema": ("period",),
    "price_below_ema": ("period",),
    "cross_above_ma": ("period",),
    "cross_below_ma": ("period",),
    "price_above_emas": ("periods",),
    "price_below_emas": ("periods",),
}
_EMA_FAST_SLOW_INDICATORS: dict[str, tuple[str, str]] = {
    "ema_cross": ("fast", "slow"),
    "ema_cross_bearish": ("fast", "slow"),
}

_DEFAULT_TIMEOUT_S = 30.0


def _required_extra_columns(configs: list[ScreenConfig]) -> list[str]:
    """Collect dynamically-referenced columns (e.g. EMA100) for the base query."""
    periods: set[int] = set()
    for config in configs:
        for flt in config.filters:
            params = flt.params or {}
            if flt.indicator in _EMA_PERIOD_INDICATORS:
                for key in _EMA_PERIOD_INDICATORS[flt.indicator]:
                    value = params.get(key)
                    if isinstance(value, (int, float)):
                        periods.add(int(value))
                    elif isinstance(value, list):
                        periods.update(int(p) for p in value if isinstance(p, (int, float)))
            elif flt.indicator in _EMA_FAST_SLOW_INDICATORS:
                fast_key, slow_key = _EMA_FAST_SLOW_INDICATORS[flt.indicator]
                for key in (fast_key, slow_key):
                    if isinstance(params.get(key), (int, float)):
                        periods.add(int(params[key]))
    return [f"EMA{p}" for p in sorted(periods) if f"EMA{p}" not in SNAPSHOT_COLUMNS]


def build_base_config(configs: list[ScreenConfig], size: int = 1500) -> ScreenConfig:
    """Synthetic ScreenConfig describing the broad base snapshot.

    Doubles as the TVCache key payload so the snapshot participates in the
    engine's stale-while-revalidate flow like any other discovery.
    """
    return ScreenConfig(
        name="base-snapshot",
        description="One-Snapshot-Multi-Screen liquid US equity universe",
        asset_classes=["equities"],
        timeframes=["1D"],
        filters=list(_BASE_GATES),
        limit=size,
    )


class SnapshotMultiScreenEngine:
    """Fetches one base snapshot and masks it locally per template."""

    def __init__(self, specialist: TVScreenerSpecialist, size: int = 1500) -> None:
        self.specialist = specialist
        self.size = size
        self.log = get_logger("conflu.screener.snapshot_engine")

    # ── base snapshot fetch ───────────────────────────────

    async def fetch_snapshot(self, configs: list[ScreenConfig]) -> pd.DataFrame | None:
        """Run ONE upstream query returning the masked-ready base frame."""
        q = Query()
        q.set_markets("america")
        q.set_property("interval", "1D")
        q.select(*SNAPSHOT_COLUMNS, *_required_extra_columns(configs))

        condition = self.specialist.compile_filters(list(_BASE_GATES))
        if condition is not None:
            q.where2(condition)

        q.limit(self.size)

        loop = asyncio.get_running_loop()
        start = time.monotonic()
        try:
            total, df = await asyncio.wait_for(
                loop.run_in_executor(None, q.get_scanner_data),
                timeout=_DEFAULT_TIMEOUT_S,
            )
        except TimeoutError:
            self.log.warning("snapshot_timeout", timeout_s=_DEFAULT_TIMEOUT_S)
            return None
        except Exception:
            self.log.exception("snapshot_fetch_failed")
            return None

        self.log.info(
            "snapshot_fetched",
            rows=0 if df is None else len(df),
            reported_total=total,
            ms=round((time.monotonic() - start) * 1000),
        )
        if df is None or df.empty:
            return None
        return df

    # ── local masking ─────────────────────────────────────

    def mask_template(
        self,
        snapshot: pd.DataFrame,
        config: ScreenConfig,
    ) -> TVDiscoveryResult | None:
        """Apply one template's filters locally. None ⇒ fail-closed."""
        start = time.monotonic()

        mask = self.specialist.evaluate_filters_local(snapshot, list(config.filters))
        if mask is None:
            self.log.warning("template_mask_failed_closed", screen=config.name)
            return None

        matched = snapshot.loc[mask]
        tickers = matched["ticker"].str.split(":").str[-1].unique().tolist() if "ticker" in matched.columns else []

        return TVDiscoveryResult(
            screen_name=config.name,
            total_matches=len(tickers),
            tickers=tickers,
            execution_ms=round((time.monotonic() - start) * 1000),
            raw_data=matched,
            timeframe=config.timeframes[0] if config.timeframes else "1D",
        )

    def discover_all_local(
        self,
        snapshot: pd.DataFrame,
        configs: list[ScreenConfig],
    ) -> dict[str, TVDiscoveryResult]:
        """Mask every template against the same snapshot.

        Returns results keyed by template stem; templates that fail-closed
        are omitted (callers fall back to legacy discovery for those).
        """
        out: dict[str, TVDiscoveryResult] = {}
        for config in configs:
            result = self.mask_template(snapshot, config)
            if result is not None:
                out[config.name] = result
        covered = len(out)
        if covered < len(configs):
            log.warning(
                "partial_snapshot_coverage",
                covered=covered,
                requested=len(configs),
            )
        return out
