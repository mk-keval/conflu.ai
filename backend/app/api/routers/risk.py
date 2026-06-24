"""Risk management API router.

- GET  /api/v1/risk/{symbol}          — Beta for a single symbol
- GET  /api/v1/risk/beta              — Beta for multiple symbols
- GET  /api/v1/risk/correlation       — Correlation matrix
- GET  /api/v1/risk/var               — VaR/CVaR
- POST /api/v1/risk/kelly             — Kelly optimization
- POST /api/v1/risk/position-size     — Position sizing
- GET  /api/v1/risk/summary           — Full risk assessment
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from backend.app.api.dependencies import RiskEngineDep
from backend.app.api.schemas import (
    ApiResponse,
    MetaInfo,
    RiskBetaRequest,
    RiskCorrelationRequest,
    RiskKellyRequest,
    RiskPositionSizeRequest,
    RiskSummaryRequest,
    RiskVarRequest,
)
from backend.app.core.logging import get_logger

router = APIRouter(prefix="/risk", tags=["risk"])
log = get_logger("conflu.api.risk")


@router.get(
    "/{symbol}",
    summary="Get symbol beta",
    description="Get beta and tracking error for a single symbol vs a benchmark.",
    status_code=200,
)
async def get_symbol_beta(
    symbol: str,
    benchmark: str | None = None,
    window: int = 60,
    engine: RiskEngineDep = None,
) -> Any:
    """Get beta for a single symbol."""
    results = await engine.compute_beta(symbols=[symbol], benchmark=benchmark, window=window)

    return ApiResponse(
        data=results[0] if results else {},
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.get(
    "/beta",
    summary="Get multi-symbol beta",
    description="Get beta values for multiple symbols vs a benchmark.",
    status_code=200,
)
async def get_beta(
    params: Annotated[RiskBetaRequest, Depends()],
    engine: RiskEngineDep = None,
) -> Any:
    """Get beta for multiple symbols."""
    results = await engine.compute_beta(
        symbols=params.symbols,
        benchmark=params.benchmark,
        window=params.window,
    )

    return ApiResponse(
        data=results,
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.get(
    "/correlation",
    summary="Get correlation matrix",
    description="Get the Pearson correlation matrix for a list of symbols.",
    status_code=200,
)
async def get_correlation(
    params: Annotated[RiskCorrelationRequest, Depends()],
    engine: RiskEngineDep = None,
) -> Any:
    """Get correlation matrix."""
    result = await engine.compute_correlation(
        symbols=params.symbols,
        window=params.window,
        group_by=params.group_by,
    )

    return ApiResponse(
        data=result,
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.get(
    "/var",
    summary="Get VaR/CVaR",
    description="Compute Value at Risk and Conditional VaR for a portfolio of symbols "
    "using historical, parametric, or Monte Carlo methods.",
    status_code=200,
)
async def get_var(
    params: Annotated[RiskVarRequest, Depends()],
    engine: RiskEngineDep = None,
) -> Any:
    """Get VaR/CVaR for a portfolio."""
    portfolio_id = f"var_{'_'.join(params.symbols[:3])}"
    result = await engine.compute_var(
        portfolio_id=portfolio_id,
        returns=None,
        method=params.method,
        confidence=params.confidence,
        horizon=params.horizon,
    )

    return ApiResponse(
        data=result,
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.post(
    "/kelly",
    summary="Compute Kelly optimization",
    description="Compute optimal position sizes using the Kelly Criterion based on a backtest run's trade statistics.",
    status_code=200,
)
async def post_kelly(
    request: RiskKellyRequest,
    engine: RiskEngineDep = None,
) -> Any:
    """Compute Kelly optimization from backtest results."""
    result = await engine.compute_kelly(
        backtest_run_id=request.backtest_run_id,
        max_dd=request.max_dd_target,
    )

    return ApiResponse(
        data=result,
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.post(
    "/position-size",
    summary="Compute position sizes",
    description="Compute risk-adjusted position sizes using ATR, Kelly, or fixed methods.",
    status_code=200,
)
async def post_position_size(
    request: RiskPositionSizeRequest,
    engine: RiskEngineDep = None,
) -> Any:
    """Compute position sizes."""
    # Load OHLCV data for position sizing
    from backend.app.core.database import get_db

    with get_db(read_only=True) as con:
        placeholders = ",".join("?" * len(request.symbols))
        close_data = con.sql(
            f"""
            SELECT symbol, timestamp, close
            FROM ohlcv
            WHERE symbol IN ({placeholders}) AND timeframe = '1D'
            ORDER BY symbol, timestamp DESC
            LIMIT 500
            """,
            params=[*request.symbols],
        ).fetchdf()

    if close_data.empty:
        return ApiResponse(
            data={"sizes": {}, "method": request.method},
            meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
        )

    import pandas as pd

    # Pivot to wide format for engine
    close_pivot = close_data.pivot(index="timestamp", columns="symbol", values="close").dropna()

    # Create dummy entries (all True) — last bar entry signal
    entries = pd.DataFrame(True, index=close_pivot.index, columns=close_pivot.columns)

    result = await engine.compute_position_size(
        close=close_pivot,
        entries=entries,
        method=request.method,
        cash=request.cash,
        params=request.params,
    )

    sizes: dict[str, float] = {}
    if result is not None and not result.empty:
        last_row = result.iloc[-1]
        for col in result.columns:
            sizes[str(col)] = float(last_row[col])

    return ApiResponse(
        data={"sizes": sizes, "method": request.method, "cash": request.cash},
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )


@router.get(
    "/summary",
    summary="Get full risk assessment",
    description="Get a comprehensive risk assessment for a portfolio including VaR, beta, correlation, and risk score.",
    status_code=200,
)
async def get_risk_summary(
    params: Annotated[RiskSummaryRequest, Depends()],
    engine: RiskEngineDep = None,
) -> Any:
    """Get full portfolio risk assessment."""
    result = await engine.analyze_portfolio(
        portfolio_id=params.portfolio_id,
        symbols=params.symbols or [],
    )

    return ApiResponse(
        data=result.model_dump() if hasattr(result, "model_dump") else result,
        meta=MetaInfo(timestamp=datetime.now(UTC).isoformat()),
    )
