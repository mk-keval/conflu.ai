# Pre-Registration — Forward Sample v0.1

**Experiment ID:** `FWD-v0.1`
**Status:** Active — frozen; no decision-changing edits until the trigger
**Registered:** 2026-10-28 (documenting rules already in force; see provenance)
**First actual fill:** 2026-10-22 — SF @ 65.40
**Journal of record:** `data/paper_trades.db`
**Scorecard:** [SCORECARD.md](SCORECARD.md)
**Review agenda:** [FORWARD_TEST_REVIEW.md](FORWARD_TEST_REVIEW.md)

---

## Why this file exists

The forward sample is the only evidence that can kill or confirm the deployed
system. A sample judged after the fact invites goalpost movement: a new metric
when the old one looks bad, a new exclusion when a trade embarrasses the thesis,
a "just one more month" when the kill rule fires.

This file fixes the rules **before** the sample can produce a verdict. It was
written on 2026-10-28, after the first fill and one closed trade, because the
earlier decisions (D-72, D-73) existed only across several documents. The rules
themselves predate the first fill; this is a consolidation, not a new design.
That timing is disclosed rather than hidden — the hypotheses, metrics, trigger
and kill rule are all traceable to documents dated before 2026-10-22.

---

## Experiment card

| Field | Value |
|---|---|
| Question | Does the deployed screen → gate → pending-order → exit pipeline produce positive expectancy in R on real, tradeable forward fills? |
| System | Live Morning Brief path: regime screens → per-ticker analysis → 7-step gate → sizing → pending orders → exit sync |
| Universe | Whatever the deployed screens return each day, after the conviction floor and gate. Not a fixed symbol list. |
| Instrument | US equities, long bias (the current system is long-only in practice) |
| Sample unit | One **closed forward trade** (a real fill with a `date_closed`) |
| Observation window | First actual fill 2026-10-22 → 30 closed trades or 2026-12-03, whichever first |
| Primary endpoint | Expectancy in R over closed forward trades |
| Decision rule | Kill if expectancy ≤ 0 at n ≥ 30; otherwise continue/review |
| Data source | `data/paper_trades.db` only; replay/backtest tables are excluded |
| Analysis script | `python scripts/scorecard.py` |
| Integrity gate | `python scripts/verify_journal.py` must PASS before scoring |

---

## Frozen design (no changes mid-sample)

These are the rules the sample is measuring. Changing any of them changes the
experiment and requires a new sample ID (see Amendment policy).

| Area | Frozen rule |
|---|---|
| Screens / menus | `config/regime_screens.yaml` as deployed; no weight or menu changes |
| Regime permission | None — the current system has no permission gate; do not add one mid-sample |
| Conviction floor | `min_conviction = 5` on the brief ticker |
| Gate | 7-step gate, unchanged; 2.5:1 PASS / 2.0:1 CONDITIONAL with r1 ≥ 1.0 |
| Sizing | 1% risk formula, 25% notional hard cap, 0.5% floor; CONDITIONAL × 0.5 |
| Portfolio caps | 8 open positions; 30% sector exposure (by planned size); duplicate-symbol block |
| Targets | Structural targets as produced by the analysis; no cap, no nearest-resistance rule |
| R:R measurement | The gate's reported `risk_reward` (to the last target), recorded as `risk_reward_planned`; **not** reconciled to the exit target |
| Time stop | `max_hold_days` from the plan (20/30/60 calendar days), executed as the first session on/after the cutoff |
| Entry model | After-close signal → pending limit at `entry_low`; MOO optional; 3-session expiry |
| Fill timing | Only bars strictly after `signal_date`; no same-day fills (D-73) |
| Same-session exits | Fill-bar stop closes at −1R; fill-bar targets are ignored (conservative) |
| Exit model | Stop first (gap-aware), then T2, then T1, then time stop; full exit, no scale-out, no trail |
| Costs | 10 bps fee + 5 bps slippage per side in dollars; R remains gross |

**Deliberately not fixed:** the number of candidates per day, the number of fills,
and the mix of screens. Those are outputs of the frozen pipeline, not inputs to
be tuned.

---

## Endpoints and metrics

### Primary

**Expectancy in R** = `mean(realized_r)` over closed forward trades, where
`realized_r = (exit − entry) / (entry − stop)` and is gross of costs.

### Secondary (reported, not decisive)

- Win rate (`realized_r > 0` ÷ closed).
- Profit factor (`sum(wins) / abs(sum(losses))`).
- Average win R and average loss R.
- Net dollar P&L after costs; gross dollars; total costs.
- MFE gap (`mean(mfe_r − realized_r)`) — the review-A signal.
- Per-template and per-regime expectancy, **descriptive only below 30 closed
  trades per cell**.
- Execution diagnostics: fill rate, expiry vs cancel, same-session stop rate.

### Legacy pass bar (flagged, not applied)

`VISION.md` carries a second bar: hit rate > 50% AND average R > 0.5 after ≥ 20
closed trades. It predates the expectancy-first framing and conflicts with a
system whose losses are −1R and whose targets are far away. It is flagged for
user sign-off (P0-4, D-74). Until that sign-off is recorded, this pre-registration
uses the **kill rule** as the only decisive threshold and reports the legacy bar
as context. This is a disclosed open item, not a silent change.

---

## Trigger and decision rules

### Review trigger

**30 closed forward trades OR 2026-12-03 (6 weeks from the first actual fill),
whichever comes first.**

The two triggers do different jobs:

- **30 closed trades** is the statistical trigger. The kill rule can fire only
  here.
- **2026-12-03** is a calendar review. It fires even if the sample is small. At
  the current pace it will arrive with far fewer than 30 closes.

### At the 2026-12-03 review

1. Run the integrity gate and the scorecard.
2. Report n, expectancy, win rate, PF, MFE gap, dollar P&L, fill rate and
   rejection count.
3. Report confidence intervals. With n < 30 the interval will be wide; say so.
4. Decide only: **continue the frozen sample**, **extend the calendar review**,
   or **stop for a documented operational reason**. Do **not** kill the system on
   expectancy at n < 30 — that is not the pre-registered rule.
5. Any design change proposed at this review is P1/P2 and starts a **new**
   sample; it does not retroactively judge v0.1.

### At 30 closed trades

- If expectancy ≤ 0: **kill or change**. A written reason is required to extend.
- If expectancy > 0: the system survives the kill rule; the review agenda
  (items A–D) still decides whether the edge is real, fragile or execution luck.
- Report the same metrics as above, plus per-template/regime cells with n ≥ 30.

### What never counts

- Voided rows (PM/AMGN/CCK/MMM) — phantom fills, retained for audit only.
- Legacy rows (NTNX/WBD/NVDA) — `exclude_from_stats = 1`.
- Replay / backtest / what-if rows — separate tables, simulation only.
- Open positions and pending orders — not closed evidence.
- Hypothetical exits that "would have" happened — no counterfactual scoring in
  the primary endpoint.

---

## Data integrity gates

Before any scorecard is quoted:

```bash
python scripts/verify_journal.py
```

Hard failures (exit code 1):

- **Phantom fill** — a filled order whose journal entry is not strictly after
  the signal date.
- **Dollar P&L mismatch** — stored `pnl_usd` ≠ `shares × (exit − entry) − costs`.

Warnings (do not fail, must be reported):

- **Plan R:R gap** — the gate's `risk_reward_planned` differs from the R:R
  recomputed from stored targets. This is the known D-74 provenance gap. It is
  logged, not "fixed" mid-sample.

A backup of the live DB must exist before any write that changes journal rows.
`python scripts/backup_journal.py` writes a timestamped copy under
`data/backups/`.

---

## Exclusions and honest gaps

- A missed daily run is an **honest gap**. Do not backfill entries, invent
  prices, or reconstruct a signal that did not exist after the close.
- A signal that never fills is a **valid observation**, not a missing trade. It
  enters the fill-rate diagnostic, not the expectancy.
- A row with irrecoverable provenance (e.g. no `target_3`, no stored shares) stays
  in the journal with the gap visible. It is not silently repaired into a
  cleaner-looking sample.
- The four phantom rows and the three legacy rows remain visible in the Journal
  UI and CSV export. Hiding them would make the audit trail dishonest.

---

## Amendment policy

| Change type | Allowed mid-sample? | Procedure |
|---|---|---|
| Measurement fix that cannot change which trades are taken or how they exit | Yes | ADR + verifier/test; log it here; re-run the scorecard |
| Bug fix that changes fills, exits, sizing or selection | **No** | Stop, void the affected cohort, start `FWD-v0.2` with a new first fill |
| New screen, weight, target rule, permission gate or size rule | **No** | Same as above |
| Kill-rule, trigger or metric definition change | **No** | New pre-registration; the old sample is judged on the old rules |
| Documentation clarification with no behavioral effect | Yes | Record in the change log |

The test is behavioral: **would the change alter a historical decision or exit?**
If yes, it is a new experiment. "It would have been more accurate" is not an
exemption.

---

## Deviations and amendments log

| Date | Item | Type | Decision | Effect on sample |
|---|---|---|---|---|
| 2026-10-21 | Pending orders / T+1 fills (D-73) | Execution correction **before** the sample clock restarted | Voided PM/AMGN/CCK/MMM; clock restarts at first actual fill | None on v0.1; the phantom rows never count |
| 2026-10-28 | Canonical dollar P&L, plan provenance, phantom/P&L verifier (D-74) | Measurement only | Added columns, backfill, scripts; no decision change | Corrected `pnl_usd`; R unchanged; sample continues |
| 2026-10-28 | This pre-registration | Documentation | Consolidates D-72/D-73 rules; flags P0-4 | None |

No rule change has been applied after the first actual fill (2026-10-22).

---

## Open items that could change the *review*, not the sample

| Item | Where | Status |
|---|---|---|
| Legacy WR > 50% / avg R > 0.5 bar | `VISION.md` | Awaiting user sign-off (P0-4) |
| Target hierarchy: T1 vs gate R:R (review A) | `PIPELINE_AUDIT.md` F5 | Frozen; first review decision |
| Choppy menu / `ranging` unreachable (review B) | `PIPELINE_AUDIT.md` F6 | Frozen |
| Permission, cross-screen rank, daily cap (review B) | `PIPELINE_AUDIT.md` F7 | Frozen |
| Sector-rotation 4th screen (review C/D) | `PIPELINE_AUDIT.md` F8 | Frozen |
| Regime hysteresis, portfolio heat (P2) | `PIPELINE_AUDIT.md` F9/F10 | Frozen |
| Gate R:R ≠ stored plan R:R (D-74 warning) | `SCORECARD.md` | Logged; fixing it would change decisions |

---

## Template for the next experiment

Copy this block into a new file (`PRE_REGISTRATION-v0.2.md`) when a
decision-changing amendment is approved.

```markdown
# Pre-Registration — <experiment name>

**Experiment ID:** FWD-v0.2
**Registered:** YYYY-MM-DD
**First actual fill:** YYYY-MM-DD (or "not yet")
**Supersedes:** FWD-v0.1 (reason)

## Question
<one sentence; the decision this experiment informs>

## Change from the previous experiment
<exactly one design change; everything else frozen>

## Frozen rules
<table or bullets, including screens, gate, sizing, targets, exits, costs>

## Endpoints
Primary: <metric and definition>
Secondary: <list>

## Trigger
<sample size and/or date>

## Decision rule
<kill / pass / continue, with thresholds>

## Exclusions
<voided, legacy, replay, open rows, honest gaps>

## Integrity gate
<command and hard-fail conditions>

## Deviations log
| Date | Item | Type | Effect |
```

---

## Change log

| Date | Change |
|---|---|
| 2026-10-28 | Created; consolidates D-72/D-73 and records the current sample rules |
