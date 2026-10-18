# D-68: Paper Journal → SQLite + One-Click EOD Combined Run (A+B)

**Date**: 2026-10-18
**Status**: Accepted — plan authorizes P1–P4; implementation starts P1 in the same session series
**Branch**: fix/technical-tab-empty
**Plan**: [.sisyphus/plans/paper-journal-sqlite-eod.md](../../.sisyphus/plans/paper-journal-sqlite-eod.md)

## Context

- The paper-trade journal is CSV-first (`docs/paper_trades/*.csv`, D-7/D-51) and is effectively maintained/read like an Excel sheet. The user wants daily trades visible in the UI with no sheet maintenance.
- The workflow has two touchpoints (A: gate enforcement → entries; B: exit sync). Because they must be run **separately**, the user frequently forgets one → nothing logged → the measurement loop starves (the 2026-09 evidence audit, D-50, exists precisely because the record was never closed).
- The UI surfaces built for this (`DailyRoutine`, `ExpectancyMeter`, `OpenPositionsTracker`, `AdherenceDashboard`) currently render empty: `hydrateFromJournal()` is dead code — implemented but never called — and `paperTrades` is excluded from localStorage persistence. This is why the CSV/Excel remained the de-facto interface.
- Three latent bugs surface once the rhythm becomes "run both after close": Touchpoint A **overwrites** today's file on re-run (`open("w")`), dates are stamped in **UTC** (evening runs roll to the next day), and exits have **no same-day guard**.

## Decision

1. **Storage → SQLite.** The journal of record becomes `data/paper_trades.db` (stdlib `sqlite3`, WAL, 3 tables: `paper_trades`, `rejections`, `workflow_runs`). DuckDB stays analytics-only (ADR-001 untouched). One-time import of the existing CSVs (files preserved untouched); CSV becomes an **export** format. Upsert key `(date_entered, symbol)` makes same-day re-runs idempotent.
2. **One-click after-close combined run.** `POST /workflow/paper-trades/run-close` runs Touchpoint A then Touchpoint B (apply) in one call — the button in the Daily Routine tab, mirrored by `paper_trade_from_brief.py --run-close`. Individual dry-run/review buttons remain.
3. **Missed entry days stay honest gaps.** Exits self-heal (B walks OHLCV from each entry date); missed entries are not backfilled, and the gap is visible in a new runs strip (`workflow_runs`).
4. **No scheduler.** Button only. An OS-level Task Scheduler recipe remains a future, zero-app-weight option.
5. **Correctness rails carried with the move:** ET market dates (`zoneinfo`), upsert (kills the overwrite bug), same-day exit guard, `entry_timing='eod'` + entry-bar excursion exclusion, run logging.
6. **UI visibility:** hydration wired on mount/focus/post-action; new Journal tab (14-day runs strip, trades table with filters, rejections, CSV export).

## Rationale

- **SQLite over DuckDB** for the journal: row-level CRUD and concurrent small writes are SQLite's domain; DuckDB's single-writer analytics model is the wrong tool and D-32 already made DuckDB explicitly non-load-bearing. Zero new dependencies, one file, trivial backup (`copy`), fits the "light" constraint.
- **One combined run**: the failure mode is a human forgetting one of two steps, not a missing capability. A single after-close action removes the failure mode; the exit logic already skips the entry bar, so EOD semantics are clean.
- **Honest gaps**: the repo's evidence culture (R23/R24 corrections in D-50/51) already established that a tidy-looking but fabricated sample is worse than an incomplete one. Backfill would contaminate the only sample that matters.
- **Keeping the exact endpoint/JSON shapes** and the `journal.py` public API means gate, sizing, exits, verification, and the frontend need no parallel rewrite — the swap is surgical.

## Consequences

- **Positive:** no Excel/CSV maintenance; one action per day; journal visible in the UI; same-day re-runs safe; expectancy-per-template/regime starts working (template/regime columns were silently dropped by the CSV writer — the DB stores them).
- **Trade-offs:** a new store file (plus backup discipline); SQLite write concurrency must use WAL + short transactions; the CLI and API must both go through the store module to avoid writer divergence (the old CSV patch path is deleted).
- **Migration:** automatic on first boot when the DB is empty and CSVs exist; logged counts; CSVs remain on disk as a frozen backup. Export CSV endpoint exists for any Excel need.

## Validation

- Plan acceptance criteria (§11 of the plan): DB is journal of record; one-click run lands entries+exits+run row; idempotent re-run; ET dates; existing endpoint shapes unchanged; backend 834+ tests + frontend vitest/tsc/build green.

## Related

- Supersedes the storage choice of **D-7** (CSV as source of truth → SQLite as source of truth, CSV as export); amends the interplay with **D-40** (localStorage decision unaffected — workflow state stays in localStorage; journal was already backend-owned).
- Builds on **D-50/D-51/D-53/D-56/D-59/D-64** (gate enforcement spine, schema v2, auto exits, expectancy tracking).
- Plan: [.sisyphus/plans/paper-journal-sqlite-eod.md](../../.sisyphus/plans/paper-journal-sqlite-eod.md)
- Session: [2026-10-18 paper journal DB + EOD combined run (planning)](../SESSIONS/2026-10-18_paper-journal-db-eod-planning.md)
