"""Filter Sweep API router.

Provides endpoints for running filter parameter sweeps and retrieving results.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from backend.app.api.dependencies import BacktestEngineDep
from backend.app.api.schemas import ApiResponse, MetaInfo
from backend.app.core.database import get_db
from backend.app.core.logging import get_logger
from backend.app.infrastructure.backtest.filter_sweep import (
    FilterParamRange,
    FilterSweepConfig,
    PRESET_SWEEPS,
)
from backend.app.infrastructure.backtest.filter_sweep_engine import (
    FilterSweepEngine,
    FilterSweepSummary,
    FilterSweepConfig,
    run_filter_sweep,
    run_preset_sweep,
)

router = APIRouter(prefix="/filter-sweep", tags=["filter-sweep"])
log = get_logger("conflu.api.filter_sweep")


# In-memory storage for sweep results (in production, use Redis/DB)
_sweep_results: dict[str, FilterSweepSummary] = {}
_active_sweeps: dict[str, str] = {}  # sweep_id -> status


@router.get(
    "/presets",
    summary="List available preset sweep configurations",
    description="Returns list of available preset filter sweep configurations.",
)
async def list_presets() -> Any:
    """List available preset sweep configurations."""
    presets = {}
    for name, config in PRESET_SWEEPS.items():
        presets[name] = {
            "name": config.name,
            "description": config.description,
            "screen_name": config.screen_name,
            "symbols": config.symbols,
            "timeframe": config.timeframe,
            "start_date": config.start_date,
            "end_date": config.end_date,
            "optimization_metric": config.optimization_metric,
            "max_combinations": config.max_combinations,
            "params": {k: v.model_dump() for k, v in config.param_grid.items()},
        }
    return ApiResponse(data=presets, meta=MetaInfo())


@router.get(
    "/params",
    summary="List available filter parameters for sweeping",
    description="Returns all available filter parameters that can be swept.",
)
async def list_filter_params() -> Any:
    """List all available filter parameters for sweeping."""
    from backend.app.infrastructure.backtest.filter_sweep import DEFAULT_FILTER_PARAM_RANGES
    params = {k: v.model_dump() for k, v in DEFAULT_FILTER_PARAM_RANGES.items()}
    return ApiResponse(data=params, meta=MetaInfo())


@router.post(
    "/run",
    summary="Run a custom filter parameter sweep",
    description="Run a filter parameter sweep with custom configuration.",
    status_code=200,
)
async def run_custom_sweep(
    config: FilterSweepConfig,
    background_tasks: BackgroundTasks,
) -> Any:
    """Run a custom filter parameter sweep."""
    sweep_id = config.sweep_id or str(uuid4())
    config.sweep_id = sweep_id

    # Store initial status
    _active_sweeps[sweep_id] = "running"

    async def run_sweep():
        try:
            engine = FilterSweepEngine()
            result = await run_filter_sweep(config)
            _sweep_results[sweep_id] = result
            _active_sweeps[sweep_id] = "completed"
        except Exception as e:
            log.exception("filter_sweep_failed", sweep_id=sweep_id, error=str(e))
            _active_sweeps[sweep_id] = "failed"
            _sweep_results[sweep_id] = FilterSweepSummary(
                sweep_id=sweep_id,
                name="Failed",
                screen_name="",
                total_combinations=0,
                valid_results=0,
                failed_results=0,
                status="failed",
                error_message=str(e),
            )

    background_tasks.add_task(run_sweep)

    return ApiResponse(
        data={"sweep_id": sweep_id, "status": "started"},
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.post(
    "/run-preset/{preset_name}",
    summary="Run a preset filter sweep",
    description="Run a predefined filter sweep configuration by name.",
    status_code=200,
)
async def run_preset_sweep_endpoint(
    preset_name: str,
    background_tasks: BackgroundTasks,
    symbols: list[str] | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    optimization_metric: str | None = Query(None),
) -> Any:
    """Run a preset filter sweep with optional overrides."""
    if preset_name not in PRESET_SWEEPS:
        raise HTTPException(status_code=404, detail=f"Unknown preset: {preset_name}")

    base_config = PRESET_SWEEPS[preset_name]
    sweep_id = str(uuid4())

    # Create config with overrides
    config_dict = base_config.model_dump()
    config_dict["sweep_id"] = sweep_id
    if symbols:
        config_dict["symbols"] = symbols
    if start_date:
        config_dict["start_date"] = start_date
    if end_date:
        config_dict["end_date"] = end_date
    if optimization_metric:
        config_dict["optimization_metric"] = optimization_metric

    config = FilterSweepConfig(**config_dict)

    _active_sweeps[sweep_id] = "running"

    async def run_sweep():
        try:
            result = await run_preset_sweep(preset_name)
            _sweep_results[sweep_id] = result
            _active_sweeps[sweep_id] = "completed"
        except Exception as e:
            log.exception("preset_sweep_failed", sweep_id=sweep_id, error=str(e))
            _active_sweeps[sweep_id] = "failed"

    background_tasks.add_task(run_sweep)

    return ApiResponse(
        data={"sweep_id": sweep_id, "status": "started", "preset": preset_name},
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.get(
    "/status/{sweep_id}",
    summary="Get sweep progress status",
    description="Get the current progress status of a running sweep.",
)
async def get_sweep_status(sweep_id: str) -> Any:
    """Get the current progress status of a sweep."""
    if sweep_id not in _active_sweeps:
        raise HTTPException(status_code=404, detail=f"Sweep {sweep_id} not found")

    # Get progress from engine if available
    status = _active_sweeps.get(sweep_id, "unknown")

    return ApiResponse(
        data={
            "sweep_id": sweep_id,
            "status": status,
        },
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.get(
    "/result/{sweep_id}",
    summary="Get filter sweep results",
    description="Retrieve the results of a completed filter sweep.",
)
async def get_sweep_results(sweep_id: str) -> Any:
    """Get the results of a completed filter sweep."""
    if sweep_id not in _sweep_results:
        # Check if still running
        if sweep_id in _active_sweeps:
            return ApiResponse(
                data={"status": _active_sweeps[sweep_id], "message": "Sweep still running"},
                meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
            )
        raise HTTPException(status_code=404, detail=f"Sweep results {sweep_id} not found")

    result = _sweep_results[sweep_id]
    return ApiResponse(
        data=result.model_dump(),
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.get(
    "/list",
    summary="List all completed sweeps",
    description="List all completed filter sweeps with summary info.",
)
async def list_sweeps() -> Any:
    """List all completed sweeps."""
    sweeps = []
    for sweep_id, result in _sweep_results.items():
        sweeps.append({
            "sweep_id": sweep_id,
            "name": result.name,
            "screen_name": result.screen_name,
            "status": result.status,
            "total_combinations": result.total_combinations,
            "valid_results": result.valid_results,
            "failed_results": result.failed_results,
            "best_expectancy": result.best_by_expectancy.get("expectancy") if result.best_by_expectancy else None,
            "best_sharpe": result.best_by_sharpe.get("sharpe") if result.best_by_sharpe else None,
            "created_at": result.created_at,
            "duration_ms": result.duration_ms,
        })

    # Sort by created_at descending
    sweeps.sort(key=lambda x: x["created_at"], reverse=True)

    return ApiResponse(data=sweeps, meta=MetaInfo())


@router.delete(
    "/{sweep_id}",
    summary="Delete sweep results",
    description="Delete sweep results from memory.",
    status_code=200,
)
async def delete_sweep(sweep_id: str) -> Any:
    """Delete sweep results."""
    if sweep_id in _sweep_results:
        del _sweep_results[sweep_id]
    if sweep_id in _active_sweeps:
        del _active_sweeps[sweep_id]

    return ApiResponse(data={"message": f"Sweep {sweep_id} deleted"}, meta=MetaInfo())


# Export for internal use
def get_sweep_result(sweep_id: str) -> FilterSweepSummary | None:
    """Get sweep result by ID (for internal use)."""
    return _sweep_results.get(sweep_id)