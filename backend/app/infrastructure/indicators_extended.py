"""Extended indicator computations: ADX, OBV, BB, VWAP, Stochastics.

Registered via @indicator decorator into the same _INDICATOR_REGISTRY.
"""

from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from backend.app.infrastructure.indicators import indicator


@indicator(name="obv", timeframe="1D")
def compute_obv(df: pd.DataFrame) -> pd.DataFrame:
    """Compute On-Balance Volume.

    OBV = cumulative(volume * sign(close - previous_close))

    Args:
        df: DataFrame with 'close' and 'volume' columns.

    Returns:
        DataFrame with symbol, timestamp, indicator_name, value columns.
    """
    result = df[["symbol", "timestamp"]].copy()
    values = ta.obv(close=df["close"], volume=df["volume"])
    result["indicator_name"] = "obv"
    result["value"] = values
    return result


@indicator(name="bb", timeframe="1D")
def compute_bb(
    df: pd.DataFrame,
    length: int = 20,
    std: int = 2,
) -> pd.DataFrame:
    """Compute Bollinger Bands (upper, middle, lower).

    Returns three rows per timestamp: 'bb_lower', 'bb_middle', 'bb_upper'.

    Args:
        df: DataFrame with 'close' column.
        length: BB period (default 20).
        std: Standard deviations (default 2).

    Returns:
        DataFrame with symbol, timestamp, indicator_name, value columns.
    """
    bb_result = ta.bbands(close=df["close"], length=length, std=std)
    if bb_result is None or bb_result.empty:
        return pd.DataFrame(columns=["symbol", "timestamp", "indicator_name", "value"])

    base = df[["symbol", "timestamp"]]
    rows = []
    col_map = {
        f"BBL_{length}_{std}": "bb_lower",
        f"BBM_{length}_{std}": "bb_middle",
        f"BBU_{length}_{std}": "bb_upper",
    }
    for old_name, new_name in col_map.items():
        if old_name in bb_result.columns:
            part = base.copy()
            part["indicator_name"] = new_name
            part["value"] = bb_result[old_name].values
            rows.append(part)

    return pd.concat(rows, ignore_index=True)


@indicator(name="vwap", timeframe="1D")
def compute_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """Compute Volume-Weighted Average Price.

    VWAP = cumulative(price * volume) / cumulative(volume)
    Using typical price: (high + low + close) / 3

    Args:
        df: DataFrame with 'high', 'low', 'close', 'volume' columns.

    Returns:
        DataFrame with symbol, timestamp, indicator_name, value columns.
    """
    result = df[["symbol", "timestamp"]].copy()
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cum_pv = (typical_price * df["volume"]).cumsum()
    cum_vol = df["volume"].cumsum()
    values = cum_pv / cum_vol
    result["indicator_name"] = "vwap"
    result["value"] = values
    return result


@indicator(name="adx", timeframe="1D")
def compute_adx(
    df: pd.DataFrame,
    length: int = 14,
) -> pd.DataFrame:
    """Compute Average Directional Index.

    Args:
        df: DataFrame with 'high', 'low', 'close' columns.
        length: ADX period (default 14).

    Returns:
        DataFrame with symbol, timestamp, indicator_name, value columns.
    """
    adx_result = ta.adx(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        length=length,
    )
    if adx_result is None or adx_result.empty:
        return pd.DataFrame(columns=["symbol", "timestamp", "indicator_name", "value"])

    result = df[["symbol", "timestamp"]].copy()
    col = f"ADX_{length}"
    if col in adx_result.columns:
        result["indicator_name"] = "adx"
        result["value"] = adx_result[col].values
    else:
        result["indicator_name"] = "adx"
        result["value"] = float("nan")

    return result


@indicator(name="stoch", timeframe="1D")
def compute_stoch(
    df: pd.DataFrame,
    k: int = 14,
    d: int = 3,
    smooth: int = 3,
) -> pd.DataFrame:
    """Compute Stochastic Oscillator (%K and %D lines).

    Returns two rows per timestamp: 'stoch_k', 'stoch_d'.

    Args:
        df: DataFrame with 'high', 'low', 'close' columns.
        k: %K period (default 14).
        d: %D smoothing period (default 3).
        smooth: Smoothing factor (default 3).

    Returns:
        DataFrame with symbol, timestamp, indicator_name, value columns.
    """
    stoch_result = ta.stoch(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        k=k,
        d=d,
        smooth_k=smooth,
    )
    if stoch_result is None or stoch_result.empty:
        return pd.DataFrame(columns=["symbol", "timestamp", "indicator_name", "value"])

    base = df[["symbol", "timestamp"]]
    rows = []
    for col in stoch_result.columns:
        name = col.lower().replace("stoch", "stoch_")
        part = base.copy()
        part["indicator_name"] = name
        part["value"] = stoch_result[col].values
        rows.append(part)

    return pd.concat(rows, ignore_index=True)
