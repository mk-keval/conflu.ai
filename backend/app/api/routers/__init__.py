"""API routers package."""

from backend.app.api.routers.backtest import router as backtest_router
from backend.app.api.routers.data import router as data_router
from backend.app.api.routers.health import router as health_router
from backend.app.api.routers.risk import router as risk_router
from backend.app.api.routers.regime import router as regime_router
from backend.app.api.routers.sector_rotation import router as sector_rotation_router
from backend.app.api.routers.ticker_analysis import router as ticker_analysis_router
from backend.app.api.routers.tv_screener import router as tv_screener_router

__all__ = [
    "backtest_router",
    "data_router",
    "health_router",
    "regime_router",
    "risk_router",
    "sector_rotation_router",
    "ticker_analysis_router",
    "tv_screener_router",
]
