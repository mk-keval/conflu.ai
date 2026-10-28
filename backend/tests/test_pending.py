"""Pending-order execution tests (D-73).

The regression this file protects: a signal produced after the close must
never fill from the signal day's bar. Every test starts with a signal date and
only later bars may fill.
"""

from __future__ import annotations

import pandas as pd

from backend.app.domain.workflow import pending


def _bar(date: str, open_: float, high: float, low: float, close: float) -> dict:
    return {"date": date, "open": open_, "high": high, "low": low, "close": close}


def _order(**over: object) -> dict:
    row: dict[str, object] = {
        "signal_date": "2026-10-20",
        "symbol": "AAA",
        "order_type": "limit",
        "limit_price": 100.0,
        "entry_low": 100.0,
        "entry_high": 102.0,
        "stop_loss": 95.0,
        "position_size_pct": 20.0,
        "account_value": 100_000.0,
        "expires_after_sessions": 3,
    }
    row.update(over)
    return row


def test_limit_never_fills_on_the_signal_bar() -> None:
    """The 2026-10-19/20 phantom-fill bug: same-day low is not a fill."""
    bars = [
        _bar("2026-10-20", 101.0, 103.0, 98.0, 102.0),  # signal day: low 98
        _bar("2026-10-21", 101.0, 102.0, 100.5, 101.5),  # never touches 100
    ]
    decision = pending.evaluate_order(_order(), bars, today="2026-10-21")
    assert decision.status == pending.PENDING
    assert decision.fill_date is None
    assert decision.sessions_seen == 1


def test_limit_fills_at_limit_on_next_session() -> None:
    bars = [
        _bar("2026-10-20", 101.0, 103.0, 98.0, 102.0),
        _bar("2026-10-21", 101.0, 102.0, 99.5, 100.5),
    ]
    decision = pending.evaluate_order(_order(), bars, today="2026-10-21")
    assert decision.status == pending.FILLED
    assert decision.fill_date == "2026-10-21"
    assert decision.fill_price == 100.0
    assert decision.bar["low"] == 99.5


def test_limit_gap_below_limit_fills_at_open() -> None:
    bars = [_bar("2026-10-21", 98.5, 99.5, 97.0, 99.0)]
    decision = pending.evaluate_order(_order(), bars, today="2026-10-21")
    assert decision.status == pending.FILLED
    assert decision.fill_price == 98.5


def test_limit_gap_through_stop_cancels_instead_of_filling() -> None:
    bars = [_bar("2026-10-21", 94.0, 96.0, 92.0, 93.0)]
    decision = pending.evaluate_order(_order(), bars, today="2026-10-21")
    assert decision.status == pending.CANCELLED
    assert "stop" in decision.reason


def test_limit_expires_after_three_sessions() -> None:
    bars = [
        _bar("2026-10-21", 103.0, 104.0, 101.0, 102.0),
        _bar("2026-10-22", 102.0, 103.0, 101.5, 102.5),
        _bar("2026-10-23", 103.0, 104.0, 102.0, 103.0),
        _bar("2026-10-26", 99.0, 100.0, 98.0, 99.5),  # too late
    ]
    decision = pending.evaluate_order(_order(), bars, today="2026-10-26")
    assert decision.status == pending.EXPIRED
    assert decision.bar["date"] == "2026-10-23"


def test_moo_fills_at_next_open_inside_zone() -> None:
    bars = [_bar("2026-10-21", 101.0, 102.0, 99.0, 100.0)]
    decision = pending.evaluate_order(
        _order(order_type="moo", limit_price=None), bars, today="2026-10-21"
    )
    assert decision.status == pending.FILLED
    assert decision.fill_price == 101.0


def test_moo_cancels_above_entry_zone() -> None:
    bars = [_bar("2026-10-21", 103.0, 104.0, 102.0, 103.5)]
    decision = pending.evaluate_order(
        _order(order_type="moo", limit_price=None), bars, today="2026-10-21"
    )
    assert decision.status == pending.CANCELLED
    assert "above" in decision.reason


def test_moo_cancels_through_stop() -> None:
    bars = [_bar("2026-10-21", 94.0, 96.0, 93.0, 95.0)]
    decision = pending.evaluate_order(
        _order(order_type="moo", limit_price=None), bars, today="2026-10-21"
    )
    assert decision.status == pending.CANCELLED


def test_future_bars_are_ignored() -> None:
    bars = [_bar("2026-10-21", 101.0, 102.0, 99.5, 100.5)]
    decision = pending.evaluate_order(_order(), bars, today="2026-10-20")
    assert decision.status == pending.PENDING
    assert decision.sessions_seen == 0


def test_normalize_bars_reads_a_dataframe_with_a_date_index() -> None:
    frame = pd.DataFrame(
        {"Open": [101.0], "High": [102.0], "Low": [99.0], "Close": [100.5]},
        index=pd.to_datetime(["2026-10-21"]),
    )
    bars = pending.normalize_bars(frame)
    assert bars == [{
        "date": "2026-10-21", "open": 101.0, "high": 102.0,
        "low": 99.0, "close": 100.5,
    }]


def test_build_filled_row_uses_actual_fill_and_t1_timing() -> None:
    decision = pending.FillDecision(
        pending.FILLED, fill_date="2026-10-21", fill_price=100.0,
        bar=_bar("2026-10-21", 101.0, 102.0, 99.0, 100.5),
    )
    row = pending.build_filled_row(_order(notes="Triggers: A"), decision)
    assert row["date_entered"] == "2026-10-21"
    assert row["entry_price"] == 100.0
    assert row["entry_timing"] == "t1_limit"
    assert row["shares"] == 200.0
    assert "Pending limit $100.00 filled 2026-10-21" in row["notes"]


def test_worse_moo_fill_caps_shares_at_planned_risk() -> None:
    # 20% of 100k = $20k notional; plan risk = $1k at a $5 stop.
    # Fill 102 → risk-based shares 1000/7 = 142.86 (notional would be 196.08).
    assert pending.planned_shares(_order(), 102.0) == 142.86


def test_same_session_stop_closes_at_minus_one_r() -> None:
    decision = pending.FillDecision(
        pending.FILLED, fill_date="2026-10-21", fill_price=100.0,
        bar=_bar("2026-10-21", 101.0, 102.0, 94.0, 96.0),
    )
    assert pending.same_bar_stop(_order(), decision) is True
    exit_row = pending.stop_exit(_order(), decision)
    assert exit_row["date_closed"] == "2026-10-21"
    assert exit_row["exit_reason"] == "stop"
    assert exit_row["exit_price"] == 95.0
    assert exit_row["realized_r"] == -1.0
    assert exit_row["pnl_gross_usd"] == -1000.0
    assert exit_row["costs_usd"] == 58.5
    assert exit_row["pnl_usd"] == -1058.5
