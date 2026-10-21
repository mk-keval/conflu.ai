# D-72: Forward-Sample Execution v0.1 — Measurement Integrity + Calendar-Day Time Stop

**Date:** 2026-10-19
**Status:** Accepted — implemented; sample started 2026-10-19 (run id 1; PM accepted).
**Execution timing superseded by D-73 (2026-10-21):** the PM/AMGN/CCK/MMM entries were
after-close phantom fills, are voided, and the sample clock restarts at the first actual
T+1 fill. The measurement fields from this decision remain in force.
**Branch:** `fix/technical-tab-empty`
**Related:** D-68 (SQLite journal), D-70 (honest validation), D-71 (two-month replay),
`docs/PAPER_TRADING/PIPELINE_AUDIT.md`

## Context

The 2026-10-19 pipeline audit found that the live paper-trading path could not answer
the pre-registered forward-test questions:

- screen/template and confluence were read from the verdict (where they do not exist),
  so every row stored `template = NULL` and `confluence_count = 0`;
- sector was read from the verdict (also absent), so every row stored `sector = NULL`
  and the 30% sector cap could never fire;
- the plan's `max_hold_days` (20/30/60 calendar days) was never persisted, so the live
  exit loop had no time stop;
- the 3 open rows from 2026-10-05/06 predate this instrumentation and cannot be part of
  a clean forward sample.

The user chose the recommended option: **measurement fixes + the documented time stop**,
then start the sample. Targets and the R:R gate were explicitly left alone as review
item A.

## Decision

1. **Attribution is recorded from the authoritative source.** `screen_name` and
   `confluence_score` come from the morning-brief ticker; market `regime` comes from the
   brief. Rejections store `template` and `regime` too.
2. **Sector comes from the analysis response** (`TickerAnalysisResponse.sector`), not the
   verdict body. The sector-exposure check uses the unhalved risk-based size as the upper
   bound, so the 30% cap cannot be understated when a CONDITIONAL trade is halved later.
3. **The plan's time stop is persisted and executed.** `max_hold_days` is written at
   entry. The plan states calendar days; `exits.infer_exit` counts trading bars, so
   `exits.hold_limit_bars` maps the cutoff to the first session on/after the calendar
   date in both exit paths (API and CLI).
4. **The 3 legacy rows are out-of-sample, not deleted.** They are flagged
   `exclude_from_stats=1`, remain open/visible, and are skipped by expectancy and rolling
   metrics. They still occupy their open-book slots (3 of 8).
5. **Everything else is frozen.** Target selection, R:R semantics, screen menus, regime
   permission, sizing and entry ranking are unchanged until the review trigger.

## Implementation

| Area | Change |
|---|---|
| Schema | `paper_trades.max_hold_days`, `paper_trades.exclude_from_stats` (default 0), `rejections.template`, `rejections.regime`; idempotent `ALTER TABLE` migration |
| Router | `_build_row` takes the brief ticker + market regime; response sector; unhalved size for portfolio fit; stores max hold |
| CLI | `build_row` parity with the router; same attribution and time-stop fields |
| Exits | `hold_limit_bars` calendar-day → bar-count conversion; both sync paths pass the converted limit |
| Scorecard | `verification` filters `exclude_from_stats` rows from template and rolling expectancy; `/journal/closed` and the frontend expectancy/adherence meters use the same filter (`ExpectancyMeter.tsx`, `AdherenceDashboard.tsx`) |
| Legacy data | NTNX/WBD/NVDA flagged in `data/paper_trades.db` after the migration |

## Verification

- 51 focused backend tests pass: journal schema/round-trip, CLI gate behavior, exit
  inference, scorecard exclusion, and workflow endpoints (including new router
  attribution + sector-cap tests). Frontend typecheck passes; the expectancy and journal
  tests pass (18 tests across the touched UI paths).
- Live DB migration verified: new columns exist; the 3 legacy rows show
  `exclude_from_stats = 1`. The first daily run completed on 2026-10-19 (run id 1):
  1 accepted (PM), 4 rejected, 0 exits; `workflow_runs` now has its first row.
  PM stored sector `Consumer Defensive`, template `Sector Rotation Holdings`, regime
  `Neutral`, confluence 4, and `max_hold_days = 30`.
- No change was made to targets, R:R gate logic, screen weights, or sizing.

## Consequences

- The forward sample can now be evaluated per screen/sector/regime, and review items A
  (MFE) and C (per-screen) become answerable. The first live entry (PM, Sector Rotation
  Holdings) has T1 ≈7.2R, so the unchanged target geometry is represented in the sample.
- The time stop is a real behavior change: open trades now close at the plan's calendar
  cutoff even if no target/stop is hit. This is why execution v0.1 is frozen before the
  first run.
- The 3 legacy rows remain in the open book (slot/heat accounting) but not in the stats.
  If they block new entries before they close, that is an operational cost of preserving
  the historical record rather than deleting it.

## Guardrails

- Do not backfill missed days.
- Do not change targets/R:R or the screen menus mid-sample; those are review decisions.
- The 30-closed-trade / 6-week trigger is counted only from
  `exclude_from_stats = 0` closed rows entered on/after the first `run_close`.
