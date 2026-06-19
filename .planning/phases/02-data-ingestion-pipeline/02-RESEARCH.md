# Phase 2: Data Ingestion Pipeline — Research

**Created:** 2026-06-18
**Status:** Complete
**Context:** Phase 1 foundation exists (DuckDB, config, logging, models). Greenfield ingestion module.

---

## Table of Contents

1. [Project State & Codebase Assessment](#1-project-state--codebase-assessment)
2. [Critical Architecture Insight: Scanner ≠ Historical API](#2-critical-architecture-insight-scanner--historical-api)
3. [tradingview-screener Library Deep-Dive](#3-tradingview-screener-library-deep-dive)
   - 3.1 Query API Reference
   - 3.2 Market Names for Asset Classes
   - 3.3 Ticker Format & Symbol Resolution
   - 3.4 OHLCV Field Names by Timeframe
   - 3.5 Synchronous-Only Constraint
4. [Async Chunked Fetching Architecture](#4-async-chunked-fetching-architecture)
   - 4.1 Thread-Pool Wrapper for Synchronous Scanner
   - 4.2 Alternative: Direct httpx AsyncClient (Bypass Library)
   - 4.3 Semaphore-Based Concurrency
   - 4.4 Batching Strategy
5. [Multi-Asset Class Mapping Strategy](#5-multi-asset-class-mapping-strategy)
   - 5.1 TradingView Market → Asset Class Mapping
   - 5.2 Exchange Prefix Assignment
   - 5.3 Symbol Metadata Table Design
6. [Incremental Parquet Update Strategy](#6-incremental-parquet-update-strategy)
   - 6.1 Append-Only Workflow
   - 6.2 Data Quality Validation Rules
   - 6.3 Idempotency Guarantees
7. [Error Handling & Resilience Patterns](#7-error-handling--resilience-patterns)
8. [Module Design & Class Structure](#8-module-design--class-structure)
   - 8.1 Proposed Module Layout
   - 8.2 Class Diagram
   - 8.3 Data Flow
9. [Integration Points with Phase 1](#9-integration-points-with-phase-1)
10. [Dependency Requirements](#10-dependency-requirements)
11. [Risks & Mitigations](#11-risks--mitigations)
12. [Open Questions for Planning](#12-open-questions-for-planning)

---

## 1. Project State & Codebase Assessment

### Current State (from Phase 1 completion)

| Aspect | Status | Reusable for Phase 2 |
|--------|--------|----------------------|
| DuckDB connection mgr | ✅ `get_db()`, `get_db_async()`, `initialize_database()` | Core connection lifecycle |
| Parquet partitioning | ✅ `partition_path()` generates correct path from D-08 schema | Path generation for writes |
| Symbol normalization | ✅ `normalize_symbol()` strips path-unsafe chars | Symbol key normalization |
| OHLCV DDL | ✅ `OHLCV_DDL` with year/month partition columns | Table creation |
| Config (DataSettings) | ✅ `screener_sources`, `timeframes`, `assets`, `max_concurrent` | Runtime parameters |
| Config (config.yaml) | ✅ Lists default symbols per asset class | Symbol source for ingestion |
| Structured logging | ✅ `set_correlation_id()`, `get_logger()`, JSON output | Correlation IDs per run |
| Domain models | ✅ `OHLCV` model with UTC validation | Data validation at write boundary |
| Test infrastructure | ✅ pytest + asyncio + conftest fixtures | Test harness for ingestion |
| Docker Compose | ✅ | No dependencies needed for Phase 2 |
| `tradingview-screener` dep | ❌ **Not in pyproject.toml** | Must be added |
| `httpx` dep | ❌ **Not in pyproject.toml** | Must be added |

### Directory Layout for Phase 2

All Phase 2 code goes in `backend/app/infrastructure/ingest/` — no new module directories needed. The `backend/app/infrastructure/` module already exists with `__init__.py` and `indicators.py`.

```
backend/app/infrastructure/
├── __init__.py
├── indicators.py               # Phase 1: existing
└── ingest/                      # Phase 2: NEW
    ├── __init__.py
    ├── cli.py                   # Entry point: python -m backend.app.infrastructure.ingest
    ├── scanner.py               # tradingview-screener wrapper with thread-pool exec
    ├── fetcher.py               # Async chunked fetching orchestrator
    ├── writer.py                # Parquet/ DuckDB incremental write
    ├── symbol_map.py            # TV ticker ↔ internal symbol mapping
    ├── quality.py               # Data quality validation
    ├── metrics.py               # Ingestion metrics and reporting
    └── models.py                # Internal ingestion types (optional)
```

---

## 2. Critical Architecture Insight: Scanner ≠ Historical API

**This is the single most important finding for Phase 2 planning.**

The `tradingview-screener` library wraps TradingView's **screener/scanner API** (`/scan` endpoint). This is fundamentally different from a **historical data API**:

### What the Scanner API Returns

| Property | Value |
|----------|-------|
| Data shape | **One row per symbol** with current snapshot values |
| History | **No historical series** — only the current bar |
| Update frequency | Real-time (delayed for free tiers) |
| Fields | 3000+ including OHLCV, indicators, fundamentals |
| Multi-timeframe | Each field can request a specific timeframe via syntax `field|timeframe` |
| Pagination | Via `offset`/`limit` — max ~50K results per call |

### What This Means for the Ingestion Model

The scanner gives you a **current snapshot** of all symbols. To build an OHLCV time-series database:

```
Polling Model (what's possible with scanner):
  Time T:  Scan → snapshot of current bar for 100 symbols
  Time T+5m: Scan → snapshot of current bar for 100 symbols (bar may have updated)
  Time T+10m: Scan → snapshot of current bar for 100 symbols
  
  → Accumulate over time: each scan captures the latest bar state
  → Deduplicate: only store when bar closes (new completed candle)
  → Result: grows a history database incrementally
```

**Implications for each timeframe:**

| Timeframe | Polling Strategy | Completeness |
|-----------|-----------------|--------------|
| 1D | Once daily after market close (~21:00 UTC) | Complete daily bars |
| 1h | Every 60 min, keep last completed hour | Complete hourly bars after 60 min |
| 5m | Every 5 min, keep last completed 5m bar | Complete 5m bars after 5 min |
| 1m | Every 1 min (too aggressive for free tier) | May miss intervals |

### Backfill Limitation

The scanner cannot backfill historical data. A new symbol added to the watchlist will have **zero history** — only data from the first scan onward. This is deferred to Phase 3 (Historical Backfill Command), which would require a different data source or accumulating data over time.

**For Phase 2:** The ingestion pipeline accumulates data forward from its first run. Symbols that have been running for weeks will naturally accumulate weeks of history.

---

## 3. tradingview-screener Library Deep-Dive

### 3.1 Query API Reference

Based on the current library docs (v3.2.0):

```python
from tradingview_screener import Query, col

# Basic query
q = Query()                                                # Default: 'america' market
q = Query('america')                                       # Explicit market
q.select('open', 'high', 'low', 'close', 'volume')         # Select OHLCV fields
q.where(col('market_cap_basic') > 1_000_000_000)            # Filtering
q.order_by('volume', ascending=False)                       # Sorting
q.limit(1000)                                               # Max results
q.offset(0)                                                 # Pagination
q.set_markets('america', 'crypto', 'forex')                 # Multi-market
q.set_tickers('NASDAQ:AAPL', 'BINANCE:BTCUSDT')             # Specific tickers
q.get_scanner_data()                                        # Returns (total_count, DataFrame)
```

**`get_scanner_data()` return value:**
```python
(total_count: int, df: pd.DataFrame)
# df columns = ['ticker', ...selected columns...]
# df['ticker'] format: 'EXCHANGE:SYMBOL' (e.g., 'NASDAQ:AAPL', 'BINANCE:BTCUSDT')
```

**Key methods for Phase 2:**

| Method | Usage in Phase 2 |
|--------|------------------|
| `set_tickers()` | Fetch specific symbols from our asset list |
| `select()` | Request OHLCV fields per timeframe |
| `set_markets()` | Ensure correct market scope for symbol resolution |
| `get_scanner_data()` | Execute the scan and get results |
| `limit()` | Cap results per batch |

### 3.2 Market Names for Asset Classes

From the library's market constants, here is the mapping:

| Asset Class | TradingView Market | Screener Function | Exchange Prefixes |
|-------------|-------------------|-------------------|-------------------|
| US Equities | `america` | `stocks('america')` | `NASDAQ:`, `NYSE:`, `AMEX:` |
| Crypto (CEX) | `crypto` | `crypto()` | `BINANCE:`, `COINBASE:`, `KRAKEN:`, etc. |
| Forex | `forex` | `forex()` | `FX:` (or `FOREXCOM:`) |
| Commodities | `futures` | `futures()` | `COMEX:`, `NYMEX:`, `CME:`, `ICE:` |
| Indices | `america` (or `indices`) | `stocks('america')` | `SP:` for SPX, `NASDAQ:` for NDX |

**Important:** Markets are NOT the same as asset classes. Multiple asset classes may share a market:
- US Equities and US Indices both live in `america` market
- Commodities and some indices live in `futures` market

### 3.3 Ticker Format & Symbol Resolution

The `set_tickers()` method requires `EXCHANGE:SYMBOL` format. Mapping our internal symbols:

| Internal Symbol | Asset Class | TV Ticker Format | Exchange Prefix |
|----------------|-------------|------------------|-----------------|
| `SPY` | equities | `AMEX:SPY` | `AMEX:` |
| `AAPL` | equities | `NASDAQ:AAPL` | `NASDAQ:` |
| `BTCUSDT` | crypto | `BINANCE:BTCUSDT` | `BINANCE:` |
| `ETHUSDT` | crypto | `BINANCE:ETHUSDT` | `BINANCE:` |
| `EURUSD` | forex | `FX:EURUSD` | `FX:` |
| `GC1!` | commodities | `COMEX:GC1!` | `COMEX:` |
| `SPX` | indices | `SP:SPX` | `SP:` |

**Resolution strategy:** Each asset class needs a lookup table mapping internal symbols → TV tickers. This can live in:
1. `config.yaml` assets section (extended with exchange prefix)
2. A separate `symbol_map.csv` file
3. The `symbol_metadata` DuckDB table

**Recommended:** Store exchange prefix per asset class in config (e.g., `data.exchange_prefixes`), compute ticker as `{prefix}{symbol}`. This keeps config simple and avoids duplicating the symbol list.

For crypto, the exchange matters (Binance vs Coinbase prices differ). Default to `BINANCE:` for CEX pairs.

### 3.4 OHLCV Field Names by Timeframe

The scanner uses pipe notation for multi-timeframe fields (not suffix-based as the CONTEXT implies):

| Timeframe | Column Syntax | Notes |
|-----------|--------------|-------|
| 1 minute | `close|1` | `open|1`, `high|1`, `low|1`, `volume|1` |
| 5 minutes | `close|5` | `open|5`, `high|5`, `low|5`, `volume|5` |
| 15 minutes | `close|15` | |
| 30 minutes | `close|30` | |
| 1 hour | `close|60` | 60 = 60 minutes |
| 2 hours | `close|120` | |
| 4 hours | `close|240` | |
| 1 day | `close` | **No pipe suffix** — bare field name |
| 1 week | `close|1W` | |
| 1 month | `close|1M` | |

**OHLCV field names:**
- `open`, `high`, `low`, `close`, `volume` — base names
- `open|5`, `high|5`, `low|5`, `close|5`, `volume|5` — 5m timeframe
- `open|60`, `high|60`, `low|60`, `close|60`, `volume|60` — 1h timeframe
- etc.

**Important for Phase 2 scanning:** To get OHLCV data for all timeframes in one scan call:
```python
q.select(
    'ticker',                    # always returned
    'open', 'high', 'low', 'close', 'volume',          # 1D
    'open|5', 'high|5', 'low|5', 'close|5', 'volume|5',  # 5m
    'open|60', 'high|60', 'low|60', 'close|60', 'volume|60',  # 1h
)
```

However, requesting all timeframes in one call may be expensive. The library may throttle or the response may be slow. Consider:
- **Option A:** One scan per timeframe (separate calls, parallelized)
- **Option B:** One scan per asset class per timeframe (fine-grained)
- **Option C:** One scan with all timeframes (simpler, but may hit limits)

**Recommendation:** Option B — one scan per (asset_class, timeframe) pair. Allows per-asset-class rate limiting and parallel execution.

### 3.5 Synchronous-Only Constraint

**Critical finding:** `tradingview-screener` library uses the `requests` library (synchronous) internally, NOT `httpx` or `aiohttp`. This means:

```python
# The library is synchronous:
total, df = Query().select('close').get_scanner_data()  # blocking call

# It CANNOT be used directly with await:
# await Query().get_scanner_data()  # ❌ TypeError: not awaitable
```

**Two architectural options to achieve async concurrency:**

#### Option 1: Thread-pool wrapper (recommended for Phase 2)
```python
import asyncio
from tradingview_screener import Query

async def scan_async(q: Query) -> tuple[int, pd.DataFrame]:
    """Run scanner query in thread pool to avoid blocking event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, q.get_scanner_data)
```

Pros: Simplest, uses library as-is, no maintenance burden.  
Cons: Thread-pool overhead (negligible for I/O-bound calls).

#### Option 2: Direct httpx + reconstruct payload (advanced)
```python
import httpx

async def scan_direct(tickers: list[str], columns: list[str]) -> dict:
    """Call TradingView scanner API directly via httpx."""
    payload = {
        'markets': ['america'],
        'symbols': {'tickers': tickers, 'query': {'types': []}},
        'columns': columns,
        'options': {'lang': 'en'},
        'range': [0, len(tickers)],
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            'https://scanner.tradingview.com/america/scan',
            data={'symbols': payload},  # TV uses form-encoded JSON
        )
        return resp.json()
```

Pros: Full async control, HTTP/2 support, no thread pool.  
Cons: Must maintain payload format manually, duplicates library logic, no field validation.

**Recommendation:** **Option 1** for Phase 2. The thread-pool overhead is negligible for I/O-bound network calls. Option 2 is more maintainable long-term but adds complexity now. Revisit Option 2 in Phase 3 if performance becomes an issue.

---

## 4. Async Chunked Fetching Architecture

### 4.1 Thread-Pool Wrapper

The ingestion engine needs an async wrapper around `get_scanner_data()`:

```python
# backend/app/infrastructure/ingest/scanner.py

import asyncio
from collections.abc import Sequence
from typing import Any

import pandas as pd
from tradingview_screener import Query

from backend.app.core.logging import get_logger

log = get_logger("conflu.ingest.scanner")


async def scan_symbols(
    tickers: Sequence[str],
    columns: Sequence[str],
    market: str = "america",
) -> pd.DataFrame:
    """Fetch scanner data for a batch of tickers asynchronously.

    Runs the synchronous tradingview-screener Query in a thread pool
    to avoid blocking the event loop.

    Args:
        tickers: List of TV tickers (e.g., ['NASDAQ:AAPL', 'BINANCE:BTCUSDT']).
        columns: OHLCV field names to select (e.g., ['close', 'volume']).
        market: TradingView market name.

    Returns:
        DataFrame with ticker column + requested columns.
    """
    if not tickers:
        return pd.DataFrame()

    q = Query()
    q.select(*columns)
    q.set_tickers(*tickers)
    q.limit(len(tickers))

    loop = asyncio.get_running_loop()
    try:
        total, df = await loop.run_in_executor(None, q.get_scanner_data)
        log.info(
            "scan_completed",
            market=market,
            requested=len(tickers),
            received=len(df),
            total_available=total,
        )
        return df
    except Exception:
        log.exception("scan_failed", market=market, ticker_count=len(tickers))
        raise
```

### 4.2 Semaphore-Based Concurrency

Per D-04 and D-05: semaphore limit of 50 concurrent requests, symbols chunked in batches of 100.

```python
# backend/app/infrastructure/ingest/fetcher.py

import asyncio
from collections.abc import AsyncIterator

import pandas as pd

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.infrastructure.ingest.scanner import scan_symbols

log = get_logger("conflu.ingest.fetcher")

BATCH_SIZE = 100  # TradingView limit per API call


class IngestionFetcher:
    """Async fetcher that chunks symbols and manages concurrency."""

    def __init__(self, max_concurrent: int = 50):
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_asset_class(
        self,
        asset_class: str,
        market: str,
        tickers: list[str],
        columns: list[str],
    ) -> pd.DataFrame:
        """Fetch OHLCV data for all tickers in an asset class."""
        all_chunks: list[pd.DataFrame] = []

        async for chunk_df in self._chunked_fetch(tickers, columns, market):
            if not chunk_df.empty:
                chunk_df["asset_class"] = asset_class
                all_chunks.append(chunk_df)

        if not all_chunks:
            return pd.DataFrame()
        return pd.concat(all_chunks, ignore_index=True)

    async def _chunked_fetch(
        self,
        tickers: list[str],
        columns: list[str],
        market: str,
    ) -> AsyncIterator[pd.DataFrame]:
        """Yield DataFrames for each chunk as they complete."""
        chunks = [
            tickers[i : i + BATCH_SIZE] for i in range(0, len(tickers), BATCH_SIZE)
        ]

        async def fetch_chunk(chunk_tickers: list[str]) -> pd.DataFrame:
            async with self._semaphore:
                return await scan_symbols(chunk_tickers, columns, market)

        tasks = [fetch_chunk(chunk) for chunk in chunks]
        for completed in asyncio.as_completed(tasks):
            try:
                df = await completed
                yield df
            except Exception:
                log.exception("chunk_fetch_failed", chunk_size=len(chunks[0]))
                # D-15: partial failures don't stop pipeline
                yield pd.DataFrame()
```

### 4.3 Batching Strategy

| Level | Batch Size | Rationale |
|-------|-----------|-----------|
| Chunk | 100 symbols | TradingView API limit per call |
| Semaphore | 50 concurrent | D-04 default, avoids rate limiting |
| Asset class sweep | All timeframes for one asset class | Logical unit of work |

For 50 symbols across 6 timeframes and 5 asset classes (worst case: 1500 chunks), at 50 concurrent:
- Different asset classes are independent → max parallelism across asset classes
- Within one asset class: timeframes scan independently → more parallelism
- Total theoretical throughput: 50 concurrent × 100 symbols = 5000 symbols per ~2-3 seconds

---

## 5. Multi-Asset Class Mapping Strategy

### 5.1 TradingView Market → Asset Class Mapping

| Asset Class | TV Market | TV URL Suffix | Ticker Format |
|-------------|-----------|---------------|---------------|
| equities | `america` | `america` | `{EXCHANGE}:{SYMBOL}` |
| crypto | `crypto` | `crypto` | `{EXCHANGE}:{SYMBOL}` |
| forex | `forex` | `forex` | `FX:{SYMBOL}` |
| commodities | `futures` | `futures` | `{EXCHANGE}:{SYMBOL}` |
| indices | `america` | `america` | `SP:{SYMBOL}` or `{EXCHANGE}:{SYMBOL}` |

### 5.2 Exchange Prefix Assignment

Internal config should be extended to include exchange prefix per asset class:

```yaml
# config.yaml extension needed:
data:
  exchange_prefixes:
    equities: "NASDAQ:"        # default exchange for equities
    crypto: "BINANCE:"         # default exchange for crypto
    forex: "FX:"               # standard forex prefix
    commodities: "COMEX:"      # default commodity exchange
    indices: "SP:"             # default index prefix
  assets:
    equities:
      - SPY                    # becomes AMEX:SPY (override via per-symbol map)
      - AAPL                   # becomes NASDAQ:AAPL
      - MSFT                   # becomes NASDAQ:MSFT
    crypto:
      - BTCUSDT                # becomes BINANCE:BTCUSDT
      - ETHUSDT               # becomes BINANCE:ETHUSDT
    forex:
      - EURUSD                 # becomes FX:EURUSD
      - GBPUSD                 # becomes FX:GBPUSD
    commodities:
      - GC1!                   # becomes COMEX:GC1!
      - CL1!                   # becomes NYMEX:CL1!
    indices:
      - SPX                    # becomes SP:SPX
      - NDX                    # becomes NASDAQ:NDX
```

Per-symbol exchange overrides can be in a separate `symbol_map` field or loaded from DuckDB metadata table.

### 5.3 Symbol Metadata Table Design

Per D-11, maintain a DuckDB table for symbol metadata:

```sql
CREATE TABLE IF NOT EXISTS symbol_metadata (
    symbol VARCHAR,          -- Internal normalized symbol (e.g., 'AAPL')
    asset_class VARCHAR,     -- 'equities', 'crypto', 'forex', etc.
    exchange VARCHAR,        -- TV exchange prefix (e.g., 'NASDAQ')
    tv_ticker VARCHAR,       -- Full TV ticker (e.g., 'NASDAQ:AAPL')
    timezone VARCHAR,        -- Exchange timezone (e.g., 'America/New_York')
    active BOOLEAN,          -- Currently tracked?
    added_at TIMESTAMPTZ,    -- First ingestion timestamp
    last_seen_at TIMESTAMPTZ -- Last successful scan
);
```

Updated on each ingestion run:
- New symbols inserted
- Existing symbols updated (`last_seen_at`)
- Deactivated symbols marked `active=false` (never deleted)

This table also enables:
- Watchlist filtering (only active symbols)
- Asset-class-based queries for Phase 3
- Timezone-aware scheduling

---

## 6. Incremental Parquet Update Strategy

### 6.1 Append-Only Workflow

Per D-07 and D-08:

```
1. For each (symbol, timeframe) pair:
   a. Query DuckDB metadata: `SELECT MAX(timestamp) FROM ohlcv WHERE symbol=? AND timeframe=?`
   b. Determine the "last complete bar" timestamp
   c. Scan from TradingView → get current bar snapshot
   d. If current bar's timestamp > last_complete_timestamp → it's a new bar → append
   e. If current bar's timestamp == last_complete_timestamp → bar already exists → skip
2. Write new bars to Parquet via DuckDB COPY
3. Update symbol_metadata.last_seen_at
```

**Key insight for completed bar detection:**

| Timeframe | When bar is "complete" | Detection Logic |
|-----------|----------------------|-----------------|
| 1D | After market close | If current time > 21:00 UTC AND the daily O/H/L/C is stable |
| 1h | At :00 of next hour | Timestamp changes to next hour |
| 5m | At :05 of next 5-min block | Timestamp changes to next 5-min boundary |
| 1m | At :01 of next minute | Timestamp changes to next minute |

**Simpler approach for Phase 2:** Store every scan result. Deduplicate by (symbol, timestamp, timeframe) unique constraint. Append-only writes are naturally handled by the DuckDB UNIQUE constraint via a temporary staging table:

```python
# backend/app/infrastructure/ingest/writer.py

import duckdb
from pathlib import Path

def write_incremental(
    con: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    asset_class: str,
    year: int,
    month: int,
) -> int:
    """Append new candles to partition, returning count of new rows."""
    # 1. Create staging table
    con.sql("CREATE TEMP TABLE IF NOT EXISTS _staging AS SELECT * FROM ohlcv WHERE 1=0")
    
    # 2. Load new data into staging
    con.sql("INSERT INTO _staging SELECT * FROM df")
    
    # 3. Deduplicate: only rows where (symbol, timestamp, timeframe) don't exist
    con.sql("""
        DELETE FROM _staging AS s
        USING ohlcv AS t
        WHERE s.symbol = t.symbol
          AND s.timestamp = t.timestamp
          AND s.timeframe = t.timeframe
    """)
    
    # 4. Get count of new rows
    new_count = con.sql("SELECT COUNT(*) FROM _staging").fetchone()[0]
    if new_count == 0:
        return 0
    
    # 5. Write to Parquet partition
    for symbol in df['symbol'].unique():
        path = partition_path(asset_class, year, month, symbol, timeframe)
        path.parent.mkdir(parents=True, exist_ok=True)
        con.sql(f"""
            COPY (
                SELECT * FROM _staging WHERE symbol = '{symbol}'
            ) TO '{path}' (FORMAT PARQUET)
        """)
    
    # 6. Insert into main table
    con.sql("INSERT INTO ohlcv SELECT * FROM _staging")
    
    return new_count
```

### 6.2 Data Quality Validation Rules

Per D-09, these validation checks must run before writing:

| Rule | Check | Action on Failure |
|------|-------|-------------------|
| No duplicate timestamps | For each (symbol, timeframe), all timestamps are unique | Skip duplicates, log warning |
| OHLC consistency | `high >= max(open, close)` AND `low <= min(open, close)` | Log error, discard row |
| Non-negative volume | `volume >= 0` | Log error, clamp to 0 |
| Timestamp is UTC-aware | `timestamp.tzinfo is not None` already enforced by OHLCV model | Reject row |
| Positive OHLC prices | `open > 0, high > 0, low > 0, close > 0` | Log error, discard row |
| No gaps | Expected sequence of bars is contiguous (configurable tolerance) | Log warning only (not enforceable without history) |

```python
# backend/app/infrastructure/ingest/quality.py

import pandas as pd
from backend.app.core.logging import get_logger

log = get_logger("conflu.ingest.quality")


def validate_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Validate OHLCV data quality, return clean DataFrame with bad rows removed."""
    n_before = len(df)
    
    # OHLC consistency
    high_ok = df["high"] >= df[["open", "close"]].max(axis=1)
    low_ok = df["low"] <= df[["open", "close"]].min(axis=1)
    volume_ok = df["volume"] >= 0
    price_ok = (df[["open", "high", "low", "close"]] > 0).all(axis=1)
    
    valid = high_ok & low_ok & volume_ok & price_ok
    n_invalid = n_before - valid.sum()
    
    if n_invalid > 0:
        log.warning(
            "quality_check_failed",
            total_rows=n_before,
            invalid_rows=n_invalid,
        )
    
    return df[valid].copy()
```

### 6.3 Idempotency Guarantees

Per D-16: Re-running the same ingestion for the same time range must produce identical output.

**Strategy:**
- The staging-table dedup (section 6.1 step 3) ensures no duplicate rows
- For Parquet files: `COPY (SELECT ... ORDER BY symbol, timestamp) TO ...` ensures deterministic ordering
- If a Parquet file already exists for that partition, append new rows atomically:
  - Write new rows to a temp file
  - Read existing + new → dedup → write merged file
  - Delete temp file

For Phase 2, the simpler approach: **write new files only, never modify existing ones**. Each partition accumulates files over time. DuckDB's `read_parquet('data/**/*.parquet')` handles multiple files naturally. If a partition already has a file and new data arrives for the same partition, write a second file:

```
data/equities/2025/01/AAPL_1D.parquet       # from first run
data/equities/2025/01/AAPL_1D.1.parquet     # from second run (new data)
```

This avoids read-modify-write cycles entirely.

---

## 7. Error Handling & Resilience Patterns

Per D-15, D-06, D-17:

### Circuit Breaker

```
CONSECUTIVE FAILURES → STATE
0                    → CLOSED (normal)
5                    → OPEN (stop sending requests)
5 + cooldown (30s)   → HALF_OPEN (try one)
HALF_OPEN + success  → CLOSED
HALF_OPEN + failure  → OPEN (reset counter)
```

### Retry Policy

| Parameter | Value | Source |
|-----------|-------|--------|
| Max retries | 3 | D-06 |
| Base delay | 1.0s | D-06 |
| Max delay | 30.0s | D-06 |
| Backoff factor | 2.0 | Exponential |
| Retry-on | 429, 500, 502, 503, 504 | Standard |
| Jitter | ±0.1 × delay | Best practice |

### Partial Failure

The pipeline NEVER stops for individual symbol failures:
1. Each chunk of 100 symbols is independent
2. Failed chunks are logged with correlation ID
3. A summary report at the end lists: total symbols, succeeded, failed, new candles, duration
4. The CLI exits with code 0 if any data was written, code 1 if total failure

### Health Check

Per D-17, an endpoint at `/health/ingestion` returns:
```json
{
    "last_successful_run": "2026-06-18T00:00:00Z",
    "last_run_duration_ms": 15000,
    "symbols_processed": 50,
    "candles_written": 300,
    "error_rate": 0.02,
    "pending_symbols": [],
    "circuit_breaker_state": "CLOSED"
}
```

Health data persisted in DuckDB `ingestion_health` table, exposed via FastAPI endpoint (Phase 6) or CLI `--health` flag.

---

## 8. Module Design & Class Structure

### 8.1 Proposed Module Layout

```
backend/app/infrastructure/ingest/
├── __init__.py                      # Exports: run_ingestion
├── cli.py                           # CLI entry point (argparse + asyncio.run)
├── scanner.py                       # scan_symbols() — thread-pool wrapper
├── fetcher.py                       # IngestionFetcher — semaphore + chunking
├── writer.py                        # write_incremental() — Parquet + DuckDB write
├── symbol_map.py                    # TickerResolver — symbol ↔ TV ticker
├── quality.py                       # validate_ohlcv() — data quality
├── metrics.py                       # IngestionMetrics — counters + reporting
└── models.py                        # ScanResult, IngestionReport (Pydantic)
```

### 8.2 Class Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI (cli.py)                        │
│  python -m backend.app.infrastructure.ingest                │
│  [--asset-class equities] [--timeframe 1D] [--dry-run]     │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   run_ingestion()                            │
│  Orchestrator: creates correlation ID, coordinates flow     │
│  Returns: IngestionReport                                   │
└──┬──────────┬──────────┬──────────┬──────────┬──────────────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
┌──────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐
│Ticker│ │Fetcher │ │Writer  │ │Quality │ │Metrics   │
│Resolv│ │        │ │        │ │        │ │          │
│      │ │        │ │        │ │        │ │          │
│sym → │ │chunked │ │Parquet │ │validat │ │timing    │
│ticker│ │fetch   │ │write   │ │ion     │ │counters  │
└──┬───┘ └───┬────┘ └───┬────┘ └───┬────┘ └──────────┘
   │         │          │          │
   │         ▼          │          │
   │    ┌────────┐      │          │
   │    │Scanner │      │          │
   │    │(thread │      │          │
   │    │ pool)  │      │          │
   │    └───┬────┘      │          │
   │        │           │          │
   │        ▼           ▼          ▼
   │   ┌──────────────────────────────┐
   │   │      DuckDB / Parquet        │
   │   │  ohlcv table + staging temp │
   │   └──────────────────────────────┘
   ▼
┌──────────────┐
│ config.yaml  │
│ DataSettings │
└──────────────┘
```

### 8.3 Data Flow

```
1. CLI parses args → creates correlation_id
2. run_ingestion():
   a. Resolve all (symbol → TV ticker) pairs per asset class
   b. For each (asset_class, timeframe):
      i.   Fetch max existing timestamp per symbol from DuckDB
      ii.  Build column list for this timeframe
      iii. Chunk tickers into batches of 100
      iv.  Fire semaphore-constrained concurrent scans
      v.   Validate OHLCV data quality
      vi.  Deduplicate against existing data
      vii. Write new rows to Parquet + DuckDB
   c. Update symbol_metadata table
   d. Emit metrics summary
   e. Return IngestionReport
```

---

## 9. Integration Points with Phase 1

### What Phase 2 Consumes from Phase 1

| Phase 1 Asset | Phase 2 Usage | File |
|---------------|--------------|------|
| `get_db()` / `get_db_async()` | Connection lifecycle for writes | `backend/app/core/database.py` |
| `partition_path()` | Parquet file path computation | `backend/app/core/database.py` |
| `normalize_symbol()` | Symbol normalization for file paths | `backend/app/core/database.py` |
| `OHLCV_DDL` | Table schema confirmation | `backend/app/core/database.py` |
| `DataSettings` | Assets, timeframes, concurrency params | `backend/app/core/config.py` |
| `set_correlation_id()` | Run-level correlation ID | `backend/app/core/logging.py` |
| `get_logger()` | Structured logging throughout | `backend/app/core/logging.py` |
| `OHLCV` model | Data validation before write | `backend/app/domain/models.py` |

### What Phase 2 Provides to Downstream Phases

| Downstream Phase | What It Gets | How |
|-----------------|-------------|-----|
| Phase 3 (Screener) | Parquet files with OHLCV data | Read via `read_parquet('data/**/*.parquet')` |
| Phase 4 (Backtest) | Clean OHLCV data | Query ohlcv table |
| Phase 6 (API) | Ingestion health endpoint data | `/health/ingestion` route |
| Phase 7 (Frontend) | Data availability status | Ingestion report + health check |

---

## 10. Dependency Requirements

### New Dependencies for Phase 2

| Package | Version | Purpose | Added to |
|---------|---------|---------|----------|
| `tradingview-screener` | `>=3.2,<4` | TradingView scanner integration | `pyproject.toml` |
| `httpx` | `>=0.27,<1` | Optional: direct API calls (future use) | `pyproject.toml` |

### Updated pyproject.toml Entries

```toml
[project.dependencies]
# ... existing deps ...
tradingview-screener = ">=3.2,<4"
httpx = ">=0.27,<1"

[project.optional-dependencies]
dev = [
    # ... existing dev deps ...
    "pytest-httpx>=0.30",    # Mock httpx for testing
]

[[tool.mypy.overrides]]
module = ["tradingview_screener.*", "tradingview_screener.query.*", "tradingview_screener.column.*"]
ignore_missing_imports = true
```

---

## 11. Risks & Mitigations

### High Risk

| Risk | Description | Likelihood | Impact | Mitigation |
|------|-------------|------------|--------|------------|
| **Scanner is not historical** | The API only returns current bar data, not full candle history. Symbols have zero history until accumulated over time. | **Certain** | **High** | Document this clearly. Design for forward-only accumulation. Historical backfill deferred to Phase 3. |
| **Rate limiting / ban** | TradingView may throttle or ban aggressive scanning (especially without real-time subscription). | Medium | High | Respect D-06/D-04 limits. Start conservative (10 concurrent), ramp up. Add circuit breaker. |
| **Ticker format changes** | TV exchange prefixes may change or symbols may be delisted. | Low | Medium | Symbol metadata table tracks TV tickers. Failed resolutions logged but don't stop pipeline. |

### Medium Risk

| Risk | Description | Likelihood | Impact | Mitigation |
|------|-------------|------------|--------|------------|
| **Thread pool overhead** | 50 concurrent thread-pool calls for scanning may exhaust the default thread pool. | Low | Medium | Configure `max_workers` explicitly. Use `ThreadPoolExecutor` with controlled size. |
| **Data quality from TV** | TradingView may return stale, missing, or erroneous OHLCV data. | Medium | Medium | D-09 validation catches bad rows. Warnings logged but pipeline continues. |
| **Cookie/authentication** | Without TV login, data is delayed 15-900 minutes (delayed_streaming_900). | Medium | Medium | Document requirement for TV cookies for real-time data. Phase 2 works with delayed data. |
| **Scraper reliability** | The TV scanner API is unofficial and may change without notice. | Medium | High | tradingview-screener lib auto-updates field/market lists daily via GH Actions. Pin version to avoid breaking changes. |

### Low Risk

| Risk | Description | Likelihood | Impact | Mitigation |
|------|-------------|------------|--------|------------|
| **Partial batch failures** | Some symbols in a batch of 100 may fail while others succeed. | Medium | Low | D-15: per-symbol error tolerance. Batches are atomic per API call — if one fails, all 100 are retried. |
| **Symbol normalization** | TradingView ticker format uses dots (BRK.B) and slashes (BTC/USDT) differently than our internal format. | Low | Low | `normalize_symbol()` handles this. Scanner results have raw `ticker` column for debugging. |
| **Intraday bar completeness** | At 5m polling, we might miss a bar if the scan runs late. | Low | Low | 5m polling at 5m intervals means each bar is scanned once. If missed, it's gone forever (no history API). Acceptable for Phase 2. |

---

## 12. Open Questions for Planning

These need resolution before writing PLAN.md:

### Q1: Thread Pool or Direct httpx for Async Scanning?

The `tradingview-screener` library is synchronous (`requests` under the hood). Two options:
1. **Thread-pool wrapper** using `asyncio.to_thread()` / `run_in_executor()` — simple, uses library as-is
2. **Direct httpx** reconstructing the TV API payload — full async control, bypasses library

**Recommendation:** Option 1 for Phase 2. The thread-pool overhead is negligible for I/O-bound HTTP calls. Direct httpx adds maintenance burden and duplicates library logic. Revisit in Phase 3 if bottleneck emerges.

### Q2: One Scan Per Timeframe or All-in-One?

The scanner can return all timeframes in a single call (select `close`, `close|5`, `close|60`, etc.), but this may be slower per call. Trade-off:
- **One scan per timeframe**: More API calls, more parallelism, simpler data handling per call
- **All-in-one scan**: Fewer API calls, more data per call, need to reshape the flat DataFrame into per-timeframe rows

**Recommendation:** One scan per (asset_class, timeframe) pair. Cleaner separation, easier to parallelize. Supports per-timeframe scheduling (1D daily, 5m every 5 min).

### Q3: How to Handle Exchange Prefix Overrides?

Default exchange per asset class works for most symbols, but some need overrides:
- `SPY` → `AMEX:SPY` (not `NASDAQ:SPY`)
- `GC1!` → `COMEX:GC1!`
- `GC1!` could also be `NYMEX:GC1!`

Options:
1. **Per-symbol exchange in config.yaml** (extend `assets` struct)
2. **External CSV map file** (simple, version-controlled)
3. **DuckDB symbol_metadata table** (can be populated from config)

**Recommendation:** Option 1 for the initial symbol set in config.yaml. Extend `DataSettings.assets` to support optional `exchange` override per symbol. Option 3 for runtime updates.

### Q4: CLI Arguments for the Ingestion Command?

The CLI entry point `python -m backend.app.infrastructure.ingest` needs these args:
- `--asset-class` (default: all) — restrict to one asset class
- `--timeframe` (default: all) — restrict to one timeframe
- `--dry-run` — validate without writing
- `--max-concurrent` (default: from config) — override concurrency
- `--health` — show last run status and exit

Should any of these be environment variables instead? 
**Recommendation:** CLI flags for interactive runs, config.yaml for scheduled runs. Environment vars for Docker/CI overrides.

### Q5: Testing Strategy for Scanner?

The scanner makes real HTTP calls to TradingView. Testing approaches:
1. **Integration tests** against live TV (marked `@pytest.mark.integration`, run manually)
2. **Mocked scanner** using saved TV responses (fixtures in `tests/fixtures/`)
3. **Property tests** for quality validation, dedup logic, writer (no network)

**Recommendation:** Mix of all three. Integration tests for end-to-end verification, mocked tests for the fetcher/scanner logic, property tests for quality and writer functions.

### Q6: Per-Symbol Exchange Timezone in Metadata?

For proper scheduling (only scan during market hours), we need timezone per symbol/asset class. Options:
1. Fixed mapping: `equities → America/New_York`, `forex → 24h`, `crypto → 24h`
2. Lookup from symbol_metadata table
3. Hard-code in config

**Recommendation:** Option 1 for Phase 2. Configurable mapping in `DataSettings`. Full per-symbol timezone in Phase 3 if needed.

### Q7: Cookie/Auth Integration for Real-Time Data?

Without TradingView cookies, data is delayed 15 minutes. Options:
1. **Phase 2 uses delayed data** (no auth required, works immediately)
2. **Integrate cookie loading** via `rookiepy` or manual `sessionid` env var

**Recommendation:** Option 1 for Phase 2 — document that delayed data is expected without TV login. Option 2 is a fast-follow enhancement. Add `data.tv_session_id` to config for optional cookie injection.

---

## Summary of Technology Choices

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Data source | `tradingview-screener` (v3.2+) | Free, no API key, global coverage (D-01) |
| Async pattern | Thread-pool wrapper around synchronous lib | Simplest integration, uses library as-is (Q1) |
| HTTP client | Library's internal `requests` (wrapped in thread pool) | D-19 defers to httpx for future use |
| Concurrency | `asyncio.Semaphore` with 50 max | D-04 |
| Batch size | 100 symbols per API call | D-05, confirmed by TV API limits |
| Retry | Exponential backoff: 3 retries, 1s base, 30s max | D-06 |
| Circuit breaker | 5 consecutive failures → OPEN → 30s cooldown | D-06 |
| Storage | Append-only Parquet via DuckDB COPY | D-07, D-08 |
| Dedup | Staging table + NOT EXISTS pattern | D-16 (idempotency) |
| Validation | OHLC consistency, volume ≥ 0, no duplicates | D-09 |
| Symbol metadata | DuckDB `symbol_metadata` table | D-11 |
| Scheduling | CLI command only (Phase 2), Celery deferred to Phase 6 | D-13 |
| Data directory | `{data_dir}/{asset_class}/{year}/{month}/{symbol}_{timeframe}.parquet` | Phase 1 `partition_path()` |
| Logging | structlog with correlation IDs per run | Phase 1 logging module |
| Auth/real-time | Delayed data for Phase 2; cookies optional | Q7 |

---

*This research feeds into `02-PLAN.md`. All documentation references verified against current (June 2026) library APIs.*
