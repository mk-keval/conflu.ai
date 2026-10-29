# 2026-10-28: Forward Sample Versioning (D-76)

**Scope:** code, schema, tests, docs. **No trading rule changed.**

## What was decided

Q2 = **C** (user decision):

- **FWD-v0.1 is closed for verdict purposes.** Its 1 closed trade (CRS, −1.00R)
  and 2 open positions (SF, IOSP) are reference only; no pass/fail verdict will
  be issued from them.
- **The daily loop continues** as `interim` data from 2026-10-29. Fills, expiries
  and execution diagnostics are tracked; they are never evidence.
- **FWD-v0.2 is the scored sample.** Its clock starts at the first fill after the
  Bundle A spec (target hierarchy, gate R:R, exits per family, dynamic-plan
  wiring) is frozen and pre-registered.

No past row was re-decided under the new logic. The legitimate what-if is a
separate labeled replay (`rules_version='v0.2'`, H-09), run once after the freeze
and never counted as confirmatory evidence.

## Implementation

- New `backend/app/domain/workflow/sample.py`: `v0.1` / `interim` / `v0.2`,
  `SCORED_SAMPLE_VERSION = v0.2`, `CURRENT_SAMPLE_VERSION = interim`.
- `paper_trades` and `pending_orders` carry `sample_version`. The first
  migration backfills every existing row/order to `v0.1`; the DDL default for
  future raw inserts is `interim` (fail-safe: unscored).
- `upsert_entry` sets the version on insert only — a re-run or import cannot move
  a row between samples. `build_filled_row` copies the pending order's version.
- Legacy CSV imports without the column default to `v0.1`, not the current
  sample.
- `verification.in_scored_sample` and version-filtered expectancy/rolling
  queries; `find_sample_version_issues` fails on unknown versions or a filled
  order whose journal row differs.
- `scripts/scorecard.py` scores only v0.2 and prints v0.1/interim as a reference
  table. It now also computes the D-75 pass bar and the 8R/12R drawdown breaker.
  The time trigger is 42 days after the first **scored** fill.
- `scripts/verify_journal.py` treats sample-version issues as a FAIL.

## Live DB migration

- Pre-migration backup: `data/backups/paper_trades_20261029T002004Z.db`.
- `paper_trades`: 10/10 rows `v0.1`.
- `pending_orders`: 5/5 `v0.1`; DUK remains the only `pending` order.
- `verify_journal.py` → **PASS**: 0 phantom fills, 0 dollar-P&L mismatches,
  0 sample-version issues, 3 plan-R:R warnings (unchanged).
- `scorecard.py` → scored v0.2: 0 closed; reference v0.1: 1 closed, −1.00R,
  −$30.01 net, MFE gap +4.72R.

## Tests

- 56 focused journal/pending/verification/scorecard tests pass.
- 25 workflow/paper-trade endpoint tests pass.
- New coverage: insert-only version, explicit/unknown version, pending-order
  version, fill inheritance, scored-version filtering, version-mismatch
  detection, scorecard reference filtering, D-75 pass-bar branches, drawdown.

## What did not change

Targets, R:R gate, screens, menus, weights, sizing, regime permission, exit
rules, fill rules, costs, the daily loop and D-75's bar/kill rule. No historical
row was rewritten.

## Next

1. Write and freeze the **Bundle A** spec (P1-6/P1-7/P1-8, P4-15): target
   hierarchy, the R:R metric the exit actually pays, exit policy per setup
   family, and dynamic-plan wiring.
2. Flip `CURRENT_SAMPLE_VERSION` and `SCORED_SAMPLE_VERSION` to `v0.2` in the
   freeze commit; pre-register FWD-v0.2 with the D-75 bar and the 6-week/30-close
   trigger.
3. Implement, add tests, run the H-09 replay (exploratory, `rules_version='v0.2'`).
4. Start the v0.2 clock at the first fill after the freeze. `interim` rows stay
   out of both scorecards.
