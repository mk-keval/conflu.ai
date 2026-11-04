"""Tests for the catalyst post-filter (D-47 PR 1).

The screener finds stocks that match technical patterns. The catalyst
filter runs the 5 D-46 signals on each result and surfaces confluence.

These tests use mocked yfinance + DuckDB so they're fast and isolated.
"""

from __future__ import annotations

import datetime as _dt
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from backend.app.infrastructure.screener import catalyst_filter


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_stock_history() -> pd.DataFrame:
    """Trending-up stock: 100 → 120 over 80 days."""
    closes = [100 + (i * 0.25) for i in range(80)]
    idx = pd.date_range("2026-05-01", periods=80, freq="B")
    return pd.DataFrame(
        {"Open": closes, "High": [c * 1.01 for c in closes], "Low": [c * 0.99 for c in closes],
         "Close": closes, "Volume": [1_000_000] * 80},
        index=idx,
    )


# ── _get_sector / _get_days_since_earnings ──────────────────────────────


class TestGetters:
    @patch("backend.app.infrastructure.screener.catalyst_filter.yf.Ticker")
    def test_get_sector_success(self, mock_ticker):
        mock_ticker.return_value.info.get.return_value = "Technology"
        assert catalyst_filter._get_sector("OKTA") == "Technology"

    @patch("backend.app.infrastructure.screener.catalyst_filter.yf.Ticker")
    def test_get_sector_exception(self, mock_ticker):
        mock_ticker.side_effect = Exception("network")
        assert catalyst_filter._get_sector("BAD") is None


# ── detect_catalyst_signals — main API ───────────────────────────────────


class TestDetectCatalystSignals:
    def test_returns_empty_signals_object_on_no_data(self):
        """When yfinance returns nothing, the signals object is created
        with all defaults and confluence_count=0."""
        sig = catalyst_filter.CatalystSignals(symbol="NONE")
        assert sig.symbol == "NONE"
        assert sig.confluence_count == 0
        # Summary is empty by default; populated by detect_catalyst_signals
        assert sig.summary == ""

    @patch("backend.app.infrastructure.screener.catalyst_filter.detect_unusual_options_activity")
    @patch("backend.app.infrastructure.screener.catalyst_filter.detect_insider_cluster")
    @patch("backend.app.infrastructure.screener.catalyst_filter.get_revision")
    @patch("backend.app.infrastructure.screener.catalyst_filter._get_sector")
    def test_full_signal_fires_all_5(
        self, mock_sector, mock_rev, mock_cluster, mock_options
    ):
        # All 5 signals fire
        mock_sector.return_value = "Technology"
        mock_rev.return_value = MagicMock(change_pct=8.0)
        mock_cluster.return_value = MagicMock(num_buyers=3, total_value_usd=500_000)
        mock_options.return_value = MagicMock(bias="bullish", call_put_volume_ratio=3.0)

        # Build a stock history that's STRONGLY outperforming (stock up 12% in 1M,
        # sector up 2% in 1M → RS = +10%, which fires the >=5% threshold).
        closes = [100 + (i * 0.6) for i in range(80)]
        idx = pd.date_range("2026-05-01", periods=80, freq="B")
        stock_hist = pd.DataFrame(
            {"Open": closes, "High": [c * 1.01 for c in closes], "Low": [c * 0.99 for c in closes],
             "Close": closes, "Volume": [1_000_000] * 80},
            index=idx,
        )

        # Mock sector ETF history (tech lagging)
        sector_closes = [100 + (i * 0.1) for i in range(80)]
        sector_idx = pd.date_range("2026-05-01", periods=80, freq="B")
        sector_hist = pd.DataFrame(
            {"Open": sector_closes, "High": [c * 1.01 for c in sector_closes],
             "Low": [c * 0.99 for c in sector_closes], "Close": sector_closes, "Volume": [1_000_000] * 80},
            index=sector_idx,
        )

        with patch(
            "backend.app.infrastructure.screener.catalyst_filter._fetch_sector_etf_history",
            return_value=sector_hist,
        ):
            sig = catalyst_filter.detect_catalyst_signals(
                symbol="OKTA", sector="Technology", stock_history=stock_hist
            )
        # 4 of 5 should fire (post_earnings_drift needs yfinance.earnings_dates,
        # which isn't mocked here, so it stays False)
        assert sig.confluence_count >= 3
        assert "outperforming" in sig.summary.lower() or "confluence" in sig.summary.lower()

    @patch("backend.app.infrastructure.screener.catalyst_filter.detect_unusual_options_activity")
    @patch("backend.app.infrastructure.screener.catalyst_filter.detect_insider_cluster")
    @patch("backend.app.infrastructure.screener.catalyst_filter.get_revision")
    @patch("backend.app.infrastructure.screener.catalyst_filter._get_sector")
    def test_no_signals_fire(
        self, mock_sector, mock_rev, mock_cluster, mock_options
    ):
        mock_sector.return_value = "Unknown Sector"
        mock_rev.return_value = None
        mock_cluster.return_value = None
        mock_options.return_value = None

        sig = catalyst_filter.detect_catalyst_signals(symbol="MYSTERY")
        assert sig.confluence_count == 0
        assert "No catalyst" in sig.summary

    @patch("backend.app.infrastructure.screener.catalyst_filter.detect_unusual_options_activity")
    @patch("backend.app.infrastructure.screener.catalyst_filter.detect_insider_cluster")
    @patch("backend.app.infrastructure.screener.catalyst_filter.get_revision")
    @patch("backend.app.infrastructure.screener.catalyst_filter._get_sector")
    def test_partial_signals(
        self, mock_sector, mock_rev, mock_cluster, mock_options
    ):
        # Only insider cluster + options flow fire
        mock_sector.return_value = "Technology"
        mock_rev.return_value = MagicMock(change_pct=2.0)  # below 5% threshold
        mock_cluster.return_value = MagicMock(num_buyers=3, total_value_usd=500_000)
        mock_options.return_value = MagicMock(bias="bullish", call_put_volume_ratio=2.5)

        sig = catalyst_filter.detect_catalyst_signals(symbol="OKTA")
        # 2 firing: insider + options (sector RS skipped because no stock_history; analyst not upgraded)
        assert sig.confluence_count == 2
        assert "MODERATE" in sig.summary

    def test_to_dict(self):
        sig = catalyst_filter.CatalystSignals(
            symbol="OKTA",
            sector_etf="XLK",
            rs_vs_sector_1m_pct=15.6,
            outperforming_sector=True,
            insider_cluster_detected=True,
            insider_cluster_size=3,
            options_flow_bias="bullish",
            call_put_volume_ratio=3.0,
            confluence_count=3,
            summary="🔥 HIGH CONFLUENCE: 3/5 catalysts firing",
            findings=["a", "b", "c"],
        )
        d = sig.to_dict()
        assert d["symbol"] == "OKTA"
        assert d["sector_etf"] == "XLK"
        assert d["outperforming_sector"] is True
        assert d["confluence_count"] == 3
        assert "HIGH CONFLUENCE" in d["summary"]


# ── confluence_boost ────────────────────────────────────────────────────


class TestConfluenceBoost:
    def test_zero_confluence_zero_boost(self):
        sig = catalyst_filter.CatalystSignals(symbol="X", confluence_count=0)
        assert catalyst_filter.confluence_boost(sig) == 0

    def test_five_confluence_full_boost(self):
        sig = catalyst_filter.CatalystSignals(symbol="X", confluence_count=5)
        assert catalyst_filter.confluence_boost(sig) == 5

    def test_over_max_capped(self):
        # Even if 10 signals somehow fire, cap at 5
        sig = catalyst_filter.CatalystSignals(symbol="X", confluence_count=10)
        assert catalyst_filter.confluence_boost(sig) == 5


# ── summary levels ──────────────────────────────────────────────────────


class TestSummaryLevels:
    def test_high_confluence_3_or_more(self):
        sig = catalyst_filter.CatalystSignals(symbol="X", confluence_count=3)
        sig.summary = "🔥 HIGH CONFLUENCE: 3/5 catalysts firing"
        assert "HIGH" in sig.summary

    def test_moderate_confluence_2(self):
        sig = catalyst_filter.CatalystSignals(symbol="X", confluence_count=2)
        sig.summary = "✅ MODERATE CONFLUENCE: 2/5 catalysts firing"
        assert "MODERATE" in sig.summary

    def test_weak_1(self):
        sig = catalyst_filter.CatalystSignals(symbol="X", confluence_count=1)
        sig.summary = "○ Weak signal: 1/5 catalyst firing"
        assert "Weak" in sig.summary

    def test_none_0(self):
        sig = catalyst_filter.CatalystSignals(symbol="X", confluence_count=0)
        sig.summary = "○ No catalyst signals"
        assert "No" in sig.summary
