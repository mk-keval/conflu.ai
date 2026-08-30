# Session Log — 2026-08-29: Housekeeping — Retire Indicator Cache + GitNexus Re-index + Frontend Build Fix

**Branch:** feat/swing-parity-upgrade
**Scope:** The three deferred housekeeping items flagged during Phase 1 planning ("Lets fix the deferred ones"). Deferred from D-39/D-40: (1) retire the zombie `indicator_values` cache, (2) re-run the GitNexus index so Phase-1 Sprint 7/8 symbols are queryable, (3) fix the frontend `package-lock.json`/esbuild drift. No new feature work.

## Change

### Item 1 — Retire zombie `indicator_values` + `indicator_snapshot` cache (D-32 intent, now enforced)
- **`backend/app/core/database.py`** — removed `INDICATOR_VALUES_DDL` + `INDICATOR_SNAPSHOT_DDL` constants and their two init `con.execute` calls. These created/created-the-schema at every startup but were never written or read on-demand (D-32 already retired the cache; the tables were leftovers).
- **`backend/app/core/config.py`** — removed dead flags `cached_indicators` + `indicator_cache_enabled`; kept + marked **DEPRECATED** `cache_indicators` (generic "materialized views" toggle, still valid in `config.yaml`).
- **`backend/app/infrastructure/screener/cache.py`** — DELETED (dead `IndicatorCache`).
- **`config.yaml`** — removed dangling keys `cached_indicators` (list) + `indicator_cache_enabled`; kept `cache_indicators: true`.
- **Live DuckDB tables dropped** via temp script `backend/_retire_indicator_cache.py` (since deleted): `indicator_values` **939,874 rows** dropped; `indicator_snapshot` **0 rows** dropped (dormant sibling, never written); both now NOT PRESENT.
- **KEPT (live contract):** the `indicator_values: dict[str, float]` **response field** on `ScreenSymbolResult` (schemas.py:117) + `models.py` — referenced by `frontend/src/types/screener.ts`, `ScreenerRow.tsx`, `ColumnToggle.tsx`. Out of scope to rename.

### Item 2 — Re-run GitNexus index
- `npx gitnexus analyze` said "Already up to date" (stale — index is commit-freshness based and skips the uncommitted Phase-1 working tree). Ran `npx gitnexus analyze --force` → **13,370 nodes | 21,993 edges | 423 clusters | 286 flows** (56.6s). Sprint 7/8 symbols (AdherenceDashboard, useAdherence, adherenceExport, etc.) now resolve via `gitnexus_query`.

### Item 3 — Fix frontend `package-lock.json` / esbuild drift
- Root cause: `vitest@4.1.11` requires `vite: ^6.0.0 || ^7.0.0 || ^8.0.0` **hard** → nested `node_modules/vitest/node_modules/vite`@6 → needs `esbuild@0.28.2` (the "missing esbuild@0.28.2" production-build blocker) AND orphans vitest under `npm ci` → `tsc` "Cannot find module 'vitest'".
- Fix: downgraded `vitest ^4.1.11 → ^3.2.4` in `frontend/package.json`; regenerated the lockfile **on the host** (container isn't a live mount for package files). Vitest@3.2.4 resolves 3.2.7, whose `vite` peer range accepts `vite@5.4.21` — no nested vite@6, no active esbuild@0.28.2 (remaining strings are orphaned `@esbuild/*` metadata).

## Verification
- **Backend:** full suite identical baseline — `docker exec conflu-api sh -lc 'cd /app/backend && python -m pytest -q --ignore=tests/e2e'` = **553 passed, 21 failed, 2 errors** (all pre-existing environmental: ambient `CONFLU_CORE__LOG_LEVEL=DEBUG`, education fixture `FileNotFound`, backtest/screen tests on untouched code). Config loads cleanly.
- **Retirement grep:** zero refs to `indicator_snapshot` / `indicator_values` in live `app/`; no test imports removed code.
- **GitNexus:** `gitnexus_query` + `gitnexus_context` resolve the Sprint 7/8 symbols (index fresh).
- **Frontend:** `npm ci` (374 pkgs) + `npm run build` **SUCCEEDS** (tsc passes, vite v5.4.21 → `dist/`). `npx vitest run` = **131 passed / 9 files** (identical to Sprint 8 baseline — zero regression).
- **`gitnexus_detect_changes`:** risk **critical / 161 symbols / 26 files** — but this is the **aggregate uncommitted working tree** (Sprints 1–8 phase work not yet committed, not a per-change blast radius). My housekeeping edits themselves are scoped (DB DDL/config/cache.py + package manifests) and verified non-breaking.

## Decisions
- D-41 records the housekeeping retirement (enforcing the D-32 cache-retirement decision) + GitNexus re-index + frontend build fix.

## Not done
- The `indicator_values` **response field** rename (out of scope; live API/UI contract).
- Production Docker image rebuild to confirm the esbuild blocker is gone end-to-end (optional follow-up; host `npm run build` already succeeded with the fixed lockfile).
- Committing the Phase-1 Sprints 1–8 + housekeeping working tree (user has not requested a commit).
