"""ScreenEngine — orchestrator for the screener filter pipeline.

Flow:
1. Load ScreenConfig from YAML
2. Resolve filter dependencies -> indicator names needed
3. For each timeframe (top-down):
   a. Cache.get_latest() -> latest indicator values
   b. Broadcast higher-TF indicators to this TF (ffill)
   c. Apply each filter -> boolean masks
   d. AND-combine masks within timeframe
   e. AND-combine with parent mask (narrowing candidates)
4. Compute scores
5. Build results DataFrame
6. Output: DataFrame / CSV / JSON / WebSocket
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from backend.app.core.config import settings
from backend.app.core.logging import get_logger, set_correlation_id
from backend.app.infrastructure.screener.broadcasting import sort_timeframes
from backend.app.infrastructure.screener.cache import IndicatorCache
from backend.app.infrastructure.screener.configs import ScreenConfig, load_screen_template
from backend.app.infrastructure.screener.filters import _FILTER_REGISTRY, list_filters
from backend.app.infrastructure.screener.models import FilterRunResult, ScreenRunResult
from backend.app.infrastructure.screener.scoring import compute_pass_rates, compute_score

log = get_logger("conflu.screener.engine")


class ScreenEngine:
    """Orchestrator for screen evaluation.

    Loads config, resolves indicators, applies filters, scores results.
    Supports multi-timeframe top-down narrowing and parallel asset classes.
    """

    def __init__(self) -> None:
        self._cache = IndicatorCache()
        self._log = get_logger("conflu.screener.engine")
        self._correlation_id: str | None = None

    async def screen(
        self,
        config: ScreenConfig | str,
        symbols: list[str] | None = None,
        timeframes: list[str] | None = None,
    ) -> ScreenRunResult:
        """Run a screen configuration against all symbols.

        Args:
            config: ScreenConfig instance or name of screen template.
            symbols: Optional subset of symbols to screen (None = all).
            timeframes: Override timeframes (None = from config).

        Returns:
            ScreenRunResult with matched symbols and filter statistics.
        """
        self._correlation_id = set_correlation_id()
        start = time.monotonic()

        # 1. Resolve config
        if isinstance(config, str):
            cfg = load_screen_template(config)
        else:
            cfg = config

        tfs = sort_timeframes(timeframes or cfg.timeframes, descending=True)
        filters_by_tf = self._group_filters_by_timeframe(cfg.filters, tfs)

        # 2. Track per-filter results
        per_filter_masks: dict[str, pd.Series] = {}
        candidates_mask: pd.Series | None = None
        all_indicator_data: dict[str, Any] = {}

        # 3. Evaluate top-down
        for tf in tfs:
            tf_filters = filters_by_tf.get(tf, [])
            if not tf_filters:
                continue

            # Get indicator data for this timeframe
            indicator_data = await self._load_indicator_data(tf, symbols)

            if indicator_data is None or indicator_data.empty:
                self._log.warning("no_indicator_data", timeframe=tf)
                continue

            # Store for later use
            all_indicator_data[tf] = indicator_data

            # Apply each filter
            for flt in tf_filters:
                filter_def = _FILTER_REGISTRY.get(flt.indicator)
                if filter_def is None:
                    self._log.warning("filter_not_found", filter_name=flt.indicator)
                    continue

                try:
                    mask = filter_def.func(indicator_data, **flt.params)

                    # Apply negation if specified
                    if flt.negate:
                        mask = ~mask

                    # Fill NaN with False (no match)
                    mask = mask.fillna(False)

                    per_filter_masks[flt.indicator] = mask

                    # AND-combine into timeframe mask
                    if candidates_mask is None:
                        candidates_mask = mask
                    else:
                        candidates_mask = candidates_mask & mask

                except Exception:
                    self._log.exception(
                        "filter_evaluation_failed",
                        filter_name=flt.indicator,
                        timeframe=tf,
                    )

            # Early exit: no candidates left
            if candidates_mask is not None and not candidates_mask.any():
                self._log.info("no_candidates", timeframe=tf)
                break

        # 4. Compute scores
        total_filters = len(cfg.filters)
        if candidates_mask is None:
            scores = pd.Series(dtype=float)
        else:
            scores = compute_score(
                mask=candidates_mask,
                total_filters=total_filters,
                per_filter_masks=per_filter_masks,
            )

        # 5. Build results
        matched_symbols = (
            list(scores[scores > 0].index) if not scores.empty else []
        )
        pass_rates = compute_pass_rates(per_filter_masks) if per_filter_masks else {}

        # Build matched symbols detail
        symbol_details: list[dict[str, Any]] = []
        for sym in matched_symbols:
            symbol_details.append({
                "symbol": sym,
                "score": float(scores[sym]),
                "matched_filters": [
                    name for name, mask in per_filter_masks.items()
                    if sym in mask.index and mask.get(sym, False)
                ],
            })

        # Build filter run results
        filter_results = []
        for name, mask in per_filter_masks.items():
            filter_results.append(
                FilterRunResult(
                    filter_name=name,
                    category=getattr(
                        _FILTER_REGISTRY.get(name), "category", ""
                    ),
                    matched=int(mask.sum()) if not mask.empty else 0,
                    total=len(mask) if not mask.empty else 0,
                    pass_rate=pass_rates.get(name, 0.0),
                )
            )

        duration_ms = (time.monotonic() - start) * 1000

        return ScreenRunResult(
            screen_name=cfg.name,
            timestamp=datetime.now(timezone.utc),
            duration_ms=round(duration_ms, 2),
            total_symbols=len(scores) if not scores.empty else 0,
            symbols_matched=len(matched_symbols),
            filter_results=filter_results,
            symbols=symbol_details,
        )

    async def _load_indicator_data(
        self,
        timeframe: str,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame | None:
        """Load indicator data for a timeframe from cache.

        Aggregates all cached indicators into a single wide DataFrame.
        If cache is empty, computes on-the-fly.
        """
        # Get all registered indicators
        all_indicators = list_filters()
        indicator_names = list(all_indicators.keys())

        # For each indicator, get latest values
        data_frames: list[pd.DataFrame] = []
        for ind_name in indicator_names:
            try:
                df = await self._cache.get_latest(
                    indicator_name=ind_name,
                    timeframe=timeframe,
                    symbols=symbols,
                )
                if df is not None and not df.empty:
                    # Pivot to wide format: symbol -> indicator value
                    df = df.rename(columns={"value": ind_name})
                    data_frames.append(df[["symbol", ind_name]])
            except Exception:
                self._log.debug(
                    "indicator_data_unavailable",
                    indicator=ind_name,
                    timeframe=timeframe,
                )

        if not data_frames:
            return None

        # Merge all indicator values on symbol
        result = data_frames[0]
        for df in data_frames[1:]:
            result = result.merge(df, on="symbol", how="outer")

        return result

    def _group_filters_by_timeframe(
        self,
        filters: list[Any],
        timeframes: list[str],
    ) -> dict[str, list[Any]]:
        """Group filter rules by their target timeframe."""
        grouped: dict[str, list[Any]] = {tf: [] for tf in timeframes}
        for flt in filters:
            tf = flt.timeframe if hasattr(flt, "timeframe") else "1D"
            if tf in grouped:
                grouped[tf].append(flt)
            else:
                # Put in the nearest higher timeframe
                grouped[timeframes[0]].append(flt)
        return grouped

    async def screen_to_csv(
        self,
        config: ScreenConfig | str,
        path: str | Path,
        symbols: list[str] | None = None,
    ) -> ScreenRunResult:
        """Run screen and export results to CSV."""
        from backend.app.infrastructure.screener.export import export_csv

        result = await self.screen(config, symbols=symbols)
        if result.symbols:
            df = pd.DataFrame(result.symbols)
            export_csv(df, path)
        return result

    async def screen_to_json(
        self,
        config: ScreenConfig | str,
        path: str | Path,
        symbols: list[str] | None = None,
    ) -> ScreenRunResult:
        """Run screen and export results to JSON."""
        from backend.app.infrastructure.screener.export import export_json

        result = await self.screen(config, symbols=symbols)
        if result.symbols:
            df = pd.DataFrame(result.symbols)
            export_json(df, path)
        return result
