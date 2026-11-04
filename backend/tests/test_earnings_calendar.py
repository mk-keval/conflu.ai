"""Tests for the yfinance-backed earnings calendar (D-48 PR 2).

Replaces the hand-curated JSON with a yfinance-backed implementation.
The JSON is now a *manual override* (for tickers where yfinance is
wrong), not the primary data source.

These tests use mocked yfinance to avoid network calls. We verify:
  1. yfinance earningsTimestampStart is used (the NEXT earnings date)
  2. yfinance earningsTimestamp is used as fallback
  3. Cache hits/misses work correctly
  4. Manual override takes precedence
  5. yfinance exception path returns (False, None) safely
  6. Window filtering: only earnings in next N days return True
"""

from __future__ import annotations

import datetime as _dt
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from backend.app.domain.ticker_analysis import earnings_filter


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_caches():
    """Each test starts with a fresh cache."""
    earnings_filter.clear_cache()
    yield
    earnings_filter.clear_cache()


def _make_yf_info(timestamp: int | None) -> dict:
    """Build a yfinance .info dict with the given next-earnings timestamp."""
    info = {}
    if timestamp is not None:
        info["earningsTimestampStart"] = timestamp
    return info


# ── _fetch_yfinance_earnings ────────────────────────────────────────────


class TestFetchYfinanceEarnings:
    @patch("backend.app.domain.ticker_analysis.earnings_filter.yf.Ticker")
    def test_uses_earningsTimestampStart(self, mock_ticker):
        # OKTA prints tomorrow
        ts = int((_dt.datetime.now() + _dt.timedelta(days=1)).timestamp())
        mock_ticker.return_value.info = _make_yf_info(ts)
        result = earnings_filter._fetch_yfinance_earnings("OKTA")
        assert result == _dt.datetime.fromtimestamp(ts, tz=_dt.timezone.utc).date().isoformat()

    @patch("backend.app.domain.ticker_analysis.earnings_filter.yf.Ticker")
    def test_falls_back_to_earningsTimestamp(self, mock_ticker):
        # Only earningsTimestamp (most recent) is set, no Start
        ts = int((_dt.datetime.now() + _dt.timedelta(days=2)).timestamp())
        info = {"earningsTimestamp": ts}
        mock_ticker.return_value.info = info
        result = earnings_filter._fetch_yfinance_earnings("XYZ")
        assert result == _dt.datetime.fromtimestamp(ts, tz=_dt.timezone.utc).date().isoformat()

    @patch("backend.app.domain.ticker_analysis.earnings_filter.yf.Ticker")
    def test_no_earnings_data_returns_none(self, mock_ticker):
        mock_ticker.return_value.info = {}
        result = earnings_filter._fetch_yfinance_earnings("NODATA")
        assert result is None

    @patch("backend.app.domain.ticker_analysis.earnings_filter.yf.Ticker")
    def test_yfinance_exception_returns_none(self, mock_ticker):
        mock_ticker.side_effect = Exception("network error")
        result = earnings_filter._fetch_yfinance_earnings("BAD")
        assert result is None

    @patch("backend.app.domain.ticker_analysis.earnings_filter.yf.Ticker")
    def test_cache_hit_skips_yfinance(self, mock_ticker):
        # Pre-populate the cache
        earnings_filter._calendar_cache["CACHED"] = (
            _dt.datetime.now().timestamp(),
            "2026-12-01",
        )
        result = earnings_filter._fetch_yfinance_earnings("CACHED")
        assert result == "2026-12-01"
        # yfinance should NOT have been called
        mock_ticker.assert_not_called()

    @patch("backend.app.domain.ticker_analysis.earnings_filter.yf.Ticker")
    def test_caches_none_result_too(self, mock_ticker):
        """If yfinance returns no data, we cache None to avoid hammering it."""
        mock_ticker.return_value.info = {}
        earnings_filter._fetch_yfinance_earnings("NOPE")
        # Second call should use cache, not call yfinance
        mock_ticker.reset_mock()
        result = earnings_filter._fetch_yfinance_earnings("NOPE")
        assert result is None
        mock_ticker.assert_not_called()


# ── _load_manual_overrides ──────────────────────────────────────────────


class TestLoadManualOverrides:
    def test_missing_file_returns_empty_list(self):
        """When earnings_calendar.json doesn't exist, return []."""
        with patch.object(earnings_filter, "_CALENDAR_PATH",
                          Path("/nonexistent/path/calendar.json")):
            result = earnings_filter._load_manual_overrides()
            assert result == []

    def test_empty_file_returns_empty_list(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("[]")
            path = Path(f.name)
        try:
            with patch.object(earnings_filter, "_CALENDAR_PATH", path):
                earnings_filter.clear_cache()
                result = earnings_filter._load_manual_overrides()
                assert result == []
        finally:
            path.unlink()
            earnings_filter.clear_cache()

    def test_parses_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [{"ticker": "AAPL", "report_date": "2026-10-30", "session": "after-close"}],
                f,
            )
            path = Path(f.name)
        try:
            with patch.object(earnings_filter, "_CALENDAR_PATH", path):
                earnings_filter.clear_cache()
                result = earnings_filter._load_manual_overrides()
                assert result == [
                    {"ticker": "AAPL", "report_date": "2026-10-30", "session": "after-close"}
                ]
        finally:
            path.unlink()
            earnings_filter.clear_cache()

    def test_invalid_json_returns_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{not valid json")
            path = Path(f.name)
        try:
            with patch.object(earnings_filter, "_CALENDAR_PATH", path):
                earnings_filter.clear_cache()
                result = earnings_filter._load_manual_overrides()
                assert result == []
        finally:
            path.unlink()
            earnings_filter.clear_cache()


# ── get_binary_risk — full integration ─────────────────────────────────


class TestGetBinaryRisk:
    @patch("backend.app.domain.ticker_analysis.earnings_filter.yf.Ticker")
    def test_earnings_in_5d_returns_true(self, mock_ticker):
        # Earnings in 3 days
        ts = int((_dt.datetime.now() + _dt.timedelta(days=3)).timestamp())
        mock_ticker.return_value.info = _make_yf_info(ts)
        binary_risk, earnings_date = earnings_filter.get_binary_risk("AAPL", window_days=5)
        assert binary_risk is True
        assert earnings_date is not None

    @patch("backend.app.domain.ticker_analysis.earnings_filter.yf.Ticker")
    def test_earnings_in_7d_returns_false_with_5d_window(self, mock_ticker):
        # Earnings in 7 days, window is 5
        ts = int((_dt.datetime.now() + _dt.timedelta(days=7)).timestamp())
        mock_ticker.return_value.info = _make_yf_info(ts)
        binary_risk, earnings_date = earnings_filter.get_binary_risk("AAPL", window_days=5)
        assert binary_risk is False
        # Out-of-window returns (False, None) — date is not returned
        # unless binary_risk is True (preserves original API contract)
        assert earnings_date is None

    @patch("backend.app.domain.ticker_analysis.earnings_filter.yf.Ticker")
    def test_earnings_in_past_returns_false(self, mock_ticker):
        # Earnings was 30 days ago
        ts = int((_dt.datetime.now() - _dt.timedelta(days=30)).timestamp())
        mock_ticker.return_value.info = _make_yf_info(ts)
        binary_risk, earnings_date = earnings_filter.get_binary_risk("AAPL", window_days=5)
        assert binary_risk is False
        assert earnings_date is None

    @patch("backend.app.domain.ticker_analysis.earnings_filter.yf.Ticker")
    def test_no_data_returns_safe_default(self, mock_ticker):
        mock_ticker.return_value.info = {}
        binary_risk, earnings_date = earnings_filter.get_binary_risk("NOPE")
        assert binary_risk is False
        assert earnings_date is None

    @patch("backend.app.domain.ticker_analysis.earnings_filter.yf.Ticker")
    def test_manual_override_takes_precedence(self, mock_ticker):
        # yfinance says earnings in 30 days (not in window)
        ts = int((_dt.datetime.now() + _dt.timedelta(days=30)).timestamp())
        mock_ticker.return_value.info = _make_yf_info(ts)

        # But manual override says earnings in 2 days
        report_date = (_dt.date.today() + _dt.timedelta(days=2)).isoformat()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [{"ticker": "AAPL", "report_date": report_date, "session": "after-close"}],
                f,
            )
            path = Path(f.name)
        try:
            with patch.object(earnings_filter, "_CALENDAR_PATH", path):
                earnings_filter.clear_cache()
                binary_risk, earnings_date = earnings_filter.get_binary_risk("AAPL", window_days=5)
                assert binary_risk is True
                assert earnings_date == report_date
        finally:
            path.unlink()
            earnings_filter.clear_cache()

    def test_manual_only_skips_yfinance_fallback(self):
        with patch.object(
            earnings_filter,
            "_fetch_yfinance_earnings",
            side_effect=AssertionError("screener path must not call yfinance"),
        ):
            binary_risk, earnings_date = earnings_filter.get_binary_risk(
                "ZZZZ", allow_yfinance=False
            )
        assert binary_risk is False
        assert earnings_date is None

    def test_manual_only_still_reads_manual_calendar(self):
        report_date = (_dt.date.today() + _dt.timedelta(days=2)).isoformat()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                [{"ticker": "AAPL", "report_date": report_date, "session": "after-close"}],
                f,
            )
            path = Path(f.name)
        try:
            with patch.object(earnings_filter, "_CALENDAR_PATH", path):
                earnings_filter.clear_cache()
                with patch.object(
                    earnings_filter,
                    "_fetch_yfinance_earnings",
                    side_effect=AssertionError("screener path must not call yfinance"),
                ):
                    binary_risk, earnings_date = earnings_filter.get_binary_risk(
                        "AAPL", allow_yfinance=False
                    )
                assert binary_risk is True
                assert earnings_date == report_date
        finally:
            path.unlink()
            earnings_filter.clear_cache()
