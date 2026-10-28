# Forward Scorecard — v0.1

**Status:** Live sample, 1 closed trade — **not evidence yet**
**Snapshot:** 2026-10-28 (after run id 7)
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

## Current snapshot (2026-10-28)

| Item | Value |
|---|---|
| First actual fill | **2026-10-22** — SF @ 65.40 |
| Closed forward trades | **1** |
| Open forward trades | 2 (SF, IOSP) |
| Pending orders | 1 (DUK limit 122.57, signal 2026-10-26) |
| Expectancy | **−1.00 R** |
| Win rate | 0.0% (0 / 1) |
| Profit factor | n/a (no winners yet) |
| Average win / loss | n/a / −1.00 R |
| Total R | −1.00 R |
| Net dollars (after costs) | **−$30.01** |
| Gross dollars | −$25.17 |
| Costs (10 bps fee + 5 bps slippage/side) | $4.84 |
| MFE gap | **+4.72 R** |
| Kill rule | **NOT YET** — 1 / 30 closed |
| Time review trigger | 2026-12-03 |

### Closed trade ledger

| Symbol | Entered | Entry | Stop | Closed | Exit | R | MFE | MAE | Gross | Costs | Net |
|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| CRS | 2026-10-26 | 278.24 | 273.93 | 2026-10-27 | 273.93 (stop) | −1.00 | +3.72 | −1.11 | −$25.17 | $4.84 | −$30.01 |

### Per template / regime (descriptive only, n = 1)

| Template | Regime | n | Expectancy | Win rate | PF |
|---|---|---:|---:|---:|---:|
| Distribution | Risk-Off | 1 | −1.000 R | 0.0% | n/a |

Do not read a pattern from a single row. The table is printed because the plumbing
works, not because it says anything about the screen.

---

## What the first closed trade says

CRS is a clean illustration of review item A, not a verdict on the system:

- The plan's first target was **11.2R** away (T1 397.79, entry 278.24, stop
  273.93). The gate recorded 4.32; the stored plan recomputes to 11.89. Those
  numbers never reconciled (see D-74 and the verifier warnings).
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
| `pnl_gross_usd` | `(exit_price − entry_price) × shares` |
| `costs_usd` | `(entry_price + exit_price) × shares × 15 bps` (10 bps fee + 5 bps slippage per side) |
| `pnl_usd` | `pnl_gross_usd − costs_usd` — **net of costs** |
| Expectancy | `mean(realized_r)` over closed forward trades |
| Win rate | closed trades with `realized_r > 0` ÷ closed forward trades |
| Profit factor | `sum(winning R) / abs(sum(losing R))` |
| MFE gap | `mean(mfe_r − realized_r)` — positive means profit was left on the table |

R stays gross to match the backtest convention (D-71). Dollars are net because
that is what an account experiences. The two must not be mixed: a positive
expectancy in R with negative net dollars is possible when costs dominate small
wins.

---

## Sample filter (exactly these rows count)

A row counts only when **all** of the following are true:

1. `voided = 0` — the four phantom fills (PM/AMGN/CCK/MMM) never count.
2. `exclude_from_stats = 0` — the three pre-instrumentation rows
   (NTNX/WBD/NVDA) never count.
3. `date_closed` is set and `realized_r` is numeric — open rows are not evidence.

Pending orders are not trades. They reserve a slot and capital, but they enter the
scorecard only after a real fill creates a journal row.

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
`VISION.md`. In short:

- **Review trigger:** 30 closed forward trades **or** 2026-12-03 (6 weeks from the
  first actual fill), whichever comes first.
- **Kill rule:** expectancy ≤ 0 after **30+ closed trades** → change the system or
  stop. "Give it more time" requires a written reason.
- **Legacy pass bar:** VISION.md also carries "hit rate > 50% AND average R > 0.5
  after ≥ 20 closed trades." That bar predates the current expectancy-first
  framing and is flagged for user sign-off (P0-4, D-74). It is **not** applied in
  this scorecard until that decision is recorded. The kill rule is the binding
  decider.

At the current pace the time trigger will fire long before 30 closed trades. That
review is a **progress review** — confidence intervals, execution diagnostics and
a decision on whether the sample is worth continuing — not a kill-rule verdict.

---

## Execution diagnostics (from `pending_orders`, not in the one-page script)

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

---

## What this scorecard does not answer

- Whether the screens have an edge (n = 1).
- Whether the gate rejects winners (rejections are logged, but no counterfactual
  exits are computed).
- Whether targets are reachable (the sample has one closed trade at 11.2R T1).
- Whether the replay's −0.203R carries into forward data (different execution,
  different universe, different gate).
- Whether the system should be changed. That decision waits for the trigger and
  the review file.

---

## Change log

| Date | Change | Decision |
|---|---|---|
| 2026-10-28 | Created; canonical definitions and first live snapshot | D-74 |
