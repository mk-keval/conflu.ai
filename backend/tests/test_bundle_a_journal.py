"""Bundle A (D-77) — fill inheritance, journal legs and verifier invariants.

The v0.2 row contract: a pending order carries the family + ATR, the fill
inherits both, Plan R is measured from the planned fill to T1, exits record
their legs, and the verifier rejects any row whose numbers the legs do not
support.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from backend.app.domain.workflow import journal as journal_mod
from backend.app.domain.workflow import journal_store as js
from backend.app.domain.workflow import pending
from backend.app.domain.workflow import sample as sample_mod
from backend.app.domain.workflow import verification


def _order(**over: object) -> dict[str, object]:
    row: dict[str, object] = {
        "signal_date": "2026-10-29",
        "symbol": "AAA",
        "order_type": "limit",
        "limit_price": 100.0,
        "entry_low": 100.0,
        "entry_high": 102.0,
        "stop_loss": 95.0,
        "target_1": 110.0,
        "target_2": 115.0,
        "target_3": 120.0,
        "position_size_pct": 10.0,
        "account_value": 100_000.0,
        "setup_family": "trend",
        "atr_at_entry": 2.0,
        "sample_version": sample_mod.SAMPLE_VERSION_V02,
    }
    row.update(over)
    return row


def _fill(price: float = 100.0) -> pending.FillDecision:
    return pending.FillDecision(
        pending.FILLED,
        fill_date="2026-10-30",
        fill_price=price,
        reason="limit touched",
        bar={"date": "2026-10-30", "open": 101, "high": 103, "low": 99, "close": 102},
    )


# ── Pending fills inherit the order's geometry ──────────────────────────


def test_v02_fill_inherits_family_atr_and_planned_fill_metrics() -> None:
    row = pending.build_filled_row(_order(), _fill())

    assert row["setup_family"] == "trend"
    assert row["atr_at_entry"] == 2.0
    assert row["sample_version"] == sample_mod.SAMPLE_VERSION_V02
    # Planned fill 100, stop 95 -> 1R = 5. T1 110 = 2.0R, T3 120 = 4.0R.
    assert row["plan_rr"] == 2.0
    assert row["target_1_r"] == 2.0
    assert row["stretch_rr"] == 4.0


def test_v01_fill_keeps_the_legacy_midpoint_last_target_basis() -> None:
    order = _order(setup_family=None, atr_at_entry=None, sample_version="v0.1")
    row = pending.build_filled_row(order, _fill())

    assert row["setup_family"] is None
    assert row["atr_at_entry"] is None
    # Midpoint 101, stop 95 -> 1R = 6. T1 110 = 1.5R, T3 120 = 3.17R.
    assert row["plan_rr"] == 3.17
    assert row["target_1_r"] == 1.5
    assert row["stretch_rr"] == 3.17


def test_same_session_stop_writes_one_full_leg() -> None:
    order = _order()
    decision = pending.FillDecision(
        pending.FILLED,
        fill_date="2026-10-30",
        fill_price=100.0,
        bar={"date": "2026-10-30", "open": 101, "high": 103, "low": 94, "close": 99},
    )
    updates = pending.stop_exit(order, decision)

    legs = json.loads(updates["exit_legs"])
    assert len(legs) == 1
    assert legs[0]["price"] == 95.0
    assert legs[0]["size_pct"] == 100.0
    assert legs[0]["reason"] == "stop"
    assert legs[0]["r"] == -1.0
    assert updates["realized_r"] == -1.0


# ── Journal schema round-trip ───────────────────────────────────────────


def test_family_columns_and_exit_legs_round_trip() -> None:
    assert js.upsert_entry({
        "date_entered": "2026-10-30", "symbol": "AAA", "sector": "Technology",
        "entry_price": 100.0, "stop_loss": 95.0, "position_size_pct": 10.0,
        "target_1": 110.0, "target_2": 115.0, "target_3": 120.0,
        "plan_rr": 2.0, "target_1_r": 2.0, "stretch_rr": 4.0,
        "setup_family": "trend", "atr_at_entry": 2.0,
        "sample_version": sample_mod.SAMPLE_VERSION_V02,
    }) == "inserted"

    legs = [
        {"date": "2026-11-02", "price": 110.0, "shares": 33.33,
         "size_pct": 33.333333, "reason": "target_1", "r": 2.0},
        {"date": "2026-11-03", "price": 115.0, "shares": 33.33,
         "size_pct": 33.333333, "reason": "target_2", "r": 3.0},
        {"date": "2026-11-04", "price": 111.0, "shares": 33.34,
         "size_pct": 33.333334, "reason": "trail", "r": 2.2},
    ]
    assert js.update_exit("2026-10-30", "AAA", {
        "date_closed": "2026-11-04",
        "exit_price": 112.0,
        "exit_reason": "scale_out",
        "realized_r": 2.4,
        "exit_legs": json.dumps(legs, separators=(",", ":")),
    }) is True

    row = js.fetch_rows()[0]
    assert row["setup_family"] == "trend"
    assert row["atr_at_entry"] == "2.0"
    assert row["stretch_rr"] == "4.0"
    stored_legs = json.loads(row["exit_legs"])
    assert [leg["reason"] for leg in stored_legs] == ["target_1", "target_2", "trail"]


def test_export_header_includes_the_family_contract() -> None:
    header = js.export_csv().splitlines()[0].split(",")
    for column in ("setup_family", "stretch_rr", "atr_at_entry", "exit_legs"):
        assert column in header


# ── Verifier: exit legs ─────────────────────────────────────────────────


def _closed_row(**over: object) -> dict[str, object]:
    row: dict[str, object] = {
        "symbol": "AAA",
        "date_entered": "2026-10-30",
        "date_closed": "2026-11-04",
        "entry_price": "100.0",
        "stop_loss": "95.0",
        "exit_price": "112.0",
        "realized_r": "2.4",
        "setup_family": "trend",
        "sample_version": sample_mod.SAMPLE_VERSION_V02,
        "exit_legs": json.dumps([
            {"date": "2026-11-02", "price": 110.0, "size_pct": 33.333333,
             "reason": "target_1", "r": 2.0},
            {"date": "2026-11-03", "price": 115.0, "size_pct": 33.333333,
             "reason": "target_2", "r": 3.0},
            {"date": "2026-11-04", "price": 111.0, "size_pct": 33.333334,
             "reason": "trail", "r": 2.2},
        ], separators=(",", ":")),
    }
    row.update(over)
    return row


def test_verifier_accepts_weighted_legs() -> None:
    assert verification.find_exit_leg_issues([_closed_row()]) == []


def test_verifier_flags_exit_price_that_is_not_the_leg_vwap() -> None:
    issues = verification.find_exit_leg_issues([
        _closed_row(exit_price="113.5"),
    ])
    assert len(issues) == 1
    assert "leg VWAP" in issues[0]["reason"]


def test_verifier_flags_realized_r_that_does_not_match_the_legs() -> None:
    issues = verification.find_exit_leg_issues([
        _closed_row(realized_r="3.0"),
    ])
    assert len(issues) == 1
    assert "weighted leg R" in issues[0]["reason"]


def test_verifier_flags_legs_that_do_not_sum_to_100() -> None:
    legs = [{"date": "2026-11-02", "price": 110.0, "size_pct": 50.0,
             "reason": "target_1", "r": 2.0}]
    issues = verification.find_exit_leg_issues([
        _closed_row(exit_legs=json.dumps(legs), exit_price="110.0", realized_r="2.0"),
    ])
    assert any("sum to" in issue["reason"] for issue in issues)


def test_verifier_flags_a_closed_family_row_without_legs() -> None:
    issues = verification.find_exit_leg_issues([_closed_row(exit_legs=None)])
    assert issues[0]["reason"] == "closed family row has no exit legs"


def test_verifier_exempts_legacy_rows_without_legs() -> None:
    row = _closed_row(
        setup_family=None, sample_version=sample_mod.SAMPLE_VERSION_V01,
        exit_legs=None,
    )
    assert verification.find_exit_leg_issues([row]) == []


# ── Verifier: family provenance ─────────────────────────────────────────


def test_family_issues_for_scored_rows_and_orders() -> None:
    trades = [
        {"symbol": "MISS", "sample_version": "v0.2", "setup_family": None},
        {"symbol": "GOOD", "sample_version": "v0.2", "setup_family": "breakout"},
        {"symbol": "OLD", "sample_version": "v0.1", "setup_family": "trend"},
    ]
    orders = [
        {"symbol": "PEND", "sample_version": "v0.2", "setup_family": None},
        {"symbol": "PGOOD", "sample_version": "v0.2", "setup_family": "unknown"},
    ]
    issues = verification.find_family_issues(trades, orders)
    symbols = {issue["symbol"] for issue in issues}
    assert symbols == {"MISS", "OLD", "PEND"}


def test_plan_rr_gap_carries_the_sample_version() -> None:
    rows = [{
        "symbol": "AAA", "sample_version": "v0.2",
        "risk_reward_planned": "2.5", "plan_rr": "1.0",
    }, {
        "symbol": "BBB", "sample_version": "v0.1",
        "risk_reward_planned": "2.5", "plan_rr": "1.0",
    }]
    gaps = verification.find_plan_rr_gaps(rows)
    assert {gap["sample_version"] for gap in gaps} == {"v0.2", "v0.1"}


# ── Scorecard: family breakdown ─────────────────────────────────────────


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "scorecard.py"
_spec = importlib.util.spec_from_file_location("scorecard_script", SCRIPT)
scorecard = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(scorecard)


def test_scorecard_reports_closed_trades_by_family() -> None:
    journal_mod.upsert_entry({
        "date_entered": "2026-10-30", "symbol": "TREND", "sector": "Technology",
        "entry_price": 100.0, "stop_loss": 95.0, "position_size_pct": 10.0,
        "setup_family": "trend", "sample_version": sample_mod.SAMPLE_VERSION_V02,
    })
    journal_mod.update_exit("2026-10-30", "TREND", {
        "date_closed": "2026-11-04", "exit_price": 110.0,
        "exit_reason": "target_1", "realized_r": 2.0,
    })
    journal_mod.upsert_entry({
        "date_entered": "2026-10-30", "symbol": "BREAK", "sector": "Technology",
        "entry_price": 100.0, "stop_loss": 95.0, "position_size_pct": 10.0,
        "setup_family": "breakout", "sample_version": sample_mod.SAMPLE_VERSION_V02,
    })
    journal_mod.update_exit("2026-10-30", "BREAK", {
        "date_closed": "2026-11-04", "exit_price": 95.0,
        "exit_reason": "stop", "realized_r": -1.0,
    })

    card = scorecard.build_scorecard()
    families = {item["family"]: item for item in card["per_family"]}
    assert set(families) == {"trend", "breakout"}
    assert families["trend"]["n"] == 1
    assert families["trend"]["expectancy_r"] == 2.0
    assert families["breakout"]["expectancy_r"] == -1.0
