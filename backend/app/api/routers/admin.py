"""Admin endpoints for cache warming and data refresh.

D-44 Task 8. Currently exposes a single endpoint,
``POST /api/v1/admin/refresh-data``, that pre-warms the in-memory
yfinance OHLCV cache so subsequent per-ticker analyses use fresh
data. The user can hit this on Sunday afternoon (or any time) with
a list of symbols; the default watchlist covers the top ~50 S&P 500
tickers.

There is no auth on this endpoint yet. For production, gate it behind
an admin token or IP allowlist.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.app.core.logging import get_logger
from backend.app.domain.ticker_analysis.technical import (
    _fetch_daily_ohlcv,
    _fetch_weekly_ohlcv,
)

log = get_logger("conflu.api.admin")
router = APIRouter(prefix="/admin", tags=["admin"])


# Default watchlist — top S&P 500 by market cap + the system's primary
# ticker-analysis surface. Move to config later if needed.
DEFAULT_WATCHLIST: list[str] = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
    "JPM", "V", "MA", "UNH", "XOM", "JNJ", "WMT", "PG",
    "HD", "CVX", "KO", "PEP", "MRK", "ABBV", "BAC", "COST",
    "AVGO", "TMO", "NFLX", "CRM", "ORCL", "CSCO", "ADBE",
    "VZ", "T", "PFE", "NKE", "INTC", "QCOM", "TXN", "AMD",
    "SLB", "ESTC", "NWS", "IQV", "SCHW", "WHD", "GFL", "GWRE",
    "SE", "WDAY", "PD", "WT", "CBZ", "AUGO", "VEEV",
]


class RefreshRequest(BaseModel):
    """Optional body for POST /admin/refresh-data. If symbols is omitted,
    the DEFAULT_WATCHLIST is used.
    """
    model_config = {"extra": "forbid"}
    symbols: list[str] | None = Field(
        default=None,
        description="Tickers to pre-warm. If null, uses the default watchlist.",
    )


class RefreshResponse(BaseModel):
    refreshed: int
    failed: list[dict[str, str]]
    duration_ms: int
    timestamp: str


@router.post("/refresh-data", response_model=RefreshResponse)
async def refresh_data(req: RefreshRequest | None = None) -> RefreshResponse:
    """Pre-warm the yfinance OHLCV cache for the given (or default) symbols.

    The function calls the same fetchers used by the orchestrator, so
    subsequent `POST /api/v1/ticker/{symbol}/analyze` calls will hit the
    cache (TTL 6h) instead of re-fetching from yfinance.
    """
    start = time.monotonic()
    symbols = (req.symbols if req and req.symbols else None) or DEFAULT_WATCHLIST
    refreshed = 0
    failed: list[dict[str, str]] = []

    for sym in symbols:
        try:
            # Both fetchers write into the module-level _OHLCV_CACHE.
            _fetch_daily_ohlcv(sym)
            _fetch_weekly_ohlcv(sym)
            refreshed += 1
        except Exception as e:
            failed.append({"symbol": sym, "error": str(e)[:200]})
            log.warning("admin_refresh_failed", symbol=sym, error=str(e))

    duration_ms = round((time.monotonic() - start) * 1000)
    log.info(
        "admin_refresh_complete",
        refreshed=refreshed,
        failed=len(failed),
        duration_ms=duration_ms,
    )
    return RefreshResponse(
        refreshed=refreshed,
        failed=failed,
        duration_ms=duration_ms,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
