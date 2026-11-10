"""Setup functions for research backtesting.

Each setup returns a boolean Series (True = signal at that day's close).
"""

import pandas as pd


def liquid(df: pd.DataFrame) -> pd.Series:
    """Common liquidity gate applied to all setups and control.
    
    Liquid = (close >= 10) & (adv_usd20 >= 20_000_000)
    """
    return (df["close"] >= 10) & (df["adv_usd20"] >= 20_000_000)


def statistical_mean_reversion(df: pd.DataFrame) -> pd.Series:
    """Statistical Mean Reversion setup.
    
    liquid & rsi14 < 32 & cci20 < -100 & atr_pct < 0.04 & rvol10 > 1.2
    """
    liq = liquid(df)
    return (
        liq
        & (df["rsi14"] < 32)
        & (df["cci20"] < -100)
        & (df["atr_pct"] < 0.04)
        & (df["rvol10"] > 1.2)
    )


def breakout_52week(df: pd.DataFrame) -> pd.Series:
    """52-Week Breakout setup (from daily bars).
    
    liquid & close > ema200 & ema20 > ema50 & ema50 > ema200 &
    macd > macd_signal & adx14 > 30 & rvol10 > 1.5
    """
    liq = liquid(df)
    return (
        liq
        & (df["close"] > df["ema200"])
        & (df["ema20"] > df["ema50"])
        & (df["ema50"] > df["ema200"])
        & (df["macd"] > df["macd_signal"])
        & (df["adx14"] > 30)
        & (df["rvol10"] > 1.5)
    )


def low_vol_setup(df: pd.DataFrame) -> pd.Series:
    """Low Vol Setup.
    
    liquid & close > ema50 & (bb_upper / bb_lower) < 1.05 &
    rsi14 > 45 & rsi14 < 60 & atr_pct < 0.03 & rvol10 < 0.8
    """
    liq = liquid(df)
    bb_ratio = df["bb_upper"] / df["bb_lower"]
    return (
        liq
        & (df["close"] > df["ema50"])
        & (bb_ratio < 1.05)
        & (df["rsi14"] > 45)
        & (df["rsi14"] < 60)
        & (df["atr_pct"] < 0.03)
        & (df["rvol10"] < 0.8)
    )


def volume_trend_accumulation(df: pd.DataFrame) -> pd.Series:
    """Volume Trend Accumulation setup.
    
    liquid & close > sma20 & close > ema50 & rvol10 > 1.3 &
    rsi14 > 55 & rsi14 < 70 & adx14 > 25
    """
    liq = liquid(df)
    return (
        liq
        & (df["close"] > df["sma20"])
        & (df["close"] > df["ema50"])
        & (df["rvol10"] > 1.3)
        & (df["rsi14"] > 55)
        & (df["rsi14"] < 70)
        & (df["adx14"] > 25)
    )


# Map of setup names to functions
SETUPS = {
    "statistical_mean_reversion": statistical_mean_reversion,
    "breakout_52week": breakout_52week,
    "low_vol_setup": low_vol_setup,
    "volume_trend_accumulation": volume_trend_accumulation,
}


def eligible(df: pd.DataFrame) -> pd.Series:
    """Return True where liquid AND all required indicators are not NaN.
    
    Used by the random control to find eligible symbols per day.
    """
    liq = liquid(df)
    # Check that all indicators used by any setup are not NaN
    required_cols = [
        "rsi14", "cci20", "atr_pct", "rvol10",
        "ema20", "ema50", "ema200", "macd", "macd_signal", "adx14",
        "bb_upper", "bb_lower", "sma20"
    ]
    not_nan = pd.Series(True, index=df.index)
    for col in required_cols:
        if col in df.columns:
            not_nan = not_nan & df[col].notna()
    return liq & not_nan