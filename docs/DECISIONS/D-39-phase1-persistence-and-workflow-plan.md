# D-39: Phase-1 Guided Workflow — Persistence (DuckDB) + Approved 7-Sprint Plan (persona gap #4)

> **⚠️ SUPERSEDED (D-40):** Item 1 (Persistence: extend DuckDB) is **REVERSED** by user decision. Phase-1 workflow state now persists in **localStorage (frontend-only)**. DuckDB remains the analytical store; it is NOT used for workflow state. See [D-40](D-40-phase1-workflow-persistence-localstorage-supersede.md). Items 2-4 (Daily Routine, 7-sprint plan, housekeeping) remain in effect as amended by plan v2.1.

**Status:** Superseded (item 1) / Accepted (items 2-4)
**Date:** 2026-08-28
**Branch:** feat/swing-parity-upgrade
**Evidence:** DuckDB verified live — `data/conflu.duckdb` is 71.5 MB, last written today; 24 tables; `ohlcv` 7,523 rows read by `backtest.py`/`risk.py`; `indicator_values` 939,874 rows (legacy, retired by D-32). Oracle architecture consult (`bg_bab1517a`) and Momus plan critique (`bg_338b4072`) both reviewed. Plan: `.sisyphus/plans/phase1-elite-guided-workflow.md` v2.0.

## Context

The beginner working-professional persona walkthrough (`docs/PERSONA_VALIDATION_ANALYSIS.md`) exposed gap #4: **learning is reactive, not guided**. A zero-knowledge ~30-min/day user can read analysis but has no structured process — no daily routine, no pre-trade checklist, no scaled execution, no journaling loop. Gaps #1-2 (data/critical-bug) were closed earlier; gap #3 was closed via D-38.

Phase 1 turns the static analysis output into **in-flow guided trading process** (Daily Routine + Validation Gate + Execution Engine + paper-trade/adherence), with the blueprint success metric: **user completes 20 paper trades with >80% plan adherence.**

## Decision

1. **Persistence: extend DuckDB (LOCKED).** Add 5 workflow tables to `backend/app/core/database.py` `initialize_database()` following the existing DDL pattern (`CREATE TABLE IF NOT EXISTS` + indexes, `user_id VARCHAR DEFAULT 'default'`, `created_at TIMESTAMPTZ`). Tables: `daily_routines`, `daily_routine_steps`, `validation_gates`, `paper_trades`, `adherence_scores`.

   - **Rationale (resolved 2026-08-28):** User weighed localStorage (matches the app's fetch-on-demand philosophy) vs DuckDB. Verified: DuckDB is load-bearing for *analytical* data; the app's "don't warehouse" philosophy correctly applies to **analytical** data, but **user workflow state is a different category** — it's the user's durable history, not market data. Phase 1's core value is an 8-week journal + trade history; localStorage loses it on browser-switch/cache-clear, and the journal's *real-time reasoning* is the one thing that can't be faithfully recreated via re-entry. Oracle and Momus both independently validated DuckDB as correct/no-blocker.
   - **Frontend stays thin/abstracted:** a `workflowStore` behind clean read/write functions, local-first with background backend sync (D-C), so the storage backend is swappable later.

2. **Flexible "Daily Routine" (NOT time-locked).** 4-step user-driven sequential (Pre-Market → Market Open → Mid-Day → After-Close Journal), steps unlock 1→2→3→4, each timestamped; **Step 4 (After-Close Journal, 3-question thesis-vs-reality) is the mandatory adherence-driving step.** Gentle guidance, no hard time locks.

3. **7-sprint MVP, each independently demoable.** Ship all 6 core features; defer to Phase 2 (Sunday Command Center, Discovery Lab, Risk Command Center, Review Engine, Apprenticeship Mode, time-gating). Validation Gate simplified 7→5 steps (Liquidity, Structure, Risk/Reward w/ portfolio-fit, Edge Check, Conviction Score). Execution Engine wraps existing `/professional/position-size` (no new sizing math). Incorporate all Momus BLOCKERs (router prefix `/api/v1/workflow`, WorkflowPage sidebar/tab entry, TickerAnalysisPage "Validate Setup" button) + MAJORs (PlanStepType enum, conviction 0-10→high/med/low mapping, 13-step PaperTradePlanSteps taxonomy, regime glossary terms).

4. **Separate housekeeping (NOT this phase):** zombie `indicator_values` cache (939,874 stale rows from retired pre-D-32 pipeline). Disable `indicator_cache_enabled` flag (`config.py:185`) / drop stale rows / add cleanup task as an independent item — do NOT bundle with Phase 1.

## Consequences

- **Positive:** Durable, backend-queryable workflow history survives browser switches/cache clears — protects the journal + 20-trade adherence metric that is the phase's entire point.
- **Positive:** Reuses existing DuckDB seam + `/professional/position-size` + TermLink/`education.json` infrastructure; zero breaking API changes; low blast radius (additive router + new components).
- **Risk / deferral:** localStorage re-entry fallback exists but doesn't faithfully recreate journal timing — mitigated by DuckDB durability. Phase 2-5 features (Review Engine, Command Centers) need server-side trade aggregation — the DuckDB seam is already positioned for this.
- **Not done yet:** implementation. Phase 1 spans Sprints 1-8; work begins after user approves this plan.

## Files Touched
- `.sisyphus/plans/phase1-elite-guided-workflow.md` (the approved v2.0 plan)
- `docs/DECISIONS/index.md` (this entry)
- `docs/index.md` (Recent Activity)
- `INDEX.md` (Recent Activity)
