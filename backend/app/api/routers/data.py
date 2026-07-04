"""Data API router — fetches OHLCV + indicators on-demand via Yahoo Finance.

- GET /api/v1/indicators/{symbol}  — Indicator values (computed via pandas-ta)
- GET /api/v1/indicators           — Bulk indicator values
- GET /api/v1/data/{symbol}        — OHLCV candle data
- GET /api/v1/data/symbols         — Common symbols (static list, no DB)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

import pandas as pd
import pandas_ta as ta
import yfinance as yf
from fastapi import APIRouter, Depends, Query

from backend.app.api.schemas import ApiResponse, IndicatorQueryParams, MetaInfo, OHLCVQueryParams
from backend.app.core.logging import get_logger

router = APIRouter(prefix="/data", tags=["data"])
log = get_logger("conflu.api.data")

# ── Timeframe mapping: frontend format → yfinance interval/period ──
_YF_INTERVAL: dict[str, str] = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "60m",
    "4h": "60m",  # 4h is aggregated from 1h bars
    "1D": "1d", "1W": "1wk", "1M": "1mo",
}

_YF_PERIOD: dict[str, str] = {
    "1m": "1d", "5m": "5d", "15m": "5d", "30m": "5d",
    "1h": "1mo",
    "4h": "1mo",
    "1D": "6mo", "1W": "2y", "1M": "5y",
}

# ── Indicator computation registry ──
# (fn, kwargs, result_column) — result_column=None means single-series indicator
_INDICATOR_DEFS: dict[str, tuple] = {
    "rsi":    (ta.rsi,    {"length": 14},                          None),
    "macd":   (ta.macd,   {"fast": 12, "slow": 26, "signal": 9},  "MACD_12_26_9"),
    "ema_20": (ta.ema,    {"length": 20},                          None),
    "ema_50": (ta.ema,    {"length": 50},                          None),
    "bb":     (ta.bbands, {"length": 20, "std": 2},                "BBM_20_2.0"),
    "atr":    (ta.atr,    {"length": 14},                          None),
    "adx":    (ta.adx,    {"length": 14},                          "ADX_14"),
}


def _fetch_ohlcv(symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
    """Fetch OHLCV from Yahoo Finance. Empty DataFrame if symbol not found."""
    interval = _YF_INTERVAL.get(timeframe.upper(), timeframe)
    period = _YF_PERIOD.get(timeframe.upper(), "1mo")

    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
    except Exception:
        log.warning("yfinance_fetch_failed", symbol=symbol, timeframe=timeframe)
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    df = df.reset_index()

    # yfinance returns Datetime for intraday, Date for daily+
    ts_col = "Datetime" if "Datetime" in df.columns else "Date"
    df = df.rename(columns={
        ts_col: "timestamp",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    })

    cols = [c for c in ["timestamp", "open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[cols]

    # Convert timestamp to ISO string
    df["timestamp"] = df["timestamp"].apply(
        lambda t: t.isoformat() if hasattr(t, "isoformat") else str(t)
    )

    for c in ["open", "high", "low", "close", "volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # 4h — aggregate from 1h bars
    if timeframe.upper() == "4H" and not df.empty:
        _dt = pd.to_datetime(df["timestamp"])
        df = df.set_index(_dt).resample("4h").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum",
        }).dropna().reset_index()
        df["timestamp"] = df["timestamp"].apply(
            lambda t: t.isoformat() if hasattr(t, "isoformat") else str(t)
        )

    if len(df) > limit:
        df = df.tail(limit)

    return df


def _compute_indicators(
    ohlcv: pd.DataFrame,
    names: list[str],
) -> dict[str, list[dict[str, Any]]]:
    """Compute technical indicators from OHLCV using pandas-ta."""
    result: dict[str, list[dict[str, Any]]] = {}

    if ohlcv.empty:
        return {n: [] for n in names}

    for name in names:
        if name not in _INDICATOR_DEFS:
            result[name] = []
            continue

        fn, kwargs, col = _INDICATOR_DEFS[name]

        try:
            if name in ("atr", "adx"):
                series = fn(ohlcv["high"], ohlcv["low"], ohlcv["close"], **kwargs)
            else:
                series = fn(ohlcv["close"], **kwargs)
        except Exception as exc:
            log.warning("indicator_compute_failed", indicator=name, error=str(exc))
            result[name] = []
            continue

        if series is None:
            result[name] = []
            continue

        # Extract the right column for multi-series indicators
        if isinstance(series, pd.DataFrame):
            num_cols = series.select_dtypes(include="number").columns
            if col and col in series.columns:
                values = series[col]
            elif len(num_cols) > 0:
                values = series[num_cols[0]]
            else:
                result[name] = []
                continue
        else:
            values = series

        records = [
            {"timestamp": ohlcv.iloc[i]["timestamp"], "value": float(values.iloc[i])}
            for i in range(min(len(values), len(ohlcv)))
            if pd.notna(values.iloc[i])
        ]
        result[name] = records

    return result


@router.get(
    "/indicators/{symbol}",
    summary="Get indicator values",
    description="Retrieve indicator values for a symbol. Supports comma-separated "
    "indicator names (e.g., 'rsi,macd,ema') and configurable timeframe. "
    "Data fetched from Yahoo Finance and computed on-demand.",
    status_code=200,
)
async def get_indicators(
    symbol: str,
    params: Annotated[IndicatorQueryParams, Depends()],
) -> Any:
    """Get indicator values for a symbol (on-demand via Yahoo Finance + pandas-ta)."""
    ohlcv = _fetch_ohlcv(symbol, params.timeframe, limit=params.limit)

    names = [n.strip() for n in params.indicators.split(",") if n.strip()] if params.indicators else []
    indicators_data = _compute_indicators(ohlcv, names) if not ohlcv.empty else {n: [] for n in names}

    return ApiResponse(
        data={"symbol": symbol, "timeframe": params.timeframe, "indicators": indicators_data},
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.get(
    "/indicators",
    summary="Get bulk indicators",
    description="Retrieve indicator values for multiple symbols in a single request.",
    status_code=200,
)
async def get_bulk_indicators(
    symbols: str = Query(..., description="Comma-separated list of symbols"),
    timeframe: str = Query("1D", description="Timeframe"),
    indicators: str | None = Query(None, description="Comma-separated indicator names"),
) -> Any:
    """Get indicator values for multiple symbols (on-demand)."""
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    names = [n.strip() for n in indicators.split(",") if n.strip()] if indicators else []
    result: dict[str, dict[str, Any]] = {}

    for sym in symbol_list:
        ohlcv = _fetch_ohlcv(sym, timeframe, limit=200)
        result[sym] = _compute_indicators(ohlcv, names) if not ohlcv.empty else {n: [] for n in names}

    return ApiResponse(
        data={"symbols": symbol_list, "timeframe": timeframe, "indicators": result},
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.get(
    "/symbols",
    summary="List available symbols",
    description="Return a static list of common symbols (no database dependency). "
    "Frontend does not require this for autocomplete.",
    status_code=200,
)
async def get_symbols(
    asset_class: str | None = Query(None, description="Filter by asset class"),
    active_only: bool = Query(True, description="Only return active symbols"),
) -> Any:
    """List available symbols. Static list — autocomplete is not needed."""
    COMMON: list[dict[str, Any]] = [
        {"symbol": "AAPL", "asset_class": "equities", "exchange": "NASDAQ", "name": "Apple Inc.", "active": True},
        {"symbol": "MSFT", "asset_class": "equities", "exchange": "NASDAQ", "name": "Microsoft Corp.", "active": True},
        {"symbol": "GOOGL", "asset_class": "equities", "exchange": "NASDAQ", "name": "Alphabet Inc.", "active": True},
        {"symbol": "AMZN", "asset_class": "equities", "exchange": "NASDAQ", "name": "Amazon.com Inc.", "active": True},
        {"symbol": "NVDA", "asset_class": "equities", "exchange": "NASDAQ", "name": "NVIDIA Corp.", "active": True},
        {"symbol": "META", "asset_class": "equities", "exchange": "NASDAQ", "name": "Meta Platforms Inc.", "active": True},
        {"symbol": "TSLA", "asset_class": "equities", "exchange": "NASDAQ", "name": "Tesla Inc.", "active": True},
        {"symbol": "JPM", "asset_class": "equities", "exchange": "NYSE", "name": "JPMorgan Chase & Co.", "active": True},
        {"symbol": "SPY", "asset_class": "etf", "exchange": "NYSEARCA", "name": "SPDR S&P 500 ETF", "active": True},
        {"symbol": "QQQ", "asset_class": "etf", "exchange": "NASDAQ", "name": "Invesco QQQ Trust", "active": True},
    ]
    # Filter by asset_class if provided
    if asset_class:
        COMMON = [s for s in COMMON if s["asset_class"] == asset_class]

    return ApiResponse(
        data=COMMON,
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.get(
    "/{symbol}",
    summary="Get OHLCV data",
    description="Retrieve OHLCV candle data for a symbol. "
    "Data fetched from Yahoo Finance on-demand — no pre-ingestion needed.",
    status_code=200,
)
async def get_data(
    symbol: str,
    params: Annotated[OHLCVQueryParams, Depends()],
) -> Any:
    """Get OHLCV candle data for a symbol (on-demand via Yahoo Finance)."""
    df = _fetch_ohlcv(symbol, params.timeframe, limit=params.limit)

    candles = []
    if not df.empty:
        for _, row in df.iterrows():
            candles.append({
                "timestamp": row["timestamp"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            })

    return ApiResponse(
        data={"symbol": symbol, "timeframe": params.timeframe, "candles": candles},
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )
