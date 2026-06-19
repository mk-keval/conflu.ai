"""Tests for screener filter registry and built-in filters."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.app.infrastructure.screener.filters import (
    _FILTER_REGISTRY,
    list_filters,
    list_filters_by_category,
)


class TestFilterRegistry:
    """Test the filter registry and decorator."""

    def test_list_filters_returns_all_categories(self) -> None:
        """list_filters() returns filters from all 5 categories."""
        registry = list_filters()
        categories = {fdef.category for fdef in registry.values()}
        assert categories == {"trend", "momentum", "volume", "volatility", "pattern"}

    def test_list_filters_by_category(self) -> None:
        """list_filters_by_category returns only matching category."""
        trend = list_filters_by_category("trend")
        for fdef in trend.values():
            assert fdef.category == "trend"

    def test_list_filters_returns_at_least_21_filters(self) -> None:
        """At least 21 built-in filters are registered."""
        assert len(list_filters()) >= 21

    def test_each_filter_has_required_attributes(self) -> None:
        """Every FilterDef has name, category, description, func, params."""
        for name, fdef in list_filters().items():
            assert fdef.name == name
            assert fdef.category in ("trend", "momentum", "volume", "volatility", "pattern")
            assert isinstance(fdef.description, str)
            assert callable(fdef.func)


class TestTrendFilters:
    """Test trend category filters."""

    @pytest.fixture
    def df(self) -> pd.DataFrame:
        """Synthetic data with trend indicator columns."""
        n = 100
        close = 100.0 + np.cumsum(np.random.default_rng(42).normal(0, 1.0, n))
        # Ensure ema_200 is safely below the lowest close point
        ema_200_value = min(close) - 5.0
        return pd.DataFrame({
            "symbol": ["TEST"] * n,
            "close": close,
            "ema_200": [ema_200_value] * n,
            "ema_50": [98.0] * n,
            "adx": np.linspace(15, 35, n),
        })

    def test_price_above_ema_true(self, df: pd.DataFrame) -> None:
        mask = _FILTER_REGISTRY["price_above_ema"].func(df, period=200)
        assert mask.dtype == bool
        assert mask.iloc[-1]  # Last bar price should be above flat EMA

    def test_price_below_ema_false_above(self, df: pd.DataFrame) -> None:
        mask = _FILTER_REGISTRY["price_below_ema"].func(df, period=200)
        assert mask.dtype == bool
        assert not mask.iloc[-1]

    def test_adx_trending(self, df: pd.DataFrame) -> None:
        mask = _FILTER_REGISTRY["adx_trending"].func(df, threshold=25.0)
        assert mask.dtype == bool
        assert mask.iloc[-1]  # ADX ends at 35 > 25

    def test_adx_non_trending(self, df: pd.DataFrame) -> None:
        mask = _FILTER_REGISTRY["adx_non_trending"].func(df, threshold=20.0)
        assert mask.dtype == bool
        assert mask.iloc[0]  # ADX starts at 15 < 20

    def test_ema_cross_bullish(self, df: pd.DataFrame) -> None:
        mask = _FILTER_REGISTRY["ema_cross"].func(df, fast=50, slow=200)
        assert mask.dtype == bool
        assert mask.iloc[-1]  # ema_50 > ema_200


class TestMomentumFilters:
    """Test momentum category filters."""

    @pytest.fixture
    def df(self) -> pd.DataFrame:
        """Synthetic data with momentum indicator columns."""
        return pd.DataFrame({
            "symbol": ["TEST"] * 100,
            "rsi": np.concatenate([np.linspace(20, 80, 50), np.linspace(80, 20, 50)]),
            "macd_line": np.concatenate([np.linspace(-1, 2, 50), np.linspace(2, -1, 50)]),
            "macd_signal": np.concatenate([np.linspace(0, 1, 50), np.linspace(1, 0, 50)]),
            "macd_hist": np.concatenate([np.linspace(-1, 1, 50), np.linspace(1, -1, 50)]),
        })

    def test_rsi_oversold(self, df: pd.DataFrame) -> None:
        mask = _FILTER_REGISTRY["rsi_oversold"].func(df, threshold=30.0)
        assert mask.dtype == bool
        assert mask.iloc[0]  # RSI starts at 20 < 30

    def test_rsi_overbought(self, df: pd.DataFrame) -> None:
        mask = _FILTER_REGISTRY["rsi_overbought"].func(df, threshold=70.0)
        assert mask.dtype == bool
        assert mask.iloc[49]  # RSI at 80 > 70

    def test_rsi_range(self, df: pd.DataFrame) -> None:
        mask = _FILTER_REGISTRY["rsi_range"].func(df, low=30.0, high=70.0)
        assert mask.dtype == bool
        # Some should be in range, some outside
        assert mask.any() and not mask.all()

    def test_macd_bullish(self, df: pd.DataFrame) -> None:
        mask = _FILTER_REGISTRY["macd_bullish"].func(df)
        assert mask.dtype == bool
        assert mask.iloc[25]  # macd_line > macd_signal in first half

    def test_macd_bearish(self, df: pd.DataFrame) -> None:
        mask = _FILTER_REGISTRY["macd_bearish"].func(df)
        assert mask.dtype == bool
        assert mask.iloc[75]  # macd_line < macd_signal in second half

    def test_macd_histogram_rising(self, df: pd.DataFrame) -> None:
        mask = _FILTER_REGISTRY["macd_histogram_rising"].func(df)
        assert mask.dtype == bool
        # First bar has no previous -> False
        assert not mask.iloc[0]


class TestVolumeFilters:
    """Test volume category filters."""

    @pytest.fixture
    def df(self) -> pd.DataFrame:
        """Synthetic data with volume columns."""
        n = 100
        rng = np.random.default_rng(42)
        return pd.DataFrame({
            "symbol": ["TEST"] * n,
            "volume": np.concatenate([
                rng.integers(1000, 2000, 80),
                np.linspace(2000, 50000, 20),  # ramp up to extreme at end
            ]),
            "obv": np.cumsum(rng.normal(0, 100, n)),
        })

    def test_rvol_high(self, df: pd.DataFrame) -> None:
        mask = _FILTER_REGISTRY["rvol_high"].func(df, threshold=1.5)
        assert mask.dtype == bool
        # Last 20 bars have much higher volume
        assert mask.iloc[-1]

    def test_rvol_low(self, df: pd.DataFrame) -> None:
        mask = _FILTER_REGISTRY["rvol_low"].func(df, threshold=0.5)
        assert mask.dtype == bool
        # First bars have normal volume, not low relative to 20-period avg

    def test_obv_slope_positive(self, df: pd.DataFrame) -> None:
        mask = _FILTER_REGISTRY["obv_slope_positive"].func(df, lookback=5)
        assert mask.dtype == bool


class TestVolatilityFilters:
    """Test volatility category filters."""

    @pytest.fixture
    def df(self) -> pd.DataFrame:
        """Synthetic data with volatility indicator columns."""
        n = 100
        close = 100.0 + np.cumsum(np.random.default_rng(42).normal(0, 1.0, n))
        # Use wide enough bands to contain the random walk
        margin = (close.max() - close.min()) * 0.5 + 5.0
        mid = (close.max() + close.min()) / 2
        return pd.DataFrame({
            "symbol": ["TEST"] * n,
            "close": close,
            "atr": np.concatenate([
                np.linspace(0.5, 1.0, 50),
                np.linspace(1.0, 3.0, 50),  # volatility increase
            ]),
            "bb_lower": [mid - margin] * n,
            "bb_upper": [mid + margin] * n,
        })

    def test_atr_percentile_high(self, df: pd.DataFrame) -> None:
        mask = _FILTER_REGISTRY["atr_percentile_high"].func(df, percentile=75.0)
        assert mask.dtype == bool

    def test_atr_percentile_low(self, df: pd.DataFrame) -> None:
        mask = _FILTER_REGISTRY["atr_percentile_low"].func(df, percentile=25.0)
        assert mask.dtype == bool

    def test_bb_inside(self, df: pd.DataFrame) -> None:
        mask = _FILTER_REGISTRY["bb_inside"].func(df)
        assert mask.dtype == bool
        assert mask.all()  # Price stays within bands

    def test_bb_touch(self, df: pd.DataFrame) -> None:
        """Test when price touches an outer band."""
        df_out = df.copy()
        df_out["close"] = df_out["bb_lower"] - 1.0  # Below lower band
        mask = _FILTER_REGISTRY["bb_touch"].func(df_out)
        assert mask.dtype == bool
        assert mask.all()


class TestPatternFilters:
    """Test pattern category filters (use raw OHLCV)."""

    @pytest.fixture
    def bullish_engulfing(self) -> pd.DataFrame:
        """Two bars: first red, second green that engulfs."""
        return pd.DataFrame({
            "open": [105.0, 99.5],
            "high": [106.0, 110.0],
            "low": [104.0, 99.0],
            "close": [100.0, 109.0],
        })

    def test_engulfing_bullish(self, bullish_engulfing: pd.DataFrame) -> None:
        mask = _FILTER_REGISTRY["candle_engulfing"].func(
            bullish_engulfing, direction="bullish",
        )
        assert mask.dtype == bool
        # Second bar engulfs: open < prev close AND close > prev open
        assert mask.iloc[1]

    def test_engulfing_bearish(self) -> None:
        """Two bars: first green, second red that engulfs."""
        df = pd.DataFrame({
            "open": [100.0, 110.0],
            "high": [104.0, 112.0],
            "low": [99.0, 105.0],
            "close": [104.0, 99.0],  # close < prev open (100)
        })
        mask = _FILTER_REGISTRY["candle_engulfing"].func(df, direction="bearish")
        assert mask.iloc[1]

    def test_hammer(self) -> None:
        """Hammer: long lower wick, small body."""
        df = pd.DataFrame({
            "open": [101.0],
            "high": [101.2],  # small upper wick (0.2)
            "low": [95.0],    # long lower wick (5.5)
            "close": [100.5],  # body = 0.5
        })
        mask = _FILTER_REGISTRY["candle_hammer"].func(df)
        assert mask.iloc[0]

    def test_doji(self) -> None:
        """Doji: open and close nearly equal."""
        df = pd.DataFrame({
            "open": [100.0],
            "high": [102.0],
            "low": [98.0],
            "close": [100.05],
        })
        mask = _FILTER_REGISTRY["candle_doji"].func(df)
        assert mask.iloc[0]

    def test_not_doji_wide_range(self) -> None:
        """Large body is not a doji."""
        df = pd.DataFrame({
            "open": [100.0],
            "high": [110.0],
            "low": [90.0],
            "close": [105.0],
        })
        mask = _FILTER_REGISTRY["candle_doji"].func(df)
        assert not mask.iloc[0]


class TestFilterComposition:
    """Test combining multiple filters."""

    def test_and_combination(self) -> None:
        """Two AND filters produce intersection."""
        df = pd.DataFrame({
            "symbol": ["A", "B", "C"],
            "rsi": [25, 50, 75],
            "volume": [1000, 2000, 3000],
        })
        oversold = df["rsi"] < 30
        low_vol = df["volume"] < 1500
        combined = oversold & low_vol
        assert combined.iloc[0]  # A (idx 0) passes both
        assert not combined.iloc[1]  # B (idx 1) passes neither
        assert not combined.iloc[2]  # C (idx 2) fails both

    def test_or_combination(self) -> None:
        """Two OR filters produce union."""
        df = pd.DataFrame({
            "symbol": ["A", "B", "C"],
            "rsi": [25, 50, 75],
        })
        oversold = df["rsi"] < 30
        overbought = df["rsi"] > 70
        combined = oversold | overbought
        assert combined.iloc[0]  # A (idx 0) is oversold
        assert not combined.iloc[1]  # B (idx 1) is neither
        assert combined.iloc[2]  # C (idx 2) is overbought
