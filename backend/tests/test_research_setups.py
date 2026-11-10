"""Tests for research setups."""

import numpy as np
import pandas as pd
import pytest

from backend.app.research.setups import (
    statistical_mean_reversion,
    breakout_52week,
    low_vol_setup,
    volume_trend_accumulation,
    eligible,
    liquid,
)


def _make_df(close, high=None, low=None, open_=None, volume=None):
    """Helper to create a DataFrame with indicators."""
    from backend.app.research.indicators import add_indicators
    
    n = len(close)
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    
    if high is None:
        high = close + 1
    if low is None:
        low = close - 1
    if open_ is None:
        open_ = close
    if volume is None:
        volume = np.full(n, 10000000)
    
    df = pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume
    }, index=dates)
    
    return add_indicators(df)


def test_statistical_mean_reversion_trigger():
    """Build a frame that should trigger statistical_mean_reversion."""
    # Need: rsi14 < 32, cci20 < -100, atr_pct < 0.04, rvol10 > 1.2, liquid
    # Create oversold condition with declining prices and volume spike at end
    n = 100
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    
    # Steady decline for RSI < 32
    close = 100 - np.arange(n) * 0.5
    # Add some volatility for CCI
    high = close + 0.5
    low = close - 0.5
    # Low volume initially, then spike for rvol10 > 1.2
    volume = np.full(n, 5000000)
    volume[-10:] = 50000000  # Volume spike at end
    
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": volume}, index=dates)
    from backend.app.research.indicators import add_indicators
    df = add_indicators(df)
    
    signals = statistical_mean_reversion(df)
    # Should have some signals after warmup
    assert signals.iloc[50:].any()


def test_statistical_mean_reversion_no_trigger():
    """Build a frame that should NOT trigger statistical_mean_reversion."""
    # Rising prices - RSI should be high
    close = 100 + np.arange(100) * 0.5
    high = close + 0.5
    low = close - 0.5
    volume = np.full(100, 50000000)
    
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": volume},
                      index=pd.date_range("2020-01-01", periods=100, freq="D"))
    from backend.app.research.indicators import add_indicators
    df = add_indicators(df)
    
    signals = statistical_mean_reversion(df)
    # Should not trigger on rising prices
    assert not signals.iloc[50:].any()


def test_breakout_52week_trigger():
    """Build a frame that should trigger breakout_52week."""
    n = 300
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    
    # Strong uptrend: close > ema200, ema20 > ema50 > ema200, macd > signal, adx > 30
    close = 100 + np.cumsum(np.random.randn(n) * 0.2 + 0.15)
    high = close + np.abs(np.random.randn(n) * 0.3)
    low = close - np.abs(np.random.randn(n) * 0.3)
    volume = np.abs(np.random.randn(n) * 2000000 + 5000000)
    
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": volume}, index=dates)
    from backend.app.research.indicators import add_indicators
    df = add_indicators(df)
    
    signals = breakout_52week(df)
    # Should have some signals in strong uptrend
    assert signals.iloc[100:].any()


def test_breakout_52week_no_trigger():
    """Build a frame that should NOT trigger breakout_52week."""
    # Downtrend
    close = 100 - np.arange(200) * 0.3
    high = close + 0.5
    low = close - 0.5
    volume = np.full(200, 5000000)
    
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": volume},
                      index=pd.date_range("2020-01-01", periods=200, freq="D"))
    from backend.app.research.indicators import add_indicators
    df = add_indicators(df)
    
    signals = breakout_52week(df)
    assert not signals.any()


def test_low_vol_setup_trigger():
    """Build a frame that should trigger low_vol_setup."""
    n = 100
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    
    # Low volatility, flat price with slight upward bias, low rvol
    # Need RSI between 45-60
    close = 100 + np.sin(np.arange(n) * 0.5) * 0.5 + np.arange(n) * 0.01
    high = close + 0.1
    low = close - 0.1
    # High volume for first 45 days, then very low for rvol10 < 0.8
    volume = np.full(n, 500000)
    volume[:45] = 50000000
    
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": volume}, index=dates)
    from backend.app.research.indicators import add_indicators
    df = add_indicators(df)
    
    signals = low_vol_setup(df)
    assert signals.iloc[50:].any()


def test_low_vol_setup_no_trigger():
    """Build a frame that should NOT trigger low_vol_setup."""
    # High volatility
    close = 100 + np.cumsum(np.random.randn(100) * 3)
    high = close + np.abs(np.random.randn(100) * 2)
    low = close - np.abs(np.random.randn(100) * 2)
    volume = np.full(100, 50000000)
    
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": volume},
                      index=pd.date_range("2020-01-01", periods=100, freq="D"))
    from backend.app.research.indicators import add_indicators
    df = add_indicators(df)
    
    signals = low_vol_setup(df)
    assert not signals.iloc[50:].any()


def test_volume_trend_accumulation_trigger():
    """Build a frame that should trigger volume_trend_accumulation."""
    n = 100
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    
    # Strong uptrend with regular pullbacks, then volume spike
    close = np.full(n, 100.0)
    for i in range(1, n):
        close[i] = close[i-1] + 0.4
        if i % 4 == 0:
            close[i] -= 1.0
    high = close + 0.5
    low = close - 0.5
    volume = np.full(n, 50000000)
    volume[60:63] = 200000000  # Sudden volume spike
    
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": volume}, index=dates)
    from backend.app.research.indicators import add_indicators
    df = add_indicators(df)
    
    signals = volume_trend_accumulation(df)
    assert signals.iloc[60:63].any()


def test_volume_trend_accumulation_no_trigger():
    """Build a frame that should NOT trigger volume_trend_accumulation."""
    # Downtrend
    close = 100 - np.arange(100) * 0.3
    high = close + 0.5
    low = close - 0.5
    volume = np.full(100, 5000000)
    
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": volume},
                      index=pd.date_range("2020-01-01", periods=100, freq="D"))
    from backend.app.research.indicators import add_indicators
    df = add_indicators(df)
    
    signals = volume_trend_accumulation(df)
    assert not signals.iloc[50:].any()


def test_no_signal_on_nan_indicators():
    """No setup should return True where any required indicator is NaN."""
    # Very short frame - indicators will be NaN
    close = np.array([100.0, 101.0, 102.0])
    high = close + 0.5
    low = close - 0.5
    volume = np.full(3, 50000000)
    
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": volume},
                      index=pd.date_range("2020-01-01", periods=3, freq="D"))
    from backend.app.research.indicators import add_indicators
    df = add_indicators(df)
    
    for name, setup_fn in {
        "statistical_mean_reversion": statistical_mean_reversion,
        "breakout_52week": breakout_52week,
        "low_vol_setup": low_vol_setup,
        "volume_trend_accumulation": volume_trend_accumulation,
    }.items():
        signals = setup_fn(df)
        # All should be False (or NaN which evaluates to False in bool context)
        assert not signals.any(), f"{name} returned True on NaN indicators"


def test_eligible():
    """Test eligible function."""
    n = 100
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    close = 100 + np.arange(n) * 0.1
    high = close + 0.5
    low = close - 0.5
    # Low price early on to fail liquid gate (close < 10) - for longer than indicator warmup
    close[:50] = 5.0  # Keep price low for 50 days
    volume = np.full(n, 50000000)
    
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": volume}, index=dates)
    from backend.app.research.indicators import add_indicators
    df = add_indicators(df)
    
    elig = eligible(df)
    # Should be True after warmup period
    assert elig.iloc[60:].all()
    # Should be False early on (liquid fails + NaN indicators)
    assert not elig.iloc[:50].any()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])