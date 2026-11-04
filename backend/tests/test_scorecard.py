"""Canonical scorecard filtering and D-75 pass bar (D-76)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from backend.app.domain.workflow import journal as journal_mod
from backend.app.domain.workflow import sample as sample_mod

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "scorecard.py"
_spec = importlib.util.spec_from_file_location("scorecard_script", SCRIPT)
scorecard = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(scorecard)


def _closed(symbol: str, day: str, version: str, r: float) -> None:
    journal_mod.upsert_entry({
        "date_entered": day, "symbol": symbol, "sector": "Technology",
        "entry_price": 100.0, "stop_loss": 95.0, "position_size_pct": 10.0,
        "template": "trend-pullback", "regime": "neutral",
        "gate_verdict": "PASS", "sample_version": version,
    })
    assert journal_mod.update_exit(day, symbol, {
        "date_closed": "2026-10-30", "exit_price": 100.0 + 5.0 * r,
        "exit_reason": "target_1", "realized_r": r,
    })


def test_scorecard_counts_only_the_scored_sample_version() -> None:
    _closed("V01", "2026-10-05", sample_mod.SAMPLE_VERSION_V01, 5.0)
    _closed("CUR", "2026-10-06", sample_mod.SCORED_SAMPLE_VERSION, -1.0)
    _closed("LOOP", "2026-10-07", sample_mod.SAMPLE_VERSION_INTERIM, 3.0)

    journal_mod.upsert_entry({
        "date_entered": "2026-10-08", "symbol": "OPEN", "sector": "Technology",
        "entry_price": 100.0, "stop_loss": 95.0, "position_size_pct": 10.0,
        "gate_verdict": "PASS", "sample_version": sample_mod.SCORED_SAMPLE_VERSION,
    })
    journal_mod.insert_pending_order({
        "date_entered": "2026-10-08", "symbol": "PEND", "entry_low": 100.0,
        "entry_high": 102.0, "entry_price": 100.0, "stop_loss": 95.0,
        "position_size_pct": 10.0, "account_value": 100_000.0, "gate_verdict": "PASS",
        "sample_version": sample_mod.SCORED_SAMPLE_VERSION,
    })

    card = scorecard.build_scorecard()
    assert card["sample"]["scored_version"] == sample_mod.SCORED_SAMPLE_VERSION
    assert card["sample"]["closed"] == 1
    assert card["sample"]["open"] == 1
    assert card["sample"]["pending"] == 1
    assert card["headline"]["total_r"] == -1.0

    reference = {item["version"]: item for item in card["reference_versions"]}
    assert reference[sample_mod.SAMPLE_VERSION_V01]["closed"] == 1
    assert reference[sample_mod.SAMPLE_VERSION_V01]["headline"]["total_r"] == 5.0
    assert reference[sample_mod.SAMPLE_VERSION_INTERIM]["closed"] == 1
    assert reference[sample_mod.SAMPLE_VERSION_V01]["scored"] is False


def test_d75_pass_bar_requires_edge_and_loss_control() -> None:
    assert scorecard._pass_bar(29, {
        "expectancy_r": 0.2, "profit_factor": 1.5, "avg_loss_r": -1.0,
    }).startswith("not evaluable")
    assert scorecard._pass_bar(30, {
        "expectancy_r": 0.2, "profit_factor": 1.5, "avg_loss_r": -1.0,
    }) == "PASS"
    assert "profit factor" in scorecard._pass_bar(30, {
        "expectancy_r": 0.2, "profit_factor": 1.2, "avg_loss_r": -1.0,
    })
    assert "average loss" in scorecard._pass_bar(30, {
        "expectancy_r": 0.2, "profit_factor": 1.5, "avg_loss_r": -1.2,
    })
    assert "expectancy" in scorecard._pass_bar(30, {
        "expectancy_r": 0.0, "profit_factor": 1.5, "avg_loss_r": -1.0,
    })


def test_drawdown_is_peak_to_trough_cumulative_r() -> None:
    rows = [
        {"symbol": "A", "date_closed": "2026-10-01", "realized_r": 2.0},
        {"symbol": "B", "date_closed": "2026-10-02", "realized_r": -1.0},
        {"symbol": "C", "date_closed": "2026-10-03", "realized_r": -1.0},
        {"symbol": "D", "date_closed": "2026-10-04", "realized_r": 3.0},
    ]
    assert scorecard._max_drawdown_r(rows) == 2.0
    assert scorecard._drawdown_status(2.0).startswith("CLEAR")
    assert scorecard._drawdown_status(8.0).startswith("REVIEW")
    assert scorecard._drawdown_status(12.0).startswith("KILL")
