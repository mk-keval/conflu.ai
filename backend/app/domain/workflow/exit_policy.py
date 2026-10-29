"""Bundle A exit policy (D-77) — family targets + multi-leg simulation.

This is the v0.2 exit contract. It replaces the v0.1 walker (``exits.infer_exit``)
for rows that carry a ``setup_family``. v0.1 rows keep ``setup_family = NULL`` and
are never re-simulated:

    setup_family = NULL  ->  legacy single exit (``exits.infer_exit``)
    setup_family = ...   ->  this module

Two pure pieces:

1. **Target selection** — structural resistance / swing highs / measured move,
   nearest-first inside the family band. No ATR or percentage fallback: a trade
   with no structural objective is rejected (D-77/A4).
2. **Exit simulation** — family-specific tranches, breakeven at +1R, ATR trail
   after T1 and a calendar-day time stop. One function is shared by the live
   exit sync and the H-09 replay so the rules cannot drift.

Conventions match v0.1 (conservative):
- the entry bar is excluded (bar 0 unless the bars start after the entry date);
- a bar that touches both the stop and a target is ambiguous and the stop wins;
- a gap through the stop fills at the open; a gap above a target fills at the
  target;
- breakeven is evaluated at the close and active next bar;
- the trail never loosens.

No I/O. ``simulate_exit`` returns an ``ExitSimulation`` whose
``as_exit_columns`` produces the journal exit columns.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Iterable, Literal, Mapping

from backend.app.domain.workflow import pnl as pnl_mod
from backend.app.domain.workflow.exits import (
    EXIT_STOP,
    EXIT_TARGET_1,
    EXIT_TARGET_2,
    EXIT_TIME,
    hold_limit_bars,
)

SetupFamily = Literal["trend", "breakout", "mean_reversion", "rotation", "unknown"]
SETUP_FAMILIES = ("trend", "breakout", "mean_reversion", "rotation", "unknown")

EXIT_TRAIL = "trail"
EXIT_SCALE_OUT = "scale_out"

# Rejection labels (D-77/A4). The verdict and the gate carry the same string.
REJECT_TOO_CLOSE = "target too close"
REJECT_TOO_FAR = "target too far"
REJECT_NO_OBJECTIVE = "no structural objective"
REJECT_INVALID_GEOMETRY = "invalid plan geometry"


@dataclass(frozen=True)
class FamilyPolicy:
    """One family's frozen band, exit fractions and management rules."""

    family: str
    half_size_floor_r: float
    full_size_floor_r: float
    max_t1_r: float
    time_stop_days: int
    t1_fraction: float
    t2_fraction: float
    breakeven_at_r: float | None
    trail_atr_multiple: float | None


# D-77 3.3 (bands) and 5.1/5.2 (exits). The half-size floor is the gate's
# CONDITIONAL floor; the full-size floor is the PASS floor.
FAMILY_POLICIES: dict[str, FamilyPolicy] = {
    "trend": FamilyPolicy(
        family="trend",
        half_size_floor_r=2.0,
        full_size_floor_r=2.5,
        max_t1_r=4.0,
        time_stop_days=30,
        t1_fraction=1.0 / 3.0,
        t2_fraction=1.0 / 3.0,
        breakeven_at_r=1.0,
        trail_atr_multiple=2.0,
    ),
    "breakout": FamilyPolicy(
        family="breakout",
        half_size_floor_r=2.0,
        full_size_floor_r=2.5,
        max_t1_r=5.0,
        time_stop_days=20,
        t1_fraction=0.5,
        t2_fraction=0.0,
        breakeven_at_r=1.0,
        trail_atr_multiple=2.5,
    ),
    "mean_reversion": FamilyPolicy(
        family="mean_reversion",
        half_size_floor_r=1.25,
        full_size_floor_r=1.5,
        max_t1_r=2.5,
        time_stop_days=10,
        t1_fraction=1.0,
        t2_fraction=0.0,
        breakeven_at_r=None,
        trail_atr_multiple=None,
    ),
    "rotation": FamilyPolicy(
        family="rotation",
        half_size_floor_r=1.75,
        full_size_floor_r=2.0,
        max_t1_r=3.0,
        time_stop_days=15,
        t1_fraction=1.0,
        t2_fraction=0.0,
        breakeven_at_r=1.0,
        trail_atr_multiple=None,
    ),
    "unknown": FamilyPolicy(
        family="unknown",
        half_size_floor_r=2.0,
        full_size_floor_r=2.5,
        max_t1_r=4.0,
        time_stop_days=20,
        t1_fraction=1.0,
        t2_fraction=0.0,
        breakeven_at_r=1.0,
        trail_atr_multiple=None,
    ),
}

# Screen -> family (D-77/A3). Keys are normalized display names: lowercase,
# punctuation collapsed to single spaces. Slugs (``trend-follower-v2``) normalize
# to the same key, so the brief's display name and the config's slug agree.
_TREND_SCREENS = frozenset({
    "trend follower",
    "trend follower v2",
    "trend leader",
    "trend pullback",
    "trend pullback v2",
    "institutional trend follower",
    "institutional trend follower mtf",
    "institutional swing quality",
    "institutional quality v2",
    "quality trend fundamentals",
    "high conviction stack",
    "institutional accumulation",
})
_BREAKOUT_SCREENS = frozenset({
    "52 week breakout",
    "bull flag continuation",
    "vcp breakout",
    "volatility expansion",
    "low vol setup",
})
_MEAN_REVERSION_SCREENS = frozenset({
    "mean reversion",
    "statistical mean reversion",
})
_ROTATION_PREFIX = "sector rotation"


def _screen_key(name: Any) -> str:
    text = str(name or "").strip().lower()
    if not text:
        return ""
    out: list[str] = []
    for char in text:
        out.append(char if char.isalnum() else " ")
    return " ".join("".join(out).split())


def family_for_screen(screen_name: Any) -> SetupFamily:
    """Map a brief ``screen_name`` to a setup family; unmapped -> ``unknown``."""
    key = _screen_key(screen_name)
    if key in _TREND_SCREENS:
        return "trend"
    if key in _BREAKOUT_SCREENS:
        return "breakout"
    if key in _MEAN_REVERSION_SCREENS:
        return "mean_reversion"
    if key.startswith(_ROTATION_PREFIX):
        return "rotation"
    return "unknown"


def normalize_family(value: Any) -> str | None:
    """Coerce a stored/request family to a known value; None when invalid."""
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return text if text in SETUP_FAMILIES else None


def policy_for(family: Any) -> FamilyPolicy:
    """Policy for a family; an invalid/absent family behaves as ``unknown``."""
    return FAMILY_POLICIES[normalize_family(family) or "unknown"]


# ── Target selection ────────────────────────────────────────────────────


@dataclass(frozen=True)
class TargetSelection:
    """Selected structural levels plus the rejection reason when none fit."""

    family: str
    targets: tuple[float, ...] = ()
    rejection: str | None = None
    detail: str = ""
    t1_r: float | None = None
    stretch_r: float | None = None
    candidates: tuple[float, ...] = ()

    @property
    def ok(self) -> bool:
        return self.rejection is None and bool(self.targets)


def _positive(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number) or number <= 0:
        return None
    return number


def collect_candidates(
    *,
    price: Any,
    key_resistance: Iterable[Any] | None = None,
    swing_highs: Iterable[Any] | None = None,
    swing_lows: Iterable[Any] | None = None,
) -> list[float]:
    """Structural levels above price within ``1.5 x price`` (D-77 3.1).

    Resistance and swing highs are resistance. When price is above every known
    level, the prior swing range is projected as a measured move. There is no
    ATR/percentage fallback: an empty list means "no structural objective".
    """
    close = _positive(price)
    if close is None:
        return []

    max_level = close * 1.5
    levels: set[float] = set()
    resistances = list(key_resistance or [])
    highs_raw = list(swing_highs or [])
    lows_raw = list(swing_lows or [])

    for raw in resistances + highs_raw:
        level = _positive(raw)
        if level is not None and close < level <= max_level:
            levels.add(round(level, 2))

    highs = [v for v in (_positive(x) for x in highs_raw) if v is not None]
    lows = [v for v in (_positive(x) for x in lows_raw) if v is not None]
    if highs and lows:
        range_height = max(highs) - min(lows)
        if range_height > 0:
            projection = round(close + range_height, 2)
            if close < projection <= max_level:
                levels.add(projection)

    return sorted(levels)


def select_targets(
    *,
    entry_low: Any,
    stop_loss: Any,
    family: Any,
    candidates: Iterable[Any],
) -> TargetSelection:
    """Pick T1/T2/T3 nearest-first inside the family band (D-77 3.2).

    R is measured from the planned fill: ``(level - entry_low) / (entry_low - stop)``.
    A trade with no candidate inside the band is rejected, never given a
    manufactured target.
    """
    fam = normalize_family(family) or "unknown"
    policy = FAMILY_POLICIES[fam]

    entry = _positive(entry_low)
    stop = _positive(stop_loss)
    if entry is None or stop is None or entry <= stop:
        return TargetSelection(
            family=fam, rejection=REJECT_INVALID_GEOMETRY,
            detail=f"entry_low={entry_low} stop={stop_loss}",
        )

    risk = entry - stop
    levels = sorted({
        level for level in (_positive(raw) for raw in candidates)
        if level is not None and level > entry
    })
    if not levels:
        return TargetSelection(
            family=fam, rejection=REJECT_NO_OBJECTIVE,
            detail="no structural level above the planned fill",
        )

    def r_of(level: float) -> float:
        return (level - entry) / risk

    in_band = [
        level for level in levels
        if policy.half_size_floor_r <= r_of(level) <= policy.max_t1_r
    ]

    if not in_band:
        above = [level for level in levels if r_of(level) > policy.max_t1_r]
        if above:
            nearest = above[0]
            nearest_r = r_of(nearest)
            return TargetSelection(
                family=fam, rejection=REJECT_TOO_FAR,
                detail=(
                    f"nearest above cap {nearest:.2f} is {nearest_r:.2f}R > "
                    f"{policy.max_t1_r:.2f}R cap"
                ),
                candidates=tuple(levels),
            )
        below = [level for level in levels if r_of(level) < policy.half_size_floor_r]
        return TargetSelection(
            family=fam, rejection=REJECT_TOO_CLOSE,
            detail=(
                f"highest {below[-1]:.2f} is {r_of(below[-1]):.2f}R < "
                f"{policy.half_size_floor_r:.2f}R floor"
            ) if below else "all levels below the planned fill",
            candidates=tuple(levels),
        )

    t1 = in_band[0]
    t1_index = levels.index(t1)
    t2 = levels[t1_index + 1] if t1_index + 1 < len(levels) else None
    t3 = levels[t1_index + 2] if t1_index + 2 < len(levels) else None

    targets = tuple(round(level, 2) for level in (t1, t2, t3) if level is not None)
    return TargetSelection(
        family=fam,
        targets=targets,
        t1_r=round(r_of(t1), 2),
        stretch_r=round(r_of(t3), 2) if t3 is not None else None,
        candidates=tuple(levels),
    )


# ── Exit simulation ─────────────────────────────────────────────────────


@dataclass
class ExitLeg:
    """One partial (or full) exit."""

    date: str
    price: float
    size_pct: float          # percent of the original position, 0-100
    shares: float | None
    reason: str
    r: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "price": round(self.price, 4),
            "shares": None if self.shares is None else round(self.shares, 4),
            "size_pct": round(self.size_pct, 4),
            "reason": self.reason,
            "r": round(self.r, 4),
        }


@dataclass
class ExitSimulation:
    """Result of one multi-leg exit walk."""

    exit_price: float | None
    exit_date: str | None
    exit_reason: str | None
    legs: list[ExitLeg] = field(default_factory=list)
    bars_held: int = 0
    ambiguous: bool = False
    mfe_r: float | None = None
    mae_r: float | None = None
    plan_adherence: float | None = None
    remaining_fraction: float = 0.0

    def legs_json(self) -> str | None:
        if not self.legs:
            return None
        return json.dumps([leg.as_dict() for leg in self.legs], separators=(",", ":"))

    def as_exit_columns(
        self,
        *,
        entry: Any,
        stop: Any,
        shares: Any,
    ) -> dict[str, Any]:
        """Journal exit columns for this simulation (empty when no exit fired)."""
        if self.exit_price is None or self.exit_date is None:
            return {}
        entry_f = _positive(entry)
        stop_f = _positive(stop)
        if entry_f is None or stop_f is None or entry_f <= stop_f:
            return {}
        try:
            shares_f = float(shares) if shares not in (None, "") else None
        except (TypeError, ValueError):
            shares_f = None

        realized_r = (self.exit_price - entry_f) / (entry_f - stop_f)
        money = pnl_mod.dollar_pnl(entry_f, self.exit_price, shares_f) or {}
        return {
            "date_closed": self.exit_date,
            "exit_price": round(self.exit_price, 2),
            "exit_reason": self.exit_reason,
            "realized_r": round(realized_r, 2),
            "pnl_usd": money.get("pnl_usd"),
            "pnl_gross_usd": money.get("pnl_gross_usd"),
            "costs_usd": money.get("costs_usd"),
            "mfe_r": None if self.mfe_r is None else round(self.mfe_r, 2),
            "mae_r": None if self.mae_r is None else round(self.mae_r, 2),
            "plan_adherence": self.plan_adherence,
            "exit_legs": self.legs_json(),
        }


def _bar_values(bar: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    try:
        return (
            float(bar["open"]), float(bar["high"]),
            float(bar["low"]), float(bar["close"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _plan_adherence(legs: list[ExitLeg]) -> float:
    """1.0 all planned legs fired; 0.5 trail/time stop on the remainder; 0.0 stop."""
    reasons = [leg.reason for leg in legs]
    if EXIT_STOP in reasons:
        return 0.0
    if any(reason in (EXIT_TRAIL, EXIT_TIME) for reason in reasons):
        return 0.5
    return 1.0


def simulate_exit(
    bars: list[dict[str, Any]],
    *,
    entry: Any,
    stop: Any,
    targets: Iterable[Any],
    family: Any,
    shares: Any = None,
    atr: Any = None,
    entry_date: str | None = None,
    max_hold_days: int | None = None,
    exclude_entry_bar_excursions: bool = True,
) -> ExitSimulation:
    """Walk daily bars after the entry bar and apply the family exit policy.

    ``bars`` begins on (or after) the entry date and is ascending. Bar 0 is the
    entry bar and is skipped; if the series starts strictly after ``entry_date``
    (missing fill-day bar), bar 0 is a normal hold bar.

    ``max_hold_days`` overrides the family time stop when supplied (the synthesis
    plan records the family value; the replay may pass the same value).
    """
    family_name = normalize_family(family) or "unknown"
    policy = FAMILY_POLICIES[family_name]

    entry_f = _positive(entry)
    stop_f = _positive(stop)
    levels = [level for level in (_positive(t) for t in targets) if level is not None]
    if (
        not bars or entry_f is None or stop_f is None
        or entry_f <= stop_f or not levels
    ):
        return ExitSimulation(None, None, None)

    risk = entry_f - stop_f
    t1 = levels[0]
    t2 = levels[1] if len(levels) > 1 else None

    plan: list[tuple[float, float, str]] = [(t1, policy.t1_fraction, EXIT_TARGET_1)]
    if policy.t2_fraction > 0 and t2 is not None:
        plan.append((t2, policy.t2_fraction, EXIT_TARGET_2))

    try:
        shares_f = float(shares) if shares not in (None, "") else None
    except (TypeError, ValueError):
        shares_f = None

    atr_f = _positive(atr)
    trail_distance = (
        policy.trail_atr_multiple * atr_f
        if policy.trail_atr_multiple is not None and atr_f is not None
        else 2.0 * risk
    )

    time_days = max_hold_days if max_hold_days is not None else policy.time_stop_days
    time_stop_bars = hold_limit_bars(bars, entry_date, time_days)

    legs: list[ExitLeg] = []
    remaining = 1.0
    next_leg = 0
    active_stop = stop_f
    trail_level: float | None = None
    breakeven_done = False
    highest_close = entry_f
    max_high: float | None = None
    min_low: float | None = None
    ambiguous = False
    final_bar = 0

    def _add_leg(price: float, fraction: float, reason: str, day: str) -> None:
        nonlocal remaining
        take = min(fraction, remaining)
        if take <= 0:
            return
        legs.append(ExitLeg(
            date=day,
            price=price,
            size_pct=take * 100.0,
            shares=None if shares_f is None else shares_f * take,
            reason=reason,
            r=(price - entry_f) / risk,
        ))
        remaining = round(remaining - take, 10)
        if remaining < 1e-9:
            remaining = 0.0

    def _finish(day: str, bars_held: int) -> ExitSimulation:
        weighted = sum(leg.price * leg.size_pct for leg in legs)
        weights = sum(leg.size_pct for leg in legs)
        vwap = weighted / weights if weights else None
        if not legs or vwap is None:
            return ExitSimulation(None, None, None, bars_held=bars_held)
        return ExitSimulation(
            exit_price=vwap,
            exit_date=day,
            exit_reason=EXIT_SCALE_OUT if len(legs) > 1 else legs[0].reason,
            legs=list(legs),
            bars_held=bars_held,
            ambiguous=ambiguous,
            mfe_r=None if max_high is None else (max_high - entry_f) / risk,
            mae_r=None if min_low is None else (min_low - entry_f) / risk,
            plan_adherence=_plan_adherence(legs),
            remaining_fraction=remaining,
        )

    for idx, bar in enumerate(bars):
        values = _bar_values(bar)
        if values is None:
            continue
        open_, high, low, close = values
        day = str(bar.get("date") or "")[:10]

        if idx == 0:
            starts_on_entry = (
                not entry_date or day <= str(entry_date)[:10]
            )
            if exclude_entry_bar_excursions or starts_on_entry:
                continue

        bars_held = idx + 1
        final_bar = bars_held
        max_high = high if max_high is None else max(max_high, high)
        min_low = low if min_low is None else min(min_low, low)

        # 1. Active stop (initial / breakeven / trail). A bar that also touches
        # an unfilled target is ambiguous and the stop wins.
        effective_stop = active_stop
        effective_reason = EXIT_STOP
        if trail_level is not None and trail_level > effective_stop:
            effective_stop = trail_level
            effective_reason = EXIT_TRAIL

        if open_ <= effective_stop or low <= effective_stop:
            unfilled = [price for price, _frac, _reason in plan[next_leg:]]
            ambiguous = any(high >= price for price in unfilled)
            fill = open_ if open_ <= effective_stop else effective_stop
            _add_leg(fill, remaining, effective_reason, day)
            return _finish(day, bars_held)

        # 2/3. Target limits, nearest first. A gap above a target fills at the
        # target (conservative; MFE records the gap).
        while next_leg < len(plan):
            price, fraction, reason = plan[next_leg]
            if high < price:
                break
            _add_leg(price, fraction, reason, day)
            next_leg += 1
            if remaining <= 0:
                break

        if remaining <= 0:
            return _finish(day, bars_held)

        # 4. Calendar time stop on the remainder, at the close.
        if time_stop_bars is not None and bars_held >= time_stop_bars:
            _add_leg(close, remaining, EXIT_TIME, day)
            return _finish(day, bars_held)

        # End-of-bar management, active next bar.
        highest_close = max(highest_close, close)
        if (
            not breakeven_done
            and policy.breakeven_at_r is not None
            and high >= entry_f + policy.breakeven_at_r * risk
        ):
            breakeven_done = True
            active_stop = max(active_stop, entry_f)
        if policy.trail_atr_multiple is not None and next_leg >= 1:
            candidate = max(entry_f, highest_close - trail_distance)
            if trail_level is None or candidate > trail_level:
                trail_level = candidate

    return ExitSimulation(
        None, None, None,
        legs=list(legs),
        bars_held=final_bar,
        ambiguous=ambiguous,
        mfe_r=None if max_high is None else (max_high - entry_f) / risk,
        mae_r=None if min_low is None else (min_low - entry_f) / risk,
        plan_adherence=None,
        remaining_fraction=remaining,
    )


__all__ = [
    "SETUP_FAMILIES",
    "EXIT_TRAIL",
    "EXIT_SCALE_OUT",
    "REJECT_TOO_CLOSE",
    "REJECT_TOO_FAR",
    "REJECT_NO_OBJECTIVE",
    "REJECT_INVALID_GEOMETRY",
    "FamilyPolicy",
    "FAMILY_POLICIES",
    "TargetSelection",
    "ExitLeg",
    "ExitSimulation",
    "family_for_screen",
    "normalize_family",
    "policy_for",
    "collect_candidates",
    "select_targets",
    "simulate_exit",
]
