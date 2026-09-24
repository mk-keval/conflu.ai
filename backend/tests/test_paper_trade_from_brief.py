"""Gate enforcement in the paper-trade script (plan Sec.1D).

Exercises ``paper_trade_from_brief.build_row`` offline — no API, no real
journal mutations:

1. A verdict whose attached gate PASSES (and an empty verified journal) →
   a full-size trade row with entry_type=initial.
2. A hard gate FAIL → a rejection row (never a trade).
3. A missing stop_loss → rejection (never a blank-stop trade).
4. A CONDITIONAL gate → a half-size trade row with gate fields recorded.
5. A journal with an open position in the same sector that would breach the
   exposure ceiling → Step 6 fails → rejection.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

# Same bootstrap the script uses at runtime.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend" / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import backend.app.domain.ticker_analysis  # noqa: F401  (import-order: gate ↔ synthesis cycle)

from backend.app.domain.workflow import gate as gate_module
from backend.app.domain.workflow import journal as journal_module
from paper_trade_from_brief import build_row


def _mk_gate(overall: str, steps: list[tuple[str, bool, bool, str]]) -> dict[str, Any]:
    return {
        "overall": overall,
        "conviction_score": 7,
        "data_gaps": [],
        "evaluated_at": "2026-09-18T00:00:00",
        "steps": [
            {"name": n, "passed": p, "conditional": c, "note": nt}
            for n, p, c, nt in steps
        ],
    }


GATE_PASS = _mk_gate("PASS", [
    ("Liquidity", True, False, "ok"),
    ("Structure", True, False, "ok"),
    ("Positioning", True, False, "ok"),
    ("Catalyst", True, False, "ok"),
    ("Risk/Reward", True, False, "ok"),
    ("Portfolio Fit", False, True, "synthesis path"),
    ("Conviction", True, False, "ok"),
])

GATE_FAIL = _mk_gate("FAIL", [
    ("Liquidity", True, False, "ok"),
    ("Risk/Reward", False, False, "Stop distance 15.0% versus configured ceiling 10.0%."),
    ("Portfolio Fit", False, True, "synthesis path"),
    ("Conviction", True, False, "ok"),
])

GATE_COND = _mk_gate("CONDITIONAL", [
    ("Liquidity", True, False, "ok"),
    ("Risk/Reward", False, True, "5d stub ONLY"),
    ("Portfolio Fit", False, True, "synthesis path"),
    ("Conviction", True, False, "ok"),
])


def _verdict(
    *,
    gate: dict[str, Any],
    stop: float | None = 95.0,
    sector: str = "Healthcare",
    targets: list[float] | None = None,
) -> dict[str, Any]:
    return {
        "price": 100.0,
        "sector": sector,
        "verdict": {
            "action": "BUY",
            "conviction": 8,
            "gate": gate,
            "entry_zone_low": 98.0,
            "entry_zone_high": 102.0,
            "stop_loss": stop,
            "targets": targets or [110.0, 120.0],
            "risk_reward": 2.4,
            "position_size_pct": 0.0,
            "buy_triggers": ["EMA cross", "ROE beat"],
        },
    }


BRIEF = {"screen_name": "s", "confluence_score": 83, "verdict": "BUY"}


def test_pass_with_empty_journal_writes_full_size_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(journal_module, "read_open_positions", lambda *a, **k: [])
    row, rejection = build_row("TEST", BRIEF, _verdict(gate=GATE_PASS))
    assert rejection is None
    assert row is not None
    assert row["gate_verdict"] == "PASS"
    assert row["entry_type"] == "initial"
    assert row["position_size_pct"] == 20.0  # 1% risk / 5% stop-distance, capped at 25
    assert row["stop_loss"] == 95.0
    assert row["confluence_count"] == 4  # 83/100 → 0-5
    assert "raw confluence 83/100" in row["notes"]  # R7: raw preserved


def test_hard_fail_produces_rejection_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(journal_module, "read_open_positions", lambda *a, **k: [])
    row, rejection = build_row("TEST", BRIEF, _verdict(gate=GATE_FAIL))
    assert row is None
    assert rejection is not None
    assert rejection["gate_verdict"] == "FAIL"
    assert rejection["failed_step"] == "Risk/Reward"
    assert "ceiling" in rejection["reason"]


def test_blank_stop_loss_always_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(journal_module, "read_open_positions", lambda *a, **k: [])
    row, rejection = build_row("TEST", BRIEF, _verdict(gate=GATE_PASS, stop=None))
    assert row is None
    assert rejection is not None
    assert rejection["failed_step"] == "stop_loss"


def test_conditional_gate_halves_size_and_records_step(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(journal_module, "read_open_positions", lambda *a, **k: [])
    row, rejection = build_row("TEST", BRIEF, _verdict(gate=GATE_COND))
    assert rejection is None
    assert row is not None
    assert row["gate_verdict"] == "CONDITIONAL"
    assert row["gate_failed_step"] == "Risk/Reward"
    # Base size 20.0 (5% stop distance from 100→95) halved to 10.0.
    assert row["position_size_pct"] == 10.0


def test_sector_exposure_ceiling_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    open_positions = [
        {"symbol": "OTHER", "sector": "Healthcare", "position_size_pct": 28.0,
         "stop_loss": 90.0, "entry_type": "initial"},
    ]
    monkeypatch.setattr(journal_module, "read_open_positions", lambda *a, **k: open_positions)
    row, rejection = build_row("TEST", BRIEF, _verdict(gate=GATE_PASS))
    assert row is None
    assert rejection is not None
    assert rejection["failed_step"] == "Portfolio Fit"