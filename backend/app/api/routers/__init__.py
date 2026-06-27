"""API routers package."""

from backend.app.api.routers.backtest import router as backtest_router
from backend.app.api.routers.data import router as data_router
from backend.app.api.routers.health import router as health_router
from backend.app.api.routers.risk import router as risk_router
from backend.app.api.routers.tv_screener import router as tv_screener_router

__all__ = [
    "backtest_router",
    "data_router",
    "health_router",
    "risk_router",
    "tv_screener_router",
]
