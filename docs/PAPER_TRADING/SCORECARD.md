# Forward Scorecard — FWD-v0.2 (scored)

**Status:** Scored sample not started — **0 closed**. FWD-v0.1 is closed for
verdicts (1 closed, −1.00R) and is shown as **reference only** (D-76).
**Snapshot:** 2026-10-28 (after run id 7; sample-version migration)
**Source of truth:** `python scripts/scorecard.py` → reads `data/paper_trades.db`
**Pre-registration:** [PRE_REGISTRATION.md](PRE_REGISTRATION.md)
**Integrity gate:** `python scripts/verify_journal.py` must print `PASS` before this
scorecard is quoted.

This is the only forward scorecard. The 2-month replay (`replay_runs` /
`replay_trades`), template validation and what-if experiments are design evidence;
they never enter these numbers. Replay rows are stored in separate tables and are
not read by `scripts/scorecard.py`.

The snapshot below is a dated record, not a live number. Re-run the script before
using any figure in a decision; if the doc and the script disagree, the script wins.

---

## Sample versions (D-76)

| Version | Rows | Scored? |
|---|---|---|
| `v0.1` | Everything before 2026-10-28 (1 closed CRS, 2 open SF/IOSP, 1 pending DUK) | **No** — closed for verdicts; reference only |
| `interim` | Daily-loop rows from 2026-10-29 until the v0.2 freeze | **No** — execution diagnostics only |
| `v0.2` | First fill after the Bundle A spec freeze | **Yes** — the canonical scorecard |

The version is set once on insert and never moved by a re-run. A filled pending
order inherits its order's version. Rows from other versions appear in the
scorecard only under "other samples (reference)".

---

## Current snapshot (2026-10-28)

### Scored sample — FWD-v0.2

| Item | Value |
|---|---|
| First actual fill | none yet |
| Closed scored trades | **0** |
| Open scored trades | 0 |
| Pending scored orders | 0 |
| Expectancy | n/a |
| Win rate / profit factor | n/a |
| Net dollars (after costs) | n/a |
| Drawdown (peak-to-trough R) | 0.00 R — **CLEAR** |
| Kill rule | **NOT YET** — 0 / 30 closed |
| Pass bar (D-75) | **not evaluable** — 0 / 30 closed |
| Time review trigger | 42 days after the first scored fill |

### Reference — FWD-v0.1 (closed for verdicts, never scored)

| Item | Value |
|---|---|
| First actual fill | **2026-10-22** — SF @ 65.40 |
| Closed forward trades | **1** |
| Open forward trades | 2 (SF, IOSP) |
| Pending orders | 1 (DUK limit 122.57, signal 2026-10-26) |
| Expectancy | −1.00 R |
| Win rate | 0.0% (0 / 1) |
| Profit factor | n/a (no winners) |
| Average win / loss | n/a / −1.00 R |
| Total R | −1.00 R |
| Net dollars (after costs) | **−$30.01** |
| Gross dollars | −$25.17 |
| Costs (10 bps fee + 5 bps slippage/side) | $4.84 |
| MFE gap | **+4.72 R** |
| Verdict | **None** — closed for verdicts 2026-10-28 (Q2/D-76) |

### Closed trade ledger — v0.1 reference

| Symbol | Entered | Entry | Stop | Closed | Exit | R | MFE | MAE | Gross | Costs | Net |
|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| CRS | 2026-10-26 | 278.24 | 273.93 | 2026-10-27 | 273.93 (stop) | −1.00 | +3.72 | −1.11 | −$25.17 | $4.84 | −$30.01 |

### Per template / regime — v0.1 reference (descriptive only, n = 1)

| Template | Regime | n | Expectancy | Win rate | PF |
|---|---|---:|---:|---:|---:|
| Distribution | Risk-Off | 1 | −1.000 R | 0.0% | n/a |

Do not read a pattern from a single row. The table is printed because the plumbing
works, not because it says anything about the screen.

---

## What the v0.1 reference trade says

CRS is a clean illustration of review item A, not a verdict on the system (and
not scored — v0.1 is closed for verdicts):

- The plan's first target was **11.2R** from the entry-zone midpoint (284.08) —
  **27.7R** from the actual fill (278.24); T1 397.79, stop 273.93. The gate
  recorded 4.32; the stored plan recomputes to 11.89 from the same midpoint.
  Those numbers never reconciled (see D-74 and the verifier warnings).
- The trade reached **+3.72R MFE** and then closed at the stop for −1.00R. A
  trailing stop or a nearer first target could have changed the outcome; the
  frozen design has neither.
- One trade cannot distinguish "bad luck" from "targets are unreachable." The
  review trigger exists to answer that with a sample, not with this row.

---

## Definitions (do not fork these)

| Metric | Definition |
|---|---|
| `realized_r` | `(exit_price − entry_price) / (entry_price − stop_loss)` — **gross of costs** |
| `target_1_r`, `plan_rr` | R distance to T1 / R:R to the last target, measured from the **entry-zone midpoint** (the gate's basis), not the fill. Do not compare directly to `realized_r`. |
| `pnl_gross_usd` | `(exit_price − entry_price) × shares` |
| `costs_usd` | `(entry_price + exit_price) × shares × 15 bps` (10 bps fee + 5 bps slippage per side) |
| `pnl_usd` | `pnl_gross_usd − costs_usd` — **net of costs** |
| Expectancy | `mean(realized_r)` over closed forward trades |
| Win rate | closed trades with `realized_r > 0` ÷ closed forward trades |
| Profit factor | `sum(winning R) / abs(sum(losing R))` |
| MFE gap | `mean(mfe_r − realized_r)` — positive means profit was left on the table |
| Drawdown | peak-to-trough cumulative `realized_r`, chronological by close date |
| Pass bar (D-75) | at 30+ closed: expectancy > 0 **and** PF ≥ 1.3 **and** avg loss ≤ 1.0R. Win rate is reported, not gated |
| Risk circuit breaker | 8R peak-to-trough drawdown → stop and review; 12R → kill |

R stays gross to match the backtest convention (D-71). Dollars are net because
that is what an account experiences. The two must not be mixed: a positive
expectancy in R with negative net dollars is possible when costs dominate small
wins.

---

## Sample filter (exactly these rows count)

A row counts only when **all** of the following are true:

1. `sample_version` equals the scored version (`v0.2`) — v0.1 and interim rows
   are reference only (D-76).
2. `voided = 0` — the four phantom fills (PM/AMGN/CCK/MMM) never count.
3. `exclude_from_stats = 0` — the three pre-instrumentation rows
   (NTNX/WBD/NVDA) never count.
4. `date_closed` is set and `realized_r` is numeric — open rows are not evidence.

Pending orders are not trades. They reserve a slot and capital, but they enter the
scorecard only after a fill creates a journal row **and** the row carries the
scored version (a filled order inherits its order's version).

---

## Reproduce

```bash
python scripts/verify_journal.py    # PASS/FAIL measurement gate
python scripts/scorecard.py         # human-readable scorecard
python scripts/scorecard.py --json  # same numbers, machine-readable
```

The scripts read the journal configured by `journal_store` (default
`data/paper_trades.db`). A backup should exist before any write; see
`python scripts/backup_journal.py`.

---

## Trigger, pass bar and kill rule

The pre-registered rules are in [PRE_REGISTRATION.md](PRE_REGISTRATION.md) and
`VISION.md`. In short, for the **scored** sample (v0.2):

- **Review trigger:** 30 closed scored trades **or** 42 days (6 weeks) after the
  first scored fill, whichever comes first. The old 2026-12-03 date belonged to
  v0.1 and no longer applies.
- **Pass bar (D-75):** at **30+ closed trades**, expectancy > 0 after costs,
  profit factor ≥ 1.3, and average loss ≤ 1.0R. Win rate, average win, payoff
  ratio and MFE capture are reported, not gated. A win rate below 50% is
  acceptable when the winners are large enough.
- **Risk circuit breaker:** 8R peak-to-trough drawdown → stop new entries and
  review; 12R → kill.
- **Kill rule:** expectancy ≤ 0 after **30+ closed trades**, or the 12R breaker
  → change the system or stop. "Give it more time" requires a written reason.

No verdict is issued from v0.1 or from `interim` rows. At the current pace the
time trigger will fire long before 30 closed trades. That review is a **progress
review** — confidence intervals, execution diagnostics and a decision on whether
the sample is worth continuing — not a kill-rule verdict.

---

## Execution diagnostics — v0.1 reference (from `pending_orders`, not in the one-page script)

| Diagnostic | Value |
|---|---|
| Orders created | 5 |
| Filled | 3 (SF, IOSP, CRS) |
| Expired unfilled | 1 (CVX) |
| Cancelled | 0 |
| Still pending | 1 (DUK) |
| Fill rate, all created | 60% (3 / 5) |
| Fill rate, resolved orders | 75% (3 / 4) |
| Same-session stops | 0 / 3 |

A low fill rate means the desired entry zones are deeper than actual pullbacks.
Expiry (never touched) and cancellation (gapped through the stop or above the MOO
cap) mean different things about the setup and must stay separate. These
diagnostics belong in the review, not in the expectancy number.

These counts are the v0.1 reference set. Orders created from 2026-10-29 are
tagged `interim` and stay out of the scored sample; their diagnostics will reset
when FWD-v0.2 starts at its first scored fill.

---

## What this scorecard does not answer

- Whether the screens have an edge (n = 1).
- Whether the gate rejects winners (rejections are logged, but no counterfactual
  exits are computed).
- Whether targets are reachable (the sample has one closed trade whose T1 sat
  27.7R above the fill, or 11.2R from the entry-zone midpoint).
- Whether the replay's −0.203R carries into forward data (different execution,
  different universe, different gate).
- Whether the system should be changed. That decision waits for the trigger and
  the review file.

---

## Change log

| Date | Change | Decision |
|---|---|---|
| 2026-10-28 | Created; canonical definitions and first live snapshot | D-74 |
