"""Bundle A (D-77) — workflow wiring: row provenance, rejections, sync legs."""

from __future__ import annotations

import asyncio
import json

import pandas as pd
import pytest

from backend.app.domain.workflow import journal as journal_mod
from backend.app.domain.workflow import verification


def _build_verdict(*, screen_targets: list[float] | None = None) -> dict:
    return {
        "sector": "Technology",
        "verdict": {
            "action": "BUY",
            "conviction": 8,
            "gate": {
                "overall": "PASS",
                "conviction_score": 8,
                "data_gaps": [],
                "evaluated_at": "2026-10-19T00:00:00",
                "steps": [{
                    "name": "Portfolio Fit", "passed": False,
                    "conditional": True, "note": "synthesis path",
                }],
            },
            "entry_zone_low": 100.0,
            "entry_zone_high": 102.0,
            "stop_loss": 95.0,
            "targets": screen_targets or [110.0, 115.0, 120.0],
            "risk_reward": 2.0,
            "position_size_pct": 0.0,
            "buy_triggers": ["EMA cross"],
            "trade_plan": {
                "max_hold_days": 20,
                "atr_at_entry": 1.0,
                "setup_family": "breakout",
            },
        },
    }


def test_build_row_stores_family_planned_fill_metrics_and_atr() -> None:
    from backend.app.api.routers import workflow as wf

    row, rejection = asyncio.run(wf._build_row(
        "TEST",
        {"screen_name": "52-Week Breakout", "confluence_score": 80},
        _build_verdict(),
        market_regime="neutral",
    ))

    assert rejection is None and row is not None
    assert row["setup_family"] == "breakout"
    assert row["atr_at_entry"] == 1.0
    # Planned fill 100, stop 95 -> 1R = 5. T1 110 = 2.0R, T3 120 = 4.0R.
    assert row["plan_rr"] == 2.0
    assert row["target_1_r"] == 2.0
    assert row["stretch_rr"] == 4.0


def test_build_row_rejects_a_plan_without_a_structural_target() -> None:
    from backend.app.api.routers import workflow as wf

    verdict = _build_verdict()
    verdict["verdict"]["plan_rejection"] = "target too far"
    verdict["verdict"]["targets"] = []
    verdict["verdict"]["risk_reward"] = None

    row, rejection = asyncio.run(wf._build_row(
        "TEST",
        {"screen_name": "52-Week Breakout", "confluence_score": 80},
        verdict,
        market_regime="neutral",
    ))

    assert row is None
    assert rejection is not None
    assert rejection["failed_step"] == "plan"
    assert "target too far" in rejection["reason"]
    assert rejection["template"] == "52-Week Breakout"


def test_sync_exits_writes_weighted_v02_legs(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.api.routers import workflow as wf

    journal_mod.upsert_entry({
        "date_entered": "2026-10-01", "symbol": "AAA", "sector": "Technology",
        "entry_price": 100.0, "stop_loss": 95.0, "position_size_pct": 10.0,
        "shares": 100.0, "target_1": 110.0, "target_2": 115.0, "target_3": 120.0,
        "setup_family": "trend", "atr_at_entry": 1.0,
        "max_hold_days": 30, "gate_verdict": "PASS",
        "sample_version": "v0.2",
    })

    bars = pd.DataFrame({
        "Date": pd.to_datetime([
            "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04",
        ]),
        "Open": [100.0, 101.0, 112.0, 114.0],
        "High": [101.0, 111.0, 116.0, 115.0],
        "Low": [99.0, 100.5, 111.0, 112.0],
        "Close": [100.0, 110.5, 115.5, 113.0],
    })
    monkeypatch.setattr(wf, "_fetch_daily_ohlcv", lambda _sym: bars)

    resp = asyncio.run(wf.sync_exits(wf.SyncExitsRequest(apply=True)))

    assert resp.data.updated == 1
    item = resp.data.items[0]
    assert item.setup_family == "trend"
    legs = json.loads(item.exit_legs)
    assert [leg["reason"] for leg in legs] == ["target_1", "target_2", "trail"]
    # 1/3 at 110, 1/3 at 115, 1/3 at 113.5 (2x1.0 ATR trail under the 115.5 close)
    vwap = (110 + 115 + 113.5) / 3
    assert item.exit_price == pytest.approx(round(vwap, 2))
    assert item.realized_r == pytest.approx(round((vwap - 100) / 5, 2))
    assert item.plan_adherence == 0.5

    row = journal_mod.read_rows()[0]
    assert row["exit_reason"] == "scale_out"
    assert row["exit_legs"] == item.exit_legs
    # The row the sync wrote passes the D-77 leg invariants.
    assert verification.find_exit_leg_issues([row]) == []
