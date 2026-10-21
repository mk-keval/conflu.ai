"""Pending-order service (D-73) — the DB-aware half of next-session fills.

``pending.py`` decides what an order *would* do from bars. This module reads
active orders, fetches bars through an injected provider, persists the fill as
a journal entry, and closes the same-session stop. Both the API router and the
CLI call this so there is exactly one fill implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from backend.app.core.logging import get_logger
from backend.app.domain.workflow import journal_store, pending

log = get_logger("conflu.workflow.pending_service")

BarsProvider = Callable[[str], Any]


@dataclass
class PendingFillResult:
    """One order's outcome for the current run."""

    order_id: int
    symbol: str
    status: str
    fill_date: str | None = None
    fill_price: float | None = None
    same_day_stop: bool = False
    note: str = ""


def create_pending_order(
    trade_row: Mapping[str, Any],
    *,
    order_type: str = pending.ORDER_LIMIT,
    expires_after_sessions: int = pending.DEFAULT_EXPIRY_SESSIONS,
) -> int | None:
    """Create an order from an accepted gate row. None = duplicate active order."""
    order_type = str(order_type or pending.ORDER_LIMIT).strip().lower()
    if order_type not in pending.ORDER_TYPES:
        raise ValueError(f"Unknown order type {order_type!r}")

    entry_low = trade_row.get("entry_low")
    entry_high = trade_row.get("entry_high")
    stop = trade_row.get("stop_loss")
    limit_price: float | None = None

    if order_type == pending.ORDER_LIMIT:
        try:
            limit_price = float(entry_low or trade_row.get("entry_price") or 0)
            stop_f = float(stop or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("limit order requires numeric entry/stop") from exc
        if limit_price <= 0 or stop_f <= 0 or limit_price <= stop_f:
            raise ValueError("limit order requires entry_low above stop_loss")
    else:
        try:
            cap = float(entry_high or entry_low or trade_row.get("entry_price") or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("MOO order requires a numeric entry zone") from exc
        if cap <= 0:
            raise ValueError("MOO order requires an entry zone (entry_high)")

    return journal_store.insert_pending_order(
        dict(trade_row),
        order_type=order_type,
        limit_price=limit_price,
        expires_after_sessions=expires_after_sessions,
    )


def process_pending_orders(
    *,
    today: str,
    bars_provider: BarsProvider,
) -> list[PendingFillResult]:
    """Fill or expire every active order using bars up to ``today``.

    Per-symbol failures are logged and reported, never raised: one bad feed
    must not block the rest of the book or the new after-close signals.
    """
    results: list[PendingFillResult] = []
    for order in journal_store.list_pending_orders("pending", limit=1000):
        order_id = int(order.get("id") or 0)
        symbol = str(order.get("symbol") or "").strip().upper()
        try:
            bars = pending.normalize_bars(bars_provider(symbol))
            if not bars:
                results.append(PendingFillResult(
                    order_id=order_id, symbol=symbol, status=pending.PENDING,
                    note="no OHLCV available",
                ))
                continue

            decision = pending.evaluate_order(order, bars, today=today)

            if decision.status == pending.FILLED and decision.fill_date:
                row = pending.build_filled_row(order, decision)
                journal_store.upsert_entry(row)
                stopped = pending.same_bar_stop(order, decision)
                if stopped:
                    journal_store.update_exit(
                        row["date_entered"], row["symbol"],
                        pending.stop_exit(order, decision),
                    )
                journal_store.update_pending_order(
                    order_id, status=pending.FILLED,
                    status_date=decision.fill_date, status_reason=decision.reason,
                )
                log.info(
                    "pending.filled", order_id=order_id, symbol=symbol,
                    fill_date=decision.fill_date, fill_price=decision.fill_price,
                    same_day_stop=stopped,
                )
                results.append(PendingFillResult(
                    order_id=order_id, symbol=symbol, status=pending.FILLED,
                    fill_date=decision.fill_date, fill_price=decision.fill_price,
                    same_day_stop=stopped, note=decision.reason,
                ))
                continue

            if decision.status in (pending.EXPIRED, pending.CANCELLED):
                status_date = (
                    str((decision.bar or {}).get("date") or "")[:10] or today
                )
                journal_store.update_pending_order(
                    order_id, status=decision.status,
                    status_date=status_date, status_reason=decision.reason,
                )
                log.info(
                    "pending.closed", order_id=order_id, symbol=symbol,
                    status=decision.status, reason=decision.reason,
                )
                results.append(PendingFillResult(
                    order_id=order_id, symbol=symbol, status=decision.status,
                    note=decision.reason,
                ))
                continue

            results.append(PendingFillResult(
                order_id=order_id, symbol=symbol, status=pending.PENDING,
                note=decision.reason,
            ))
        except Exception as exc:  # one symbol must not block the run
            log.warning(
                "pending.process_failed", order_id=order_id,
                symbol=symbol, error=str(exc),
            )
            results.append(PendingFillResult(
                order_id=order_id, symbol=symbol, status="error", note=str(exc),
            ))
    return results


__all__ = ["BarsProvider", "PendingFillResult", "create_pending_order", "process_pending_orders"]
