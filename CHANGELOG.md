# CHANGELOG — Decision Log

## 2026-06-19 18:30 — Phase 5: Risk Management Engine (Complete)

**Prompt:** Execute Phase 5 Risk Management Engine plan across all 4 waves — ATR position sizing, beta hedging, correlation matrix, VaR/CVaR, Kelly optimization, risk engine orchestrator, WebSocket streaming, HTML reporting, and test suite.

**Changes:**
- 11 new files in `backend/app/infrastructure/risk/` (beta, correlation, var, kelly, position_sizing, engine, streaming, metrics, reporting, models, __init__)
- 8 new test files in `backend/tests/` (67 test cases)
- Modified: `pyproject.toml`, `config.yaml`, `backend/app/domain/models.py`, `backend/app/core/config.py`, `backend/app/core/database.py`

**Architecture Decision:**
- Risk computation partitioned into 5 standalone modules (beta, correlation, var, kelly, position_sizing) plus engine orchestrator — maximizes testability
- Vectorized pandas/cov for all matrix operations (no Python loops over symbols)
- PositionSizingRefiner composes Phase 4 PositionSizer (does not reimplement ATR/Kelly)
- Half-Kelly default (50% fraction) per D-16 conservative sizing
- Composite risk score: VaR (40pts) + diversification (30pts) + beta (30pts)
- HTML reports with inline CSS — zero template dependencies
- Existing DuckDB connection pool reused for data loading
- Streaming follows Phase 3 screener patterns (connection registry, sequence numbers, history replay)

**Risk Level:** MEDIUM (new infrastructure module, 19 files)

**Verification:**
- Tests: 67/67 PASS (total project: 193)
- Imports: All module imports verified

**Breaking Changes:** None

**Decision ID:** PHASE-05-COMPLETE

## 2026-06-19 00:30 — Phase 2: Data Ingestion Pipeline (Complete)

**Changes:**
- 9 new files in `backend/app/infrastructure/ingest/` (scanner, symbol_map, quality, models, fetcher, writer, metrics, cli, __init__)
- 8 new test files in `backend/tests/` (75 test cases)
- Modified: `pyproject.toml`, `config.yaml`, `backend/app/core/config.py`, `backend/app/core/database.py`

**Architecture Decision:** Append-only Parquet writes with staging-table dedup via DuckDB COPY. TradingView scanner wrapped in thread pool for async compatibility. Semaphore-based concurrency (50) with batch size 100.

**Risk Level:** MEDIUM (new infrastructure module, 25+ files)

**Verification:**
- Tests: 75/75 PASS
- Imports: All module imports verified

**Breaking Changes:** None

**Decision ID:** PHASE-02-COMPLETE
