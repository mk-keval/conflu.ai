"""Canonical paper-trade P&L accounting.

One definition for every dollar figure in the journal:

    gross = (exit_price - entry_price) * shares
    costs = (entry_price + exit_price) * shares * (fees_bps + slippage_bps) / 10_000
    net   = gross - costs

R stays a price multiple, gross of costs:

    realized_r = (exit_price - entry_price) / (entry_price - stop_loss)

That matches the backtest convention (D-71): R is gross, dollar P&L is net of
10 bps fees + 5 bps slippage per side. Before D-74 the live sync multiplied R
by *notional* instead of dollar risk, overstating losses by the position-size
factor.

This module is pure: no I/O, no database.
"""

from __future__ import annotations

from math import isfinite
from typing import Any, Iterable, Mapping

FEE_BPS = 10.0
SLIPPAGE_BPS = 5.0


def _positive(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number) or number <= 0:
        return None
    return number


def _price(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number) or number <= 0:
        return None
    return number


def dollar_pnl(
    entry_price: Any,
    exit_price: Any,
    shares: Any,
    *,
    fees_bps: float = FEE_BPS,
    slippage_bps: float = SLIPPAGE_BPS,
) -> dict[str, float] | None:
    """Gross, costs and net dollars for one closed trade.

    Returns ``None`` when the inputs cannot produce a meaningful figure
    (missing/zero shares, non-finite prices). Never raises for bad data: the
    journal keeps the row and the verifier reports the gap.
    """
    entry = _price(entry_price)
    exit_ = _price(exit_price)
    qty = _positive(shares)
    if entry is None or exit_ is None or qty is None:
        return None

    gross = (exit_ - entry) * qty
    rate = (float(fees_bps) + float(slippage_bps)) / 10_000.0
    costs = (entry + exit_) * qty * rate
    return {
        "pnl_gross_usd": round(gross, 2),
        "costs_usd": round(costs, 2),
        "pnl_usd": round(gross - costs, 2),
    }


def plan_metrics(
    entry_low: Any,
    entry_high: Any,
    stop_loss: Any,
    targets: Iterable[Any],
) -> dict[str, float] | None:
    """R distance to T1 and R:R to the last target, at the zone midpoint.

    Mirrors the gate's ``_geometric_rr_long`` so the journal can reproduce the
    number the gate actually saw. ``entry_low``/``entry_high`` may be a single
    entry price (both the same).
    """
    low = _price(entry_low)
    high = _price(entry_high) or low
    stop = _price(stop_loss)
    if low is None or high is None or stop is None:
        return None

    mid = (low + high) / 2.0
    risk = mid - stop
    if risk <= 0:
        return None

    levels: list[float] = []
    for target in targets:
        level = _price(target)
        if level is not None:
            levels.append(level)
    if not levels:
        return None

    return {
        "entry_basis": round(mid, 4),
        "plan_rr": round((levels[-1] - mid) / risk, 2),
        "target_1_r": round((levels[0] - mid) / risk, 2),
    }


__all__ = [
    "FEE_BPS",
    "SLIPPAGE_BPS",
    "dollar_pnl",
    "plan_metrics",
]
