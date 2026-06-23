"""FastAPI application factory for conflu.ai API.

Creates the FastAPI application with all routers, middleware, exception handlers,
WebSocket support, and observability instrumentation wired together.

Usage:
    uvicorn backend.app.api.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.core.database import initialize_database
from backend.app.core.logging import configure_logging, get_logger

log = get_logger("conflu.api.main")

# ── OpenAPI Tags Metadata ──

tags_metadata = [
    {
        "name": "health",
        "description": "Liveness, readiness, and dependency checks",
    },
    {
        "name": "screener",
        "description": "Multi-timeframe technical screener — run filter pipelines across "
        "asset classes",
    },
    {
        "name": "backtest",
        "description": "Strategy backtesting — vectorized simulation, walk-forward "
        "optimization, Monte Carlo",
    },
    {
        "name": "data",
        "description": "OHLCV and indicator data retrieval",
    },
    {
        "name": "risk",
        "description": "Risk management — VaR, beta, correlation, Kelly, position sizing",
    },
    {
        "name": "streaming",
        "description": "WebSocket real-time streaming — price, indicators, signals",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifecycle: startup resource initialization, shutdown teardown.

    Startup:
    1. Configure structlog
    2. Initialize DuckDB tables (idempotent)
    3. Start WebSocket background tasks
    4. Initialize Prometheus instrumentator (if enabled)
    5. Initialize OpenTelemetry (if configured)

    Shutdown:
    1. Close WebSocket connections
    2. Shut down OpenTelemetry
    """
    # ── Startup ──
    log.info("app_startup_begin")

    configure_logging(
        log_level=settings.core.log_level, log_json=settings.core.log_json
    )
    initialize_database()

    # Initialize OpenTelemetry
    if settings.api.otel_exporter_otlp_endpoint:
        from backend.app.api.observability import setup_opentelemetry

        setup_opentelemetry(app)

    # Start WebSocket background streams
    from backend.app.api.ws.manager import ws_manager

    ws_manager.start_background_tasks(app)

    log.info("app_startup_complete")

    yield

    # ── Shutdown ──
    # Close WebSocket connections
    await ws_manager.close_all()

    # Shut down OpenTelemetry
    if settings.api.otel_exporter_otlp_endpoint:
        try:
            from opentelemetry import trace

            trace.get_tracer_provider().shutdown()
        except Exception:
            log.exception("otel_shutdown_error")

    log.info("app_shutdown_complete")


def create_app() -> FastAPI:
    """Application factory.

    Returns a fully configured FastAPI instance with all routers, middleware,
    exception handlers, and WebSocket support.

    Middleware order (first added = outermost on request):
    1. CORSMiddleware
    2. RequestLogMiddleware (correlation ID, timing, logging)
    3. RateLimitMiddleware (token bucket)
    4. APIKeyMiddleware (X-API-Key header)
    5. PrometheusMiddleware (metrics) - added conditionally
    """
    app = FastAPI(
        title="conflu.ai API",
        description="Multi-asset trading platform — screener, backtest, risk analysis, "
        "and real-time data streaming",
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
        openapi_tags=tags_metadata,
    )

    # ── Initialize Prometheus instrumentation (must be before middleware) ──
    if settings.api.prometheus_enabled:
        from backend.app.api.observability import setup_prometheus

        setup_prometheus(app)

    # ── Middleware (order matters: first added = outermost) ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=settings.api.cors_allow_credentials,
        allow_methods=settings.api.cors_allow_methods,
        allow_headers=settings.api.cors_allow_headers,
    )

    from backend.app.api.middleware import (
        APIKeyMiddleware,
        RateLimitMiddleware,
        RequestLogMiddleware,
    )

    app.add_middleware(RequestLogMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(APIKeyMiddleware)

    # ── Routers ──
    from backend.app.api.routers import (
        alerts_router,
        backtest_router,
        data_router,
        health_router,
        replay_router,
        risk_router,
        screen_crud_router,
        screener_router,
        sharing_router,
    )

    app.include_router(health_router)
    app.include_router(screener_router, prefix="/api/v1")
    app.include_router(screen_crud_router, prefix="/api/v1")
    app.include_router(alerts_router, prefix="/api/v1")
    app.include_router(sharing_router, prefix="/api/v1")
    app.include_router(replay_router, prefix="/api/v1")
    app.include_router(backtest_router, prefix="/api/v1")
    app.include_router(data_router, prefix="/api/v1")
    app.include_router(risk_router, prefix="/api/v1")

    # ── WebSocket ──
    from backend.app.api.ws.handler import register_ws_routes

    register_ws_routes(app)

    # ── Exception handlers ──
    from backend.app.api.exceptions import register_exception_handlers

    register_exception_handlers(app)

    log.info("app_created", title=app.title, version=app.version)
    return app


# Module-level FastAPI instance for uvicorn
app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=True,
    )
