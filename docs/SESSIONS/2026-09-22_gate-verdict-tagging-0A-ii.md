# Session Log — 2026-09-22: Gate Verdict Tagging (0A-ii)

## Summary
Implemented Phase 0A-ii gate verdict tagging in the historical control study script (`control_study_voided_cohort.py`). This completes the counterfactual validation of the gate logic against the voided 2026-09 bypass cohort.

## Changes Made

### `backend/scripts/control_study_voided_cohort.py`
Added 0A-ii gate verdict tagging functionality:

1. **New `tag_gate_verdict()` function** (lines 407-451):
   - Builds `GateInput` from historical row data (symbol, entry_price, stop_loss, targets, sector, position_size_pct)
   - Calls existing `evaluate_gate()` from `backend.app.domain.workflow.gate`
   - Returns `(gate_verdict, gate_failed_step)` where verdict is PASS/FAIL/CONDITIONAL and failed_step is the first step causing non-PASS

2. **Gate verdict tagging loop** (lines 694-708):
   - Iterates over all 31 cohort rows
   - Stores `gate_verdicts` and `gate_failed_steps` lists aligned with row order
   - Prints summary: PASS/FAIL/CONDITIONAL counts

3. **Gate-PASS subset extraction** (line 724):
   - Filters rows where `gate_verdict == "PASS"` for separate exit replay

4. **Enhanced markdown report** (lines 49-85 in render_markdown):
   - New "## Gate verdict tagging (0A-ii)" section with table: date, symbol, action, gate_verdict, gate_failed_step
   - Totals row showing PASS/FAIL/CONDITIONAL counts
   - Exit replay comparison section when `--backfill-exits` is used (shows full cohort vs gate-PASS subset metrics)

5. **Dual exit replay** (lines 713-737):
   - Runs exit replay on full cohort (existing behavior)
   - Runs exit replay on gate-PASS subset (new)
   - Prints comparison metrics in console and report

## Verification

### Offline run (no network):
```bash
python backend/scripts/control_study_voided_cohort.py
```
Output:
- 31 rows from 7 files processed
- Manufacture detector: 4 manufactured, 0 structural, 27 indeterminate
- Gate verdict tagging: 0 PASS, 0 FAIL, 31 CONDITIONAL (all CONDITIONAL due to missing liquidity data in bypass cohort)
- Report written to `docs/SESSIONS/2026-09-18_ungated-cohort-control-study.md`

### Test results:
- All 13 control study tests pass (`test_control_study_voided_cohort.py`)
- All 17 gate tests pass (`test_gate.py`)
- 19/20 synthesis geometry tests pass (1 pre-existing failure in `test_downgrade_to_watch_when_both_fail` unrelated to this work)

## Report Output
The generated report now includes:
1. Manufacture detector (R25 classification) — existing
2. **Gate verdict tagging (0A-ii)** — **NEW** — table with all 31 rows tagged
3. Stop-distance distribution & sizing check — existing
4. Exit replay comparison (when `--backfill-exits` used) — **NEW** — full cohort vs gate-PASS subset

## Next Steps
- Once 1H source fix lands (structural targets for R/R measurement), the 5d R:R floor (Step 5d) will activate
- Re-run 0A-ii with `--backfill-exits` to compare expectancy/profit factor of gate-PASS vs full cohort
- This will validate whether the gate improves outcomes before live deployment