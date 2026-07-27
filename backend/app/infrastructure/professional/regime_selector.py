"""Regime-aware screen selector — picks the top 3 screens for a given market regime.

Heuristic scoring
=================
Each screen is scored on four weighted axes (higher = better):

+-----------------------+--------+
| Factor                | Weight |
+-----------------------+--------+
| regime_match          |  40 %  |
| historical_win_rate   |  25 %  |
| avg_conviction        |  20 %  |
| liquidity_score       |  15 %  |
+-----------------------+--------+

* **regime_match** — 1.0 if the screen's `regime` field equals the current
  regime, 0.0 otherwise.
* **historical_win_rate** — backtest win rate (defaults to 0.5 when no data).
* **avg_conviction** — average signal conviction the screen produces (default
  0.5).
* **liquidity_score** — average dollar volume of results (default 0.5).

If **no** screen YAML carries a `regime` field, a hardcoded fallback map
is used instead.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from backend.app.core.logging import get_logger
from backend.app.infrastructure.screener.configs import (
    ScreenConfig,
    _resolve_screens_dir,
    load_screen_template,
)

log = get_logger("conflu.professional.regime_selector")

# ═══════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════

# Heuristic scoring weights (must sum to 1.0)
_REGIME_WEIGHT = 0.40
_WIN_RATE_WEIGHT = 0.25
_CONVICTION_WEIGHT = 0.20
_LIQUIDITY_WEIGHT = 0.15

# Fallback screen names (filename stems) per regime — used when no screen
# YAML carries a `regime` field.
_FALLBACK_MAP: dict[str, list[str]] = {
    "strong_trend": [
        "trend-follower",
        "institutional-trend-follower-mtf",
        "trend-leader",
    ],
    "ranging": [
        "mean-reversion",
        "low-vol-setup",
        "statistical-mean-reversion",
    ],
    "high_vol": [
        "volatility-expansion",
        "volume-surge-breakout",
        "breakout",
    ],
}

_DEFAULT_SCORE = 0.5  # neutral fallback for missing data fields

# Simple dict-based cache:  key = f"{regime}:{date_key}"  ->  list of ScreenConfig
_selector_cache: dict[str, list[ScreenConfig]] = {}


# ═══════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════


def _today_key() -> str:
    """Return today's ISO date string — used for cache key expiry (~24 h TTL)."""
    return datetime.now(timezone.utc).date().isoformat()


def _try_read_screen_yaml(path: Path) -> dict[str, Any] | None:
    """Safely load a YAML file, returning `None` on failure."""
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            log.warning("screen_yaml_not_a_dict", path=str(path))
            return None
        return data
    except Exception:
        log.warning("screen_yaml_read_failed", path=str(path), exc_info=True)
        return None


# ═══════════════════════════════════════════════════════
# RegimeScreenSelector
# ═══════════════════════════════════════════════════════


class RegimeScreenSelector:
    """Selects the top 3 screens for a given market regime using heuristic scoring.

    Usage
    -----
    .. code-block:: python

        selector = RegimeScreenSelector()
        screens = selector.select_top_screens("strong_trend")
        # -> [ScreenConfig(...), ScreenConfig(...), ScreenConfig(...)]

    Caching
    -------
    Results are cached in a module-level dict keyed by `regime:YYYY-MM-DD`
    and automatically expire when the calendar date changes (TTL ≈ 24 h).
    """

    __slots__ = ("_log",)

    def __init__(self) -> None:
        self._log = get_logger("conflu.professional.regime_selector")

    # ── public API ────────────────────────────────────────

    def select_top_screens(self, regime: str) -> list[ScreenConfig]:
        """Return up to 3 :class:ScreenConfig instances best suited for *regime*.

        Parameters
        ----------
        regime : str
            Current market regime label, e.g. `"strong_trend"`, `"ranging"`,
            `"high_vol"`.  Case-sensitive — must match screen YAML `regime`
            values exactly.

        Returns
        -------
        list[ScreenConfig]
            Up to three screen configurations, ordered by descending total score.
            Returns an empty list if no screens could be loaded.
        """
        global _selector_cache

        date_key = _today_key()
        cache_key = f"{regime}:{date_key}"

        cached = _selector_cache.get(cache_key)
        if cached is not None:
            self._log.debug("regime_selector_cache_hit", regime=regime, date=date_key)
            return cached

        self._log.debug("regime_selector_cache_miss", regime=regime, date=date_key)
        result = self._select(regime)
        _selector_cache[cache_key] = result

        # Evict stale entries for other regimes/dates so the dict doesn't grow unbounded
        _prune_cache(cache_key)

        return result

    # ── core selection logic (uncached) ───────────────────

    def _select(self, regime: str) -> list[ScreenConfig]:
        """Run the full selection algorithm — no caching applied here."""
        raw_screens = self._discover_screens()

        # If no screen has a `regime` field at all → use hardcoded fallback.
        has_any_regime = any(s.regime is not None for s in raw_screens)
        if not has_any_regime:
            self._log.info(
                "no_screen_regime_field_found_using_fallback",
                regime=regime,
            )
            return list(self._load_fallback(regime))

        # Score each screen
        scored: list[tuple[float, str]] = []
        for s in raw_screens:
            regime_match = 1.0 if s.regime == regime else 0.0
            total = (
                regime_match * _REGIME_WEIGHT
                + s.historical_win_rate * _WIN_RATE_WEIGHT
                + s.avg_conviction * _CONVICTION_WEIGHT
                + s.liquidity_score * _LIQUIDITY_WEIGHT
            )
            scored.append((total, s.name))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_names = [name for _, name in scored[:3]]

        self._log.info(
            "top_screens_selected",
            regime=regime,
            screens=top_names,
            top_scores=[round(s, 4) for s, _ in scored[:3]],
        )

        return list(self._load_screens(top_names))

    # ── screen discovery ─────────────────────────────────

    def _discover_screens(self) -> list[_ScreenMeta]:
        """Scan `config/screens/` and return metadata for every YAML file."""
        screens_dir = _resolve_screens_dir()
        if not screens_dir.is_dir():
            self._log.warning("screens_directory_not_found", path=str(screens_dir))
            return []

        meta_list: list[_ScreenMeta] = []
        for p in sorted(screens_dir.glob("*.yaml")):
            raw = _try_read_screen_yaml(p)
            if raw is None:
                continue

            name = p.stem
            regime = raw.get("regime")  # optional — may be None
            meta_list.append(
                _ScreenMeta(
                    name=name,
                    regime=str(regime) if regime is not None else None,
                )
            )

        return meta_list

    # ── fallback loading ──────────────────────────────────

    def _load_fallback(self, regime: str) -> tuple[ScreenConfig, ...]:
        """Return hardcoded fallback screens for *regime*.

        Returns an empty tuple for unrecognised regimes.
        """
        screen_names = _FALLBACK_MAP.get(regime)
        if screen_names is None:
            self._log.warning(
                "unknown_regime_no_fallback_available",
                regime=regime,
                known=list(_FALLBACK_MAP),
            )
            return ()
        self._log.info(
            "loading_fallback_screens",
            regime=regime,
            screens=screen_names,
        )
        return self._load_screens(screen_names)

    # ── screen loading helper ─────────────────────────────

    @staticmethod
    def _load_screens(names: list[str]) -> tuple[ScreenConfig, ...]:
        """Load multiple screen configs, silently skipping failures."""
        results: list[ScreenConfig] = []
        for name in names:
            try:
                results.append(load_screen_template(name))
            except Exception:
                log.warning(
                    "failed_to_load_screen_template",
                    screen=name,
                    exc_info=True,
                )
        return tuple(results)


# ═══════════════════════════════════════════════════════
# Cache management
# ═══════════════════════════════════════════════════════


def _prune_cache(current_key: str) -> None:
    """Remove cache entries whose date portion differs from *current_key*.

    Keeps at most one entry per regime (the most recent) to prevent unbounded
    growth in the module-level `_selector_cache` dict.
    """
    global _selector_cache

    # Derive today's date from the current key (format: "regime:YYYY-MM-DD")
    try:
        _, today = current_key.split(":", 1)
    except ValueError:
        return

    stale_keys = [k for k in _selector_cache if not k.endswith(f":{today}")]
    for k in stale_keys:
        log.debug("evicting_stale_cache_entry", key=k)
        del _selector_cache[k]


# ═══════════════════════════════════════════════════════
# Internal data class
# ═══════════════════════════════════════════════════════


class _ScreenMeta:
    """Lightweight metadata extracted from a screen YAML for scoring.

    We deliberately avoid constructing a full :class:ScreenConfig here
    because those are frozen (`extra="forbid"`) and would reject the
    `regime` field that may be present in the YAML.
    """

    __slots__ = (
        "name",
        "regime",
        "historical_win_rate",
        "avg_conviction",
        "liquidity_score",
    )

    def __init__(
        self,
        name: str,
        regime: str | None = None,
        historical_win_rate: float = _DEFAULT_SCORE,
        avg_conviction: float = _DEFAULT_SCORE,
        liquidity_score: float = _DEFAULT_SCORE,
    ) -> None:
        self.name = name
        self.regime = regime
        self.historical_win_rate = historical_win_rate
        self.avg_conviction = avg_conviction
        self.liquidity_score = liquidity_score
