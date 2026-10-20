# Forward Test — Review Backlog (after ~30 closed paper trades)

**Created:** 2026-10-19
**Decision:** Option 1 — no rule changes now; run the live paper loop forward and decide
with real evidence (user decision after the 2-month replay, D-71).
**Trigger:** 30 closed forward trades **or** 6 weeks from the first `run_close`
(≈ 2026-11-30 if the sample starts 2026-10-19), whichever first.
**Status:** LIVE — sample started 2026-10-19 (run id 1; PM accepted, 4 rejected,
0 closed scored trades). The clock runs to 30 closed scored trades or ≈2026-11-30.

**First run (2026-10-19, run id 1):** 1 accepted — **PM** (Sector Rotation
Holdings, Neutral, CONDITIONAL 12.5%, T1 ≈7.2R, 30-day time stop); 4 rejected —
PG/WMT on conviction, SG/XERS with no entry geometry; 0 exits (the 3 legacy rows +
today's PM are correctly skipped). This is the first forward evidence, not a verdict.

**What to watch from run 1:** PM is from the unvalidated *Sector Rotation Holdings*
screen (F8) and its T1 is ≈7.2R (F5). SG/XERS reached sizing with no entry
geometry (entry 0) and were honestly rejected; check whether the 52-Week Breakout
screen should emit an entry zone. Do not change either mid-sample.

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

## Guardrails

- **Execution v0.1 is frozen from the first run** (measurement fixes + calendar-day time
  stop only). No changes to screens, weights, targets, R:R gate or sizing before the
  trigger.
- The 3 legacy rows (NTNX/WBD/NVDA) are flagged `exclude_from_stats=1`; they are visible
  and open but never count toward the 30 closed trades, expectancy or the kill rule.
- The replay ledger stays simulation-only; the forward journal + VISION.md kill rule
  (expectancy ≤ 0 after 30+ closed trades → stop) remains the decider.
- Do not backfill missed days. A missed run is an honest gap.

## Related artifacts

- `docs/PAPER_TRADING/PIPELINE_AUDIT.md` — read-only audit (2026-10-19) of the live
  screener → gate → exit pipeline; root causes and prioritized fixes mapped to the four
  dials (F1–F10).
- `docs/PAPER_TRADING/V2_RISK_GOVERNOR_BLUEPRINT.md` — four-dials design proposal
  (permission / playbook / size / exits), with success criteria and guardrails.
- `run_replay_experiments.py` — what-if runner (design learning only).
- `docs/backtests/replay_whatif_*.json` — the 2026-10-19 experiment artifacts.
- Session log addendum 2: `docs/SESSIONS/2026-10-19_paper-trade-replay-2mo.md`.
