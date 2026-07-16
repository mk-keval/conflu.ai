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
| **Phase 4: Production Hardening** | ⏳ Pending | Error handling, rate limiting, caching, logging, frontend integration |

## Next Milestone: v1.1 — Validation Infrastructure & Paper Trading

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 5: Validation Infrastructure** | ⏳ Planned | WalkForward, MonteCarlo, StressTest, PaperTrading, Regime, Statistical validators + Orchestrator |
| **Phase 6: Paper Trading + Portfolio + Alerts** | ⏳ Planned | Virtual order execution, portfolio tracker, alert system, paper trading UI |
| **Phase 7: Learning Path + Behavioral Coach + Community** | ⏳ Planned | Learning curriculum, behavioral coach, community Q&A, tax center |

## Archive: v0.1 Foundation (Legacy)

The original 10-phase GSD plan (Foundation → Data Ingestion → Screener Engine → Backtest → Risk → API → Frontend → Advanced Screener → Advanced Backtest → Production) was built with a DuckDB-dependent approach. The architecture was redesigned to use TradingView Screener as the primary data source.

- Phase 1-2 (Foundation + Data Ingestion): ✅ Solid, retained
- Phase 3-10 (Screener + Backtest + Risk + API + Frontend + Advanced + Production): 🔄 Replaced by TV Screener approach
