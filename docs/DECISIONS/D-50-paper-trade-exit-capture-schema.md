# D-50: Paper-Trade Measurement Loop - Exit-Capture Schema + Void the 2026-09 Bypass Cohort

**Status:** Accepted
**Date:** 2026-09-16
**Branch:** `fix/technical-tab-empty`

> **⚠ AMENDED SAME DAY by [D-51](D-51-paper-trade-schema-v2-and-gate-sequencing.md).**
> Two claims below were superseded after this record was written:
>
> 1. **The "(7%)" figure in Context is T1-based and wrong for the blueprint's floor.** The
>    audit computed `rr1 = (target_1 - entry)/(entry - stop)`; the blueprint specifies its
>    2.5 floor **at Target 2**. T2-based, the figure is **11/30 (37%)**. And **neither
>    number is a selectivity measure** — the cohort's targets were engineered to clear
>    R:R >= 2.0, so the distribution measures the repair mechanism, not setup quality. The
>    plan's "~93% rejection" throughput estimate is withdrawn as unknowable pre-fix.
> 2. **"29/31 violate the 5% single-name cap" — there is no enforced cap.** Four
>    conflicting values exist and none of them binds
>    (`TradePlan.max_position_pct = 10.0`, inert; `conviction_caps` up to `0.25`,
>    effective; `paper_trading_validator.py:139 = 0.20`; `professional/models.py:217 =
>    0.05`). The README's "5%" matches none. Sizing (2D) is a build item precisely because
>    the cap this line assumed does not exist.
>
> The **schema in decision 2 is also superseded**: 21 columns -> **29 (21 ENTRY + 8
> EXIT)** per D-51, with `shares` moved to the ENTRY group and
> `entry_low`/`entry_high`/`risk_reward_planned`/`gate_version` added. Everything else in
> this record stands.

> **Numbering note:** `D-49` is reserved for the uncommitted Windows cp1252 +
> `+nan%` fixes already labelled "D-49" in
> `docs/SESSIONS/2026-09-05_paper-trade-high-conviction.md`, which has no
> formal record yet. This record takes the next free slot, D-50.

## Context

We were about to design and build the enforcement spine (a 7-step validation
gate ported to the backend + a review engine) on top of the existing
paper-trade record.

A read-only evidence audit of `docs/paper_trades/` (7 files, 31 rows,
2026-09-03 -> 2026-09-15) found the record **cannot validate anything**:

- **0 exits.** The 12-column schema has no `exit_price`, `status`, `pnl`, or
  `realized_r`. `README.md` Step 4 instructed the operator to record the
  outcome; it was never performed. Win rate, expectancy, profit factor and
  average R are all **not computable**.
- **0 decisions.** All 31 rows are bullish (17 STRONG BUY / 11 ACCUMULATE /
  3 BUY). Nothing was rejected, so no selection signal exists to grade.
- **Geometry fails the system's own gate.** Only **2/30 (7%)** reach the 2.5:1
  R:R floor (median 1.53; worst TARS 0.43, T 0.51, SLDE 0.54). Stops as wide as
  **30.6%** of entry.
- **No sizing rule.** **29/31** rows violate the 5% single-name cap. Conviction 3
  produced 7 distinct sizes. The best R:R in the book (BULL 3.99) received the
  *smallest* allocation (3.3%).
- **Concentration.** 81% of rows in two sectors, with pyramiding into unchanged
  stops (MU 944.36 -> 971.31 -> 971.60 against a static 883.17 stop).
- **Contradictions shipped.** 11 rows carry overbought RSI (up to 78.9) and a
  buy call in the same string; 10 rows flag *"yfinance D/E appears incorrect"*;
  VZ merger arb (capped +0.26%) shipped as STRONG BUY with no stop.

Root cause: all 31 rows were written by `backend/scripts/paper_trade_from_brief.py`,
which appends **every** candidate above a conviction floor directly to CSV -
bypassing the gate, the conviction-based sizing, and any notion of a decision.
The frontend workflow was never involved. The record is a *candidate dump*, not
a set of trades.

Separately, the operating manual had drifted from the code and the blueprint:

- `docs/PAPER_TRADING/README.md:41` said *"At least 1.5-2x the stop distance"*
  versus **2.5:1** in `frontend/src/workflow/gate.ts` (`RISK_REWARD_PASS`) and
  `ELITE_SWING_TRADING_BLUEPRINT.md`.
- An uncommitted working-tree edit replaced the checklist line
  *"Pick 1-2 that match your conviction"* with *"Look at the candidates, drop the
  ones you don't want"* - deleting the selection step while adding a script
  section that writes everything.

Full evidence: `docs/SESSIONS/2026-09-16_paper-trade-evidence-audit.md`.

## Decision

**1. Measure before enforce.** The gate is designed from the audit's findings,
not from the blueprint's wishlist. Closing the measurement loop comes first.

**2. Approve the exit-capture schema (additive, 21 columns total).**
The existing 12 entry columns are unchanged; 9 outcome columns are appended:

| Column | Purpose |
|---|---|
| `date_closed` | when the position ended |
| `exit_price` | realized exit |
| `exit_reason` | `stop` / `target_1` / `target_2` / `trail` / `time_stop` / `thesis_break` / `manual` |
| `shares` | actual size taken (replaces `position_size_pct` guesswork) |
| `realized_r` | `(exit_price - entry_price) / (entry_price - stop_loss)`, signed |
| `pnl_usd` | optional - account curve |
| `mfe_r` | optional - best unrealized R (did we exit too early?) |
| `mae_r` | optional - worst unrealized R (was the stop too wide?) |
| `plan_adherence` | `followed` / `partial` / `broke` - **process** metric, not success metric |

**3. Add a rejection log.** `docs/paper_trades/REJECTIONS.csv` records every
candidate the gate rejected and which step killed it. Without it, "0 rejections
in 31 rows" can never become a measurable number, and the gate's true rejection
rate is unknowable.

**4. Void the 2026-09 bypass-path cohort.** All 7 files (31 rows) moved to
`docs/paper_trades/archive/2026-09-bypass-path-voided/`, retained byte-for-byte
with an explanatory README. They are explicitly **excluded** from any win-rate,
expectancy or adherence calculation. The measurement loop restarts at the first
run written against the new schema.

**5. Fix the documentation drift.** `README.md` R:R threshold corrected to
2.5:1; the selection step restored in the checklist; Step 4 rewritten as a
mandatory exit-capture step; Step 5 given the real north-star metrics
(expectancy, profit factor) plus a kill criterion and a minimum-sample rule; a
KNOWN GAP warning added that the script currently bypasses the gate; the file
layout corrected.

**6. North-star metric is expectancy, not adherence.** `plan_adherence` is
retained as a process metric. A perfectly adhered-to bad plan still loses.

**7. Availability premise: 1-2 touchpoints per day.** The blueprint's 4-stage
clock (6:00 / 9:30 / 12:00 / 4:15) does not fit a working professional. The
flow is designed around a pre-market decision (bracket orders placed, executing
unattended) plus an after-close journal. This collapses the planned 4-stage
"Daily Mission".

## Consequences

**Benefits**
- The loop is now closable: `realized_r` makes expectancy computable.
- The gate gets designed against measured failures rather than assumptions.
- The gate's rejection rate becomes observable via `REJECTIONS.csv` - the
  metric that tells us whether selection exists at all.
- Docs, code and blueprint agree on the 2.5:1 floor.

**Costs / risks**
- **No usable historical sample.** Voiding the cohort means starting from zero
  closed trades. Expectancy cannot be reported until enough exits accumulate
  (~30+ per pattern before any pattern-level claim).
- The exit-capture columns are populated **by hand** until tooling exists. If
  Step 4 is skipped again, the loop silently reopens. This is the single
  biggest ongoing risk.
- The gate is still **not enforced** in
  `backend/scripts/paper_trade_from_brief.py`. Until it is, Step 2 remains a
  manual discipline step and the script will keep emitting unvalidated
  candidate dumps. Documented as a KNOWN GAP.
- Portfolio Fit (gate step 6) remains unenforceable - no position state exists
  anywhere. Position tracking is now understood to be a **prerequisite** for
  that step, reversing the earlier deferral to Phase 2.

## Files

- `docs/paper_trades/TEMPLATE.csv` - rewritten to the 21-column schema
- `docs/paper_trades/REJECTIONS.csv` - new rejection-log template
- `docs/paper_trades/archive/2026-09-bypass-path-voided/` - 7 CSVs + README
- `docs/PAPER_TRADING/README.md` - 7 drift corrections
- `docs/SESSIONS/2026-09-16_paper-trade-evidence-audit.md` - the audit
- `INDEX.md`, `docs/index.md`, `docs/DECISIONS/index.md` - refreshed

No application source code was modified.
