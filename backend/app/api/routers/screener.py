"""Screener API router.

POST /api/v1/screen — Run a screen configuration against all active symbols.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from starlette.responses import JSONResponse, StreamingResponse

from backend.app.api.dependencies import ScreenEngineDep
from backend.app.api.schemas import (
    ApiResponse,
    CustomScreenConfig,
    MetaInfo,
    ScreenRequest,
    ScreenSymbolResult,
)
from backend.app.infrastructure.screener.configs import ScreenConfig

router = APIRouter(prefix="/screen", tags=["screener"])


def _convert_custom_config(custom: CustomScreenConfig) -> ScreenConfig:
    """Convert API CustomScreenConfig to internal ScreenConfig."""
    from backend.app.infrastructure.screener.configs import FilterRule

    filters = [
        FilterRule(
            category=f.category,
            indicator=f.indicator,
            params=f.params,
            operator=f.operator,
            timeframe=f.timeframe,
            negate=f.negate,
            compare_timeframe=f.compare_timeframe,
        )
        for f in custom.filters
    ]
    return ScreenConfig(
        name=custom.name,
        description=custom.description,
        asset_classes=custom.asset_classes,
        timeframes=custom.timeframes,
        filters=filters,
    )


def _resolve_config(request: ScreenRequest) -> ScreenConfig | str:
    """Resolve config to either template name or ScreenConfig object."""
    if isinstance(request.config, str):
        return request.config
    return _convert_custom_config(request.config)


@router.post(
    "",
    summary="Run a technical screen",
    description="Execute a predefined screen configuration or custom filter configuration "
    "against all active symbols. Supports multi-timeframe top-down evaluation "
    "with AND/OR filter composition. Returns matched symbols with scores, "
    "matched filters, and indicator values. Optionally export results as CSV or JSON.",
    response_description="Screen results with matched symbols and metadata",
    status_code=200,
)
async def run_screen(
    request: ScreenRequest,
    engine: ScreenEngineDep,
) -> Any:
    """Run a screen configuration and return results.

    Args:
        request: Screen configuration including config name or custom config,
                 optional symbol subset, timeframe overrides, and export format.
        engine: Injected ScreenEngine instance.

    Returns:
        Standard ApiResponse envelope or StreamingResponse for CSV/JSON export.
    """
    resolved_config = _resolve_config(request)

    # Handle export formats
    if request.export_format == "csv":
        result = await engine.screen(
            config=resolved_config,
            symbols=request.symbols,
            timeframes=request.timeframes,
        )
        csv_data = await engine.screen_to_csv(
            config=resolved_config,
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
            config=resolved_config,
            path="",
            symbols=request.symbols,
        )
        return JSONResponse(content=json_data)

    # Standard JSON response
    result = await engine.screen(
        config=resolved_config,
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
