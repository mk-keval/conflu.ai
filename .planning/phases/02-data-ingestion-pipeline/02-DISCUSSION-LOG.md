# Phase 2: Data Ingestion Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-18
**Phase:** 2-data-ingestion-pipeline
**Areas discussed:** Data Source, Async Fetching, Parquet Updates, Symbol Mapping, Scheduling, Error Handling

---

## Data Source & tradingview-screener

| Option | Description | Selected |
|--------|-------------|----------|
| tradingview-screener | Free, no API key, global coverage | ✓ |
| Alpha Vantage | Free tier limited, requires key | |
| Yahoo Finance (yfinance) | Unofficial, rate limited | |
| Polygon.io | Paid, high quality | |

**User's choice:** tradingview-screener
**Notes:** Wrapper with rate limiting, retries, circuit breaker. Support 5 asset classes.

---

## Async Chunked Fetching

| Option | Description | Selected |
|--------|-------------|----------|
| Semaphore (50 concurrent) | Controlled concurrency, simple | ✓ |
| asyncio.Queue + workers | More complex, backpressure | |
| Unbounded asyncio.gather | Risk of rate limiting | |

**User's choice:** Semaphore 50 concurrent, batches of 100 symbols
**Notes:** Exponential backoff retry (3 retries, base 1s, max 30s). Circuit breaker after 5 failures.

---

## Incremental Parquet Updates

| Option | Description | Selected |
|--------|-------------|----------|
| Append-only (query max timestamp) | Simple, idempotent | ✓ |
| Upsert with MERGE | Complex, DuckDB limited | |
| Full refresh daily | Slow, redundant | |

**User's choice:** Append-only with max timestamp query per (symbol, timeframe)
**Notes:** Data quality validation: no duplicates, OHLC consistency, volume >= 0.

---

## Symbol Normalization & Mapping

| Option | Description | Selected |
|--------|-------------|----------|
| TradingView native format | Direct mapping, preserve exchange info | ✓ |
| Custom internal format | Normalized but loses info | |
| ISIN/CUSIP mapping | Standard but extra lookup | |

**User's choice:** TradingView native format (BTCUSDT, SPY, EURUSD, GC1!, SPX)
**Notes:** Metadata table with exchange, timezone, active flag.

---

## Scheduling & Orchestration

| Option | Description | Selected |
|--------|-------------|----------|
| CLI command (Phase 2) | Simple, manual/ cron | ✓ |
| Celery beat (Phase 6) | Production scheduler | Deferred |
| APScheduler | In-process scheduling | |

**User's choice:** CLI command `python -m backend.app.infrastructure.ingest` for Phase 2
**Notes:** Daily full refresh (1D) + incremental intraday (5m default). Later Celery in Phase 6.

---

## Error Handling & Resilience

| Option | Description | Selected |
|--------|-------------|----------|
| Fail fast on any error | Simple, but loses data | |
| Partial failure tolerance | Log failures, continue | ✓ |
| Retry with exponential backoff | Standard resilience pattern | ✓ |

**User's choice:** Partial failures logged, pipeline continues. Summary report at end.
**Notes:** Idempotent re-runs. Health check endpoint for monitoring.

---

## OpenCode's Discretion

- Exact internal API design for the ingestion module (class structure, method signatures).
- Choice of HTTP client (httpx vs aiohttp) — both work, prefer httpx for simplicity.
- Exact retry/backoff parameters beyond baseline (3 retries, base 1s, max 30s).

---

## Deferred Ideas

- Real-time WebSocket streaming (Phase 3/6)
- Historical backfill command (Phase 3)
- Celery worker for scheduled ingestion (Phase 6)
- Multiple data source fallback (Alpha Vantage, Yahoo Finance) — future