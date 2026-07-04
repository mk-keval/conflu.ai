# conflu.ai — Project State

## Overview
The project was initially built with a 10-phase DuckDB-dependent architecture (v0.1 Foundation). The screening engine has been redesigned to use TradingView Screener as the primary discovery source. DuckDB is retained for backtest OHLCV storage only.

## Current Milestone: v1.0 — TV Screener + Deep Analysis

### ✅ Phase 1: TV Screener Specialist
**Status:** Complete
TV Screener integration, confluence scorer, 5-factor scoring, YAML-driven screen configs.

### ✅ Phase 2: Deep Analysis Orchestrator
**Status:** Complete
On-demand OHLCV + backtest + risk for TV-discovered tickers.

### ✅ Phase 3: Cleanup & Consolidation
**Status:** Complete
Deleted 23 old DuckDB-dependent screener files, cleaned router registrations.

### ✅ Phase 4: Production Hardening
**Status:** Complete
Rate limiter (25 req/min token bucket), TTL cache (60s, 50 entries LRU), API hardening with Pydantic request/response models, 67 new tests, removed unsupported filters from FILTER_MAP.

### ✅ Phase 5: UI / Frontend Integration
**Status:** Complete
Professional dark theme, virtualized screener table, detail panel, multi-template selector, column customizer, MTF charts page, indicator panel, export buttons.

### ✅ Scoring Calibration & SHORT Screens
**Status:** Complete
Graded thresholds (replaced binary checks), MTF weighted stacking (replaced strict intersection), 3 SHORT screen templates, fundamental grading, volatility-regime stops.

## Current Work (ui-audit-fixes branch)
- UI audit fixes: z-index stacking, chart crash (React hooks violation), chart height inconsistencies, brand refresh
- See [Session Log](docs/SESSIONS/ses_20260703213318.md)

## Archive: v0.1 Foundation (Legacy)
The original 10-phase DuckDB-dependent architecture is archived. Phases 1–2 (Foundation + Data Ingestion) are retained for backtest OHLCV pipeline. Phases 3–10 are superseded by the TV Screener approach.
