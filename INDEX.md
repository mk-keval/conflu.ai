# conflu.ai — Trading Intelligence Platform

## Project Index

### Documentation
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — Project architecture & data flow
- [SESSION LOGS](docs/SESSIONS/) — Per-session activity logs
- [CHANGELOG.md](CHANGELOG.md) — Decision log & significant changes

### Phases
- [Phase 1: Foundation & Core Infrastructure](.planning/phases/01-foundation-core-infrastructure/01-SUMMARY.md) — ✅ Completed 2026-06-18
- [Phase 2: Data Ingestion Pipeline](.planning/phases/02-data-ingestion-pipeline/02-SUMMARY.md) — ✅ Completed 2026-06-19
- [Phase 4: Backtest Engine](.planning/phases/04-backtest-engine/04-SUMMARY.md) — ✅ Completed 2026-06-19
- [Phase 5: Risk Management Engine](.planning/phases/05-risk-engine/05-SUMMARY.md) — ✅ Completed 2026-06-19

### Test Status
- **Total tests**: 193 (51 Phase 1 + 75 Phase 2 + 67 Phase 5)
- **Status**: ✅ All passing
- **Phase 1 suites**: config (11), database (7), models (12), indicators (8), logging (6)
- **Phase 2 suites**: scanner (7), symbol_map (11), quality (8), models (7), fetcher (6), writer (4), metrics (7), CLI (11)
- **Phase 5 suites**: risk_models (16), risk_beta (6), risk_correlation (5), risk_var (8), risk_kelly (7), risk_position_sizing (4), risk_streaming (7), risk_engine (9)

### Recent Activity
1. **2026-06-19**: Phase 5 completed — Risk Management Engine (67 tests, 11 source files, 8 test files)
2. **2026-06-19**: Phase 2 completed — Data Ingestion Pipeline (75 tests, 9 source files, 8 test files)
3. **2026-06-18**: Phase 1 completed — Foundation & Core Infrastructure (51 tests, 17 source files)
