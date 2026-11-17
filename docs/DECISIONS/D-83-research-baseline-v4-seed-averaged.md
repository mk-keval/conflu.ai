# D-83: Research Baseline v4 - Seed-Averaged Headline and P-Value

**Date:** 2026-11-17
**Status:** Accepted and implemented. **The 2026-11-17 result tables recorded here supersede
the D-82 result tables for the headline expectancy and the p-value.** Every D-82 engine and
measurement guarantee (no same-day recycling, masked warm-up, one evaluation window,
daily-equity Sharpe, calendar CAGR, month-block bootstrap CI, `REVIEW` drawdown label,
eligible controls, clean-tree guard, research CI) stands and is still enforced.
**Branch:** `research/baseline-backtesting`
**Commits:** `3bfb68c` (code + tests), `8db1c25` (four v4 artifacts + regenerated
`BASELINE_REPORT.md`), plus this documentation commit (find it with
`git log --oneline -- docs/DECISIONS/D-83-*.md`). All four artifacts record
`run.code.revision = 3bfb68c` and `run.code.dirty = false`.
**Related:** D-82 (supersedes its headline numbers), D-81, D-80, H-12 in
[`docs/backtests/HYPOTHESIS_LOG.md`](../backtests/HYPOTHESIS_LOG.md),
[`BASELINE_REPORT.md`](../backtests/research/BASELINE_REPORT.md),
[`DIAGNOSTICS.md`](../backtests/research/DIAGNOSTICS.md),
[`ABLATION.md`](../backtests/research/ABLATION.md),
[`VALIDITY_NOTES.md`](../backtests/research/VALIDITY_NOTES.md).

## Context

D-82 made the engine realistic and put the strategy and all controls on one evaluation
window. Its baseline, like D-81's, took its headline from **one engine seed (42)**. That
seed does not change the signals: the four setups produce a fixed `signal` column, and the
seed only shuffles the order of same-date candidates when more than one competes for a
scarce portfolio slot. It nevertheless moves the measured expectancy, because different
candidates fill the eight slots and the cash.

The size of that sensitivity was already recorded in
[`DIAGNOSTICS.md`](../backtests/research/DIAGNOSTICS.md) section (a), a separate 20-seed
sweep by `scripts/research_diagnostics.py`:

| Setup | 20-seed mean of `r_net_mean` | Across-seed std | Min | Max |
|---|---|---|---|---|
| `breakout_52week` | +0.0308 | 0.0140 | +0.0092 | +0.0566 |
| `low_vol_setup` | +0.0073 | 0.0198 | -0.0293 | +0.0506 |
| `statistical_mean_reversion` | +0.0161 | 0.0188 | -0.0303 | +0.0524 |
| `volume_trend_accumulation` | +0.0089 | 0.0230 | -0.0458 | +0.0380 |

The D-82 v3 artifacts, whose headline was seed 42, recorded +0.0333 / +0.0280 / +0.0489 /
-0.0039 (breakout / low_vol / SMR / volume). The sweep's panel ends one day earlier
(2026-11-11 vs the artifacts' 2026-11-12), so the two columns are **not like-for-like**;
they are shown only because they were the measurements available before T10. The
same-run comparison is the one in the Results section below.

The same-day-recycling ablation
([`ABLATION.md`](../backtests/research/ABLATION.md)) also records across-seed std separate
from the D-81 -> D-82 move: the recycling flag accounts for +81.7% / +102.4% / +99.3% /
+32.5% of that move, i.e. the D-82 headline change was the recycling contract, not seed
noise. The seed spread is a separate, smaller source of variation.

## Decision

Adopt the following for every research baseline from v4 onward.

1. **The headline expectancy is the mean of N engine seeds.**
   `scripts/run_research_baseline.py` gains `--n-strategy-seeds` (default **20**). The
   strategy is run with seeds `42..42+N-1` on **identical signals**. The primary artifact
   (trades, equity, metrics, all account statistics) remains **seed 42**, so the artifact
   schema and every downstream consumer change only by addition.
2. **The sweep is recorded in the artifact.** `run_info.strategy_seeds` holds
   `{seeds, r_net_mean[], mean, std, se}`. `std` is the population standard deviation
   (`ddof=0`), matching `scripts/research_diagnostics.py`; `se = std / sqrt(N)`.
3. **The test p-value is seed-averaged.** `p_values_seed_avg` applies
   `compute_control_pvalues` to a copy of the metrics whose `r_net_mean` is the seed mean,
   against the same control runs, with the same formula, direction and correction as
   `p_values`. `p_values` (seed 42) is unchanged and kept for comparison.
4. **The report shows both.** The main table gains
   `Expectancy (mean of N seeds)`. The control table gains
   `Strategy seed mean`, `Gap vs control (strategy seed-mean - control mean)`,
   `Gap / control std = gap / control_std`, `SE of means (shuffle + control mean only; not
   a test) = sqrt(se_strategy^2 + control_std^2 / n_control)`, and `p (seed-averaged)`,
   while retaining `p (seed 42)`.
5. **The verdict uses the seed-averaged p-value.** No other verdict rule changes: the
   month-block bootstrap lower bound, the per-year profitability requirement and the
   drawdown `REVIEW` label are untouched. If the seed-mean gap is more than **2 control
   standard deviations** negative (`Gap / control std < -2.0`), the report prints
   `**<setup>**: strategy underperforms matched control (informational)`; that line does
   not change the verdict. The flag compares the gap to the spread of single
   matched-control runs, not to the SE of means: the SE covers only candidate-shuffle
   noise and the error of the control mean, and ignores which stocks the signals pick, so
   it overstated significance by roughly 4x. The SE stays in the table as a description.
6. **Old artifacts still render.** A missing `strategy_seeds` / `p_values_seed_avg` shows
   `n/a` and the verdict falls back to the seed-42 p-value.

## What changed

| # | Change | Commit | Regression test |
|---|---|---|---|
| 1 | `strategy_seed_summary` + `strategy_seed_r_net_mean` + `run_strategy_seeds`; the runner sweeps seeds and keeps seed 42 as the primary run. | `3bfb68c` | `test_strategy_seed_summary_reports_list_and_stats`, `test_run_strategy_seeds_on_synthetic_panel` |
| 2 | `run_info.strategy_seeds` written to the artifact. | `3bfb68c` | `test_artifact_contains_strategy_seeds` |
| 3 | `p_values_seed_avg` computed with `compute_control_pvalues` on the seed-mean metric and written to the artifact. | `3bfb68c` | `test_artifact_contains_strategy_seeds` |
| 4 | `--n-strategy-seeds` (default 20, validated `>= 1`). | `3bfb68c` | arg validation in `main`; CLI exercised by the smoke run and the four v4 runs |
| 5 | Report: seed-mean column, gap / SE / seed-averaged p columns, seed-averaged verdict, underperformance line, two new deviation notes. | `3bfb68c` | `test_main_table_renders_seed_mean_column`, `test_control_table_renders_gap_se_and_seed_averaged_p`, `test_underperformance_line_when_gap_below_two_se`, `test_no_underperformance_line_when_gap_is_inside_two_se`, `test_verdict_uses_seed_averaged_p_value`, `test_verdict_seed_average_can_remove_candidate` |
| 6 | Four v4 artifacts re-run at `3bfb68c` with defaults (`--end` = 2026-11-17, no recycling) and `BASELINE_REPORT.md` regenerated. | `8db1c25` | n/a (generated artifacts) |
| 7 | Underperformance flag corrected to `Gap / control std < -2.0`; `SE of gap` renamed `SE of means (shuffle + control mean only; not a test)`; `Gap / control std` column added; report regenerated from the existing four artifacts (no re-run). | this change (T11) | `test_control_table_renders_gap_se_and_seed_averaged_p`, `test_underperformance_line_when_gap_below_two_control_std`, `test_no_underperformance_line_when_gap_is_inside_two_control_std`, `test_old_se_rule_flags_but_control_std_rule_does_not` |

## Verification

| Check | Result |
|---|---|
| Research + report tests | **104 passed** (`test_research_{control,data,diagnostics,engine,indicators,metrics,runner,setups}.py` + `test_make_baseline_report.py`) after T11 added the old-rule-vs-new-rule test |
| `ruff check` (2 scripts + 2 test files) | clean |
| Smoke run | `--quick --n-strategy-seeds 2` exit 0; artifact carried both p-value sets and a 2-seed summary |
| Clean-tree guard | tree clean before each of the four runs; `dirty = false` in all four artifacts |
| Baseline runs | 4/4 exit 0, `Reconciliation: PASS` |
| Artifact provenance | revision `3bfb68c`; `allow_same_day_recycling = false`; `eval_start = "2016-01-01"`; requested 2015-01-01..2026-11-17 |
| Panel | actual `2015-01-02..2026-11-17`; 501 tradable; 2 dropped (KVUE 1 row, VYLR 34 rows) |
| Cache | span covering 2026-11-17; breakout downloaded 503 (2 failed), then the other three had 503 hits each |

## Results (valid for this panel and window)

Verbatim mechanical output of
[`BASELINE_REPORT.md`](../backtests/research/BASELINE_REPORT.md). Trade statistics exclude
censored trades and exits before 2016-01-01; account statistics include every trade.

### D-82 vs D-83

D-82 columns are the v3 artifacts (panel ends 2026-11-12, revision `7ed0135`); D-83
columns are the v4 artifacts (panel ends 2026-11-17, revision `3bfb68c`). The D-83
seed-42 and seed-mean columns come from the same run and are directly comparable; the
D-82/D-83 difference also carries five extra sessions of data.

| Setup | D-82 seed 42 | D-83 seed 42 | D-83 seed mean (std / se) | Control mean (std, n) | Gap (seed-mean - control) | SE of means (not a test) | Gap / control std | p (seed 42) | p (seed-averaged) | Verdict (verbatim) |
|---|---|---|---|---|---|---|---|---|---|---|
| `breakout_52week` | +0.0333 | +0.0277 | +0.0278 (0.0148 / 0.0033) | +0.0355 (0.0271, 30) | -0.0077 | 0.0060 | -0.28 | 0.6452 | 0.6452 | NO EVIDENCE OF EDGE |
| `low_vol_setup` | +0.0280 | +0.0243 | +0.0107 (0.0185 / 0.0041) | +0.0253 (0.0257, 30) | -0.0146 | 0.0062 | -0.57 | 0.5484 | 0.7097 | NO EVIDENCE OF EDGE |
| `statistical_mean_reversion` | +0.0489 | +0.0566 | +0.0167 (0.0183 / 0.0041) | +0.0349 (0.0231, 30) | -0.0182 | 0.0059 | -0.79 | 0.2258 | 0.8065 | NO EVIDENCE OF EDGE |
| `volume_trend_accumulation` | -0.0039 | -0.0069 | +0.0036 (0.0213 / 0.0048) | +0.0502 (0.0201, 30) | -0.0466 | 0.0060 | -2.31 | 1.0000 | 1.0000 | NO EVIDENCE OF EDGE |

Seed-42 vs seed-mean within the D-83 artifacts: breakout +0.0277 -> +0.0278, low_vol
+0.0243 -> +0.0107, SMR +0.0566 -> +0.0167, volume -0.0069 -> +0.0036. For low_vol, SMR and
volume the seed-42 number is above the 20-seed mean; for breakout the two are within
0.0001 R.

### Main table (verbatim)

| Setup | n | Win rate | Avg win R | Avg loss R | Expectancy net | Expectancy (mean of 20 seeds) | 95% CI (iid) | 95% CI (block) | Expectancy gross | PF | CAGR | Max DD | Reconciliation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| breakout_52week | 1686 | 48.3% | 1.085 | -0.959 | 0.028 | 0.028 | [-0.026, 0.083] | [-0.049, 0.105] | 0.100 | 1.06 | 1.3% | -22.0% | PASS |
| low_vol_setup | 1747 | 48.8% | 1.106 | -1.006 | 0.024 | 0.011 | [-0.029, 0.077] | [-0.065, 0.113] | 0.116 | 1.05 | 1.1% | -33.2% | PASS |
| statistical_mean_reversion | 1677 | 50.4% | 1.017 | -0.919 | 0.057 | 0.017 | [0.002, 0.110] | [-0.016, 0.137] | 0.118 | 1.12 | 2.9% | -23.4% | PASS |
| volume_trend_accumulation | 2147 | 47.0% | 1.091 | -0.982 | -0.007 | 0.004 | [-0.056, 0.042] | [-0.080, 0.065] | 0.066 | 0.99 | -0.9% | -35.6% | PASS |

### Shadow controls (verbatim from the report's artifacts)

Seed-averaged `permuted` / `shifted` p-values: 0.9091 / 0.3333 (breakout), 0.9091 / 0.6667
(low_vol), 0.7273 / 1.0000 (SMR), 1.0000 / 1.0000 (volume). Seed-42 shadows were
0.9091 / 0.3333, 0.8182 / 0.6667, 0.2727 / 1.0000, 1.0000 / 1.0000. Floors at 10 and 2
runs are 0.091 and 0.333.

### Underperformance lines

Under the corrected rule (`Gap / control std < -2.0`), the report prints the informational
line for `volume_trend_accumulation` only, and not for `breakout_52week`,
`low_vol_setup` or `statistical_mean_reversion`:

- **volume_trend_accumulation**: strategy underperforms matched control (informational)

The originally published D-83 report used `gap < -2 * SE_of_gap`, with
`SE_of_gap = sqrt(se_strategy^2 + control_std^2 / n_control)`; that rule flagged `low_vol_setup`,
`statistical_mean_reversion` and `volume_trend_accumulation`. **The SE-based flag was
replaced because it ignored selection variability**: the SE covers only candidate-shuffle
noise and the error of the control mean, not which stocks the signals pick, so it
overstated significance by roughly 4x. The table now compares the gap to the spread of
single matched-control runs (`Gap / control std`), and the SE column is kept only as a
description of the two means.

| Flag rule | breakout | low_vol | SMR | volume | Lines printed |
|---|---|---|---|---|---|
| Old: `gap < -2 SE_of_gap` | -1.30 SE | -2.33 SE | -3.09 SE | -7.74 SE | low_vol, SMR, volume |
| New: `Gap / control std < -2.0` | -0.28 | -0.57 | -0.79 | -2.31 | volume only |

Only `volume_trend_accumulation` remains flagged; `low_vol_setup` and
`statistical_mean_reversion` dropped. `BASELINE_REPORT.md` was regenerated from the same
four artifacts (no baseline re-run); p-values and verdicts are unchanged.

## Deviations from the pre-registered plan

- **The headline and p-value rule was changed after seeing D-82 results.** D-82's
  headline was seed 42. The seed-averaged headline, the gap/SE columns and the
  seed-averaged verdict were introduced in T10 after the D-82 tables and the 20-seed
  sweep in `DIAGNOSTICS.md` had been read. A second number that is chosen after seeing the
  first is not a pre-registered test, so these results are labelled exploratory and do not
  enter any pass bar, kill rule or scorecard.
- **The underperformance flag compares the gap with the spread of single matched-control
  runs (z < -2).** With four setups tested, a family-wise threshold would be about
  z < -2.5; the flag is informational and is not corrected for multiple testing.
- **The strategy's own sampling uncertainty is the month-block CI in the main table**,
  which is far wider than the SE of means.
- **The four v4 runs used the default `--end` (2026-11-17), not the D-82 end date.** The
  panel therefore carries five more sessions (2026-11-13..2026-11-17) than the D-82
  artifacts. The D-82/D-83 columns are not a controlled one-variable comparison; the
  within-run seed-42 vs seed-mean columns are.
- **The primary artifact is still seed 42.** The sweep does not replace the trades or the
  equity curve; the account columns, CIs, per-year tables and sanity checks all describe
  seed 42. A seed-mean CAGR or drawdown is not recorded.
- **`p_values_seed_avg` treats the seed mean as one realization.** The control p-value
  formula is applied to the seed mean as if it were a single strategy value. The seed
  standard error is reported separately through `SE of means (shuffle + control mean only;
  not a test)`; it is not folded into the p-value.
- **The old-artifact path is fallback only.** Artifacts without `strategy_seeds` render
  `n/a` in the seed columns and use the seed-42 p-value for the verdict. The D-81/D-82
  artifacts are unchanged; the report is regenerated from the newest artifact per setup.
- **`--n-strategy-seeds` is not free.** Each run is N full portfolio passes over the same
  cached panel. The v4 runs used the default 20; the flag is recorded via `run_info`, and
  a future report showing a different N will label the column with that N.
- **`std` is population std (`ddof=0`).** This matches `research_diagnostics.py` so the
  v3 sweep and the v4 sweep use one definition; it is not the sample std (`ddof=1`) used
  by the daily-equity Sharpe.

## What this does not settle

- **Survivorship.** The universe is today's S&P 500 membership. Names that were delisted
  or removed are absent, which flatters historical results for every setup and control.
- **No walk-forward, no holdout.** Every number is in-sample on one panel. A seed average
  reduces one source of run-to-run variation; it does not create an out-of-sample test.
- **Research setups are not the deployed templates.** These four setups are standalone
  research implementations; they differ from the deployed screens' exits, gates and
  position rules (D-70/D-77). A result here is not a verdict on deployed behavior.
- **The control pool is all eligible symbols.** The matched-random control draws from the
  full eligible universe, not from the setup's own candidate pool or sector mix, so it is
  not a size- and sector-matched benchmark.
- **The matched control's p-value floor is 0.032 with 30 runs.** Clearing p <= 0.05
  requires the strategy to beat essentially all 30 control draws.
- **Seed averaging is not signal robustness.** The sweep holds the signals fixed, so it
  measures slot-allocation sensitivity only. It says nothing about parameter sensitivity,
  data revisions or regime change.

## Consequences

- Every future baseline run records a 20-seed summary and a seed-averaged p-value by
  default; `--n-strategy-seeds 1` reproduces a single-seed run if needed.
- The report's headline and verdict now use the seed-averaged numbers. A reader comparing
  a v4 report to D-82 must use the new columns; the seed-42 column is retained and labelled.
- `BASELINE_REPORT.md` is a pure function of the newest artifact per setup, so regenerating
  it after a future run changes the headline without touching this record.
- The D-82 decision record carries a banner pointing here for the headline; its engine
  contract, tests and guarantees are unchanged.

## Alternatives considered

- **Keep seed 42 and report seed std as an error bar.** Rejected: a single-seed headline
  remains one draw, and the p-value would still test that draw.
- **Average the p-values across seeds.** Rejected: p-values from the same controls under
  different seeds are not independent; averaging them has no clean null distribution.
- **Use the minimum or maximum seed.** Rejected: both are selection on the outcome.
- **Randomize the seed per run and publish whichever run finished.** Rejected: not
  reproducible, and it silently changes the artifact identity.
- **Re-run the controls for every strategy seed.** Rejected for cost and because the
  existing 30 control runs already define the null; it remains a possible follow-up.

## Follow-ups

1. Record the seed-mean CAGR / max drawdown if a future decision needs account statistics
   that are not seed-42.
2. If a setup ever clears the seed-averaged p-value, re-run it with more control draws
   (the 30-run floor is 0.032) before treating it as a candidate.
3. Keep the seed sweep and DIAGNOSTICS section (a) in sync: both use seeds 42..61 and
   population std, but DIAGNOSTICS runs its own panel and is not artifact-derived.
4. Fold the seed-mean into `VALIDITY_NOTES.md` if the research/deployed comparison is
   revisited.
