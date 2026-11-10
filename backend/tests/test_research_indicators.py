"""Tests for research indicators."""

import numpy as np
import pandas as pd
import pytest

from backend.app.research.indicators import add_indicators


def test_rsi14_rising_close():
    """Strictly rising close -> rsi14 should be 100 after warmup."""
    dates = pd.date_range("2020-01-01", periods=100, freq="D")
    close = np.arange(100, 200, dtype=float)
    df = pd.DataFrame({
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": 1000000
    }, index=dates)
    
    result = add_indicators(df)
    # After warmup (14 bars), RSI should be 100 for strictly rising
    assert np.isclose(result["rsi14"].iloc[-1], 100, atol=1e-6)


def test_atr14_constant_range():
    """Constant high-low range of 2, flat close -> atr14 converges to 2."""
    dates = pd.date_range("2020-01-01", periods=100, freq="D")
    close = np.full(100, 100.0)
    df = pd.DataFrame({
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": 1000000
    }, index=dates)
    
    result = add_indicators(df)
    # After warmup, ATR should converge to 2 (high-low = 2)
    assert np.isclose(result["atr14"].iloc[-1], 2.0, atol=1e-6)


def test_no_lookahead():
    """Indicator values at row 299 must be identical whether computed on full or truncated frame."""
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=400, freq="D")
    
    # Generate random walk OHLCV
    close = 100 + np.cumsum(np.random.randn(400) * 0.5)
    high = close + np.abs(np.random.randn(400) * 0.3)
    low = close - np.abs(np.random.randn(400) * 0.3)
    open_ = close + np.random.randn(400) * 0.2
    volume = np.abs(np.random.randn(400) * 100000 + 1000000)
    
    df = pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume
    }, index=dates)
    
    # Compute on full frame
    full = add_indicators(df)
    
    # Compute on truncated frame
    truncated = add_indicators(df.iloc[:300])
    
    # Compare row 299 (index 299)
    indicator_cols = [
        "ema20", "ema50", "ema200", "sma20", "rsi14", "atr14", "atr_pct",
        "adx14", "macd", "macd_signal", "cci20", "bb_upper", "bb_lower",
        "vol_sma10", "rvol10", "adv_usd20"
    ]
    
    for col in indicator_cols:
        v1 = full[col].iloc[299]
        v2 = truncated[col].iloc[299]
        assert np.isclose(v1, v2, rtol=1e-10, equal_nan=True), f"Lookahead detected in {col}: {v1} != {v2}"


def test_adx14_bounds():
    """ADX14 always within [0, 100] where not NaN."""
    dates = pd.date_range("2020-01-01", periods=100, freq="D")
    close = 100 + np.cumsum(np.random.randn(100) * 0.5)
    high = close + np.abs(np.random.randn(100) * 0.3)
    low = close - np.abs(np.random.randn(100) * 0.3)
    open_ = close + np.random.randn(100) * 0.2
    volume = np.abs(np.random.randn(100) * 100000 + 1000000)
    
    df = pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume
    }, index=dates)
    
    result = add_indicators(df)
    adx = result["adx14"].dropna()
    assert (adx >= 0).all() and (adx <= 100).all()


def test_pandas_ta_crosscheck():
    """Cross-check RSI and ATR against pandas_ta if available."""
    pytest.importorskip("pandas_ta")
    
    dates = pd.date_range("2020-01-01", periods=200, freq="D")
    close = 100 + np.cumsum(np.random.randn(200) * 0.5)
    high = close + np.abs(np.random.randn(200) * 0.3)
    low = close - np.abs(np.random.randn(200) * 0.3)
    open_ = close + np.random.randn(200) * 0.2
    volume = np.abs(np.random.randn(200) * 100000 + 1000000)
    
    df = pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume
    }, index=dates)
    
    result = add_indicators(df)
    
    import pandas_ta as ta
    df_ta = df.copy()
    df_ta.ta.rsi(length=14, append=True)
    df_ta.ta.atr(length=14, append=True)
    
    # Compare after warmup (100 rows)
    rsi_ours = result["rsi14"].iloc[100:]
    rsi_ta = df_ta["RSI_14"].iloc[100:]
    atr_ours = result["atr14"].iloc[100:]
    atr_ta = df_ta["ATRr_14"].iloc[100:]
    
    # Relative tolerance 1e-3
    assert np.allclose(rsi_ours, rsi_ta, rtol=1e-3, equal_nan=True)
    assert np.allclose(atr_ours, atr_ta, rtol=1e-3, equal_nan=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])