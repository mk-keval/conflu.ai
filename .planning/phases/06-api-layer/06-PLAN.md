# Phase 6: API Layer — Plan

**Created:** 2026-06-19
**Status:** Ready for execution
**Phase Goal:** FastAPI REST + WebSocket, authentication, rate limiting, observability

---

## must_haves

Every task below must produce code that — when all tasks are complete — satisfies:

1. `backend/app/api/main.py` exists and exports `app: FastAPI` which uvicorn can load
2. `POST /api/v1/screen` delegates to `ScreenEngine.screen()` and returns `{data, meta}` envelope
3. `POST /api/v1/backtest` delegates to `BacktestEngine.run()` and returns `{data, meta}` envelope
4. `GET /api/v1/indicators/{symbol}` queries `IndicatorCache.get_series()` and returns indicator values
5. `GET /api/v1/data/{symbol}` queries DuckDB OHLCV table and returns candle data
6. `GET /api/v1/risk/{symbol}` delegates to `RiskEngine.compute_beta()` and returns risk metrics
7. `GET /api/v1/risk/beta`, `correlation`, `var`, `kelly`, `position-size`, `summary` all delegate to `RiskEngine`
8. `/ws/stream` accepts WebSocket connections and supports channel-based subscriptions
9. `GET /health` returns `{status: "ok"}` and `GET /health/ready` verifies DuckDB connectivity
10. `X-API-Key` header authentication works when `api_keys` list is non-empty in config
11. Token-bucket rate limiting returns 429 with `X-RateLimit-*` headers when exceeded
12. Every request gets a `correlation_id` logged via structlog and returned as `X-Request-ID` header
13. `/metrics` endpoint exposes Prometheus metrics
14. Error responses follow `{error: {code, message, details, request_id}}` format
15. All new code passes `mypy --strict` and `ruff`

---

## Wave 1: Foundation (Wave 1)

**Dependencies:** None
**Files modified:** `backend/app/core/config.py`, `config.yaml`, `backend/app/api/__init__.py` (already exists, no changes needed), `backend/app/api/schemas.py`, `backend/app/api/exceptions.py`, `backend/app/api/middleware.py`, `backend/app/api/dependencies.py`

### Task 1.1: Extend APISettings with new fields

<read_first>
- `backend/app/core/config.py` (read existing `APISettings` class at line 289-304)
- `config.yaml` (read existing `api:` section at line 134-139)
- `.planning/phases/06-api-layer/06-RESEARCH.md` section 11 (Configuration Extensions, lines 1875-1957)
</read_first>

<action>
Add the following fields to the existing `APISettings` class in `backend/app/core/config.py`:

```python
# Rate limits per endpoint group (D-14)
rate_limit_screener: int = Field(default=30, ge=1, le=1000, description="Screener endpoint requests/min")
rate_limit_backtest: int = Field(default=10, ge=1, le=100, description="Backtest endpoint requests/min")
rate_limit_data: int = Field(default=200, ge=1, le=5000, description="Data endpoint requests/min")
rate_limit_ws: int = Field(default=10, ge=1, le=100, description="WebSocket messages/second/client")

# Authentication (D-10, D-11)
api_keys: list[str] = Field(default_factory=list, description="Valid API keys. Empty = auth disabled (dev mode).")
jwt_secret: str = Field(default="", description="JWT signing secret (deferred)")
jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
jwt_expire_minutes: int = Field(default=60, description="JWT token expiry in minutes")

# CORS
cors_allow_credentials: bool = True
cors_allow_methods: list[str] = Field(default=["*"])
cors_allow_headers: list[str] = Field(default=["*"])

# OpenTelemetry (D-17)
otel_service_name: str = "conflu-api"
otel_exporter_otlp_endpoint: str = Field(default="", description="OTLP gRPC endpoint (empty = console exporter)")

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

Add `"*"` to the existing `cors_origins` default — change to `["http://localhost:5173", "http://localhost:3000"]`.

Then update `config.yaml` `api:` section to include:
```yaml
api:
  host: 0.0.0.0
  port: 8000
  cors_origins:
    - http://localhost:5173
    - http://localhost:3000
  rate_limit: 100
  rate_limit_screener: 30
  rate_limit_backtest: 10
  rate_limit_data: 200
  rate_limit_ws: 10
  api_keys: []
  jwt_secret: ""
  jwt_algorithm: HS256
  jwt_expire_minutes: 60
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
</action>

<acceptance_criteria>
- `APISettings` class has all 22 new fields listed above
- `config.yaml` `api:` section has all the new YAML keys
- `mypy --strict backend/app/core/config.py` passes
- `ruff check backend/app/core/config.py` passes
</acceptance_criteria>

---

### Task 1.2: Create API Pydantic schemas (schemas.py)

<read_first>
- `backend/app/domain/models.py` (existing domain models — `OHLCV`, `Signal`, `Position`, `Trade`, `Metrics`, `ScreenResult`, `BacktestConfig`, `RiskParams`)
- `backend/app/infrastructure/backtest/models.py` (existing `BacktestRunConfig`, `BacktestRunRecord`)
- `backend/app/infrastructure/risk/models.py` (existing `VaRResult`, `BetaResult`, `CorrelationResult`, `KellyRecommendation`, `RiskAssessment`)
- `backend/app/infrastructure/screener/models.py` (existing `ScreenRunResult`, `FilterRunResult`)
- `.planning/phases/06-api-layer/06-RESEARCH.md` section 5 (REST Endpoints Design, lines 527-740) and section 5.2 (Response Envelope Format, lines 578-614)
</read_first>

<action>
Create `backend/app/api/schemas.py` with:

1. **Response Envelope Models:**
   - `MetaInfo` — `timestamp: str`, `request_id: str`, `duration_ms: float | None`
   - `ApiResponse[T]` — generic `data: T`, `meta: MetaInfo`
   - `ApiErrorResponse` — `error: ErrorDetail`
   - `ErrorDetail` — `code: str`, `message: str`, `details: dict[str, Any] | None`, `request_id: str | None`

2. **Screener Schemas:**
   - `ScreenRequest` — frozen, extra="forbid", fields: `config: str`, `symbols: list[str] | None = None`, `timeframes: list[str] | None = None`, `export_format: Literal["json", "csv"] | None = None`
   - `ScreenSymbolResult` — `symbol: str`, `score: float`, `matched_filters: list[str]`, `indicator_values: dict[str, float]`

3. **Backtest Schemas:**
   - `BacktestRequest` — frozen, extra="forbid", fields: `symbols: list[str]`, `start: datetime`, `end: datetime`, `initial_cash: float = 100_000.0`, `fees_bps: float = 10.0`, `slippage_bps: float = 5.0`, `position_sizing: Literal["fixed", "atr", "kelly"] = "fixed"`, `sizing_params: dict[str, Any]`, `signal_params: dict[str, Any]` — with `@field_validator("start", "end")` ensuring UTC
   - `BacktestResultData` — `run_id: str`, `symbol: str`, `timeframe: str`, `metrics: Metrics | None`, `trades_count: int`, `duration_ms: float`

4. **Data/Indicator Schemas:**
   - `IndicatorQueryParams` — `timeframe: str = "1D"`, `indicators: str | None`, `limit: int = 200` (query params via Depends, not body)
   - `OHLCVQueryParams` — `timeframe: str = "1D"`, `start: datetime | None`, `end: datetime | None`, `limit: int = 500`

5. **Risk Schemas:**
   - `RiskVarRequest` — `symbols: list[str] (min_length=1)`, `confidence: float = 0.95`, `method: Literal["historical", "parametric", "monte_carlo"] = "historical"`, `horizon: int = 1`
   - `RiskBetaRequest` — `symbols: list[str] (min_length=1)`, `benchmark: str | None`, `window: int = 60`
   - `RiskCorrelationRequest` — `symbols: list[str] (min_length=2)`, `window: int = 30`, `group_by: str | None`
   - `RiskKellyRequest` — `backtest_run_id: str`, `max_dd_target: float = 0.25`
   - `RiskPositionSizeRequest` — `symbols: list[str]`, `method: Literal["atr", "kelly", "fixed"] = "atr"`, `cash: float = 100_000.0`, `params: dict[str, Any]`
   - `RiskSummaryRequest` — `portfolio_id: str = "default"`, `symbols: list[str] | None`

6. **Health Schema:**
   - `HealthResponse` — `status: str`, `service: str`, `version: str`, `timestamp: str`
   - `HealthCheckDetail` — `database: bool`, `indicator_cache: bool`
   - `ReadinessResponse` — extends HealthResponse with `checks: HealthCheckDetail`

7. **WebSocket Schema:**
   - `WSSubscriptionRequest` — `type: Literal["subscribe", "unsubscribe"]`, `channels: list[str]`
   - `WSSubscriptionChannel` — enum with values: `price`, `indicator`, `signal`, `screener`, `risk`, `backtest`
   - `StreamChannel` — Literal type for channel string patterns

All models must use `model_config = ConfigDict(frozen=True)` where appropriate and `extra="forbid"` for request models. Use `from __future__ import annotations`.
</action>

<acceptance_criteria>
- `backend/app/api/schemas.py` exists and contains all classes listed above
- `python -c "from backend.app.api.schemas import ApiResponse, ScreenRequest, BacktestRequest, IndicatorQueryParams, OHLCVQueryParams, RiskVarRequest, RiskBetaRequest, RiskCorrelationRequest, RiskKellyRequest, RiskPositionSizeRequest, HealthResponse, ApiErrorResponse, ErrorDetail"` succeeds
- `mypy --strict backend/app/api/schemas.py` passes
</acceptance_criteria>

---

### Task 1.3: Create API exception classes and handlers (exceptions.py)

<read_first>
- `.planning/phases/06-api-layer/06-RESEARCH.md` section 10 (Error Handling & Exception Middleware, lines 1749-1867)
- `backend/app/core/logging.py` (for `correlation_id` context var and `get_logger()`)
</read_first>

<action>
Create `backend/app/api/exceptions.py` with:

1. **Exception Classes:**
   - `ApiException(Exception)` — base: `status_code`, `code`, `message`, `details`
   - `NotFoundException(ApiException)` — `(resource, identifier)` -> 404, code="NOT_FOUND"
   - `ValidationException(ApiException)` — 422, code="VALIDATION_ERROR"
   - `RateLimitException(ApiException)` — 429, code="RATE_LIMIT_EXCEEDED"
   - `EngineException(ApiException)` — wraps engine errors: `(engine, original_error)` -> 500, code="{ENGINE}_ERROR"

2. **Exception Handler Registration:**
   - `register_exception_handlers(app: FastAPI)` function that registers:
     - `@app.exception_handler(ApiException)` — returns JSONResponse with `{error: {code, message, details, request_id}}`
     - `@app.exception_handler(Exception)` — fallback: logs full traceback, returns sanitized `INTERNAL_ERROR` (no stack traces)
     - `@app.exception_handler(HTTPException)` — handles FastAPI built-in HTTPExceptions (422 validation) into `{error: {code: "HTTP_ERROR", message, details, request_id}}`

Import `Request` from `fastapi`, `JSONResponse` from `starlette.responses`, `HTTPException` from `fastapi`, `correlation_id` from `backend.app.core.logging`, and `get_logger` from `backend.app.core.logging`.

Set `log.exception` with `path=request.url.path` in the general fallback handler per RESEARCH.md lines 1833-1851.
</action>

<acceptance_criteria>
- `backend/app/api/exceptions.py` exists with all exception classes
- `register_exception_handlers` function exists and is callable
- `python -c "from backend.app.api.exceptions import ApiException, NotFoundException, ValidationException, RateLimitException, EngineException, register_exception_handlers"` succeeds
- `mypy --strict backend/app/api/exceptions.py` passes
</acceptance_criteria>

---

### Task 1.4: Create API middleware (middleware.py)

<read_first>
- `.planning/phases/06-api-layer/06-RESEARCH.md` section 7 (Authentication, lines 1232-1412) and section 8 (Rate Limiting, lines 1416-1506)
- `backend/app/core/logging.py` (for `set_correlation_id()`, `correlation_id`, `get_logger()`)
- `backend/app/core/config.py` (for `settings.api`)
</read_first>

<action>
Create `backend/app/api/middleware.py` with:

1. **TokenBucket** class (simple in-memory token bucket, RESEARCH.md lines 1437-1474):
   - `__init__(self, rate: int, window_s: int = 60)` — rate tokens per window
   - `consume(self, tokens: int = 1) -> bool` — thread-safe with `threading.Lock()`
   - `_refill(self)` — refill based on elapsed time
   - `remaining(self) -> int` — current token count
   - `reset_in(self) -> float` — seconds until full refill

2. **RequestLogMiddleware** (BaseHTTPMiddleware, RESEARCH.md lines 1296-1316):
   - `dispatch(self, request, call_next)` — sets correlation_id via `set_correlation_id()`, times the request, logs `event="http_request"` with `method`, `path`, `status`, `duration_ms`, adds `X-Request-ID` response header
   - Skip logging for `/health`, `/health/ready`, `/metrics` to reduce noise

3. **RateLimitMiddleware** (BaseHTTPMiddleware, RESEARCH.md lines 1319-1388):
   - Per-client token buckets keyed by API key or IP
   - Path-based rate groups: `/api/v1/screen*` -> `rate_limit_screener`, `/api/v1/backtest*` -> `rate_limit_backtest`, `/api/v1/data*` -> `rate_limit_data`, `/api/v1/risk*` -> default `rate_limit`, else default
   - Public paths (`/health`, `/health/ready`, `/docs`, `/redoc`, `/metrics`) skip rate limiting
   - Returns 429 with headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`
   - On success, adds `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` response headers

4. **APIKeyMiddleware** (BaseHTTPMiddleware, RESEARCH.md lines 1248-1283):
   - `PUBLIC_PATHS = {"/health", "/health/ready", "/docs", "/redoc", "/api/v1/openapi.json"}`
   - Skips auth for public paths and `/ws/*` paths
   - If `settings.api.api_keys` is empty -> auth disabled (dev mode)
   - Checks `X-API-Key` header against `settings.api.api_keys` list
   - Returns 401 with `{error: {code: "UNAUTHORIZED", message: "Valid X-API-Key header required"}}` on failure

Use `from __future__ import annotations`. Import `time`, `threading`, `JSONResponse` from `starlette.responses`, `BaseHTTPMiddleware` from `starlette.middleware.base`, `Request`, `Response` from `starlette.requests`/`starlette.responses`.
</action>

<acceptance_criteria>
- `backend/app/api/middleware.py` exists with `TokenBucket`, `RequestLogMiddleware`, `RateLimitMiddleware`, `APIKeyMiddleware`
- `python -c "from backend.app.api.middleware import TokenBucket, RequestLogMiddleware, RateLimitMiddleware, APIKeyMiddleware"` succeeds
- Token bucket: `b = TokenBucket(10, 60); assert b.consume(); ... b.remaining() == 9; b.reset_in() > 0`
- `mypy --strict backend/app/api/middleware.py` passes
</acceptance_criteria>

---

### Task 1.5: Create API dependencies (dependencies.py)

<read_first>
- `backend/app/infrastructure/screener/engine.py` (ScreenEngine — `async def screen()`)
- `backend/app/infrastructure/backtest/engine.py` (BacktestEngine — `async def run(config)`)
- `backend/app/infrastructure/risk/engine.py` (RiskEngine — `async def compute_beta()`, `compute_var()`, etc.)
- `backend/app/infrastructure/screener/cache.py` (IndicatorCache — `async def get_series()`, `async def get_latest()`)
</read_first>

<action>
Create `backend/app/api/dependencies.py` with FastAPI dependency injection functions:

1. `get_screen_engine() -> ScreenEngine` — returns `ScreenEngine()` (async)
2. `get_backtest_engine() -> BacktestEngine` — returns `BacktestEngine()` (async)
3. `get_risk_engine() -> RiskEngine` — returns `RiskEngine()` (async)
4. `get_indicator_cache() -> IndicatorCache` — returns `IndicatorCache()` (async)

Add typed `Annotated` type aliases for cleaner route signatures:
```python
ScreenEngineDep = Annotated[ScreenEngine, Depends(get_screen_engine)]
BacktestEngineDep = Annotated[BacktestEngine, Depends(get_backtest_engine)]
RiskEngineDep = Annotated[RiskEngine, Depends(get_risk_engine)]
IndicatorCacheDep = Annotated[IndicatorCache, Depends(get_indicator_cache)]
```
</action>

<acceptance_criteria>
- `backend/app/api/dependencies.py` exists with all 4 dependency functions and 4 type aliases
- `python -c "from backend.app.api.dependencies import ScreenEngineDep, BacktestEngineDep, RiskEngineDep, IndicatorCacheDep"` succeeds
- `mypy --strict backend/app/api/dependencies.py` passes
</acceptance_criteria>

---

## Wave 2: Core API Routers (Wave 2)

**Dependencies:** Wave 1
**Files modified:** All files under `backend/app/api/routers/`

### Task 2.1: Create router __init__ and health router

<read_first>
- `backend/app/api/exceptions.py` (exception patterns)
- `backend/app/api/schemas.py` (HealthResponse, ReadinessResponse)
- `backend/app/core/database.py` (`get_db()`, `initialize_database()`)
- `.planning/phases/06-api-layer/06-RESEARCH.md` section 9.4 (Health Endpoints, lines 1676-1744)
</read_first>

<action>
Create `backend/app/api/routers/__init__.py` that imports and exports all routers:
```python
from backend.app.api.routers.health import router as health_router
from backend.app.api.routers.screener import router as screener_router
from backend.app.api.routers.backtest import router as backtest_router
from backend.app.api.routers.data import router as data_router
from backend.app.api.routers.risk import router as risk_router

__all__ = [
    "health_router",
    "screener_router",
    "backtest_router",
    "data_router",
    "risk_router",
]
```

Create `backend/app/api/routers/health.py` with:

1. `GET /health` — liveness check. Returns `{"status": "ok", "service": "conflu-api", "version": "0.2.0", "timestamp": "<iso>"}`
2. `GET /health/ready` — readiness check. Verifies DuckDB connectivity via `get_db()` and checks `indicator_values` table exists via `information_schema.tables`. Returns `{"status": "healthy"|"degraded", "service": "conflu-api", "version": "0.2.0", "timestamp": "<iso>", "checks": {"database": true|false, "indicator_cache": true|false}}`. Returns 503 if any check fails.

Use `APIRouter(tags=["health"])`. Raise `JSONResponse` with `status_code=503` for degraded readiness.
</action>

<acceptance_criteria>
- `backend/app/api/routers/__init__.py` exports all 5 router names
- `GET /health` returns 200 with `{"status": "ok"}`
- `GET /health/ready` returns 200/503 with `checks` dict
- `mypy --strict backend/app/api/routers/` passes
</acceptance_criteria>

---

### Task 2.2: Create screener router

<read_first>
- `backend/app/api/schemas.py` (ScreenRequest, ScreenSymbolResult, ApiResponse)
- `backend/app/api/dependencies.py` (ScreenEngineDep)
- `backend/app/infrastructure/screener/engine.py` (ScreenEngine — `async def screen()`, returns `ScreenRunResult`)
- `backend/app/infrastructure/screener/models.py` (ScreenRunResult, FilterRunResult)
- `.planning/phases/06-api-layer/06-RESEARCH.md` section 5.1 — Screener Endpoint (lines 527-539)
</read_first>

<action>
Create `backend/app/api/routers/screener.py`:

```python
router = APIRouter(prefix="/screen", tags=["screener"])
```

1. **`POST /api/v1/screen`** — accepts `ScreenRequest` body, calls `engine.screen(config=request.config, symbols=request.symbols, timeframes=request.timeframes)`, returns `ApiResponse[list[ScreenSymbolResult]]` with `data=symbols` and `meta` containing `screen_name`, `total_symbols`, `symbols_matched`, `duration_ms`, `timestamp`.

Response envelope should use `ScreenSymbolResult` for each entry. The `meta` field should be a dict with:
```python
{
    "screen_name": result.screen_name,
    "total_symbols": result.total_symbols,
    "symbols_matched": result.symbols_matched,
    "duration_ms": result.duration_ms,
    "timestamp": result.timestamp.isoformat(),
}
```

Add OpenAPI metadata: `summary="Run a technical screen"`, `description="Execute a predefined screen configuration against all active symbols..."`, `response_description="Screen results with matched symbols and metadata"`, `status_code=200`.

If `request.export_format == "csv"`, call `engine.screen_to_csv()` and use a `StreamingResponse` with `media_type="text/csv"` instead. If `request.export_format == "json"`, call `engine.screen_to_json()` similarly.

Use `Depends()` for the engine injection.
</action>

<acceptance_criteria>
- `POST /api/v1/screen` endpoint exists, accepts `ScreenRequest` JSON body
- Returns `ApiResponse` with `data` and `meta` fields
- `POST /api/v1/screen` with `{"config": "trend-follower"}` returns 200
- `mypy --strict backend/app/api/routers/screener.py` passes
</acceptance_criteria>

---

### Task 2.3: Create backtest router

<read_first>
- `backend/app/api/schemas.py` (BacktestRequest, BacktestResultData, ApiResponse)
- `backend/app/api/dependencies.py` (BacktestEngineDep)
- `backend/app/infrastructure/backtest/engine.py` (BacktestEngine — `async def run()`, `run_walk_forward()`, `run_monte_carlo()`, returns `BacktestRunRecord`)
- `backend/app/infrastructure/backtest/models.py` (BacktestRunConfig, BacktestRunRecord, OptimizationResult, MCSimulationResult)
- `.planning/phases/06-api-layer/06-RESEARCH.md` section 5.1 — Backtest Endpoints (lines 542-547)
</read_first>

<action>
Create `backend/app/api/routers/backtest.py`:

```python
router = APIRouter(prefix="/backtest", tags=["backtest"])
```

1. **`POST /api/v1/backtest`** — accepts `BacktestRequest`, converts to `BacktestRunConfig` (map `BacktestRequest` fields + generate `run_id` via `uuid4()`), calls `engine.run(config)`, returns `ApiResponse[BacktestResultData]` with `meta` containing `duration_ms`, `symbol`.

2. **`POST /api/v1/backtest/optimize`** — accepts `BacktestRequest`, calls `engine.run_walk_forward(config)`, returns optimization results.

3. **`POST /api/v1/backtest/monte-carlo`** — accepts `BacktestRequest`, calls `engine.run_monte_carlo(config)`, returns MC results.

4. **`GET /api/v1/backtest/{run_id}`** — retrieves a stored backtest result by `run_id` from DuckDB's `backtest_results` table.

5. **`GET /api/v1/backtest/{run_id}/trades`** — retrieves trades for a run.

6. **`GET /api/v1/backtest/{run_id}/equity`** — retrieves equity curve for a run.

For the GET endpoints, query the DuckDB tables directly using `get_db()` dependency.

Add OpenAPI metadata (summary, description) for each endpoint. Use `status_code=200` for POST endpoints, `Depends()` for engine injection.
</action>

<acceptance_criteria>
- All 6 backtest endpoints exist under `/api/v1/backtest*`
- `POST /api/v1/backtest` accepts JSON body and returns 200
- `GET /api/v1/backtest/{run_id}` exists
- `GET /api/v1/backtest/{run_id}/trades` exists
- `GET /api/v1/backtest/{run_id}/equity` exists
- `mypy --strict backend/app/api/routers/backtest.py` passes
</acceptance_criteria>

---

### Task 2.4: Create data router

<read_first>
- `backend/app/api/schemas.py` (IndicatorQueryParams, OHLCVQueryParams, ApiResponse)
- `backend/app/api/dependencies.py` (IndicatorCacheDep)
- `backend/app/infrastructure/screener/cache.py` (IndicatorCache — `async def get_series()`, `get_latest()`)
- `backend/app/core/database.py` (`get_db()`)
- `.planning/phases/06-api-layer/06-RESEARCH.md` section 5.1 — Data Endpoints (lines 556-565)
</read_first>

<action>
Create `backend/app/api/routers/data.py`:

```python
router = APIRouter(prefix="/data", tags=["data"])
```

1. **`GET /api/v1/indicators/{symbol}`** — query params via `Depends(IndicatorQueryParams)`. For each indicator name in the comma-separated `indicators` param, calls `cache.get_series(indicator_name, timeframe, symbol, limit)`. Returns `ApiResponse` with `data: {symbol, timeframe, indicators: {name: [{timestamp, value}, ...]}}`.

2. **`GET /api/v1/indicators`** — bulk indicator endpoint. Accepts `symbols` (comma-separated), `timeframe`, `indicators` query params. Returns indicators for multiple symbols.

3. **`GET /api/v1/data/{symbol}`** — query params via `Depends(OHLCVQueryParams)`. Queries DuckDB `ohlcv` table directly:
   ```sql
   SELECT timestamp, open, high, low, close, volume
   FROM ohlcv
   WHERE symbol = ? AND timeframe = ?
     AND (? IS NULL OR timestamp >= ?)
     AND (? IS NULL OR timestamp <= ?)
   ORDER BY timestamp DESC
   LIMIT ?
   ```
   Returns `ApiResponse` with `data: {symbol, timeframe, candles: [{timestamp, open, high, low, close, volume}, ...]}`.

4. **`GET /api/v1/data/symbols`** — accepts `asset_class` (optional) and `active_only` (default True) query params. Queries `symbol_metadata` table. Returns list of symbols with their asset_class, exchange, tv_ticker metadata.

Add OpenAPI metadata for each endpoint.
</action>

<acceptance_criteria>
- `GET /api/v1/indicators/{symbol}` returns indicator data
- `GET /api/v1/data/{symbol}` returns OHLCV candle data
- `GET /api/v1/data/symbols` returns symbol list
- `mypy --strict backend/app/api/routers/data.py` passes
</acceptance_criteria>

---

### Task 2.5: Create risk router

<read_first>
- `backend/app/api/schemas.py` (RiskVarRequest, RiskBetaRequest, RiskCorrelationRequest, RiskKellyRequest, RiskPositionSizeRequest, RiskSummaryRequest, ApiResponse)
- `backend/app/api/dependencies.py` (RiskEngineDep)
- `backend/app/infrastructure/risk/engine.py` (RiskEngine — `async def compute_beta()`, `compute_var()`, `compute_correlation()`, `compute_kelly()`, `compute_position_size()`, `analyze_portfolio()`)
- `.planning/phases/06-api-layer/06-RESEARCH.md` section 5.1 — Risk Endpoints (lines 568-576)
</read_first>

<action>
Create `backend/app/api/routers/risk.py`:

```python
router = APIRouter(prefix="/risk", tags=["risk"])
```

1. **`GET /api/v1/risk/{symbol}`** — query params: `benchmark`, `window`. Calls `engine.compute_beta([symbol], benchmark, window)`. Returns `ApiResponse` with beta data for the symbol.

2. **`GET /api/v1/risk/beta`** — accepts `RiskBetaRequest` as query params. Calls `engine.compute_beta(...)`. Returns beta data for multiple symbols.

3. **`GET /api/v1/risk/correlation`** — accepts `RiskCorrelationRequest` as query params. Calls `engine.compute_correlation(...)`. Returns correlation matrix.

4. **`GET /api/v1/risk/var`** — accepts `RiskVarRequest` as query params. Calls `engine.compute_var(...)`. Returns VaR/CVaR results.

5. **`POST /api/v1/risk/kelly`** — accepts `RiskKellyRequest` body. Calls `engine.compute_kelly(...)`. Returns Kelly recommendation.

6. **`POST /api/v1/risk/position-size`** — accepts `RiskPositionSizeRequest` body. Calls `engine.compute_position_size(...)`. Returns position sizes.

7. **`GET /api/v1/risk/summary`** — accepts `RiskSummaryRequest` query params. Calls `engine.analyze_portfolio(...)`. Returns full risk assessment.

Add OpenAPI metadata for each endpoint. Use `Depends()` for engine injection.
</action>

<acceptance_criteria>
- All 7 risk endpoints exist under `/api/v1/risk*`
- `GET /api/v1/risk/beta?symbols=AAPL&symbols=MSFT` returns beta data
- `POST /api/v1/risk/kelly` accepts JSON body
- `mypy --strict backend/app/api/routers/risk.py` passes
</acceptance_criteria>

---

## Wave 3: WebSocket Layer (Wave 3)

**Dependencies:** Wave 1
**Files modified:** All files under `backend/app/api/ws/`

### Task 3.1: Create WebSocket manager (manager.py)

<read_first>
- `backend/app/infrastructure/screener/streaming.py` (ConnectionManager — existing Phase 3 pattern)
- `backend/app/infrastructure/risk/streaming.py` (RiskStreamManager — existing Phase 5 pattern)
- `.planning/phases/06-api-layer/06-RESEARCH.md` section 6.3 (WebSocketManager, lines 923-1160)
- `backend/app/core/config.py` (for `settings.api` WS settings)
</read_first>

<action>
Create `backend/app/api/ws/manager.py` with the `WebSocketManager` class (composition-based, RESEARCH.md lines 938-1159):

```python
class WebSocketManager:
    """Unified WebSocket connection manager for all streaming channels.
    
    Single connection pool shared across all channel types.
    Channel-based subscriptions (subscribe/unsubscribe on-the-fly).
    Per-connection sequence numbering.
    History buffer for reconnection replay.
    Background update loops (on-demand: only when clients connected).
    """
```

Fields:
- `_connections: dict[str, Any]` — ws_id -> WebSocket
- `_subscriptions: dict[str, set[str]]` — ws_id -> {channels}
- `_channel_subscribers: dict[str, set[str]]` — channel -> {ws_ids}
- `_sequences: dict[str, int]` — ws_id -> next_seq
- `_history: dict[str, list[dict]]` — ws_id -> [messages]
- `_max_history: int = 100`
- `_background_tasks: dict[str, asyncio.Task]`

Methods:
- `register(ws_id, websocket)` — register connection
- `disconnect(ws_id)` — cleanup subscriptions
- `handle_message(ws_id, websocket, data)` — routes to subscribe/unsubscribe/ping/resync handlers
- `broadcast(channel, message)` — send to all subscribers with sequence numbers, store history
- `start_background_tasks(app)` — launch `_price_update_loop()` and `_indicator_update_loop()`
- `close_all()` — cancel tasks, close connections
- `_handle_subscribe(ws_id, channels)` — subscribe to channels
- `_handle_unsubscribe(ws_id, channels)` — unsubscribe
- `_resync(ws_id, websocket, last_sequence)` — replay missed messages
- `_price_update_loop()` — background: 1s interval, broadcasts to `price:*` channels
- `_indicator_update_loop()` — background: 5s interval, broadcasts to `indicator:*` channels

Export singleton: `ws_manager = WebSocketManager()`.

Import channel providers from `channels.py` for the background loops.
</action>

<acceptance_criteria>
- `backend/app/api/ws/manager.py` exists with `WebSocketManager` class
- `ws_manager` singleton exported
- `python -c "from backend.app.api.ws.manager import ws_manager, WebSocketManager"` succeeds
- `mypy --strict backend/app/api/ws/manager.py` passes
</acceptance_criteria>

---

### Task 3.2: Create WebSocket channels and update providers (channels.py)

<read_first>
- `.planning/phases/06-api-layer/06-RESEARCH.md` section 6.2 (Channel-Based Subscriptions, lines 849-917)
- `backend/app/core/database.py` (`get_db()`)
- `backend/app/infrastructure/screener/cache.py` (IndicatorCache — `async def get_latest()`)
</read_first>

<action>
Create `backend/app/api/ws/channels.py` with:

1. **`_update_providers`** module-level dict: `dict[str, Callable]` mapping channel prefixes to provider functions

2. **`register_update_provider(channel_prefix, provider)`** function to register providers

3. **`price_update_provider(symbol)`** — fetches latest close+volume from DuckDB `ohlcv` table. Returns dict with `symbol`, `price`, `volume`, `timestamp`.

4. **`indicator_update_provider(symbol, indicator_name)`** — fetches latest indicator value via `IndicatorCache.get_latest()`. Returns dict with `symbol`, `indicator`, `value`, `timestamp`.

5. **Channel constants:**
   - `CHANNEL_PRICE = "price"` — `price:{symbol}`
   - `CHANNEL_INDICATOR = "indicator"` — `indicator:{symbol}:{name}`
   - `CHANNEL_SIGNAL = "signal"` — `signal:{symbol}`
   - `CHANNEL_SCREENER = "screener"` — `screener:{name}`
   - `CHANNEL_RISK = "risk"` — `risk:{portfolio}`
   - `CHANNEL_BACKTEST = "backtest"` — `backtest:{run_id}`

All providers use `get_db()` / `IndicatorCache` and are async functions.
</action>

<acceptance_criteria>
- `backend/app/api/ws/channels.py` exists with all channel constants and provider functions
- `python -c "from backend.app.api.ws.channels import CHANNEL_PRICE, CHANNEL_INDICATOR, price_update_provider, indicator_update_provider"` succeeds
- `mypy --strict backend/app/api/ws/channels.py` passes
</acceptance_criteria>

---

### Task 3.3: Create WebSocket route handler (handler.py)

<read_first>
- `backend/app/api/ws/manager.py` (ws_manager singleton)
- `backend/app/core/config.py` (settings.api.api_keys for optional WS auth)
- `.planning/phases/06-api-layer/06-RESEARCH.md` section 6.1 (Single Multiplexed Endpoint, lines 787-846)
</read_first>

<action>
Create `backend/app/api/ws/handler.py`:

```python
ws_router = APIRouter()

@ws_router.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
```

Handler flow:
1. Accept connection: `await websocket.accept()`
2. Generate `ws_id = str(uuid4())`
3. Optionally handle auth message: if client sends `{"type": "auth", "api_key": "..."}`, validate against `settings.api.api_keys` (if keys are configured). Send `AUTH_FAILED` and close with code 4001 on failure.
4. Send `{"type": "connected", "connection_id": ws_id, "timestamp": "...", "server_version": "0.2.0"}`
5. Register via `ws_manager.register(ws_id, websocket)`
6. Main loop: `while True: data = await websocket.receive_json(); await ws_manager.handle_message(ws_id, websocket, data)`
7. Handle `WebSocketDisconnect`: call `ws_manager.disconnect(ws_id)`, log
8. General Exception: log, try close with 1011

Also export `register_ws_routes(app: FastAPI)` function that includes the `ws_router` on the app.

The handler should also update the `ws_connections_gauge` Prometheus metric on connect/disconnect.
</action>

<acceptance_criteria>
- `backend/app/api/ws/handler.py` exists with `ws_router` and `register_ws_routes` function
- WebSocket endpoint exists at `/ws/stream`
- `python -c "from backend.app.api.ws.handler import ws_router, register_ws_routes"` succeeds
- `mypy --strict backend/app/api/ws/handler.py` passes
</acceptance_criteria>

---

### Task 3.4: Create WS __init__

<read_first>
- (No file to read — this is a simple package init)
</read_first>

<action>
Create `backend/app/api/ws/__init__.py`:

```python
"""WebSocket streaming — unified /ws/stream endpoint with channel-based subscriptions.

Usage:
    from backend.app.api.ws.handler import ws_router, register_ws_routes
    from backend.app.api.ws.manager import ws_manager
"""

from backend.app.api.ws.manager import ws_manager

__all__ = [
    "ws_manager",
]
```
</action>

<acceptance_criteria>
- `backend/app/api/ws/__init__.py` exists
- `python -c "from backend.app.api.ws import ws_manager"` succeeds
</acceptance_criteria>

---

## Wave 4: Observability & App Factory (Wave 4)

**Dependencies:** Wave 1, Wave 2, Wave 3
**Files modified:** `backend/app/api/observability.py`, `backend/app/api/main.py`, `pyproject.toml`

### Task 4.1: Create observability module (observability.py)

<read_first>
- `.planning/phases/06-api-layer/06-RESEARCH.md` section 9 (Observability, lines 1510-1665)
- `backend/app/core/config.py` (for `settings.api` OTel and Prometheus settings)
</read_first>

<action>
Create `backend/app/api/observability.py` with:

1. **`setup_prometheus(app: FastAPI)`** (RESEARCH.md lines 1546-1573):
   - Uses `prometheus_fastapi_instrumentator.Instrumentator` with `should_group_status_codes=True`, `should_ignore_untemplated=True`
   - Exposes at `/metrics`
   - Adds custom metrics: `ws_connections_active` (Gauge), `rate_limit_exceeded_total` (Counter with `endpoint_group` label)
   - Register the instrumentator on the app

2. **`setup_opentelemetry(app: FastAPI)`** (RESEARCH.md lines 1629-1665):
   - Creates `TracerProvider` with `Resource(service.name=settings.api.otel_service_name)`
   - If `settings.api.otel_exporter_otlp_endpoint` is set, use `OTLPSpanExporter`; otherwise use `ConsoleSpanExporter`
   - Adds `BatchSpanProcessor` to provider
   - Calls `FastAPIInstrumentor.instrument_app(app)`
   - Note: Wrap in try/except ImportError for optional packages

3. **Global Prometheus metrics** (RESEARCH.md lines 1605-1621):
   - `ws_connections_gauge` — `Gauge("ws_connections_active", ...)`
   - `ws_messages_total` — `Counter("ws_messages_total", ..., labelnames=("channel_type",))`
   - `ws_errors_total` — `Counter("ws_errors_total", ..., labelnames=("error_type",))`

Use `from __future__ import annotations`. Handle imports gracefully (try/except for optional packages).
</action>

<acceptance_criteria>
- `backend/app/api/observability.py` exists with `setup_prometheus` and `setup_opentelemetry` functions
- Exports `ws_connections_gauge`, `ws_messages_total`, `ws_errors_total`
- `python -c "from backend.app.api.observability import setup_prometheus, setup_opentelemetry"` succeeds
- `mypy --strict backend/app/api/observability.py` passes (or has appropriate ignores for optional imports)
</acceptance_criteria>

---

### Task 4.2: Create main.py (app factory)

<read_first>
- All files created in Waves 1-3
- `backend/app/core/config.py` (settings)
- `backend/app/core/database.py` (initialize_database)
- `backend/app/core/logging.py` (configure_logging)
- `.planning/phases/06-api-layer/06-RESEARCH.md` section 3 (FastAPI Application Factory, lines 243-365) and section 4 (Module Structure, lines 421-517)
</read_first>

<action>
Create `backend/app/api/main.py` per RESEARCH.md lines 249-365:

1. **`lifespan(app)`** async context manager:
   - Startup: `configure_logging(log_level=...)`, `initialize_database()`, `setup_prometheus(app)` if enabled, `setup_opentelemetry(app)` if OTLP endpoint configured, `ws_manager.start_background_tasks(app)`
   - Shutdown: `ws_manager.close_all()`, OTel shutdown

2. **`create_app() -> FastAPI`** factory function:
   - Creates FastAPI with `title="conflu.ai API"`, `description="..."`, `version="0.2.0"`, `docs_url="/docs"`, `redoc_url="/redoc"`, `openapi_url="/api/v1/openapi.json"`, `lifespan=lifespan`
   - `openapi_tags=tags_metadata` with health, screener, backtest, data, risk, streaming tags (RESEARCH.md lines 491-517)
   - Middleware (order matters): `CORSMiddleware` (outermost), `RequestLogMiddleware`, `RateLimitMiddleware`, `APIKeyMiddleware` (innermost — closest to handler)
   - Routers: `health_router` (no prefix), `screener_router` (prefix="/api/v1"), `backtest_router` (prefix="/api/v1"), `data_router` (prefix="/api/v1"), `risk_router` (prefix="/api/v1")
   - WebSocket: `register_ws_routes(app)`
   - Exception handlers: `register_exception_handlers(app)`

3. **`app = create_app()`** — module-level FastAPI instance for uvicorn

4. **CLI entry point** (optional but useful):
   ```python
   if __name__ == "__main__":
       import uvicorn
       uvicorn.run(
           "backend.app.api.main:app",
           host=settings.api.host,
           port=settings.api.port,
           reload=True,
       )
   ```
</action>

<acceptance_criteria>
- `backend/app/api/main.py` exists with `create_app()` and `app` singleton
- `python -c "from backend.app.api.main import app; assert hasattr(app, 'routes')"` succeeds
- `app.title == "conflu.ai API"`
- `/docs` and `/redoc` routes exist
- All routers, middleware, and exception handlers registered
- `mypy --strict backend/app/api/main.py` passes (with expected FastAPI/starlette exceptions)
</acceptance_criteria>

---

### Task 4.3: Update pyproject.toml with new dependencies

<read_first>
- `pyproject.toml` (read current dependencies at lines 1-92)
- `.planning/phases/06-api-layer/06-RESEARCH.md` section 13 (Dependencies & pyproject.toml, lines 2107-2159)
</read_first>

<action>
Update `pyproject.toml`:

1. **Add to `[project.dependencies]`:**
   - `prometheus-fastapi-instrumentator = ">=7.0,<8"`

2. **Add optional dependencies for observability (OTel):**
   ```toml
   [project.optional-dependencies]
   observability = [
       "opentelemetry-api>=1.25",
       "opentelemetry-sdk>=1.25",
       "opentelemetry-instrumentation-fastapi>=0.50b",
       "opentelemetry-exporter-otlp>=1.25",
   ]
   ```

3. **Add to `[project.optional-dependencies] test = [...]`:**
   - `"httpx>=0.27"` (for FastAPI TestClient)

4. **Add mypy override for `prometheus_fastapi_instrumentator.*`:**
   ```toml
   [[tool.mypy.overrides]]
   module = "prometheus_fastapi_instrumentator.*"
   ignore_missing_imports = true
   ```
</action>

<acceptance_criteria>
- `pyproject.toml` has `prometheus-fastapi-instrumentator` in `[project.dependencies]`
- `[project.optional-dependencies] observability = [...]` exists with 4 OTel packages
- `[project.optional-dependencies] test` has `httpx>=0.27`
- Mypy override for `prometheus_fastapi_instrumentator.*` exists
</acceptance_criteria>

---

## Verification

After all tasks complete, run these verification steps:

1. **Import check:** `python -c "from backend.app.api.main import app"` succeeds
2. **App startup:** `uvicorn backend.app.api.main:app --host 0.0.0.0 --port 8000 &` starts without errors
3. **Health endpoints:**
   ```bash
   curl http://localhost:8000/health
   # → {"status":"ok","service":"conflu-api","version":"0.2.0",...}
   
   curl http://localhost:8000/health/ready
   # → {"status":"healthy"|"degraded","checks":{...}}
   ```
4. **OpenAPI:**
   ```bash
   curl http://localhost:8000/docs
   # → 200 OK (Swagger UI)
   
   curl http://localhost:8000/api/v1/openapi.json
   # → OpenAPI spec JSON
   ```
5. **CORS headers:**
   ```bash
   curl -H "Origin: http://localhost:5173" -H "Access-Control-Request-Method: GET" -X OPTIONS http://localhost:8000/health
   # → Access-Control-Allow-Origin: http://localhost:5173
   ```
6. **Correlation ID:**
   ```bash
   curl -v http://localhost:8000/health
   # → X-Request-ID header present
   ```
7. **Rate limiting:**
   ```bash
   for i in {1..5}; do curl -v http://localhost:8000/api/v1/backtest 2>&1 | grep "X-RateLimit"; done
   # → X-RateLimit-Remaining decreases with each request
   ```
8. **API key auth (when keys configured):**
   ```bash
   curl -H "X-API-Key: invalid" http://localhost:8000/api/v1/screen
   # → 401 UNAUTHORIZED
   ```
9. **Prometheus metrics:**
   ```bash
   curl http://localhost:8000/metrics
   # → prometheus metric output (not 404)
   ```
10. **Mypy:** `mypy --strict backend/app/api/` passes
11. **Ruff:** `ruff check backend/app/api/` passes
</verification>
