"""Tests for the lightweight macro context module (D-46 PR 1).

The macro context is what an elite trader holds in their head when sizing
any trade: VIX, SPY/QQQ close, leading/lagging sectors, risk regime.
These tests verify the lightweight fetcher works, classifies VIX correctly,
identifies leaders/laggers, and respects the TTL cache.
"""

from __future__ import annotations

import time
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from backend.app.infrastructure.professional import macro_context


# ── Fixtures ──────────────────────────────────────────────────────────────


def _mock_history(closes: list[float]) -> pd.DataFrame:
    """Build a minimal yfinance history DataFrame with the given closes."""
    idx = pd.date_range("2026-08-25", periods=len(closes), freq="D")
    return pd.DataFrame(
        {"Close": closes, "Open": closes, "High": closes, "Low": closes, "Volume": [0] * len(closes)},
        index=idx,
    )


@pytest.fixture(autouse=True)
def _reset_cache():
    """Ensure each test starts with a clean cache."""
    macro_context.clear_cache()
    yield
    macro_context.clear_cache()


# ── VIX classification ───────────────────────────────────────────────────


class TestVixClassification:
    def test_calm_under_15(self):
        assert macro_context._classify_vix(13.5) == "calm"

    def test_normal_15_to_20(self):
        assert macro_context._classify_vix(17.0) == "normal"

    def test_elevated_20_to_30(self):
        assert macro_context._classify_vix(24.5) == "elevated"

    def test_fear_30_plus(self):
        assert macro_context._classify_vix(35.0) == "fear"

    def test_none_returns_unknown(self):
        assert macro_context._classify_vix(None) == "unknown"

    def test_boundary_15_is_normal(self):
        # 15.0 is at the boundary — falls into "normal" (15 <= vix < 20)
        assert macro_context._classify_vix(15.0) == "normal"

    def test_boundary_20_is_elevated(self):
        # 20.0 is at the boundary — falls into "elevated" (20 <= vix < 30)
        assert macro_context._classify_vix(20.0) == "elevated"


# ── Single fetcher helpers ──────────────────────────────────────────────


class TestFetchOne:
    @patch("backend.app.infrastructure.professional.macro_context.yf.Ticker")
    def test_returns_last_close(self, mock_ticker):
        mock_ticker.return_value.history.return_value = _mock_history([100, 101, 102])
        assert macro_context._fetch_one("SPY") == 102

    @patch("backend.app.infrastructure.professional.macro_context.yf.Ticker")
    def test_returns_none_on_empty(self, mock_ticker):
        mock_ticker.return_value.history.return_value = pd.DataFrame()
        assert macro_context._fetch_one("FAKE") is None

    @patch("backend.app.infrastructure.professional.macro_context.yf.Ticker")
    def test_returns_none_on_exception(self, mock_ticker):
        mock_ticker.return_value.history.side_effect = Exception("network")
        assert macro_context._fetch_one("SPY") is None


class TestPctChange:
    @patch("backend.app.infrastructure.professional.macro_context.yf.Ticker")
    def test_positive_change(self, mock_ticker):
        mock_ticker.return_value.history.return_value = _mock_history([100, 102])
        assert macro_context._pct_change("SPY") == pytest.approx(2.0)

    @patch("backend.app.infrastructure.professional.macro_context.yf.Ticker")
    def test_negative_change(self, mock_ticker):
        mock_ticker.return_value.history.return_value = _mock_history([100, 98])
        assert macro_context._pct_change("SPY") == pytest.approx(-2.0)

    @patch("backend.app.infrastructure.professional.macro_context.yf.Ticker")
    def test_returns_none_on_insufficient_data(self, mock_ticker):
        mock_ticker.return_value.history.return_value = _mock_history([100])
        assert macro_context._pct_change("SPY") is None

    @patch("backend.app.infrastructure.professional.macro_context.yf.Ticker")
    def test_zero_prev_returns_none(self, mock_ticker):
        mock_ticker.return_value.history.return_value = _mock_history([0, 100])
        assert macro_context._pct_change("SPY") is None


# ── get_macro_context (the public API) ───────────────────────────────────


class TestGetMacroContext:
    @patch("backend.app.infrastructure.professional.macro_context._fetch_one")
    @patch("backend.app.infrastructure.professional.macro_context._pct_change")
    def test_basic_construction(self, mock_pct, mock_fetch):
        # VIX=14.5 → calm regime
        # SPY=767, QQQ=716, DXY=104
        # Sectors: XLE +3, XLF +1, XLK -1
        mock_fetch.side_effect = lambda sym: {
            "^VIX": 14.5, "SPY": 767.0, "QQQ": 716.0, "DX-Y.NYB": 104.0
        }.get(sym)
        mock_pct.side_effect = lambda sym: {
            "SPY": 0.5, "QQQ": -0.3,
            "XLE": 3.0, "XLF": 1.0, "XLY": -1.0, "XLP": 0.5, "XLI": -0.5,
            "XLV": 1.5, "XLB": 0.0, "XLK": -2.0, "XLU": -0.5,
            "XBI": 2.0, "XHB": -0.2, "XRT": -0.3,
        }.get(sym)

        ctx = macro_context.get_macro_context()
        assert ctx.vix == 14.5
        assert ctx.risk_regime == "calm"
        assert ctx.leading_sector == "XLE"
        assert ctx.leading_sector_1d_pct == pytest.approx(3.0)
        assert ctx.lagging_sector == "XLK"
        assert ctx.lagging_sector_1d_pct == pytest.approx(-2.0)

    @patch("backend.app.infrastructure.professional.macro_context._fetch_one")
    @patch("backend.app.infrastructure.professional.macro_context._pct_change")
    def test_fear_regime(self, mock_pct, mock_fetch):
        mock_fetch.side_effect = lambda sym: {"^VIX": 32.0, "SPY": 700.0, "QQQ": 650.0, "DX-Y.NYB": 108.0}.get(sym)
        mock_pct.side_effect = lambda sym: None
        ctx = macro_context.get_macro_context()
        assert ctx.risk_regime == "fear"

    @patch("backend.app.infrastructure.professional.macro_context._fetch_one")
    @patch("backend.app.infrastructure.professional.macro_context._pct_change")
    def test_tolerates_partial_failure(self, mock_pct, mock_fetch):
        # VIX works, SPY/QQQ fail
        mock_fetch.side_effect = lambda sym: {"^VIX": 16.0}.get(sym)
        mock_pct.side_effect = lambda sym: None
        ctx = macro_context.get_macro_context()
        assert ctx.vix == 16.0
        assert ctx.spy_close is None
        assert ctx.risk_regime == "normal"
        # No sector data → no leader/lagger
        assert ctx.leading_sector is None

    @patch("backend.app.infrastructure.professional.macro_context._fetch_one")
    @patch("backend.app.infrastructure.professional.macro_context._pct_change")
    def test_to_dict_round_trip(self, mock_pct, mock_fetch):
        mock_fetch.side_effect = lambda sym: {"^VIX": 14.0, "SPY": 770.0, "QQQ": 720.0, "DX-Y.NYB": 103.0}.get(sym)
        mock_pct.side_effect = lambda sym: {"SPY": 0.1, "QQQ": 0.2, "XLE": 1.0}.get(sym)
        ctx = macro_context.get_macro_context()
        d = ctx.to_dict()
        assert isinstance(d, dict)
        assert d["vix"] == 14.0
        assert d["risk_regime"] == "calm"
        assert "timestamp" in d


# ── TTL cache ────────────────────────────────────────────────────────────


class TestTtlCache:
    @patch("backend.app.infrastructure.professional.macro_context._fetch_one")
    @patch("backend.app.infrastructure.professional.macro_context._pct_change")
    def test_cache_hit_within_ttl(self, mock_pct, mock_fetch):
        # First call populates the cache
        mock_fetch.side_effect = lambda sym: {"^VIX": 14.0, "SPY": 770.0, "QQQ": 720.0, "DX-Y.NYB": 103.0}.get(sym)
        mock_pct.side_effect = lambda sym: {"SPY": 0.1}.get(sym)
        ctx1 = macro_context.get_macro_context()
        assert macro_context._cached is not None

        # Second call within TTL — should NOT re-fetch (VIX would be different)
        mock_fetch.side_effect = lambda sym: {"^VIX": 50.0, "SPY": 999.0, "QQQ": 999.0, "DX-Y.NYB": 999.0}.get(sym)
        mock_pct.side_effect = lambda sym: {"SPY": 99.9}.get(sym)
        ctx2 = macro_context.get_macro_context()
        # Should be the same cached object — VIX still 14.0
        assert ctx2.vix == 14.0
        assert ctx2 is ctx1  # Same object (cached)

    @patch("backend.app.infrastructure.professional.macro_context._fetch_one")
    @patch("backend.app.infrastructure.professional.macro_context._pct_change")
    def test_force_refresh_bypasses_cache(self, mock_pct, mock_fetch):
        mock_fetch.side_effect = lambda sym: {"^VIX": 14.0, "SPY": 770.0, "QQQ": 720.0, "DX-Y.NYB": 103.0}.get(sym)
        mock_pct.side_effect = lambda sym: {"SPY": 0.1}.get(sym)
        macro_context.get_macro_context()
        # Force refresh with different data
        mock_fetch.side_effect = lambda sym: {"^VIX": 50.0, "SPY": 999.0, "QQQ": 999.0, "DX-Y.NYB": 999.0}.get(sym)
        mock_pct.side_effect = lambda sym: {"SPY": 99.9}.get(sym)
        ctx = macro_context.get_macro_context(force_refresh=True)
        assert ctx.vix == 50.0

    @patch("backend.app.infrastructure.professional.macro_context._fetch_one")
    @patch("backend.app.infrastructure.professional.macro_context._pct_change")
    def test_cache_expires_after_ttl(self, mock_pct, mock_fetch):
        mock_fetch.side_effect = lambda sym: {"^VIX": 14.0, "SPY": 770.0, "QQQ": 720.0, "DX-Y.NYB": 103.0}.get(sym)
        mock_pct.side_effect = lambda sym: {"SPY": 0.1}.get(sym)
        macro_context.get_macro_context()
        # Manually expire the cache by setting the timestamp backward
        macro_context._cached_at = time.monotonic() - macro_context._CACHE_TTL - 1
        # Now refresh mocks and call again
        mock_fetch.side_effect = lambda sym: {"^VIX": 50.0, "SPY": 999.0, "QQQ": 999.0, "DX-Y.NYB": 999.0}.get(sym)
        mock_pct.side_effect = lambda sym: {"SPY": 99.9}.get(sym)
        ctx = macro_context.get_macro_context()
        assert ctx.vix == 50.0  # Re-fetched because cache expired
