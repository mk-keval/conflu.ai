"""Shared ATR-based entry/stop/target math.

Consolidates the duplicated "compute trade levels from ATR" logic that
previously lived inline in multiple scorers (TV confluence scorer, deep
analysis orchestrator). The multipliers are PARAMETERS — each caller passes the
same values it used before, so outputs are byte-for-byte identical. This module
only provides locality (one place to reason about the math), it does NOT unify
the different threshold policies.

Historical policy notes (preserved per caller):
- TV confluence scorer (confluence_scorer.py): volatility-regime-adaptive
  multipliers via ``vol_regime_multipliers`` (R:R ~1.5-1.67 for T1).
- Deep analysis (deep_analysis.py): fixed 2x ATR stop / 2x / 3x ATR targets.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradeLevels:
    """Computed trade levels from price + ATR."""
    entry: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_reward: float


def vol_regime_multipliers(atr_pct: float) -> tuple[float, float, float]:
    """Return (stop_mult, target_mult_1, target_mult_2) for a volatility regime.

    ATR% of price determines the regime:
    - low (<1%), normal (1-3%), high (>3%).
    First target R:R is asymmetric: T1 offers ~1.5x the stop distance so swing
    traders get meaningful reward for the risk taken.
    """
    if atr_pct < 1.0:
        return 1.5, 2.5, 3.5   # R:R = 1.67 for T1
    if atr_pct > 3.0:
        return 3.0, 5.0, 7.0   # R:R = 1.67 for T1
    return 2.0, 3.0, 4.5       # R:R = 1.5 for T1


def compute_atr_levels(
    close: float,
    atr: float,
    stop_mult: float,
    target_mult_1: float,
    target_mult_2: float,
    *,
    is_long: bool = True,
) -> TradeLevels:
    """Compute entry/stop/targets from close + ATR with explicit multipliers.

    Direction-aware: for a long, stop is below close and targets above; for a
    short, the signs flip. NOTE: levels are intentionally NOT rounded here —
    historical callers (confluence scorer, deep analysis) did not round them;
    only ``risk_reward`` was rounded (2dp). Preserving that exact behavior.
    """
    if is_long:
        stop_loss = close - (stop_mult * atr)
        target_1 = close + (target_mult_1 * atr)
        target_2 = close + (target_mult_2 * atr)
    else:
        stop_loss = close + (stop_mult * atr)
        target_1 = close - (target_mult_1 * atr)
        target_2 = close - (target_mult_2 * atr)
    risk_reward = round(target_mult_1 / stop_mult, 2)
    return TradeLevels(
        entry=close,
        stop_loss=stop_loss,
        target_1=target_1,
        target_2=target_2,
        risk_reward=risk_reward,
    )


def compute_fallback_levels(close: float, *, is_long: bool = True) -> TradeLevels:
    """Non-ATR fallback used when ATR is missing/zero (≈5%/10% moves)."""
    if is_long:
        stop_loss = close * 0.95
        target_1 = close * 1.05
        target_2 = close * 1.10
    else:
        stop_loss = close * 1.05
        target_1 = close * 0.95
        target_2 = close * 0.90
    return TradeLevels(
        entry=close,
        stop_loss=stop_loss,
        target_1=target_1,
        target_2=target_2,
        risk_reward=1.0,
    )
