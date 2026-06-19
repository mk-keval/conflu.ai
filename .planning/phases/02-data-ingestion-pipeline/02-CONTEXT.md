# Phase 2: Data Ingestion Pipeline - Context

**Gathered:** 2026-06-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the data ingestion pipeline: tradingview-screener integration, async chunked fetching, incremental Parquet updates, multi-asset support (equities, crypto, forex, commodities, indices). This phase delivers the data layer that feeds the screener (Phase 3) and backtest engine (Phase 4).
</domain>

<decisions>
## Implementation Decisions

### Data Source & tradingview-screener
- **D-01:** Use `tradingview-screener` as primary data source (free, no API key, global coverage). Wrapper handles rate limiting, retries, and error handling.
- **D-02:** Support 5 asset classes: US Equities, Crypto (spot), Forex, Commodities, Indices. Each with separate TradingView scan configs.
- **D-03:** Timeframes: 1m, 5m, 15m, 1h, 4h, 1D. Ingestion prioritized by timeframe (1D first, then intraday).

### Async Chunked Fetching
- **D-04:** Semaphore-based concurrency control (default: 50 concurrent requests). Configurable via `data.max_concurrent`.
- **D-05:** Chunk symbols into batches of 100 per API call (TradingView limit). Process chunks asynchronously.
- **D-06:** Exponential backoff retry (3 retries, base delay 1s, max 30s). Circuit breaker after 5 consecutive failures.

### Incremental Parquet Updates
- **D-07:** Append-only writes. Query existing max timestamp per (symbol, timeframe), fetch only newer candles.
- **D-08:** Use DuckDB `COPY` for bulk Parquet writes. Partition by `asset_class/year/month/symbol_timeframe.parquet`.
- **D-09:** Data quality validation: no duplicate timestamps, OHLC consistency (high >= max(O,C) >= low >= min(O,C)), volume >= 0.

### Symbol Normalization & Mapping
- **D-10:** Map TradingView symbols to internal format: `BTCUSDT` (crypto), `SPY` (equities), `EURUSD` (forex), `GC1!` (commodities), `SPX` (indices).
- **D-11:** Maintain symbol metadata in DuckDB table: `symbol, asset_class, exchange, timezone, active`. Updated on each ingestion run.

### Scheduling & Orchestration
- **D-12:** Daily full refresh (1D timeframe) + incremental intraday updates (configurable interval: 5m default).
- **D-13:** Ingestion runs as standalone CLI command (`python -m backend.app.infrastructure.ingest`) for Phase 2. Later wrapped in Celery worker (Phase 6).
- **D-14:** Progress logging with correlation IDs. Emit metrics: symbols_processed, candles_fetched, bytes_written, duration_ms, errors.

### Error Handling & Resilience
- **D-15:** Partial failures don't stop pipeline. Log failed symbols, continue with rest. Summary report at end.
- **D-16:** Idempotent re-runs: same timestamp range produces identical Parquet files (deterministic ordering).
- **D-17:** Health check endpoint `/health/ingestion` returns last successful run, pending symbols, error rate.

### OpenCode's Discretion
- **D-18:** Exact internal API design for the ingestion module (class structure, method signatures).
- **D-19:** Choice of HTTP client (httpx vs aiohttp) — both work, prefer httpx for simplicity.
- **D-20:** Exact retry/backoff parameters beyond D-06 baseline.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1 Foundations (from prior phase)
- `.planning/phases/01-foundation-core-infrastructure/01-CONTEXT.md` — Core decisions D-01 through D-17
- `.planning/phases/01-foundation-core-infrastructure/01-RESEARCH.md` — Technical research on DuckDB, vectorbt, pandas-ta
- `backend/app/core/config.py` — Config classes (CoreSettings, DataSettings, ComputeSettings)
- `backend/app/core/database.py` — `get_db()`, `partition_path()`, `normalize_symbol()`, `OHLCV_DDL`
- `backend/app/core/logging.py` — `configure_logging()`, `set_correlation_id()`, `get_logger()`
- `backend/app/domain/models.py` — `OHLCV` model (primary output of ingestion)

### Project Requirements
- `REQUIREMENTS.md` — FR-001 (Multi-Asset Data Ingestion), NFR-001 (Performance)
- `.planning/ROADMAP.md` — Phase 2 success criteria and dependencies

### External Documentation
- tradingview-screener: https://github.com/tradingview-screener/tradingview-screener
- DuckDB Python COPY: https://duckdb.org/docs/stable/data/parquet/overview
- httpx async: https://www.python-httpx.org/async/
- asyncio semaphore: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (from Phase 1)
- `backend/app/core/database.py` — DuckDB connection manager, `partition_path()`, `normalize_symbol()`
- `backend/app/core/config.py` — `DataSettings` with `max_concurrent`, `screener_sources`, `timeframes`, `assets`
- `backend/app/core/logging.py` — Structured logging with correlation IDs
- `backend/app/domain/models.py` — `OHLCV` Pydantic model for validation

### Established Patterns
- Async-first I/O with semaphore concurrency control
- Pydantic models for data validation at boundaries
- DuckDB context managers for connection lifecycle
- Correlation IDs propagated through async contextvars

### Integration Points
- Phase 1 `DataSettings` config drives ingestion behavior
- `partition_path()` and `normalize_symbol()` reused for Parquet writes
- `OHLCV` model used for validation before write
- Ingestion metrics logged via Phase 1 logging infrastructure

</code_context>

<specifics>
## Specific Ideas

- Use `tradingview-screener` `Query` class with `set_markets()`, `add_filter()`, `get_scanner_data()`
- Ingestion runs: daily (00:00 UTC) for 1D, every 5m for intraday during market hours
- Store raw TradingView response in `data/raw/` for debugging (optional, can be disabled)
- Symbol metadata table enables future features: watchlists, asset class filtering

</specifics>

<deferred>
## Deferred Ideas

- Real-time WebSocket streaming (Phase 3/6)
- Historical backfill command (Phase 3)
- Celery worker for scheduled ingestion (Phase 6)
- Multiple data source fallback (Alpha Vantage, Yahoo Finance) — future

None — discussion stayed within phase scope
</deferred>

---

*Phase: 2-Data Ingestion Pipeline*
*Context gathered: 2026-06-18*