# 2026-10-28: P0 Measurement Integrity — Correct P&L, Plan Provenance, Scorecard (D-74)

**Session type:** Measurement fix + documentation
**Decision:** [D-74](../DECISIONS/D-74-p0-measurement-integrity.md)
**Branch:** `fix/technical-tab-empty`
**HEAD at start:** `f1797e5` (`fix(workflow): fill after-close signals from next-session bars (D-73)`)
**Status:** Implemented and verified; changes uncommitted at session end

## Why

D-73 fixed the execution model (pending orders / T+1 fills) and restarted the forward
sample at the first actual fill (2026-10-22, SF @ 65.40). The docs said P0 measurement
was done. A live-journal audit found three defects that made the reported numbers wrong:

1. **Dollar P&L used notional, not risk.** `pnl_usd = realized_r × account_value ×
   position_size_pct/100`. CRS stored −$1,624.99; the actual trade was −$25.17 gross /
   −$30.01 net.
2. **Gate R:R and stored plan R:R did not reconcile.** CRS 4.32 vs 11.89; IOSP 6.15 vs
   3.99; SF 6.47 vs 4.36. `target_3` was never persisted, and the gate's `risk_reward`
   can be stale independently of the targets.
3. **Live dollars were gross, backtests net.** The replay convention is 10 bps fee +
   5 bps slippage per side.

All three are measurement issues. None changes which trades are taken or how they exit.

## What changed

| Area | Change |
|---|---|
| P&L | New `backend/app/domain/workflow/pnl.py`: canonical gross / costs / net; R stays a gross price multiple |
| Schema | `target_3`, `plan_rr`, `target_1_r`, `pnl_gross_usd`, `costs_usd`; idempotent migration; pending orders get `target_3` |
| Entry | `_build_row` stores the third target and plan metrics; `risk_reward_planned` remains the gate's number |
| Fill/exit | `pending.py` / router use canonical dollars; same-session stops get net P&L too |
| Integrity | `verification.py` gains `find_phantom_fills`, `find_pnl_mismatches`, `find_plan_rr_gaps`; `in_forward_sample` filter |
| Scripts | `verify_journal.py` (PASS/FAIL), `scorecard.py` (one page), `backup_journal.py`, `backfill_p0_measurement.py` |
| Docs | `SCORECARD.md`, `PRE_REGISTRATION.md`, `HYPOTHESIS_LOG.md`, `D-74`, README/REVIEW/AUDIT updates |
| Live DB | Backed up to `data/backups/paper_trades_20261028T230900Z.db`; backfilled 10 rows |

## Verification

```text
python scripts/verify_journal.py
[PASS] Phantom fills: 0
[PASS] Dollar P&L: 0 mismatch(es)
[WARN] Plan R:R gaps: 3
PASS

python scripts/scorecard.py
closed 1 / open 2 / pending 1
Expectancy: -1.0 R   Win rate: 0.0
Dollars: net -30.01 | gross -25.17 | costs 4.84   MFE gap: 4.7239 R
Kill rule: NOT YET — 1/30 closed
```

- 42 focused tests pass (P&L, verification integrity, pending, workflow endpoints);
  65 including the journal-store tests.
- Full backend suite: 936 passed, 6 failed — none in the D-74 paths. Five are
  pre-existing unrelated failures (`test_insider_cluster.py` × 4,
  `test_technical_data_quality.py::test_earnings_filter_missing_file_safe_default`);
  the sixth is the e2e Swagger UI title assertion
  (`e2e/test_tv_screener_e2e.py::TestSwaggerUI::test_swagger_ui_loads`), also
  unrelated (stale title expectation).
- Live DB backup exists before the backfill.

## What the first valid trade shows

CRS: entry 278.24, stop 273.93, T1 397.79 (**11.2R**), MFE **+3.72R**, closed at the
stop **−1.00R**. This is the review-A pattern (MFE ≫ realized R, T1 unreachable) in its
first forward data point. One trade is an anecdote, not a verdict.

## What did not change

Targets, R:R gate, screens, menus, weights, sizing, regime permission, exit rules,
sample clock. The 2026-12-03 calendar review is a progress review; the kill rule still
requires 30+ closed trades. The legacy VISION.md WR > 50% / avg R > 0.5 bar is flagged
as P0-4 and needs user sign-off before editing.

## Next

1. Continue the daily after-close loop. DUK is on its 3rd eligible session
   (2026-10-29): fill or expire.
2. Keep `verify_journal.py` PASS before quoting the scorecard.
3. Do not apply P1/P2 (target hierarchy, choppy menu, permission, sizing) mid-sample.
4. Decide P0-4 (legacy pass bar) before the review.
5. Commit the P0 fixes and docs (changes were uncommitted at session end).

## Files

Code: `pnl.py` (new), `journal_store.py`, `pending.py`, `workflow.py`,
`verification.py`; tests `test_pnl.py` (new), `test_verification_integrity.py` (new),
`test_pending.py`, `test_workflow_endpoints.py`.

Scripts: `verify_journal.py`, `scorecard.py`, `backfill_p0_measurement.py`,
`backup_journal.py` (all new).

Docs: `SCORECARD.md`, `PRE_REGISTRATION.md` (new), `HYPOTHESIS_LOG.md` (new),
`D-74-p0-measurement-integrity.md` (new), `README.md`, `FORWARD_TEST_REVIEW.md`,
`PIPELINE_AUDIT.md`, `docs/index.md`, `docs/DECISIONS/index.md`.
