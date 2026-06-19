"""Filter registry with @filter decorator and built-in screen filters.

Five categories: trend, momentum, volume, volatility, pattern.
Uses the same registry pattern as the @indicator decorator in indicators.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Literal

import pandas as pd

_FILTER_REGISTRY: dict[str, FilterDef] = {}


@dataclass
class FilterParam:
    """A parameter for a filter function."""

    name: str
    type: Literal["float", "int", "str", "bool"]
    default: Any
    description: str


@dataclass
class FilterDef:
    """Definition of a registered filter."""

    name: str
    category: str  # 'trend', 'momentum', 'volume', 'volatility', 'pattern'
    description: str
    func: Callable[..., pd.Series]
    params: list[FilterParam] = field(default_factory=list)
    timeframes_supported: list[str] = field(
        default_factory=lambda: ["1D", "4h", "1h", "15m", "5m"],
    )


def filter(
    name: str,
    category: str,
    description: str = "",
    params: list[FilterParam] | None = None,
    timeframes_supported: list[str] | None = None,
) -> Callable[[Callable[..., pd.Series]], Callable[..., pd.Series]]:
    """Register a screen filter function.

    The wrapped function must accept a DataFrame of indicator values
    and return a boolean pd.Series (mask) with the same index.

    Args:
        name: Canonical filter name (e.g., 'rsi_oversold').
        category: Filter category ('trend', 'momentum', 'volume', 'volatility', 'pattern').
        description: Human-readable description.
        params: List of parameter definitions for validation/UI.
        timeframes_supported: Timeframes this filter works on (default all).

    Returns:
        A decorator that registers the filter and wraps it for validation.
    """

    def decorator(func: Callable[..., pd.Series]) -> Callable[..., pd.Series]:
        _FILTER_REGISTRY[name] = FilterDef(
            name=name,
            category=category,
            description=description or func.__doc__ or "",
            func=func,
            params=params or [],
            timeframes_supported=timeframes_supported or ["1D", "4h", "1h", "15m", "5m"],
        )

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> pd.Series:
            result = func(*args, **kwargs)
            if not isinstance(result, pd.Series) or result.dtype != bool:
                msg = f"Filter '{name}' must return a boolean Series, got {type(result)}"
                raise ValueError(msg)
            return result

        return wrapper

    return decorator


def list_filters() -> dict[str, FilterDef]:
    """Return a copy of the registered filter registry.

    Returns:
        Dict mapping filter name to its FilterDef.
    """
    return dict(_FILTER_REGISTRY)


def list_filters_by_category(category: str) -> dict[str, FilterDef]:
    """Return filters filtered by category.

    Args:
        category: Filter category to filter by.

    Returns:
        Dict mapping filter name to FilterDef for matching category.
    """
    return {
        name: fdef
        for name, fdef in _FILTER_REGISTRY.items()
        if fdef.category == category
    }


# =============================================================================
# Trend Filters
# =============================================================================


@filter(
    name="price_above_ema",
    category="trend",
    description="Price close is above the EMA of given period",
    params=[FilterParam(name="period", type="int", default=200, description="EMA period")],
)
def price_above_ema(df: pd.DataFrame, period: int = 200) -> pd.Series:
    """Close price above EMA. df must have 'close' and indicator columns."""
    col = f"ema_{period}"
    if col in df.columns:
        return df["close"] > df[col]
    return pd.Series(False, index=df.index)


@filter(
    name="price_below_ema",
    category="trend",
    description="Price close is below the EMA of given period",
    params=[FilterParam(name="period", type="int", default=200, description="EMA period")],
)
def price_below_ema(df: pd.DataFrame, period: int = 200) -> pd.Series:
    """Close price below EMA."""
    col = f"ema_{period}"
    if col in df.columns:
        return df["close"] < df[col]
    return pd.Series(False, index=df.index)


@filter(
    name="adx_trending",
    category="trend",
    description="ADX above threshold indicates strong trend",
    params=[FilterParam(name="threshold", type="float", default=25.0, description="ADX threshold")],
)
def adx_trending(df: pd.DataFrame, threshold: float = 25.0) -> pd.Series:
    """ADX > threshold indicates trending market."""
    if "adx" in df.columns:
        return df["adx"] > threshold
    return pd.Series(False, index=df.index)


@filter(
    name="adx_non_trending",
    category="trend",
    description="ADX below threshold indicates weak/range-bound market",
    params=[FilterParam(name="threshold", type="float", default=20.0, description="ADX threshold")],
)
def adx_non_trending(df: pd.DataFrame, threshold: float = 20.0) -> pd.Series:
    """ADX < threshold indicates non-trending/ranging market."""
    if "adx" in df.columns:
        return df["adx"] < threshold
    return pd.Series(False, index=df.index)


@filter(
    name="ema_cross",
    category="trend",
    description="Fast EMA crossed above slow EMA (bullish)",
    params=[
        FilterParam(name="fast", type="int", default=50, description="Fast EMA period"),
        FilterParam(name="slow", type="int", default=200, description="Slow EMA period"),
    ],
)
def ema_cross(df: pd.DataFrame, fast: int = 50, slow: int = 200) -> pd.Series:
    """Bullish EMA cross: fast EMA > slow EMA."""
    fast_col = f"ema_{fast}"
    slow_col = f"ema_{slow}"
    if fast_col in df.columns and slow_col in df.columns:
        return df[fast_col] > df[slow_col]
    return pd.Series(False, index=df.index)


# =============================================================================
# Momentum Filters
# =============================================================================


@filter(
    name="rsi_oversold",
    category="momentum",
    description="RSI below threshold indicates oversold condition",
    params=[FilterParam(name="threshold", type="float", default=30.0, description="RSI threshold")],
)
def rsi_oversold(df: pd.DataFrame, threshold: float = 30.0) -> pd.Series:
    """RSI below oversold threshold."""
    if "rsi" in df.columns:
        return df["rsi"] < threshold
    return pd.Series(False, index=df.index)


@filter(
    name="rsi_overbought",
    category="momentum",
    description="RSI above threshold indicates overbought condition",
    params=[FilterParam(name="threshold", type="float", default=70.0, description="RSI threshold")],
)
def rsi_overbought(df: pd.DataFrame, threshold: float = 70.0) -> pd.Series:
    """RSI above overbought threshold."""
    if "rsi" in df.columns:
        return df["rsi"] > threshold
    return pd.Series(False, index=df.index)


@filter(
    name="rsi_range",
    category="momentum",
    description="RSI within a specified range",
    params=[
        FilterParam(name="low", type="float", default=30.0, description="Lower bound"),
        FilterParam(name="high", type="float", default=70.0, description="Upper bound"),
    ],
)
def rsi_range(df: pd.DataFrame, low: float = 30.0, high: float = 70.0) -> pd.Series:
    """RSI between low and high."""
    if "rsi" in df.columns:
        return (df["rsi"] > low) & (df["rsi"] < high)
    return pd.Series(False, index=df.index)


@filter(
    name="macd_bullish",
    category="momentum",
    description="MACD line above signal line (bullish)",
)
def macd_bullish(df: pd.DataFrame) -> pd.Series:
    """MACD line above signal line (bullish)."""
    if "macd_line" in df.columns and "macd_signal" in df.columns:
        return df["macd_line"] > df["macd_signal"]
    return pd.Series(False, index=df.index)


@filter(
    name="macd_bearish",
    category="momentum",
    description="MACD line below signal line (bearish)",
)
def macd_bearish(df: pd.DataFrame) -> pd.Series:
    """MACD line below signal line (bearish)."""
    if "macd_line" in df.columns and "macd_signal" in df.columns:
        return df["macd_line"] < df["macd_signal"]
    return pd.Series(False, index=df.index)


@filter(
    name="macd_histogram_rising",
    category="momentum",
    description="MACD histogram is rising (current > previous)",
)
def macd_histogram_rising(df: pd.DataFrame) -> pd.Series:
    """MACD histogram value is higher than previous bar."""
    if "macd_hist" in df.columns:
        return df["macd_hist"] > df["macd_hist"].shift(1)
    return pd.Series(False, index=df.index)


# =============================================================================
# Volume Filters
# =============================================================================


@filter(
    name="rvol_high",
    category="volume",
    description="Relative volume above threshold indicates high activity",
    params=[FilterParam(name="threshold", type="float", default=1.5, description="RVOL threshold")],
)
def rvol_high(df: pd.DataFrame, threshold: float = 1.5) -> pd.Series:
    """Relative volume > threshold. Uses volume and 20-period avg volume."""
    if "volume" in df.columns:
        avg_vol = df["volume"].rolling(20).mean()
        rvol = df["volume"] / avg_vol
        return rvol > threshold
    return pd.Series(False, index=df.index)


@filter(
    name="rvol_low",
    category="volume",
    description="Relative volume below threshold indicates low activity",
    params=[FilterParam(name="threshold", type="float", default=0.5, description="RVOL threshold")],
)
def rvol_low(df: pd.DataFrame, threshold: float = 0.5) -> pd.Series:
    """Relative volume < threshold."""
    if "volume" in df.columns:
        avg_vol = df["volume"].rolling(20).mean()
        rvol = df["volume"] / avg_vol
        return rvol < threshold
    return pd.Series(False, index=df.index)


@filter(
    name="obv_slope_positive",
    category="volume",
    description="OBV slope positive over lookback period indicates accumulation",
    params=[FilterParam(name="lookback", type="int", default=5, description="Lookback period")],
)
def obv_slope_positive(df: pd.DataFrame, lookback: int = 5) -> pd.Series:
    """OBV slope positive over lookback period (accumulation)."""
    if "obv" in df.columns:
        slope = df["obv"] - df["obv"].shift(lookback)
        return slope > 0
    return pd.Series(False, index=df.index)


# =============================================================================
# Volatility Filters
# =============================================================================


@filter(
    name="atr_percentile_high",
    category="volatility",
    description="ATR above its percentile threshold indicates high volatility",
    params=[
        FilterParam(name="percentile", type="float", default=75.0, description="ATR percentile threshold"),
    ],
)
def atr_percentile_high(df: pd.DataFrame, percentile: float = 75.0) -> pd.Series:
    """ATR above rolling percentile."""
    if "atr" in df.columns:
        atr_threshold = df["atr"].rolling(100).quantile(percentile / 100.0)
        return df["atr"] > atr_threshold
    return pd.Series(False, index=df.index)


@filter(
    name="atr_percentile_low",
    category="volatility",
    description="ATR below its percentile threshold indicates low volatility",
    params=[
        FilterParam(name="percentile", type="float", default=25.0, description="ATR percentile threshold"),
    ],
)
def atr_percentile_low(df: pd.DataFrame, percentile: float = 25.0) -> pd.Series:
    """ATR below rolling percentile."""
    if "atr" in df.columns:
        atr_threshold = df["atr"].rolling(100).quantile(percentile / 100.0)
        return df["atr"] < atr_threshold
    return pd.Series(False, index=df.index)


@filter(
    name="bb_inside",
    category="volatility",
    description="Price is inside the Bollinger Bands",
)
def bb_inside(df: pd.DataFrame) -> pd.Series:
    """Price inside Bollinger Bands (between lower and upper)."""
    if all(col in df.columns for col in ["bb_lower", "bb_upper"]):
        return (df["close"] >= df["bb_lower"]) & (df["close"] <= df["bb_upper"])
    return pd.Series(False, index=df.index)


@filter(
    name="bb_touch",
    category="volatility",
    description="Price touches or breaks an outer Bollinger Band",
)
def bb_touch(df: pd.DataFrame) -> pd.Series:
    """Price touches/breaks upper or lower Bollinger Band."""
    if all(col in df.columns for col in ["bb_lower", "bb_upper"]):
        return (df["close"] <= df["bb_lower"]) | (df["close"] >= df["bb_upper"])
    return pd.Series(False, index=df.index)


# =============================================================================
# Pattern Filters (receive raw OHLCV data, not indicator values)
# =============================================================================


@filter(
    name="candle_engulfing",
    category="pattern",
    description="Bullish or bearish engulfing candlestick pattern",
    params=[FilterParam(name="direction", type="str", default="bullish", description="Direction: bullish or bearish")],
)
def candle_engulfing(df: pd.DataFrame, direction: str = "bullish") -> pd.Series:
    """Detect bullish/bearish engulfing patterns.

    Bullish engulfing: current open < previous close AND current close > previous open.
    Bearish engulfing: current open > previous close AND current close < previous open.
    """
    prev = df.shift(1)
    if direction == "bullish":
        return (df["open"] < prev["close"]) & (df["close"] > prev["open"])
    else:
        return (df["open"] > prev["close"]) & (df["close"] < prev["open"])


@filter(
    name="candle_hammer",
    category="pattern",
    description="Hammer candlestick pattern with long lower wick",
)
def candle_hammer(df: pd.DataFrame) -> pd.Series:
    """Detect hammer pattern (long lower wick, small body, small or no upper wick)."""
    body = abs(df["close"] - df["open"])
    lower_wick = df[["open", "close"]].min(axis=1) - df["low"]
    upper_wick = df["high"] - df[["open", "close"]].max(axis=1)
    return (lower_wick > body * 2) & (upper_wick < body * 0.5)


@filter(
    name="candle_doji",
    category="pattern",
    description="Doji candlestick pattern where open and close are nearly equal",
)
def candle_doji(df: pd.DataFrame) -> pd.Series:
    """Detect doji pattern (open ≈ close, within 5% of full range)."""
    body = abs(df["close"] - df["open"])
    full_range = df["high"] - df["low"]
    # Avoid division by zero
    body_pct = body / full_range.replace(0, float("nan"))
    return body_pct < 0.05
