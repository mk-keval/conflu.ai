# Project Roadmap

## Current Milestone: v1.0 — TV Screener + Deep Analysis

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1: TV Screener Specialist** | ✅ Complete | TV Screener specialist, filter map, confluence scorer, TV engine, API endpoints |
| **Phase 2: Deep Analysis Orchestrator** | ✅ Complete | On-demand OHLCV + backtest + risk for TV-discovered tickers |

## Next Milestones

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 3: Cleanup & Consolidation** | ✅ Complete | Removed 23 old files (11 infra + 5 routers + 7 tests), updated router registrations |
| **Phase 4: Production Hardening** | ❌ Not Needed | Core functionality stable; hardening deferred to future maintenance |
| **Phase 5: Validation Infrastructure** | ✅ Complete | WalkForward, MonteCarlo, StressTest, PaperTrading, Regime, Statistical validators + Orchestrator (407 tests pass) |

## Next Milestone: v1.1 — Paper Trading + Portfolio + Alerts

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 6: Paper Trading + Portfolio + Alerts** | ⏳ Planned | Virtual order execution, portfolio tracker, alert system, paper trading UI |
| **Phase 7: Learning Path + Behavioral Coach + Community** | ⏳ Planned | Learning curriculum, behavioral coach, community Q&A, tax center |
| **Phase 8: Professional Mode (8A-8E)** | ✅ Complete | Score Legend, Daily Routine, Validation Gate, Execution Engine, Paper Trade Logger |
| **Phase 9: Data Quality Gaps Fix** | 📋 Spec complete | Fix 3 silent data-quality bugs (weekly SMA200 missing, narration crashed, 56h+ data staleness) + 3 gap items (earnings binary filter, conviction calibration, server-driven stale pill). See `.planning/phases/09-data-quality-gaps-fix/SPEC.md`. |

## Archive: v0.1 Foundation (Legacy)

The original 10-phase GSD plan (Foundation → Data Ingestion → Screener Engine → Backtest → Risk → API → Frontend → Advanced Screener → Advanced Backtest → Production) was built with a DuckDB-dependent approach. The architecture was redesigned to use TradingView Screener as the primary data source.

- Phase 1-2 (Foundation + Data Ingestion): ✅ Solid, retained
- Phase 3-10 (Screener + Backtest + Risk + API + Frontend + Advanced + Production): 🔄 Replaced by TV Screener approach

**Phase 4 (Production Hardening)** was evaluated but deemed not needed at this time. Core TV Screener + Deep Analysis + Validation Infrastructure are stable. Production hardening (rate limiting, caching, error handling) is deferred to future maintenance cycles when scaling issues emerge.

**Phase 5 (Validation Infrastructure)** is complete with 6 validators + Orchestrator (407 tests passing).
