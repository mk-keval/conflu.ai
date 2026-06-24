"""Data API router.

- GET /api/v1/indicators/{symbol}  — Get indicator values for a symbol
- GET /api/v1/indicators           — Bulk indicator values for multiple symbols
- GET /api/v1/data/{symbol}        — Get OHLCV candle data
- GET /api/v1/data/symbols         — List available symbols
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from backend.app.api.dependencies import IndicatorCacheDep
from backend.app.api.schemas import ApiResponse, IndicatorQueryParams, MetaInfo, OHLCVQueryParams
from backend.app.core.database import get_db
from backend.app.core.logging import get_logger

router = APIRouter(prefix="/data", tags=["data"])
log = get_logger("conflu.api.data")


@router.get(
    "/indicators/{symbol}",
    summary="Get indicator values",
    description="Retrieve indicator values for a symbol. Supports comma-separated "
    "indicator names (e.g., 'rsi,macd,ema') and configurable timeframe.",
    status_code=200,
)
async def get_indicators(
    symbol: str,
    params: Annotated[IndicatorQueryParams, Depends()],
    cache: IndicatorCacheDep = None,
) -> Any:
    """Get indicator values for a symbol."""
    indicators_data: dict[str, list[dict[str, Any]]] = {}

    if params.indicators:
        indicator_names = [n.strip() for n in params.indicators.split(",") if n.strip()]
        for name in indicator_names:
            series = await cache.get_series(
                indicator_name=name,
                timeframe=params.timeframe,
                symbol=symbol,
                limit=params.limit,
            )
            if series is not None and not series.empty:
                records = []
                for _, row in series.iterrows():
                    records.append(
                        {
                            "timestamp": (
                                row["timestamp"].isoformat()
                                if hasattr(row["timestamp"], "isoformat")
                                else str(row["timestamp"])
                            ),
                            "value": float(row["value"]) if "value" in row else None,
                        }
                    )
                indicators_data[name] = records
            else:
                indicators_data[name] = []

    return ApiResponse(
        data={
            "symbol": symbol,
            "timeframe": params.timeframe,
            "indicators": indicators_data,
        },
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
    cache: IndicatorCacheDep = None,
) -> Any:
    """Get indicator values for multiple symbols."""
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    result: dict[str, dict[str, Any]] = {}

    if indicators:
        indicator_names = [n.strip() for n in indicators.split(",") if n.strip()]
        for sym in symbol_list:
            sym_data: dict[str, list[dict[str, Any]]] = {}
            for name in indicator_names:
                series = await cache.get_series(
                    indicator_name=name,
                    timeframe=timeframe,
                    symbol=sym,
                    limit=200,
                )
                if series is not None and not series.empty:
                    records = []
                    for _, row in series.iterrows():
                        records.append(
                            {
                                "timestamp": (
                                    row["timestamp"].isoformat()
                                    if hasattr(row["timestamp"], "isoformat")
                                    else str(row["timestamp"])
                                ),
                                "value": float(row["value"]) if "value" in row else None,
                            }
                        )
                    sym_data[name] = records
                else:
                    sym_data[name] = []
            result[sym] = sym_data

    return ApiResponse(
        data={
            "symbols": symbol_list,
            "timeframe": timeframe,
            "indicators": result,
        },
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.get(
    "/symbols",
    summary="List available symbols",
    description="Get the list of available trading symbols with metadata.",
    status_code=200,
)
async def get_symbols(
    asset_class: str | None = Query(None, description="Filter by asset class"),
    active_only: bool = Query(True, description="Only return active symbols"),
) -> Any:
    """Get list of available symbols."""
    conditions = []
    params: list[Any] = []

    if asset_class:
        conditions.append("asset_class = ?")
        params.append(asset_class)
    if active_only:
        conditions.append("active = true")

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_db(read_only=True) as con:
        rows = con.sql(
            f"""
            SELECT symbol, asset_class, exchange, tv_ticker, active
            FROM symbol_metadata
            {where_clause}
            ORDER BY symbol
            """,
            params=params,
        ).fetchall()

    symbols = []
    for row in rows:
        symbols.append(
            {
                "symbol": row[0],
                "asset_class": row[1],
                "exchange": row[2],
                "tv_ticker": row[3],
                "name": row[3],  # Use tv_ticker as name since name column doesn't exist
                "active": bool(row[4]),
            }
        )

    return ApiResponse(
        data=symbols,
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.get(
    "/{symbol}",
    summary="Get OHLCV data",
    description="Retrieve OHLCV candle data for a symbol with optional date range filtering.",
    status_code=200,
)
async def get_data(
    symbol: str,
    params: Annotated[OHLCVQueryParams, Depends()],
) -> Any:
    """Get OHLCV candle data for a symbol."""
    with get_db(read_only=True) as con:
        rows = con.sql(
            """
            SELECT timestamp, open, high, low, close, volume
            FROM ohlcv
            WHERE symbol = ? AND timeframe = ?
              AND (? IS NULL OR timestamp >= ?::TIMESTAMPTZ)
              AND (? IS NULL OR timestamp <= ?::TIMESTAMPTZ)
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            params=[
                symbol,
                params.timeframe,
                params.start,
                params.start,
                params.end,
                params.end,
                params.limit,
            ],
        ).fetchall()

    candles = []
    for row in rows:
        candles.append(
            {
                "timestamp": (row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0])),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            }
        )

    return ApiResponse(
        data={
            "symbol": symbol,
            "timeframe": params.timeframe,
            "candles": candles,
        },
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )
