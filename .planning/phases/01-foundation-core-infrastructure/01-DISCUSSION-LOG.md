# Phase 1: Foundation & Core Infrastructure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-18
**Phase:** 1-foundation-core-infrastructure
**Areas discussed:** Configuration Management, DuckDB & Parquet Storage, Vectorized Compute Primitives, Domain Models, Structured Logging, Testing Infrastructure, Type Safety, Docker Compose

---

## Configuration Management

| Option | Description | Selected |
|--------|-------------|----------|
| Pydantic Settings (YAML + env override) | Type-safe config with validation, env var precedence | ✓ |
| Raw YAML + manual parsing | Simpler but no validation | |
| Python dataclasses + tomllib | Modern but less ecosystem support | |

**User's choice:** Pydantic Settings with YAML + env override
**Notes:** Separate config files per layer (core, data, compute, api, frontend). Local overrides gitignored.

---

## DuckDB & Parquet Storage

| Option | Description | Selected |
|--------|-------------|----------|
| Partition by asset_class/year/month/symbol_timeframe | Enables partition pruning, isolates asset classes | ✓ |
| Partition by symbol only | Simpler but no time-based pruning | |
| Single table with indexes only | No partition pruning, slower for large datasets | |

**User's choice:** asset_class/year/month/symbol_timeframe.parquet
**Notes:** Symbol normalized to filesystem-safe names. Indexes on (symbol, timeframe, timestamp) and (asset_class, year, month).

---

## Vectorized Compute Primitives (ZERO LOOPS)

| Option | Description | Selected |
|--------|-------------|----------|
| pandas-ta + vectorbt IndicatorsFactory | Battle-tested, broadcasting support, zero loops | ✓ |
| Custom NumPy implementations | Full control but reinventing wheels | |
| TA-Lib wrapper | C-speed but dependency complexity | |

**User's choice:** pandas-ta + vectorbt with indicator registry pattern
**Notes:** Indicator registry with @indicator decorator. Multi-timeframe broadcasting via vectorbt.Data.pivot(). Cache in DuckDB materialized views.

---

## Domain Models (Pydantic)

| Option | Description | Selected |
|--------|-------------|----------|
| Frozen Pydantic models (extra='forbid') | Immutable, strict validation, serialization | ✓ |
| Dataclasses with manual validation | Less boilerplate but runtime errors | |
| TypedDict + runtime checks | Lightweight but no validation | |

**User's choice:** Frozen Pydantic models with ConfigDict(frozen=True, extra='forbid')
**Notes:** All timestamps UTC-aware. Models: OHLCV, Signal, Position, Trade, Metrics, ScreenResult, BacktestConfig, RiskParams.

---

## Structured Logging

|Logging

| Option | Description | Selected |
|--------|-------------|----------|
| structlog + JSON + correlation IDs | Industry standard, structured, traceable | ✓ |
| Standard logging + JSON formatter | Basic but less structured | |
| loguru | Nice API but less ecosystem integration | |

**User's choice:** structlog with JSON output, correlation IDs via contextvars
**Notes:** Fields: timestamp, level, logger, event, correlation_id, phase, duration_ms. Levels: DEBUG/INFO/WARNING/ERROR.

---

## Testing Infrastructure

| Option | Description | Selected |
|--------|-------------|----------|
| pytest + pytest-asyncio + hypothesis | Property-based testing for vectorized ops | ✓ |
| unittest + mock | Standard but verbose | |
| pytest only | Missing property-based testing | |

**User's choice:** pytest + pytest-asyncio + hypothesis
**Notes:** Property tests for indicator idempotence, broadcast correctness, partition pruning, signal composition associativity. Fixtures: synthetic OHLCV, in-memory DuckDB, vectorbt portfolio.

---

## Type Safety

| Option | Description | Selected |
|--------|-------------|----------|
| mypy --strict in CI | Maximum safety, catches all type issues | ✓ |
| mypy basic | Less strict, misses issues | |
| pyright only | Good but mypy is project standard | |

**User's choice:** mypy --strict with disallow_untyped_defs, warn_return_any, no_implicit_optional
**Notes:** All public APIs fully typed. pyproject.toml configuration.

---

## Docker Compose

| Option | Description | Selected |
|--------|-------------|----------|
| Multi-stage Dockerfile (builder -> runtime) | Small production image, fast builds | ✓ |
| Single-stage Dockerfile | Simpler but larger images | |
| No Docker, venv only | Not production-ready | |

**User's choice:** Multi-stage Dockerfile with services: api, worker, redis, postgres (optional)
**Notes:** python:3.11-slim base. docker-compose.yml for local dev.

---

## OpenCode's Discretion

- Exact project layout within `backend/app/` (module organization) — follow clean architecture but exact file grouping is flexible.
- Choice between Polars vs Pandas for internal DataFrames — both supported, prefer Polars for performance but Pandas for pandas-ta/vectorbt compatibility.

---

## Deferred Ideas

- Authentication/JWT (Phase 6)
- Celery worker for async backtests (Phase 6)
- PostgreSQL for user data (future)
- Advanced partitioning (Phase 2 optimization)
- Real-time WebSocket server (Phase 3/6)