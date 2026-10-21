"""Workflow endpoint tests (D-68 plan P2 — correctness rails).

Endpoints are called as plain coroutines (no HTTP layer). FastAPI
``Body``/``Query`` defaults are FieldInfo objects, so tests always pass
explicit arguments. Journal writes land in the per-test tmp DB (conftest
``_isolated_journal_db``).
"""

from __future__ import annotations

import asyncio
import json
from datetime import date, timedelta
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


def _previous_session(today: str) -> str:
    """Most recent weekday before ``today`` (test date arithmetic only)."""
    day = date.fromisoformat(today) - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day.isoformat()


def _pending_bars(signal: str, today: str) -> pd.DataFrame:
    """Signal-day low 98 (must be ignored) + today's touch of the 100 limit."""
    return pd.DataFrame({
        "Date": pd.to_datetime([signal, today]),
        "Open": [101.0, 101.0], "High": [103.0, 102.0],
        "Low": [98.0, 99.5], "Close": [102.0, 100.5],
    })


def _queue_pending(signal: str, **over: object) -> int:
    row: dict[str, object] = {
        "date_entered": signal, "symbol": "AAA", "sector": "Technology",
        "entry_low": 100.0, "entry_high": 102.0, "entry_price": 100.0,
        "stop_loss": 95.0, "target_1": 110.0, "target_2": 120.0,
        "position_size_pct": 20.0, "account_value": 100_000.0,
        "gate_verdict": "PASS", "template": "trend-pullback",
        "regime": "neutral", "notes": "test signal",
    }
    row.update(over)
    order_id = journal_mod.insert_pending_order(row)
    assert order_id
    return order_id


def test_pending_fills_from_next_session_not_the_signal_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-73 regression: the signal-day low (98) is not a fill; T+1 is."""
    wf = _wire_enforce_stubs(monkeypatch, tickers=())
    today = journal_mod.market_today()
    signal = _previous_session(today)
    _queue_pending(signal)
    monkeypatch.setattr(wf, "_fetch_daily_ohlcv", lambda _sym: _pending_bars(signal, today))

    resp = asyncio.run(wf.enforce_paper_trades(wf.EnforceRequest()))
    assert len(resp.data.fills) == 1
    fill = resp.data.fills[0]
    assert fill.symbol == "AAA"
    assert fill.fill_date == today
    assert fill.fill_price == 100.0
    assert fill.same_day_stop is False

    rows = journal_mod.read_rows()
    assert len(rows) == 1
    row = rows[0]
    assert row["date_entered"] == today
    assert row["entry_price"] == "100.0"
    assert row["entry_timing"] == "t1_limit"
    assert row["shares"] == "200.0"
    assert "Pending limit $100.00 filled" in (row["notes"] or "")
    assert journal_mod.list_pending_orders("pending") == []
    assert journal_mod.list_pending_orders("all")[0]["status"] == "filled"


def test_pending_signal_is_never_filled_by_the_signal_day_bar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exact phantom-fill case: a same-day bar below the limit is ignored."""
    wf = _wire_enforce_stubs(monkeypatch, tickers=())
    today = journal_mod.market_today()
    _queue_pending(today)
    monkeypatch.setattr(wf, "_fetch_daily_ohlcv", lambda _sym: pd.DataFrame({
        "Date": pd.to_datetime([today]),
        "Open": [101.0], "High": [103.0], "Low": [98.0], "Close": [102.0],
    }))

    resp = asyncio.run(wf.enforce_paper_trades(wf.EnforceRequest()))
    assert resp.data.fills == []
    assert journal_mod.read_rows() == []
    pending = journal_mod.list_pending_orders("pending")
    assert len(pending) == 1 and pending[0]["status"] == "pending"


def test_pending_expires_after_the_configured_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wf = _wire_enforce_stubs(monkeypatch, tickers=())
    today = journal_mod.market_today()
    signal = (date.fromisoformat(today) - timedelta(days=10)).isoformat()
    _queue_pending(signal, expires_after_sessions=3)
    dates = pd.bdate_range(end=today, periods=4)
    frame = pd.DataFrame({
        "Date": dates,
        "Open": [103.0] * 4, "High": [104.0] * 4,
        "Low": [101.0] * 4, "Close": [102.0] * 4,  # never touches 100
    })
    monkeypatch.setattr(wf, "_fetch_daily_ohlcv", lambda _sym: frame)

    resp = asyncio.run(wf.enforce_paper_trades(wf.EnforceRequest()))
    assert resp.data.fills == []
    assert len(resp.data.closed_orders) == 1
    assert resp.data.closed_orders[0].status == "expired"
    assert journal_mod.read_rows() == []
    assert journal_mod.list_pending_orders("pending") == []
    expired = journal_mod.list_pending_orders("expired")[0]
    assert expired["status_date"] == dates[-2].strftime("%Y-%m-%d")  # 3rd session


def test_pending_fill_with_same_session_stop_closes_at_minus_one_r(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wf = _wire_enforce_stubs(monkeypatch, tickers=())
    today = journal_mod.market_today()
    signal = _previous_session(today)
    _queue_pending(signal)
    monkeypatch.setattr(wf, "_fetch_daily_ohlcv", lambda _sym: pd.DataFrame({
        "Date": pd.to_datetime([signal, today]),
        "Open": [101.0, 101.0], "High": [103.0, 102.0],
        "Low": [98.0, 94.0], "Close": [102.0, 96.0],  # fill 100 → stop 95
    }))

    resp = asyncio.run(wf.enforce_paper_trades(wf.EnforceRequest()))
    assert resp.data.fills[0].same_day_stop is True
    row = journal_mod.read_rows()[0]
    assert row["date_entered"] == today
    assert row["date_closed"] == today
    assert row["exit_reason"] == "stop"
    assert row["exit_price"] == "95.0"
    assert row["realized_r"] == "-1.0"
    assert row["pnl_usd"] == "-1000.0"


def test_open_positions_exclude_voided_and_include_pending() -> None:
    from backend.app.api.routers import workflow as wf

    today = journal_mod.market_today()
    journal_mod.upsert_entry({
        "date_entered": "2026-10-19", "symbol": "BAD",
        "entry_price": 185.97, "stop_loss": 180.0,
    })
    journal_mod.void_trade("2026-10-19", "BAD", "phantom fill")
    _queue_pending(today, symbol="WAIT")

    resp = asyncio.run(wf.get_open_positions())
    assert resp.data.positions == []
    assert resp.data.pending_count == 1
    assert resp.data.pending_orders[0].symbol == "WAIT"

    listed = asyncio.run(wf.get_pending_orders(status="pending", limit=200))
    assert listed.data.count == 1
    assert listed.data.items[0].order_type == "limit"


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
    # Earlier same-day order this run will not re-accept.
    journal_mod.insert_pending_order({
        "date_entered": today, "symbol": "OLD", "entry_low": 50.0,
        "entry_price": 50.0, "stop_loss": 45.0,
    })

    resp = asyncio.run(wf.enforce_paper_trades(wf.EnforceRequest(min_conviction=5)))
    assert [i.symbol for i in resp.data.accepted] == ["NEW"]
    assert resp.data.accepted[0].order_status == "pending"
    assert "1 earlier pending order(s) kept" in resp.data.message

    # Accepted signals are orders, not journal entries yet.
    assert journal_mod.read_rows() == []
    pending = {o["symbol"]: o for o in journal_mod.list_pending_orders("pending")}
    assert set(pending) == {"NEW", "OLD"}
    run = journal_mod.list_runs(limit=1)[0]
    assert run["mode"] == "enforce"
    assert run["apply"] == 1
    assert run["accepted"] == 1
    assert run["rejected"] == 0
    assert run["updated"] == 0  # no fills this run
    assert run["skipped"] == 1  # earlier same-day pending order kept
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


def test_run_close_fills_then_queues_pending_then_exits_one_run_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-73 order guarantee: fills → new pending orders → exits; one run row."""
    wf = _wire_enforce_stubs(monkeypatch, tickers=("NEW",))
    journal_mod.upsert_entry({
        "date_entered": "2026-10-01", "symbol": "OLD", "sector": "Technology",
        "entry_price": 100.0, "stop_loss": 95.0, "target_1": 110.0,
    })

    def _fake_ohlcv(sym: str):
        # OLD needs exit bars; NEW (queued today) has no eligible T+1 bar yet.
        return _two_bar_ohlcv()

    monkeypatch.setattr(wf, "_fetch_daily_ohlcv", _fake_ohlcv)

    resp = asyncio.run(wf.run_close(wf.RunCloseRequest(min_conviction=5)))
    data = resp.data
    assert [i.symbol for i in data.enforce.accepted] == ["NEW"]
    assert data.exits.updated == 1

    # NEW is a pending order, not a same-day journal fill.
    pending = journal_mod.list_pending_orders("pending")
    assert [o["symbol"] for o in pending] == ["NEW"]
    assert [i.symbol for i in data.exits.items] == ["OLD"]  # NEW has no position yet

    rows = {r["symbol"]: r for r in journal_mod.read_rows()}
    assert rows["OLD"]["date_closed"] == "2026-10-02"
    assert rows["OLD"]["exit_reason"] == "target_1"
    assert "NEW" not in rows

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
    assert run["skipped"] == 0
    assert run["status"] == "ok"
    details = json.loads(run["details_json"])
    assert details["enforce"]["accepted"] == ["NEW"]
    assert details["exits"]["applied"] == ["OLD"]

    # Idempotent re-run: the active NEW order is not duplicated, is reported as
    # already queued (not rejected), and no rejection row is written.
    snapshot = {r["symbol"]: r["date_closed"] for r in journal_mod.read_rows()}
    resp2 = asyncio.run(wf.run_close(wf.RunCloseRequest(min_conviction=5)))
    assert {r["symbol"]: r["date_closed"] for r in journal_mod.read_rows()} == snapshot
    assert [i.symbol for i in resp2.data.enforce.accepted] == ["NEW"]
    assert resp2.data.enforce.accepted[0].order_status == "pending"
    assert resp2.data.enforce.rejected == []
    assert "0 pending order(s) created, 1 already queued today" in resp2.data.enforce.message
    assert len(journal_mod.list_pending_orders("pending")) == 1
    assert journal_mod.list_rejections(limit=50) == []
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
    assert "NEW" not in rows                      # NEW is a pending order
    assert journal_mod.list_pending_orders("pending")[0]["symbol"] == "NEW"
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
