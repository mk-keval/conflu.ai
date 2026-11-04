"""Tests for the persistent watchlist service (D-49 PR 1).

D-49 adds a simple in-process watchlist with verdict-change detection.
"""

from __future__ import annotations

import pytest

from backend.app.infrastructure.professional.watchlist_service import (
    WatchlistService,
    get_watchlist_service,
)


@pytest.fixture
def svc() -> WatchlistService:
    return WatchlistService()


# ── Watchlist CRUD ─────────────────────────────────────────────────────


class TestWatchlistCRUD:
    def test_empty_by_default(self, svc):
        assert svc.get_watchlist() == []

    def test_add_single_ticker(self, svc):
        result = svc.add_tickers(["AAPL"])
        assert result == ["AAPL"]

    def test_add_uppercases(self, svc):
        result = svc.add_tickers(["aapl", "msft"])
        assert result == ["AAPL", "MSFT"]

    def test_add_strips_whitespace(self, svc):
        result = svc.add_tickers(["  NVDA  ", "  CRWD"])
        assert result == ["NVDA", "CRWD"]

    def test_add_dedupes(self, svc):
        svc.add_tickers(["AAPL", "MSFT"])
        result = svc.add_tickers(["AAPL", "NVDA"])
        assert result == ["AAPL", "MSFT", "NVDA"]

    def test_remove_ticker(self, svc):
        svc.add_tickers(["AAPL", "MSFT", "NVDA"])
        result = svc.remove_ticker("MSFT")
        assert result == ["AAPL", "NVDA"]

    def test_remove_unknown_ticker_is_noop(self, svc):
        svc.add_tickers(["AAPL"])
        result = svc.remove_ticker("MSFT")
        assert result == ["AAPL"]

    def test_remove_clears_last_known_verdict(self, svc):
        svc.add_tickers(["AAPL"])
        svc.record_verdicts({"AAPL": {"action": "BUY", "conviction": 7}})
        assert svc.get_last_verdict("AAPL") is not None
        svc.remove_ticker("AAPL")
        assert svc.get_last_verdict("AAPL") is None

    def test_clear(self, svc):
        svc.add_tickers(["AAPL", "MSFT"])
        svc.clear()
        assert svc.get_watchlist() == []
        assert svc.get_all_last_verdicts() == {}
        assert svc.get_last_refresh_time() is None


# ── Verdict change detection ──────────────────────────────────────────


class TestVerdictChangeDetection:
    def test_first_record_no_change(self, svc):
        alerts = svc.record_verdicts({"AAPL": {"action": "BUY", "conviction": 7}})
        assert alerts == []

    def test_action_change_emits_alert(self, svc):
        svc.record_verdicts({"AAPL": {"action": "ACCUMULATE", "conviction": 4}})
        alerts = svc.record_verdicts({"AAPL": {"action": "BUY", "conviction": 4}})
        assert len(alerts) == 1
        a = alerts[0]
        assert a["symbol"] == "AAPL"
        assert a["from_action"] == "ACCUMULATE"
        assert a["to_action"] == "BUY"

    def test_conviction_change_of_2_emits_alert(self, svc):
        svc.record_verdicts({"AAPL": {"action": "BUY", "conviction": 5}})
        alerts = svc.record_verdicts({"AAPL": {"action": "BUY", "conviction": 7}})
        assert len(alerts) == 1
        assert alerts[0]["to_conviction"] == 7

    def test_conviction_change_of_1_does_not_alert(self, svc):
        svc.record_verdicts({"AAPL": {"action": "BUY", "conviction": 5}})
        alerts = svc.record_verdicts({"AAPL": {"action": "BUY", "conviction": 6}})
        assert alerts == []

    def test_no_change_does_not_alert(self, svc):
        svc.record_verdicts({"AAPL": {"action": "BUY", "conviction": 7}})
        alerts = svc.record_verdicts({"AAPL": {"action": "BUY", "conviction": 7}})
        assert alerts == []

    def test_multiple_symbols_partial_changes(self, svc):
        svc.record_verdicts({
            "AAPL": {"action": "BUY", "conviction": 7},
            "MSFT": {"action": "BUY", "conviction": 6},
            "NVDA": {"action": "HOLD", "conviction": 3},
        })
        alerts = svc.record_verdicts({
            "AAPL": {"action": "BUY", "conviction": 7},
            "MSFT": {"action": "BUY", "conviction": 8},
            "NVDA": {"action": "ACCUMULATE", "conviction": 5},
        })
        assert len(alerts) == 2


# ── Last refresh state ────────────────────────────────────────────────


class TestLastRefresh:
    def test_last_refresh_time_set(self, svc):
        assert svc.get_last_refresh_time() is None
        svc.set_last_refresh([])
        assert svc.get_last_refresh_time() is not None

    def test_get_last_refresh_alerts(self, svc):
        alerts = [{"symbol": "X", "from_action": "HOLD", "to_action": "BUY"}]
        svc.set_last_refresh(alerts)
        assert svc.get_last_refresh_alerts() == alerts


# ── Module singleton ──────────────────────────────────────────────────


class TestSingleton:
    def test_get_watchlist_service_returns_same_instance(self):
        s1 = get_watchlist_service()
        s2 = get_watchlist_service()
        assert s1 is s2
