"""Workflow endpoint tests (D-68 plan P2 — correctness rails).

Endpoints are called as plain coroutines (no HTTP layer). FastAPI
``Body``/``Query`` defaults are FieldInfo objects, so tests always pass
explicit arguments. Journal writes land in the per-test tmp DB (conftest
``_isolated_journal_db``).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from backend.app.domain.workflow import journal as journal_mod


def test_sync_exits_same_day_guard_and_run_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.api.routers import workflow as wf

    today = journal_mod.market_today()
    journal_mod.upsert_entry({
        "date_entered": today, "symbol": "AAA", "sector": "Technology",
        "entry_price": 100.0, "stop_loss": 95.0, "target_1": 110.0,
    })

    def _must_not_fetch(_sym: str):
        raise AssertionError("no OHLCV fetch for rows entered today")

    monkeypatch.setattr(wf, "_fetch_daily_ohlcv", _must_not_fetch)

    resp = asyncio.run(wf.sync_exits(wf.SyncExitsRequest(apply=True)))
    assert resp.data.updated == 0
    assert resp.data.skipped == 1
    item = resp.data.items[0]
    assert item.skipped is True
    assert item.skip_reason == "entered today — exits start next session"
    # The guard does not close the row.
    assert not journal_mod.read_rows()[0].get("date_closed")

    run = journal_mod.list_runs(limit=1)[0]
    assert run["mode"] == "sync_exits"
    assert run["apply"] == 1
    assert run["updated"] == 0
    assert run["skipped"] == 1


def test_sync_exits_with_no_open_rows_still_logs_run() -> None:
    from backend.app.api.routers import workflow as wf

    resp = asyncio.run(wf.sync_exits(wf.SyncExitsRequest()))
    assert resp.data.updated == 0
    assert resp.data.items == []

    run = journal_mod.list_runs(limit=1)[0]
    assert run["mode"] == "sync_exits"
    assert run["apply"] == 0
    assert run["message"] == "No open journal rows to sync."


def test_enforce_logs_run_and_reports_kept_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.api import dependencies as deps
    from backend.app.api.routers import workflow as wf

    today = journal_mod.market_today()
    # Earlier same-day acceptance this run will not re-accept.
    journal_mod.upsert_entry({
        "date_entered": today, "symbol": "OLD", "entry_price": 50.0,
    })

    class _Brief:
        def model_dump(self, mode: str = "json") -> dict:
            return {"screen_sections": [
                {"screen_name": "S", "tickers": [{"symbol": "NEW", "conviction": 9}]},
            ]}

    class _Service:
        async def generate_morning_brief(self):
            return _Brief()

    class _Engine:
        async def analyze_async(self, _req):
            return SimpleNamespace(model_dump=lambda mode="json": {})

    async def _get_engine():
        return _Engine()

    async def _fake_build_row(sym, brief_t, verdict):
        return {
            "date_entered": today, "symbol": sym, "sector": "Technology",
            "entry_price": 100.0, "stop_loss": 95.0, "gate_verdict": "PASS",
        }, None

    monkeypatch.setattr(wf, "_get_morning_brief_service", lambda: _Service())
    monkeypatch.setattr(deps, "get_ticker_analysis_engine", _get_engine)
    monkeypatch.setattr(wf, "_build_row", _fake_build_row)

    resp = asyncio.run(wf.enforce_paper_trades(wf.EnforceRequest(min_conviction=5)))
    assert [i.symbol for i in resp.data.accepted] == ["NEW"]
    assert "1 earlier acceptance(s) kept" in resp.data.message

    assert {r["symbol"] for r in journal_mod.read_rows()} == {"NEW", "OLD"}
    run = journal_mod.list_runs(limit=1)[0]
    assert run["mode"] == "enforce"
    assert run["apply"] == 1
    assert run["accepted"] == 1
    assert run["rejected"] == 0
    assert run["updated"] == 1
    assert run["skipped"] == 1  # earlier same-day acceptance kept
    assert run["status"] == "ok"


def test_runs_and_rejections_endpoints() -> None:
    from backend.app.api.routers import workflow as wf

    journal_mod.insert_rejection({
        "date_seen": journal_mod.market_today(), "symbol": "BBB",
        "sector": "Technology", "action": "WATCH", "conviction": 4,
        "failed_step": "Conviction", "gate_verdict": "FAIL",
        "reason": "below conviction floor", "notes": "",
    })
    journal_mod.record_run(
        "enforce", apply=True, accepted=1, rejected=1, message="m",
        details={"accepted": ["NEW"], "rejected": ["BBB"]},
    )

    rej = asyncio.run(wf.get_journal_rejections(limit=200))
    assert rej.data.count == 1
    assert rej.data.items[0].symbol == "BBB"
    assert rej.data.items[0].conviction == 4
    assert rej.data.items[0].failed_step == "Conviction"

    runs = asyncio.run(wf.get_runs(limit=14))
    assert runs.data.count == 1
    item = runs.data.items[0]
    assert item.mode == "enforce"
    assert item.apply is True
    assert item.details == {"accepted": ["NEW"], "rejected": ["BBB"]}


def test_export_endpoint_returns_csv() -> None:
    from backend.app.api.routers import workflow as wf

    journal_mod.upsert_entry({
        "date_entered": "2026-10-05", "symbol": "AAPL", "entry_price": 219.0,
    })
    resp = asyncio.run(wf.export_journal())
    text = resp.body.decode("utf-8")
    lines = text.strip().splitlines()
    assert lines[0].startswith("date_entered,symbol,")
    assert "entry_timing" in lines[0]
    assert "AAPL" in lines[1]
    assert resp.media_type == "text/csv"
