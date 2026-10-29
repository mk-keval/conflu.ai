# D-76: Forward Sample Versioning — v0.1 Closed for Verdicts, v0.2 Scored

**Date:** 2026-10-28
**Status:** Accepted — user decision (Q2 = C); code, schema and docs
**Branch:** `fix/technical-tab-empty`
**Related:** D-72/D-73 (execution v0.1), D-74 (measurement integrity), D-75
(pass bar), D-71 (replay separation), Q1/Q2 session 2026-10-28

## Context

By 2026-10-28 the v0.1 sample had **1 closed trade** (CRS, −1.00R) and two open
positions (SF, IOSP). The pipeline audit had found that the gate's R:R and the
exit walker's target did not agree — the gate can accept a trade for a reason
the exit never honors — and that the dynamic exit plan (`scale_out`,
`trail_type`, `trail_activation_r`) is computed and discarded. That is a
coherence defect in the design being measured, not a strategy hypothesis.

The user chose **Q2 = C**:

1. **Close v0.1 for verdict purposes** — no pass/fail verdict will be issued
   from it; it remains reference data.
2. **Keep the daily loop running** — fills, expiries and execution diagnostics
   continue as **interim** data while Bundle A is specified and built.
3. **Start FWD-v0.2** at the first fill after the Bundle A spec is frozen;
   v0.2 is the sample the canonical scorecard judges.

Without an explicit version, "which rows count" would depend on a hand-applied
`exclude_from_stats` flag. That is fragile, invisible in the journal, and easy
to forget on the day the new sample starts. It also invites the wrong fix:
re-deciding old rows under the new rules, which would destroy the audit trail
and inject hindsight.

## Decision

Add an immutable `sample_version` to `paper_trades` and `pending_orders`.

| Version | Rows | Status |
|---|---|---|
| `v0.1` | Every row that predates the column (10 journal rows, 5 orders) | **Closed for verdicts 2026-10-28**; reference only, never a verdict |
| `interim` | New rows from 2026-10-29 until the v0.2 spec freeze | Execution diagnostics only; **never evidence** |
| `v0.2` | First fill after the Bundle A spec freeze | **Scored sample** |

Rules:

- **The version is set once, on insert.** A re-run, import or entry update never
  moves an existing row between samples.
- **A filled pending order inherits its order's version.** A v0.1 order cannot
  become an interim or v0.2 journal row.
- **A CSV without the column is a legacy artifact** and imports as `v0.1`, not
  as the current sample.
- **The scorecard counts only the scored version** (`v0.2`), with the existing
  `voided = 0` and `exclude_from_stats = 0` filters. v0.1 and interim rows are
  printed as **reference** — visible, never folded into the headline.
- **`verify_journal.py` fails** on an unknown version or on a filled order whose
  journal row carries a different version.

`sample_version` is orthogonal to `voided` / `exclude_from_stats`: those mark
individual bad or legacy rows; this marks the design a row belongs to.

## Why not rewrite past decisions under the new logic

The user asked whether the old rows could be re-decided with the v0.2 rules.
**No.** The journal is the record of what the system actually did:

- A v0.2 gate applied to the 2026-10-26 CRS signal is a **simulation**, not the
  trade that happened. Rewriting the row turns history into hindsight.
- The comparison `v0.1` vs `v0.2` is only meaningful if each row was traded
  under its own rules.
- Using CRS's outcome to decide whether the entry should have happened is
  look-ahead by construction.
- A system that silently rewrites its own history is not auditable.

The legitimate version of the question is a **separate labeled replay**:
`rules_version = 'v0.2'`, same window/universe/costs, run once after the spec
freeze, never mixed with the journal and never counted as confirmatory evidence
(H-09; D-71 rules).

## Implementation

| File | Change |
|---|---|
| `backend/app/domain/workflow/sample.py` | New: versions, labels, `SCORED_SAMPLE_VERSION` (v0.2), `CURRENT_SAMPLE_VERSION` (interim), `normalize_sample_version`, `is_scored_version` |
| `backend/app/domain/workflow/journal_store.py` | `sample_version` on both tables; first-migration backfill to v0.1; insert-only version; pending-order inheritance; CSV import defaults to v0.1; export includes the column |
| `backend/app/domain/workflow/pending.py` | `build_filled_row` copies the order's version |
| `backend/app/domain/workflow/verification.py` | `in_scored_sample`, version-filtered expectancy/rolling queries, `find_sample_version_issues` |
| `scripts/scorecard.py` | Scores only the scored version; reports other versions as reference; adds the D-75 pass bar and the 8R/12R drawdown breaker; time trigger is 6 weeks after the first **scored** fill |
| `scripts/verify_journal.py` | Version check is a FAIL condition |
| Tests | New `test_scorecard.py`; version/migration/inheritance cases in `test_journal_db.py`, `test_pending.py`, `test_verification.py`, `test_verification_integrity.py` |

## What did not change

- No target, gate, screen, menu, weight, sizing rule, regime permission or exit
  rule changed.
- No historical decision was re-decided; no row was deleted, voided or relabeled
  beyond the one-time v0.1 backfill.
- The daily loop, fill rules and execution model are unchanged.
- D-75's pass bar and kill rule are unchanged; they now apply to v0.2.
- The three plan-R:R warnings remain logged, not fixed.

## Verification

- Migration on the live DB: 10/10 `paper_trades` rows and 5/5 `pending_orders`
  rows are `v0.1`; DUK remains the only pending order.
- `python scripts/verify_journal.py` → **PASS**: 0 phantom fills, 0 dollar-P&L
  mismatches, 0 sample-version issues, 3 plan-R:R warnings.
- `python scripts/scorecard.py` → scored v0.2: 0 closed; reference v0.1:
  1 closed, −1.00R, −$30.01 net.
- Focused suites: 56 journal/pending/verification/scorecard tests and 25
  workflow/paper-trade endpoint tests pass.
- Pre-migration backup: `data/backups/paper_trades_20261029T002004Z.db`.

## Open items

| Item | Status |
|---|---|
| Bundle A spec: target hierarchy, gate R:R, exit per family, dynamic-plan wiring, replay alignment | **Open — next** |
| Flip `CURRENT_SAMPLE_VERSION` and `SCORED_SAMPLE_VERSION` to `v0.2` in the freeze commit | After the spec is frozen |
| Pre-register FWD-v0.2 (D-75 bar, 6-week/30-close trigger) | After the spec is frozen |
| H-09 exploratory replay under `rules_version='v0.2'` | After the spec is frozen; not evidence |
| Interim rows in the scorecard | Excluded by version; execution diagnostics only |
