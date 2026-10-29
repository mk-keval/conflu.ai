"""Tests for the D-74 journal integrity checks."""

from __future__ import annotations

from backend.app.domain.workflow import verification


def _trade(**overrides):
    row = {
        "symbol": "SF",
        "date_entered": "2026-10-22",
        "date_closed": None,
        "entry_price": 65.40,
        "exit_price": None,
        "shares": 25.02,
        "realized_r": None,
        "pnl_usd": None,
        "voided": 0,
        "exclude_from_stats": 0,
        "risk_reward_planned": 6.47,
        "plan_rr": 4.36,
        "sample_version": "v0.1",
    }
    row.update(overrides)
    return row


def _order(**overrides):
    row = {
        "symbol": "SF",
        "signal_date": "2026-10-21",
        "status": "filled",
        "status_date": "2026-10-22",
        "sample_version": "v0.1",
    }
    row.update(overrides)
    return row


def test_t_plus_one_fill_passes() -> None:
    assert verification.find_phantom_fills([_trade()], [_order()]) == []


def test_same_day_fill_is_a_phantom() -> None:
    violations = verification.find_phantom_fills(
        [_trade(date_entered="2026-10-21")], [_order(status_date="2026-10-21")],
    )
    assert len(violations) == 1
    assert violations[0]["reason"] == "entry is not strictly after the signal date"


def test_filled_order_without_journal_row_fails() -> None:
    violations = verification.find_phantom_fills([], [_order()])
    assert len(violations) == 1
    assert violations[0]["reason"] == "filled order has no journal entry"


def test_unfilled_orders_are_ignored() -> None:
    assert verification.find_phantom_fills([], [_order(status="expired")]) == []


def test_dollar_pnl_mismatch_is_flagged() -> None:
    row = _trade(
        date_closed="2026-10-27", exit_price=273.93, shares=5.84,
        entry_price=278.24, realized_r=-1.0, pnl_usd=-1624.99,
    )
    mismatches = verification.find_pnl_mismatches([row])
    assert len(mismatches) == 1
    assert mismatches[0]["expected"] == -30.01


def test_correct_dollar_pnl_passes() -> None:
    row = _trade(
        date_closed="2026-10-27", exit_price=273.93, shares=5.84,
        entry_price=278.24, realized_r=-1.0, pnl_usd=-30.01,
    )
    assert verification.find_pnl_mismatches([row]) == []


def test_plan_rr_gap_is_a_warning() -> None:
    gaps = verification.find_plan_rr_gaps([_trade(risk_reward_planned=10.28, plan_rr=0.65)])
    assert len(gaps) == 1
    assert gaps[0]["gap"] == 9.63


def test_known_sample_versions_pass() -> None:
    assert verification.find_sample_version_issues([_trade()], [_order()]) == []


def test_unknown_sample_version_is_flagged() -> None:
    issues = verification.find_sample_version_issues(
        [_trade(sample_version="v9.9")], [],
    )
    assert len(issues) == 1
    assert issues[0]["reason"] == "unknown sample_version"

    issues = verification.find_sample_version_issues(
        [], [_order(status="pending", sample_version="v9.9")],
    )
    assert len(issues) == 1
    assert issues[0]["reason"] == "unknown pending-order sample_version"


def test_fill_must_inherit_the_order_version() -> None:
    issues = verification.find_sample_version_issues(
        [_trade(sample_version="interim")], [_order(sample_version="v0.2")],
    )
    assert len(issues) == 1
    assert issues[0]["reason"] == "filled order and journal row versions differ"
    assert issues[0]["order_version"] == "v0.2"
    assert issues[0]["row_version"] == "interim"
