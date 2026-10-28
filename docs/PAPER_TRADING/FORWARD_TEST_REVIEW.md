# Forward Test — Review Backlog (after ~30 closed paper trades)

**Created:** 2026-10-19
**Decision:** Option 1 — no rule changes now; run the live paper loop forward and decide
with real evidence (user decision after the 2-month replay, D-71).
**Trigger:** 30 closed forward trades **or** 2026-12-03 (6 weeks from the first actual
fill 2026-10-22), whichever first. The calendar trigger is a progress review; the kill
rule can fire only at 30+ closed.
**Status:** **ACTIVE** (since 2026-10-22). As of 2026-10-28: 1 closed (CRS −1.00R,
MFE +3.72R), 2 open (SF, IOSP), 1 pending (DUK). The 2026-10-19/20 rows remain voided
and the 3 legacy rows remain excluded; the review has **not** fired.

## Execution correction (2026-10-21) — the first four entries were phantom fills

The after-close pipeline booked entries at prices that never traded that session:

| Row | Signal | Booked | Session low | Verdict |
|---|---|---|---|---|
| PM | 2026-10-19 | 185.97 | 199.35 | void |
| AMGN | 2026-10-20 | 406.02 | 425.11 | void |
| CCK | 2026-10-20 | 112.46 | 106.09 | void (after-close look-ahead) |
| MMM | 2026-10-20 | 168.80 | 162.13 | void (after-close look-ahead) |

CCK/MMM did close inside their zones, but the signal existed only after the close, so a
same-day fill is look-ahead either way. The four rows are kept for the audit trail with
`voided=1`; they are not positions, do not consume slots/capital, and never enter the
scorecard.

D-73 replaces same-day booking with pending orders: a signal after close becomes a
pending limit (default) or MOO order, and it can fill only from an actual bar *after* the
signal date. Unfilled orders expire after 3 sessions. A fill bar that trades through the
stop closes the trade at −1R the same day; same-day targets are ignored (conservative
intrabar order). Sizing, targets, R:R gate and screens are unchanged.

**Sample clock:** starts at the first actual fill (T+1 after an after-close signal), not
at run 1. Until then, the scorecard has zero valid trades. Do not backfill missed days.
That condition was met on **2026-10-22** (SF @ 65.40); see the live-state addendum below.

**Pre-correction history (invalidated, kept for audit):** run 1 (2026-10-19) "accepted"
PM (Sector Rotation Holdings, Neutral, CONDITIONAL 12.5%, T1 ≈7.2R, 30-day time stop) and
rejected PG/WMT (conviction) and SG/XERS (no entry geometry). Those four entries never
filled at a tradeable price; the structural questions they raised (Sector Rotation is
unvalidated, T1 ≈7.2R, breakout screens can emit no entry zone) remain valid review
topics — do not change them mid-sample.

**Open book after the correction:** NTNX/WBD/NVDA only (legacy, excluded from stats,
no time stop, still occupying 3 of 8 slots). The four voided rows are not in the book.

**New execution diagnostics to watch (not rule changes):**
- **Fill rate** — filled orders ÷ orders created. A low rate means the desired entry
  zones are too deep for the actual pullbacks.
- **Expiry vs cancel** — expired (never touched) vs cancelled (gapped through the stop
  or opened above the MOO cap). They mean different things about the setup.
- **Same-session stop rate** — fills that stop out on the fill bar. This is the
  conservative intrabar assumption; a high rate is a warning about entry timing.
- **Phantom-fill count must stay zero** — every journal entry's `date_entered` must be
  strictly after its pending order's `signal_date`.

**Audit addendum (2026-10-19):** the read-only pipeline audit
(`docs/PAPER_TRADING/PIPELINE_AUDIT.md`) found that the live path differs from the replay
in ways that affect items A–D: T1 in the current open rows sits ~8–11R away, the gate
measures R/R to the last target while exits pay T1, the live exit loop had no time stop
(`max_hold_days` was never persisted), screen/confluence/sector attribution was not
recorded, and the sector-exposure cap was consequently dead.

**Execution v0.1 applied (2026-10-19):** the user approved measurement + the documented
time stop before starting. Screen/confluence/regime now land on every entry and
rejection, sector is stored and the 30% cap is real, `max_hold_days` is persisted and
executed as calendar days, and the 3 legacy rows are flagged out-of-sample. **Targets and
the R/R gate are unchanged** — item A is still the first review decision.

## Live-state addendum (2026-10-28) — the first valid trade is on the board

The sample is no longer empty. After the D-73 restart:

| Symbol | Signal | Filled | Entry | Stop | State (2026-10-28) |
|---|---|---|---:|---:|---|
| SF | 2026-10-21 | 2026-10-22 | 65.40 | 61.26 | open |
| IOSP | 2026-10-21 | 2026-10-23 | 97.74 | 94.53 | open |
| CRS | 2026-10-24 | 2026-10-26 | 278.24 | 273.93 | **closed 2026-10-27, stop, −1.00R** |
| CVX | 2026-10-24 | — | — | 200.95 | expired unfilled (3 sessions) |
| DUK | 2026-10-26 | — | — | 111.84 | pending; 3rd eligible session 2026-10-29 |

Run ids 3–7 are all `ok`; 40 rejections are logged. The four phantom rows
(PM/AMGN/CCK/MMM) and the three legacy rows (NTNX/WBD/NVDA) remain visible but
excluded.

**P0 measurement correction (D-74, 2026-10-28) — no decision change:** the live
`pnl_usd` was multiplying R by notional instead of dollar risk. CRS reported
−$1,624.99; the correct figures are gross −$25.17, costs $4.84, net −$30.01.
`scripts/verify_journal.py` now enforces phantom fills and dollar P&L (PASS: 0
and 0), and warns on gate-vs-stored-plan R:R gaps (3 warnings). `scripts/scorecard.py`
is the canonical scorecard. Definitions and the pre-registration are in
`SCORECARD.md` / `PRE_REGISTRATION.md`.

**What this means for the review (still no changes):**

- **Item A (exit design):** CRS is the first direct evidence. T1 was **11.2R**
  away; the trade reached **+3.72R MFE**, then stopped for **−1.00R**. That is
  exactly the "MFE ≫ realized R" pattern the review was designed to detect. One
  trade is an anecdote, not a conclusion; do not change targets on it.
- **Items C/D (per-screen, gate):** the data now exists — 5 orders, 3 fills, 40
  rejections, one closed trade. The cells are still too small for a conclusion.
- **The calendar trigger (2026-12-03)** will arrive before 30 closes at the
  current pace. It is a **progress review** (confidence intervals, fill rate,
  whether to continue), not a kill-rule verdict. The kill rule remains 30+
  closed trades.

## Why this file exists

The 2-month replay (371 trades, 114 W / 257 L, −0.203R gross, PF 0.63) flagged two
structural concerns the user raised. We do NOT act on a single 2-month simulation;
these are hypotheses to check against forward (real, gated) data at the review.

## What-if experiments (2026-10-19) — hypothesis sizing (in-sample, NOT evidence)

`run_replay_experiments.py` re-ran the same cached window (500 names, same as-of regime
map) with one hypothesis changed at a time; the baseline reproduced the stored run
exactly. R-multiples are gross; dollar P&L is net of costs.

| Variant | Trades | WR (net) | Exp R (gross) | PF | Net P&L | Choppy exp R |
|---|---|---|---|---|---|---|
| baseline (deployed) | 371 | 30.7% | −0.203 | 0.63 | −$99,788 | −0.322 |
| wide target (4.5 ATR) | 361 | 29.1% | −0.179 | 0.68 | −$88,532 | −0.322 |
| choppy = full ranging menu | 534 | 36.0% | −0.123 | 0.76 | −$100,146 | −0.168 |
| ranging menu + wide target | 528 | 35.2% | −0.089 | 0.83 | −$81,268 | −0.144 |
| choppy = mean-reversion only | 332 | 39.8% | −0.015 | 0.97 | −$26,427 | −0.038 |

What this says (hypotheses, not conclusions):

- **Menu routing alone is not the fix.** The full ranging menu halves per-trade chop
  bleed but takes 67% more choppy trades (405 vs 242); total $ loss is unchanged. The
  single-screen variant (choppy → mean-reversion only) is ≈ flat gross (−0.015R,
  −$26.4k net) but still below the ≈44% net break-even win rate.
- **Screen edges are regime-specific.** statistical-mean-reversion was positive overall
  (+0.162R) because of neutral days, but −0.298R on choppy days. Mean-reversion is the
  only chop screen that is ≈ flat; low-vol-setup is ≈ −0.37R everywhere it traded.
- **Wider targets help where trends exist, not in chop.** Net avg win +1.07R → +1.21R;
  neutral net expectancy −0.057R → +0.031R; choppy unchanged at −0.322R.
- **Sizing only reduces damage.** Halving chop risk: −$99.8k → −$52.9k (baseline) and
  −$26.4k → −$16.2k (best variant); R is unchanged.

Artifacts: `docs/backtests/replay_whatif_20261019_211236.json`,
`docs/backtests/replay_whatif_20261019_214028.json`; runner
`run_replay_experiments.py`.

## A. Exit design caps the winners (reward:risk ceiling)

- Design: ATR stop 2.0 / target 3.0 → best-case win ≈ **+1.5R**. Replay avg win +1.05R,
  avg loss −0.83R; only 67/371 (18%) of trades reached target — most winners exit early
  (15-bar time cap or end-of-window).
- Break-even win rate: **~40% at the design cap** (−1R losses), **44.6% net** with the
  observed avg win/loss and costs. The replay delivered **30.7% net** overall (26.4% in
  choppy). The what-if wide-target variant lowers the requirement (≈41% net) but does
  not change choppy behavior.
- Forward check on the first 30 closed trades: win rate, avg win R, avg loss R, and
  **MFE** (`mfe_r` is already captured by the exit sync):
  - MFE ≫ realized R → exits leave money on the table → consider trailing stop, partial
    scale-out at target, wider target in trend regimes.
  - MFE ≈ realized R → entries are the constraint → raise selectivity instead.
- Wiring gap (verified 2026-10-19, code): the Ticker Analysis layer **builds** a dynamic
  trade-management plan (trail stops, scale in/out, breakeven rules — `trail_type` /
  `trail_activation_r`), but **no execution path consumes it**: the live exit walker
  (`domain/workflow/exits.py`: stop → T1/T2 → time stop, full exit, stop checked first)
  and the backtest engine both exit at static levels set at entry. "Dynamic management"
  is currently advisory output, not behavior — wiring it is a candidate review fix.
- Audit addition (2026-10-19): the live path is worse than the replay here. T1 in the
  current open rows sits **8–11R** away (NTNX +8.2R, WBD +10.9R, NVDA +8.1R), and the
  gate checks R/R to the *last* target. **Time stop: fixed in execution v0.1** —
  `max_hold_days` is now stored and executed as calendar days, so trades can no longer
  sit open forever. **Target hierarchy / R:R metric: unchanged** (item A below); the
  legacy 3 rows do not enter the scorecard. See audit F3/F5.
- First forward data point (2026-10-28): CRS had T1 at **11.2R**, reached **+3.72R
  MFE**, and stopped at **−1.00R**. This is the pattern item A predicts, but n = 1.
  The 3 legacy rows remain excluded; do not add them to this observation.

## B. Regime response gap — "choppy" serves continuation screens; "ranging" is unreachable

Verified in code, 2026-10-19 (`morning_brief._REGIME_LABEL_MAP`,
`regime._composite_to_label`, `regime_selector`):

- The detector can only emit labels mapping to **strong_trend / neutral / choppy /
  high_vol**. The **"ranging" menu (statistical-mean-reversion #1, mean-reversion #2)
  can never be selected automatically** — it is configured but dead except for a
  manual `regime_override`.
- "Cautious" (composite 35–50) → key **choppy** → menu = bull-flag-continuation (85),
  trend-pullback-v2 (80), low-vol-setup (65, defensive). All three are
  continuation/breakout setups — deliberate per the P1.1 comment in `morning_brief.py`
  ("a mid-range composite is NOT a reason to serve only defensive screens").
- Replay result on the 21 choppy sessions: **242 trades (65% of all trades), and every
  screen in the menu lost ≈ −0.35R** (low-vol-setup 97 trades −0.357R; bull-flag 88
  −0.346R; trend-pullback 57 −0.226R).
- What-if (2026-10-19): swapping choppy to the full ranging menu halved the per-trade
  chop bleed (−0.322R → −0.168R gross), but 67% more trades left the total loss
  unchanged (−$100.1k). Choppy → mean-reversion only was ≈ flat (−0.015R gross,
  −$26.4k net) but still below break-even. Menu routing alone does not create a
  positive choppy edge — permission/selectivity (trade less, trade only the screen
  that works) is the missing behavior change.
- The only consistently positive screen, statistical-mean-reversion (+0.162R, PF 1.52,
  WR 44.8%, 67 trades), traded **only via the neutral menu's defensive slot** — i.e.
  the system profited from mean reversion almost by accident, never because the regime
  asked for it.
- Review questions (no changes yet):
  1. Should the choppy menu include mean-reversion primaries (fix the playbook/mood
     mismatch)?
  2. Should "ranging" become reachable from the detector (e.g. composite mid-range +
     low ADX / narrow breadth), or should the choppy menu simply be rebuilt?
  3. Should choppy add a **behavior change** (trade fewer signals, smaller size,
     stronger confirmation) instead of merely swapping a long-only menu?

## C. Per-screen forward confirmation

Replay worst → best (expectancy R / trades):

| Screen | Exp R | Trades |
|---|---|---|
| low-vol-setup | −0.357 | 97 |
| bull-flag-continuation | −0.346 | 88 |
| volume-trend-accumulation | −0.253 | 23 |
| trend-pullback-v2 | −0.226 | 57 |
| 52week-breakout | −0.150 | 24 |
| trend-follower-v2 | +0.021 | 9 |
| statistical-mean-reversion | +0.162 | 67 |
| institutional-trend-follower-mtf | +0.183 | 6 |

Forward: build the same table from real journal trades before re-weighting / retiring
any screen.

**Unblocked 2026-10-19 (execution v0.1):** live entries now store `template` and
`confluence_count` from the brief ticker (and `regime` from the brief); rejections store
`template`/`regime`. The forward table can now be built as soon as closed trades exist.
**First cell (2026-10-28):** Distribution / Risk-Off, n = 1, −1.00R. Descriptive only;
one row cannot rank a screen.

## D. Gate effectiveness

The replay has no gate (it entered every signal). Forward, measure the rejection rate
and whether rejected candidates would actually have won or lost. If the gate adds no
edge, improve it rather than trusting it.

Audit note (2026-10-19): there is no forward data yet — `rejections` and `workflow_runs`
are both empty. **Fixed in execution v0.1:** the sector-exposure step now has real sector
data and can reject; rejections are tagged with `template`/`regime` for per-screen
analysis. **Still open:** the 2.5:1 floor is measured to the last target rather than the
exit target (audit F5, item A), so gate effectiveness must be read alongside the target
hierarchy decision.

**Live state (2026-10-28):** 7 runs, **40 rejections**, 5 orders, 3 fills, 1 closed.
The rejection rate is high (40 rejected vs 3 filled), but there is no counterfactual
P&L for the rejected names yet, so the gate's *selection* value is unmeasured. The
gate's *measurement* value is now recorded; the review can compute it once the sample
is larger.

## Guardrails

- **Execution v0.1 is frozen from the first actual fill (2026-10-22)** (measurement
  fixes + calendar-day time stop only). No changes to screens, weights, targets, R:R
  gate or sizing before the trigger. D-74 is measurement-only (P&L arithmetic, plan
  provenance, verifier) and does not change a decision.
- The 3 legacy rows (NTNX/WBD/NVDA) are flagged `exclude_from_stats=1`; they are visible
  and open but never count toward the 30 closed trades, expectancy or the kill rule.
  The 4 phantom rows (PM/AMGN/CCK/MMM) are `voided=1` and also never count.
- The replay ledger stays simulation-only; the forward journal + VISION.md kill rule
  (expectancy ≤ 0 after 30+ closed trades → stop) remains the decider. The 2026-12-03
  calendar review is a progress review, not a kill-rule verdict.
- Do not backfill missed days. A missed run is an honest gap.
- Run `python scripts/verify_journal.py` before quoting any scorecard number; it must
  print `PASS`.

## Related artifacts

- `docs/PAPER_TRADING/PIPELINE_AUDIT.md` — read-only audit (2026-10-19) of the live
  screener → gate → exit pipeline; root causes and prioritized fixes mapped to the four
  dials (F1–F10).
- `docs/PAPER_TRADING/SCORECARD.md` — canonical forward metrics, definitions and the
  current snapshot.
- `docs/PAPER_TRADING/PRE_REGISTRATION.md` — frozen rules, trigger, kill rule and
  amendment policy for FWD-v0.1.
- `docs/backtests/HYPOTHESIS_LOG.md` — every experiment with its evidence label
  (confirmatory / exploratory / measurement / invalid).
- `docs/DECISIONS/D-74-p0-measurement-integrity.md` — the P0 measurement fix.
- `docs/PAPER_TRADING/V2_RISK_GOVERNOR_BLUEPRINT.md` — four-dials design proposal
  (permission / playbook / size / exits), with success criteria and guardrails.
- `run_replay_experiments.py` — what-if runner (design learning only).
- `docs/backtests/replay_whatif_*.json` — the 2026-10-19 experiment artifacts.
- Session log addendum 2: `docs/SESSIONS/2026-10-19_paper-trade-replay-2mo.md`.
