"""Technical indicators for research backtesting.

All indicators use only past/current data (no look-ahead).
"""

import numpy as np
import pandas as pd


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all technical indicators to a DataFrame.
    
    Args:
        df: DataFrame with columns open, high, low, close, volume.
        
    Returns:
        DataFrame copy with added indicator columns.
    """
    out = df.copy()
    close = out["close"]
    high = out["high"]
    low = out["low"]
    volume = out["volume"]
    
    # EMAs
    out["ema20"] = close.ewm(span=20, adjust=False).mean()
    out["ema50"] = close.ewm(span=50, adjust=False).mean()
    out["ema200"] = close.ewm(span=200, adjust=False).mean()
    
    # SMA20
    out["sma20"] = close.rolling(20).mean()
    
    # RSI 14 (Wilder)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / avg_loss
    out["rsi14"] = 100 - 100 / (1 + rs)
    out.loc[avg_loss == 0, "rsi14"] = 100
    
    # True Range and ATR14
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    out["atr14"] = tr.ewm(alpha=1/14, adjust=False).mean()
    out["atr_pct"] = out["atr14"] / close
    
    # ADX 14 (Wilder)
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    plus_dm_series = pd.Series(plus_dm, index=close.index)
    minus_dm_series = pd.Series(minus_dm, index=close.index)
    
    atr14 = out["atr14"]
    plus_di = 100 * plus_dm_series.ewm(alpha=1/14, adjust=False).mean() / atr14
    minus_di = 100 * minus_dm_series.ewm(alpha=1/14, adjust=False).mean() / atr14
    
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    out["adx14"] = dx.ewm(alpha=1/14, adjust=False).mean()
    
    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["macd"] = ema12 - ema26
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()
    
    # CCI 20
    tp = (high + low + close) / 3
    tp_sma20 = tp.rolling(20).mean()
    mad = tp.rolling(20).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
    out["cci20"] = (tp - tp_sma20) / (0.015 * mad)
    
    # Bollinger Bands
    bb_std = close.rolling(20).std(ddof=0)
    out["bb_upper"] = out["sma20"] + 2 * bb_std
    out["bb_lower"] = out["sma20"] - 2 * bb_std
    
    # Volume indicators
    out["vol_sma10"] = volume.rolling(10).mean()
    out["rvol10"] = volume / out["vol_sma10"]
    out["adv_usd20"] = (close * volume).rolling(20).mean()
    
    return out