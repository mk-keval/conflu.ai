# Hypothesis & Experiment Log

**Purpose:** one place to see every strategy question this project has tested, how
it was tested, and whether the result is allowed to influence a decision. The log
exists to stop three failure modes: citing a superseded backtest, treating an
in-sample what-if as evidence, and quietly re-testing the same idea until it looks
good.

**Rule:** an experiment is logged **before** it is run. A result without a
pre-declared question is exploratory by definition, no matter how good it looks.

---

## Labels

| Label | Meaning | Can it change a live decision? |
|---|---|---|
| **Confirmatory** | Pre-registered, out-of-sample, forward | Yes — this is the evidence the kill rule uses |
| **Exploratory** | In-sample, post-hoc, or a what-if | No — it generates the next hypothesis |
| **Measurement** | Fixes what is recorded, not what is traded | No decision change; may correct reported numbers |
| **Superseded / invalid** | The engine or data was wrong | No — historical context only |

The forward sample (`FWD-v0.1`) is the only confirmatory experiment. Everything
else in this file is input to the review, never a verdict.

---

## Log

| ID | Date | Experiment | Type | n | Headline result | Status |
|---|---|---|---|---|---|---|
| H-01 | 2026-09 | D-61 elite template deployment | Exploratory (superseded) | 21 templates × 10 symbols × 730d | 12 templates "elite" (WR > 55%, PF > 1.5) | **Invalid** — engine had a 4h blind spot, silent skips, look-ahead exits (D-70) |
| H-02 | 2026-10-19 | D-70 honest template validation | Exploratory (in-sample) | 19 templates × 30 symbols, ~700d | Expectancy +0.07…+0.33R; PF 1.0–1.9; only `breakdown` (short, undeployed) negative | Valid as validation; not forward evidence |
| H-03 | 2026-10-19 | D-71 two-month replay of deployed screens | Exploratory (in-sample replay) | 371 trades, 503 names, 60 days | WR 30.7%, expectancy −0.203R, PF 0.63, −$99.8k at 1% risk; loss concentrated in choppy (242 trades, −0.322R) | Valid as simulation; never enters the scorecard |
| H-04a | 2026-10-19 | What-if: baseline reproduction | Exploratory | 371 | Reproduced stored run exactly | Control |
| H-04b | 2026-10-19 | What-if: wide target (4.5 ATR) | Exploratory | 361 | −0.179R gross, PF 0.68; neutral improves, choppy unchanged | Hypothesis only |
| H-04c | 2026-10-19 | What-if: choppy = full ranging menu | Exploratory | 534 | −0.123R gross; per-trade bleed halves but 67% more chop trades; total $ loss unchanged | Hypothesis only |
| H-04d | 2026-10-19 | What-if: ranging menu + wide target | Exploratory | 528 | −0.089R gross, PF 0.83; still negative | Hypothesis only |
| H-04e | 2026-10-19 | What-if: choppy = mean-reversion only | Exploratory | 332 | −0.015R gross, PF 0.97, −$26.4k net; near flat, still below break-even | Hypothesis only |
| H-05 | 2026-10-19 | D-72 execution v0.1: attribution, sector cap, calendar time stop | Measurement | — | Screen/confluence/regime/sector/max_hold persisted; 3 legacy rows excluded | Applied |
| H-06 | 2026-10-21 | D-73 pending orders / T+1 fills | Measurement (pre-sample correction) | 5 orders to date | Four phantom fills voided; no same-day fills possible; fill rate becomes a diagnostic | Applied; sample restarted |
| H-07 | 2026-10-28 | D-74 canonical P&L, plan provenance, phantom/P&L verifier | Measurement | 10 journal rows | CRS −$1,624.99 → −$30.01 net; 0 phantom fills; 0 P&L mismatches; 3 R:R provenance warnings | Applied; sample continues |
| H-08 | 2026-10-22 → | **FWD-v0.1 forward sample** | **Confirmatory** | 1 closed / 2 open / 1 pending | Expectancy −1.00R, MFE gap +4.72R, net −$30.01 | **Active — not yet evidence** |
| H-09 | 2026-10-30 | D-78 H-09: v0.1 vs v0.2 geometry on one signal stream | Exploratory (counterfactual) | 147 fills; v0.1 accepted 120; v0.2 accepted 103 (44 rejected) | v0.2 accepted −0.138R vs v0.1 accepted −0.050R; exit-only on 103 paired fills −0.138R vs −0.096R; rejected counterfactual +0.012R | Frozen; dry-run only; earliest full write 2026-11-24; never evidence |
| H-10 | 2026-11-12 | D-81 research baseline v2: 4 setups vs matched-random/permuted/shifted controls | Exploratory (in-sample, 2015-2026) | 1876 / 1982 / 1860 / 2373 closed trades | No setup beat the matched control (p 0.61-0.94); mechanical verdicts NO EVIDENCE OF EDGE for `breakout_52week`, `statistical_mean_reversion`, `volume_trend_accumulation`; `low_vol_setup` flagged SUSPECTED BUG (max DD -43.0% vs -40% guard) | **Superseded by H-11 (D-82)** — valid only for the D-81 engine/window; the D-82 run replaces it. Never the scorecard, pass bar or kill rule |
| H-11 | 2026-11-13 | D-82 research baseline v3: same four setups under a realistic engine (no same-day recycling, masked warm-up, one evaluation window, block-bootstrap CI) | Exploratory (in-sample, 2015-2026) | 1684 / 1746 / 1680 / 2120 closed trades | No setup beat the matched control (p 0.29–1.00); max DD worst -35.6%; mechanical verdicts NO EVIDENCE OF EDGE for all four; `low_vol_setup` no longer flagged | **Exploratory** — valid for one 2015-2026 panel and the D-82 contract; never the scorecard, pass bar or kill rule. **Superseded for the headline by H-12 (D-83)**; the D-82 contract stands. Supersedes H-10 |
| H-12 | 2026-11-17 | D-83 research baseline v4: same four setups, headline expectancy and p-value averaged over 20 engine seeds (42..61) on identical signals | Exploratory (in-sample, 2015-2026; post-hoc rule change) | 1686 / 1747 / 1677 / 2147 closed trades (seed 42) | Seed-mean expectancy +0.0278 / +0.0107 / +0.0167 / +0.0036; matched p (seed-averaged) 0.6452 / 0.7097 / 0.8065 / 1.0000; informational underperformance line for volume only (Gap / control std -2.31; low_vol -0.57 and SMR -0.79 not flagged); NO EVIDENCE OF EDGE for all four | **Exploratory** - valid for one 2015-2026 panel and the D-83 rule; the seed-averaged headline was introduced after seeing D-82, so it is not pre-registered. Never the scorecard, pass bar or kill rule. Supersedes H-11 for the headline |
| H-13 | 2026-11-17 | E1 / D-84 event study: forward returns after each real setup signal, minus the same-date eligible-universe mean, at horizons 1, 5, 10, 20, 60; no stops, targets or portfolio rules | Exploratory (in-sample, 2015-2026; post-hoc, no pre-registration) | 9014 / 4915 / 9168 / 14481 events after cooldown (SMR / breakout / low_vol / volume) | h=5 mean excess -9.0 / +7.7 / -5.2 / +5.5 bp; h=20 -26.1 / +14.6 / -15.4 / -11.1 bp; 200 matched-random nulls, seeds 50000..50199 | **EXPLORATORY** - one survivorship-biased panel, no walk-forward, same-date eligibility benchmark, no portfolio constraints. Not pre-registered. Never the scorecard, D-75 pass bar, kill rule or forward verdict |
| H-14 | 2026-11-17 | E2 / D-84 exit study: five exit variants (B0-B4) on the same entries, compared with 100 matched-random entry sets under the same exit | Exploratory (in-sample, 2015-2026; post-hoc, no pre-registration) | 16683 / 6819 / 18346 / 20830 entries before exit-variant drops (SMR / breakout / low_vol / volume) | Best mean r_net: low_vol B4 0.2463 (gap 0.0310, gap/std 2.66); worst: breakout B3 -0.0484 (gap -0.0500, gap/std -4.02); 4 setups x 5 variants = 20 cells, not independent | **EXPLORATORY** - one survivorship-biased panel, no walk-forward, no capacity or slot competition, shared entries across variants and nulls. Not pre-registered. Never the scorecard, D-75 pass bar, kill rule or forward verdict |

---

## What each experiment actually tested

### H-01 — D-61 elite template deployment (invalid)

**Question:** which of the 21 templates have a deployable edge?

**What happened:** the original engine reported PF 3–52 and 12 "elite" templates.
D-70 found the engine had a 4-hour timeframe blind spot, silently skipped rules it
could not evaluate, and used look-ahead/collapsed exits. The numbers were not
reproducible under honest mechanics.

**Consequence:** every D-61 statistic is retired. `config/regime_screens.yaml`
still carries a caveat banner; weights were not re-tuned (user decision). Do not
cite D-61 in any review.

---

### H-02 — D-70 honest template validation (exploratory)

**Question:** with honest mechanics (full rule objects, per-rule timeframes,
next-open entries, ATR 2.0/3.0 exits, 15-bar cap, costs), do the deployed
templates still show positive expectancy?

**Design:** 19 templates × 30 symbols, trailing ~700 days, 0 capacity violations.
This is in-sample validation on a fixed symbol list — not a forward test and not a
portfolio simulation.

**Result:** expectancy +0.07…+0.33R, PF 1.0–1.9. The deployed set is mostly
positive; `bull-flag-continuation` is the weakest deployed template (PF 1.15);
only `breakdown` (short, not deployed) is negative.

**What it supports:** the templates are not obviously broken under honest
mechanics. **What it does not support:** that the deployed *system* (screens +
gate + sizing + exits) makes money. H-03 tests that; it does not.

Artifact: `docs/backtests/VALIDATION_REPORT.md`,
`docs/backtests/validation_20261019_191610.json`.

---

### H-03 — D-71 two-month replay (exploratory)

**Question:** if the deployed screens had run over the last two months, with
as-of regime selection and honest execution, what would the ledger look like?

**Design:** 503-name S&P 500, 60 days, regime computed as of each signal day,
screen mix parity-tested against the live selector, next-open entries, ATR 2/3
exits, 15-bar cap, 10 + 5 bps per side, dedupe per symbol/day. Separate
`replay_runs` / `replay_trades` tables.

**Result:** 371 trades, 114 W / 257 L, WR 30.7%, expectancy −0.203R, PF 0.63,
−$99.8k at 1% risk. 242 of 371 trades (65%) and ~94% of the dollar loss came from
choppy-regime sessions; every deployed choppy screen lost ≈ −0.35R. Only
`statistical-mean-reversion` (+0.162R), `institutional-trend-follower-mtf`
(+0.183R, 6 trades) and `trend-follower-v2` (+0.021R, 9 trades) were positive.

**What it supports:** the deployed menu is structurally mismatched to chop; the
gate is not the only problem. **What it does not support:** a forward verdict.
TradingView cannot be rewound, so the replay does not reproduce the live brief
(ranking, confluence, catalysts, gate) and its universe/execution differ.

**Critical caveat:** the replay has no gate. It enters every signal. A negative
replay is a statement about the screens, not about the gated live system.

Artifact: `docs/backtests/replay_20261019_202541.json`, session log
`docs/SESSIONS/2026-10-19_paper-trade-replay-2mo.md`.

---

### H-04 — What-if family (exploratory, in-sample)

**Question:** which single design change most improves the replay's negative
expectancy?

**Design:** re-ran the cached replay window with one change at a time. Baseline
reproduced the stored run exactly. R-multiples are gross; dollar P&L is net of the
same costs.

| Variant | Trades | WR (net) | Exp R (gross) | PF | Net P&L | Choppy exp R |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 371 | 30.7% | −0.203 | 0.63 | −$99,788 | −0.322 |
| wide target (4.5 ATR) | 361 | 29.1% | −0.179 | 0.68 | −$88,532 | −0.322 |
| choppy = full ranging menu | 534 | 36.0% | −0.123 | 0.76 | −$100,146 | −0.168 |
| ranging menu + wide target | 528 | 35.2% | −0.089 | 0.83 | −$81,268 | −0.144 |
| choppy = mean-reversion only | 332 | 39.8% | −0.015 | 0.97 | −$26,427 | −0.038 |

**What it supports:**

- Menu routing alone is not the fix: the full ranging menu halves per-trade chop
  bleed but takes 67% more chop trades, so total dollars are unchanged.
- The single-screen chop variant is near flat gross but still below the ~44% net
  break-even win rate.
- Wider targets help trend/neutral, not chop.
- Sizing reductions cut dollar damage but do not change R.

**What it does not support:** any claim that one of these variants is deployable.
Five variants on one 60-day window is a multiple-comparisons exercise; the best
row is the most likely to be noise. These are hypotheses for the review, not a
menu recommendation.

Artifacts: `docs/backtests/replay_whatif_20261019_211236.json`,
`docs/backtests/replay_whatif_20261019_214028.json`, runner
`run_replay_experiments.py`.

---

### H-05 — D-72 execution v0.1 (measurement)

**Question:** can the live path record what it actually decided (screen,
confluence, sector, regime, time stop)?

**Result:** yes. Attribution now comes from the brief ticker (not the verdict),
sector from the analysis response (the 30% cap binds), `max_hold_days` is stored
and executed as calendar days, and the 3 legacy rows are flagged
`exclude_from_stats=1`.

**Not a strategy test.** It did not change targets, the R:R gate, screens,
sizing or regime permission.

---

### H-06 — D-73 pending orders (measurement, pre-sample)

**Question:** were the first four forward entries real?

**Result:** no. PM and AMGN were booked far below the session low; CCK and MMM
were same-day fills after an after-close signal (look-ahead). All four are voided
and visible (`voided=1`, `exclude_from_stats=1`). The execution model is now:
pending limit at `entry_low`, T+1 or later fills only, 3-session expiry,
same-session stop but no same-session target.

**Consequence:** the forward clock restarts at the first actual fill (2026-10-22,
SF @ 65.40). The pre-correction runs remain in `workflow_runs` as history; they are
not evidence.

---

### H-07 — D-74 P0 measurement (measurement)

**Question:** do the reported dollar P&L and the stored plan geometry match what
actually happened?

**Result:** no, on both counts.

- `pnl_usd` multiplied R by **notional** instead of dollar risk. CRS reported
  −$1,624.99; the actual gross was −$25.17 and net −$30.01.
- The gate's R:R and the journal's stored-plan R:R did not reconcile (CRS 4.32 vs
  11.89; IOSP 6.15 vs 3.99; SF 6.47 vs 4.36). The gate used a `risk_reward` value
  that was not always the last stored target; `target_3` was never persisted.
- The live path recorded gross dollars while the backtests recorded net.

**What changed:** a canonical P&L module, `pnl_gross_usd` / `costs_usd` /
`plan_rr` / `target_1_r` / `target_3` columns, a backfill, and
`scripts/verify_journal.py` as a PASS/FAIL gate. No trading decision changed.

---

### H-08 — FWD-v0.1 forward sample (confirmatory, active)

**Question:** does the deployed system produce positive expectancy on real,
tradeable forward fills?

**Pre-registration:** [PRE_REGISTRATION.md](../PAPER_TRADING/PRE_REGISTRATION.md).
**Current state:** 1 closed (CRS −1.00R, MFE +3.72R), 2 open (SF, IOSP), 1 pending
(DUK). Expectancy −1.00R; net −$30.01; kill rule not yet (1/30).

**This is the only row in the log that can kill the system.** It is deliberately
underpowered today. The correct statement is "no verdict", not "negative
expectancy confirmed."

---

### H-09 — D-78 H-09 replay: v0.1 vs v0.2 geometry (exploratory, frozen)

**Backfilled 2026-11-11 from [D-78](../DECISIONS/D-78-h09-replay-freeze.md).**

**Question:** on one signal stream, does the v0.2 geometry plus exit policy beat
v0.1, or does it just reject more trades?

**Design:** the D-71 entry stream over the frozen window 2026-08-20 to
2026-10-19, planned twice on shared signal-close geometry (entry band, stop
`C − 2.0×ATR`, D-73 limit fill). v0.1 reproduces the live midpoint gate and
`infer_exit`; v0.2 applies the nearest structural T1 inside the family band,
the family Plan-R floor and the D-77 exit policy. Only gate step 5 is replayable.

**Result (dry run, censored):** 147 fills; v0.1 accepted 120, v0.2 accepted 103
(44 rejected: target too close 15, too far 24, no structural objective 5).
v0.2 accepted −0.138R vs v0.1 accepted −0.050R; exit-only on 103 paired fills
−0.138R vs −0.096R; the 44 rejected plans' v0.1 counterfactual was +0.012R.

**What it supports:** v0.2's exit policy did not add value on this window and
v0.2 rejected marginally profitable v0.1 trades. **What it does not support:**
any v0.2 verdict. Evidence label `exploratory_h09_not_evidence`; never the
scorecard, D-75 bar, kill rule or `/expectancy`. Earliest full write:
2026-11-24 (36-day horizon). Artifacts:
`docs/backtests/h09_replay_20261030_150747.json` and `..._151453.json`.

---

### H-10 — D-81 research baseline v2: four setups vs matched controls (exploratory, in-sample)

**Question:** does any of the four setup signal streams beat a size-matched random
control on one clean S&P 500 panel?

**Design:** standalone `backend/app/research` harness. Daily bars, signal at close,
next-open entry, 2.0 ATR stop, 3.0 ATR target, 15-bar hold, 0.5% equity risk, 8
positions, 20% notional cap, 15 bps/side. Entries size off previous-close equity (no
look-ahead), open positions are marked with forward-filled closes, and every position is
closed (`data_end` / `eod_censored`) with a hard `final_equity == start_equity +
sum(pnl_usd)` check. Window 2015-01-01..2026-11-11 on the current S&P 500 snapshot (501
tradable symbols; 2 dropped with reasons). Controls: 30 matched-random runs (same daily
entry count as the strategy, random eligible symbol), 10 permuted-date runs, 2
time-shifted runs. One-sided p-values on `r_net_mean` with `(k+1)/(n+1)`; direction never
flipped. Report statistics exclude censored trades and 2015 exits.

**Result (valid for this panel):**

| Setup | n | Win rate | Expectancy net | PF | CAGR | Max DD | matched p | Verdict |
|---|---|---|---|---|---|---|---|---|
| breakout_52week | 1876 | 47.2% | -0.008 | 0.98 | -1.6% | -36.0% | 0.9355 | NO EVIDENCE OF EDGE |
| low_vol_setup | 1982 | 47.5% | 0.000 | 1.00 | -0.7% | **-43.0%** | 0.6774 | **SUSPECTED BUG** |
| statistical_mean_reversion | 1860 | 47.7% | -0.001 | 1.00 | -0.9% | -35.2% | 0.6129 | NO EVIDENCE OF EDGE |
| volume_trend_accumulation | 2373 | 47.8% | 0.018 | 1.03 | 0.2% | -37.8% | 0.7742 | NO EVIDENCE OF EDGE |

All four accounts reconcile. Matched control trade counts (1979-2468) are close to the
strategies' closed counts (1876-2373). Shadow controls: permuted p-values 1.0000 /
0.7273 / 0.8182 / 0.7273; shifted 0.6667 / 0.3333 / 1.0000 / 0.3333 (breakout / low_vol /
SMR / volume). Their floors are 0.091 and 0.333 at 10 and 2 runs.

**What it supports:** on one clean 2015-2026 panel, no setup beat the matched random
control at p <= 0.05. The report's mechanical verdict is `NO EVIDENCE OF EDGE` for three
setups. `low_vol_setup` hit the report's -40% max-drawdown guard (-43.0%), which is a
request to investigate the account path, not an edge claim. **What it does not support:**
any deployment, weight change or scorecard entry. This is not a verdict on the deployed
templates (different exits, D-70/D-77), there is no holdout, the universe is the current
index (survivorship), and the matched control cannot reach p < 0.032 with 30 runs.

**Evidence label:** `exploratory_research` — research harness only; never the
scorecard, D-75 pass bar, kill rule or `/expectancy`.

**Artifacts:** `docs/backtests/research/{setup}_20261111_21*.json`
(HEAD `dcc9565`, dirty; all invariants hold) and the generated
[`BASELINE_REPORT.md`](research/BASELINE_REPORT.md); see the
[artifact README](research/README.md). **Status:** 2015-2026 re-run recorded; supersedes
the D-80 2020-2023 row, which is retained in the D-80 record as history. The 13
superseded artifacts are quarantined under `research/invalid_20261110/`.

**Superseded 2026-11-13 by [D-82](../DECISIONS/D-82-research-baseline-v3-engine-realism.md)
/ H-11.** The D-81 guarantees stand; the D-81 *result table* is no longer current because
same-day slot recycling, unmasked indicator warm-up, two different samples and a
per-trade-R Sharpe/bar-count CAGR were still in the harness.

---

### H-11 — D-82 research baseline v3: same four setups under a realistic engine (exploratory, in-sample)

**Question:** once the engine stops allowing same-day slot recycling, masks indicator
warm-up, and measures the strategy and every control over one declared evaluation window,
does any of the four setups beat a size-matched random control?

**Design:** standalone `backend/app/research` harness. Daily bars, signal at close,
next-open entry, 2.0 ATR stop, 3.0 ATR target, 15-bar hold, 0.5% equity risk, 8 positions,
20% notional cap, 15 bps/side, **no same-day recycling**. Entries size off previous-close
equity (no look-ahead), open positions are marked with forward-filled closes, and every
position is closed (`data_end` / `eod_censored`) with a hard `final_equity == start_equity
+ sum(pnl_usd)` check. Every indicator is masked at its own window; `eligible()` requires
`atr14`. Window 2015-01-01..2026-11-13 on the current S&P 500 snapshot (501 tradable
symbols; 2 dropped with reasons). Trade statistics and all four control families use
uncensored trades with exit date >= 2016-01-01 (`EVAL_START`); equity statistics use the
full curve; reconciliation uses all trades. Controls: 30 matched-random runs, 10
permuted-date runs, 2 time-shifted runs, all applying `eligible()`. One-sided p-values on
`r_net_mean` with `(k+1)/(n+1)`; direction never flipped. The 95% CI is a month-block
bootstrap and the verdict uses its lower bound.

**Result (valid for this panel):**

| Setup | n | Win rate | Expectancy net | PF | CAGR | Max DD | matched p | Verdict |
|---|---|---|---|---|---|---|---|---|
| breakout_52week | 1684 | 48.6% | 0.033 | 1.07 | 1.5% | -21.1% | 0.6452 | NO EVIDENCE OF EDGE |
| low_vol_setup | 1746 | 48.4% | 0.028 | 1.05 | 1.6% | -31.6% | 0.3871 | NO EVIDENCE OF EDGE |
| statistical_mean_reversion | 1680 | 50.1% | 0.049 | 1.11 | 2.4% | -23.4% | 0.2903 | NO EVIDENCE OF EDGE |
| volume_trend_accumulation | 2120 | 47.0% | -0.004 | 0.99 | -0.6% | -35.6% | 1.0000 | NO EVIDENCE OF EDGE |

All four accounts reconcile. Matched control trade counts (1668-2042) are close to the
strategies' closed counts (1680-2120). Shadow controls: permuted p-values 1.0000 / 0.8182 /
0.2727 / 1.0000; shifted 0.3333 / 0.6667 / 1.0000 / 1.0000 (breakout / low_vol / SMR /
volume). Their floors are 0.091 and 0.333 at 10 and 2 runs.

**What it supports:** on one clean 2015-2026 panel under the D-82 contract, no setup beat
the matched random control at p <= 0.05; the smallest p is 0.2903. `low_vol_setup` is no
longer flagged — its D-81 flag was the -40% drawdown guard, and its D-82 max drawdown is
-31.6%. **What it does not support:** any deployment, weight change or scorecard entry.
This is not a verdict on the deployed templates (different exits, D-70/D-77), there is no
holdout, the universe is the current index (survivorship), and the matched control cannot
reach p < 0.032 with 30 runs. The artifacts predate the T6(a) control-eligibility fix, so
their control p-values do not include that gate; the effect was not re-measured (T6 forbids
re-running the baseline).

**Evidence label:** `exploratory_research` — research harness only; never the scorecard,
D-75 pass bar, kill rule or `/expectancy`.

**Artifacts:** `docs/backtests/research/{setup}_20261113_*.json` (revision `7ed0135`;
`dirty = false` for the first run and `dirty = true` for the other three, because the
preceding run's artifact was untracked — no source file differed; `eval_start =
2016-01-01`; all invariants hold) and the generated
[`BASELINE_REPORT.md`](research/BASELINE_REPORT.md); see the
[artifact README](research/README.md). **Status:** 2015-2026 re-run recorded; supersedes
H-10. The D-81 artifacts stay in place as the previous baseline and must not be cited as
current.

**Ablation (2026-11-16):** re-running the four setups with `--allow-same-day-recycling`
(one flag; everything else default) gives expectancy net -0.0004 / -0.0007 / -0.0007 /
+0.0032 with matched p 0.9032 / 0.7097 / 0.6129 / 0.9677 (breakout / low_vol / SMR /
volume). On expectancy net the flag accounts for +81.7% / +102.4% / +99.3% / +32.5% of the
D-81 → D-82 move. These runs use the 2026-11-16 default panel, record `dirty = false` at
revision `7628660`, and are documented in [`ABLATION.md`](research/ABLATION.md) with the
refreshed [`DIAGNOSTICS.md`](research/DIAGNOSTICS.md).

**Superseded for the headline (2026-11-17):** H-12 (D-83) replaces this headline with the
mean of 20 engine seeds, and the test p-value with the seed-averaged p-value. The D-82
engine contract, the artifacts above and every guarantee in this section stand; only the
headline expectancy and p-value columns are superseded.

### H-12 - D-83 research baseline v4: 20-seed headline and seed-averaged p-value (exploratory, in-sample, post-hoc)

**Question:** the engine seed does not change the signals, only which same-date candidates
fill the eight slots. If the same four setups are run under seeds 42..61 on identical
signals, does the seed-mean expectancy or the seed-averaged p-value change the D-82
verdict?

**Design:** same harness and contract as H-11 (no same-day recycling, masked warm-up,
`EVAL_START = 2016-01-01`, 2.0 ATR stop / 3.0 ATR target / 15-bar hold, 0.5% risk, 8
positions, 20% cap, 15 bps/side). `--n-strategy-seeds 20` runs the strategy 20 times and
records `run_info.strategy_seeds = {seeds, r_net_mean[], mean, std, se}` (population std,
`se = std/sqrt(20)`). Seed 42 remains the primary artifact; its trades, equity, metrics,
CIs, per-year tables and reconciliation are unchanged. `p_values_seed_avg` applies the
same `compute_control_pvalues` formula to the seed-mean `r_net_mean` against the same 30
matched-random / 10 permuted / 2 shifted controls. Window 2015-01-01..2026-11-17 on the
current S&P 500 snapshot (501 tradable symbols; 2 dropped with reasons).

**Result (valid for this panel and window):**

| Setup | n | Seed 42 | 20-seed mean (std / se) | Control mean (std) | Gap | Gap / control std | SE of means (not a test) | p (seed 42) | p (seed-averaged) | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| `breakout_52week` | 1686 | +0.0277 | +0.0278 (0.0148 / 0.0033) | +0.0355 (0.0271) | -0.0077 | -0.28 | 0.0060 | 0.6452 | 0.6452 | NO EVIDENCE OF EDGE |
| `low_vol_setup` | 1747 | +0.0243 | +0.0107 (0.0185 / 0.0041) | +0.0253 (0.0257) | -0.0146 | -0.57 | 0.0062 | 0.5484 | 0.7097 | NO EVIDENCE OF EDGE |
| `statistical_mean_reversion` | 1677 | +0.0566 | +0.0167 (0.0183 / 0.0041) | +0.0349 (0.0231) | -0.0182 | -0.79 | 0.0059 | 0.2258 | 0.8065 | NO EVIDENCE OF EDGE |
| `volume_trend_accumulation` | 2147 | -0.0069 | +0.0036 (0.0213 / 0.0048) | +0.0502 (0.0201) | -0.0466 | -2.31 | 0.0060 | 1.0000 | 1.0000 | NO EVIDENCE OF EDGE |

All four accounts reconcile. Seed-42 vs seed-mean is +0.0277 -> +0.0278 (breakout),
+0.0243 -> +0.0107 (low_vol), +0.0566 -> +0.0167 (SMR), -0.0069 -> +0.0036 (volume). The
report printed the informational underperformance line for volume only
(`Gap / control std = -2.31`); breakout (-0.28), low_vol (-0.57) and SMR (-0.79) are not
flagged. `SE of means` is descriptive only (shuffle noise plus the error of the control
mean, not selection variability). The flag was corrected in T11 from `gap < -2 SE` to
`gap / control_std < -2`; p-values and verdicts are unchanged. Shadow seed-averaged
p-values: permuted / shifted 0.9091 / 0.3333 (breakout), 0.9091 / 0.6667 (low_vol),
0.7273 / 1.0000 (SMR), 1.0000 / 1.0000 (volume).

**What it supports:** on this panel, with the signals held fixed, the 20-seed mean does not
raise any setup above the matched control, and the seed-averaged p-values are at or above
the seed-42 p-values (0.6452, 0.7097, 0.8065, 1.0000). For low_vol, SMR and volume the
seed-42 expectancy is above the 20-seed mean; for breakout the two differ by 0.0001 R.
**What it does not support:** any deployment, weight change or scorecard entry. The
seed-averaged headline was chosen after the D-82 tables were read, so it is not a
pre-registered test; the panel is still the current index (survivorship) with no
walk-forward, the research setups differ from the deployed templates, and the matched
control draws from all eligible symbols rather than the setup's own candidates.

**Evidence label:** `exploratory_research` - research harness only; never the scorecard,
D-75 pass bar, kill rule or `/expectancy`.

**Artifacts:** `docs/backtests/research/{breakout_52week_20261117_095332,
low_vol_setup_20261117_100100, statistical_mean_reversion_20261117_100839,
volume_trend_accumulation_20261117_101631}.json` (revision `3bfb68c`, `dirty = false`,
`allow_same_day_recycling = false`, 20 seeds 42..61, `eval_start = "2016-01-01"`) and the
generated [`BASELINE_REPORT.md`](research/BASELINE_REPORT.md); see the
[artifact README](research/README.md). **Status:** supersedes H-11 for the headline; the
D-82 engine contract and artifacts stand.

---

### H-13 — E1 / D-84 event study (exploratory)

**Question (task title):** does the signal carry information, at which horizon?

**Design:** committed as `687df51`. `backend/app/research/events.py` (pure) plus
`scripts/research_event_study.py` load the same panel as the baseline runner
(`download_daily` on `.cache/research`, 2015-01-01 -> latest, `add_indicators`;
`NON_TRADABLE` excluded) and mark `ret_h = close[e+h-1] / open[e] - 1` at horizons
1, 5, 10, 20, 60 after each `SETUPS[name](df)` signal with `eligible(df)` at the
signal bar and entry date >= 2016-01-01. Cooldown drops a repeat when the previous
accepted event is <= 5 bars earlier. Excess = event `ret_h` minus the same-date mean
over all eligible symbols. Null: 200 matched-random sets per setup from
`backend.app.research.control.matched_random_signals`, seeds 50000..50199. Flags:
`--setups`, `--horizons`, `--cooldown`, `--n-null`, `--report`, `--json-dir`.
Panel: 2015-01-02 -> 2026-11-17, 501 tradable, 2 dropped, 503 cache hits / 0 downloads.

**Result:** events after cooldown 9014 / 4915 / 9168 / 14481 (SMR / breakout /
low_vol / volume). h=5 mean excess -9.0 / +7.7 / -5.2 / +5.5 bp; h=20 -26.1 /
+14.6 / -15.4 / -11.1 bp. Full h=5 and h=20 tables, including the by-calendar-year
rows, are copied into [D-84](../DECISIONS/D-84-research-signal-information-and-exit-shape.md)
and the source is [`EVENT_STUDY.md`](research/EVENT_STUDY.md).

**What it supports / does not support:** the report states the event study "has no
stops, targets, position limits, slot competition or capital constraint; it cannot be
read as a portfolio result", and the benchmark "is a same-date market/eligibility mean,
not a sector- or size-matched benchmark". **Evidence label:** `EXPLORATORY` — one
in-sample, survivorship-biased panel, no walk-forward, no pre-registration. Never the
scorecard, D-75 pass bar, kill rule or forward verdict.

**Artifacts:** `docs/backtests/research/EVENT_STUDY.md` (generated),
`docs/backtests/research/event_study/event_study_20261117_134829.json` (generated),
`backend/tests/test_research_events.py` (six synthetic tests),
`docs/SESSIONS/research-discovery-log.md` (E1 entry).

---

### H-14 — E2 / D-84 exit study (exploratory)

**Question (task title):** are our exits wasting a real signal?

**Design:** committed as `62abbef`. `backend/app/research/exit_study.py` (pure) plus
`scripts/research_exit_study.py` apply variants B0-B4 to the same entries (signal at
`t`, entry at the open of `t+1`, `atr14` of the signal bar, skip NaN/<=0). 1R is
always `2 * ATR`; costs are 15 bps per side with the engine's `r_net`/`r_gross`
formulas; B4 exits at the close of the 20th bar including entry (`max_hold=19`).
Null: 100 matched-random entry sets per setup from
`backend.app.research.control.matched_random_signals`, seeds 60000..60099, same entry
and exit rules. Flags: `--setups`, `--n-null`, `--report`, `--json-dir`. The work log
records that the first smoke-run trailing stop used pre-entry highs and was corrected
before the full run.

**Result:** entries considered before drops 16683 / 6819 / 18346 / 20830. Best mean
`r_net`: `low_vol_setup` B4 0.2463 (null mean 0.2153, null std 0.0116, gap 0.0310,
gap/std 2.66, p_high 0.0099, p_low 1.0000). Worst: `breakout_52week` B3 -0.0484
(null mean 0.0016, null std 0.0125, gap -0.0500, gap/std -4.02, p_high 1.0000,
p_low 0.0099). Full 4 x 5 table is in [`EXIT_STUDY.md`](research/EXIT_STUDY.md).

**What it supports / does not support:** the report states the analysis "ignores
portfolio capacity and slot competition: every signal is taken as an independent
trade, with no limit on concurrent positions or capital" and "variants share the same
entries and the same signals are reused across variants and null draws, so the cells
are not independent trials". **Evidence label:** `EXPLORATORY` — one in-sample,
survivorship-biased panel, no walk-forward, no pre-registration. Never the scorecard,
D-75 pass bar, kill rule or forward verdict.

**Artifacts:** `docs/backtests/research/EXIT_STUDY.md` (generated),
`docs/backtests/research/event_study/exit_study_20261117_142553.json` (generated),
`backend/tests/test_research_exit_study.py` (six synthetic tests),
`docs/SESSIONS/research-discovery-log.md` (E2 entry).

---

## Trial ledger

Values copied verbatim from `docs/backtests/research/EVENT_STUDY.md` and
`docs/backtests/research/EXIT_STUDY.md`. **E1: 4 setups x 5 horizons = 20 cells.
E2: 4 setups x 5 variants = 20 cells.** Every cell is `EXPLORATORY`.

### E1 — 20 cells (setup x horizon)

| Setup | h | n | dates | mean excess (bp) | 95% CI (bp) | hit rate | raw mean | raw mean - 30 bp | null mean (bp) | null std (bp) | p_high | p_low | Label |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| statistical_mean_reversion | 1 | 9014 | 1684 | -1.4 | [-6.8, 4.2] | 49.7% | -0.018% | -0.318% | 0.0 | 1.3 | 0.8507 | 0.1542 | EXPLORATORY |
| statistical_mean_reversion | 5 | 9014 | 1684 | -9.0 | [-21.6, 4.3] | 49.4% | 0.405% | 0.105% | -0.0 | 3.0 | 1.0000 | 0.0050 | EXPLORATORY |
| statistical_mean_reversion | 10 | 9010 | 1682 | -15.6 | [-37.6, 5.4] | 49.2% | 0.312% | 0.012% | -0.1 | 4.1 | 1.0000 | 0.0050 | EXPLORATORY |
| statistical_mean_reversion | 20 | 8990 | 1673 | -26.1 | [-57.7, 3.4] | 47.6% | 0.995% | 0.695% | -0.1 | 6.0 | 1.0000 | 0.0050 | EXPLORATORY |
| statistical_mean_reversion | 60 | 8752 | 1637 | -51.7 | [-115.2, 16.5] | 48.0% | 4.236% | 3.936% | -0.5 | 9.7 | 1.0000 | 0.0050 | EXPLORATORY |
| breakout_52week | 1 | 4915 | 1478 | 1.8 | [-4.6, 8.0] | 50.3% | -0.000% | -0.300% | 0.0 | 1.8 | 0.1542 | 0.8507 | EXPLORATORY |
| breakout_52week | 5 | 4910 | 1476 | 7.7 | [-9.2, 25.2] | 49.9% | 0.223% | -0.077% | 0.1 | 4.5 | 0.0547 | 0.9502 | EXPLORATORY |
| breakout_52week | 10 | 4881 | 1472 | 20.9 | [-2.3, 45.4] | 50.1% | 0.615% | 0.315% | -0.2 | 6.7 | 0.0100 | 0.9950 | EXPLORATORY |
| breakout_52week | 20 | 4837 | 1462 | 14.6 | [-21.5, 52.0] | 48.1% | 0.823% | 0.523% | -0.3 | 9.1 | 0.0448 | 0.9602 | EXPLORATORY |
| breakout_52week | 60 | 4813 | 1448 | 31.4 | [-37.7, 100.4] | 48.2% | 3.169% | 2.869% | -0.6 | 16.4 | 0.0398 | 0.9652 | EXPLORATORY |
| low_vol_setup | 1 | 9168 | 1911 | -0.8 | [-3.1, 1.4] | 49.5% | -0.002% | -0.302% | -0.0 | 0.9 | 0.8060 | 0.1990 | EXPLORATORY |
| low_vol_setup | 5 | 9165 | 1909 | -5.2 | [-13.0, 2.5] | 49.6% | 0.143% | -0.157% | 0.2 | 2.4 | 0.9900 | 0.0149 | EXPLORATORY |
| low_vol_setup | 10 | 9163 | 1908 | -11.5 | [-26.9, 2.7] | 49.2% | 0.380% | 0.080% | 0.0 | 3.6 | 1.0000 | 0.0050 | EXPLORATORY |
| low_vol_setup | 20 | 9161 | 1906 | -15.4 | [-44.8, 10.2] | 48.8% | 1.008% | 0.708% | -0.1 | 4.9 | 1.0000 | 0.0050 | EXPLORATORY |
| low_vol_setup | 60 | 9109 | 1878 | -49.2 | [-104.6, 2.4] | 47.8% | 2.176% | 1.876% | -0.0 | 8.1 | 1.0000 | 0.0050 | EXPLORATORY |
| volume_trend_accumulation | 1 | 14481 | 2369 | 1.6 | [-2.1, 5.2] | 50.8% | 0.023% | -0.277% | -0.1 | 0.9 | 0.0299 | 0.9751 | EXPLORATORY |
| volume_trend_accumulation | 5 | 14465 | 2366 | 5.5 | [-2.8, 13.5] | 49.6% | 0.237% | -0.063% | 0.1 | 2.6 | 0.0299 | 0.9751 | EXPLORATORY |
| volume_trend_accumulation | 10 | 14411 | 2362 | 3.1 | [-9.6, 17.4] | 48.7% | 0.504% | 0.204% | -0.0 | 3.3 | 0.1692 | 0.8358 | EXPLORATORY |
| volume_trend_accumulation | 20 | 14285 | 2352 | -11.1 | [-35.8, 13.0] | 48.1% | 0.808% | 0.508% | 0.1 | 5.1 | 0.9851 | 0.0199 | EXPLORATORY |
| volume_trend_accumulation | 60 | 14160 | 2320 | -11.7 | [-57.6, 30.6] | 47.2% | 3.130% | 2.830% | -0.4 | 9.4 | 0.8756 | 0.1294 | EXPLORATORY |

### E2 — 20 cells (setup x variant)

| Setup | Variant | n | mean r_net | null mean | null std | gap | gap/std | p_high | p_low | Label |
|---|---|---|---|---|---|---|---|---|---|---|
| statistical_mean_reversion | B0 | 16659 | 0.0494 | 0.0758 | 0.0068 | -0.0264 | -3.87 | 1.0000 | 0.0099 | EXPLORATORY |
| statistical_mean_reversion | B1 | 16651 | 0.0331 | 0.0715 | 0.0079 | -0.0384 | -4.89 | 1.0000 | 0.0099 | EXPLORATORY |
| statistical_mean_reversion | B2 | 16593 | 0.1545 | 0.1763 | 0.0098 | -0.0218 | -2.22 | 0.9901 | 0.0198 | EXPLORATORY |
| statistical_mean_reversion | B3 | 16668 | 0.0453 | 0.0617 | 0.0078 | -0.0164 | -2.10 | 0.9901 | 0.0198 | EXPLORATORY |
| statistical_mean_reversion | B4 | 16639 | 0.0649 | 0.1191 | 0.0108 | -0.0542 | -5.03 | 1.0000 | 0.0099 | EXPLORATORY |
| breakout_52week | B0 | 6772 | -0.0018 | 0.0250 | 0.0124 | -0.0268 | -2.16 | 1.0000 | 0.0099 | EXPLORATORY |
| breakout_52week | B1 | 6754 | 0.0010 | 0.0290 | 0.0128 | -0.0280 | -2.18 | 0.9802 | 0.0297 | EXPLORATORY |
| breakout_52week | B2 | 6754 | 0.0127 | 0.0819 | 0.0178 | -0.0692 | -3.90 | 1.0000 | 0.0099 | EXPLORATORY |
| breakout_52week | B3 | 6786 | -0.0484 | 0.0016 | 0.0125 | -0.0500 | -4.02 | 1.0000 | 0.0099 | EXPLORATORY |
| breakout_52week | B4 | 6712 | 0.0641 | 0.0609 | 0.0181 | 0.0032 | 0.18 | 0.4653 | 0.5446 | EXPLORATORY |
| low_vol_setup | B0 | 18338 | 0.0572 | 0.0616 | 0.0072 | -0.0044 | -0.61 | 0.7030 | 0.3069 | EXPLORATORY |
| low_vol_setup | B1 | 18338 | 0.0998 | 0.1006 | 0.0085 | -0.0008 | -0.09 | 0.5347 | 0.4752 | EXPLORATORY |
| low_vol_setup | B2 | 18330 | 0.1887 | 0.1653 | 0.0112 | 0.0234 | 2.09 | 0.0297 | 0.9802 | EXPLORATORY |
| low_vol_setup | B3 | 18335 | 0.0604 | 0.0511 | 0.0078 | 0.0093 | 1.20 | 0.1188 | 0.8911 | EXPLORATORY |
| low_vol_setup | B4 | 18336 | 0.2463 | 0.2153 | 0.0116 | 0.0310 | 2.66 | 0.0099 | 1.0000 | EXPLORATORY |
| volume_trend_accumulation | B0 | 20696 | 0.0161 | 0.0360 | 0.0071 | -0.0199 | -2.81 | 1.0000 | 0.0099 | EXPLORATORY |
| volume_trend_accumulation | B1 | 20635 | 0.0085 | 0.0497 | 0.0077 | -0.0412 | -5.37 | 1.0000 | 0.0099 | EXPLORATORY |
| volume_trend_accumulation | B2 | 20633 | 0.0554 | 0.1073 | 0.0103 | -0.0519 | -5.05 | 1.0000 | 0.0099 | EXPLORATORY |
| volume_trend_accumulation | B3 | 20750 | -0.0095 | 0.0184 | 0.0075 | -0.0280 | -3.73 | 1.0000 | 0.0099 | EXPLORATORY |
| volume_trend_accumulation | B4 | 20536 | 0.0809 | 0.1164 | 0.0099 | -0.0355 | -3.59 | 1.0000 | 0.0099 | EXPLORATORY |

---

## Evidence hierarchy

```
FWD-v0.1 forward journal          ← only confirmatory evidence; kill rule lives here
  ↑
D-73 execution model              ← makes forward fills honest
  ↑
D-70 honest templates             ← makes backtest mechanics believable
  ↑
D-71 replay / H-04 what-ifs       ← exploratory; hypotheses only
  ↑
D-61 (invalid)                    ← do not cite
```

Replay and what-if rows are stored in separate tables and never feed the
scorecard. A backtest can suggest a change; only the forward sample can justify
keeping it.

---

## Hypotheses carried into the forward review

These are the questions the sample is designed to inform. They were fixed on
2026-10-19 (review file) and are not new.

| ID | Hypothesis | Falsified if | Review item |
|---|---|---|---|
| R-A | The static exit leaves R on the table because T1 is far and there is no trail | MFE ≈ realized R across closed trades | A |
| R-B | The choppy menu is mismatched; mean reversion is benched | Forward choppy trades are not worse than neutral/trend | B |
| R-C | Screen edges are regime-specific, not universal | A screen is consistently positive across regimes | C |
| R-D | The gate adds selection value | Rejected candidates outperform accepted ones | D |

Current directional evidence: R-A is supported by one trade (CRS +3.72R MFE →
−1.00R realized), which is an anecdote, not a sample. R-B/R-C are supported only
by the replay. R-D has no forward counterfactual yet.

---

## Rules for the next entry

1. Write the question and the metric **before** running the test.
2. Change one thing at a time; keep the rest of the configuration fixed.
3. Record n, window, universe, costs and artifact path.
4. Label it exploratory unless it is an out-of-sample forward test.
5. If it changes a live decision, it is not an experiment — it is a new sample.
6. Do not re-run a failed what-if with a new window until it passes; that is
   fitting, not testing.

### Entry template

```markdown
| H-XX | YYYY-MM-DD | <name> | Exploratory / Confirmatory / Measurement | <n> | <headline> | <status> |
```

Attach: question, design, result, what it supports, what it does not support,
artifact path, and the decision it does (not) justify.

---

## Change log

| Date | Change |
|---|---|
| 2026-10-28 | Created; consolidated D-61/D-70/D-71/what-ifs/D-73/D-74 and registered FWD-v0.1 |
| 2026-11-11 | Backfilled H-09 (D-78 replay) and added H-10 (D-79 research baseline) as **invalid as recorded** (mixed cache panel + stranded-position equity bug); see D-79 |
| 2026-11-11 | Replaced H-10 with the **D-80 clean re-run** on one consistent 2020-2023 panel (cache + equity defects fixed); D-79 row retained as audit trail, superseded; see D-80 |
| 2026-11-12 | Replaced H-10 with the **D-81 v2 re-run** on 2015-2026 (no-look-ahead sizing, forward-filled marking, matched-random control, one-sided p-value); D-80 2020-2023 result retained as superseded history; 13 old artifacts quarantined under `research/invalid_20261110/` |
| 2026-11-13 | Added H-11 (D-82 v3 re-run: no same-day recycling, masked indicator warm-up, one evaluation window, daily-equity Sharpe, calendar CAGR, block-bootstrap CI, drawdown breach relabelled REVIEW, control eligibility); D-81 row retained as superseded; four new `*_20261113_*.json` artifacts |
| 2026-11-16 | Added the H-11 same-day-recycling ablation (four `*_20261116_*_recycle_on.json` runs, `dirty = false` at `7628660`) and refreshed `DIAGNOSTICS.md`; H-11 verdict unchanged |
| 2026-11-17 | Added H-12 (D-83 v4 re-run: headline expectancy and p-value averaged over 20 seeds 42..61 on identical signals, `p_values_seed_avg`, seed-mean report columns, 103 tests) and marked H-11 **superseded for the headline**; the D-82 engine contract and artifacts stand |
| 2026-11-17 | Added H-13 (E1 event study: `backend/app/research/events.py`, `scripts/research_event_study.py`, 6 tests, `EVENT_STUDY.md` + JSON, commit `687df51`); 20 setup x horizon cells, all EXPLORATORY and not pre-registered |
| 2026-11-17 | Added H-14 (E2 exit study: `backend/app/research/exit_study.py`, `scripts/research_exit_study.py`, 6 tests, `EXIT_STUDY.md` + JSON, commit `62abbef`); 20 setup x variant cells, all EXPLORATORY and not pre-registered |
| 2026-11-17 | E3 documentation only: recorded D-84, added the trial ledger (E1 20 cells, E2 20 cells) and added `docs/backtests/research/PREREGISTRATION_TEMPLATE.md` for future runs; no code, test, workflow or artifact change |
