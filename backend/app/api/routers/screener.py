"""Screener API router.

POST /api/v1/screen — Run a screen configuration against all active symbols.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from starlette.responses import JSONResponse, StreamingResponse

from backend.app.api.dependencies import ScreenEngineDep
from backend.app.api.schemas import ApiResponse, MetaInfo, ScreenRequest, ScreenSymbolResult

router = APIRouter(prefix="/screen", tags=["screener"])


@router.post(
    "",
    summary="Run a technical screen",
    description="Execute a predefined screen configuration against all active symbols. "
    "Supports multi-timeframe top-down evaluation with AND/OR filter composition. "
    "Returns matched symbols with scores, matched filters, and indicator values. "
    "Optionally export results as CSV or JSON.",
    response_description="Screen results with matched symbols and metadata",
    status_code=200,
)
async def run_screen(
    request: ScreenRequest,
    engine: ScreenEngineDep,
) -> Any:
    """Run a screen configuration and return results.

    Args:
        request: Screen configuration including config name, optional symbol subset,
                 timeframe overrides, and export format.
        engine: Injected ScreenEngine instance.

    Returns:
        Standard ApiResponse envelope or StreamingResponse for CSV/JSON export.
    """
    # Handle export formats
    if request.export_format == "csv":
        result = await engine.screen(
            config=request.config,
            symbols=request.symbols,
            timeframes=request.timeframes,
        )
        csv_data = await engine.screen_to_csv(
            config=request.config,
            path="",  # Will return string instead of writing to file
            symbols=request.symbols,
        )
        return StreamingResponse(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=screen_results.csv"},
        )

    if request.export_format == "json":
        json_data = await engine.screen_to_json(
            config=request.config,
            path="",
            symbols=request.symbols,
        )
        return JSONResponse(content=json_data)

    # Standard JSON response
    result = await engine.screen(
        config=request.config,
        symbols=request.symbols,
        timeframes=request.timeframes,
    )

    symbols = [
        ScreenSymbolResult(
            symbol=s.get("symbol", ""),
            score=float(s.get("score", 0)),
            matched_filters=list(s.get("matched_filters", [])),
            indicator_values=dict(s.get("indicator_values", {})),
        )
        for s in result.symbols
    ]

    return ApiResponse(
        data=symbols,
        meta=MetaInfo(
            timestamp=datetime.now(UTC).isoformat(),
            duration_ms=result.duration_ms,
        ),
    )
