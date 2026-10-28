# D-74: P0 Measurement Integrity — Canonical Dollar P&L, Plan Provenance, Phantom/P&L Verifier

**Date:** 2026-10-28
**Status:** Accepted — implemented; forward sample continues (measurement only)
**Branch:** `fix/technical-tab-empty`
**HEAD at decision:** `f1797e5` (`fix(workflow): fill after-close signals from next-session bars (D-73)`)
**Related:** D-73 (pending orders / T+1 fills), D-72 (execution v0.1), D-71
(two-month replay), D-68 (SQLite journal), `docs/PAPER_TRADING/SCORECARD.md`,
`docs/PAPER_TRADING/PRE_REGISTRATION.md`, `docs/PAPER_TRADING/PIPELINE_AUDIT.md`,
`docs/backtests/HYPOTHESIS_LOG.md`

## Context

D-73 fixed the execution model and restarted the forward clock at the first actual
fill (2026-10-22, SF @ 65.40). By 2026-10-28 the journal held three valid fills
(SF, IOSP, CRS), one closed trade (CRS, stopped at −1R) and one pending order
(DUK). The docs said the P0 measurement items were done.

They were not. Auditing the live journal against the actual fills exposed three
defects that made the reported numbers wrong even though the trades were real:

### 1. Dollar P&L multiplied R by notional, not risk

The exit sync computed:

```python
risk_amount = account_value * (position_size_pct / 100.0)
pnl_usd = realized_r * risk_amount
```

`position_size_pct` is a **notional** allocation. It is the risk-based size capped
at 25% and halved for CONDITIONAL entries; it is not the dollar risk of the trade.
Multiplying R by it treats the whole position as if it could be lost.

CRS made the error visible:

| Figure | Old value | Correct value |
|---|---:|---:|
| Realized R | −1.00 | −1.00 |
| Shares | 5.84 | 5.84 |
| Entry / exit | 278.24 / 273.93 | 278.24 / 273.93 |
| Dollar risk (`shares × (entry − stop)`) | — | $25.17 |
| Gross P&L | — | −$25.17 |
| Costs (15 bps total) | — | $4.84 |
| Net P&L | **−$1,624.99** | **−$30.01** |

The old number was 54× too large. It was not a display rounding issue; it was the
wrong quantity.

A second, smaller inconsistency: the live path recorded **gross** dollars while
the backtests recorded **net** dollars (10 bps fee + 5 bps slippage per side,
D-71). Comparing them was apples to oranges.

### 2. The gate's R:R and the journal's stored plan did not reconcile

The gate checks `v["risk_reward"]` and stores it as `risk_reward_planned`. The
exit walker uses the stored `target_1` / `target_2`. Those are not guaranteed to
be the same geometry, and the journal never stored the third target the gate may
have used.

The verifier found three gaps in the first three valid rows:

| Symbol | Gate R:R | Stored-plan R:R | Gap |
|---|---:|---:|---:|
| CRS | 4.32 | 11.89 | −7.57 |
| IOSP | 6.15 | 3.99 | +2.16 |
| SF | 6.47 | 4.36 | +2.11 |

IOSP and SF are consistent with a missing `target_3` (the gate saw a further
level). CRS runs the other way: the gate's 4.32 is *lower* than the stored plan's
11.89, so it is not simply a missing third target — the gate used a different or
stale `risk_reward` value. That is the provenance defect in its sharpest form.

This is **review item A** (target hierarchy). It was deliberately not fixed in
D-72 or D-73 because changing which target the gate measures would change which
trades are accepted. D-74 records the gap; it does not reconcile it.

### 3. There was no automated integrity gate

The journal could contain a phantom fill or a wrong dollar figure and the
scorecard would still print a number. D-73 added the fill rules; nothing verified
that the live rows obeyed them after the fact.

## Decision

Make measurement canonical and verifiable, without changing any trading decision:

1. **One P&L definition.** Add `backend/app/domain/workflow/pnl.py`:
   - `gross = (exit − entry) × shares`
   - `costs = (entry + exit) × shares × (10 + 5 bps)`
   - `net = gross − costs`
   - `realized_r` stays a gross price multiple: `(exit − entry) / (entry − stop)`.
2. **One plan-provenance record.** Store `target_3`, `plan_rr` (R:R to the last
   stored target at the zone midpoint) and `target_1_r` on entries and pending
   orders. Keep `risk_reward_planned` as the gate's reported number; do not
   overwrite it. The two can disagree, and the verifier says so.
3. **One integrity gate.** Add `scripts/verify_journal.py`:
   - **FAIL** on any phantom fill (entry not strictly after the signal date).
   - **FAIL** on any closed forward row whose `pnl_usd` ≠ canonical net.
   - **WARN** on any gate-vs-stored-plan R:R gap; warnings do not fail the run.
4. **One scorecard.** Add `scripts/scorecard.py` with the canonical filters and
   definitions; the doc points to the script, not to hand-copied numbers.
5. **Backfill the existing rows, never the decisions.** Compute the missing
   measurement fields from the stored levels; leave entries, exits, stops,
   targets, sizing and `realized_r` untouched. Existing rows cannot recover a
   `target_3` that was never stored; the gap stays visible.
6. **Back up before writing.** `scripts/backup_journal.py` writes a timestamped
   copy under `data/backups/`. The pre-backfill backup is
   `data/backups/paper_trades_20261028T230900Z.db`.

Nothing in this decision changes targets, the R:R gate, screens, sizing, regime
permission or exit rules. The forward sample continues under v0.1.

## Implementation

| Area | Change | Files |
|---|---|---|
| P&L | Canonical `dollar_pnl` + `plan_metrics`; net dollars, gross R | `backend/app/domain/workflow/pnl.py` |
| Schema | `target_3`, `plan_rr`, `target_1_r`, `pnl_gross_usd`, `costs_usd`; idempotent migration; pending orders get `target_3` | `backend/app/domain/workflow/journal_store.py` |
| Entry | `_build_row` stores the third target, plan R:R and T1 R; `risk_reward_planned` remains the gate's value | `backend/app/api/routers/workflow.py` |
| Fill/exit | Pending fills and same-session stops use canonical dollars; fallback derives shares for legacy rows without a `shares` value | `backend/app/domain/workflow/pending.py`, `pending_service.py`, router |
| Integrity | `find_phantom_fills`, `find_pnl_mismatches`, `find_plan_rr_gaps`; `in_forward_sample` filter | `backend/app/domain/workflow/verification.py` |
| Scripts | `verify_journal.py` (PASS/FAIL), `scorecard.py` (one page), `backup_journal.py`, `backfill_p0_measurement.py` | `scripts/` |
| Tests | P&L math, provenance, phantom fill, P&L mismatch, scorecard filter, backfill dry-run | `backend/tests/test_pnl.py`, `test_verification_integrity.py`, existing pending/router tests |

## Backfill result

Applied to 10 journal rows (3 legacy, 4 voided, 3 forward):

- `plan_rr` and `target_1_r` computed for every row from the stored levels.
- Closed forward row CRS: `pnl_gross_usd = −25.17`, `costs_usd = 4.84`,
  `pnl_usd = −30.01` (was −1,624.99).
- `target_3` remains `NULL` for every pre-D-74 row. It cannot be recovered; the
  verifier reports the resulting gap instead of inventing a level.
- No entry, exit, stop, target, share count or `realized_r` was changed.

## Verification

```text
python scripts/verify_journal.py
Journal: C:\_Code\conflu.ai\data\paper_trades.db
Rows: 10 total, 3 forward (1 closed / 2 open), 1 pending, 3 filled

[PASS] Phantom fills: 0
[PASS] Dollar P&L: 0 mismatch(es)
[WARN] Plan R:R gaps: 3
  - CRS: gate 4.32 vs stored plan 11.89 (gap -7.57)
  - IOSP: gate 6.15 vs stored plan 3.99 (gap +2.16)
  - SF: gate 6.47 vs stored plan 4.36 (gap +2.11)

PASS
```

```text
python scripts/scorecard.py
Sample: first fill 2026-10-22 | trigger 30 closed or 2026-12-03
        | closed 1 / open 2 / pending 1
Kill rule: NOT YET — 1/30 closed

Expectancy: -1.0 R   Win rate: 0.0
Profit factor: None   Avg win/loss: None / -1.0 R   Total: -1.0 R
Dollars: net -30.01 | gross -25.17 | costs 4.84   MFE gap: 4.7239 R
```

Tests:

- 42 focused tests pass (P&L, verification integrity, pending fills, workflow
  endpoints); 65 including the journal-store tests.
- Full backend suite: **936 passed, 6 failed** — none in the D-74 paths. Five are
  the pre-existing unrelated failures (`backend/tests/test_insider_cluster.py` × 4,
  `backend/tests/test_technical_data_quality.py::test_earnings_filter_missing_file_safe_default`);
  the sixth is the e2e Swagger UI title assertion
  (`backend/tests/e2e/test_tv_screener_e2e.py::TestSwaggerUI::test_swagger_ui_loads`),
  also unrelated (stale title expectation).

## Consequences

- **The reported dollar P&L is now the account's P&L, not a notional multiple.**
  At the current position sizes the numbers are small (CRS net −$30.01), which is
  correct: the 25% notional cap and CONDITIONAL halving mean a tight-stop trade
  risks well under 1% of the account. The old figure implied a risk the system
  never took.
- **R is unchanged and remains the primary metric.** The fix does not flatter or
  punish the strategy; it only stops the dollar column from lying.
- **The target hierarchy is now visible in the data.** CRS reached +3.72R MFE and
  still lost 1R because T1 was 11.2R away. That is exactly the review-A question,
  now measurable rather than inferred.
- **The provenance gap is logged, not hidden.** Three warnings are part of the
  permanent record until the target hierarchy is redesigned. A future fix will
  start a new sample; it will not retroactively rewrite v0.1.
- **The sample is still tiny.** One closed trade, even with correct arithmetic, is
  not evidence. The kill rule remains at 30 closed trades.

## Not changed

- Targets and the R:R gate (review A).
- Screens, menus, weights and regime permission (review B).
- Sizing formula, 25% notional cap, CONDITIONAL halving (size dial).
- Exit rules (stop → T2 → T1 → time stop; full exit).
- The forward sample clock or its pre-registration.
- `VISION.md`'s legacy "WR > 50% AND avg R > 0.5" bar. It is flagged as P0-4 and
  needs user sign-off before any edit; D-74 does not silently remove it.

## Open items

| Item | Owner | Status |
|---|---|---|
| P0-4: decide whether the legacy WR > 50% / avg R > 0.5 bar survives | User | Open — sign-off required |
| Reconcile gate R:R with the exit target (review A) | Review after trigger | Frozen |
| Backfill `target_3` for pre-D-74 rows | Not possible | Documented gap |
| Per-screen forward table (review C) | Review after trigger | Data now available |
| Add fill-rate/expiry diagnostics to `scorecard.py` | Measurement backlog | Documented in SCORECARD.md, not yet in the script |
| Actual broker fills vs the 10+5 bps model | Later | Fixed model is an assumption, not a measurement |
