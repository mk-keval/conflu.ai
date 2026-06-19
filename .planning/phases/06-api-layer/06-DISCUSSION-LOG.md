# Phase 6: API Layer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-19
**Phase:** 6-api-layer
**Areas discussed:** REST API Design, WebSocket Streaming, Authentication, Rate Limiting, Observability, Error Handling

---

## REST API Design

| Option | Description | Selected |
|--------|-------------|----------|
| FastAPI async endpoints | Native async, auto OpenAPI | ✓ |
| Flask sync + thread pool | Simpler, but blocking | |
| Starlette raw | More control, more boilerplate | |

**User's choice:** FastAPI async endpoints
**Notes:** Versioned under `/api/v1/`. 5 core endpoints: screen, backtest, indicators, risk, data. Pydantic request/response with strict validation. OpenAPI at `/docs`.

---

## WebSocket Streaming

| Option | Description | Selected |
|--------|-------------|----------|
| Single endpoint + channel multiplexing | Single WS, channel-based subscriptions | ✓ |
| Separate WS per feature | Separate endpoints per feature | |
| Server-Sent Events (SSE) | Simpler, unidirectional | |

**User's choice:** Single WebSocket endpoint `/ws/stream` with channel-based subscriptions
**Notes:** Channels: price, indicator, signal, risk, backtest. Delta updates at configurable intervals. Sequence numbers for replay.

---

## Authentication & Authorization

| Option | Description | Selected |
|--------|-------------|----------|
| JWT + API key | Bearer token + API key header | ✓ |
| OAuth2/OIDC | Full identity provider | |
| API key only | Simple header auth | |

**User's choice:** JWT + API key
**Notes:** API key for programmatic access (X-API-Key header). JWT for future multi-user (Bearer token). Phase 6 implements API key only; JWT deferred. Roles: admin, trader, viewer.

---

## Rate Limiting

| Option | Description | Selected |
|--------|-------------|----------|
| Token bucket (SlowAPI) | FastAPI-native, Redis-backed | ✓ |
| Custom token bucket | Custom implementation | |
| Fixed window | Simple but bursty | |

**User's choice:** Token bucket via SlowAPI
**Notes:** Per client (API key or IP). Default: 100 req/min REST, 10 msg/s WS. Configurable per endpoint group. Rate limit headers included.

---

## Observability

| Option | Description | Selected |
|--------|-------------|----------|
| Structured logs + Prometheus + OpenTelemetry | Full stack | ✓ |
| Basic logs + Prometheus | Minimal | |
| Custom metrics only | Basic | |

**User's choice:** Structured JSON logging + Prometheus + OpenTelemetry
**Notes:** Correlation IDs via middleware. Prometheus metrics at `/metrics`. OpenTelemetry auto-instrumentation for FastAPI. Health endpoints: `/health` + `/health/ready`.

---

## Error Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Standardized error envelope + global handler | Consistent, safe | ✓ |
| Custom per-endpoint | Flexible but inconsistent | |
| FastAPI default | Basic | |

**User's choice:** Standardized error envelope + global exception handler
**Notes:** `{error: {code, message, details}}`. No stack traces in production. Custom exceptions for validation, DB, computation errors.

---

## OpenCode's Discretion

- Exact module structure for API package (routers, middleware, schemas, services)
- Choice of rate limiting library (SlowAPI vs custom token bucket)
- WebSocket connection manager implementation (reuse Phase 3/5 patterns vs new)

---

## Deferred Ideas

- OAuth2/OIDC integration (Keycloak, Auth0)
- GraphQL endpoint for flexible querying
-application/json
- gRPC interface for high-performance internal
- WebSocket compression (permessage-deflate)
- API versioning strategy beyond v1
- Advanced rate limiting tiers (premium, enterprise)