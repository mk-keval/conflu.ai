"""FastAPI dependency injection providers for backend engines.

Each function provides an async instance of the corresponding engine.
Type aliases are provided for cleaner route signatures.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from backend.app.infrastructure.backtest.engine import BacktestEngine
from backend.app.infrastructure.risk.engine import RiskEngine
from backend.app.infrastructure.screener.cache import IndicatorCache
from backend.app.infrastructure.screener.engine import ScreenEngine
from backend.app.infrastructure.screener.screen_replay import ScreenReplay
from backend.app.infrastructure.screener.sharing import ScreenSharing


async def get_screen_engine() -> ScreenEngine:
    """Dependency that provides a ScreenEngine instance."""
    return ScreenEngine()


async def get_backtest_engine() -> BacktestEngine:
    """Dependency that provides a BacktestEngine instance."""
    return BacktestEngine()


async def get_risk_engine() -> RiskEngine:
    """Dependency that provides a RiskEngine instance."""
    return RiskEngine()


async def get_indicator_cache() -> IndicatorCache:
    """Dependency that provides an IndicatorCache instance."""
    return IndicatorCache()


async def get_screen_replay() -> ScreenReplay:
    """Dependency that provides a ScreenReplay instance."""
    return ScreenReplay()


async def get_screen_sharing() -> ScreenSharing:
    """Dependency that provides a ScreenSharing instance."""
    return ScreenSharing()


# Typed Annotated aliases for cleaner route signatures
ScreenEngineDep = Annotated[ScreenEngine, Depends(get_screen_engine)]
BacktestEngineDep = Annotated[BacktestEngine, Depends(get_backtest_engine)]
RiskEngineDep = Annotated[RiskEngine, Depends(get_risk_engine)]
IndicatorCacheDep = Annotated[IndicatorCache, Depends(get_indicator_cache)]
ScreenReplayDep = Annotated[ScreenReplay, Depends(get_screen_replay)]
ScreenSharingDep = Annotated[ScreenSharing, Depends(get_screen_sharing)]
