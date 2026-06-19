# Phase 6: API Layer - Context

**Gathered:** 2026-06-19
**Status:** Ready for planning

<domain>
## Phase Boundary

API Layer: FastAPI REST + WebSocket, authentication, rate limiting, observability. This phase exposes all Phase 1-5 capabilities via HTTP and WebSocket interfaces.
</domain>

<decisions>
## Implementation Decisions

### REST API Design
- **D-01:** REST API built on FastAPI with async endpoints. Versioned under `/api/v1/`.
- **D-02:** Core endpoints: `POST /api/v1/screen` (run screener), `POST /api/v1/backtest` (run backtest), `GET /api/v1/indicators/{symbol}` (get indicator values), `GET /api/v1/risk/{symbol}` (get risk metrics), `GET /api/v1/data/{symbol}` (get OHLCV data).
- **D-03:** Request/response models use Pydantic with strict validation. Response envelope: `{data: T, meta: {timestamp, request_id}}`.
- **D-04:** OpenAPI/Swagger auto-generated at `/docs` and `/redoc`. Tags for grouping: screener, backtest, risk, data.

### WebSocket Streaming
- **D-05:** Single WebSocket endpoint: `/ws/stream`. Multiplexed channels via message `type` field.
- **D-06:** Client subscribes to channels via `{"type": "subscribe", "channels": ["price:AAPL", "indicator:AAPL:rsi", "signal:AAPL"]}`.
- **D-07:** Server pushes delta updates (only changed values) at configurable interval (default 1s for price, 5s for indicators).
- **D-08:** Connection lifecycle: handshake → auth (optional) → subscribe → periodic updates → disconnect. Sequence numbers for replay.

### Authentication & Authorization
- **D-09:** JWT-based authentication (optional, for future multi-user). Bearer token in Authorization header.
- **D-10:** API key authentication (simple, for programmatic access). Header: `X-API-Key`.
- **D-11:** Role-based access: `admin` (full), `trader` (read/write own), `viewer` (read-only). Phase 6 implements API key only; JWT deferred.

### Rate Limiting
- **D-12:** Token bucket algorithm per client (by API key or IP). Default: 100 req/min for REST, 10 msg/s for WebSocket.
- **D-13:** Rate limit headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.
- **D-14:** Configurable per endpoint group: screener (stricter), backtest (lenient), data (moderate).

### Observability
- **D-15:** Structured JSON logging with correlation IDs (request_id propagated across async boundaries).
- **D-16:** Prometheus metrics: `http_requests_total`, `http_request_duration_seconds`, `ws_connections_active`, `rate_limit_exceeded_total`.
- **D-17:** OpenTelemetry traces for request/response lifecycle (spans for DB, external calls, computation).
- **D-18:** Health endpoint: `GET /health` (liveness), `GET /health/ready` (readiness with DB check).

### Error Handling
- **D-19:** Standardized error responses: `{error: {code, message, details}}` with appropriate HTTP status codes.
- **D-20:** Global exception handler for validation errors, DB errors, computation errors. No stack traces in production.

### OpenCode's Discretion
- **D-21:** Exact module structure for API package (routers, middleware, schemas, services).
- **D-22:** Choice of rate limiting library (slowapi vs custom token bucket).
- **D-23:** WebSocket connection manager implementation (reuse Phase 3/5 patterns vs new).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1-5 Foundations
- `.planning/phases/01-foundation-core-infrastructure/01-CONTEXT.md` — Core decisions
- `.planning/phases/02-data-ingestion-pipeline/02-CONTEXT.md` — Data ingestion decisions
- `.planning/phases/03-screener-engine/03-CONTEXT.md` — Screener decisions (WebSocket patterns)
- `.planning/phases/04-backtest-engine/04-CONTEXT.md` — Backtest decisions
- `.planning/phases/05-risk-engine/05-CONTEXT.md` — Risk engine decisions

### Existing Code Assets
- `backend/app/infrastructure/screener/streaming.py` — ConnectionManager pattern (reuse for WebSocket)
- `backend/app/infrastructure/risk/streaming.py` — RiskStreamManager pattern (reuse for WebSocket)
- `backend/app/core/config.py` — Settings pattern (extend for API settings)
- `backend/app/core/database.py` — DuckDB connection pool, `get_db()`, `get_db_async()`
- `backend/app/domain/models.py` — Domain models (extend for API request/response)
- `backend/app/infrastructure/backtest/engine.py` — BacktestEngine (consume in API)
- `backend/app/infrastructure/risk/engine.py` — RiskEngine (consume in API)
- `backend/app/infrastructure/screener/engine.py` — ScreenEngine (consume in API)

### Project Requirements
- `REQUIREMENTS.md` — FR-006 (API Layer), NFR-001 (Performance), NFR-002 (Reliability), NFR-003 (Maintainability), NFR-004 (Observability)
- `.planning/ROADMAP.md` — Phase 6 success criteria

### External Documentation
- FastAPI: https://fastapi.tiangolo.com/
- FastAPI WebSockets: https://fastapi.tiangolo.com/advanced/websockets/
- SlowAPI (rate limiting): https://github.com/laurait/slowapi
- Prometheus FastAPI Instrumentator: https://github.com/trallard/prometheus-fastapi-instrumentator
- OpenTelemetry Python: https://opentelemetry.io/docs/instrumentation/python/
- JWT in FastAPI: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (from Phases 1-5)
- `ConnectionManager` in `screener/streaming.py` — WebSocket connection lifecycle, broadcast, subscription management
- `RiskStreamManager` in `risk/streaming.py` — Real-time risk updates, sequence tracking, delta updates
- `ScreenEngine` in `screener/engine.py` — Screener execution, signal generation
- `BacktestEngine` in `backtest/engine.py` — Backtest execution, walk-forward, Monte Carlo
- `RiskEngine` in `risk/engine.py` — Risk analysis, VaR, beta, correlation, Kelly
- `get_db()` / `get_db_async()` — DuckDB connection management
- Settings pattern — Pydantic Settings with YAML + env override

### Established Patterns
- Async-first FastAPI with dependency injection
- Pydantic models for request/response validation
- Structured logging with correlation IDs
- DuckDB connection pool with async wrappers
- Pydantic Settings with YAML + env override
- Structured error handling with custom exceptions

### Integration Points
- Phase 3 Screener → `/api/v1/screen` endpoint, WebSocket `signal` channel
- Phase 4 Backtest → `/api/v1/backtest` endpoint, WebSocket `backtest` channel
- Phase 5 Risk → `/api/v1/risk/{symbol}` endpoint, WebSocket `risk` channel
- Phase 2 Data → `/api/v1/data/{symbol}` and `/api/v1/indicators/{symbol}` endpoints

</code_context>

<specifics>
## Specific Ideas

- Reuse `ConnectionManager` from Phase 3 as base for unified WebSocket manager
- Extend `RiskStreamManager` pattern for unified real-time updates
- Single WebSocket endpoint with channel-based subscriptions
- Request ID propagation via middleware for full traceability
- Rate limiting via SlowAPI (FastAPI native) with Redis backend (optional)
- JWT secret from settings, RSA keys for production
- OpenTelemetry auto-instrumentation for FastAPI + SQLAlchemy + HTTPX

</specifics>

<deferred>
## Deferred Ideas

- OAuth2/OIDC integration (Keycloak, Auth0)
- GraphQL endpoint for flexible querying
- gRPC interface for high-performance internal communication
- WebSocket compression (permessage-deflate)
- API versioning strategy beyond v1
- Advanced rate limiting tiers (premium, enterprise)

None — discussion stayed within phase scope
</deferred>

---

*Phase: 6-API Layer*
*Context gathered: 2026-06-19*