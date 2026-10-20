"""Workflow endpoint tests (D-68 plan P2 — correctness rails).

Endpoints are called as plain coroutines (no HTTP layer). FastAPI
``Body``/``Query`` defaults are FieldInfo objects, so tests always pass
explicit arguments. Journal writes land in the per-test tmp DB (conftest
``_isolated_journal_db``).
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from backend.app.domain.workflow import journal as journal_mod


def _wire_enforce_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    tickers: tuple[str, ...] = ("NEW",),
    rows_by_symbol: dict[str, dict] | None = None,
):
    """Stub morning brief + engine + _build_row so enforce/run-close run offline."""
    from backend.app.api import dependencies as deps
    from backend.app.api.routers import workflow as wf

    if rows_by_symbol is None:
        today = journal_mod.market_today()
        rows_by_symbol = {
            s: {
                "date_entered": today, "symbol": s, "sector": "Technology",
                "entry_price": 100.0, "stop_loss": 95.0, "gate_verdict": "PASS",
            }
            for s in tickers
        }

    class _Brief:
        def model_dump(self, mode: str = "json") -> dict:
            return {"screen_sections": [
                {"screen_name": "S",
                 "tickers": [{"symbol": s, "conviction": 9} for s in tickers]},
            ]}

    class _Service:
        async def generate_morning_brief(self):
            return _Brief()

    class _Engine:
        async def analyze_async(self, _req):
            return SimpleNamespace(model_dump=lambda mode="json": {})

    async def _get_engine():
        return _Engine()

    async def _fake_build_row(sym, brief_t, verdict, market_regime=""):
        return dict(rows_by_symbol[sym]), None

    monkeypatch.setattr(wf, "_get_morning_brief_service", lambda: _Service())
    monkeypatch.setattr(deps, "get_ticker_analysis_engine", _get_engine)
    monkeypatch.setattr(wf, "_build_row", _fake_build_row)
    return wf


def _two_bar_ohlcv() -> pd.DataFrame:
    """Bars for an entry dated 2026-10-01: target_1 (110) hit on the next bar."""
    return pd.DataFrame({
        "Date": pd.to_datetime(["2026-10-01", "2026-10-02"]),
        "Open": [100.0, 111.0], "High": [101.0, 112.0],
        "Low": [99.0, 110.0], "Close": [100.5, 111.0],
    })


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
    wf = _wire_enforce_stubs(monkeypatch, tickers=("NEW",))

    today = journal_mod.market_today()
    # Earlier same-day acceptance this run will not re-accept.
    journal_mod.upsert_entry({
        "date_entered": today, "symbol": "OLD", "entry_price": 50.0,
    })

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


def test_run_close_writes_entries_then_exits_one_run_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P3.4: order guarantee, single combined row, idempotent re-run."""
    wf = _wire_enforce_stubs(monkeypatch, tickers=("NEW",))
    journal_mod.upsert_entry({
        "date_entered": "2026-10-01", "symbol": "OLD", "sector": "Technology",
        "entry_price": 100.0, "stop_loss": 95.0, "target_1": 110.0,
    })

    def _fake_ohlcv(sym: str):
        assert sym == "OLD"  # today's NEW row is guard-skipped, never fetched
        return _two_bar_ohlcv()

    monkeypatch.setattr(wf, "_fetch_daily_ohlcv", _fake_ohlcv)

    resp = asyncio.run(wf.run_close(wf.RunCloseRequest(min_conviction=5)))
    data = resp.data
    assert [i.symbol for i in data.enforce.accepted] == ["NEW"]
    assert data.exits.updated == 1

    # Order guarantee: NEW was written by the enforce phase first, so the exit
    # phase saw it and guard-skipped it (skipped, not an error).
    new_item = next(i for i in data.exits.items if i.symbol == "NEW")
    assert new_item.skipped is True
    assert "entered today" in (new_item.skip_reason or "")

    rows = {r["symbol"]: r for r in journal_mod.read_rows()}
    assert rows["OLD"]["date_closed"] == "2026-10-02"
    assert rows["OLD"]["exit_reason"] == "target_1"
    assert not rows["NEW"].get("date_closed")

    # Exactly ONE workflow_runs row for the combined call.
    runs = journal_mod.list_runs(limit=10)
    assert len(runs) == 1
    run = runs[0]
    assert run["mode"] == "run_close"
    assert run["id"] == data.run_id
    assert run["apply"] == 1
    assert run["accepted"] == 1
    assert run["rejected"] == 0
    assert run["updated"] == 1   # exits applied
    assert run["skipped"] == 1   # today's new entry kept open
    assert run["status"] == "ok"
    details = json.loads(run["details_json"])
    assert details["enforce"]["accepted"] == ["NEW"]
    assert details["exits"]["applied"] == ["OLD"]

    # Idempotent re-run: journal state unchanged, one more run row only.
    snapshot = {r["symbol"]: r["date_closed"] for r in journal_mod.read_rows()}
    resp2 = asyncio.run(wf.run_close(wf.RunCloseRequest(min_conviction=5)))
    assert {r["symbol"]: r["date_closed"] for r in journal_mod.read_rows()} == snapshot
    assert resp2.data.enforce.accepted[0].symbol == "NEW"
    assert resp2.data.exits.updated == 0
    runs2 = journal_mod.list_runs(limit=10)
    assert len(runs2) == 2
    assert all(r["mode"] == "run_close" for r in runs2)


def test_run_close_dry_exits_writes_entries_but_no_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wf = _wire_enforce_stubs(monkeypatch, tickers=("NEW",))
    journal_mod.upsert_entry({
        "date_entered": "2026-10-01", "symbol": "OLD",
        "entry_price": 100.0, "stop_loss": 95.0, "target_1": 110.0,
    })
    monkeypatch.setattr(wf, "_fetch_daily_ohlcv", lambda _sym: _two_bar_ohlcv())

    resp = asyncio.run(wf.run_close(wf.RunCloseRequest(apply_exits=False)))
    assert resp.data.exits.updated == 1  # would-be applied (preview)
    assert "would be applied" in resp.data.exits.message
    assert "re-run with apply=true" in resp.data.exits.message
    assert "exits preview only" in resp.data.message

    rows = {r["symbol"]: r for r in journal_mod.read_rows()}
    assert "NEW" in rows                      # entries written
    assert not rows["OLD"].get("date_closed")  # exits only previewed

    run = journal_mod.list_runs(limit=1)[0]
    assert run["mode"] == "run_close"
    assert run["apply"] == 1
    assert run["updated"] == 1  # would-be exits (preview, per message)


def test_run_close_logs_error_row_when_enforce_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import HTTPException

    from backend.app.api.routers import workflow as wf

    class _Service:
        async def generate_morning_brief(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(wf, "_get_morning_brief_service", lambda: _Service())

    with pytest.raises(HTTPException):
        asyncio.run(wf.run_close(wf.RunCloseRequest()))

    run = journal_mod.list_runs(limit=1)[0]
    assert run["mode"] == "run_close"
    assert run["status"] == "error"
    assert "Enforce failed" in run["message"]


def _build_verdict(*, sector: str = "Technology", max_hold: int = 30) -> dict:
    return {
        "sector": sector,
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
            "targets": [110.0, 120.0],
            "risk_reward": 2.0,
            "position_size_pct": 0.0,
            "buy_triggers": ["EMA cross"],
            "trade_plan": {"max_hold_days": max_hold},
        },
    }


def test_build_row_attribution_comes_from_brief_and_response() -> None:
    """Audit F1/F2: screen/confluence from the brief, sector from the response."""
    from backend.app.api.routers import workflow as wf

    brief_t = {"screen_name": "trend-pullback", "confluence_score": 83}
    row, rejection = asyncio.run(
        wf._build_row("TEST", brief_t, _build_verdict(), market_regime="neutral")
    )
    assert rejection is None and row is not None
    assert row["template"] == "trend-pullback"
    assert row["sector"] == "Technology"
    assert row["regime"] == "neutral"
    assert row["max_hold_days"] == 30
    assert row["confluence_count"] == 4


def test_build_row_sector_cap_uses_response_sector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit F2: once sector is populated, the 30% cap actually fires."""
    from backend.app.api.routers import workflow as wf

    monkeypatch.setattr(
        journal_mod, "read_open_positions",
        lambda *a, **k: [{
            "symbol": "OTHER", "sector": "Technology",
            "position_size_pct": "28.0",
        }],
    )
    row, rejection = asyncio.run(
        wf._build_row(
            "TEST",
            {"screen_name": "trend-pullback", "confluence_score": 83},
            _build_verdict(),
            market_regime="neutral",
        )
    )
    assert row is None
    assert rejection is not None
    assert rejection["failed_step"] == "Portfolio Fit"
    assert rejection["template"] == "trend-pullback"
    assert rejection["regime"] == "neutral"


def test_closed_trades_endpoint_excludes_legacy_rows() -> None:
    """The closed-trades summary (win rate/expectancy) is the scored sample only."""
    from backend.app.api.routers import workflow as wf

    for symbol, realized_r, excluded in (("KEEP", 1.0, False), ("LEGACY", -3.0, True)):
        journal_mod.upsert_entry({
            "date_entered": "2026-10-05", "symbol": symbol,
            "sector": "Technology", "entry_price": 100.0, "stop_loss": 95.0,
            "position_size_pct": 10.0, "template": "trend-pullback",
            "regime": "neutral", "gate_verdict": "PASS",
        })
        journal_mod.update_exit("2026-10-05", symbol, {
            "date_closed": "2026-10-09", "exit_price": 100.0 + 5.0 * realized_r,
            "exit_reason": "target_1", "realized_r": realized_r,
        })
        if excluded:
            journal_mod.set_exclude_from_stats("2026-10-05", symbol, True)

    resp = asyncio.run(wf.get_closed_trades())
    assert resp.data.count == 1
    assert [t.symbol for t in resp.data.trades] == ["KEEP"]
    assert resp.data.expectancy_r == 1.0
