"""Tests for the unusual options activity detector (D-46 PR 5).

The elite trader watches for unusual options activity as a confirmation
signal. Call/put volume ratio > 2x + call volume > 1.5x open interest
= bullish (smart money opening new long positions). These tests use
mocked yfinance data so they're fast and deterministic.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from backend.app.infrastructure import options_flow


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_option_df(rows: list[dict]) -> pd.DataFrame:
    """Build a yfinance-style options chain DataFrame."""
    return pd.DataFrame(rows)


def _call(strike: float, vol: int, oi: int) -> dict:
    return {
        "strike": strike,
        "volume": vol,
        "openInterest": oi,
        "lastPrice": 5.0,
        "impliedVolatility": 0.5,
    }


def _put(strike: float, vol: int, oi: int) -> dict:
    return {
        "strike": strike,
        "volume": vol,
        "openInterest": oi,
        "lastPrice": 5.0,
        "impliedVolatility": 0.5,
    }


def _build_chain(call_rows: list[dict], put_rows: list[dict]):
    """Return a MagicMock that mimics yf.Ticker(...).option_chain() result."""
    calls = _make_option_df(call_rows)
    puts = _make_option_df(put_rows)
    chain = MagicMock()
    chain.calls = calls
    chain.puts = puts
    return chain


# ── detect_unusual_options_activity ─────────────────────────────────────


class TestDetectUnusualOptionsActivity:
    @patch("backend.app.infrastructure.options_flow.yf.Ticker")
    def test_bullish_call_activity(self, mock_ticker):
        # 5000 calls, 1000 puts → ratio 5.0 (>2.0 threshold)
        # call OI = 2000, call vol = 5000 → vol/OI 2.5 (>1.5 threshold)
        # = bullish unusual activity
        calls = [_call(80, 1000, 400), _call(85, 2000, 800), _call(90, 2000, 800)]
        puts = [_put(75, 200, 1000), _put(70, 400, 1500), _put(65, 400, 1500)]
        y = MagicMock()
        y.options = ("2026-09-04",)
        y.option_chain.return_value = _build_chain(calls, puts)
        mock_ticker.return_value = y

        flow = options_flow.detect_unusual_options_activity("TEST")
        assert flow is not None
        assert flow.bias == "bullish"
        assert flow.call_volume == 5000
        assert flow.put_volume == 1000
        assert flow.call_put_volume_ratio == pytest.approx(5.0)
        assert flow.call_volume_oi_ratio == pytest.approx(2.5)
        # Should produce a bullish finding
        assert any("Unusual call activity" in f for f in flow.findings)

    @patch("backend.app.infrastructure.options_flow.yf.Ticker")
    def test_bearish_put_activity(self, mock_ticker):
        # Reverse: more puts than calls
        calls = [_call(80, 200, 1000), _call(85, 200, 1000)]
        puts = [_put(75, 2000, 800), _put(70, 3000, 1500)]
        y = MagicMock()
        y.options = ("2026-09-04",)
        y.option_chain.return_value = _build_chain(calls, puts)
        mock_ticker.return_value = y

        flow = options_flow.detect_unusual_options_activity("TEST")
        assert flow is not None
        assert flow.bias == "bearish"
        assert flow.put_volume == 5000
        assert flow.call_volume == 400
        # Should produce a bearish finding
        assert any("Unusual put activity" in f for f in flow.findings)

    @patch("backend.app.infrastructure.options_flow.yf.Ticker")
    def test_neutral_no_signal(self, mock_ticker):
        # Ratio ~1.0, no unusual vol/OI
        calls = [_call(80, 500, 1000), _call(85, 500, 1000)]
        puts = [_put(75, 500, 1000), _put(70, 500, 1000)]
        y = MagicMock()
        y.options = ("2026-09-04",)
        y.option_chain.return_value = _build_chain(calls, puts)
        mock_ticker.return_value = y

        flow = options_flow.detect_unusual_options_activity("TEST")
        # Ratio 1.0 < 2.0 threshold → not bullish
        # Inverse ratio 1.0 < 2.0 threshold → not bearish
        assert flow is None

    @patch("backend.app.infrastructure.options_flow.yf.Ticker")
    def test_no_options_data(self, mock_ticker):
        y = MagicMock()
        y.options = ()
        mock_ticker.return_value = y
        flow = options_flow.detect_unusual_options_activity("TEST")
        assert flow is None

    @patch("backend.app.infrastructure.options_flow.yf.Ticker")
    def test_empty_options_chain(self, mock_ticker):
        y = MagicMock()
        y.options = ("2026-09-04",)
        y.option_chain.return_value = _build_chain([], [])
        mock_ticker.return_value = y
        flow = options_flow.detect_unusual_options_activity("TEST")
        assert flow is None

    @patch("backend.app.infrastructure.options_flow.yf.Ticker")
    def test_low_volume_returns_none(self, mock_ticker):
        # 50 calls, 50 puts → total 100 < MIN_TOTAL_VOLUME (1000)
        calls = [_call(80, 30, 100), _call(85, 20, 100)]
        puts = [_put(75, 30, 100), _put(70, 20, 100)]
        y = MagicMock()
        y.options = ("2026-09-04",)
        y.option_chain.return_value = _build_chain(calls, puts)
        mock_ticker.return_value = y
        flow = options_flow.detect_unusual_options_activity("TEST")
        assert flow is None

    @patch("backend.app.infrastructure.options_flow.yf.Ticker")
    def test_call_oi_zero_uses_infinity(self, mock_ticker):
        # If call OI is 0 but call volume is high, vol/OI is inf → bullish
        calls = [_call(80, 5000, 0)]
        puts = [_put(75, 100, 1000)]
        y = MagicMock()
        y.options = ("2026-09-04",)
        y.option_chain.return_value = _build_chain(calls, puts)
        mock_ticker.return_value = y
        flow = options_flow.detect_unusual_options_activity("TEST")
        assert flow is not None
        assert flow.bias == "bullish"
        assert flow.call_volume_oi_ratio == float("inf")

    @patch("backend.app.infrastructure.options_flow.yf.Ticker")
    def test_exception_during_fetch(self, mock_ticker):
        mock_ticker.side_effect = Exception("network error")
        flow = options_flow.detect_unusual_options_activity("TEST")
        assert flow is None

    @patch("backend.app.infrastructure.options_flow.yf.Ticker")
    def test_uses_nearest_expiration(self, mock_ticker):
        # yfinance gives multiple expirations; we use the first
        calls = [_call(80, 2000, 500)]
        puts = [_put(75, 200, 2000)]
        y = MagicMock()
        y.options = ("2026-09-04", "2026-09-11", "2026-09-18")
        y.option_chain.return_value = _build_chain(calls, puts)
        mock_ticker.return_value = y
        flow = options_flow.detect_unusual_options_activity("TEST")
        assert flow is not None
        assert flow.expiration == "2026-09-04"  # nearest

    @patch("backend.app.infrastructure.options_flow.yf.Ticker")
    def test_to_dict(self, mock_ticker):
        calls = [_call(80, 1000, 400), _call(85, 2000, 800)]
        puts = [_put(75, 200, 1000)]
        y = MagicMock()
        y.options = ("2026-09-04",)
        y.option_chain.return_value = _build_chain(calls, puts)
        mock_ticker.return_value = y
        flow = options_flow.detect_unusual_options_activity("TEST")
        d = flow.to_dict()
        assert d["symbol"] == "TEST"
        assert d["call_volume"] == 3000
        assert d["put_volume"] == 200
        assert d["call_put_volume_ratio"] == pytest.approx(15.0)
        assert d["bias"] == "bullish"
        assert "findings" in d
