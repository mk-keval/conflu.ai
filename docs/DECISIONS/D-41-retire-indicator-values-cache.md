# D-41: Housekeeping — Retire Zombie `indicator_values` Cache + Frontend Build Fix

**Status:** Accepted (implemented + verified, housekeeping follow-up to Phase 1)
**Date:** 2026-08-29
**Branch:** feat/swing-parity-upgrade
**Evidence:** All three deferred housekeeping items (flagged in D-39/D-40) completed and verified: (1) zombie `indicator_values` cache retired — live DuckDB tables dropped, DDL/init/config/dead-code removed, backend suite identical baseline; (2) GitNexus index refreshed via `analyze --force` so Phase-1 Sprint 7/8 symbols are queryable; (3) frontend `package-lock.json`/esbuild drift fixed — vitest downgrade restored `npm ci` + `npm run build` and un-orphaned vitest.

## Context

Three housekeeping items were deferred out of Phase 1 (Sprints 1–8) planning and teed up as "Lets fix the deferred ones":

1. **Zombie `indicator_values` cache.** D-23 originally built an indicator cache; D-32 moved the platform to TV-Screener-first / on-demand, retiring the indicator-cache precompute path. The decision to retire the cache was already made in D-32, but the **DuckDB table (`indicator_values`, ~939,874 stale rows) and several DDL/config/dead-code remnants were never actually deleted** — they kept being created at app startup and never read (no on-demand writer, no consumer). Also discovered opportunistically: `indicator_snapshot` was an equally-dormant sibling table that had never been written at all (0 rows).
2. **Stale GitNexus index.** `npx gitnexus analyze` reported "Already up to date" even though Phase-1 Sprint 7/8 added new symbols — the index is commit-freshness-based and skipped uncommitted working-tree changes. Sprint 7/8 symbols (AdherenceDashboard, useAdherence, adherenceExport, etc.) were not queryable.
3. **Frontend `package-lock.json` / esbuild drift.** `vitest@4.1.11` required `vite: ^6.0.0 || ^7.0.0 || ^8.0.0` as a **hard** dependency → npm installed nested `node_modules/vitest/node_modules/vite`@6 → needed `esbuild@0.28.2`, which failed to resolve on this host (the "missing esbuild@0.28.2" production-build blocker). It also caused `tsc` "Cannot find module 'vitest'" because `npm ci` orphaned vitest when it couldn't satisfy the vite conflict.

## Decision

1. **Retire the zombie indicator cache completely (D-32 intent, now actually enforced):**
   - Remove `INDICATOR_VALUES_DDL` + `INDICATOR_SNAPSHOT_DDL` constants and their two init `con.execute` calls from `backend/app/core/database.py`.
   - Remove dead config flags `cached_indicators` + `indicator_cache_enabled` from `backend/app/core/config.py`; keep + mark **DEPRECATED** `cache_indicators` (a generic "materialized views" toggle still valid in `config.yaml`).
   - Delete `backend/app/infrastructure/screener/cache.py` (dead `IndicatorCache`).
   - Remove dangling YAML keys from `config.yaml` (`cached_indicators` list + `indicator_cache_enabled`); keep `cache_indicators: true`.
   - **Drop the live DuckDB tables** `indicator_values` (939,874 rows) and `indicator_snapshot` (0 rows) via a temp script (since deleted). Both now NOT PRESENT.
   - **KEEP the live contract** `indicator_values: dict[str, float]` on `ScreenSymbolResult` (schemas.py:117) and `models.py` — that is a **response field name**, referenced by `frontend/src/types/screener.ts` + `ScreenerRow.tsx` + `ColumnToggle.tsx`. Renaming it is out of scope (would break the live API/UI contract).
2. **Refresh the GitNexus index** with `npx gitnexus analyze --force` so the uncommitted Phase-1 working tree is indexed (13,370 nodes | 21,993 edges | 423 clusters | 286 flows).
3. **Fix the frontend build drift:** downgrade `vitest ^4.1.11 → ^3.2.4` in `frontend/package.json` (resolves to 3.2.7, whose `vite` peer range is `^5.0.0 || ^6.0.0 || ^7.0.0-0` — compatible with the project's `vite@5.4.21`), and regenerate `frontend/package-lock.json` **on the host** (the `conflu-frontend` container only live-mounts `src`, `public`, `index.html` — not package manifests).

## Consequences

- **Positive:** No more 939,874 stale rows created/recreated at every startup; startup faster and DB cleaner. Removing dead code/config shrinks the surface and eliminates confusion (the retired cache was documentation of a path already abandoned in D-32).
- **Positive:** GitNexus now resolves Sprint 7/8 symbols → `gitnexus_impact` / `gitnexus_context` are authoritative again for the new dashboard/workflow code.
- **Positive:** `npm ci` (374 pkgs) + `npm run build` **SUCCEED** (tsc passes, vite v5.4.21 → `dist/`); vitest no longer orphaned, so `tsc --noEmit` finds the module; **`npx vitest run` = 131 passed / 9 files** (identical to the Sprint 8 baseline — zero regression). No active `esbuild@0.28.2` remains post-lockfile-regen (the remaining `0.28.2` strings are orphaned `@esbuild/*` metadata).
- **Risk / none material:** The `indicator_values` response *field* is untouched — only the retired DuckDB *table* and cache plumbing were removed. Backend suite verified identical baseline (553 pass / 21 fail / 2 errors — all pre-existing environmental: ambient `CONFLU_CORE__LOG_LEVEL=DEBUG`, education fixture `FileNotFound`, and backtest/screen tests on untouched code).
- **Future:** A real on-demand indicator layer that needs a warehouse can revisit; D-32's TV-first/on-demand philosophy is unchanged.

## Files Touched

- `backend/app/core/database.py` — REMOVED `INDICATOR_VALUES_DDL` + `INDICATOR_SNAPSHOT_DDL` + their init `con.execute` calls.
- `backend/app/core/config.py` — REMOVED `cached_indicators` + `indicator_cache_enabled`; `cache_indicators` kept + marked DEPRECATED.
- `config.yaml` — REMOVED `cached_indicators` list + `indicator_cache_enabled`; kept `cache_indicators: true`.
- `backend/app/infrastructure/screener/cache.py` — DELETED (dead `IndicatorCache`).
- `backend/_retire_indicator_cache.py` — TEMP (since deleted) used to drop the live tables.
- `frontend/package.json` — vitest `^4.1.11` → `^3.2.4`.
- `frontend/package-lock.json` — regenerated (root `vitest: ^3.2.4`, `node_modules/vitest` = 3.2.7, vite = 5.4.21, no nested `node_modules/vitest/node_modules/vite`).
- `docs/DECISIONS/D-41-retire-indicator-values-cache.md` — this record.
- `docs/SESSIONS/2026-08-29_housekeeping-indicator-cache-and-build-fix.md` — session log.
- `docs/index.md`, `INDEX.md`, `docs/DECISIONS/index.md` — index refresh.
