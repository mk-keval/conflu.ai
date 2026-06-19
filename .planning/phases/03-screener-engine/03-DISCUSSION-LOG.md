# Phase 3: Screener Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-19
**Phase:** 3-screener-engine
**Areas discussed:** Filter Pipeline, Indicator Cache, Multi-Timeframe, Screen Config, WebSocket, Performance

---

## Filter Pipeline Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Composable boolean masks | Pure functions DataFrame -> bool mask, AND/OR/NOT | ✓ |
| SQL-based filters | Push down to DuckDB WHERE clauses | |
| Expression trees | Build AST, compile to SQL/NumPy | |

**User's choice:** Composable boolean masks with `@filter` decorator
**Notes:** Five categories: Trend, Momentum, Volume, Volatility, Pattern. Filters return boolean masks. Combinable via AND/OR/NOT.

---

## Indicator Cache & Materialized Views

| Option | Description | Selected |
|--------|-------------|----------|
| DuckDB materialized views | CREATE VIEW, REFRESH after ingestion | ✓ |
| Parquet sidecar files | Separate indicator Parquet per symbol | |
| In-memory cache + periodic flush | Redis/heap cache, flush to DB | |

**User's choice:** DuckDB materialized views (CREATE OR REPLACE VIEW)
**Notes:** Core indicators: RSI, MACD, EMA/SMA, ATR, ADX, OBV, VWAP, BB, Stoch. Refresh after ingestion completes.

---

## Multi-Timeframe Broadcasting

| Option | Description | Selected |
|--------|-------------|----------|
| vectorbt Data.pivot() + broadcasting | Align indicators, forward-fill from daily | ✓ |
| Independent per-timeframe evaluation | Run filters per TF, join on symbol | |
| Resample on-the-fly | resample() in pandas per query | |

**User's choice:** vectorbt broadcasting via Data.pivot()
**Notes:** Hierarchy: 1D (trend) → 4h (confirmation) → 1h/15m (entry). Cross-timeframe rules as boolean AND of per-TF masks.

---

## Screen Configuration & Persistence

| Option | Description | Selected |
|--------|-------------|----------|
| YAML/JSON configs in config/screens/ | Versioned, Git-tracked, shareable | ✓ |
| Database-backed screens | CRUD API, version in DB | |
| Python DSL classes | Type-safe, IDE autocomplete | |

**User's choice:** YAML configs in config/screens/
**Notes:** Built-in templates: Trend Follower, Mean Reversion, Breakout, Volume Surge.

---

## Real-Time WebSocket Streaming

| Option | Description | Selected |
|--------|-------------|----------|
| FastAPI WebSocket endpoint | Native, integrates with existing API | ✓ |
| Separate Socket.io server | More features, separate process | |
| Server-Sent Events (SSE) | Simpler, unidirectional | |

**User's choice:** FastAPI WebSocket (/api/v1/ws/screener/{screen_id})
**Notes:** Streams every 5s, delta updates only. Sequence numbers for reconnection.

---

## Performance & Scalability

| Option | Description | Selected |
|--------|-------------|----------|
| Single DataFrame vectorized ops | All symbols at once, no loops | ✓ |
| Per-symbol chunked processing | Smaller memory footprint | |
| Dask/Ray distributed | Horizontal scaling | |

**User's choice:** Vectorized single DataFrame, parallel per asset class
**Notes:** Target 5000 symbols < 10s warm, < 30s cold.

---

## OpenCode's Discretion

- Exact internal API for filter evaluation engine
- DuckDB materialized view vs regular view (performance vs freshness)
- WebSocket message format and heartbeat interval

---

## Deferred Ideas

- Natural language filter builder (Phase 8)
- ML-based filter optimization (Phase 9)
- Distributed screening across workers (Phase 10)
- Real-time order book data integration (future)