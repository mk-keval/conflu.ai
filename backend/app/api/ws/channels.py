"""WebSocket channel definitions and update provider functions.

Channels provide real-time data for specific streaming topics.
Each channel prefix maps to a provider function that fetches the latest data.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from backend.app.core.database import get_db
from backend.app.core.logging import get_logger
from backend.app.infrastructure.screener.cache import IndicatorCache

log = get_logger("conflu.api.ws.channels")


# ── Channel Update Provider Registry ──

_update_providers: dict[str, Callable[..., Coroutine[Any, Any, dict[str, Any]]]] = {}


def register_update_provider(
    channel_prefix: str,
    provider: Callable[..., Coroutine[Any, Any, dict[str, Any]]],
) -> None:
    """Register a provider function for a channel prefix.

    Args:
        channel_prefix: e.g., 'price:', 'indicator:', 'screener:', 'risk:'
        provider: Async callable that returns update data dict.
    """
    _update_providers[channel_prefix] = provider
    log.info("update_provider_registered", channel_prefix=channel_prefix)


# ── Channel Constants ──

CHANNEL_PRICE = "price"
CHANNEL_INDICATOR = "indicator"
CHANNEL_SIGNAL = "signal"
CHANNEL_SCREENER = "screener"
CHANNEL_RISK = "risk"
CHANNEL_BACKTEST = "backtest"


# ── Price Update Provider ──


async def price_update_provider(symbol: str) -> dict[str, Any]:
    """Fetch latest price for a symbol from DuckDB.

    Args:
        symbol: Trading symbol (e.g., 'AAPL').

    Returns:
        Dict with symbol, price, volume, timestamp.
    """
    try:
        with get_db(read_only=True) as con:
            result = con.sql(
                "SELECT timestamp, close, volume FROM ohlcv "
                "WHERE symbol = ? AND timeframe = '1D' "
                "ORDER BY timestamp DESC LIMIT 1",
                params=[symbol],
            ).fetchdf()
    except Exception:
        log.exception("price_update_db_error", symbol=symbol)
        return {"symbol": symbol, "price": None, "volume": None, "error": "db_error"}

    if result.empty:
        return {"symbol": symbol, "price": None, "volume": None}

    row = result.iloc[0]
    return {
        "symbol": symbol,
        "price": float(row["close"]),
        "volume": float(row["volume"]),
        "timestamp": (
            row["timestamp"].isoformat() if hasattr(row["timestamp"], "isoformat") else str(row["timestamp"])
        ),
    }


# ── Indicator Update Provider ──


async def indicator_update_provider(symbol: str, indicator_name: str) -> dict[str, Any]:
    """Fetch latest indicator value for a symbol.

    Args:
        symbol: Trading symbol.
        indicator_name: Indicator name (e.g., 'rsi_14', 'macd').

    Returns:
        Dict with symbol, indicator, value, timestamp.
    """
    try:
        cache = IndicatorCache()
        df = await cache.get_latest(indicator_name, timeframe="1D", symbols=[symbol])
    except Exception:
        log.exception("indicator_update_error", symbol=symbol, indicator=indicator_name)
        return {"symbol": symbol, "indicator": indicator_name, "value": None}

    if df is None or df.empty:
        return {"symbol": symbol, "indicator": indicator_name, "value": None}

    row = df.iloc[0]
    return {
        "symbol": symbol,
        "indicator": indicator_name,
        "value": float(row["value"]) if "value" in row else None,
        "timestamp": (
            row["timestamp"].isoformat() if hasattr(row["timestamp"], "isoformat") else str(row["timestamp"])
        ),
    }
