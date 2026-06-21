"""Backtest API router.

- POST /api/v1/backtest             — Run a backtest
- POST /api/v1/backtest/optimize    — Walk-forward optimization
- POST /api/v1/backtest/monte-carlo — Monte Carlo simulation
- GET  /api/v1/backtest/{run_id}    — Retrieve stored backtest result
- GET  /api/v1/backtest/{run_id}/trades  — Retrieve trades for a run
- GET  /api/v1/backtest/{run_id}/equity  — Retrieve equity curve
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter

from backend.app.api.dependencies import BacktestEngineDep
from backend.app.api.exceptions import NotFoundError
from backend.app.api.schemas import (
    ApiResponse, BacktestRequest, BacktestResultData, CompareRequest, MetaInfo,
    OptimizeRequest, OptimizeResponse, RegimeRequest, ReportRequest, ReportResponse,
)
from backend.app.core.database import get_db
from backend.app.core.logging import get_logger
from backend.app.infrastructure.backtest.comparison import StrategyComparator
from backend.app.infrastructure.backtest.models import BacktestRunConfig, BacktestRunRecord, ComparisonConfig, OptimizationSearchSpace
from backend.app.infrastructure.backtest.optimization import BacktestOptimizer
from backend.app.infrastructure.backtest.regimes import RegimeDetector
from backend.app.infrastructure.backtest.reporting import ReportGenerator
from backend.app.infrastructure.backtest.models import ReportConfig as ReportCfgModel

router = APIRouter(prefix="/backtest", tags=["backtest"])
log = get_logger("conflu.api.backtest")


def _request_to_config(request: BacktestRequest, run_id: str) -> BacktestRunConfig:
    """Convert API request to BacktestRunConfig."""
    return BacktestRunConfig(
        run_id=run_id,
        symbols=request.symbols,
        start=request.start,
        end=request.end,
        initial_cash=request.initial_cash,
        fees_bps=request.fees_bps,
        slippage_bps=request.slippage_bps,
        position_sizing=request.position_sizing,
        sizing_params=request.sizing_params,
    )


@router.post(
    "",
    summary="Run a backtest",
    description="Execute a backtest simulation for the specified symbols and date range. "
    "Supports position sizing methods: fixed, ATR-based, or Kelly.",
    response_description="Backtest results with metrics and metadata",
    status_code=200,
)
async def run_backtest(
    request: BacktestRequest,
    engine: BacktestEngineDep,
) -> Any:
    """Run a backtest simulation."""
    run_id = str(uuid4())
    config = _request_to_config(request, run_id)

    record = await engine.run(config)

    return ApiResponse(
        data=BacktestResultData(
            run_id=record.run_id,
            symbol=record.symbol,
            timeframe=record.timeframe,
            metrics=record.metrics,
            trades_count=record.trades_count,
            duration_ms=record.duration_ms,
        ),
        meta=MetaInfo(
            timestamp=datetime.now(UTC).isoformat(),
            duration_ms=record.duration_ms,
        ),
    )


@router.post(
    "/optimize",
    summary="Run walk-forward optimization",
    description="Run a walk-forward optimization over the parameter grid to find "
    "the best-performing parameter set for the given symbols and date range.",
    status_code=200,
)
async def optimize_backtest(
    request: BacktestRequest,
    engine: BacktestEngineDep,
) -> Any:
    """Run walk-forward optimization."""
    run_id = str(uuid4())
    config = _request_to_config(request, run_id)

    result = await engine.run_walk_forward(config)

    return ApiResponse(
        data=result.model_dump(),
        meta=MetaInfo(
            timestamp=datetime.now(UTC).isoformat(),
        ),
    )


@router.post(
    "/monte-carlo",
    summary="Run Monte Carlo simulation",
    description="Run a Monte Carlo simulation to assess the statistical distribution "
    "of potential outcomes for the given backtest configuration.",
    status_code=200,
)
async def monte_carlo_backtest(
    request: BacktestRequest,
    engine: BacktestEngineDep,
) -> Any:
    """Run Monte Carlo simulation."""
    run_id = str(uuid4())
    config = _request_to_config(request, run_id)

    result = await engine.run_monte_carlo(config)

    return ApiResponse(
        data=result.model_dump(),
        meta=MetaInfo(
            timestamp=datetime.now(UTC).isoformat(),
        ),
    )


@router.get(
    "/{run_id}",
    summary="Get backtest result",
    description="Retrieve a stored backtest result by run ID.",
    status_code=200,
)
async def get_backtest(run_id: str) -> Any:
    """Retrieve a stored backtest result."""
    with get_db(read_only=True) as con:
        row = con.sql(
            "SELECT * FROM backtest_results WHERE run_id = ?",
            params=[run_id],
        ).fetchone()

    if not row:
        raise NotFoundError("BacktestRun", run_id)

    return ApiResponse(
        data=dict(row),
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.get(
    "/{run_id}/trades",
    summary="Get backtest trades",
    description="Retrieve the trade ledger for a completed backtest run.",
    status_code=200,
)
async def get_backtest_trades(run_id: str) -> Any:
    """Retrieve trades for a backtest run."""
    with get_db(read_only=True) as con:
        rows = con.sql(
            "SELECT * FROM backtest_trades WHERE run_id = ? ORDER BY entry_time",
            params=[run_id],
        ).fetchall()

    if not rows:
        raise NotFoundError("BacktestRun", run_id)

    return ApiResponse(
        data=[dict(r) for r in rows],
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.get(
    "/{run_id}/equity",
    summary="Get backtest equity curve",
    description="Retrieve the equity curve for a completed backtest run.",
    status_code=200,
)
async def get_backtest_equity(run_id: str) -> Any:
    """Retrieve equity curve for a backtest run."""
    with get_db(read_only=True) as con:
        rows = con.sql(
            "SELECT timestamp, equity FROM backtest_equity "
            "WHERE run_id = ? ORDER BY timestamp",
            params=[run_id],
        ).fetchall()

    if not rows:
        raise NotFoundError("BacktestRun", run_id)

    return ApiResponse(
        data=[dict(r) for r in rows],
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


# ── Phase 9: Advanced Backtest Endpoints ──


@router.post("/optimize-v2", summary="Run parameter optimization", status_code=200)
async def optimize_backtest_v2(request: OptimizeRequest, engine: BacktestEngineDep) -> Any:
    """Run parameter optimization with grid/random/bayesian methods."""
    import uuid
    optimizer = BacktestOptimizer(engine=engine)
    run_id = str(uuid.uuid4())
    base_config = BacktestRunConfig(
        run_id=run_id, symbols=request.symbols, start=request.start, end=request.end,
        initial_cash=request.initial_cash, fees_bps=request.fees_bps,
        slippage_bps=request.slippage_bps, position_sizing=request.position_sizing,
        sizing_params=request.sizing_params,
    )
    search_space = OptimizationSearchSpace(
        method=request.method, grid_params=request.grid_params,
        param_distributions=request.param_distributions, objectives=request.objectives,
        max_trials=request.max_trials, timeout_s=request.timeout_s,
        n_jobs=request.n_jobs, early_stopping=request.early_stopping,
    )
    result = await optimizer.optimize(base_config, search_space)
    return ApiResponse(
        data=OptimizeResponse(
            study_id=result.study_id, symbol=result.symbol, method=result.method,
            best_params=result.best_params, best_objectives=result.best_objectives,
            n_trials=result.n_trials, duration_ms=result.duration_ms,
            param_importance=result.param_importance,
        ),
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat(), duration_ms=result.duration_ms),
    )


@router.post("/regimes", summary="Detect market regimes", status_code=200)
async def detect_regimes(request: RegimeRequest) -> Any:
    """Detect market regimes for a symbol/date range."""
    import pandas as pd
    detector = RegimeDetector()
    with get_db(read_only=True) as con:
        placeholders = ",".join("?" * len(request.symbols))
        result = con.sql(
            f"SELECT symbol, timestamp, open, high, low, close, volume FROM ohlcv WHERE symbol IN ({placeholders}) AND timestamp >= ? AND timestamp <= ? ORDER BY timestamp",
            params=[*request.symbols, request.start, request.end],
        ).fetchdf()
    if result.empty:
        return ApiResponse(data=[], meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()))
    result.set_index("timestamp", inplace=True)
    result.index = pd.DatetimeIndex(result.index)
    from backend.app.infrastructure.backtest.models import RegimeConfig as RegimeCfg
    regime_result = detector.detect(result, RegimeCfg(method=request.method, n_states=request.n_states, window_days=request.window_days))
    return ApiResponse(data=regime_result.model_dump(), meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()))


@router.post("/{run_id}/report", summary="Generate backtest report", status_code=200)
async def generate_report(run_id: str, request: ReportRequest) -> Any:
    """Generate a report for a backtest run."""
    with get_db(read_only=True) as con:
        row = con.sql("SELECT * FROM backtest_results WHERE run_id = ?", params=[run_id]).fetchone()
    if not row:
        raise NotFoundError("BacktestRun", run_id)

    import json
    from backend.app.domain.models import Metrics
    metrics_json = row["metrics_json"] if row.get("metrics_json") else "{}"
    metrics_data = json.loads(metrics_json) if isinstance(metrics_json, str) else (metrics_json or {})

    run_record = BacktestRunRecord(
        run_id=row["run_id"], config_hash=row["config_hash"], symbol=row["symbol"],
        timeframe=row["timeframe"], start_date=row["start_date"], end_date=row["end_date"],
        initial_cash=row["initial_cash"], position_sizing=row["position_sizing"],
        metrics=Metrics(**{k: v for k, v in metrics_data.items() if k in Metrics.model_fields}),
        duration_ms=row.get("duration_ms", 0.0), trades_count=0,
    )

    extra_data: dict[str, Any] = {}
    with get_db(read_only=True) as con:
        equity_rows = con.sql("SELECT timestamp, equity, drawdown FROM backtest_equity_curves WHERE run_id = ? ORDER BY timestamp", params=[run_id]).fetchall()
        if equity_rows:
            extra_data["equity_curve"] = [{"timestamp": str(r[0]), "equity": r[1], "drawdown": r[2] if len(r) > 2 else 0} for r in equity_rows]
        trade_rows = con.sql("SELECT * FROM backtest_trades WHERE run_id = ? ORDER BY entry_time", params=[run_id]).fetchall()
        if trade_rows:
            extra_data["trades"] = [dict(r) for r in trade_rows]

    generator = ReportGenerator()
    results = generator.generate(run_record, ReportCfgModel(
        formats=request.formats, template_name=request.template,
        include_equity_curve=request.include_equity_curve, include_drawdown=request.include_drawdown,
        include_trade_analysis=request.include_trade_analysis, include_regime_analysis=request.include_regime_analysis,
        include_parameter_sensitivity=request.include_parameter_sensitivity,
    ), extra_data)

    formats_list = [{"format": r.format, "download_url": f"/api/v1/backtest/reports/{r.report_id}.{r.format}"} for r in results if r.report_path]
    return ApiResponse(
        data=ReportResponse(report_id=results[0].report_id if results else "", formats=formats_list, size_bytes=sum(r.size_bytes for r in results), created_at=datetime.now(UTC).isoformat()),
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.post("/compare", summary="Compare backtest runs", status_code=200)
async def compare_backtests(request: CompareRequest) -> Any:
    """Compare multiple backtest runs."""
    comparator = StrategyComparator()
    result = await comparator.compare(ComparisonConfig(
        run_ids=request.run_ids, labels=request.labels,
        include_significance=request.include_significance, bootstrap_samples=request.bootstrap_samples,
    ))
    return ApiResponse(data=result.model_dump(), meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()))
