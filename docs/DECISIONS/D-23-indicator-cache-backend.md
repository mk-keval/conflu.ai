# D-23: IndicatorCache Backend for Screener Indicators

**Status:** **Retired / Superseded (2026-08-16)** — the on-demand path replaced this
**Date:** 2026-07-03

## Context

The Charts page has 4 indicator series (RSI, MACD, EMA_20, Bollinger Bands) that fetch data via API. The backend router `data.py` referenced `IndicatorCache` from `backend.app.infrastructure.screener.cache`, but the `cache.py` module did not exist — only a `__init__.py` existed in that directory. This caused ModuleNotFoundError 500 on all indicator endpoints.

The `indicator_values` table in DuckDB already contained 939,874 rows with pre-computed indicator data for symbols traded in the screener universe, but no reader class existed to query it.

## Decision

Create a dedicated `IndicatorCache` class in `backend/app/infrastructure/screener/cache.py` that:

1. **Reads from `indicator_values` table** — queries by `symbol`, `indicator_name`, and optional `timeframe` filter
2. **Returns TVDataPoint-compatible dicts** — `[{ timestamp: unix_ms, value: number }]` matching the existing frontend type
3. **Accepts `timeframe` as optional** — defaults to `1D` when omitted (consistent with frontend's `activeTimeframes[0]`)
4. **Handles empty results gracefully** — returns empty list (not null/error) when no data exists for a symbol/indicator combination

This approach was chosen over:
- **Removing IndicatorCache references** — data already exists, just needed a reader
- **Computing indicators on-the-fly** — expensive and unnecessary when pre-computed data is available
- **Inline queries in the route handler** — would duplicate the query logic and make it harder to test

## Consequences

**Positive:**
- All 4 indicator API endpoints now return 200 with real data
- BB indicators return empty arrays (no Bollinger Bands data in DB) rather than errors
- `NaT` values in DuckDB are caught defensively in `data.py` to prevent `float(NaT)` crashes
- Class is testable in isolation from the route handler

**Risks:**
- `timeframe` case sensitivity: DB uses `4h` (lowercase `h`), frontend sends `4H` (uppercase) — may cause empty results for 4H timeframe
- No caching layer (yet) — each API call queries DuckDB directly
