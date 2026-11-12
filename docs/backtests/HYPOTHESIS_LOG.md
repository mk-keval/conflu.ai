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
| H-10 | 2026-11-12 | D-81 research baseline v2: 4 setups vs matched-random/permuted/shifted controls | Exploratory (in-sample, 2015-2026) | 1876 / 1982 / 1860 / 2373 closed trades | No setup beat the matched control (p 0.61-0.94); mechanical verdicts NO EVIDENCE OF EDGE for `breakout_52week`, `statistical_mean_reversion`, `volume_trend_accumulation`; `low_vol_setup` flagged SUSPECTED BUG (max DD -43.0% vs -40% guard) | **Exploratory** — valid for one 2015-2026 panel; never the scorecard, pass bar or kill rule. Supersedes the D-80 2020-2023 row |

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
