"""FastAPI dependency injection providers for backend engines.

Each function provides an async instance of the corresponding engine.
Type aliases are provided for cleaner route signatures.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends


async def get_screen_engine() -> object:
    """Dependency that provides a ScreenEngine instance."""
    from backend.app.infrastructure.screener.engine import ScreenEngine
    return ScreenEngine()


async def get_backtest_engine() -> object:
    """Dependency that provides a BacktestEngine instance."""
    from backend.app.infrastructure.backtest.engine import BacktestEngine
    return BacktestEngine()


async def get_risk_engine() -> object:
    """Dependency that provides a RiskEngine instance."""
    from backend.app.infrastructure.risk.engine import RiskEngine
    return RiskEngine()


async def get_indicator_cache() -> object:
    """Dependency that provides an IndicatorCache instance."""
    from backend.app.infrastructure.screener.cache import IndicatorCache
    return IndicatorCache()


async def get_screen_replay() -> object:
    """Dependency that provides a ScreenReplay instance."""
    from backend.app.infrastructure.screener.screen_replay import ScreenReplay
    return ScreenReplay()


async def get_screen_sharing() -> object:
    """Dependency that provides a ScreenSharing instance."""
    from backend.app.infrastructure.screener.sharing import ScreenSharing
    return ScreenSharing()


# Typed Annotated aliases for cleaner route signatures
ScreenEngineDep = Annotated[object, Depends(get_screen_engine)]
BacktestEngineDep = Annotated[object, Depends(get_backtest_engine)]
RiskEngineDep = Annotated[object, Depends(get_risk_engine)]
IndicatorCacheDep = Annotated[object, Depends(get_indicator_cache)]
ScreenReplayDep = Annotated[object, Depends(get_screen_replay)]
ScreenSharingDep = Annotated[object, Depends(get_screen_sharing)]
