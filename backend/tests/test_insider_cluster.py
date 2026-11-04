"""Tests for the insider cluster detector (D-46 PR 4).

The elite trader watches for cluster insider buying — 3+ insiders
buying in the same week is the strongest insider signal. We test
the detector with synthetic DataFrames (mocking yfinance) so the
tests are fast and don't depend on live data.
"""

from __future__ import annotations

import datetime as _dt
from unittest.mock import patch

import pandas as pd
import pytest

from backend.app.infrastructure import insider_cluster


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_insider_df(rows: list[dict]) -> pd.DataFrame:
    """Build a yfinance-style insider_transactions DataFrame."""
    return pd.DataFrame(rows)


def _buy_row(insider: str, days_ago: int, value: float = 200_000, position: str = "Director") -> dict:
    return {
        "Insider": insider,
        "Position": position,
        "Start Date": _dt.date.today() - _dt.timedelta(days=days_ago),
        "Text": f"Purchase at price 100.00 per share.",
        "Value": value,
        "Shares": 2000,
    }


def _sell_row(insider: str, days_ago: int) -> dict:
    return {
        "Insider": insider,
        "Position": "Director",
        "Start Date": _dt.date.today() - _dt.timedelta(days=days_ago),
        "Text": f"Sale at price 100.00 per share.",
        "Value": 500_000,
        "Shares": 5000,
    }


# ── detect_insider_cluster ──────────────────────────────────────────────


class TestDetectInsiderCluster:
    @patch("backend.app.infrastructure.insider_cluster.yf.Ticker")
    def test_cluster_of_three_in_same_week(self, mock_ticker):
        rows = [
            _buy_row("CEO Alice", days_ago=2),
            _buy_row("CFO Bob", days_ago=3),
            _buy_row("Director Carol", days_ago=4),
        ]
        mock_ticker.return_value.insider_transactions = _make_insider_df(rows)
        cluster = insider_cluster.detect_insider_cluster("TEST")
        assert cluster is not None
        assert cluster.num_buyers == 3
        assert cluster.num_buy_transactions == 3
        assert cluster.total_value_usd == pytest.approx(600_000)
        assert "CEO Alice" in cluster.insiders
        assert "CFO Bob" in cluster.insiders
        assert "Director Carol" in cluster.insiders
        # Should produce a cluster finding
        assert any("Insider cluster" in f for f in cluster.findings)

    @patch("backend.app.infrastructure.insider_cluster.yf.Ticker")
    def test_only_two_buyers_no_cluster(self, mock_ticker):
        rows = [
            _buy_row("CEO Alice", days_ago=2),
            _buy_row("CFO Bob", days_ago=3),
        ]
        mock_ticker.return_value.insider_transactions = _make_insider_df(rows)
        cluster = insider_cluster.detect_insider_cluster("TEST")
        assert cluster is None  # 2 < MIN_INSIDERS_FOR_CLUSTER (3)

    @patch("backend.app.infrastructure.insider_cluster.yf.Ticker")
    def test_three_buyers_but_different_weeks(self, mock_ticker):
        rows = [
            _buy_row("CEO Alice", days_ago=2),
            _buy_row("CFO Bob", days_ago=3),
            _buy_row("Director Carol", days_ago=20),  # different week
        ]
        mock_ticker.return_value.insider_transactions = _make_insider_df(rows)
        cluster = insider_cluster.detect_insider_cluster("TEST")
        # Only 2 buyers in the most recent week → no cluster
        assert cluster is None

    @patch("backend.app.infrastructure.insider_cluster.yf.Ticker")
    def test_three_buyers_two_in_same_week_one_different(self, mock_ticker):
        # The cluster is based on the week with the most buyers
        rows = [
            _buy_row("CEO Alice", days_ago=2),
            _buy_row("CFO Bob", days_ago=3),
            _buy_row("Director Carol", days_ago=15),  # different week
            _buy_row("VP Dave", days_ago=16),  # same as Carol's week
        ]
        mock_ticker.return_value.insider_transactions = _make_insider_df(rows)
        cluster = insider_cluster.detect_insider_cluster("TEST")
        # Most recent week has 2 (Alice + Bob); older week has 2 (Carol + Dave)
        # Both have 2 buyers → no cluster
        assert cluster is None

    @patch("backend.app.infrastructure.insider_cluster.yf.Ticker")
    def test_small_purchases_filtered(self, mock_ticker):
        rows = [
            _buy_row("CEO Alice", days_ago=2, value=10_000),  # < $100k
            _buy_row("CFO Bob", days_ago=3, value=10_000),
            _buy_row("Director Carol", days_ago=4, value=10_000),
        ]
        mock_ticker.return_value.insider_transactions = _make_insider_df(rows)
        cluster = insider_cluster.detect_insider_cluster("TEST")
        # All 3 are too small — should be filtered out
        assert cluster is None

    @patch("backend.app.infrastructure.insider_cluster.yf.Ticker")
    def test_only_sells_no_cluster(self, mock_ticker):
        rows = [
            _sell_row("CEO Alice", days_ago=2),
            _sell_row("CFO Bob", days_ago=3),
            _sell_row("Director Carol", days_ago=4),
        ]
        mock_ticker.return_value.insider_transactions = _make_insider_df(rows)
        cluster = insider_cluster.detect_insider_cluster("TEST")
        assert cluster is None  # sells don't count

    @patch("backend.app.infrastructure.insider_cluster.yf.Ticker")
    def test_empty_dataframe(self, mock_ticker):
        mock_ticker.return_value.insider_transactions = pd.DataFrame()
        cluster = insider_cluster.detect_insider_cluster("TEST")
        assert cluster is None

    @patch("backend.app.infrastructure.insider_cluster.yf.Ticker")
    def test_none_dataframe(self, mock_ticker):
        mock_ticker.return_value.insider_transactions = None
        cluster = insider_cluster.detect_insider_cluster("TEST")
        assert cluster is None

    @patch("backend.app.infrastructure.insider_cluster.yf.Ticker")
    def test_old_transactions_outside_30d_window(self, mock_ticker):
        rows = [
            _buy_row("CEO Alice", days_ago=40),  # outside 30d window
            _buy_row("CFO Bob", days_ago=45),
            _buy_row("Director Carol", days_ago=50),
        ]
        mock_ticker.return_value.insider_transactions = _make_insider_df(rows)
        cluster = insider_cluster.detect_insider_cluster("TEST")
        assert cluster is None  # All outside 30d window

    @patch("backend.app.infrastructure.insider_cluster.yf.Ticker")
    def test_same_insider_multiple_buys_counts_once(self, mock_ticker):
        rows = [
            _buy_row("CEO Alice", days_ago=2),
            _buy_row("CEO Alice", days_ago=4),  # same person, different day
            _buy_row("CFO Bob", days_ago=3),
        ]
        mock_ticker.return_value.insider_transactions = _make_insider_df(rows)
        cluster = insider_cluster.detect_insider_cluster("TEST")
        # Only 2 unique insiders (Alice + Bob), Alice bought twice
        assert cluster is None  # 2 < 3 unique

    @patch("backend.app.infrastructure.insider_cluster.yf.Ticker")
    def test_finding_includes_insider_names(self, mock_ticker):
        rows = [
            _buy_row("CEO Alice", days_ago=2),
            _buy_row("CFO Bob", days_ago=3),
            _buy_row("Director Carol", days_ago=4),
        ]
        mock_ticker.return_value.insider_transactions = _make_insider_df(rows)
        cluster = insider_cluster.detect_insider_cluster("TEST")
        assert any("CEO Alice" in f for f in cluster.findings)
        assert any("CFO Bob" in f for f in cluster.findings)

    @patch("backend.app.infrastructure.insider_cluster.yf.Ticker")
    def test_finding_truncates_many_buyers(self, mock_ticker):
        # 5 insiders = 4 + "more" truncation
        rows = [
            _buy_row(f"Inside{i}", days_ago=i) for i in range(2, 7)
        ]
        mock_ticker.return_value.insider_transactions = _make_insider_df(rows)
        cluster = insider_cluster.detect_insider_cluster("TEST")
        assert any("+2 more" in f for f in cluster.findings)

    @patch("backend.app.infrastructure.insider_cluster.yf.Ticker")
    def test_to_dict(self, mock_ticker):
        rows = [
            _buy_row("CEO Alice", days_ago=2),
            _buy_row("CFO Bob", days_ago=3),
            _buy_row("Director Carol", days_ago=4),
        ]
        mock_ticker.return_value.insider_transactions = _make_insider_df(rows)
        cluster = insider_cluster.detect_insider_cluster("TEST")
        d = cluster.to_dict()
        assert d["symbol"] == "TEST"
        assert d["num_buyers"] == 3
        assert d["total_value_usd"] == pytest.approx(600_000)
        assert "findings" in d

    @patch("backend.app.infrastructure.insider_cluster.yf.Ticker")
    def test_exception_during_fetch_returns_none(self, mock_ticker):
        mock_ticker.side_effect = Exception("network error")
        cluster = insider_cluster.detect_insider_cluster("TEST")
        assert cluster is None
