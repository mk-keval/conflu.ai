# Phase 1: Foundation & Core Infrastructure - Context

**Gathered:** 2026-06-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish core infrastructure — configuration management, DuckDB connection pool, vectorbt/pandas-ta compute primitives, structured logging, type-safe schemas, test infrastructure. This phase delivers the foundational layer that all subsequent phases depend on.
</domain>

<decisions>
## Implementation Decisions

### Configuration Management
- **D-01:** Use Pydantic Settings (pydantic-settings) for configuration with YAML/TOML support. Environment variables override file config. Config schema: `config.yaml` + `config.local.yaml` (gitignored for secrets).
- **D-02:** Separate configs per layer: `core` (DuckDB, logging), `data` (screener sources, timeframes, assets), `compute` (vectorbt params, pandas-ta indicators), `api` (host, port, CORS, rate limits), `frontend` (WS endpoint, chart config).

### DuckDB & Parquet Storage
- **D-03:** Partitioning scheme: `data/{asset_class}/{year}/{month}/{symbol}_{timeframe}.parquet` — enables partition pruning by asset_class, year, month. Symbol normalized to filesystem-safe (e.g., `BTCUSDT` → `BTCUSDT`, `SPY` → `SPY`).
- **D-04:** DuckDB connection pool using `duckdb.connect()` with thread-local connections. Context manager `get_db()` yields connections. Read-only connections for queries, read-write for ingestion.
- **D-05:** Schema: `CREATE TABLE ohlcv (symbol VARCHAR, timestamp TIMESTAMPTZ, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE, timeframe VARCHAR, asset_class VARCHAR)` with indexes on (symbol, timeframe, timestamp) and (asset_class, year, month).

### Vectorized Compute Primitives (ZERO LOOPS)
- **D-06:** All indicator computations use `pandas_ta` (vectorized) + `vectorbt.Indicators` (broadcasting across symbols/timeframes). NO explicit Python loops over DataFrame rows.
- **D-07:** Indicator registry pattern: `@indicator` decorator registers functions. Each returns a `pl.DataFrame` (Polars) or `pd.DataFrame` with columns: `symbol`, `timestamp`, `indicator_name`, `value`. Computed indicators cached in DuckDB materialized views.
- **D-08:** Multi-timeframe broadcasting via `vectorbt.Data.pivot()` + `vbt.IndicatorsFactory` — compute once on daily, broadcast to 4h/1h/15m using forward-fill.

### Domain Models (Pydantic)
- **D-09:** Core models in `backend/app/domain/models.py`: `OHLCV`, `Signal`, `Position`, `Trade`, `Metrics`, `ScreenResult`, `BacktestConfig`, `RiskParams`. All use `ConfigDict(frozen=True, extra='forbid')` for immutability.
- **D-10:** Timezone-aware timestamps (UTC) using `datetime` with `tzinfo=timezone.utc`. All DataFrame indices are `DatetimeIndex` with UTC.

### Structured Logging
- **D-11:** `structlog` with JSON output, correlation IDs via contextvars. Log levels: DEBUG (compute), INFO (API requests), WARNING (rate limits), ERROR (failures). Fields: `timestamp`, `level`, `logger`, `event`, `correlation_id`, `phase`, `duration_ms`.

### Testing Infrastructure
- **D-12:** `pytest` + `pytest-asyncio` + `hypothesis` for property-based testing. Test fixtures: synthetic OHLCV data (known patterns), DuckDB in-memory, vectorbt portfolio fixtures.
- **D-13:** Property tests for vectorized ops: indicator idempotence, broadcast correctness, partition pruning, signal composition associativity.

### Type Safety
- **D-14:** `mypy --strict` in CI. `pyproject.toml` config: `disallow_untyped_defs = true`, `warn_return_any = true`, `no_implicit_optional = true`. All public APIs fully typed.

### Docker Compose
- **D-15:** `docker-compose.yml` with services: `api` (FastAPI), `worker` (Celery for async tasks), `redis` (cache/queue), `postgres` (optional, for future auth). `Dockerfile` multi-stage: builder → runtime (python:3.11-slim).

### OpenCode's Discretion
- **D-16:** Exact project layout within `backend/app/` (module organization) — follow clean architecture but exact file grouping is flexible.
- **D-17:** Choice between Polars vs Pandas for internal DataFrames — both supported, prefer Polars for performance but Pandas for pandas-ta/vectorbt compatibility.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Vision & Requirements
- `PROJECT.md` — Vision, constraints, success criteria
- `REQUIREMENTS.md` — Functional & non-functional requirements
- `STATE.md` — Project state tracking
- `.planning/ROADMAP.md` — Phase 1 success criteria and dependencies

### Architecture & Standards
- `backend/app/core/` — Configuration, DuckDB pool, logging (to be created)
- `backend/app/domain/` — Pydantic models, validation schemas (to be created)
- `backend/app/infrastructure/` — Data handlers, vectorbt compilers (to be created)
- `backend/app/api/` — FastAPI routers (Phase 6)
- `backend/tests/` — Test infrastructure (to be created)

### External Documentation (to research)
- DuckDB Python API: https://duckdb.org/docs/api/python
- vectorbt Documentation: https://vectorbt.dev
- pandas-ta Documentation: https://github.com/twopirllc/pandas-ta
- Pydantic Settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- structlog: https://www.structlog.org
- mypy strict mode: https://mypy.readthedocs.io/en/stable/command_line.html#cmdoption-mypy-strict

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None yet — greenfield project

### Established Patterns
- Project structure follows clean architecture (domain, infrastructure, api layers)
- Type hints mandatory, mypy strict
- Async-first for all I/O
- Vectorized computation only (no loops)

### Integration Points
- Phase 2 (Data Ingestion) will use DuckDB pool from this phase
- Phase 3 (Screener) will use indicator registry and compute primitives
- Phase 4 (Backtest) will use vectorbt primitives and domain models
- Phase 6 (API) will use config, logging, and domain models

</code_context>

<specifics>
## Specific Ideas

- Use `tradingview-screener` as the primary free data source (no API key needed)
- Partition by asset_class first for query isolation (equities vs crypto vs forex)
- Pre-compute common indicators (RSI, MACD, EMA, ATR) daily and store as materialized views
- Correlation IDs propagated through async contextvars for request tracing

</specifics>

<deferred>
## Deferred Ideas

- Authentication/JWT (Phase 6)
- Celery worker for async backtests (Phase 6)
- PostgreSQL for user data (future)
- Advanced partitioning (Phase 2 optimization)
- Real-time WebSocket server (Phase 3/6)

None — discussion stayed within phase scope
</deferred>

---

*Phase: 1-Foundation & Core Infrastructure*
*Context gathered: 2026-06-18*