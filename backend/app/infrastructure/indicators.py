"""Vectorized compute primitives: indicator registry, pandas-ta wrappers, vectorbt integration.

ZERO explicit loops over DataFrame rows — all operations are vectorized.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

import pandas as pd
import pandas_ta as ta

_INDICATOR_REGISTRY: dict[str, Callable[..., pd.DataFrame]] = {}


def indicator(name: str, timeframe: str = "1D") -> Callable[[Callable[..., pd.DataFrame]], Callable[..., pd.DataFrame]]:
    """Register an indicator computation function.

    Registered functions are tracked in ``_INDICATOR_REGISTRY`` for discovery
    and caching. The wrapped function must return a DataFrame with columns:
    ``symbol``, ``timestamp``, ``indicator_name``, ``value``.

    Args:
        name: Canonical indicator name (e.g., 'rsi', 'macd').
        timeframe: Default computation timeframe (e.g., '1D', '1h').

    Returns:
        A decorator that registers the function and wraps it for validation.

    Example:
        @indicator(name="rsi", timeframe="1D")
        def compute_rsi(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
            ...
    """

    def decorator(func: Callable[..., pd.DataFrame]) -> Callable[..., pd.DataFrame]:
        _INDICATOR_REGISTRY[name] = func

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> pd.DataFrame:
            result = func(*args, **kwargs)
            required_cols = {"symbol", "timestamp", "indicator_name", "value"}
            if not required_cols.issubset(result.columns):
                msg = (
                    f"Indicator '{name}' output missing required columns. "
                    f"Expected {required_cols}, got {set(result.columns)}"
                )
                raise ValueError(msg)
            return result

        return wrapper

    return decorator


@indicator(name="rsi", timeframe="1D")
def compute_rsi(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """Compute Relative Strength Index.

    Args:
        df: DataFrame with 'close' column, plus 'symbol' and 'timestamp'.
        length: RSI lookback period (default 14).

    Returns:
        DataFrame with columns: symbol, timestamp, indicator_name, value.
    """
    result = df[["symbol", "timestamp"]].copy()
    values = ta.rsi(close=df["close"], length=length)
    result["indicator_name"] = "rsi"
    result["value"] = values
    return result


@indicator(name="macd", timeframe="1D")
def compute_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Compute MACD oscillator (MACD line, signal line, histogram).

    Returns three rows per timestamp: one for 'macd_line', 'macd_signal', 'macd_hist'.

    Args:
        df: DataFrame with 'close' column.
        fast: Fast EMA period (default 12).
        slow: Slow EMA period (default 26).
        signal: Signal line period (default 9).

    Returns:
        DataFrame with symbol, timestamp, indicator_name, value columns.
    """
    macd_result = ta.macd(close=df["close"], fast=fast, slow=slow, signal=signal)
    if macd_result is None or macd_result.empty:
        return pd.DataFrame(columns=["symbol", "timestamp", "indicator_name", "value"])

    # pandas_ta returns columns like MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9
    # Map to standard names: macd_line, macd_signal, macd_hist
    col_mapping = {
        f"MACD_{fast}_{slow}_{signal}": "macd_line",
        f"MACDs_{fast}_{slow}_{signal}": "macd_signal",
        f"MACDh_{fast}_{slow}_{signal}": "macd_hist",
    }

    rows = []
    base = df[["symbol", "timestamp"]]
    for src_col, dst_name in col_mapping.items():
        if src_col in macd_result.columns:
            part = base.copy()
            part["indicator_name"] = dst_name
            part["value"] = macd_result[src_col].values
            rows.append(part)

    return (
        pd.concat(rows, ignore_index=True)
        if rows
        else pd.DataFrame(columns=["symbol", "timestamp", "indicator_name", "value"])
    )


@indicator(name="ema", timeframe="1D")
def compute_ema(df: pd.DataFrame, length: int = 20) -> pd.DataFrame:
    """Compute Exponential Moving Average.

    Args:
        df: DataFrame with 'close' column.
        length: EMA period (default 20).

    Returns:
        DataFrame with symbol, timestamp, indicator_name, value columns.
    """
    result = df[["symbol", "timestamp"]].copy()
    values = ta.ema(close=df["close"], length=length)
    result["indicator_name"] = f"ema_{length}"
    result["value"] = values
    return result


@indicator(name="sma", timeframe="1D")
def compute_sma(df: pd.DataFrame, length: int = 50) -> pd.DataFrame:
    """Compute Simple Moving Average.

    Args:
        df: DataFrame with 'close' column.
        length: SMA period (default 50).

    Returns:
        DataFrame with symbol, timestamp, indicator_name, value columns.
    """
    result = df[["symbol", "timestamp"]].copy()
    values = ta.sma(close=df["close"], length=length)
    result["indicator_name"] = f"sma_{length}"
    result["value"] = values
    return result


@indicator(name="atr", timeframe="1D")
def compute_atr(
    df: pd.DataFrame,
    length: int = 14,
) -> pd.DataFrame:
    """Compute Average True Range for volatility measurement.

    Args:
        df: DataFrame with 'high', 'low', 'close' columns.
        length: ATR period (default 14).

    Returns:
        DataFrame with symbol, timestamp, indicator_name, value columns.
    """
    result = df[["symbol", "timestamp"]].copy()
    values = ta.atr(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        length=length,
    )
    result["indicator_name"] = "atr"
    result["value"] = values
    return result


@indicator(name="adx", timeframe="1D")
def compute_adx(
    df: pd.DataFrame,
    length: int = 14,
) -> pd.DataFrame:
    """Compute Average Directional Index for trend strength.

    Args:
        df: DataFrame with 'high', 'low', 'close' columns.
        length: ADX period (default 14).

    Returns:
        DataFrame with symbol, timestamp, indicator_name, value columns.
    """
    result = df[["symbol", "timestamp"]].copy()
    adx_result = ta.adx(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        length=length,
    )
    if adx_result is None or adx_result.empty:
        return pd.DataFrame(columns=["symbol", "timestamp", "indicator_name", "value"])

    # pandas_ta returns ADX_14, DMP_14, DMN_14
    # We want the ADX line
    adx_col = f"ADX_{length}"
    if adx_col in adx_result.columns:
        result["indicator_name"] = "adx"
        result["value"] = adx_result[adx_col].values
    return result


def list_indicators() -> dict[str, Callable[..., pd.DataFrame]]:
    """Return a copy of the registered indicator registry.

    Returns:
        Dict mapping indicator name to its registered function.
    """
    return dict(_INDICATOR_REGISTRY)


def compute_all(
    df: pd.DataFrame,
    indicators: list[str] | None = None,
    indicator_params: dict[str, dict[str, Any]] | None = None,
) -> dict[str, pd.DataFrame]:
    """Compute multiple indicators at once.

    Args:
        df: Input DataFrame with OHLCV columns.
        indicators: List of indicator names to compute. If None, compute all registered.
        indicator_params: Optional dict mapping indicator name to its specific parameters.
                         e.g., {"ema": {"length": 200}, "sma": {"length": 50}}

    Returns:
        Dict mapping indicator name to its result DataFrame.
    """
    names = indicators or list(_INDICATOR_REGISTRY.keys())
    results: dict[str, pd.DataFrame] = {}
    for name in names:
        func = _INDICATOR_REGISTRY.get(name)
        if func is not None:
            params = indicator_params.get(name, {}) if indicator_params else {}
            results[name] = func(df, **params)
    return results
