# CHANGELOG — Decision Log

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
