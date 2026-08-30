# D-40: Phase-1 Workflow Persistence — SUPERSEDE DuckDB → localStorage (frontend-only)

**Status:** Accepted (implemented, Sprint 1 verified)
**Supersedes:** D-39 item 1 (DuckDB persistence for Phase-1 workflow state)
**Date:** 2026-08-28
**Branch:** feat/swing-parity-upgrade
**Evidence:** User explicitly chose **localStorage (frontend-only)** via the decision question tool (answer: "Go localStorage (frontend-only) (Recommended)"). User reminder: *"Wait we did talk that localstorage is fine, how are we still doing duckdb?"* — the DuckDB backend was written (5 DDL tables + `domain/workflow/` + `api/routers/workflow.py`), then **fully reverted** (verified: `database.py` 0 workflow-table refs, workflow router/domain deleted, clean git diff). Plan updated to v2.1. Sprint 1 shipped and verified: vitest 57 passed (25 new + 32 existing, no regression); `tsc --noEmit` zero non-vitest errors; backend untouched.

## Context

D-39 locked DuckDB as the persistence layer for Phase-1 workflow state (Daily Routine, Validation Gates, Paper Trades, adherence), reasoning that a durable 8-week journal + trade history matters and localStorage loses it on browser-switch/cache-clear. During Sprint 1 implementation the user corrected the decision — localStorage had already been agreed as fine for this workflow state, and the app's "don't warehouse" philosophy was the user's stated preference.

This is a **decision reversal**, not an addition: the storage backend for Phase-1 workflow state changes from server-side DuckDB to browser-side localStorage.

## Decision

**Phase-1 workflow state persists in `localStorage` (frontend-only).** No DuckDB tables for workflow state. No backend workflow router/models. The 5-table DuckDB DDL work is reverted and abandoned for this phase.

1. **Storage: localStorage via Zustand `persist`** under key `conflu-workflow-v1`. `frontend/src/store/workflowStore.ts` is local-first, writes through `createJSONStorage`, with an in-memory `memoryStorage()` fallback when `localStorage` is unavailable (non-browser/vitest) so the store works in tests.
2. **Pure logic modules** (`frontend/src/workflow/routine.ts`, `adherence.ts`) keep all domain math side-effect-free and unit-testable; the store is a thin persistence+state layer. This keeps the storage backend swappable later (a future backend sync can read from the store shape) — preserving the D-39 "frontend stays thin/abstracted" goal.
3. **Accepted losses (browser-switch / cache-clear):** journal timestamps + trade/adherence history are lost with the browser profile. Mitigated by the local-first re-entry design: any state can be re-done and returned to by the user. This is the trade the user explicitly accepted.
4. **Not affected:** DuckDB remains the load-bearing analytical store (D-32 align, backtest/risk read `ohlcv`). This decision touches **workflow/user state only**, not market data.
5. **Deferred to Phase 2+, if/when server-side aggregation is needed:** the swappable store-shape seam (decision 2) is the pivot point. No work now.

## Consequences

- **Positive:** Implementation is dramatically smaller and simpler — no new backend tables, router, or models; zero API surface; zero breaking changes; fully additive frontend. Ship velocity for the remainder of Phase 1 increases.
- **Positive:** Aligns with the app's fetch-on-demand, don't-warehouse philosophy for this state category; matches the user's stated preference.
- **Positive:** Whole Phase-1 feature set (Daily Routine, Validation Gate, Execution Engine, paper trades, adherence) runs entirely client-side and remains viest-complete offline.
- **Risk / accepted:** journal + history are browser-scoped. A browser switch or cache clear resets workflow state (not market/analysis data). User accepted this; design keeps every step re-entrable.
- **Future:** Review Engine / Command Centers (Phase 2-5) that need server-side trade aggregation will introduce a backend store then — the store-shape seam keeps that open.

## Files Touched (Sprint 1)

- `frontend/src/types/workflow.ts` — NEW: `DailyRoutine`, `RoutineStep`, `ValidationGate`/`GateStep`, `PaperTrade` + `PAPER_TRADE_PLAN_STEPS` (5/3/1/3/1 = 13), `ADHERENCE_MAX_STEPS`.
- `frontend/src/workflow/routine.ts` — NEW: `ROUTINE_STEPS` (Pre-Market/Market Open/Mid-Day/After-Close Journal), step-completion logic.
- `frontend/src/workflow/adherence.ts` — NEW: rolling-20 adherence %, streak, 13-step taxonomy use.
- `frontend/src/store/workflowStore.ts` — NEW: Zustand store, persist `conflu-workflow-v1`, memory fallback.
- `frontend/src/types/index.ts` — MODIFIED: workflow type/const re-exports (additive only).
- `frontend/src/workflow/__tests__/*`, `frontend/src/store/__tests__/*` — NEW: 25 tests (57 total green).
- `backend/app/core/database.py`, `backend/app/api/routers/workflow.py`, `backend/app/domain/workflow/` — REVERTED (DuckDB undone).
- `.sisyphus/plans/phase1-elite-guided-workflow.md` — v2.1 (localStorage).
- `docs/DECISIONS/D-39-phase1-persistence-and-workflow-plan.md` — annotated SUPERSEDED (item 1).
- `docs/DECISIONS/index.md`, `docs/index.md`, `INDEX.md` — index refresh.
