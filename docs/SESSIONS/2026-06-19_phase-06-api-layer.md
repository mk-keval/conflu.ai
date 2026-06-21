# Session: Phase 6 — API Layer

**Date:** 2026-06-19
**Branch:** feat/conflu-ai-platform

## Work Done

### Wave 1: Foundation & Configuration
- Extended `core/config.py` with `APISettings` — rate limits (per-endpoint groups), API keys, JWT, CORS, OTel, Prometheus, WS config
- Created `api/schemas.py` — ApiResponse/ApiErrorResponse envelopes, ScreenRequest, BacktestRequest, IndicatorQueryParams, OHLCVQueryParams, all Risk*Request models
- Created `api/exceptions.py` — ApiError hierarchy (NotFoundError, ValidationError, RateLimitError, EngineError) + `register_exception_handlers()`
- Created `api/middleware.py` — TokenBucket, RequestLogMiddleware (correlation ID + timing), RateLimitMiddleware (per-endpoint groups), APIKeyMiddleware
- Created `api/dependencies.py` — `get_screen_engine`, `get_backtest_engine`, `get_risk_engine`, `get_indicator_cache` + Annotated type aliases

### Wave 2: REST Routers
- **health**: GET /health (liveness), GET /health/ready (DuckDB connectivity)
- **screener**: POST /api/v1/screen with JSON/CSV/JSON export
- **backtest**: POST /api/v1/backtest, /optimize, /monte-carlo, GET /{run_id}, /{run_id}/trades, /{run_id}/equity
- **data**: GET /api/v1/indicators/{symbol}, /indicators (bulk), /data/{symbol}, /data/symbols
- **risk**: GET /beta, /correlation, /var, POST /kelly, /position-size, GET /summary

### Wave 3: WebSocket Layer
- `ws/manager.py` — WebSocketManager singleton (registry, subscriptions, broadcast, history, background loops)
- `ws/channels.py` — PriceChannel (market_data price streaming), IndicatorChannel (live indicator updates)
- `ws/handler.py` — /ws/stream endpoint with API key auth, reconnection, Prometheus metrics

### Wave 4: Observability & App Factory
- `api/observability.py` — Prometheus metrics (Histogram for request duration, Counter for errors) + OpenTelemetry tracing setup
- `api/main.py` — `create_app()` factory with all middleware/routers/lifespan wired
- `pyproject.toml` — Added prometheus-fastapi-instrumentator, opentelemetry optional deps, starlette mypy override

### Verification
- **ruff**: 53→0 errors (all lint rules satisfied)
- **mypy --strict**: Environment-dependent errors only (uninstalled local package, no FastAPI stubs in venv)
- **ARCHITECTURE.md**: Updated with API layer structure, data flow, and design decisions

## Files Created (18 new)
See `docs/ARCHITECTURE.md` for full directory tree.
