# Phase 3: Screener Engine - Context

**Gathered:** 2026-06-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Multi-timeframe vectorized screening, composable filter pipeline, pre-computed indicator cache in DuckDB, real-time WebSocket streaming. This phase delivers the screener that sits on top of the data ingestion (Phase 2) and feeds backtest (Phase 4) and API (Phase 6).
</domain>

<decisions>
## Implementation Decisions

### Filter Pipeline Architecture
- **D-01:** Composable filter system using vectorized boolean masks on DataFrames. Filters are pure functions: `DataFrame -> DataFrame[bool]` returning a boolean mask. Combinable via AND/OR/NOT operators.
- **D-02:** Five filter categories built-in: Trend (price > EMA200, ADX > 25), Momentum (RSI < 30, MACD crossover), Volume (RVOL > 1.5, OBV slope), Volatility (ATR percentile, BB width), Pattern (engulfing, hammer, doji).
- **D-03:** Filter registry pattern with `@filter` decorator similar to indicator registry. Each filter has metadata: category, params, description, timeframes_supported.
- **D-04:** Filters evaluated on-demand per screen config. No pre-computation of filter results (only indicators are cached).

### Indicator Cache & Materialized Views
- **D-05:** Pre-computed indicators stored as DuckDB materialized views: `CREATE VIEW indicators_rsi_14 AS SELECT symbol, timestamp, rsi_14 FROM ...`. Updated incrementally after each ingestion run.
- **D-06:** Core cached indicators: RSI(14), MACD(12,26,9), EMA(20/50/200), SMA(50/200), ATR(14), ADX(14), OBV, VWAP, BB(20,2), Stoch(14,3,3). Covering 90% of filter needs.
- **D-07:** Materialized view refresh via `REFRESH MATERIALIZED VIEW` (DuckDB) or `CREATE OR REPLACE VIEW` after ingestion completes. Scheduled in Phase 6.

### Multi-Timeframe Broadcasting
- **D-08:** Use vectorbt `Data.pivot()` + broadcasting to align indicators across timeframes. Daily EMA200 broadcast to 4h/1h/15m via forward-fill.
- **D-09:** Screen evaluation runs per timeframe independently, then results joined on symbol. Cross-timeframe rules (e.g., "Daily > EMA200 AND 4h RSI < 30") evaluated as boolean AND of per-timeframe masks.
- **D-10:** Timeframe hierarchy: 1D (trend) → 4h (confirmation) → 1h/15m/5m (entry). Screener evaluates top-down.

### Screen Configuration & Persistence
- **D-11:** Screens defined as JSON/YAML configs: `{name, description, asset_classes, timeframes, filters: [{category, indicator, operator, threshold, timeframe}]}`. Stored in `screens/` directory.
- **D-12:** Built-in screen templates: "Trend Follower", "Mean Reversion", "Breakout", "Volume Surge". User can save/load custom screens.
- **D-13:** Screen results exported to CSV/JSON with columns: symbol, score, matched_filters, indicator_values, timestamp.

### Real-Time WebSocket Streaming
- **D-14:** WebSocket server using FastAPI + uvicorn (already in stack). Endpoint `/api/v1/ws/screener/{screen_id}` streams screen results every 5s (configurable).
- **D-15:** Streaming uses same filter pipeline but on latest cached indicators + live price from tradingview-screener. Delta updates only (changed symbols).
- **D-16:** Client reconnection handled with sequence numbers. Missed updates re-synced on reconnect.

### Performance & Scalability
- **D-17:** Vectorized evaluation: all symbols processed in single DataFrame operation. No loops over symbols.
- **D-18:** Parallel screening per asset class (5 concurrent). Within asset class, chunk by 1000 symbols.
- **D-19:** Target: screen 5000 symbols in <10s (warm cache). <30s cold.

### OpenCode's Discretion
- **D-20:** Exact internal API for filter evaluation engine (class structure, method signatures).
- **D-21:** DuckDB materialized view vs regular view decision (performance vs freshness).
- **D-22:** WebSocket message format (JSON schema) and heartbeat interval.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1-2 Foundations
- `.planning/phases/01-foundation-core-infrastructure/01-CONTEXT.md` — Core decisions D-01 through D-17
- `.planning/phases/02-data-ingestion-pipeline/02-CONTEXT.md` — Data decisions D-01 through D-20
- `.planning/phases/01-foundation-core-infrastructure/01-RESEARCH.md` — Vectorbt, pandas-ta patterns
- `.planning/phases/02-data-ingestion-pipeline/02-RESEARCH.md` — tradingview-screener, DuckDB patterns

### Existing Code Assets
- `backend/app/infrastructure/indicators.py` — `@indicator` decorator, 5 indicators, `compute_all()`
- `backend/app/core/database.py` — `get_db()`, `get_db_async()`, `partition_path()`, `OHLCV_DDL`
- `backend/app/core/config.py` — `DataSettings`DataSettings`, `ComputeSettings`, `IngestionSettings`
- `backend/app/domain/models.py` — `OHLCV`, `Signal`, `ScreenResult` models
- `backend/app/infrastructure/ingest/` — Full ingestion pipeline

### Project Requirements
- `REQUIREMENTS.md` — FR-003 (Multi-Timeframe Screener), NFR-001 (Performance)
- `.planning/ROADMAP.md` — Phase 3 success criteria

### External Documentation
- vectorbt Data & Broadcasting: https://vectorbt.dev
- DuckDB Materialized Views: https://duckdb.org/docs/stable/sql/statements/create_view
- FastAPI WebSockets: https://fastapi.tiangolo.com/advanced/websockets
- pandas boolean indexing: https://pandas.pydata.org/docs/user_guide/indexing.html#boolean-indexing

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (from Phases 1-2)
- `backend/app/infrastructure/indicators.py` — Indicator registry, `compute_all()`, `list_indicators()`
- `backend/app/core/database.py` — DuckDB connection, partition utilities, `initialize_database()`
- `backend/app/domain/models.py` — `OHLCV`, `Signal`, `ScreenResult` Pydantic models
- `backend/app/core/config.py` — Settings classes, YAML loading with env override
- `backend/app/infrastructure/ingest/fetcher.py` — Async chunked fetching pattern with semaphore

### Established Patterns
- `@decorator` registry pattern for pluggable components
- Vectorized pandas/NumPy operations (no loops)
- DuckDB for analytical queries and Parquet I/O
- Async-first with semaphore concurrency control
- Pydantic models for data validation at boundaries

### Integration Points
- Phase 2 ingestion writes Parquet + DuckDB views → Phase 3 reads for screening
- Phase 1 indicator registry provides base indicators → Phase 3 extends with filter logic
- Phase 3 screen results feed Phase 4 backtest + Phase 6 API

</code_context>

<specifics>
## Specific Ideas

- Screen config as versioned YAML files in `config/screens/` — enables Git history and sharing
- Filter DSL: human-readable syntax like `RSI(14) < 30 AND CLOSE > EMA(200)` parsed to boolean masks
- Pre-compute indicators during ingestion (Phase 2) to avoid re-computation during screening
- WebSocket streaming reuses filter engine — just runs on latest cached data + live price
- Export: CSV for Excel, JSON for API consumers

</specifics>

<deferred>
## Deferred Ideas

- Natural language filter builder (Phase 8)
- ML-based filter optimization (Phase 9)
- Distributed screening across workers (Phase 10)
- Real-time order book data integration (future)

None — discussion stayed within phase scope
</deferred>

---

*Phase: 3-Screener Engine*
*Context gathered: 2026-06-19*