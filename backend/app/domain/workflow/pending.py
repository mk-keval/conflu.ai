"""Pending-order execution (D-73) — after-close signals, next-session fills.

The 2026-10-19/20 forward entries were booked at prices that never traded:
the signal was produced after the close, but the journal stored the zone low
as if it had filled that same afternoon. This module is the measurement
correction: a signal becomes a **pending order** after the close, and it can
only fill from an actual bar *after* the signal date.

Rules (long only, execution v0.1 frozen):

- **limit** (default): fill at ``min(open, limit)`` when the bar trades at or
  below the limit; cancel if the bar opens at/below the stop (the setup gapped
  through the risk before any valid entry).
- **moo**: fill at the next open only when the open is inside the entry zone
  (``<= entry_high``); cancel above the zone (no chase) or at/below the stop.
- **expiry**: after ``expires_after_sessions`` eligible sessions with no fill,
  the order expires. Sessions are actual bars, so holidays do not consume one.
- **no look-ahead**: only bars strictly after ``signal_date`` and never after
  the run date are considered.
- **same-session stop**: if the fill bar's low touches the stop, the trade is
  closed at the stop that day. Same-session targets are deliberately ignored —
  the intrabar sequence is unknowable, so the conservative outcome wins.

Pure functions only; the service layer owns DB writes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from backend.app.domain.workflow import pnl as pnl_mod
from backend.app.domain.workflow.exits import EXIT_STOP

ORDER_LIMIT = "limit"
ORDER_MOO = "moo"
ORDER_TYPES = (ORDER_LIMIT, ORDER_MOO)

PENDING = "pending"
FILLED = "filled"
EXPIRED = "expired"
CANCELLED = "cancelled"

DEFAULT_EXPIRY_SESSIONS = 3


@dataclass
class FillDecision:
    """Outcome of evaluating one pending order against actual bars."""

    status: str
    fill_date: str | None = None
    fill_price: float | None = None
    reason: str = ""
    bar: dict[str, Any] | None = None
    sessions_seen: int = 0


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def normalize_bars(raw: Any) -> list[dict[str, Any]]:
    """Normalize a DataFrame / dict rows / tuples into ascending OHLC bars."""
    if raw is None:
        return []

    records: list[Any]
    if hasattr(raw, "reset_index") and hasattr(raw, "to_dict"):
        try:
            records = raw.reset_index().to_dict("records")
        except Exception:  # malformed frame — caller treats it as no data
            return []
    elif isinstance(raw, (list, tuple)):
        records = list(raw)
    else:
        return []

    by_date: dict[str, dict[str, Any]] = {}
    for record in records:
        if isinstance(record, Mapping):
            norm = {str(k).strip().lower(): v for k, v in record.items()}
            date = (
                norm.get("date") or norm.get("datetime")
                or norm.get("timestamp") or norm.get("index") or ""
            )
            open_ = norm.get("open")
            high = norm.get("high")
            low = norm.get("low")
            close = norm.get("close")
        elif isinstance(record, (tuple, list)) and len(record) >= 5:
            date, open_, high, low, close, *_ = record
        else:
            continue

        day = str(date or "")[:10]
        open_f, high_f, low_f = _number(open_), _number(high), _number(low)
        close_f = _number(close)
        if not day or None in (open_f, high_f, low_f, close_f):
            continue
        by_date.setdefault(day, {
            "date": day, "open": open_f, "high": high_f,
            "low": low_f, "close": close_f,
        })

    return [by_date[key] for key in sorted(by_date)]


def eligible_sessions(
    bars: list[dict[str, Any]], signal_date: str, today: str | None = None
) -> list[dict[str, Any]]:
    """Bars the order could actually fill from: strictly after the signal."""
    signal = str(signal_date or "")[:10]
    if not signal:
        return []
    cutoff = str(today or "")[:10]
    ordered = sorted(bars, key=lambda bar: str(bar.get("date") or ""))
    return [
        bar for bar in ordered
        if str(bar.get("date") or "") > signal
        and (not cutoff or str(bar.get("date") or "") <= cutoff)
    ]


def evaluate_order(
    order: Mapping[str, Any],
    bars: list[dict[str, Any]],
    *,
    today: str | None = None,
) -> FillDecision:
    """Evaluate one order against actual bars. Never raises on bad data."""
    signal_date = str(order.get("signal_date") or order.get("date_entered") or "")[:10]
    if not signal_date:
        return FillDecision(CANCELLED, reason="missing signal date")

    order_type = str(order.get("order_type") or ORDER_LIMIT).strip().lower()
    if order_type not in ORDER_TYPES:
        return FillDecision(CANCELLED, reason=f"unknown order type {order_type!r}")

    try:
        stop = float(order.get("stop_loss"))
    except (TypeError, ValueError):
        return FillDecision(CANCELLED, reason="missing stop")
    if stop <= 0:
        return FillDecision(CANCELLED, reason="invalid stop")

    limit = _number(order.get("limit_price"))
    if limit is None and order_type == ORDER_LIMIT:
        limit = _number(order.get("entry_low"))
    zone_high = _number(order.get("entry_high")) or _number(order.get("entry_low"))

    try:
        expires = max(1, int(order.get("expires_after_sessions") or DEFAULT_EXPIRY_SESSIONS))
    except (TypeError, ValueError):
        expires = DEFAULT_EXPIRY_SESSIONS

    if order_type == ORDER_LIMIT and (limit is None or limit <= stop):
        return FillDecision(CANCELLED, reason="invalid limit/stop geometry")
    if order_type == ORDER_MOO and zone_high is None:
        return FillDecision(CANCELLED, reason="missing entry zone")

    sessions = eligible_sessions(bars, signal_date, today)
    if not sessions:
        return FillDecision(PENDING, reason="waiting for the first eligible session")

    for bar in sessions[:expires]:
        open_ = float(bar["open"])
        low = float(bar["low"])

        if open_ <= stop:
            return FillDecision(
                CANCELLED,
                reason=f"opened at ${open_:.2f} at/below the ${stop:.2f} stop before a valid fill",
            )

        if order_type == ORDER_MOO:
            if zone_high is not None and open_ > zone_high:
                return FillDecision(
                    CANCELLED,
                    reason=f"opened at ${open_:.2f} above the ${zone_high:.2f} entry-zone cap (no chase)",
                )
            return FillDecision(
                FILLED, fill_date=bar["date"], fill_price=open_,
                reason="market-on-open fill inside the entry zone",
                bar=bar,
            )

        assert limit is not None
        if open_ <= limit:
            return FillDecision(
                FILLED, fill_date=bar["date"], fill_price=open_,
                reason=f"opened at ${open_:.2f} at/below the ${limit:.2f} limit",
                bar=bar,
            )
        if low <= limit:
            return FillDecision(
                FILLED, fill_date=bar["date"], fill_price=limit,
                reason=f"limit ${limit:.2f} touched",
                bar=bar,
            )

    if len(sessions) >= expires:
        return FillDecision(
            EXPIRED,
            reason=f"not filled in {expires} session(s)",
            bar=sessions[expires - 1],
            sessions_seen=len(sessions),
        )
    return FillDecision(
        PENDING,
        reason=f"no fill in {len(sessions)}/{expires} session(s)",
        sessions_seen=len(sessions),
    )


def planned_shares(order: Mapping[str, Any], fill_price: float) -> float | None:
    """Shares capped by both planned notional and planned dollar risk.

    The signal's size was computed for the desired zone entry. A better fill
    risks less; a worse MOO fill (still inside the zone) is capped so the
    planned risk is never exceeded. Sizing rules themselves are unchanged.
    """
    try:
        size_pct = float(order.get("position_size_pct") or 0)
        account = float(order.get("account_value") or 0)
        stop = float(order.get("stop_loss") or 0)
    except (TypeError, ValueError):
        return None
    if size_pct <= 0 or account <= 0 or fill_price <= stop:
        return None

    # Planned risk is measured at the desired entry (limit / zone low), not at
    # the fill: a worse MOO fill must buy fewer shares to keep that risk.
    try:
        planned_entry = float(
            order.get("limit_price") or order.get("entry_low")
            or order.get("entry_price") or fill_price
        )
    except (TypeError, ValueError):
        planned_entry = fill_price
    if planned_entry <= stop:
        planned_entry = fill_price

    notional_shares = size_pct / 100.0 * account / fill_price
    planned_risk = size_pct / 100.0 * account * (planned_entry - stop) / planned_entry
    risk_shares = planned_risk / (fill_price - stop)
    return round(min(notional_shares, risk_shares), 2)


def build_filled_row(order: Mapping[str, Any], decision: FillDecision) -> dict[str, Any]:
    """Turn a filled order into a journal entry row (actual fill date/price)."""
    if decision.status != FILLED or not decision.fill_date or not decision.fill_price:
        raise ValueError("build_filled_row requires a filled decision")

    fill = float(decision.fill_price)
    order_type = str(order.get("order_type") or ORDER_LIMIT).lower()
    limit = _number(order.get("limit_price"))
    label = f"limit ${limit:.2f} " if order_type == ORDER_LIMIT and limit else "MOO "
    order_note = f"Pending {label}filled {decision.fill_date} at ${fill:.2f} (T+1)"

    notes = str(order.get("notes") or "").strip()
    notes = f"{notes} | {order_note}" if notes else order_note

    targets = [
        level for level in (
            order.get("target_1"), order.get("target_2"), order.get("target_3"),
        ) if level not in (None, "")
    ]
    metrics = pnl_mod.plan_metrics(
        order.get("entry_low"), order.get("entry_high"),
        order.get("stop_loss"), targets,
    ) or {}

    return {
        "date_entered": decision.fill_date,
        "symbol": order.get("symbol"),
        "sector": order.get("sector"),
        "action": order.get("action"),
        "entry_type": "initial",
        "entry_price": round(fill, 4),
        "stop_loss": order.get("stop_loss"),
        "target_1": order.get("target_1"),
        "target_2": order.get("target_2"),
        "target_3": order.get("target_3"),
        "plan_rr": metrics.get("plan_rr"),
        "target_1_r": metrics.get("target_1_r"),
        "position_size_pct": order.get("position_size_pct"),
        "account_value": order.get("account_value"),
        "shares": planned_shares(order, fill),
        "confluence_count": order.get("confluence_count"),
        "signal_at_entry": order.get("signal_at_entry"),
        "gate_verdict": order.get("gate_verdict"),
        "gate_failed_step": order.get("gate_failed_step"),
        "entry_low": order.get("entry_low"),
        "entry_high": order.get("entry_high"),
        "risk_reward_planned": order.get("risk_reward_planned"),
        "gate_version": order.get("gate_version"),
        "notes": notes[:500],
        "template": order.get("template"),
        "regime": order.get("regime"),
        "max_hold_days": order.get("max_hold_days"),
        "entry_timing": "t1_limit" if order_type == ORDER_LIMIT else "moo",
    }


def same_bar_stop(order: Mapping[str, Any], decision: FillDecision) -> bool:
    """True when the fill bar itself traded through the stop after entry."""
    bar = decision.bar or {}
    try:
        return float(bar.get("low")) <= float(order.get("stop_loss"))
    except (TypeError, ValueError):
        return False


def stop_exit(order: Mapping[str, Any], decision: FillDecision) -> dict[str, Any]:
    """Exit columns for a same-session stop-out (conservative intrabar order)."""
    fill = float(decision.fill_price or 0)
    stop = float(order.get("stop_loss") or 0)
    shares = planned_shares(order, fill)
    realized_r = round((stop - fill) / (fill - stop), 2) if fill > stop else None
    money = pnl_mod.dollar_pnl(fill, stop, shares) or {}
    return {
        "date_closed": decision.fill_date,
        "exit_price": round(stop, 2),
        "exit_reason": EXIT_STOP,
        "realized_r": realized_r,
        "pnl_usd": money.get("pnl_usd"),
        "pnl_gross_usd": money.get("pnl_gross_usd"),
        "costs_usd": money.get("costs_usd"),
        "mfe_r": None,
        "mae_r": -1.0,
        "plan_adherence": 1.0,
    }


__all__ = [
    "ORDER_LIMIT", "ORDER_MOO", "ORDER_TYPES",
    "PENDING", "FILLED", "EXPIRED", "CANCELLED",
    "DEFAULT_EXPIRY_SESSIONS",
    "FillDecision",
    "normalize_bars", "eligible_sessions", "evaluate_order",
    "planned_shares", "build_filled_row", "same_bar_stop", "stop_exit",
]
