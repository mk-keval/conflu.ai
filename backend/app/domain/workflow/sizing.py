"""Risk-based position sizing (plan Sec.2D).

Size follows the plan's governing rule, ported from the daily-ritual formula:

    size_pct = min(risk_budget_pct / stop_distance_pct * 100, cap)

Where:

- ``risk_budget_pct``   = 1.0  — 1% of account risked per trade (the engine's
                          ``RiskAssessment.max_risk_per_trade_pct`` default).
- ``stop_distance_pct`` = (entry - stop) / entry * 100  — the actual stop.
- ``cap``               = MAX_POSITION_SIZE_PCT = 25.0%  — a hard safety
                          backstop only. It matches the engine's effective
                          conviction ceiling (conviction_caps 0.25) so it
                          never conflicts with the backtest path. The size is
                          governed by risk, not by the cap (D-3: retire the
                          per-position notional cap as the primary control).
- ``MIN_SIZE_PCT``      = 0.5  — floor so a valid trade never rounds to zero.
- CONDITIONAL verdict → size halved (the plan's `×0.5` for partial approval).

Pure function — no I/O. The paper-trade script (1D) calls it with the gate
verdict and journal data.
"""

from __future__ import annotations

from math import isfinite

RISK_BUDGET_PCT = 1.0
MAX_POSITION_SIZE_PCT = 25.0  # hard backstop only; risk governs size (D-3)
MIN_SIZE_PCT = 0.5
CONDITIONAL_HALVING = 0.5     # CONDITIONAL verdict → trade half size
GATE_PASS = "PASS"
GATE_CONDITIONAL = "CONDITIONAL"


def stop_distance_pct(entry: float, stop: float) -> float:
    """Entry-to-stop distance as a % of entry (long setup)."""
    return abs(entry - stop) / entry * 100


def compute_position_size_pct(
    entry: float,
    stop: float,
    gate_verdict: str | None = None,
    *,
    cap: float = MAX_POSITION_SIZE_PCT,
    risk_budget_pct: float = RISK_BUDGET_PCT,
) -> float:
    """Size as % of the account for one entry.

    Raises ``ValueError`` for degenerate geometry (non-finite/zero entry, stop
    not below entry) — the caller must reject the trade instead of sizing it.
    """
    if not isfinite(entry) or entry <= 0:
        raise ValueError(f"Entry must be finite and positive, got {entry!r}")
    if not isfinite(stop) or stop <= 0 or stop >= entry:
        raise ValueError(f"Long stop must be finite, positive and below entry, got {stop!r}")
    if not isfinite(cap) or cap <= 0:
        raise ValueError(f"Cap must be finite and positive, got {cap!r}")
    if not isfinite(risk_budget_pct) or risk_budget_pct <= 0:
        raise ValueError(f"Risk budget must be finite and positive, got {risk_budget_pct!r}")

    distance = stop_distance_pct(entry, stop)
    if distance <= 0:
        raise ValueError("Stop distance must be greater than zero")

    size_pct = min(risk_budget_pct / distance * 100, cap)
    if gate_verdict == GATE_CONDITIONAL:
        size_pct *= CONDITIONAL_HALVING
    return round(max(size_pct, MIN_SIZE_PCT), 2)


__all__ = [
    "RISK_BUDGET_PCT",
    "MAX_POSITION_SIZE_PCT",
    "MIN_SIZE_PCT",
    "stop_distance_pct",
    "compute_position_size_pct",
]