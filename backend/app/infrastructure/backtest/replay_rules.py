"""H-09 replay rules (D-78) — v0.1 vs v0.2 geometry on one signal stream.

The replay is exploratory: it answers "does the v0.2 geometry beat the v0.1
geometry on the same signals?" It is never forward evidence.

Both arms share everything that decides *whether* a trade exists:

- the signal stream (the D-71 engine's entry list),
- the entry zone and stop (``build_geometry``),
- the D-73 limit fill (``evaluate_fill``),
- the same-session stop,
- costs and sizing.

They differ only in what Bundle A changed:

- target selection,
- the gate's R:R floor,
- the exit policy.

This module is pure: no I/O, no database, no network. ``replay.py`` owns the
orchestration and the ledger.

Parity is deliberate, not accidental. ``v01_targets`` mirrors
``synthesis._get_structural_targets_long``; ``v01_gate`` and ``v02_gate`` call
the production ``gate.evaluate_risk_reward``; the exits call the production
``exits.infer_exit`` / ``exit_policy.simulate_exit``. If those change, the
parity tests fail loudly instead of silently moving the baseline.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Iterable

import pandas as pd

from backend.app.core.logging import get_logger
from backend.app.domain.ticker_analysis import technical
from backend.app.domain.workflow import exit_policy as exit_policy_mod
from backend.app.domain.workflow import exits as exits_mod
from backend.app.domain.workflow import gate as gate_mod
from backend.app.domain.workflow import pending as pending_mod
from backend.app.domain.workflow import pnl as pnl_mod

log = get_logger("conflu.backtest.replay_rules")

RULES_V01 = "v0.1"
RULES_V02 = "v0.2"
RULES_VERSIONS = (RULES_V01, RULES_V02)

# Frozen H-09 constants (§11 of the plan, D-78). Changing any of these is a new
# exploratory design, not an amendment.
ATR_PERIOD = 14
SWING_LOOKBACK = 5
MAX_STRUCTURE_MULT = 1.5
ENTRY_ZONE_ATR_MULT = 0.5
MIN_ZONE_PCT = 1.5
STOP_ATR_MULT = 2.0
FILL_EXPIRY_SESSIONS = 3
V01_MAX_HOLD_DAYS = 30
RISK_PCT = 1.0
ACCOUNT_VALUE = 100_000.0

# The signal engine is frozen separately from the plan geometry: it defines the
# population, so it must not move between arms or runs.
SIGNAL_STOP_ATR_MULT = 2.0
SIGNAL_TARGET_ATR_MULT = 3.0
SIGNAL_MAX_HOLD_BARS = 15

EVIDENCE_LABEL = "exploratory_h09_not_evidence"


# ── Geometry ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PlanGeometry:
    """The shared entry zone and stop for both arms (signal-close basis)."""

    close: float
    atr: float
    entry_low: float
    entry_high: float
    stop_loss: float
    width_pct: float

    @property
    def risk_per_share(self) -> float:
        return self.entry_low - self.stop_loss


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def build_geometry(
    close: Any,
    atr: Any,
    *,
    entry_zone_atr_mult: float = ENTRY_ZONE_ATR_MULT,
    min_zone_pct: float = MIN_ZONE_PCT,
    stop_atr_mult: float = STOP_ATR_MULT,
) -> PlanGeometry | None:
    """Build the frozen entry zone and stop from the signal bar.

    ``entry_low`` is the D-73 limit (the planned fill). The stop is 2×ATR below
    the signal close, matching the live plan's fallback branch. Returns ``None``
    when the geometry cannot produce a long trade with positive risk.
    """
    price = _finite(close)
    atr_value = _finite(atr)
    if price is None or price <= 0 or atr_value is None or atr_value <= 0:
        return None

    width_pct = max(entry_zone_atr_mult * atr_value / price, min_zone_pct / 100.0)
    entry_low = round(price * (1.0 - width_pct), 2)
    entry_high = round(price * (1.0 + 0.5 * width_pct), 2)
    stop_loss = round(price - stop_atr_mult * atr_value, 2)
    if stop_loss <= 0 or entry_low <= stop_loss:
        return None

    return PlanGeometry(
        close=round(price, 4),
        atr=round(atr_value, 4),
        entry_low=entry_low,
        entry_high=entry_high,
        stop_loss=stop_loss,
        width_pct=round(width_pct, 6),
    )


def atr_at(
    frame: pd.DataFrame,
    signal_date: str,
    *,
    period: int = ATR_PERIOD,
) -> float | None:
    """ATR(``period``) on the signal bar, using only bars up to that close."""
    if frame is None or frame.empty:
        return None
    ts = pd.Timestamp(signal_date)
    window = frame.loc[:ts]
    if len(window) < period + 1:
        return None
    try:
        import pandas_ta as ta

        series = ta.atr(
            window["High"], window["Low"], window["Close"], length=period
        )
    except Exception:  # noqa: BLE001 - missing/invalid indicator is "no ATR"
        return None
    if series is None or len(series) == 0:
        return None
    value = _finite(series.iloc[-1])
    if value is None or value <= 0:
        return None
    return round(value, 2)


# ── Structural levels ────────────────────────────────────────────────────


@dataclass(frozen=True)
class StructureLevels:
    """As-of structural levels, OHLCV only (no TradingView resistance)."""

    key_resistance: tuple[float, ...] = ()
    key_support: tuple[float, ...] = ()
    swing_highs: tuple[float, ...] = ()
    swing_lows: tuple[float, ...] = ()


def structural_levels(
    frame: pd.DataFrame,
    *,
    close: float,
    atr: float | None,
) -> StructureLevels:
    """Swing highs/lows and clustered key levels through the signal close.

    The frame must already be truncated at the signal date. Because swing
    detection needs ``lookback`` bars on both sides, the last five bars can
    never be swings — that is the honest, no-look-ahead behaviour.
    """
    if frame is None or frame.empty:
        return StructureLevels()
    swings = technical._detect_swings(frame, lookback=SWING_LOOKBACK)  # noqa: SLF001
    atr_pct = (atr / close * 100.0) if atr and close > 0 else None
    key_resistance, key_support = technical._find_key_levels(  # noqa: SLF001
        swings, frame, atr_pct, close
    )
    return StructureLevels(
        key_resistance=tuple(float(level) for level in key_resistance),
        key_support=tuple(float(level) for level in key_support),
        swing_highs=tuple(float(item["price"]) for item in swings.get("highs", [])),
        swing_lows=tuple(float(item["price"]) for item in swings.get("lows", [])),
    )


# ── Arm plans ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PlanDecision:
    """One arm's plan: targets, gate verdict and provenance."""

    arm: str
    family: str | None = None
    targets: tuple[float, ...] = ()
    rejection: str | None = None
    rejection_detail: str = ""
    gate_verdict: str | None = None
    gate_note: str | None = None
    plan_rr: float | None = None
    target_1_r: float | None = None
    stretch_rr: float | None = None

    @property
    def has_plan(self) -> bool:
        return not self.rejection and bool(self.targets)

    @property
    def accepted(self) -> bool:
        """PASS or CONDITIONAL — the trade goes in the policy book."""
        return self.has_plan and self.gate_verdict in ("PASS", "CONDITIONAL")


def _gate(
    geometry: PlanGeometry,
    targets: Iterable[float],
    *,
    family: str | None,
    risk_reward: float | None,
    symbol: str = "",
) -> tuple[str | None, str | None]:
    """Run production gate step 5 and map it to PASS / CONDITIONAL / FAIL."""
    levels = list(targets)
    if not levels or risk_reward is None or not math.isfinite(risk_reward):
        return "FAIL", "no finite plan R:R to evaluate"
    result = gate_mod.evaluate_risk_reward(
        gate_mod.GateInput(
            symbol=symbol,
            price=geometry.close,
            entry_low=geometry.entry_low,
            entry_high=geometry.entry_high,
            stop_loss=geometry.stop_loss,
            targets=levels,
            risk_reward=risk_reward,
            setup_family=family,
        )
    )
    if result.passed:
        return "PASS", result.note
    if result.conditional:
        return "CONDITIONAL", result.note
    return "FAIL", result.note


def v01_targets(
    close: float,
    atr: float | None,
    levels: StructureLevels,
) -> list[float]:
    """Mirror ``synthesis._get_structural_targets_long`` exactly.

    Structural levels above the close (up to 1.5×), plus the measured move;
    when nothing structural exists, ATR 2/3/4 or the fixed 8/15/25% fallback.
    Keep the **highest** three: v0.1 let a far level excuse a near first payout.
    """
    max_level = close * MAX_STRUCTURE_MULT
    structural: list[float] = []

    for resistance in levels.key_resistance:
        if close < resistance <= max_level and resistance not in structural:
            structural.append(round(resistance, 2))
    for swing_high in levels.swing_highs:
        if close < swing_high <= max_level and swing_high not in structural:
            structural.append(round(swing_high, 2))

    if levels.swing_highs and levels.swing_lows:
        range_height = max(levels.swing_highs) - min(levels.swing_lows)
        if range_height > 0:
            projection = round(close + range_height, 2)
            if close < projection <= max_level and projection not in structural:
                structural.append(projection)

    if not structural:
        atr_value = _finite(atr)
        if atr_value is not None and atr_value > 0:
            structural = [
                round(close + atr_value * 2, 2),
                round(close + atr_value * 3, 2),
                round(close + atr_value * 4, 2),
            ]
        else:
            structural = [
                round(close * 1.08, 2),
                round(close * 1.15, 2),
                round(close * 1.25, 2),
            ]
        structural = [level for level in structural if level <= max_level]

    return sorted(set(structural))[-3:]


def v01_plan(
    geometry: PlanGeometry,
    levels: StructureLevels,
    *,
    symbol: str = "",
) -> PlanDecision:
    """v0.1 plan: last-target / midpoint Plan R, legacy gate tiers."""
    targets = v01_targets(geometry.close, geometry.atr, levels)
    midpoint = (geometry.entry_low + geometry.entry_high) / 2.0
    risk = midpoint - geometry.stop_loss
    rr = (
        round((targets[-1] - midpoint) / risk, 2)
        if targets and risk > 0
        else None
    )
    target_1_r = (
        round((targets[0] - midpoint) / risk, 2)
        if targets and risk > 0
        else None
    )
    verdict, note = _gate(
        geometry, targets, family=None, risk_reward=rr, symbol=symbol
    )
    return PlanDecision(
        arm=RULES_V01,
        targets=tuple(targets),
        gate_verdict=verdict,
        gate_note=note,
        plan_rr=rr,
        target_1_r=target_1_r,
    )


def v02_plan(
    geometry: PlanGeometry,
    levels: StructureLevels,
    family: str,
    *,
    symbol: str = "",
) -> PlanDecision:
    """v0.2 plan: nearest structural T1 inside the family band, or rejection."""
    candidates = exit_policy_mod.collect_candidates(
        price=geometry.close,
        key_resistance=levels.key_resistance,
        swing_highs=levels.swing_highs,
        swing_lows=levels.swing_lows,
    )
    selection = exit_policy_mod.select_targets(
        entry_low=geometry.entry_low,
        stop_loss=geometry.stop_loss,
        family=family,
        candidates=candidates,
    )
    if not selection.ok:
        return PlanDecision(
            arm=RULES_V02,
            family=family,
            rejection=selection.rejection,
            rejection_detail=selection.detail,
        )

    verdict, note = _gate(
        geometry,
        selection.targets,
        family=family,
        risk_reward=selection.t1_r,
        symbol=symbol,
    )
    return PlanDecision(
        arm=RULES_V02,
        family=family,
        targets=selection.targets,
        gate_verdict=verdict,
        gate_note=note,
        plan_rr=selection.t1_r,
        target_1_r=selection.t1_r,
        stretch_rr=selection.stretch_r,
    )


# ── Fills ────────────────────────────────────────────────────────────────


def frame_to_bars(
    frame: pd.DataFrame,
    *,
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    """Normalize a daily frame to ascending OHLC bars, dropping bad rows."""
    if frame is None or frame.empty:
        return []
    sliced = frame
    if start is not None:
        sliced = sliced.loc[sliced.index >= pd.Timestamp(start)]
    if end is not None:
        sliced = sliced.loc[sliced.index <= pd.Timestamp(end)]

    bars: list[dict[str, Any]] = []
    for timestamp, row in sliced.iterrows():
        open_ = _finite(row.get("Open"))
        high = _finite(row.get("High"))
        low = _finite(row.get("Low"))
        close = _finite(row.get("Close"))
        if None in (open_, high, low, close):
            continue
        bars.append(
            {
                "date": pd.Timestamp(timestamp).date().isoformat(),
                "open": float(open_),
                "high": float(high),
                "low": float(low),
                "close": float(close),
            }
        )
    return bars


def evaluate_fill(
    geometry: PlanGeometry,
    signal_date: str,
    bars: list[dict[str, Any]],
    *,
    expiry_sessions: int = FILL_EXPIRY_SESSIONS,
    today: str | None = None,
) -> pending_mod.FillDecision:
    """D-73 limit fill from bars strictly after the signal date."""
    order = {
        "signal_date": signal_date,
        "order_type": pending_mod.ORDER_LIMIT,
        "entry_low": geometry.entry_low,
        "entry_high": geometry.entry_high,
        "limit_price": geometry.entry_low,
        "stop_loss": geometry.stop_loss,
        "expires_after_sessions": int(expiry_sessions),
    }
    return pending_mod.evaluate_order(order, bars, today=today)


# ── Sizing and accounting ────────────────────────────────────────────────


def shares_for(
    fill_price: float,
    stop_loss: float,
    *,
    risk_pct: float = RISK_PCT,
    account_value: float = ACCOUNT_VALUE,
) -> float | None:
    """Shares for a fixed fractional risk; matches the journal's 2dp quantity."""
    risk_per_share = fill_price - stop_loss
    if risk_per_share <= 0 or account_value <= 0 or risk_pct <= 0:
        return None
    return round(account_value * risk_pct / 100.0 / risk_per_share, 2)


def accounting(
    fill_price: float,
    exit_price: float,
    stop_loss: float,
    shares: float | None,
) -> dict[str, Any]:
    """Canonical realized R (gross) and dollar P&L (net of costs)."""
    risk = fill_price - stop_loss
    realized_r = (exit_price - fill_price) / risk if risk > 0 else None
    money = pnl_mod.dollar_pnl(fill_price, exit_price, shares) or {}
    return {
        "realized_r": None if realized_r is None else round(realized_r, 4),
        "pnl_usd": money.get("pnl_usd"),
        "pnl_gross_usd": money.get("pnl_gross_usd"),
        "costs_usd": money.get("costs_usd"),
    }


# ── Exits ────────────────────────────────────────────────────────────────


@dataclass
class TradeOutcome:
    """One arm's exit result, including the conservative data-edge close."""

    exit_price: float | None = None
    exit_date: str | None = None
    exit_reason: str | None = None
    realized_r: float | None = None
    pnl_usd: float | None = None
    pnl_gross_usd: float | None = None
    costs_usd: float | None = None
    bars_held: int = 0
    mfe_r: float | None = None
    mae_r: float | None = None
    plan_adherence: float | None = None
    legs: list[dict[str, Any]] = field(default_factory=list)
    censored: bool = False


def _leg(
    date: str,
    price: float,
    size_pct: float,
    shares: float | None,
    reason: str,
    realized_r: float | None,
) -> dict[str, Any]:
    return {
        "date": str(date)[:10],
        "price": round(float(price), 4),
        "shares": None if shares is None else round(float(shares), 4),
        "size_pct": round(float(size_pct), 4),
        "reason": reason,
        "r": None if realized_r is None else round(float(realized_r), 4),
    }


def same_session_stop(fill: pending_mod.FillDecision, stop_loss: float) -> bool:
    """True when the fill bar itself traded through the stop after entry."""
    bar = fill.bar or {}
    try:
        return float(bar["low"]) <= float(stop_loss)
    except (KeyError, TypeError, ValueError):
        return False


def stop_outcome(
    fill: pending_mod.FillDecision,
    stop_loss: float,
    shares: float | None,
) -> TradeOutcome:
    """Same-session stop-out at the stop (D-73 conservative ordering)."""
    fill_price = float(fill.fill_price or 0.0)
    money = accounting(fill_price, float(stop_loss), stop_loss, shares)
    day = str(fill.fill_date or "")
    return TradeOutcome(
        exit_price=round(float(stop_loss), 2),
        exit_date=day,
        exit_reason=exits_mod.EXIT_STOP,
        realized_r=money["realized_r"],
        pnl_usd=money["pnl_usd"],
        pnl_gross_usd=money["pnl_gross_usd"],
        costs_usd=money["costs_usd"],
        bars_held=1,
        mfe_r=None,
        mae_r=-1.0,
        plan_adherence=1.0,
        legs=[
            _leg(
                day, float(stop_loss), 100.0, shares,
                exits_mod.EXIT_STOP, money["realized_r"],
            )
        ],
    )


def _censor(
    bars: list[dict[str, Any]],
    fill_price: float,
    stop_loss: float,
    shares: float | None,
    *,
    mfe_r: float | None = None,
    mae_r: float | None = None,
) -> TradeOutcome:
    """Close an unresolved trade at the last available close (``eod``)."""
    if not bars:
        return TradeOutcome(censored=True)
    last = bars[-1]
    money = accounting(fill_price, float(last["close"]), stop_loss, shares)
    return TradeOutcome(
        exit_price=round(float(last["close"]), 2),
        exit_date=str(last["date"]),
        exit_reason="eod",
        realized_r=money["realized_r"],
        pnl_usd=money["pnl_usd"],
        pnl_gross_usd=money["pnl_gross_usd"],
        costs_usd=money["costs_usd"],
        bars_held=len(bars),
        mfe_r=mfe_r,
        mae_r=mae_r,
        plan_adherence=None,
        legs=[
            _leg(
                str(last["date"]), float(last["close"]), 100.0, shares,
                "eod", money["realized_r"],
            )
        ],
        censored=True,
    )


def v01_outcome(
    bars: list[dict[str, Any]],
    *,
    fill: pending_mod.FillDecision,
    stop_loss: float,
    targets: Iterable[float],
    shares: float | None,
    max_hold_days: int = V01_MAX_HOLD_DAYS,
) -> TradeOutcome:
    """v0.1 exit: ``infer_exit`` on the stored targets, 30-day time stop."""
    fill_price = float(fill.fill_price or 0.0)
    hold_bars = exits_mod.hold_limit_bars(bars, fill.fill_date, max_hold_days)
    result = exits_mod.infer_exit(
        bars,
        entry=fill_price,
        stop=float(stop_loss),
        targets=list(targets),
        max_hold_days=hold_bars,
        exclude_entry_bar_excursions=True,
    )
    if result.exit_price is None or result.exit_date is None:
        return _censor(
            bars, fill_price, stop_loss, shares,
            mfe_r=result.mfe_r, mae_r=result.mae_r,
        )

    money = accounting(fill_price, float(result.exit_price), stop_loss, shares)
    plan_adherence = (
        1.0 if result.exit_reason in (
            exits_mod.EXIT_STOP,
            exits_mod.EXIT_TARGET_1,
            exits_mod.EXIT_TARGET_2,
        ) else 0.5
    )
    return TradeOutcome(
        exit_price=round(float(result.exit_price), 2),
        exit_date=str(result.exit_date),
        exit_reason=result.exit_reason,
        realized_r=money["realized_r"],
        pnl_usd=money["pnl_usd"],
        pnl_gross_usd=money["pnl_gross_usd"],
        costs_usd=money["costs_usd"],
        bars_held=result.bars_held,
        mfe_r=result.mfe_r,
        mae_r=result.mae_r,
        plan_adherence=plan_adherence,
        legs=[
            _leg(
                str(result.exit_date), float(result.exit_price), 100.0, shares,
                str(result.exit_reason), money["realized_r"],
            )
        ],
    )


def v02_outcome(
    bars: list[dict[str, Any]],
    *,
    fill: pending_mod.FillDecision,
    stop_loss: float,
    targets: Iterable[float],
    family: str,
    atr: float | None,
    shares: float | None,
) -> TradeOutcome:
    """v0.2 exit: the frozen family policy via ``simulate_exit``."""
    fill_price = float(fill.fill_price or 0.0)
    simulation = exit_policy_mod.simulate_exit(
        bars,
        entry=fill_price,
        stop=float(stop_loss),
        targets=list(targets),
        family=family,
        shares=shares,
        atr=atr,
        entry_date=fill.fill_date,
    )
    if simulation.exit_price is None or simulation.exit_date is None:
        return _censor(
            bars, fill_price, stop_loss, shares,
            mfe_r=simulation.mfe_r, mae_r=simulation.mae_r,
        )

    money = accounting(fill_price, float(simulation.exit_price), stop_loss, shares)
    return TradeOutcome(
        exit_price=round(float(simulation.exit_price), 2),
        exit_date=str(simulation.exit_date),
        exit_reason=simulation.exit_reason,
        realized_r=money["realized_r"],
        pnl_usd=money["pnl_usd"],
        pnl_gross_usd=money["pnl_gross_usd"],
        costs_usd=money["costs_usd"],
        bars_held=simulation.bars_held,
        mfe_r=simulation.mfe_r,
        mae_r=simulation.mae_r,
        plan_adherence=simulation.plan_adherence,
        legs=_legs(simulation),
        censored=False,
    )


def _legs(simulation: exit_policy_mod.ExitSimulation) -> list[dict[str, Any]]:
    raw = simulation.legs_json()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:  # noqa: BLE001 - corrupt legs stay visible as no legs
        return []
    return parsed if isinstance(parsed, list) else []


__all__ = [
    "RULES_V01",
    "RULES_V02",
    "RULES_VERSIONS",
    "EVIDENCE_LABEL",
    "ATR_PERIOD",
    "SWING_LOOKBACK",
    "ENTRY_ZONE_ATR_MULT",
    "MIN_ZONE_PCT",
    "STOP_ATR_MULT",
    "FILL_EXPIRY_SESSIONS",
    "V01_MAX_HOLD_DAYS",
    "RISK_PCT",
    "ACCOUNT_VALUE",
    "SIGNAL_STOP_ATR_MULT",
    "SIGNAL_TARGET_ATR_MULT",
    "SIGNAL_MAX_HOLD_BARS",
    "PlanGeometry",
    "PlanDecision",
    "TradeOutcome",
    "StructureLevels",
    "build_geometry",
    "atr_at",
    "structural_levels",
    "v01_targets",
    "v01_plan",
    "v02_plan",
    "frame_to_bars",
    "evaluate_fill",
    "shares_for",
    "accounting",
    "same_session_stop",
    "stop_outcome",
    "v01_outcome",
    "v02_outcome",
]
