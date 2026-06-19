# Phase 3: Screener Engine — Research

**Created:** 2026-06-19
**Status:** Ready for planning
**Context:** Phase 1 foundation (DuckDB, config, logging, indicators) + Phase 2 ingestion (Parquet OHLCV, symbol metadata) exist.

---

## Table of Contents

1. [Project State & Codebase Assessment](#1-project-state--codebase-assessment)
2. [Critical Architecture Discovery: DuckDB Materialized Views ≠ PostgreSQL](#2-critical-architecture-discovery-duckdb-materialized-views--postgresql)
3. [Filter Pipeline Architecture](#3-filter-pipeline-architecture)
   - 3.1 Vectorized Boolean Mask Pattern
   - 3.2 Filter Registry (`@filter` Decorator)
   - 3.3 Built-in Filter Categories
   - 3.4 Filter Composition (AND/OR/NOT)
   - 3.5 Scoring System
4. [Indicator Cache Strategy](#4-indicator-cache-strategy)
   - 4.1 `indicator_values` Table Design
   - 4.2 Cache Refresh Workflow
   - 4.3 Incremental vs Full Recompute
   - 4.4 What to Cache
5. [Multi-Timeframe Broadcasting](#5-multi-timeframe-broadcasting)
   - 5.1 vectorbt broadcasting vs Pandas reindex/ffill
   - 5.2 Timeframe Hierarchy & Execution Order
   - 5.3 Cross-Timeframe Filter Rules
6. [Screen Configuration & Persistence](#6-screen-configuration--persistence)
   - 6.1 YAML Config Schema
   - 6.2 Built-in Screen Templates
   - 6.3 Screen Loading & Validation
7. [Real-Time WebSocket Streaming](#7-real-time-websocket-streaming)
   - 7.1 FastAPI WebSocket Patterns
   - 7.2 Message Format
   - 7.3 Reconnection & Sequence Numbers
8. [Export Formats](#8-export-formats)
9. [Module Design & Class Structure](#9-module-design--class-structure)
10. [Integration Points with Phases 1 & 2](#10-integration-points-with-phases-1--2)
11. [New Dependencies](#11-new-dependencies)
12. [Risks & Mitigations](#12-risks--mitigations)
13. [Open Questions for Planning](#13-open-questions-for-planning)

---

## 1. Project State & Codebase Assessment

### Current State (after Phase 1 + Phase 2 completion)

| Aspect | Status | Reusable for Phase 3 |
|--------|--------|----------------------|
| DuckDB connection mgr | ✅ `get_db()`, `get_db_async()`, `initialize_database()` | Core connection lifecycle for cache reads |
| Parquet partitioning | ✅ `partition_path()` for `{asset_class}/{year}/{month}/{symbol}_{timeframe}.parquet` | Data source for indicator computation |
| OHLCV DDL | ✅ `ohlcv` table with year/month partition columns | Primary data source |
| Config (`DataSettings`, `ComputeSettings`) | ✅ Assets, timeframes, concurrency, exchange prefixes, indicator settings | Screen runtime params |
| Config (`config.yaml`) | ✅ Exists with default symbols per asset class | Extend with screen config paths |
| Structured logging | ✅ `set_correlation_id()`, `get_logger()`, JSON output | Correlation IDs per screen run |
| Domain models | ✅ `OHLCV`, `Signal`, `ScreenResult`, `BacktestConfig`, `RiskParams` | `ScreenResult` already exists, may need extension |
| Test infrastructure | ✅ pytest + asyncio + conftest fixtures | Test harness for screener |
| Indicator registry | ✅ `@indicator` decorator, 5 indicators: RSI, MACD, EMA, SMA, ATR | Base indicator computation |
| `compute_all()` | ✅ Runs all registered indicators on a DataFrame | Batch indicator computation |
| Ingestion pipeline | ✅ Full async fetch → validate → write → metrics | Data source for screener reads |
| Symbol metadata | ✅ `symbol_metadata` table with exchange, TV ticker, timezone | Screener scope/filtering |
| FastAPI | ❌ **Not wired yet** — `backend/app/api/__init__.py` is empty | Must create WebSocket endpoint |
| `config/screens/` | ❌ **Does not exist** — must be created | Screen config storage |

### Key Insight: What Phase 3 Consumes

Phase 3 is a **read-heavy workload** on top of Phases 1 & 2. It does NOT write new OHLCV data — it reads from the `ohlcv` DuckDB table (populated by Phase 2) and from the existing indicator implementations (Phase 1). The new infrastructure is:

1. **Filter pipeline** — composable boolean masking over indicator values (pure compute)
2. **Indicator cache** — pre-computed indicator values stored in DuckDB (write-once, read-many)
3. **Screen configs** — YAML files describing what to filter
4. **WebSocket streaming** — real-time push of screen results
5. **Export** — CSV/JSON serialization of screen results

### Directory Layout for Phase 3

All Phase 3 code goes in `backend/app/infrastructure/screener/` — a new module alongside `ingest/`:

```
backend/app/infrastructure/
├── __init__.py
├── indicators.py               # Phase 1: existing
├── ingest/                      # Phase 2: existing
└── screener/                    # Phase 3: NEW
    ├── __init__.py              # Exports: run_screen, list_filters, ScreenEngine
    ├── filters.py               # @filter registry + built-in filter functions
    ├── engine.py                # ScreenEngine — orchestrator: load config → get indicators → apply filters → score
    ├── cache.py                 # IndicatorCache — compute + store/retrieve from DuckDB indicator_values table
    ├── broadcasting.py          # Multi-timeframe alignment (vectorbt broadcast + pandas ffill)
    ├── configs.py               # ScreenConfig model, YAML loader, built-in templates
    ├── scoring.py               # Score computation from matched filters
    ├── streaming.py             # WebSocket handler for real-time streaming
    ├── export.py                # CSV/JSON export utilities
    └── models.py                # Screener-specific Pydantic models (ScreenConfig, FilterDef, ScreenRun)
```

---

## 2. Critical Architecture Discovery: DuckDB Materialized Views ≠ PostgreSQL

**This is the single most important finding for Phase 3 planning.**

### The Problem

Decision D-05 states: *"Pre-computed indicators stored as DuckDB materialized views: `CREATE VIEW indicators_rsi_14 AS ...`"*

However, **DuckDB does NOT support PostgreSQL-style materialized views** (`CREATE MATERIALIZED VIEW ... REFRESH MATERIALIZED VIEW`). DuckDB views are always logical (computed on read). There is no `REFRESH MATERIALIZED VIEW` command in DuckDB.

### Options for "Pre-Computed Indicator Cache"

| Option | Description | Read Performance | Write Complexity | Freshness |
|--------|-------------|------------------|-----------------|-----------|
| **A. DuckDB `indicator_values` table** (recommended) | Compute indicators into a regular DuckDB table: `INSERT INTO indicator_values (...)` | Fast (direct table scan) | Moderate (upsert logic) | Controlled by ingestion schedule |
| **B. Standard `CREATE VIEW`** | Define views that compute indicators on read: `CREATE VIEW rsi_14 AS SELECT ...` | Slower (computes each query) | Zero (defined once) | Always fresh |
| **C. Parquet + read** | Write indicator results as Parquet files alongside OHLCV data | Fast (Parquet scan) | Two write paths | Stale until next compute |
| **D. In-memory cache** | Compute on first read, cache in Python dict/`@lru_cache` | Fastest (in-memory) | Manual invalidation | Process lifetime only |

### Recommendation

**Option A: DuckDB `indicator_values` table** — this IS the "materialized cache" even though it's not a SQL materialized view.

Rationale:
- D-05 explicitly wants pre-computed cache for fast reads → table lookup is fastest
- DuckDB tables are columnar and efficient for aggregate reads
- Can be incrementally updated after each ingestion run
- No new infrastructure needed (same DuckDB database)
- Works with DuckDB's multi-version concurrency (readers don't block writers)

```sql
-- The indicator_values table (replaces D-05's materialized views)
CREATE TABLE IF NOT EXISTS indicator_values (
    symbol VARCHAR,
    timestamp TIMESTAMPTZ,
    indicator_name VARCHAR,      -- e.g., 'rsi_14', 'ema_20', 'macd'
    value DOUBLE,
    timeframe VARCHAR,           -- which timeframe this indicator was computed for
    params VARCHAR,              -- JSON string of parameters (e.g., '{"length": 14}')
    computed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_iv_lookup ON indicator_values (symbol, indicator_name, timeframe, timestamp);
CREATE INDEX IF NOT EXISTS idx_iv_indicator ON indicator_values (indicator_name, timeframe);
```

This is a **tall, narrow table** (one row per indicator value per timestamp per symbol). For 5000 symbols × 1D bars × 10 indicators × 365 days = ~18M rows/year. DuckDB handles this easily.

### Alternative: Wide-table materialization for screening performance

For the screening hot path (read all indicators for all symbols at the latest timestamp), a **wide table** with one row per (symbol, timestamp) and columns per indicator may be faster:

```sql
-- Materialized indicator snapshot for screening (optional optimization)
CREATE TABLE IF NOT EXISTS indicator_snapshot (
    symbol VARCHAR,
    timestamp TIMESTAMPTZ,
    timeframe VARCHAR,
    rsi_14 DOUBLE,
    macd DOUBLE,
    macd_signal DOUBLE,
    macd_hist DOUBLE,
    ema_20 DOUBLE,
    ema_50 DOUBLE,
    ema_200 DOUBLE,
    sma_50 DOUBLE,
    sma_200 DOUBLE,
    atr_14 DOUBLE,
    -- plus volatility, volume, pattern indicators
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

**Decision D-20 (OpenCode's discretion):** Start with the tall `indicator_values` table in Phase 3. If screening latency exceeds targets (D-19: 5000 symbols < 10s), add the wide `indicator_snapshot` as an optimization. The `engine.py` should abstract the read path so the storage format can be swapped.

---

## 3. Filter Pipeline Architecture

### 3.1 Vectorized Boolean Mask Pattern

Per D-01: Filters are pure functions returning a boolean mask:

```python
# Every filter signature:
def my_filter(indicator_df: pd.DataFrame, threshold: float, **params) -> pd.Series:
    """Return boolean mask: True where symbol passes filter."""
    ...
```

The mask has the same index as the indicator DataFrame (one entry per symbol). Multiple filters are combined with `&` (AND), `|` (OR), `~` (NOT):

```python
mask1 = rsi_filter(rsi_df, threshold=30)          # RSI < 30 (oversold)
mask2 = volume_filter(volume_df, rvol_threshold=1.5)  # RVOL > 1.5
combined = mask1 & mask2  # Both conditions must be True
```

Key design constraints:
- **Vectorized** — no loops over symbols (D-17)
- **Pure functions** — no side effects, same input → same output
- **Combinable** — AND/OR/NOT operators on boolean Series
- **Null-safe** — NaN values in indicators → False in mask (no match)

### 3.2 Filter Registry (`@filter` Decorator)

Follow the exact pattern from Phase 1's `@indicator` registry in `indicators.py`:

```python
from __future__ import annotations

from functools import wraps
from typing import Any, Callable

import pandas as pd

_FILTER_REGISTRY: dict[str, FilterDef] = {}


@dataclass
class FilterDef:
    """Definition of a registered filter."""
    name: str
    category: str                    # 'trend', 'momentum', 'volume', 'volatility', 'pattern'
    description: str
    func: Callable[..., pd.Series]
    params: list[FilterParam]        # Parameter schemas
    timeframes_supported: list[str]  # e.g., ['1D', '4h', '1h', '15m', '5m']


@dataclass
class FilterParam:
    """A parameter for a filter function."""
    name: str
    type: Literal["float", "int", "str", "bool"]
    default: Any
    description: str


def filter(
    name: str,
    category: str,
    description: str = "",
    params: list[FilterParam] | None = None,
    timeframes_supported: list[str] | None = None,
) -> Callable[[Callable[..., pd.Series]], Callable[..., pd.Series]]:
    """Register a screen filter function.

    The wrapped function must accept a DataFrame of indicator values
    and return a boolean pd.Series (mask) with the same index.

    Args:
        name: Canonical filter name (e.g., 'rsi_oversold').
        category: Filter category ('trend', 'momentum', 'volume', 'volatility', 'pattern').
        description: Human-readable description.
        params: List of parameter definitions for validation/UI.
        timeframes_supported: Timeframes this filter works on (default all).

    Returns:
        A decorator that registers the filter and wraps it for validation.
    """
    def decorator(func: Callable[..., pd.Series]) -> Callable[..., pd.Series]:
        _FILTER_REGISTRY[name] = FilterDef(
            name=name,
            category=category,
            description=description or func.__doc__ or "",
            func=func,
            params=params or [],
            timeframes_supported=timeframes_supported or ["1D", "4h", "1h", "15m", "5m"],
        )

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> pd.Series:
            result = func(*args, **kwargs)
            if not isinstance(result, pd.Series) or result.dtype != bool:
                msg = f"Filter '{name}' must return a boolean Series, got {type(result)}"
                raise ValueError(msg)
            return result

        return wrapper

    return decorator
```

### 3.3 Built-in Filter Categories

Per D-02, five initial categories. Here is the proposed filter list with indicator dependencies:

#### Trend Filters

| Filter Name | Indicator Dependency | Logic | Timeframes |
|-------------|---------------------|-------|------------|
| `price_above_ema` | `ema_20`, `ema_50`, `ema_200` | `close > ema_N` | All |
| `price_below_ema` | `ema_20`, `ema_50`, `ema_200` | `close < ema_N` | All |
| `adx_trending` | `adx_14` | `adx > threshold` (default 25) | 1D, 4h, 1h |
| `adx_non_trending` | `adx_14` | `adx < threshold` (default 20) | 1D, 4h, 1h |
| `ema_cross` | `ema_50`, `ema_200` | `ema_50 crosses_above/below ema_200` | 1D |

#### Momentum Filters

| Filter Name | Indicator Dependency | Logic | Timeframes |
|-------------|---------------------|-------|------------|
| `rsi_oversold` | `rsi_14` | `rsi < threshold` (default 30) | All |
| `rsi_overbought` | `rsi_14` | `rsi > threshold` (default 70) | All |
| `rsi_range` | `rsi_14` | `low < rsi < high` | All |
| `macd_bullish` | `macd`, `macd_signal` | `macd > macd_signal` | All |
| `macd_bearish` | `macd`, `macd_signal` | `macd < macd_signal` | All |
| `macd_histogram_rising` | `macd_hist` | current `macd_hist > previous macd_hist` | All |

#### Volume Filters

| Filter Name | Indicator Dependency | Logic | Timeframes |
|-------------|---------------------|-------|------------|
| `rvol_high` | `volume` (from OHLCV) | `volume / avg_volume(20) > threshold` (default 1.5) | All |
| `rvol_low` | `volume` (from OHLCV) | `volume / avg_volume(20) < threshold` (default 0.5) | All |
| `obv_slope_positive` | `obv` | `OBV slope > 0 over lookback period` | 1D, 4h, 1h |
| `obv_divergence` | `obv`, `close` | Price up + OBV down (bearish divergence) | 1D |

#### Volatility Filters

| Filter Name | Indicator Dependency | Logic | Timeframes |
|-------------|---------------------|-------|------------|
| `atr_percentile_high` | `atr_14` | `ATR > percentile_threshold` (e.g., 75th percentile) | All |
| `atr_percentile_low` | `atr_14` | `ATR < percentile_threshold` (e.g., 25th percentile) | All |
| `bb_width_expanding` | `bb_lower`, `bb_upper`, `bb_middle` | Bollinger Band width increasing | 1D, 4h |
| `bb_inside` | `bb_lower`, `bb_upper` | Price inside bands | All |
| `bb_touch` | `bb_lower`, `bb_upper` | Price touches/breaks outer band | All |

#### Pattern Filters

| Filter Name | Indicator Dependency | Logic | Timeframes |
|-------------|---------------------|-------|------------|
| `candle_engulfing` | OHLCV | Bullish or bearish engulfing pattern | All |
| `candle_hammer` | OHLCV | Hammer pattern (long lower wick) | 1D, 4h |
| `candle_doji` | OHLCV | Doji pattern (open ≈ close) | All |
| `candle_three_white` | OHLCV | Three white soldiers (bullish) | 1D |
| `candle_three_black` | OHLCV | Three black crows (bearish) | 1D |

**Critical note on pattern filters:** Full candlestick pattern detection requires the raw OHLCV data, not pre-computed indicators. These filters receive the OHLCV DataFrame directly (or the relevant columns), not the `indicator_values` table. This means the filter function signature needs flexibility:

```python
@filter(name="candle_engulfing", category="pattern", timeframes_supported=["1D", "4h", "1h"])
def engulfing_filter(
    ohlcv: pd.DataFrame,
    direction: str = "bullish",
) -> pd.Series:
    """Detect bullish/bearish engulfing patterns.

    Bullish engulfing: current open < previous close AND current close > previous open.
    """
    prev = ohlcv.shift(1)
    if direction == "bullish":
        return (ohlcv["open"] < prev["close"]) & (ohlcv["close"] > prev["open"])
    else:
        return (ohlcv["open"] > prev["close"]) & (ohlcv["close"] < prev["open"])
```

### 3.4 Filter Composition (AND/OR/NOT)

A `FilterPipeline` class composes multiple filters:

```python
@dataclass
class FilterExpression:
    """A single filter with its parameters and optional negation."""
    filter_name: str
    params: dict[str, Any] = field(default_factory=dict)
    negate: bool = False  # NOT operator


@dataclass
class FilterGroup:
    """A group of filters combined with AND/OR."""
    operator: Literal["AND", "OR"]
    expressions: list[FilterExpression | FilterGroup]  # recursive nesting
```

The engine evaluates a `FilterGroup` recursively:

```python
class FilterPipeline:
    def evaluate(self, group: FilterGroup, data: dict[str, pd.DataFrame]) -> pd.Series:
        """Evaluate a filter group against indicator data."""
        masks: list[pd.Series] = []
        for expr in group.expressions:
            if isinstance(expr, FilterGroup):
                mask = self.evaluate(expr, data)
            else:
                mask = self._run_filter(expr, data)
            masks.append(mask)

        if group.operator == "AND":
            result = masks[0]
            for m in masks[1:]:
                result = result & m
        else:  # OR
            result = masks[0]
            for m in masks[1:]:
                result = result | m

        return result
```

### 3.5 Scoring System

Per D-13: Each screen result has a `score` (0–100). Two approaches:

**Approach A: Fraction-based** (recommended for Phase 3)
```
score = (matched_filters / total_filters) × 100
```
Simple, transparent, easy to explain. A symbol that matches 4 out of 5 filters → score 80.

**Approach B: Weighted** (deferred)
```
score = Σ(weight_i × matched_i) / Σ(weight_i) × 100
```
Each filter has a weight (configurable in YAML). Allows prioritizing certain conditions.

**Recommendation:** Start with Approach A. Add weights in Phase 8 if needed.

```python
def compute_score(mask: pd.Series, total_filters: int) -> pd.Series:
    """Compute fractional score for each symbol.

    Args:
        mask: Boolean Series where True means the symbol passed all filters.
        total_filters: Total number of filter expressions (count, not groups).

    Returns:
        Series with float scores 0.0–100.0. Since all filters are AND-combined,
        this is binary: 100.0 if all pass, 0.0 otherwise.
        For per-filter scoring, track individual filter results.
    """
    # Phase 3 simplification: AND-combined filters → binary result
    return mask.astype(float) * 100.0
```

For Phase 3 with AND-only composition, the score is binary (100 if all pass, 0 otherwise). When OR groups are introduced, scores become more nuanced. Track `per_filter_results` as a dict of `{filter_name: boolean_mask}` for future scoring flexibility.

---

## 4. Indicator Cache Strategy

### 4.1 `indicator_values` Table Design

As discussed in [Section 2](#2-critical-architecture-discovery-duckdb-materialized-views--postgresql), the cache is a DuckDB table, not a materialized view.

```sql
-- Core indicator cache table (tall format)
CREATE TABLE IF NOT EXISTS indicator_values (
    symbol VARCHAR,
    timestamp TIMESTAMPTZ,
    indicator_name VARCHAR,       -- e.g., 'rsi_14', 'ema_20', 'macd_line'
    value DOUBLE,
    timeframe VARCHAR,            -- '1D', '4h', '1h', etc.
    params VARCHAR,               -- JSON: {"length": 14, "fast": 12, ...}
    computed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_iv_lookup ON indicator_values (symbol, indicator_name, timeframe, timestamp);
CREATE INDEX IF NOT EXISTS idx_iv_scan ON indicator_values (indicator_name, timeframe, timestamp DESC);

-- Optional: wide snapshot table for screening performance
-- Added only if tall-table reads are too slow for D-19
CREATE TABLE IF NOT EXISTS indicator_snapshot (
    symbol VARCHAR,
    timestamp TIMESTAMPTZ,
    timeframe VARCHAR DEFAULT '1D',
    rsi_14 DOUBLE,
    macd_line DOUBLE,
    macd_signal DOUBLE,
    macd_hist DOUBLE,
    ema_20 DOUBLE,
    ema_50 DOUBLE,
    ema_200 DOUBLE,
    sma_50 DOUBLE,
    sma_200 DOUBLE,
    atr_14 DOUBLE,
    obv DOUBLE,
    vwap DOUBLE,
    bb_lower_20 DOUBLE,
    bb_middle_20 DOUBLE,
    bb_upper_20 DOUBLE,
    stoch_k_14 DOUBLE,
    stoch_d_14 DOUBLE,
    adx_14 DOUBLE,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_is_scan ON indicator_snapshot (timeframe, symbol);
```

### 4.2 Cache Refresh Workflow

The `IndicatorCache` class orchestrates computation:

```
1. Trigger: after Phase 2 ingestion run completes
   └─ Or: explicit call to update_cache()

2. For each timeframe:
   a. Query ohlcv table: get latest bars for all symbols up to MAX(timestamp)
   b. For each registered indicator:
      - Query indicator_values: get MAX(timestamp) per symbol for this indicator
      - Compute only rows where ohlcv.timestamp > cached.timestamp (incremental)
      - Insert new rows into indicator_values

3. Optionally rebuild indicator_snapshot wide table
```

```python
class IndicatorCache:
    """Pre-compute and store indicator values in DuckDB."""

    def __init__(self) -> None:
        self._log = get_logger("conflu.screener.cache")

    async def update_cache(
        self,
        timeframes: list[str] | None = None,
        indicator_names: list[str] | None = None,
    ) -> int:
        """Refresh indicator cache incrementally after ingestion.

        Args:
            timeframes: Timeframes to update (default: all configured).
            indicator_names: Indicators to compute (default: all registered).

        Returns:
            Number of new indicator values written.
        """
        # 1. Get the latest ohlcv data per (symbol, timeframe)
        # 2. For each indicator, compute values for new bars only
        # 3. Insert into indicator_values table
        # 4. Optionally update indicator_snapshot
        ...

    async def get_latest(
        self,
        indicator_name: str,
        timeframe: str = "1D",
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        """Get latest indicator values for all symbols.

        Returns DataFrame with columns: symbol, timestamp, value
        One row per symbol (latest timestamp).
        """
        ...

    async def get_series(
        self,
        indicator_name: str,
        timeframe: str = "1D",
        symbol: str | None = None,
        limit: int = 500,
    ) -> pd.DataFrame:
        """Get time series for an indicator.

        Returns DataFrame with columns: symbol, timestamp, value
        """
        ...
```

### 4.3 Incremental vs Full Recompute

**Incremental** (default for Phase 3):
- Query `MAX(timestamp)` per (symbol, indicator_name, timeframe) from `indicator_values`
- Query `ohlcv` for rows with `timestamp > MAX(cached)` per symbol
- Compute indicator on delta only
- Insert new rows
- **Pros:** Fast, minimal work per ingestion cycle
- **Cons:** Must handle the case where indicator parameters change (e.g., RSI length changes from 14 to 21) — then a full recompute is needed

**Full recompute** (on config change or explicit rebuild):
- Delete all rows for the indicator from `indicator_values`
- Recompute from scratch for all symbols and timestamps
- **Pros:** Ensures consistency after parameter changes
- **Cons:** Expensive for large datasets

**Recommendation:** Default to incremental. Provide `cache.rebuild(indicator_name)` for full recompute on parameter changes. Detect parameter changes by comparing stored `params` JSON with current config.

### 4.4 What to Cache

Per D-06, the core cached indicators. Here is the expanded list with cache table column names:

| Indicator | Table Column | Parameters | Priority |
|-----------|-------------|------------|----------|
| RSI | `rsi_14` | length=14 | Core |
| MACD | `macd_line`, `macd_signal`, `macd_hist` | fast=12, slow=26, signal=9 | Core |
| EMA | `ema_20`, `ema_50`, `ema_200` | length=20,50,200 | Core |
| SMA | `sma_50`, `sma_200` | length=50,200 | Core |
| ATR | `atr_14` | length=14 | Core |
| OBV | `obv` | (no params) | Core |
| VWAP | `vwap` | (no params — requires volume + typical price) | Core |
| Bollinger Bands | `bb_lower_20`, `bb_middle_20`, `bb_upper_20` | length=20, std=2 | Core |
| Stochastic | `stoch_k_14`, `stoch_d_14` | k=14, d=3, smooth=3 | Extended |
| ADX | `adx_14` | length=14 | Extended |

**Core** = needed for 90% of filter needs (D-06)
**Extended** = nice-to-have, can be deferred to Phase 8

**Note on ADX availability:** Phase 1's `indicators.py` does NOT implement ADX, BB, OBV, VWAP, or Stochastic. These must be added in Phase 3 (either in `indicators.py` or in a new `indicators_extended.py`). The `@indicator` registry accepts new registrations from any module.

**Recommendation:** Add the 5 missing core indicators (ADX, OBV, BB, VWAP, Stoch) to `indicators.py` or create `indicators_extended.py` in Phase 3. This keeps the indicator registry complete without modifying Phase 1's file beyond additions.

---

## 5. Multi-Timeframe Broadcasting

### 5.1 vectorbt Broadcasting vs Pandas reindex/ffill

Per D-08: *"Use vectorbt `Data.pivot()` + broadcasting to align indicators across timeframes."*

After researching vectorbt's current API, the recommendation is nuanced:

**vectorbt `broadcast()` function** (from `vectorbt.base.reshape_fns`):
- Brings arrays to same shape using NumPy broadcasting rules
- `broadcast(*arrays, index_from='stack', columns_from='stack')` — aligns indices/columns
- Works on any array-like (numpy, pandas)
- Does NOT automatically forward-fill — it aligns the index/columns, but data values remain as-is
- Best for: broadcasting parameter columns across symbols

**Pure pandas approach for timeframe alignment:**
```python
# Daily indicator → hourly alignment via reindex + forward-fill
daily_rsi = pd.Series(...)  # index = daily timestamps
hourly_timestamps = pd.DatetimeIndex(...)  # hourly timestamps

hourly_rsi = (
    daily_rsi
    .reindex(hourly_timestamps, method='ffill')  # forward-fill daily value into each hour
    .reindex(hourly_timestamps)  # ensure exact alignment
)
```

**Recommendation:** Use **pure pandas `reindex(method='ffill')`** for timeframe broadcasting rather than vectorbt's broadcast function. Rationale:

1. Forward-fill is the correct semantics (daily value applies to all sub-bars until next day)
2. `reindex` + `ffill` is well-understood, simple, and fast
3. vectorbt's broadcast is designed for column/parameter broadcasting, not time-series frequency alignment
4. Avoids adding complexity with vectorbt's Numba-dependent broadcasting

### 5.2 Timeframe Hierarchy & Execution Order

Per D-10: *"Timeframe hierarchy: 1D (trend) → 4h (confirmation) → 1h/15m/5m (entry). Screener evaluates top-down."*

The screening engine should:

```
1. Fetch indicators for the TOP timeframe (1D)
2. Apply trend filters → get candidate symbols
3. Fetch indicators for the NEXT timeframe (4h)
4. Apply confirmation filters on candidates only
5. Repeat for lower timeframes
6. Join all results on symbol
7. For cross-timeframe rules (e.g., "Daily EMA200 AND 4h RSI < 30"):
   → Boolean AND of per-timeframe masks
```

This **top-down narrowing** is critical for performance: filtering on higher timeframes first reduces the number of symbols that need processing on lower timeframes.

```python
async def screen(
    self,
    config: ScreenConfig,
    symbols: list[str] | None = None,
) -> pd.DataFrame:
    """Run a screen configuration against all symbols.

    Evaluates timeframes top-down (higher → lower), narrowing candidates
    at each step.
    """
    candidates_mask: pd.Series | None = None
    all_filters = config.filters

    for tf in config.timeframes:  # sorted: 1D, 4h, 1h, 5m
        tf_filters = [f for f in all_filters if f.timeframe == tf]

        if not tf_filters:
            continue

        # Get indicator data for this timeframe
        indicator_data = await self._load_indicator_data(tf, symbols)

        # Apply each filter
        for flt in tf_filters:
            filter_func = _FILTER_REGISTRY[flt.filter_name].func
            mask = filter_func(indicator_data, **flt.params)

            if candidates_mask is None:
                candidates_mask = mask
            else:
                candidates_mask = candidates_mask & mask  # AND across timeframes

        # Early exit: no candidates left
        if candidates_mask is not None and not candidates_mask.any():
            return pd.DataFrame()

    return self._build_results(candidates_mask, all_filters, indicator_data)
```

### 5.3 Cross-Timeframe Filter Rules

Cross-timeframe filters require broadcasting a higher-timeframe indicator to a lower timeframe:

```python
# Example: "Daily EMA200 AND 4h RSI < 30"
# 1. Compute daily EMA200 for all symbols (one value per day per symbol)
# 2. Broadcast to 4h timestamps (ffill)
# 3. Compute 4h RSI (one value per 4h bar per symbol)
# 4. Combine: broadcasted_ema200 > close AND rsi < 30

def broadcast_timeframe(
    higher_tf_df: pd.DataFrame,
    lower_tf_timestamps: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Broadcast higher-timeframe indicator to lower-timeframe timestamps.

    Uses forward-fill: the value from the higher timeframe applies
    to all lower-timeframe bars until the next higher-timeframe update.
    """
    return higher_tf_df.reindex(lower_tf_timestamps, method='ffill')
```

**Recommendation:** The `broadcasting.py` module provides `broadcast_timeframe()` and `align_timeframes()` utilities. The engine automatically broadcasts filters where `filter.timeframe != eval_timeframe`.

---

## 6. Screen Configuration & Persistence

### 6.1 YAML Config Schema

Per D-11 and D-12, screens are YAML files in `config/screens/`:

```yaml
# config/screens/trend-follower.yaml
name: "Trend Follower"
description: "Uptrending stocks with momentum confirmation"
asset_classes: ["equities", "crypto"]
timeframes: ["1D", "4h"]

filters:
  # Trend filters (daily timeframe)
  - category: trend
    indicator: price_above_ema
    params:
      period: 200
    operator: gt
    timeframe: "1D"

  - category: trend
    indicator: adx_trending
    params:
      threshold: 25
    timeframe: "1D"

  # Momentum confirmation (4h timeframe)
  - category: momentum
    indicator: macd_bullish
    timeframe: "4h"

  # Volume confirmation (4h timeframe)
  - category: volume
    indicator: rvol_high
    params:
      threshold: 1.2
    timeframe: "4h"

# Optional: weighting for advanced scoring (Phase 8+)
# weights:
#   price_above_ema_200: 2.0
#   adx_trending: 1.5
```

### 6.2 Built-in Screen Templates

Per D-12, provide these templates at launch:

| Template Name | Description | Focus |
|---------------|-------------|-------|
| `trend-follower` | Price > EMA200 + ADX > 25 + MACD bullish | Trend continuation |
| `mean-reversion` | RSI < 30 + Bollinger Band touch + volume spike | Reversion to mean |
| `breakout` | Price > 20d high + RVOL > 1.5 + MACD bullish | Breakout detection |
| `volume-surge` | RVOL > 2.0 + price range > 1.5× ATR | High-activity movers |
| `oversold-bounce` | RSI < 25 + Stochastic < 20 + bullish engulfing | Bottom fishing |

Templates are stored as YAML files in `config/screens/` and loaded at startup:

```python
SCREEN_TEMPLATES_DIR = Path("config/screens")

def load_screen_template(name: str) -> ScreenConfig:
    """Load a screen configuration from YAML."""
    path = SCREEN_TEMPLATES_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Screen template '{name}' not found at {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return ScreenConfig(**data)

def list_screen_templates() -> list[str]:
    """List available screen configuration names."""
    return sorted(p.stem for p in SCREEN_TEMPLATES_DIR.glob("*.yaml"))
```

### 6.3 Screen Loading & Validation

The `ScreenConfig` Pydantic model validates YAML contents:

```python
class FilterRule(BaseModel):
    """A single filter rule in a screen configuration."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    category: str
    indicator: str                       # References _FILTER_REGISTRY
    params: dict[str, Any] = Field(default_factory=dict)
    operator: Literal["gt", "lt", "eq", "crosses_above", "crosses_below"] = "gt"
    timeframe: str = "1D"
    negate: bool = False                 # NOT operator


class ScreenConfig(BaseModel):
    """A complete screen configuration."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: str = ""
    asset_classes: list[str] = Field(default_factory=lambda: ["equities", "crypto"])
    timeframes: list[str] = Field(default_factory=lambda: ["1D", "4h"])
    filters: list[FilterRule] = Field(default_factory=list)

    @field_validator("filters")
    @classmethod
    def validate_filter_names(cls, filters: list[FilterRule]) -> list[FilterRule]:
        """Ensure all referenced filter names are registered."""
        from backend.app.infrastructure.screener.filters import list_filters
        registered = list_filters()
        for flt in filters:
            if flt.indicator not in registered:
                raise ValueError(f"Unknown filter '{flt.indicator}'. Available: {list(registered.keys())}")
        return filters
```

---

## 7. Real-Time WebSocket Streaming

### 7.1 FastAPI WebSocket Patterns

Per D-14: *"WebSocket server using FastAPI + uvicorn (already in stack)."*

FastAPI's WebSocket support (researched from current docs) provides:

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

@app.websocket("/api/v1/ws/screener/{screen_id}")
async def screener_stream(websocket: WebSocket, screen_id: str):
    await websocket.accept()
    try:
        while True:
            # Receive client messages (e.g., parameter updates, pong)
            data = await websocket.receive_text()

            # Heartbeat: periodically send latest screen results
            results = await run_screen(screen_id)
            await websocket.send_json(results.model_dump(mode="json"))
            await asyncio.sleep(5)  # configurable interval

    except WebSocketDisconnect:
        log.info("client_disconnected", screen_id=screen_id)
```

**Key patterns from FastAPI docs:**
- `@app.websocket("/path")` — decorator for WebSocket routes
- `await websocket.accept()` — must call before any send/receive
- `websocket.send_json(data)` — sends dict as JSON (existing method)
- `websocket.receive_text()` / `receive_json()` — receive messages
- `WebSocketDisconnect` — raised when client disconnects
- `websocket.close()` — server-initiated close

### 7.2 Message Format

Per D-22 (OpenCode's discretion), the message format:

#### Server → Client (screen results update)

```json
{
    "type": "screen_update",
    "screen_id": "trend-follower",
    "sequence": 142,
    "timestamp": "2026-06-19T14:30:00Z",
    "interval_ms": 5000,
    "results": [
        {
            "symbol": "AAPL",
            "score": 100.0,
            "matched_filters": ["price_above_ema_200", "adx_trending", "macd_bullish"],
            "indicators": {
                "ema_200": 185.42,
                "adx_14": 32.1,
                "macd_line": 2.34,
                "macd_signal": 1.89
            },
            "price": 198.50,
            "change_pct": 1.2
        }
    ],
    "total_matched": 47,
    "total_symbols": 5000
}
```

#### Delta Updates (D-15)

After the initial full snapshot, only changed symbols are sent:

```json
{
    "type": "delta_update",
    "screen_id": "trend-follower",
    "sequence": 143,
    "timestamp": "2026-06-19T14:30:05Z",
    "added": [{"symbol": "MSFT", ...}],
    "removed": [{"symbol": "GOOGL"}],
    "updated": [{"symbol": "NVDA", "score": 80.0, ...}]
}
```

#### Client → Server (control messages)

```json
{
    "type": "ping"
}
```

```json
{
    "type": "update_interval",
    "interval_ms": 10000
}
```

```json
{
    "type": "change_screen",
    "screen_id": "breakout"
}
```

### 7.3 Reconnection & Sequence Numbers

Per D-16: *"Client reconnection handled with sequence numbers."*

Strategy:
1. Server maintains a `seq_per_screen: dict[str, int]` counter per screen
2. Each message has incrementing `sequence` number
3. On reconnect, client sends: `{"type": "resync", "last_sequence": 140}`
4. Server replays all delta updates from sequence 141 to current
5. If too many missed (threshold: 100 sequences), client receives full snapshot
6. Client MUST ignore messages with sequence ≤ last received (handles duplicates)

```python
class ConnectionManager:
    """Manages WebSocket connections with sequence tracking."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)  # screen_id → clients
        self._sequences: dict[str, int] = defaultdict(int)  # screen_id → seq
        self._history: dict[str, list[dict]] = defaultdict(list)  # screen_id → recent messages
        self._max_history = 100

    async def broadcast(self, screen_id: str, message: dict) -> None:
        """Send a message to all clients on a screen, with sequencing."""
        self._sequences[screen_id] += 1
        message["sequence"] = self._sequences[screen_id]

        # Store in history for reconnection
        self._history[screen_id].append(message)
        if len(self._history[screen_id]) > self._max_history:
            self._history[screen_id].pop(0)

        # Send to all connected clients
        disconnected: list[WebSocket] = []
        for ws in self._connections.get(screen_id, set()):
            try:
                await ws.send_json(message)
            except WebSocketDisconnect:
                disconnected.append(ws)
        for ws in disconnected:
            self._connections[screen_id].discard(ws)
```

---

## 8. Export Formats

Per D-13: *"Screen results exported to CSV/JSON."*

### CSV Export

Uses pandas built-in `to_csv()`:

```python
def export_csv(results: pd.DataFrame, path: str | Path) -> None:
    """Export screen results to CSV."""
    results.to_csv(path, index=False)

# Columns: symbol, score, matched_filters, indicator_values, timestamp
# matched_filters as pipe-separated string: "rsi_oversold|macd_bullish"
```

### JSON Export

Uses pandas built-in `to_json()` with orientation:

```python
def export_json(
    results: pd.DataFrame,
    path: str | Path,
    orient: str = "records",
) -> None:
    """Export screen results to JSON."""
    results.to_json(path, orient=orient, date_format="iso")

# orient='records' → list of objects
# orient='split'   → {columns, index, data} — more compact
```

### ScreenResult Model Serialization

Screen results also serialize through Pydantic:

```python
results: list[ScreenResult] = [...]
json_str = json.dumps([r.model_dump(mode="json") for r in results])
```

---

## 9. Module Design & Class Structure

### 9.1 Module Layout

```
backend/app/infrastructure/screener/
├── __init__.py                   # Exports: run_screen, list_filters, ScreenEngine
├── filters.py                    # @filter decorator, _FILTER_REGISTRY, built-in filter functions
├── engine.py                     # ScreenEngine — orchestrator class
├── cache.py                      # IndicatorCache — DuckDB indicator cache manager
├── broadcasting.py               # broadcast_timeframe(), align_timeframes()
├── configs.py                    # ScreenConfig, FilterRule, YAML loader
├── scoring.py                    # compute_score(), filter tracking
├── streaming.py                  # ConnectionManager, WebSocket handler
├── export.py                     # export_csv(), export_json()
└── models.py                     # FilterRule, ScreenConfig (Pydantic models)
```

### 9.2 Class Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                  ScreenEngine (engine.py)                        │
│  Orchestrator: load config → resolve indicators → apply filters  │
│  → score → export / stream                                       │
│                                                                  │
│  Methods:                                                        │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ screen(config) → pd.DataFrame                              │  │
│  │ screen_to_csv(config, path) → None                         │  │
│  │ screen_to_json(config, path) → None                        │  │
│  │ start_streaming(screen_id, websocket) → None               │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────┬──────────┬──────────────┬──────────────┬──────────────────┘
       │          │              │              │
       ▼          ▼              ▼              ▼
┌──────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────┐
│ Filter   │ │Indicator │ │Broadcaster │ │Connection    │
│ Pipeline │ │Cache     │ │            │ │Manager       │
│          │ │          │ │reindex()   │ │              │
│ AND/OR   │ │update    │ │ffill()     │ │broadcast()   │
│ evaluate │ │get_latest│ │align()     │ │resync()      │
└──────────┘ └──────────┘ └────────────┘ └──────────────┘
       │              │                         │
       ▼              ▼                         ▼
┌──────────┐   ┌─────────────┐          ┌──────────────┐
│ Filter   │   │ DuckDB      │          │ FastAPI      │
│ Registry │   │ indicator_  │          │ WebSocket    │
│ (@filter) │   │ values      │          │ client       │
└──────────┘   └─────────────┘          └──────────────┘
```

### 9.3 Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SCREENING FLOW                               │
│                                                                     │
│  1. User selects screen (built-in or custom)                       │
│     ↓                                                              │
│  2. ScreenConfig loaded from YAML, validated against registry      │
│     ↓                                                              │
│  3. Engine resolves filter dependencies → list of needed indicators│
│     ↓                                                              │
│  4. For each timeframe (top-down):                                 │
│     a. Cache.get_latest() → latest indicator values per symbol     │
│     b. Broadcast higher-TF indicators to this TF (ffill)           │
│     c. Apply each filter → boolean masks                           │
│     d. AND-combine masks within timeframe                          │
│     e. AND-combine with parent timeframe mask (narrowing)          │
│     ↓                                                              │
│  5. Compute scores for passing symbols                             │
│     ↓                                                              │
│  6. Build results DataFrame with matched filter details            │
│     ↓                                                              │
│  7. Output: DataFrame (programmatic) / CSV / JSON / WebSocket      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 10. Integration Points with Phases 1 & 2

### What Phase 3 Consumes from Phase 1

| Phase 1 Asset | Phase 3 Usage | File |
|---------------|--------------|------|
| `get_db()` / `get_db_async()` | Read indicator values and OHLCV data | `backend/app/core/database.py` |
| `partition_path()` | Locate OHLCV Parquet files for indicator computation | `backend/app/core/database.py` |
| `@indicator` registry | Base indicator functions used by filters | `backend/app/infrastructure/indicators.py` |
| `compute_all()` | Batch indicator computation for cache refresh | `backend/app/infrastructure/indicators.py` |
| `ComputeSettings` | Cache enable/disable, broadcast indicator list | `backend/app/core/config.py` |
| `DataSettings` | Timeframes, asset classes for screen scope | `backend/app/core/config.py` |
| `set_correlation_id()` | Run-level correlation ID | `backend/app/core/logging.py` |
| `get_logger()` | Structured logging throughout | `backend/app/core/logging.py` |
| `ScreenResult`, `Signal` | Output models | `backend/app/domain/models.py` |

### What Phase 3 Consumes from Phase 2

| Phase 2 Asset | Phase 3 Usage | File |
|---------------|--------------|------|
| `ohlcv` DuckDB table | Source data for indicator computation | `backend/app/core/database.py` (DDL) |
| `symbol_metadata` table | Symbol enumeration, asset class filtering | `backend/app/core/database.py` (DDL) |
| Parquet `data/**/*.parquet` | Alternative direct read path | Filesystem |
| `_timeframe_to_tv_suffix()` | Timeframe → TV pipe suffix conversion (reuse) | `backend/app/infrastructure/ingest/__init__.py` |

### What Phase 3 Provides to Downstream Phases

| Downstream Phase | What It Gets | How |
|-----------------|-------------|-----|
| Phase 4 (Backtest) | Filtered symbol lists, indicator values | Shared DuckDB `indicator_values` table |
| Phase 6 (API) | `ScreenEngine` class for REST endpoints, `ConnectionManager` for WebSocket | Import |
| Phase 7 (Frontend) | Screen results, real-time streaming | JSON over HTTP/WS |
| Phase 8 (Advanced Screener) | Screen config persistence, filter registry extensibility | Module hooks |

---

## 11. New Dependencies

### New Packages

| Package | Version | Purpose | Required? |
|---------|---------|---------|-----------|
| `fastapi` | `>=0.110,<1` | WebSocket endpoint for real-time streaming | YES |
| `uvicorn[standard]` | `>=0.29,<1` | ASGI server for FastAPI | YES |

These are needed ONLY if WebSocket is part of Phase 3 (D-14). If WebSocket is deferred to Phase 6, no new dependencies are needed — all screening is pure pandas/NumPy/DuckDB.

**Recommendation:** Add FastAPI + uvicorn in Phase 3 for the WebSocket endpoint. Phase 6 will expand on this with REST endpoints, auth, etc.

### Updated pyproject.toml

```toml
[project.dependencies]
# ... existing deps ...
fastapi = ">=0.110,<1"
uvicorn = {extras = ["standard"], version = ">=0.29,<1"}

[[tool.mypy.overrides]]
module = ["fastapi.*"]
ignore_missing_imports = false  # FastAPI has good stubs

# Add websockets dep for testing
[project.optional-dependencies]
test = [
    # ... existing test deps ...
    "websockets>=12.0",  # For WebSocket client testing
]
```

### No New Infrastructure

- No new databases or external services
- No new message brokers (WebSocket is direct)
- No new queue systems
- The indicator cache shares the same DuckDB database

---

## 12. Risks & Mitigations

### High Risk

| Risk | Description | Likelihood | Impact | Mitigation |
|------|-------------|------------|--------|------------|
| **DuckDB "materialized views" don't exist** | D-05 assumes `CREATE MATERIALIZED VIEW` like PostgreSQL. DuckDB only has logical views. | **Certain** | **High** | Use regular `indicator_values` table instead. Document this in PLAN.md. See [Section 2](#2-critical-architecture-discovery-duckdb-materialized-views--postgresql). |
| **WebSocket in Phase 3 overlaps with Phase 6** | Phase 6 (API Layer) also plans WebSocket. May cause conflicting implementations. | Medium | Medium | Phase 3 WebSocket is minimal (screener-only). Phase 6 adds auth, rate limiting, additional endpoints. Design `streaming.py` to be extended in Phase 6. |
| **5000 symbols < 10s performance target** | D-19 requires screening 5000 symbols in under 10 seconds with warm cache. Filter composition over large DataFrames could be slow. | Medium | High | Pre-compute indicators (cache). Use top-down narrowing. Profile early. Implement wide-table snapshot cache if tall-table reads are slow. |

### Medium Risk

| Risk | Description | Likelihood | Impact | Mitigation |
|------|-------------|------------|--------|------------|
| **Indicator parameter changes invalidate cache** | If RSI length changes from 14 to 21, cached `rsi_14` values are wrong. | Medium | Medium | Store `params` JSON in `indicator_values`. On cache read, compare config params vs stored params. Full recompute on mismatch. |
| **Pattern filters need raw OHLCV** | Pattern detection (engulfing, doji) uses raw OHLCV, not indicator values. Filter pipeline must support dual input types. | High (certain) | Medium | Filter function signature accepts either `indicator_values` or `ohlcv` data. The engine provides both based on filter metadata. |
| **WebSocket reconnection buffer size** | D-16: 100 messages of history may not be enough for long disconnections. | Low | Medium | Start with 100. Make configurable. On threshold exceeded, send full snapshot instead of delta. |
| **Cross-timeframe broadcasting correctness** | Forward-filling daily values into hourly timestamps may cause look-ahead bias if not careful with timestamps. | Medium | Low | Use `reindex(method='ffill', limit=None)` and ensure timestamps are end-of-bar. Document in broadcasting.py. |

### Low Risk

| Risk | Description | Likelihood | Impact | Mitigation |
|------|-------------|------------|--------|------------|
| **YAML screen config validation** | Invalid YAML could cause runtime errors. | Low | Low | `ScreenConfig` Pydantic model validates at load time. `validate_filter_names()` catches missing filters. |
| **Score granularity with AND-only** | All-filters-AND → binary score (100 or 0). Not useful for ranked lists. | Low | Low | Acceptable for Phase 3. Track per-filter results for future weighted scoring. |
| **Empty results** | No symbols pass all filters. | Medium | Low | Return empty DataFrame gracefully. WebSocket sends `{"results": [], "total_matched": 0}`. |
| **NaN in indicator computations** | Edge cases (zero volume, flat price) produce NaN indicators. | Low | Low | Filters treat NaN as False (no match). Document this behavior. |

---

## 13. Open Questions for Planning

These need resolution before writing PLAN.md:

### Q1: DuckDB "Materialized View" — Table or View?

The context D-05 says "materialized views" but DuckDB doesn't support PostgreSQL-style MVs. Which approach?

Options:
- **A: `indicator_values` table** — regular table with rows per (symbol, indicator_name, timestamp). Updated incrementally.
- **B: Standard `CREATE VIEW`** — compute indicators on read. No storage needed. Slower.
- **C: Wide `indicator_snapshot` table** — one row per (symbol, timestamp) with all indicators as columns. Fastest reads.

**Recommendation:** Option A (tall table) for Phase 3. Option C (wide snapshot) as optimization if D-19 targets aren't met. See [Section 2](#2-critical-architecture-discovery-duckdb-materialized-views--postgresql) for full analysis.

### Q2: Add Missing Indicators to Phase 1 or Create Extended Module?

Phase 1 provides 5 indicators (RSI, MACD, EMA, SMA, ATR). Phase 3 needs ADX, OBV, Bollinger Bands, VWAP, Stochastics (5 more). Where do these go?

Options:
- **Add to `indicators.py`** — clean, all indicators in one place. Modifies Phase 1 file.
- **`indicators_extended.py`** — keeps Phase 1 unchanged. New file alongside.
- **In `screener/` module** — tightly coupled to screener, but indicators are reusable.

**Recommendation:** Create `backend/app/infrastructure/indicators_extended.py` that registers additional indicators using the same `@indicator` decorator. This keeps Phase 1's file unchanged while extending the registry naturally (decorators fire on import).

### Q3: WebSocket — Phase 3 or Phase 6?

Phase 3 scope includes "real-time WebSocket streaming" but Phase 6 is "API Layer" with WebSocket. Clear overlap.

Options:
- **Phase 3: Minimal WebSocket** — `/api/v1/ws/screener/{screen_id}` endpoint, no auth, no rate limiting. Simple message format.
- **Phase 3: No WebSocket** — deferred entirely to Phase 6. Phase 3 delivers the engine + cache + filters + export.
- **Phase 6: Build on Phase 3** — Phase 3 provides `ConnectionManager` class + streaming logic. Phase 6 adds auth, rate limiting, additional WS endpoints.

**Recommendation:** Phase 3 provides `streaming.py` with `ConnectionManager` class. The FastAPI WebSocket route is wired in Phase 6 (or with a minimal test route in Phase 3). This separates concerns: Phase 3 = streaming runtime, Phase 6 = API surface.

### Q4: Screen Persistence for User-Defined Screens?

D-11 says screens stored in `screens/` directory. D-12 says users can save/load custom screens. How much of this in Phase 3?

Options:
- **Phase 3: File-based only** — YAML files in `config/screens/`. No user CRUD. Built-in templates only.
- **Phase 3: File + basic save** — Engine can save current config to YAML. No UI.
- **Phase 3: Full CRUD** — DuckDB `screens` table with API endpoints. Overkill.

**Recommendation:** Phase 3 = file-based built-in templates only (`config/screens/*.yaml`). User-defined screen persistence deferred to Phase 8. The `ScreenConfig` model and YAML loader are shared.

### Q5: Filter DSL or Direct YAML?

The context mentions a "Filter DSL" — human-readable syntax like `RSI(14) < 30 AND CLOSE > EMA(200)`.

Options:
- **Direct YAML** — structured JSON/YAML in screen config. No parsing needed.
- **DSL parser** — parse string expressions into filter groups. More user-friendly.

**Recommendation:** Direct YAML for Phase 3. DSL is a Phase 8 enhancement. The YAML schema is designed to be machine-generated from a future DSL parser.

### Q6: Testing Strategy for Screener?

Like Phase 2, the screener has complex dependencies (DuckDB, indicator computation). Testing approaches:

1. **Unit tests** for each filter function (pure function → easy to test with synthetic data)
2. **Integration tests** for `ScreenEngine` with in-memory DuckDB + pre-loaded test data
3. **Property tests** for score correctness, mask consistency, filter composition
4. **WebSocket tests** using `httpx` + `websockets` client lib

**Recommendation:**
- `test_filters.py` — unit test each built-in filter with synthetic OHLCV data
- `test_engine.py` — integration test with in-memory DuckDB and test indicator_values
- `test_cache.py` — test incremental updates, full recompute, parameter change detection
- `test_scoring.py` — property tests for score boundaries (0-100)
- `test_broadcasting.py` — test timeframe alignment correctness
- `test_streaming.py` — test ConnectionManager with mock WebSocket clients
- `test_configs.py` — test YAML load validation, filter name resolution
- `test_export.py` — test CSV and JSON output format

### Q7: Broadcasting library — vectorbt or pure pandas?

D-08 references vectorbt `Data.pivot()` + broadcasting, but after research, pure pandas `reindex(method='ffill')` is simpler and more appropriate for timeframe alignment.

Options:
- **vectorbt broadcast()** — uses NumPy broadcasting rules. Designed for column/parameter broadcasting, not time-series frequency alignment.
- **Pandas reindex + ffill** — industry-standard for upsampling time series. Simple, well-understood, fast.

**Recommendation:** Pure pandas `reindex(method='ffill')`. Avoids vectorbt dependency for this specific use case. Keep vectorbt for Phase 4 (backtesting) where its Portfolio API is essential.

### Q8: How does Indicator Cache Refresh Trigger?

The indicator cache needs to be refreshed after each ingestion run. How?

Options:
- **Post-ingestion hook** — `run_ingestion()` calls `cache.update_cache()` at end
- **Scheduled job** — separate cron/scheduler that runs cache refresh independently
- **On-demand** — cache is computed lazily on first screen run

**Recommendation:** **Post-ingestion hook** in Phase 3. The `run_ingestion()` function (Phase 2) calls `IndicatorCache.update_cache()` after writing data. This ensures indicators are always fresh after ingestion. For Phase 6, add a scheduled refresh via Celery or APScheduler.

### Q9: Data directory for screen configs?

Where should `config/screens/` live?

Options:
1. `config/screens/` at project root — alongside `config.yaml`
2. `backend/config/screens/` — inside backend
3. `backend/app/infrastructure/screener/templates/` — bundled with code

**Recommendation:** Option 1: `config/screens/` at project root. This keeps configurations visible and easy to version control. The path is configurable via `ComputeSettings.screens_dir`.

---

## Summary of Technology Choices

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Filter pipeline | Pandas boolean masks (vectorized) | Zero-loop, composable, follows D-01 |
| Filter registry | `@filter` decorator (follows `@indicator` pattern) | Consistency with Phase 1 |
| Indicator cache | DuckDB `indicator_values` table | D-05 intent, but table not MV (see Section 2) |
| Wide cache snapshot | Deferred to optimization pass | Only if tall-table reads miss D-19 targets |
| Multi-timeframe broadcast | Pandas `reindex(method='ffill')` | Simpler than vectorbt, correct semantics (Q7) |
| Missing indicators | New `indicators_extended.py` file | Extends registry without modifying Phase 1 (Q2) |
| Screen config format | YAML files in `config/screens/` | Git-versioned, validatable, extensible (Q5) |
| Screen persistence | File-based built-in templates only | User CRUD deferred to Phase 8 (Q4) |
| WebSocket | Minimal: `ConnectionManager` class only | Wired as endpoint in Phase 6 (Q3) |
| Export | Pandas `to_csv()` / `to_json()` | Zero-dependency, standard |
| Scoring | Fractional (matched/total) | Simple, transparent (Approach A) |
| Performance | Top-down timeframe narrowing | Reduces candidates per timeframe (D-10) |
| FastAPI | `>=0.110,<1` | WebSocket support, already in stack |
| Uvicorn | `>=0.29,<1` | ASGI server for WebSocket |
| Cache refresh | Post-ingestion hook | `run_ingestion()` → `cache.update_cache()` (Q8) |
| Config directory | `config/screens/` at project root | Version-controlled, visible (Q9) |

---

*This research feeds into `03-PLAN.md`. All documentation references verified against current (June 2026) library APIs.*
