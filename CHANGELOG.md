# CHANGELOG — Decision Log

## 2026-06-19 — Phase 8: Advanced Screener (Complete)

**Prompt:** Execute Phase 8 Advanced Screener across 6 plans (08-A through 08-F) — saved screen configurations, real-time alerts, screen sharing, historical replay, frontend integration.

**Changes:**
- **New backend files:** `backend/app/infrastructure/screener/alerts.py` (AlertEngine with 6 alert types + background loop), `backend/app/infrastructure/screener/screen_replay.py` (ScreenReplay with SignalQualityMetrics), `backend/app/infrastructure/screener/sharing.py` (ScreenSharing HMAC tokens)
- **Backend API routers:** `backend/app/api/routers/screen_crud.py` (CRUD + versions + replay), `backend/app/api/routers/alerts.py` (CRUD + history + dismiss), `backend/app/api/routers/sharing.py` (token generation), `backend/app/api/routers/replay.py` (shared screen resolution)
- **Modified backend:** `database.py` (+5 DDLs), `config.py` (+3 settings classes), `domain/models.py` (+5 domain models), `schemas.py` (+Phase 8 schemas), `dependencies.py` (+ScreenReplay/ScreenSharing deps), `main.py` (+4 routers), `ws/manager.py` (+alert background loop)
- **New frontend:** `hooks/useAlerts.ts`, `hooks/useScreenDraft.ts`, `api/screens.ts`, `api/alerts.ts`, `api/sharing.ts`, `components/screener/SaveScreenModal.tsx`, `LoadScreenModal.tsx`, `AlertsPanel.tsx`, `AlertToast.tsx`, `ShareModal.tsx`, `ScreenDiffView.tsx`, `SharedScreenerView.tsx`
- **Modified frontend:** `types/screener.ts` (+Phase 8 types), `types/ws.ts` (+alert/replay WS messages), `store/screen.ts` (+Phase 8 state), `ws/channels.ts` (+alert/replay/shared channels), `App.tsx` (+shared screen route), `ScreenerPage.tsx` (+Save/Load/Share/Alerts toolbar), barrel exports

**Architecture Decision:**
- **AlertEngine** singleton with background asyncio task, 6 evaluation strategies (price_threshold, indicator_cross, signal_trigger, volume_spike, trend_break, compound). WebSocket dispatch via `ws_manager.broadcast()` to `alert:user:{user_id}` channel
- **ScreenReplay** uses `IndicatorCache.get_as_of()` for point-in-time queries, skips weekends, caches results in `screen_replay_results` table
- **ScreenSharing** uses HMAC-SHA256 tokens (self-contained, no server-side storage), base64url encoded
- All 5 new DuckDB DDLs use `CREATE TABLE IF NOT EXISTS` for idempotent initialization
- Frontend follows existing patterns (zustand store, @tanstack/react-query, useWS hooks)

**Risk Level:** MEDIUM (new modules, 30+ files changed)

**Verification:**
- Backend Python imports resolve (modulo pre-existing package install issues)
- Frontend TypeScript follows existing patterns

**Breaking Changes:** None (all additive — new endpoints, new tables, new types)

**Decision ID:** PHASE-08-COMPLETE

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
