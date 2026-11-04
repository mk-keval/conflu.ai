# Session Log: 2026-10-19 — Forward-Sample Execution v0.1 (Measurement + Time Stop)

> Application source changed: journal schema/migration, router + CLI attribution,
> sector cap, calendar-day time stop, scorecard exclusion filter, tests. Decision: **D-72**.
> The forward sample starts on the first daily `run_close` after this change.

**Date:** 2026-10-19
**Branch:** `fix/technical-tab-empty`
**Scope:** make the forward paper sample measurable, apply the plan's documented time stop,
and exclude the 3 pre-instrumentation rows — without touching targets, R:R or screens.

## Prompt

After the read-only pipeline audit, the user chose **“Measurement + time stop
(Recommended)”** for starting the forward sample: fix the bookkeeping, persist and execute
the plan's 20–60-day time stop, make the 30% sector cap real, and exclude the 3 legacy
rows from the scorecard. Targets and the R/R gate stay untouched for review item A.

## What changed

| Area | File | Change |
|------|------|--------|
| Schema | `backend/app/domain/workflow/journal_store.py` | `max_hold_days`, `exclude_from_stats` on trades; `template`/`regime` on rejections; idempotent `ALTER TABLE` migration; `set_exclude_from_stats` |
| Attribution | `backend/app/api/routers/workflow.py` | `_build_row` reads screen/confluence from the brief ticker, sector from the analysis response, market regime from the brief; stores `max_hold_days`; rejection dicts tagged |
| Attribution | `backend/scripts/paper_trade_from_brief.py` | CLI parity: same attribution + time-stop fields |
| Sector cap | router + CLI | Portfolio-fit check uses the unhalved risk-based size (upper bound) |
| Exits | `backend/app/domain/workflow/exits.py` | `hold_limit_bars` converts calendar days to the first session on/after the cutoff; both exit paths pass the converted value |
| Scorecard | `backend/app/domain/workflow/verification.py` | Template + rolling expectancy skip `exclude_from_stats=1` |
| API | `backend/app/api/routers/workflow.py` | Rejection response includes `template`/`regime` |
| Tests | `backend/tests/` | Router attribution + sector cap, CLI attribution, time-stop conversion, schema round-trip, exclusion filter, updated endpoint stub |
| Docs | audit, review, README, D-72, indexes | status + operating notes |

## Verification

- 51 focused backend tests pass:
  `test_journal_db.py`, `test_paper_trade_from_brief.py`, `test_exits.py`,
  `test_verification.py`, `test_workflow_endpoints.py`. Frontend typecheck passes; the
  touched UI tests pass (18 tests).
- Live DB migrated successfully; new columns verified.
- NTNX/WBD/NVDA flagged `exclude_from_stats=1`; they remain open and visible.
- First daily run completed 2026-10-19 (run id 1): **1 accepted (PM)**, 4 rejected,
  0 exits. PM stored `sector=Consumer Defensive`, `template=Sector Rotation Holdings`,
  `regime=Neutral`, `confluence_count=4`, `max_hold_days=30`; T1 ≈7.2R.
- Target selection, R:R gate, screen menus, regime permission, sizing and entry ranking
  were not changed.

## Important behavior note

The plan's `max_hold_days` is stated in **calendar days**, while `infer_exit` counts
trading bars. `hold_limit_bars` maps the calendar cutoff to the first session on/after
that date. This is the only approved behavior change in execution v0.1.

## Next

1. Repeat the one-go after-close run each trading day; do not backfill missed days.
2. Confirm each run writes exactly one `workflow_runs` row and new entries show
   `template`, `sector`, `regime`, `max_hold_days`.
3. Do not change targets/R:R or screens until the trigger (30 closed forward trades or
   ~6 weeks from the first run).
4. At the trigger: run `FORWARD_TEST_REVIEW.md` items A–D; use only
   `exclude_from_stats=0` closed rows for the scorecard and kill rule.
