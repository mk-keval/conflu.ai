# conflu.ai - Project State

## Overview
The project was initially built with a 10-phase DuckDB-dependent architecture (v0.1 Foundation). The screening engine has been redesigned to use TradingView Screener as the primary discovery source. Phases 1–2 of the old architecture are retained (data ingestion for backtest OHLCV); Phases 3–10 are replaced by the new TV Screener approach.

## Current Milestone: v1.0 — TV Screener + Deep Analysis

### Phase 1: TV Screener Specialist
**Status:** ✅ Complete
**Files created:**
- `backend/app/infrastructure/screener/tv_specialist.py` — TVScreenerSpecialist class
- `backend/app/infrastructure/screener/confluence_scorer.py` — TVConfluenceScorer
- `backend/app/infrastructure/screener/tv_engine.py` — TVScreenEngine orchestrator
- `backend/app/infrastructure/screener/tv_models.py` — Pydantic models
- `backend/app/api/routers/tv_screener.py` — FastAPI endpoints
- `backend/app/infrastructure/screener/configs.py` — ScreenConfig updates
- `config/screens/*.yaml` — 5 screen templates
- `.claude/skills/tvscreener-specialist/SKILL.md` — AI agent skill
- `.planning/phases/01-tv-screener-phase1/` — GSD artifacts

### Phase 2: Deep Analysis Orchestrator
**Status:** ✅ Complete
**Files created:**
- `backend/app/infrastructure/analysis/deep_analysis.py` — DeepAnalysisOrchestrator
- `backend/app/infrastructure/backtest/engine.py` — Fixed multi-symbol OHLCV
- `backend/app/infrastructure/backtest/sizing.py` — Fixed ATR sizing
- `.planning/phases/02-deep-analysis-phase2/` — GSD artifacts

### Phase 3: Cleanup & Consolidation
**Status:** ✅ Complete
- Removed 11 old DuckDB-dependent screener files (engine.py, cache.py, filters.py, scoring.py, export.py, streaming.py, alerts.py, broadcasting.py, screen_replay.py, sharing.py, models.py)
- Removed 5 old API routers (screener.py, screen_crud.py, alerts.py, replay.py, sharing.py)
- Updated router __init__.py and main.py to remove old registrations
- Cleaned test_screener_configs.py (removed models.py references)
- Deleted 7 obsolete test files for old screener modules

### Phase 4: Production Hardening
**Status:** 🔄 In Progress
- **Wave 1 (Bugfixes):** ✅ Fixed 3 critical bugs — FILTER_MAP validation in configs.py, full FILTER_MAP + compile_filters + build_query in tv_specialist.py, deep_analyze endpoint returning real pipeline data
- **Wave 2 (Rate Limiting & Caching):** ✅ Created TVRateLimiter (token bucket, 25 req/min) and TVCache (60s TTL, 50 entries LRU); integrated into tv_engine.py discover()
- **Wave 3 (API Hardening):** ✅ Request/response models use Pydantic (TVScreenRequest, TVScreenResponse, ScoredTickerResponse); config accepts inline dict or template name; dict_to_screen_config handles universe properly; tv_screener.py endpoint uses typed models
- **Wave 4 (Tests):** ✅ Created 67 new tests across 3 files — test_tv_specialist.py (14 filter builder tests + compile/query/discover tests), test_tv_engine.py (5 engine + 3 rate limiter + 7 cache tests), test_tv_screener.py (16 request/response/helper tests); all pass
- **Wave 5 (Docs):** 🔄 STATE.md update, GSD SUMMARY.md
- **Removed unsupported filters:** `macd_hist_rising` and `bb_squeeze` removed from FILTER_MAP (tradingview_screener Column doesn't support `.shift()` or arithmetic operators)
- **Updated YAML templates:** mean-reversion, oversold-bounce, volume-surge, breakout updated to use only valid FILTER_MAP entries

## Archive: v0.1 Foundation (Legacy 10-Phase Plan)
The original GSD plan with Phases 1–10 was built around a DuckDB-dependent architecture. Phases 1–2 (Foundation + Data Ingestion) are **retained** — they provide the data pipeline for backtest OHLCV. Phases 3–10 (Screener Engine, Backtest, Risk, API, Frontend, Advanced Screener, Advanced Backtest, Production) are **superseded** by the TV Screener approach.

### What's Retained
- Phase 1: Foundation & Core Infrastructure — Core config, database, logging
- Phase 2: Data Ingestion Pipeline — OHLCV ingestion for backtesting

### What's Superseded
- Phase 3: Screener Engine → TV Screener Specialist (Phase 1, new)
- Phase 4: Backtest Engine → Deep Analysis Orchestrator (Phase 2, new)
- Phase 5-10: Risk/API/Frontend/Advanced/Production — To be evaluated

## Active Work
**Phase 3: Cleanup & Consolidation** — ✅ Complete (23 old files deleted)
**Phase 4: Production Hardening** — 🔄 Wave 5 (Docs wrap-up) — 5 Waves implemented, 67 tests passing
**Phase 5: UI / Frontend Integration** — ⏳ Future work
