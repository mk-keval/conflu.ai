"""Tests for position sizing strategies."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.app.infrastructure.backtest.sizing import PositionSizer


@pytest.fixture
def price_df() -> pd.DataFrame:
    """Simple price DataFrame with 5 bars and 2 symbols."""
    return pd.DataFrame(
        {"AAPL": [150.0, 152.0, 149.0, 155.0, 153.0], "MSFT": [300.0, 305.0, 298.0, 310.0, 308.0]},
        index=pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC"),
    )


@pytest.fixture
def entries_df() -> pd.DataFrame:
    """Entry signals: enter on bar 1 and 3 only."""
    return pd.DataFrame(
        {"AAPL": [False, True, False, True, False], "MSFT": [False, True, False, True, False]},
        index=pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC"),
    )


@pytest.fixture
def zero_entries_df() -> pd.DataFrame:
    """No entry signals."""
    return pd.DataFrame(
        {s: [False] * 5 for s in ["AAPL", "MSFT"]},
        index=pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC"),
    )


@pytest.fixture
def atr_series() -> pd.Series:
    """ATR values aligned with price index."""
    return pd.Series(
        [2.0, 2.5, 2.0, 3.0, 2.5],
        index=pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC"),
    )


class TestFixedSize:
    def test_units_mode(self, price_df, entries_df):
        sizer = PositionSizer()
        size = sizer._fixed_size(price_df, entries_df, 100_000, {"mode": "units", "value": 100})
        assert size.shape == price_df.shape
        # On entry bars, size should be 100
        assert size.iloc[1, 0] == 100  # AAPL bar 1
        assert size.iloc[3, 0] == 100  # AAPL bar 3
        # On non-entry bars, size should be 0
        assert size.iloc[0, 0] == 0

    def test_cash_mode(self, price_df, entries_df):
        sizer = PositionSizer()
        size = sizer._fixed_size(price_df, entries_df, 100_000, {"mode": "cash", "value": 10000})
        assert size.shape == price_df.shape
        # On entry bar 1, AAPL: 10000 / 152.0 ≈ 65.79
        expected = 10000 / 152.0
        assert abs(size.iloc[1, 0] - expected) < 0.01
        # Non-entry: 0
        assert size.iloc[0, 0] == 0


class TestATRSize:
    def test_with_atr(self, price_df, entries_df, atr_series):
        sizer = PositionSizer()
        size = sizer._atr_size(
            price_df, entries_df, 100_000,
            {"risk_per_trade": 0.01, "atr_multiplier": 2.0, "max_position_pct": 1.0},
            atr_series,
        )
        assert size.shape == price_df.shape
        # risk = 0.01 * 100000 = 1000, atr on bar 1 = 2.5, mult = 2.0
        # raw_size = 1000 / (2.5 * 2.0) = 200
        expected = 1000 / (2.5 * 2.0)
        assert abs(size.iloc[1, 0] - expected) < 0.01
        # Non-entry: 0
        assert size.iloc[0, 0] == 0

    def test_without_atr_falls_back(self, price_df, entries_df):
        sizer = PositionSizer()
        size = sizer._atr_size(
            price_df, entries_df, 100_000,
            {"risk_per_trade": 0.01},
            None,
        )
        assert size.shape == price_df.shape
        # Falls back to cash mode with risk_per_trade * initial_cash
        expected_cash = 0.01 * 100_000  # 1000
        assert abs(size.iloc[1, 0] - expected_cash / 152.0) < 0.01


class TestKellySize:
    def test_kelly_formula(self, price_df, entries_df):
        sizer = PositionSizer()
        # win_rate=0.5, ratio=1.5 => q=0.5, f* = 0.5 - 0.5/1.5 = 0.5 - 0.333 = 0.167
        # half-kelly (0.5) => f = 0.0833
        size = sizer._kelly_size(
            price_df, entries_df, 100_000,
            {"kelly_fraction": 0.5, "win_rate": 0.5, "avg_win_avg_loss_ratio": 1.5},
        )
        assert size.shape == price_df.shape
        # Kelly position = f * equity / price = 0.08333 * 100000 / 152 = ~54.82
        f_star = (0.5 - 0.5 / 1.5) * 0.5
        expected = f_star * 100000 / 152.0
        assert abs(size.iloc[1, 0] - expected) < 0.5

    def test_kelly_clamp_to_zero(self, price_df, entries_df):
        sizer = PositionSizer()
        # Bad win rate: f* would be negative, should clamp to 0
        size = sizer._kelly_size(
            price_df, entries_df, 100_000,
            {"kelly_fraction": 1.0, "win_rate": 0.3, "avg_win_avg_loss_ratio": 1.0},
        )
        # f* = 0.3 - 0.7/1.0 = -0.4 -> clamped to 0
        assert size.iloc[1, 0] == 0.0


class TestComputePositionSize:
    def test_unknown_method_raises(self, price_df, entries_df):
        sizer = PositionSizer()
        with pytest.raises(ValueError, match="Unknown position sizing method"):
            sizer.compute_position_size(price_df, entries_df, "unknown", 100_000)

    def test_same_shape(self, price_df, entries_df):
        sizer = PositionSizer()
        size = sizer.compute_position_size(price_df, entries_df, "fixed", 100_000)
        assert size.shape == price_df.shape

    def test_zero_entries_zero_sizes(self, price_df, zero_entries_df):
        sizer = PositionSizer()
        size = sizer.compute_position_size(price_df, zero_entries_df, "fixed", 100_000)
        assert (size.values == 0).all()
