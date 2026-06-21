"""Router package — import and export all API routers."""

from backend.app.api.routers.alerts import router as alerts_router
from backend.app.api.routers.backtest import router as backtest_router
from backend.app.api.routers.data import router as data_router
from backend.app.api.routers.health import router as health_router
from backend.app.api.routers.replay import router as replay_router
from backend.app.api.routers.risk import router as risk_router
from backend.app.api.routers.screen_crud import router as screen_crud_router
from backend.app.api.routers.screener import router as screener_router
from backend.app.api.routers.sharing import router as sharing_router

__all__ = [
    "alerts_router",
    "health_router",
    "screener_router",
    "screen_crud_router",
    "sharing_router",
    "replay_router",
    "backtest_router",
    "data_router",
    "risk_router",
]
