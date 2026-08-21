"""Regime-aware screen selector — picks the top 3 screens for a given market regime.

Selection precedence
====================
1. **Config-driven weights** (`config/regime_screens.yaml`) — per-regime
   weighted screen lists. Top-3 by weight, guaranteeing exactly one
   ``role: defensive`` secondary so NEUTRAL/CHOPPY regimes surface
   momentum/breakout/catalyst setups as PRIMARY instead of collapsing
   into all-defensive lists (RC1 fix).
2. **Heuristic scoring** over screen YAMLs carrying a `regime` field.
3. **Hardcoded fallback map** (`_FALLBACK_MAP`) when nothing else applies.

Heuristic scoring axes (when used)
==================================

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
from typing import Any, NamedTuple

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

# How many screens the selector returns (response contract).
_TOP_N = 3

# Per-regime weighted-screen config (P1.1). Lives next to config/screens/.
_REGIME_CONFIG_FILENAME = "regime_screens.yaml"

# Fallback screen names (filename stems) per regime — used when neither the
# config file nor any screen YAML carries usable regime information.
_FALLBACK_MAP: dict[str, list[str]] = {
    "strong_trend": [
        "trend-follower",
        "52week-breakout",
        "bull-flag-continuation",
    ],
    "ranging": [
        "mean-reversion",
        "low-vol-setup",
        "statistical-mean-reversion",
    ],
    "high_vol": [
        "institutional-swing-quality",
        "volatility-expansion",
        "volume-trend-accumulation",
    ],
}

_DEFAULT_SCORE = 0.5  # neutral fallback for missing data fields

# Simple dict-based cache:  key = f"{regime}:{date_key}"  ->  list of ScreenConfig
_selector_cache: dict[str, list[ScreenConfig]] = {}

# Process-lifetime cache of config/regime_screens.yaml ("regimes" mapping).
# Config changes require a restart — acceptable for an ops-tuned file.
_regime_config_cache: dict[str, Any] | None = None


# ═══════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════


class _ConfigScreenEntry(NamedTuple):
    """One weighted entry from config/regime_screens.yaml."""

    name: str
    weight: float
    role: str  # "primary" | "defensive"


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


def _load_regime_config() -> dict[str, Any]:
    """Load the per-regime screen-weight config.

    Returns the ``regimes`` mapping from ``config/regime_screens.yaml``, or
    an empty dict on any failure/absence — callers then fall back to
    heuristic scoring. Loaded once per process.
    """
    global _regime_config_cache
    if _regime_config_cache is not None:
        return _regime_config_cache

    try:
        path = _resolve_screens_dir().parent / _REGIME_CONFIG_FILENAME
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        regimes = data.get("regimes") if isinstance(data, dict) else None
        if not isinstance(regimes, dict):
            log.warning(
                "regime_config_invalid_structure",
                path=str(path),
            )
            regimes = {}
        _regime_config_cache = regimes
    except FileNotFoundError:
        log.info("regime_config_not_found_using_heuristics")
        _regime_config_cache = {}
    except Exception:
        log.warning("regime_config_read_failed", path=_REGIME_CONFIG_FILENAME, exc_info=True)
        _regime_config_cache = {}

    return _regime_config_cache


def _parse_config_entries(raw: Any) -> list[_ConfigScreenEntry]:
    """Parse and validate one regime's YAML entry list, skipping garbage."""
    entries: list[_ConfigScreenEntry] = []
    if not isinstance(raw, list):
        return entries
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        try:
            weight = float(item.get("weight", 0.0))
        except (TypeError, ValueError):
            weight = 0.0
        role = str(item.get("role") or "primary").strip().lower()
        entries.append(_ConfigScreenEntry(name=name.strip(), weight=weight, role=role))
    return entries


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
        """Run the full selection algorithm — no caching applied here.

        Precedence: config-driven weights → heuristic scoring → fallback map.
        """
        configured = self._select_from_config(regime)
        if configured:
            return configured

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

    # ── config-driven selection (P1.1) ────────────────────

    def _select_from_config(self, regime: str) -> list[ScreenConfig]:
        """Select screens from the per-regime weighted config.

        Takes the top-_TOP_N entries by weight, guaranteeing exactly one
        ``role: defensive`` secondary in the final mix (replacing the
        weakest primary slot when needed). Returns [] when the regime has
        no usable config entry.
        """
        regimes_cfg = _load_regime_config()
        if not regimes_cfg:
            return []

        entries = _parse_config_entries(regimes_cfg.get(regime))
        if not entries:
            return []

        ordered = sorted(entries, key=lambda e: e.weight, reverse=True)
        primaries = [e for e in ordered if e.role != "defensive"]
        defensives = [e for e in ordered if e.role == "defensive"]

        picked = [e.name for e in primaries[:_TOP_N]]
        if defensives:
            top_defensive = defensives[0].name
            if top_defensive not in picked:
                if len(picked) >= _TOP_N:
                    picked[-1] = top_defensive  # swap out weakest primary slot
                else:
                    picked.append(top_defensive)

        loaded = list(self._load_screens(picked))
        if len(loaded) < _TOP_N:
            # Backfill from remaining weighted candidates so a broken
            # template doesn't shrink the mix below three screens.
            loaded_names = {s.name for s in loaded}
            all_picked = set(picked)
            remaining = [e.name for e in ordered if e.name not in all_picked]
            for name in remaining:
                if len(loaded) >= _TOP_N:
                    break
                for s in self._load_screens([name]):
                    if s.name not in loaded_names:
                        loaded.append(s)
                        loaded_names.add(s.name)
        if not loaded:
            self._log.warning(
                "regime_config_screens_failed_to_load",
                regime=regime,
                screens=picked,
            )
            return []

        self._log.info(
            "screens_selected_from_config",
            regime=regime,
            screens=[s.name for s in loaded],
        )
        return list(loaded)

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
