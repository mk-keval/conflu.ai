# Phase 6: API Layer — Research

**Created:** 2026-06-19
**Status:** Ready for planning
**Context:** Phase 1 foundation (DuckDB, config, logging, domain models) + Phase 2 ingestion (Parquet OHLCV, symbol metadata) + Phase 3 screener (ScreenEngine, ConnectionManager, filter pipeline) + Phase 4 backtest (BacktestEngine, TradeLedger, PositionSizer) + Phase 5 risk (RiskEngine, VaRCalculator, BetaHedger, CorrelationAnalyzer, KellyOptimizer) exist in completed state.

---

## Table of Contents

1. [Project State & Codebase Assessment](#1-project-state--codebase-assessment)
2. [Critical Architecture: What Phases 1-5 Already Built for Phase 6](#2-critical-architecture-what-phases-1-5-already-built-for-phase-6)
3. [FastAPI Application Factory Pattern](#3-fastapi-application-factory-pattern)
4. [API Module Structure & Routers](#4-api-module-structure--routers)
5. [REST Endpoints Design](#5-rest-endpoints-design)
   - 5.1 Core Endpoint Specifications
   - 5.2 Response Envelope Format
   - 5.3 Pydantic Request/Response Models
   - 5.4 OpenAPI Tags & Documentation
6. [WebSocket Streaming Architecture](#6-websocket-streaming-architecture)
   - 6.1 Single Multiplexed Endpoint
   - 6.2 Channel-Based Subscriptions
   - 6.3 Connection Manager Unification
   - 6.4 Message Format & Sequence Numbers
7. [Authentication & Authorization](#7-authentication--authorization)
   - 7.1 API Key Authentication
   - 7.2 Middleware Design
   - 7.3 Deferred: JWT/OAuth2
8. [Rate Limiting](#8-rate-limiting)
   - 8.1 slowapi vs Custom Token Bucket
   - 8.2 Per-Endpoint Rate Groups
   - 8.3 Rate Limit Headers
9. [Observability](#9-observability)
   - 9.1 Structured Logging with Correlation IDs
   - 9.2 Prometheus Metrics
   - 9.3 OpenTelemetry Tracing
   - 9.4 Health Endpoints
10. [Error Handling & Exception Middleware](#10-error-handling--exception-middleware)
11. [Configuration Extensions](#11-configuration-extensions)
12. [Module Design & File Structure](#12-module-design--file-structure)
13. [Dependencies & pyproject.toml](#13-dependencies--pyprojecttoml)
14. [Integration Points with Phases 1-5](#14-integration-points-with-phases-1-5)
15. [Risks & Mitigations](#15-risks--mitigations)
16. [Open Questions for Planning](#16-open-questions-for-planning)

---

## 1. Project State & Codebase Assessment

### Current State (after Phase 1-5 completion)

| Aspect | Status | Reusable for Phase 6 |
|--------|--------|----------------------|
| DuckDB connection mgr | ✅ `get_db()`, `get_db_async()` | Data endpoint reads |
| Config (`APISettings`) | ✅ Exists with host, port, cors_origins, rate_limit | Extend with auth, OTel, WS settings |
| Config (`AppSettings`) | ✅ Singleton `settings` instance | Central config source |
| Structured logging | ✅ `structlog`, `set_correlation_id()`, `get_logger()` | Correlation ID per request |
| Domain models | ✅ `OHLCV`, `Signal`, `Trade`, `Metrics`, `ScreenResult`, `BacktestConfig`, `RiskParams` | Base for API request/response models |
| `ScreenEngine` (Phase 3) | ✅ `screen()`, `screen_to_csv()`, `screen_to_json()` | REST screener endpoint |
| `ConnectionManager` (Phase 3) | ✅ Register, broadcast, resync, stream_loop | Refactor for unified WS |
| `BacktestEngine` (Phase 4) | ✅ `run()`, `run_walk_forward()`, `run_monte_carlo()` | REST backtest endpoint |
| `RiskEngine` (Phase 5) | ✅ `analyze_portfolio()`, `compute_beta()`, `compute_var()`, `compute_kelly()` | REST risk endpoints |
| `RiskStreamManager` (Phase 5) | ✅ Broadcast, background_updates, resync | Reuse for risk WS streaming |
| Indicator cache | ✅ `IndicatorCache.get_series()`, `get_latest()` | Indicator endpoint |
| `partition_path()` | ✅ Locate Parquet files | Data file download |
| FastAPI | ❌ **Not wired** — `backend/app/api/__init__.py` is empty | Greenfield |
| `main.py` | ❌ **Does not exist** — Docker expects `backend.app.api.main:app` | Must create |
| Auth | ❌ **Does not exist** — no middleware, no key store | Greenfield |
| Rate limiting | ❌ **Does not exist** — no middleware, no limiter | Greenfield |
| Prometheus metrics | ❌ **Not configured** — no `/metrics` endpoint | Greenfield |
| OpenTelemetry | ❌ **Not configured** — no tracer setup | Greenfield |
| Health endpoints | ❌ **Not implemented** — no `/health` or `/health/ready` | Greenfield |

### Key Insight: Phase 6 is a Thin Orchestration Layer

Phase 6 does NOT implement new business logic. It wraps existing Phase 1-5 capabilities behind HTTP/WS interfaces. The majority of the work is:

1. **FastAPI application factory** with lifespan, middleware, exception handlers
2. **REST routers** that delegate to existing engines
3. **WebSocket unification** — single endpoint with channel multiplexing
4. **Cross-cutting concerns** — auth, rate limiting, observability, error handling

### What Phase 6 Consumes from Prior Phases

| Capability | Source Phase | How Consumed |
|-----------|-------------|-------------|
| Screen execution | Phase 3 | `ScreenEngine().screen(config_name)` |
| Indicator values | Phase 3 | `IndicatorCache().get_series(name, timeframe, symbol)` |
| Backtest execution | Phase 4 | `BacktestEngine().run(config)` |
| Walk-forward optimization | Phase 4 | `BacktestEngine().run_walk_forward(config)` |
| Monte Carlo simulation | Phase 4 | `BacktestEngine().run_monte_carlo(config)` |
| OHLCV data | Phase 2 | Direct DuckDB query via `get_db()` |
| Beta computation | Phase 5 | `RiskEngine().compute_beta(symbols)` |
| Correlation matrix | Phase 5 | `RiskEngine().compute_correlation(symbols)` |
| VaR/CVaR | Phase 5 | `RiskEngine().compute_var(portfolio_id, ...)` |
| Kelly optimization | Phase 5 | `RiskEngine().compute_kelly(backtest_run_id)` |
| Position sizing | Phase 5 | `RiskEngine().compute_position_size(...)` |
| Risk portfolio analysis | Phase 5 | `RiskEngine().analyze_portfolio(portfolio_id, symbols)` |
| WebSocket connection mgr | Phase 3 | `ConnectionManager` — extend for unified stream |
| WebSocket risk streaming | Phase 5 | `RiskStreamManager` — compose into unified stream |
| DB connection | Phase 1 | `get_db()`, `get_db_async()` |
| Config | Phase 1 | `settings` singleton |
| Logging | Phase 1 | `get_logger()`, `set_correlation_id()` |

---

## 2. Critical Architecture: What Phases 1-5 Already Built for Phase 6

### 2.1 The ConnectionManager Pattern Exists Twice

Two WebSocket manager implementations exist:

| Aspect | `ConnectionManager` (Phase 3) | `RiskStreamManager` (Phase 5) |
|--------|------------------------------|-------------------------------|
| Location | `screener/streaming.py` | `risk/streaming.py` |
| Key concept | `screen_id` → clients | `portfolio_id` → clients |
| Sequence tracking | ✅ Per-screen | ✅ Per-portfolio |
| History replay | ✅ `resync()` with full snapshot fallback | ✅ `resync()` with full snapshot |
| Background loop | ✅ `stream_loop(screen_id)` — periodic eval | ✅ `start_background_updates(portfolio_id, coro)` |
| Delta updates | ✅ Full + delta support in message format | ✅ Multiple message types |
| Ping/pong | ✅ Via `handle_client_message()` | ✅ Via `handle_client_message()` |

**Decision D-23:** Reuse `ConnectionManager` from Phase 3 as the base for a unified `WebSocketManager`. Add `RiskStreamManager`'s pattern of on-demand coroutine updates (don't hard-code the engine call). The unified manager should:

```python
class WebSocketManager:
    """Unified WebSocket connection manager for Phase 6.
    
    Single endpoint: /ws/stream
    Channel-based subscription: price, indicator, signal, screener, risk, backtest
    Combines Phase 3 ConnectionManager + Phase 5 RiskStreamManager patterns.
    """
    
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._channels: dict[str, set[str]] = defaultdict(set)  # ws_id -> {channels}
        self._sequences: dict[str, int] = defaultdict(int)
        self._history: dict[str, list[dict]] = defaultdict(list)
        self._max_history = 100
        self._update_providers: dict[str, Callable] = {}  # channel -> update function
```

### 2.2 Existing Engines Are Ready for HTTP Consumption

Each engine already has async methods that can be called from route handlers:

```python
# Phase 3: ScreenEngine
engine = ScreenEngine()
result = await engine.screen("trend-follower")  # Returns ScreenRunResult

# Phase 4: BacktestEngine
engine = BacktestEngine()
record = await engine.run(config)  # Returns BacktestRunRecord

# Phase 5: RiskEngine  
engine = RiskEngine()
assessment = await engine.analyze_portfolio(pid, symbols)
beta = await engine.compute_beta(symbols)
var = await engine.compute_var(pid, returns, "historical", 0.95)
```

**Key insight:** No wrapping or adapters needed. The engines are already async and can be directly injected into route handlers. The Phase 6 routes simply:
1. Parse HTTP request → Pydantic model
2. Call engine method with model data
3. Wrap engine result in response envelope
4. Return JSON response

### 2.3 Domain Models Exist but Need API-Specific Additions

Existing models (`domain/models.py`) cover domain entities. For API layer, we need additional request/response schemas:

**Existing (reusable):**
- `ScreenResult` — screener output row
- `BacktestConfig` — backtest parameters
- `RiskParams` — risk parameters
- `Metrics` — performance metrics
- `Trade` — trade record
- `OHLCV` — OHLCV data point

**New models needed in `api/schemas.py`:**
- `ScreenRequest` — symbol list, timeframe override
- `BacktestRequest` — full backtest config from HTTP body
- `RiskVarRequest` — symbols, confidence, method, horizon
- `RiskBetaRequest` — symbols, benchmark, window
- `RiskCorrelationRequest` — symbols, window, group_by
- `RiskKellyRequest` — backtest_run_id, max_dd_target
- `WSSubscriptionRequest` — channels to subscribe
- `ApiErrorResponse` — standardized error format
- `HealthResponse` — liveness/readiness status
- `StreamChannel` — channel types enumeration

### 2.4 Docker Already Points to the Right Module

```yaml
# docker-compose.yml line 17-18:
command: >
  sh -c "... && uvicorn backend.app.api.main:app --host 0.0.0.0 --port 8000 --reload"
```

This means `backend/app/api/main.py` must create `app: FastAPI` and import/include all routers. Phase 6 must create:
- `backend/app/api/main.py` — FastAPI app factory
- `backend/app/api/routers/` — router modules
- `backend/app/api/schemas.py` — Pydantic request/response models
- `backend/app/api/dependencies.py` — FastAPI dependencies
- `backend/app/api/middleware.py` — custom middleware

### 2.5 APISettings Exists but Needs Extension

Current `APISettings` in `config.py`:

```python
class APISettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173"]
    rate_limit: int = 100  # req/min
```

Need to add (D-21):
- `rate_limit_ws: int = 10` — WebSocket messages/second
- `rate_limit_screener: int = 30` — screener endpoint stricter
- `rate_limit_backtest: int = 10` — backtest endpoint lenient
- `rate_limit_data: int = 200` — data endpoint moderate
- `api_keys: list[str] = Field(default_factory=list)` — valid API keys (D-10)
- `jwt_secret: str = ""` — JWT secret (deferred but define now)
- `jwt_algorithm: str = "HS256"` — JWT algorithm
- `jwt_expire_minutes: int = 60` — JWT token expiry
- `cors_allow_credentials: bool = True`
- `cors_allow_methods: list[str] = ["*"]`
- `cors_allow_headers: list[str] = ["*"]`
- `otel_service_name: str = "conflu-api"`
- `otel_exporter_otlp_endpoint: str = ""`  — OTLP endpoint (empty = disabled)
- `prometheus_enabled: bool = True`
- `log_request_body: bool = False` — don't log bodies in production
- `health_db_timeout_s: float = 5.0`
- `ws_max_connections: int = 1000`
- `ws_ping_interval_s: float = 30.0`
- `ws_pong_timeout_s: float = 10.0`

---

## 3. FastAPI Application Factory Pattern

### 3.1 Lifespan Pattern (Modern FastAPI)

FastAPI deprecated `startup`/`shutdown` events in favor of the `lifespan` async context manager. Phase 6 must use this pattern.

```python
# backend/app/api/main.py
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.core.database import initialize_database
from backend.app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifecycle: startup resources, shutdown teardown.
    
    Startup:
    1. Configure structlog
    2. Initialize DuckDB tables (idempotent)
    3. Start WebSocket background tasks
    4. Initialize OpenTelemetry (if configured)
    5. Initialize Prometheus instrumentator
    
    Shutdown:
    1. Close WebSocket connections
    2. Shut down OpenTelemetry
    3. Close any background tasks
    """
    # ── Startup ──
    configure_logging(log_level=settings.core.log_level, log_json=settings.core.log_json)
    initialize_database()
    
    # Initialize Prometheus instrumentator
    if settings.api.prometheus_enabled:
        from backend.app.api.observability import setup_prometheus
        setup_prometheus(app)
    
    # Initialize OpenTelemetry
    if settings.api.otel_exporter_otlp_endpoint:
        from backend.app.api.observability import setup_opentelemetry
        setup_opentelemetry(app)
    
    # Start WebSocket background streams
    from backend.app.api.ws.manager import ws_manager
    ws_manager.start_background_tasks(app)
    
    yield
    
    # ── Shutdown ──
    # Close WebSocket connections
    await ws_manager.close_all()
    
    # Shut down OpenTelemetry
    if settings.api.otel_exporter_otlp_endpoint:
        from opentelemetry import trace
        trace.get_tracer_provider().shutdown()


def create_app() -> FastAPI:
    """Application factory.
    
    Returns configured FastAPI instance with all routers and middleware.
    """
    app = FastAPI(
        title="conflu.ai API",
        description="Multi-asset trading platform — screener, backtest, risk analysis, and real-time data streaming",
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
        # Default exception handlers overridden in middleware
    )
    
    # ── Middleware (order matters: first added = outermost) ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=settings.api.cors_allow_credentials,
        allow_methods=settings.api.cors_allow_methods,
        allow_headers=settings.api.cors_allow_headers,
    )
    
    # Custom middleware
    from backend.app.api.middleware import RequestLogMiddleware, RateLimitMiddleware
    app.add_middleware(RequestLogMiddleware)
    app.add_middleware(RateLimitMiddleware)
    
    # ── Routers ──
    from backend.app.api.routers import (
        backtest_router,
        data_router,
        health_router,
        risk_router,
        screener_router,
    )
    app.include_router(health_router)
    app.include_router(screener_router, prefix="/api/v1")
    app.include_router(backtest_router, prefix="/api/v1")
    app.include_router(data_router, prefix="/api/v1")
    app.include_router(risk_router, prefix="/api/v1")
    
    # ── WebSocket ──
    from backend.app.api.ws.handler import register_ws_routes
    register_ws_routes(app)
    
    # ── Exception handlers ──
    from backend.app.api.exceptions import register_exception_handlers
    register_exception_handlers(app)
    
    return app


app = create_app()
```

### 3.2 Middleware Ordering

Middleware executes in reverse order of registration (outermost first on request, outermost last on response):

```
Request flow:
  CORSMiddleware (outermost)
  → RequestLogMiddleware (correlation ID, timing)
  → RateLimitMiddleware (token bucket check)
  → AuthMiddleware (API key check)
  → Route handler
    
Response flow:
  Route handler
  → AuthMiddleware
  → RateLimitMiddleware (add rate limit headers)
  → RequestLogMiddleware (log completion, duration)
  → CORSMiddleware
```

### 3.3 Dependency Injection Strategy

Use FastAPI's `Depends` for shared services:

```python
# backend/app/api/dependencies.py

async def get_screen_engine() -> ScreenEngine:
    """Dependency that provides a ScreenEngine instance."""
    return ScreenEngine()

async def get_backtest_engine() -> BacktestEngine:
    return BacktestEngine()

async def get_risk_engine() -> RiskEngine:
    return RiskEngine()

async def verify_api_key(
    request: Request,
    x_api_key: str | None = Header(None),
) -> str | None:
    """Optional API key verification. Returns client_id or None."""
    if not settings.api.api_keys:
        return None  # Auth disabled
    if x_api_key in settings.api.api_keys:
        return x_api_key
    return None  # Will raise 401 if endpoint requires auth
```

---

## 4. API Module Structure & Routers

### 4.1 Directory Layout

```
backend/app/api/
├── __init__.py                    # Empty (package marker)
├── main.py                        # create_app(), lifespan, FastAPI instance
├── schemas.py                     # API Pydantic request/response models
├── dependencies.py                # FastAPI Depends() providers
├── middleware.py                  # Custom ASGI middleware
├── exceptions.py                  # Exception handlers + error response builder
├── observability.py               # Prometheus + OpenTelemetry setup
├── routers/
│   ├── __init__.py                # Export all routers
│   ├── health.py                  # /health, /health/ready
│   ├── screener.py                # POST /api/v1/screen
│   ├── backtest.py                # POST /api/v1/backtest
│   ├── data.py                    # GET /api/v1/indicators/{symbol}, GET /api/v1/data/{symbol}
│   └── risk.py                    # GET /api/v1/risk/{symbol}, /risk/beta, /risk/correlation, /risk/var, /risk/kelly, /risk/position-size
└── ws/
    ├── __init__.py                # Export ws_manager
    ├── handler.py                 # WebSocket route handler
    ├── manager.py                 # WebSocketManager (unified ConnectionManager)
    └── channels.py                # Channel definitions, update providers
```

### 4.2 Router Registration Pattern

```python
# backend/app/api/routers/screener.py
from fastapi import APIRouter, Depends

from backend.app.api.dependencies import get_screen_engine
from backend.app.api.schemas import ScreenRequest, ScreenResponse

router = APIRouter(tags=["screener"])


@router.post("/screen")
async def run_screen(
    request: ScreenRequest,
    engine: ScreenEngine = Depends(get_screen_engine),
) -> ScreenResponse:
    """Run a screen configuration and return results.
    
    - `config`: Name of a built-in screen template or inline config
    - `symbols`: Optional subset of symbols (default: all active)
    - `timeframes`: Override timeframes
    """
    result = await engine.screen(
        config=request.config,
        symbols=request.symbols,
        timeframes=request.timeframes,
    )
    return ScreenResponse(
        data=result.symbols,
        meta={
            "screen_name": result.screen_name,
            "total_symbols": result.total_symbols,
            "symbols_matched": result.symbols_matched,
            "duration_ms": result.duration_ms,
            "timestamp": result.timestamp.isoformat(),
        },
    )
```

### 4.3 OpenAPI Tags Organization

Per D-04, tags for grouping:

```python
tags_metadata = [
    {
        "name": "health",
        "description": "Liveness, readiness, and dependency checks",
    },
    {
        "name": "screener",
        "description": "Multi-timeframe technical screener — run filter pipelines across asset classes",
    },
    {
        "name": "backtest",
        "description": "Strategy backtesting — vectorized simulation, walk-forward optimization, Monte Carlo",
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
```

---

## 5. REST Endpoints Design

### 5.1 Core Endpoint Specifications

Per D-02, the five core endpoints plus extended risk endpoints from Phase 5:

#### Screener Endpoint

| Method | Path | Request Body | Response | Calls |
|--------|------|-------------|----------|-------|
| `POST` | `/api/v1/screen` | `ScreenRequest` | `ScreenResponse` | `ScreenEngine.screen()` |

```python
class ScreenRequest(BaseModel):
    config: str                                     # Template name like "trend-follower"
    symbols: list[str] | None = None                # Override symbols
    timeframes: list[str] | None = None             # Override timeframes like ["1D", "4h"]
    export_format: Literal["json", "csv"] | None = None  # Optional export
```

#### Backtest Endpoint

| Method | Path | Request Body | Response |
|--------|------|-------------|----------|
| `POST` | `/api/v1/backtest` | `BacktestRequest` | `BacktestResponse` |
| `POST` | `/api/v1/backtest/optimize` | `BacktestRequest` | `OptimizeResponse` |
| `POST` | `/api/v1/backtest/monte-carlo` | `BacktestRequest` | `MCResponse` |
| `GET` | `/api/v1/backtest/{run_id}` | — | `BacktestResponse` |
| `GET` | `/api/v1/backtest/{run_id}/trades` | — | `TradeListResponse` |
| `GET` | `/api/v1/backtest/{run_id}/equity` | — | `EquityCurveResponse` |

#### Indicator Data Endpoint

| Method | Path | Query Params | Response |
|--------|------|-------------|----------|
| `GET` | `/api/v1/indicators/{symbol}` | `timeframe`, `indicators`, `limit` | `IndicatorResponse` |
| `GET` | `/api/v1/indicators` | `symbols`, `timeframe`, `indicators` | `IndicatorBulkResponse` |

#### OHLCV Data Endpoint

| Method | Path | Query Params | Response |
|--------|------|-------------|----------|
| `GET` | `/api/v1/data/{symbol}` | `timeframe`, `start`, `end`, `limit` | `OHLCVResponse` |
| `GET` | `/api/v1/data/symbols` | `asset_class`, `active` | `SymbolListResponse` |

#### Risk Endpoints

| Method | Path | Params | Calls |
|--------|------|--------|-------|
| `GET` | `/api/v1/risk/{symbol}` | `benchmark`, `window` | `RiskEngine.compute_beta()` |
| `GET` | `/api/v1/risk/beta` | `symbols[]`, `benchmark`, `window` | `RiskEngine.compute_beta()` |
| `GET` | `/api/v1/risk/correlation` | `symbols[]`, `window`, `group_by` | `RiskEngine.compute_correlation()` |
| `GET` | `/api/v1/risk/var` | `symbols[]`, `confidence`, `method`, `horizon` | `RiskEngine.compute_var()` |
| `POST` | `/api/v1/risk/kelly` | `backtest_run_id`, `max_dd_target` | `RiskEngine.compute_kelly()` |
| `POST` | `/api/v1/risk/position-size` | `symbols`, `method`, `params`, `cash` | `RiskEngine.compute_position_size()` |
| `GET` | `/api/v1/risk/summary` | `portfolio_id`, `symbols[]` | `RiskEngine.analyze_portfolio()` |

### 5.2 Response Envelope Format

Per D-03: `{data: T, meta: {timestamp, request_id}}`

```python
class ApiResponse(BaseModel, Generic[T]):
    """Standard API response envelope.
    
    All successful responses use this structure.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    data: T
    meta: MetaInfo = Field(default_factory=MetaInfo)


class MetaInfo(BaseModel):
    """Metadata attached to every API response."""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    request_id: str = Field(default_factory=lambda: set_correlation_id())
    duration_ms: float | None = None


class ApiErrorResponse(BaseModel):
    """Standard error response envelope.
    
    Per D-19: {error: {code, message, details}}
    """
    error: ErrorDetail


class ErrorDetail(BaseModel):
    code: str                                    # Machine-readable: "RATE_LIMIT_EXCEEDED"
    message: str                                 # Human-readable: "Rate limit exceeded. Try again in 30s."
    details: dict[str, Any] | None = None        # Optional field-level validation errors
    request_id: str | None = None
```

### 5.3 Pydantic Request/Response Models

All request/response models go in `backend/app/api/schemas.py`. They extend or compose with domain models from `domain/models.py`.

```python
from backend.app.domain.models import OHLCV, Signal, Metrics, Trade


class ScreenRequest(BaseModel):
    """POST /api/v1/screen request body."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    config: str                                         # Screen template name
    symbols: list[str] | None = None                    # Subset of symbols
    timeframes: list[str] | None = None                 # Override timeframes
    export_format: Literal["json", "csv"] | None = None


class ScreenResponseData(BaseModel):
    """Single symbol result from a screen run."""
    symbol: str
    score: float
    matched_filters: list[str] = Field(default_factory=list)
    indicator_values: dict[str, float] = Field(default_factory=dict)


class ScreenResponse(ApiResponse[list[ScreenResponseData]]):
    """Response from a screen run."""
    pass  # Inherits envelope from ApiResponse


# === Backtest schemas ===

class BacktestRequest(BaseModel):
    """POST /api/v1/backtest request body."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    symbols: list[str]
    start: datetime
    end: datetime
    initial_cash: float = 100_000.0
    fees_bps: float = 10.0
    slippage_bps: float = 5.0
    position_sizing: Literal["fixed", "atr", "kelly"] = "fixed"
    sizing_params: dict[str, Any] = Field(default_factory=dict)
    signal_params: dict[str, Any] = Field(default_factory=dict)
    
    @field_validator("start", "end")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return v.astimezone(timezone.utc)


class BacktestResponseData(BaseModel):
    """Backtest result summary."""
    run_id: str
    symbol: str
    timeframe: str
    metrics: Metrics
    trades_count: int
    duration_ms: float


# === Data schemas ===

class IndicatorQueryParams(BaseModel):
    """Query params for GET /api/v1/indicators/{symbol}."""
    timeframe: str = "1D"
    indicators: str | None = None    # Comma-separated: "rsi,macd,ema"
    limit: int = 200


class OHLCVQueryParams(BaseModel):
    """Query params for GET /api/v1/data/{symbol}."""
    timeframe: str = "1D"
    start: datetime | None = None
    end: datetime | None = None
    limit: int = 500


# === Risk schemas ===

class RiskVarRequest(BaseModel):
    """Query params for GET /api/v1/risk/var."""
    symbols: list[str] = Field(min_length=1)
    confidence: float = 0.95
    method: Literal["historical", "parametric", "monte_carlo"] = "historical"
    horizon: int = 1


class RiskBetaRequest(BaseModel):
    """Query params for GET /api/v1/risk/beta."""
    symbols: list[str] = Field(min_length=1)
    benchmark: str | None = None
    window: int = 60


class RiskCorrelationRequest(BaseModel):
    """Query params for GET /api/v1/risk/correlation."""
    symbols: list[str] = Field(min_length=2)
    window: int = 30
    group_by: str | None = None


class RiskKellyRequest(BaseModel):
    """POST /api/v1/risk/kelly request body."""
    backtest_run_id: str
    max_dd_target: float = 0.25


class RiskPositionSizeRequest(BaseModel):
    """POST /api/v1/risk/position-size request body."""
    symbols: list[str]
    method: Literal["atr", "kelly", "fixed"] = "atr"
    cash: float = 100_000.0
    params: dict[str, Any] = Field(default_factory=dict)


class RiskSummaryRequest(BaseModel):
    """Query params for GET /api/v1/risk/summary."""
    portfolio_id: str = "default"
    symbols: list[str] | None = None
```

### 5.4 OpenAPI Tags & Documentation

FastAPI auto-generates OpenAPI at `/docs` and `/redoc`. Configuration:

```python
app = FastAPI(
    title="conflu.ai API",
    description="Multi-asset trading platform — screener, backtest, risk analysis, and real-time data streaming",
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json",
    openapi_tags=tags_metadata,
)
```

Each endpoint gets:
- `summary` — Brief description
- `description` — Detailed explanation with example usage
- `response_description` — What the response contains
- `tags` — Grouping tag
- `status_code` — Custom status codes for specific responses

```python
@router.post(
    "/screen",
    response_model=ScreenResponse,
    summary="Run a technical screen",
    description="Execute a predefined or inline screen configuration against all active symbols. "
                "Supports multi-timeframe top-down evaluation with AND/OR filter composition. "
                "Returns matched symbols with scores, matched filters, and indicator values.",
    response_description="Screen results with matched symbols and metadata",
    tags=["screener"],
    status_code=200,
)
```

---

## 6. WebSocket Streaming Architecture

### 6.1 Single Multiplexed Endpoint

Per D-05: Single WebSocket endpoint `/ws/stream` with multiplexed channels via `type` field.

```python
# backend/app/api/ws/handler.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

ws_router = APIRouter()


@ws_router.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """Unified WebSocket endpoint for all real-time streaming.
    
    Channel types:
    - price:{symbol}      — Real-time price updates
    - indicator:{symbol}  — Indicator value updates
    - signal:{symbol}     — Screener signal updates
    - screener:{name}     — Screener run results
    - risk:{portfolio}    — Risk metric updates
    - backtest:{run_id}   — Backtest progress updates
    
    See: channels.py for channel definitions and subscription format.
    """
    await websocket.accept()
    ws_id = str(id(websocket))
    
    try:
        # Handshake phase
        initial = await websocket.receive_json()
        if initial.get("type") == "auth" and settings.api.api_keys:
            key = initial.get("api_key", "")
            if key not in settings.api.api_keys:
                await websocket.send_json({
                    "type": "error", "code": "AUTH_FAILED",
                    "message": "Invalid API key",
                })
                await websocket.close(code=4001)
                return
        
        # Send confirmation
        await websocket.send_json({
            "type": "connected",
            "connection_id": ws_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server_version": "0.2.0",
        })
        
        # Main event loop
        while True:
            data = await websocket.receive_json()
            await ws_manager.handle_message(ws_id, websocket, data)
            
    except WebSocketDisconnect:
        ws_manager.disconnect(ws_id)
        log.info("ws_client_disconnected", connection_id=ws_id)
    except Exception:
        log.exception("ws_error", connection_id=ws_id)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
```

### 6.2 Channel-Based Subscriptions

Per D-06: Client subscribes via `{"type": "subscribe", "channels": ["price:AAPL", "indicator:AAPL:rsi", "signal:AAPL"]}`

```python
# backend/app/api/ws/channels.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

import pandas as pd

from backend.app.core.logging import get_logger

log = get_logger("conflu.api.ws.channels")


# Channel update providers — called periodically to produce data
_update_providers: dict[str, Callable[[], Coroutine[Any, Any, dict[str, Any]]]] = {}


def register_update_provider(
    channel_prefix: str,
    provider: Callable[..., Coroutine[Any, Any, dict[str, Any]]],
) -> None:
    """Register a provider function for a channel prefix.
    
    Args:
        channel_prefix: e.g., 'price:', 'indicator:', 'screener:', 'risk:'
        provider: Async callable that returns update data dict.
    """
    _update_providers[channel_prefix] = provider
    log.info("update_provider_registered", channel_prefix=channel_prefix)


# --- Channel Update Providers ---

async def price_update_provider(symbol: str) -> dict[str, Any]:
    """Fetch latest price for a symbol."""
    with get_db(read_only=True) as con:
        result = con.sql(
            "SELECT timestamp, close, volume FROM ohlcv "
            "WHERE symbol = ? AND timeframe = '1D' "
            "ORDER BY timestamp DESC LIMIT 1",
            params=[symbol],
        ).fetchdf()
    if result.empty:
        return {"symbol": symbol, "price": None, "volume": None}
    row = result.iloc[0]
    return {
        "symbol": symbol,
        "price": float(row["close"]),
        "volume": float(row["volume"]),
        "timestamp": row["timestamp"].isoformat() if hasattr(row["timestamp"], "isoformat") else str(row["timestamp"]),
    }


async def indicator_update_provider(symbol: str, indicator_name: str) -> dict[str, Any]:
    """Fetch latest indicator value for a symbol."""
    cache = IndicatorCache()
    df = await cache.get_latest(indicator_name, timeframe="1D", symbols=[symbol])
    if df is None or df.empty:
        return {"symbol": symbol, "indicator": indicator_name, "value": None}
    return {
        "symbol": symbol,
        "indicator": indicator_name,
        "value": float(df.iloc[0]["value"]),
    }
```

### 6.3 WebSocketManager: Unified Manager

Combines `ConnectionManager` (Phase 3) + `RiskStreamManager` (Phase 5) patterns:

```python
# backend/app/api/ws/manager.py
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

log = get_logger("conflu.api.ws.manager")


class WebSocketManager:
    """Unified WebSocket connection manager for all streaming channels.
    
    Features:
    - Single connection pool shared across all channel types
    - Channel-based subscriptions (subscribe/unsubscribe on-the-fly)
    - Per-connection sequence numbering
    - History buffer for reconnection replay
    - Background update loops (on-demand: only when clients connected)
    - Per-connection ping/pong handling
    """
    
    def __init__(self) -> None:
        self._connections: dict[str, Any] = {}                     # ws_id -> WebSocket
        self._subscriptions: dict[str, set[str]] = defaultdict(set)  # ws_id -> {channels}
        self._channel_subscribers: dict[str, set[str]] = defaultdict(set)  # channel -> {ws_ids}
        self._sequences: dict[str, int] = defaultdict(int)         # ws_id -> next_seq
        self._history: dict[str, list[dict]] = defaultdict(list)   # ws_id -> [messages]
        self._max_history: int = 100
        self._background_tasks: dict[str, asyncio.Task] = {}
        self._log = get_logger("conflu.api.ws.manager")
    
    async def register(self, ws_id: str, websocket: Any) -> None:
        """Register a new WebSocket connection."""
        self._connections[ws_id] = websocket
        self._log.info("ws_client_registered", connection_id=ws_id)
    
    def disconnect(self, ws_id: str) -> None:
        """Remove a WebSocket connection and its subscriptions."""
        # Remove from channel subscribers
        for channel in self._subscriptions.get(ws_id, set()):
            self._channel_subscribers[channel].discard(ws_id)
        # Remove connection
        self._connections.pop(ws_id, None)
        self._subscriptions.pop(ws_id, None)
        self._history.pop(ws_id, None)
        self._log.info("ws_client_disconnected", connection_id=ws_id)
    
    async def handle_message(self, ws_id: str, websocket: Any, data: dict) -> None:
        """Process incoming client message.
        
        Supported message types:
        - {"type": "subscribe", "channels": [...]}
        - {"type": "unsubscribe", "channels": [...]}
        - {"type": "ping"}
        - {"type": "resync", "last_sequence": N}
        """
        msg_type = data.get("type", "")
        
        if msg_type == "subscribe":
            channels = data.get("channels", [])
            await self._handle_subscribe(ws_id, channels)
        
        elif msg_type == "unsubscribe":
            channels = data.get("channels", [])
            await self._handle_unsubscribe(ws_id, channels)
        
        elif msg_type == "ping":
            try:
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                pass
        
        elif msg_type == "resync":
            last_seq = data.get("last_sequence", 0)
            await self._resync(ws_id, websocket, last_seq)
        
        else:
            self._log.warning("unknown_ws_message", type=msg_type, connection_id=ws_id)
    
    async def _handle_subscribe(self, ws_id: str, channels: list[str]) -> None:
        """Subscribe a connection to channels."""
        for channel in channels:
            self._subscriptions[ws_id].add(channel)
            self._channel_subscribers[channel].add(ws_id)
        self._log.info("ws_subscribed", connection_id=ws_id, channels=channels)
    
    async def _handle_unsubscribe(self, ws_id: str, channels: list[str]) -> None:
        """Unsubscribe a connection from channels."""
        for channel in channels:
            self._subscriptions[ws_id].discard(channel)
            self._channel_subscribers[channel].discard(ws_id)
    
    async def broadcast(self, channel: str, message: dict) -> None:
        """Send a message to all subscribers of a channel."""
        ws_ids = list(self._channel_subscribers.get(channel, set()))
        if not ws_ids:
            return
        
        # Add sequence number per connection
        disconnected: list[str] = []
        for ws_id in ws_ids:
            self._sequences[ws_id] += 1
            msg = dict(message)
            msg["sequence"] = self._sequences[ws_id]
            
            # Store in history
            self._history[ws_id].append(msg)
            if len(self._history[ws_id]) > self._max_history:
                self._history[ws_id].pop(0)
            
            # Send
            ws = self._connections.get(ws_id)
            if ws:
                try:
                    await ws.send_json(msg)
                except Exception:
                    disconnected.append(ws_id)
            else:
                disconnected.append(ws_id)
        
        for ws_id in disconnected:
            self.disconnect(ws_id)
    
    async def _resync(self, ws_id: str, websocket: Any, last_sequence: int) -> None:
        """Replay missed messages for reconnecting client."""
        history = self._history.get(ws_id, [])
        if last_sequence < (self._sequences[ws_id] - len(history)):
            # Too many missed — send reconnection guidance
            try:
                await websocket.send_json({
                    "type": "resync_required",
                    "message": "Too many messages missed. Reconnect for full state.",
                    "current_sequence": self._sequences[ws_id],
                })
            except Exception:
                pass
            return
        
        missed = [msg for msg in history if msg.get("sequence", 0) > last_sequence]
        for msg in missed:
            try:
                await websocket.send_json(msg)
            except Exception:
                break
    
    def start_background_tasks(self, app: Any) -> None:
        """Start background update loops for active channels.
        
        Launched from FastAPI lifespan startup.
        """
        # Price update loop (default 1s interval per D-07)
        self._background_tasks["price"] = asyncio.create_task(
            self._price_update_loop()
        )
        # Indicator update loop (default 5s interval per D-07)
        self._background_tasks["indicator"] = asyncio.create_task(
            self._indicator_update_loop()
        )
        self._log.info("ws_background_tasks_started")
    
    async def _price_update_loop(self) -> None:
        """Periodic price update broadcast."""
        while True:
            try:
                # Find all price:* subscriptions
                price_channels = [
                    ch for ch in self._channel_subscribers
                    if ch.startswith("price:")
                ]
                for channel in price_channels:
                    symbol = channel.split(":", 1)[1]
                    data = await price_update_provider(symbol)
                    await self.broadcast(channel, {
                        "type": "price_update",
                        "channel": channel,
                        "data": data,
                    })
                await asyncio.sleep(1.0)  # 1s interval per D-07
            except asyncio.CancelledError:
                break
            except Exception:
                self._log.exception("price_update_loop_error")
                await asyncio.sleep(5.0)
    
    async def _indicator_update_loop(self) -> None:
        """Periodic indicator value broadcast (slower interval)."""
        while True:
            try:
                indicator_channels = [
                    ch for ch in self._channel_subscribers
                    if ch.startswith("indicator:")
                ]
                for channel in indicator_channels:
                    parts = channel.split(":")
                    if len(parts) == 3:
                        _, symbol, indicator = parts
                        data = await indicator_update_provider(symbol, indicator)
                        await self.broadcast(channel, {
                            "type": "indicator_update",
                            "channel": channel,
                            "data": data,
                        })
                await asyncio.sleep(5.0)  # 5s interval per D-07
            except asyncio.CancelledError:
                break
            except Exception:
                self._log.exception("indicator_update_loop_error")
                await asyncio.sleep(10.0)
    
    async def close_all(self) -> None:
        """Close all connections and cancel background tasks."""
        # Cancel background tasks
        for name, task in self._background_tasks.items():
            task.cancel()
        # Close all WebSocket connections
        for ws_id, ws in list(self._connections.items()):
            try:
                await ws.close()
            except Exception:
                pass
        self._connections.clear()
        self._subscriptions.clear()
        self._channel_subscribers.clear()
        self._log.info("ws_all_connections_closed")


# Singleton instance
ws_manager = WebSocketManager()
```

### 6.4 Message Format & Sequence Numbers

Per D-07/D-08: Delta updates with sequence numbers.

#### Server → Client Messages

```json
{
    "type": "price_update",
    "channel": "price:AAPL",
    "sequence": 142,
    "timestamp": "2026-06-19T14:30:00.123Z",
    "data": {
        "symbol": "AAPL",
        "price": 198.50,
        "change_pct": 1.2,
        "volume": 15234000,
        "timestamp": "2026-06-19T14:30:00.000Z"
    }
}

{
    "type": "indicator_update",
    "channel": "indicator:AAPL:rsi_14",
    "sequence": 87,
    "data": {
        "symbol": "AAPL",
        "indicator": "rsi_14",
        "value": 42.5,
        "timestamp": "2026-06-19T14:30:00.000Z"
    }
}

{
    "type": "screen_update",
    "channel": "screener:trend-follower",
    "sequence": 55,
    "data": {
        "screen_name": "trend-follower",
        "total_matched": 47,
        "total_symbols": 5000,
        "symbols": [
            {"symbol": "AAPL", "score": 100.0, "matched_filters": ["price_above_ema_200", "adx_trending"]},
            {"symbol": "MSFT", "score": 80.0, "matched_filters": ["price_above_ema_200"]}
        ]
    }
}

{
    "type": "error",
    "channel": "price:BADSYMBOL",
    "code": "SYMBOL_NOT_FOUND",
    "message": "Symbol 'BADSYMBOL' not found in active universe"
}
```

#### Client → Server Messages

```json
{"type": "subscribe", "channels": ["price:AAPL", "price:MSFT", "indicator:AAPL:rsi_14", "screener:trend-follower"]}

{"type": "unsubscribe", "channels": ["price:MSFT"]}

{"type": "ping"}

{"type": "resync", "last_sequence": 140}
```

---

## 7. Authentication & Authorization

### 7.1 API Key Authentication

Per D-10: API key authentication via `X-API-Key` header. Simple implementation for Phase 6.

```python
# backend/app/api/middleware.py

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.app.core.config import settings


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Authenticate requests using X-API-Key header.
    
    If no API keys are configured in settings, authentication is disabled
    (development mode). When keys are configured, all requests must include
    a valid X-API-Key header.
    
    Deferred: JWT bearer token authentication (Phase 8+).
    """
    
    # Paths that don't require authentication
    PUBLIC_PATHS = {"/health", "/health/ready", "/docs", "/redoc", "/api/v1/openapi.json"}
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip auth for public paths
        if request.url.path in self.PUBLIC_PATHS or request.url.path.startswith("/ws/"):
            return await call_next(request)
        
        # If no API keys configured, auth is disabled
        if not settings.api.api_keys:
            return await call_next(request)
        
        # Check API key
        api_key = request.headers.get("X-API-Key")
        if api_key not in settings.api.api_keys:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Valid X-API-Key header required",
                    }
                },
            )
        
        return await call_next(request)
```

### 7.2 Middleware Design

```python
# backend/app/api/middleware.py — Full middleware module

class RequestLogMiddleware(BaseHTTPMiddleware):
    """Log all HTTP requests with correlation ID, method, path, status, duration.
    
    Uses structlog with correlation_id from contextvars.
    Sets the correlation ID at the start of each request.
    """
    
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = set_correlation_id()
        start = time.monotonic()
        
        response = await call_next(request)
        
        duration_ms = (time.monotonic() - start) * 1000
        log.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
            content_length=response.headers.get("content-length"),
        )
        
        # Add X-Request-ID header
        response.headers["X-Request-ID"] = request_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token bucket rate limiting per client.
    
    Rate limits are applied based on the endpoint path prefix:
    - /api/v1/screen*     -> screener rate limit
    - /api/v1/backtest*   -> backtest rate limit
    - /api/v1/data*       -> data rate limit
    - /api/v1/risk*       -> default rate limit
    - /ws/*               -> WebSocket rate limit (msg/s)
    """
    
    def __init__(self, app):
        super().__init__(app)
        self._buckets: dict[str, TokenBucket] = {}
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip for health/docs
        if request.url.path in {"/health", "/health/ready", "/docs", "/redoc"}:
            return await call_next(request)
        
        client_id = self._get_client_id(request)
        rate, window_s = self._get_rate_limit(request.url.path)
        
        bucket = self._get_or_create_bucket(client_id, rate, window_s)
        
        if not bucket.consume():
            return JSONResponse(
                status_code=429,
                headers={
                    "X-RateLimit-Limit": str(rate),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time() + bucket.reset_in())),
                    "Retry-After": str(int(bucket.reset_in())),
                },
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit of {rate} requests per {window_s}s exceeded",
                    }
                },
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = bucket.remaining()
        response.headers["X-RateLimit-Limit"] = str(rate)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + bucket.reset_in()))
        
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """Identify client by API key or IP."""
        api_key = request.headers.get("X-API-Key", "")
        if api_key:
            return f"key:{api_key}"
        return f"ip:{request.client.host if request.client else 'unknown'}"
    
    def _get_rate_limit(self, path: str) -> tuple[int, int]:
        """Get (rate, window_seconds) for a path."""
        if path.startswith("/api/v1/screen"):
            return settings.api.rate_limit_screener, 60
        elif path.startswith("/api/v1/backtest"):
            return settings.api.rate_limit_backtest, 60
        elif path.startswith("/api/v1/data"):
            return settings.api.rate_limit_data, 60
        else:
            return settings.api.rate_limit, 60
```

### 7.3 Deferred: JWT/OAuth2

Per D-09/D-11: JWT deferred to future phases. But plan the integration points:

```python
# Deferred — for reference during planning
"""
JWT integration points (Phase 8+):
1. Add JWT secret to APISettings (field exists)
2. Create auth router: POST /api/v1/auth/login, POST /api/v1/auth/refresh
3. Create JWT dependency: verify_token() -> UserInfo
4. Add role checking: require_role("admin") dependency
5. OAuth2 JWKS support for Keycloak/Auth0 integration

Token format:
{
    "sub": "user_id",
    "role": "admin|trader|viewer",
    "exp": timestamp,
    "iat": timestamp
}
"""
```

---

## 8. Rate Limiting

### 8.1 slowapi vs Custom Token Bucket

Per D-22: OpenCode's choice between slowapi (FastAPI native) and custom token bucket.

| Option | Pros | Cons |
|--------|------|------|
| **A: slowapi** | FastAPI-native decorators, Redis backend, in-memory fallback, rate limit headers | Extra dependency, decorator-based (not middleware), limited WS support |
| **B: Custom Token Bucket** | No dependency, full control, WS rate limiting, middleware pattern | More code, no Redis persistence by default |
| **C: fastapi-limiter** | Redis-backed, async, decorator API | Requires Redis, WS support unclear |

**Recommendation: Option B (Custom Token Bucket)** — Rationale:

1. Phase 6 is single-process — no need for Redis (yet)
2. Token bucket is simple (~50 lines)
3. Custom implementation allows unified REST + WS rate limiting in one middleware
4. Can be swapped for slowapi+Redis in production without changing the interface
5. Full control over rate limit headers per D-13

```python
class TokenBucket:
    """Simple token bucket rate limiter (in-memory).
    
    Thread-safe for sync usage (async FastAPI runs in single thread).
    """
    
    def __init__(self, rate: int, window_s: int = 60) -> None:
        self._rate = rate
        self._window_s = window_s
        self._tokens = float(rate)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()
    
    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed."""
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False
    
    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._rate, self._tokens + self._rate * (elapsed / self._window_s))
        self._last_refill = now
    
    def remaining(self) -> int:
        with self._lock:
            self._refill()
            return int(self._tokens)
    
    def reset_in(self) -> float:
        """Seconds until the bucket fully refills."""
        with self._lock:
            return max(0.0, self._window_s - (time.monotonic() - self._last_refill))
```

### 8.2 Per-Endpoint Rate Groups

Per D-14: Configurable per endpoint group.

| Group | Path Pattern | Default Rate | Why |
|-------|-------------|-------------|-----|
| **Default** | All other API | 100 req/min | General API access |
| **Screener** | `/api/v1/screen*` | 30 req/min | CPU-intensive, cache-efficient |
| **Backtest** | `/api/v1/backtest*` | 10 req/min | Heavy computation, long-running |
| **Data** | `/api/v1/data/*`, `/api/v1/indicators/*` | 200 req/min | Read-only, cached |
| **Risk** | `/api/v1/risk/*` | 60 req/min | Moderate compute |
| **WebSocket** | `/ws/*` | 10 msg/s | Per-connection message rate |
| **Health** | `/health*` | No limit | Monitoring systems |

### 8.3 Rate Limit Headers

Per D-13: Standard rate limit headers on every response.

```
X-RateLimit-Limit: 100          # Max requests in the window
X-RateLimit-Remaining: 87       # Remaining requests in current window
X-RateLimit-Reset: 1718795432   # Unix timestamp when the window resets
```

On rate limit exceeded (429):
```
Retry-After: 45                 # Seconds to wait
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1718795432
```

---

## 9. Observability

### 9.1 Structured Logging with Correlation IDs

Phase 1 already set up structlog with correlation IDs. Phase 6 ensures:

1. Every HTTP request gets a correlation ID (via `RequestLogMiddleware`)
2. Every WebSocket message gets a correlation ID
3. Correlation ID propagates to engine calls (structlog contextvars)
4. Request ID flows to responses via `X-Request-ID` header

```python
# Log format per request:
{"event": "http_request", "method": "POST", "path": "/api/v1/screen", 
 "status": 200, "duration_ms": 1450.32, "correlation_id": "abc-123",
 "timestamp": "2026-06-19T14:30:00Z", "filename": "middleware.py", 
 "func_name": "dispatch", "lineno": 42}

{"event": "http_request", "method": "GET", "path": "/health", 
 "status": 200, "duration_ms": 2.15, "correlation_id": "def-456",
 "timestamp": "2026-06-19T14:30:01Z", "filename": "middleware.py", 
 "func_name": "dispatch", "lineno": 42}
```

### 9.2 Prometheus Metrics

Per D-16: Prometheus metrics via `prometheus-fastapi-instrumentator`.

```python
# backend/app/api/observability.py

from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_fastapi_instrumentator.metrics import Info
from prometheus_client import Counter, Gauge


def setup_prometheus(app: FastAPI) -> None:
    """Configure Prometheus metrics collection.
    
    Default metrics (via Instrumentator):
    - http_requests_total (method, path, status)
    - http_request_duration_seconds (method, path)
    - http_request_size_bytes
    - http_response_size_bytes
    
    Custom metrics:
    - ws_connections_active (gauge)
    - rate_limit_exceeded_total (counter)
    - screen_duration_seconds (histogram)
    - backtest_duration_seconds (histogram)
    """
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        env_var_name="ENABLE_METRICS",
    )
    
    # Add custom metrics
    instrumentator.add(_create_ws_connections_metric())
    instrumentator.add(_create_rate_limit_exceeded_metric())
    
    # Instrument and expose
    instrumentator.instrument(app).expose(app, endpoint="/metrics")


def _create_ws_connections_metric():
    """Gauge: current active WebSocket connections."""
    ws_gauge = Gauge(
        "ws_connections_active",
        "Number of currently active WebSocket connections",
    )
    
    def metric(info: Info) -> None:
        from backend.app.api.ws.manager import ws_manager
        ws_gauge.set(len(ws_manager._connections))
    
    return metric


def _create_rate_limit_exceeded_metric():
    """Counter: total rate limit exceedances."""
    rl_counter = Counter(
        "rate_limit_exceeded_total",
        "Total number of rate-limited requests",
        labelnames=("endpoint_group",),
    )
    
    def metric(info: Info) -> None:
        # Incremented in RateLimitMiddleware
        pass
    
    return metric


# WebSocket metrics (manually updated)
ws_connections_gauge = Gauge(
    "ws_connections_active",
    "Number of currently active WebSocket connections",
)

ws_messages_total = Counter(
    "ws_messages_total",
    "Total WebSocket messages sent",
    labelnames=("channel_type",),
)

ws_errors_total = Counter(
    "ws_errors_total",
    "Total WebSocket errors",
    labelnames=("error_type",),
)
```

### 9.3 OpenTelemetry Tracing

Per D-17: OpenTelemetry traces for request lifecycle. Auto-instrumentation preferred.

```python
def setup_opentelemetry(app: FastAPI) -> None:
    """Configure OpenTelemetry for distributed tracing.
    
    Uses auto-instrumentation for FastAPI + SDK export via OTLP.
    Falls back to console exporter if no OTLP endpoint configured.
    """
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    
    resource = Resource.create({
        "service.name": settings.api.otel_service_name,
        "service.version": "0.2.0",
    })
    
    provider = TracerProvider(resource=resource)
    
    # Export to OTLP or console
    if settings.api.otel_exporter_otlp_endpoint:
        exporter = OTLPSpanExporter(
            endpoint=settings.api.otel_exporter_otlp_endpoint,
        )
    else:
        exporter = ConsoleSpanExporter()
    
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    
    # Auto-instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)
    
    # Note: Additional auto-instrumentors for HTTPX, SQLAlchemy, etc.
    # Can be added via opentelemetry-instrumentation-* packages
```

The auto-instrumentation will produce spans for:
- Each HTTP request (method, path, status code)
- Each database query (if DuckDB OTel is available)
- External HTTP calls (from httpx)

### 9.4 Health Endpoints

Per D-18: `/health` (liveness) and `/health/ready` (readiness).

```python
# backend/app/api/routers/health.py
from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Liveness check. Always returns 200 when the server is running.
    
    Used by Kubernetes/Docker health checks.
    """
    return {
        "status": "ok",
        "service": "conflu-api",
        "version": "0.2.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ready")
async def readiness():
    """Readiness check. Verifies DuckDB connectivity.
    
    Returns 200 when the service can handle requests.
    Returns 503 if dependencies are unavailable.
    """
    checks = {
        "database": False,
        "indicator_cache": False,
    }
    
    # Check DuckDB
    try:
        with get_db(read_only=True) as con:
            con.sql("SELECT 1").fetchone()
        checks["database"] = True
    except Exception:
        pass
    
    # Check indicator cache table exists
    try:
        with get_db(read_only=True) as con:
            result = con.sql(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_name = 'indicator_values'"
            ).fetchone()
            checks["indicator_cache"] = result[0] > 0 if result else False
    except Exception:
        pass
    
    all_healthy = all(checks.values())
    
    response = {
        "status": "healthy" if all_healthy else "degraded",
        "service": "conflu-api",
        "version": "0.2.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
    
    if all_healthy:
        return response
    return JSONResponse(
        status_code=503,
        content=response,
    )
```

---

## 10. Error Handling & Exception Middleware

Per D-19: Standardized error responses with `{error: {code, message, details}}`.
Per D-20: Global exception handler, no stack traces in production.

```python
# backend/app/api/exceptions.py


# ── Custom Exception Classes ──

class ApiException(Exception):
    """Base exception for API errors with structured details."""
    def __init__(
        self,
        status_code: int = 500,
        code: str = "INTERNAL_ERROR",
        message: str = "An unexpected error occurred",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


class NotFoundException(ApiException):
    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            status_code=404,
            code="NOT_FOUND",
            message=f"{resource} '{identifier}' not found",
        )


class ValidationException(ApiException):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            status_code=422,
            code="VALIDATION_ERROR",
            message=message,
            details=details,
        )


class RateLimitException(ApiException):
    def __init__(self, message: str) -> None:
        super().__init__(
            status_code=429,
            code="RATE_LIMIT_EXCEEDED",
            message=message,
        )


class EngineException(ApiException):
    """Wraps errors from underlying engines (screener, backtest, risk)."""
    def __init__(self, engine: str, original_error: str) -> None:
        super().__init__(
            status_code=500,
            code=f"{engine.upper()}_ERROR",
            message=f"{engine.capitalize()} engine error",
            details={"original_error": original_error},
        )


# ── Exception Handlers ──

def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""
    
    @app.exception_handler(ApiException)
    async def api_exception_handler(request: Request, exc: ApiException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "request_id": correlation_id.get(),
                }
            },
        )
    
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """Fallback handler for any unhandled exceptions.
        
        Logs full traceback but returns sanitized error response.
        No stack traces in production responses (D-20).
        """
        log.exception("unhandled_exception", path=request.url.path)
        
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "request_id": correlation_id.get(),
                }
            },
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle FastAPI's built-in HTTPException (e.g., 422 from validation)."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "HTTP_ERROR",
                    "message": exc.detail,
                    "details": getattr(exc, "errors", None),  # Pydantic validation errors
                    "request_id": correlation_id.get(),
                }
            },
        )
```

---

## 11. Configuration Extensions

### 11.1 Extending APISettings

```python
# In backend/app/core/config.py — additions to APISettings

class APISettings(BaseSettings):
    """API server settings."""
    model_config = SettingsConfigDict(env_prefix="CONFLU_API_")
    
    # Existing fields
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    cors_origins: list[str] = Field(default=["http://localhost:5173"])
    rate_limit: int = Field(default=100)
    
    # Rate limits per endpoint group (D-14)
    rate_limit_screener: int = Field(default=30, ge=1, le=1000)
    rate_limit_backtest: int = Field(default=10, ge=1, le=100)
    rate_limit_data: int = Field(default=200, ge=1, le=5000)
    rate_limit_ws: int = Field(default=10, ge=1, le=100, description="WS messages/second")
    
    # Authentication (D-10, D-11)
    api_keys: list[str] = Field(
        default_factory=list,
        description="Valid API keys. Empty = auth disabled (dev mode).",
    )
    jwt_secret: str = Field(default="", description="JWT signing secret (deferred)")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=60)
    
    # CORS
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = Field(default=["*"])
    cors_allow_headers: list[str] = Field(default=["*"])
    
    # OpenTelemetry (D-17)
    otel_service_name: str = "conflu-api"
    otel_exporter_otlp_endpoint: str = Field(
        default="", description="OTLP gRPC endpoint (empty = console exporter)"
    )
    
    # Prometheus (D-16)
    prometheus_enabled: bool = True
    
    # Security
    log_request_body: bool = False
    
    # Health checks
    health_db_timeout_s: float = Field(default=5.0, ge=1.0)
    
    # WebSocket (D-05, D-06)
    ws_max_connections: int = Field(default=1000, ge=1, le=10000)
    ws_ping_interval_s: float = Field(default=30.0, ge=5.0)
    ws_pong_timeout_s: float = Field(default=10.0, ge=1.0)
```

### 11.2 Default config.yaml Additions

```yaml
# In config.yaml — api section additions
api:
  rate_limit: 100
  rate_limit_screener: 30
  rate_limit_backtest: 10
  rate_limit_data: 200
  rate_limit_ws: 10
  api_keys: []
  jwt_secret: ""
  jwt_algorithm: HS256
  jwt_expire_minutes: 60
  cors_origins:
    - "http://localhost:5173"
    - "http://localhost:3000"
  cors_allow_credentials: true
  cors_allow_methods: ["*"]
  cors_allow_headers: ["*"]
  otel_service_name: "conflu-api"
  otel_exporter_otlp_endpoint: ""
  prometheus_enabled: true
  log_request_body: false
  health_db_timeout_s: 5.0
  ws_max_connections: 1000
  ws_ping_interval_s: 30.0
  ws_pong_timeout_s: 10.0
```

---

## 12. Module Design & File Structure

### 12.1 Directory Layout

```
backend/app/api/
├── __init__.py                        # Empty (package marker)
├── main.py                            # create_app(), lifespan, FastAPI instance
├── schemas.py                         # Pydantic request/response models (all endpoints)
├── dependencies.py                    # FastAPI Depends() providers
├── middleware.py                      # RequestLog, RateLimit, APIKey middleware
├── exceptions.py                      # ApiException classes, exception handlers
├── observability.py                   # Prometheus + OpenTelemetry setup
├── routers/
│   ├── __init__.py                    # Export all routers
│   ├── health.py                      # /health, /health/ready
│   ├── screener.py                    # POST /api/v1/screen
│   ├── backtest.py                    # POST /api/v1/backtest, /optimize, /monte-carlo
│   ├── data.py                        # GET /api/v1/data/{symbol}, /indicators/{symbol}
│   └── risk.py                        # GET /api/v1/risk/{symbol}, /beta, /correlation, /var, /kelly, /position-size, /summary
└── ws/
    ├── __init__.py                    # Export ws_manager
    ├── handler.py                     # /ws/stream route handler
    ├── manager.py                     # WebSocketManager (unified)
    └── channels.py                    # Channel update providers
```

### 12.2 Class & Module Dependency Diagram

```
main.py
├── create_app()
│   ├── FastAPI(lifespan=lifespan)
│   ├── add_middleware(CORSMiddleware)
│   ├── add_middleware(RequestLogMiddleware)
│   ├── add_middleware(RateLimitMiddleware)
│   ├── include_router(health_router)
│   ├── include_router(screener_router, prefix="/api/v1")
│   ├── include_router(backtest_router, prefix="/api/v1")
│   ├── include_router(data_router, prefix="/api/v1")
│   ├── include_router(risk_router, prefix="/api/v1")
│   ├── register_ws_routes(app)
│   └── register_exception_handlers(app)
│
├── lifespan()
│   ├── configure_logging()
│   ├── initialize_database()
│   ├── setup_prometheus()
│   ├── setup_opentelemetry()
│   └── ws_manager.start_background_tasks()

middleware.py
├── RequestLogMiddleware
├── RateLimitMiddleware
│   └── TokenBucket

exceptions.py
├── ApiException
├── NotFoundException
├── ValidationException
├── RateLimitException
├── EngineException
└── register_exception_handlers()

ws/manager.py
└── WebSocketManager
    ├── register()
    ├── disconnect()
    ├── handle_message()
    ├── broadcast()
    ├── start_background_tasks()
    ├── close_all()
    ├── _price_update_loop()
    └── _indicator_update_loop()

ws/handler.py
└── websocket_stream()
    ├── websocket.accept()
    ├── ws_manager.register()
    ├── ws_manager.handle_message()
    └── ws_manager.disconnect()

routers/screener.py
└── POST /api/v1/screen
    ├── Depends(get_screen_engine)
    └── ScreenEngine.screen()

routers/backtest.py
└── POST /api/v1/backtest
    ├── Depends(get_backtest_engine)
    └── BacktestEngine.run()

routers/risk.py
└── GET /api/v1/risk/{symbol}
    ├── Depends(get_risk_engine)
    └── RiskEngine.compute_beta()

routers/data.py
└── GET /api/v1/data/{symbol}
    └── Direct DuckDB query via get_db()
```

### 12.3 Data Flow

```
HTTP Request Flow:
┌──────────┐   ┌──────────┐   ┌────────────┐   ┌───────────┐   ┌──────────────┐
│  Client  │ → │  CORS    │ → │  RequestLog │ → │ RateLimit │ → │  Route       │
│          │   │ Middle.  │   │  Middle.    │   │ Middle.   │   │  Handler     │
└──────────┘   └──────────┘   └────────────┘   └───────────┘   └──────┬───────┘
                                                                      │
                                                                      ▼
                                                              ┌──────────────┐
                                                              │  Depends()   │
                                                              │  Engines     │
                                                              └──────┬───────┘
                                                                     │
                                                                     ▼
                                                              ┌──────────────┐
                                                              │  Phase 3-5   │
                                                              │  Engine Call  │
                                                              └──────┬───────┘
                                                                     │
                                                                     ▼
                                                              ┌──────────────┐
                                                              │  Response    │
                                                              │  Envelope    │
                                                              └──────────────┘

WebSocket Flow:
┌──────────┐   ┌───────────┐   ┌────────────────┐   ┌──────────────┐
│  Client  │ → │  handler  │ → │  ws_manager    │ → │  broadcast   │
│  /ws/    │   │  accept() │   │  subscribe()   │   │  to channel  │
│  stream  │   └───────────┘   └───────┬────────┘   └──────┬───────┘
└──────────┘                           │                   │
                                       ▼                   ▼
                                ┌──────────────┐   ┌──────────────┐
                                │ background   │   │  Phase 3-5   │
                                │ update loop  │   │  Engine      │
                                └──────────────┘   └──────────────┘
```

---

## 13. Dependencies & pyproject.toml

### 13.1 New Packages Required

| Package | Version | Purpose | Required? |
|---------|---------|---------|-----------|
| `fastapi` | `>=0.115,<1` | Web framework | YES (already listed in Phase 3) |
| `uvicorn[standard]` | `>=0.29,<1` | ASGI server | YES (already listed in Phase 3) |
| `prometheus-fastapi-instrumentator` | `>=7.0,<8` | Prometheus metrics | YES |
| `opentelemetry-api` | `>=1.25,<2` | OpenTelemetry API | OPTIONAL (observability) |
| `opentelemetry-sdk` | `>=1.25,<2` | OpenTelemetry SDK | OPTIONAL |
| `opentelemetry-instrumentation-fastapi` | `>=0.50b,<1` | FastAPI auto-instrumentation | OPTIONAL |
| `opentelemetry-exporter-otlp` | `>=1.25,<2` | OTLP exporter | OPTIONAL |
| `pyjwt` / `python-jose` | latest | JWT tokens | Deferred (Phase 8+) |
| `slowapi` | latest | Rate limiting | OPTIONAL (custom impl preferred) |
| `websockets` | `>=12.0` | WS client testing | DEV only |

### 13.2 pyproject.toml Additions

```toml
[project.dependencies]
# ... existing dependencies from Phase 1-5 ...
fastapi = ">=0.115,<1"
uvicorn = {extras = ["standard"], version = ">=0.29,<1"}
prometheus-fastapi-instrumentator = ">=7.0,<8"

# Optional OpenTelemetry dependencies (install only if needed)
opentelemetry-api = {version = ">=1.25,<2", optional = true}
opentelemetry-sdk = {version = ">=1.25,<2", optional = true}
opentelemetry-instrumentation-fastapi = {version = ">=0.50b,<1", optional = true}
opentelemetry-exporter-otlp = {version = ">=1.25,<2", optional = true}

[project.optional-dependencies]
observability = [
    "opentelemetry-api>=1.25",
    "opentelemetry-sdk>=1.25",
    "opentelemetry-instrumentation-fastapi>=0.50b",
    "opentelemetry-exporter-otlp>=1.25",
]

[project.optional-dependencies]
test = [
    # ... existing test deps ...
    "websockets>=12.0",
    "httpx>=0.27",  # For TestClient
]

[[tool.mypy.overrides]]
module = [
    "fastapi.*",
    "prometheus_fastapi_instrumentator.*",
    "opentelemetry.*",
]
ignore_missing_imports = false  # FastAPI has good stubs
```

### 13.3 No New Infrastructure

- **No new databases** — DuckDB handles everything
- **No new message brokers** — WebSocket is direct server-client
- **No new cache layers** — In-memory TokenBucket for rate limiting
- Redis exists in docker-compose for future rate limiting scaling

---

## 14. Integration Points with Phases 1-5

### 14.1 What Phase 6 Consumes

| Phase | Asset | File | Used By |
|-------|-------|------|---------|
| 1 | `settings` singleton | `core/config.py` | All middleware, routers, websocket |
| 1 | `get_db()`, `get_db_async()` | `core/database.py` | Data router (direct queries) |
| 1 | `configure_logging()` | `core/logging.py` | Lifespan startup |
| 1 | `set_correlation_id()` | `core/logging.py` | RequestLogMiddleware |
| 1 | `get_logger()` | `core/logging.py` | All API modules |
| 2 | `partition_path()` | `core/database.py` | Data file download (future) |
| 2 | OHLCV DuckDB table | SQL DDL in `core/database.py` | Data router, risk router |
| 3 | `ScreenEngine` | `screener/engine.py` | Screener router |
| 3 | `IndicatorCache` | `screener/cache.py` | Indicator data router, WS provider |
| 3 | `ConnectionManager` | `screener/streaming.py` | Reference pattern for WS (not consumed directly) |
| 4 | `BacktestEngine` | `backtest/engine.py` | Backtest router |
| 4 | `TradeLedger` | `backtest/ledger.py` | Backtest router (trade data) |
| 4 | `MetricsComputer` | `backtest/metrics.py` | Backtest router (metrics) |
| 5 | `RiskEngine` | `risk/engine.py` | Risk router |
| 5 | `RiskStreamManager` | `risk/streaming.py` | Reference pattern for WS |
| 5 | `BetaHedger` | `risk/beta.py` | Risk beta endpoint |
| 5 | `CorrelationAnalyzer` | `risk/correlation.py` | Risk correlation endpoint |
| 5 | `VaRCalculator` | `risk/var.py` | Risk VaR endpoint |
| 5 | `KellyOptimizer` | `risk/kelly.py` | Risk Kelly endpoint |

### 14.2 What Phase 6 Provides to Downstream Phases

| Downstream Phase | What It Gets | How |
|-----------------|-------------|-----|
| Phase 7 (Frontend) | REST API + WebSocket streaming | HTTP/WS interface |
| Phase 8 (Advanced Screener) | Save/load screen endpoints | Reuses screener router |
| Phase 9 (Advanced Backtest) | Report generation endpoints | Extends backtest router |
| Phase 10 (Production) | Metrics, health, OTel, Docker | Already configured |

---

## 15. Risks & Mitigations

### High Risk

| Risk | Description | Likelihood | Impact | Mitigation |
|------|-------------|------------|--------|------------|
| **WebSocket multiplexing complexity** | Single endpoint with dynamic subscriptions is more complex than per-feature WS endpoints. Client library compatibility issues. | Medium | High | Follow well-established pattern (WS multiplexing is common in trading platforms). Use simple channel naming. Test with `websockets` library. Document client integration. |
| **Rate limiting without Redis** | In-memory token bucket doesn't survive restart and doesn't work across multiple API instances. | Medium | Medium | Phase 6 is single-process by default. Document that Redis-backed rate limiting is the upgrade path for multi-instance deployments. |
| **Engines run in main thread** | Phase 3-5 engines use `asyncio.to_thread()` for CPU work. If API routes call engines without thread isolation, they block the event loop. | Medium | High | Ensure all engine calls from routes use `await loop.run_in_executor()` for CPU-bound work. The Phase 4 BacktestEngine already does this. ScreenEngine and RiskEngine methods need review. |
| **OpenTelemetry dependency weight** | OTel packages add ~50MB to Docker image size and may conflict with other dependencies. | High | Low | Make OTel optional via `pip install conflu[observability]`. Guard with `try/except` imports in `observability.py`. |

### Medium Risk

| Risk | Description | Likelihood | Impact | Mitigation |
|------|-------------|------------|--------|------------|
| **Prometheus instrumentator version compatibility** | FastAPI updates may break `prometheus-fastapi-instrumentator` between versions. | Low | Medium | Pin both `fastapi` and `prometheus-fastapi-instrumentator` to compatible version ranges. Test metrics endpoint after FastAPI upgrades. |
| **WebSocket /health endpoint interference** | Health checks (every 30s from Docker) count toward rate limits and appear in logs. | High | Low | Add `/health` and `/health/ready` to `PUBLIC_PATHS` and skip logging for health checks. Exclude from rate limiting. |
| **API key stored in config file** | API keys in `config.yaml` or `config.local.yaml` may be accidentally committed to git. | Medium | High | `config.local.yaml` should be `.gitignore`d. Warn users to set keys via `CONFLU_API__API_KEYS` env var. |
| **Request body logging leaks data** | Logging request bodies may leak API keys, symbol lists, or trading strategy parameters. | Medium | Medium | Default `log_request_body=False`. Log truncated bodies only in debug mode. |
| **WebSocket reconnection buffer sizing** | 100 messages may not be enough for clients that disconnect for extended periods. | Low | Medium | Make `_max_history` configurable via `settings.api.ws_max_history`. On large gaps, force full snapshot resync. |

### Low Risk

| Risk | Description | Likelihood | Impact | Mitigation |
|------|-------------|------------|--------|------------|
| **OpenAPI spec size** | With 15+ endpoints, the OpenAPI JSON may exceed 1MB. | Low | Low | Use `openapi_tags` and `include_in_schema=False` for internal routes. |
| **uvicorn reload in production** | `--reload` flag in docker-compose is for development only. | Low | Low | Remove `--reload` in production docker-compose. |
| **Mypy strictness on FastAPI** | FastAPI's dynamic routing may trigger mypy warnings. | Low | Low | Add mypy overrides for `fastapi.*` and `starlette.*` if needed. |

---

## 16. Open Questions for Planning

### Q1: slowapi vs Custom Token Bucket Middleware?
D-22 leaves this to discretion. The custom middleware approach has advantages (unified REST+WS, zero dependencies, full control), but slowapi is battle-tested and has Redis backend.
- **Recommendation:** Custom `TokenBucket` + `RateLimitMiddleware`. Simple, no deps, unified. Can swap to slowapi+Redis later.

### Q2: WebSocketManager — Inherit ConnectionManager or Composition?
Should the unified `WebSocketManager` inherit from `ConnectionManager` (Phase 3) or use composition?
- **Recommendation:** Composition. The channel-based model is different enough from screen_id-based model. Extracting a shared base class adds unnecessary abstraction for one consumer.

### Q3: OpenTelemetry — Auto-Instrumentation vs Manual Spans?
Auto-instrumentation covers HTTP + DB + HTTPX. Manual spans give more control over engine internals.
- **Recommendation:** Auto-instrumentation only for Phase 6. Add manual spans to engines in later phases if tracing reveals bottlenecks.

### Q4: Prometheus metric endpoint exposure?
Should `/metrics` be protected by API key auth?
- **Recommendation:** No — monitoring systems typically scrape without auth. If protection is needed, restrict at the network level (firewall/mesh).

### Q5: API key rotation and management?
Current API keys are static config. Should Phase 6 include key management (add/revoke via API)?
- **Recommendation:** Deferred. Static config for Phase 6. Key management API in Phase 8 (security hardening). Document that keys are set via env var or `config.local.yaml`.

### Q6: Support for background task cancellation?
Long-running backtests may need cancellation support.
- **Recommendation:** Deferred to Phase 9. Phase 6 backtests run synchronously with a timeout (configurable). Add `POST /api/v1/backtest/{run_id}/cancel` in Phase 9.

### Q7: Rate limiting for WebSocket — messages per connection vs per channel?
D-12 says 10 msg/s for WebSocket. Should this be per-connection or per-channel?
- **Recommendation:** Per-connection. A client subscribing to 5 channels still gets 10 msg/s total. This prevents abuse while keeping the model simple.

### Q8: What logging format for engine calls within API routes?
When `ScreenEngine.screen()` is called from a route, should the engine log with the API's correlation ID or its own?
- **Recommendation:** The API sets `correlation_id` via `set_correlation_id()` in `RequestLogMiddleware`. This propagates automatically to engine logs via `structlog.contextvars.merge_contextvars`. No changes needed in engines.

### Q9: Docker CMD update for uvicorn import?
Current docker-compose CMD is: `uvicorn backend.app.api.main:app`. This depends on `backend.app.api.main` existing.
- **Recommendation:** The existing docker-compose CMD is correct. After Phase 6, `backend/app/api/main.py` will exist with the `app` object. No docker-compose changes needed.

### Q10: Debug mode with request body logging?
For development, logging request bodies can be helpful. Should there be a debug mode toggle?
- **Recommendation:** Add `--debug` CLI arg or `CONFLU_API_LOG_REQUEST_BODY=true` env var. When enabled, log request body (truncated to 1KB) as `debug` level.

---

## Summary of Technology Choices

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Web framework | FastAPI (async) | Industry standard, async-native, auto-OpenAPI |
| API versioning | URL prefix `/api/v1/` | Simple, explicit, no header negotiation |
| Response envelope | `{data, meta}` | Standardized, request_id for tracing |
| OpenAPI docs | `/docs` (Swagger), `/redoc` (ReDoc) | Built-in FastAPI, zero config |
| Websocket | Single `/ws/stream`, channel-based | Multiplexed, extensible, one connection |
| WS manager | Custom `WebSocketManager` (composition) | Combines Phase 3 + Phase 5 patterns |
| Auth | API key via `X-API-Key` header | Simple, sufficient for Phase 6 |
| JWT | Deferred (Phase 8+) | Not needed for single-user/dev |
| Rate limiting | Custom `TokenBucket` middleware | Zero deps, unified REST+WS, full control |
| Metrics | `prometheus-fastapi-instrumentator` | Battle-tested, zero-config default metrics |
| Tracing | OpenTelemetry auto-instrumentation | Optional, vendor-neutral, OTLP export |
| Logging | structlog (Phase 1) + RequestLogMiddleware | Already configured, consistent format |
| Error format | `{error: {code, message, details}}` | Standardized, machine-readable codes |
| Health | `/health` (liveness) + `/health/ready` (readiness) | Docker/K8s compatible |
| Exception handling | Global handlers with sanitization | No stack traces in production |
| WebSocket test client | `websockets` + `httpx` | Async test support |
| API request models | Pydantic v2 (`schemas.py`) | Same ecosystem as domain models |

---

*This research feeds into `06-PLAN.md`. All documentation references verified against current (June 2026) library APIs.*
