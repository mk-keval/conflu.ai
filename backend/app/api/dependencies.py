"""FastAPI dependency injection providers for backend engines.

Each function provides an async instance of the corresponding engine.
Type aliases are provided for cleaner route signatures.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends


async def get_backtest_engine() -> object:
    """Dependency that provides a BacktestEngine instance."""
    from backend.app.infrastructure.backtest.engine import BacktestEngine
    return BacktestEngine()


async def get_risk_engine() -> object:
    """Dependency that provides a RiskEngine instance."""
    from backend.app.infrastructure.risk.engine import RiskEngine
    return RiskEngine()


async def get_ticker_analysis_engine() -> object:
    """Dependency that provides a TickerAnalysisService instance."""
    from backend.app.domain.ticker_analysis.orchestrator import TickerAnalysisService
    return TickerAnalysisService()


# Typed Annotated aliases for cleaner route signatures
BacktestEngineDep = Annotated[object, Depends(get_backtest_engine)]
RiskEngineDep = Annotated[object, Depends(get_risk_engine)]
TickerAnalysisDep = Annotated[object, Depends(get_ticker_analysis_engine)]
