"""Ticker analysis API router.

Provides programmatic elite-trader-grade analysis of individual tickers,
covering technical indicators, fundamentals, earnings, sentiment, and risk,
with a synthesized actionable verdict (BUY/SELL/HOLD/WATCH).

- POST /api/v1/ticker/{symbol}/analyze  — Full multi-module ticker analysis
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from backend.app.api.dependencies import TickerAnalysisDep
from backend.app.api.schemas import ApiResponse, MetaInfo
from backend.app.core.logging import get_logger
from backend.app.domain.ticker_analysis.models import TickerAnalysisRequest

router = APIRouter(prefix="/ticker", tags=["ticker"])
log = get_logger("conflu.api.ticker_analysis")


@router.post(
    "/{symbol}/analyze",
    summary="Full ticker analysis",
    description="Run the complete ticker analysis pipeline — technical, fundamental, earnings, "
    "sentiment, and risk — and return a synthesized verdict (BUY/SELL/HOLD/WATCH) "
    "with entry zone, stop loss, targets, triggers, and thesis.",
    status_code=200,
)
async def analyze_ticker(
    symbol: str,
    request: TickerAnalysisRequest,
    engine: TickerAnalysisDep = None,
) -> ApiResponse[dict[str, Any]]:
    """Run the full ticker analysis pipeline for a single symbol.

    Uses:
    - yfinance for fundamental/earnings/sentiment data (5-min in-memory cache)
    - TradingView screener for technical data (passed via tv_data)
    - In-memory synthesis engine for verdict generation

    Returns 200 with `TickerAnalysisResponse`-shaped data on success.
    Returns 200 with `error` field if the symbol cannot be resolved.
    """
    log.info("ticker_analysis_requested", symbol=symbol)

    result = engine.analyze(request)

    return ApiResponse(
        data=result.model_dump(mode="json") if hasattr(result, "model_dump") else result,
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )
