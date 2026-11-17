# Research Backtest Artifacts

**Status: the `*_20261117_*.json` files are the current baseline (v4).** They are one run of
the current S&P 500 snapshot over 2015-01-01..2026-11-17 under the D-82 engine contract, with
the D-83 seed-averaged headline and p-value (20 engine seeds, 42..61, on identical signals).
They are **exploratory**: no result here enters the D-75 pass bar, the kill rule, the
forward scorecard or any FWD-v0.2 verdict. The generated summary is
[`BASELINE_REPORT.md`](BASELINE_REPORT.md). See
[D-83](../../DECISIONS/D-83-research-baseline-v4-seed-averaged.md),
[D-82](../../DECISIONS/D-82-research-baseline-v3-engine-realism.md),
[D-81](../../DECISIONS/D-81-research-baseline-v2-honesty-and-controls.md),
[D-80](../../DECISIONS/D-80-research-baseline-remediation.md) and
[H-12](../HYPOTHESIS_LOG.md).

Validity caveats for these setups — research conditions vs deployed YAML, setup naming, control design and known simplifications — are in [`VALIDITY_NOTES.md`](VALIDITY_NOTES.md).

Sensitivity studies (seed, cost, data integrity, exit mix) are in
[`DIAGNOSTICS.md`](DIAGNOSTICS.md); they were refreshed on 2026-11-16 under the D-82 engine
(commit `7628660`), with artifact-derived columns taken from the same-day-recycling runs.
The same-day-recycling ablation (D-82 default vs recycle on) is in
[`ABLATION.md`](ABLATION.md).

The **D-82** `*_20261113_*.json` artifacts are **superseded for the headline** by D-83; they
remain valid for the D-82 engine contract and are kept as the previous baseline. The **D-81**
`*_20261111_21*.json` artifacts are **superseded**. The 13 older D-79/D-80 artifacts are
quarantined in [`invalid_20261110/`](invalid_20261110/) and must not be cited at all.

## Provenance of the current files

| Item | Value |
|---|---|
| Harness | `scripts/run_research_baseline.py` + `backend/app/research` |
| Report generator | `scripts/make_baseline_report.py` (standard library only) |
| Diagnostics | `scripts/research_diagnostics.py` (read-only; refreshed 2026-11-16, see above) |
| Code revision | `3bfb68c` in all four; `run.code.dirty = false` in all four |
| Window | requested 2015-01-01..2026-11-17; actual 2015-01-02..2026-11-17 |
| Universe | `config/replay_universe_sp500.txt` (current snapshot), SHA-256 `a53242f2...9a729080` |
| Symbols | 501 tradable; 503 loaded with SPY + ^VIX; 2 dropped (KVUE: 1 row, VYLR: 34 rows) |
| Coverage | `panel.n_symbols_ending_early = 0`; 37 symbols start late (recent listings) |
| Cache | span covering 2026-11-17; breakout downloaded 503 (2 failures), then 503 hits per setup |
| Controls | matched-random 30, permuted dates 10, time-shifted +20..+60 bars 2, unmatched random 0 |
| Exits | 2.0 ATR stop, 3.0 ATR target, 15-bar time stop |
| Portfolio | $100,000 start, 0.5% risk, 8 positions, 20% notional cap, 15 bps/side, `allow_same_day_recycling = false` |
| Strategy seeds | 20 seeds, 42..61, identical signals; seed 42 is the primary artifact run |
| Evaluation window | `run_info.eval_start = "2016-01-01"` — uncensored trades with exit date >= that date |
| Evidence label | `exploratory_research` |

Files:

```
breakout_52week_20261117_095332.json
low_vol_setup_20261117_100100.json
statistical_mean_reversion_20261117_100839.json
volume_trend_accumulation_20261117_101631.json
```

## What the files are

Each artifact carries the D-80 `run` block, a D-81/D-82 `run_info` block and the D-83
`strategy_seeds` / `p_values_seed_avg` additions:

| Field | Meaning |
|---|---|
| `setup`, `timestamp` | Setup name and run start |
| `run` | Requested vs actual span, panel coverage, universe path + SHA, cache counters, rules, control seeds, equity invariant, code revision, library versions, declared limitations |
| `run_info` | Requested `start`/`end`, `universe_path`, `n_symbols_used`, `dropped`, exit and portfolio rules (including `allow_same_day_recycling`), control budget, short `git_commit`, `quick` flag, **`eval_start`**, **`strategy_seeds`** |
| `run_info.strategy_seeds` | The D-83 seed sweep: `seeds`, per-seed `r_net_mean[]`, `mean`, `std` (population, `ddof=0`) and `se = std/sqrt(N)`. Absent in pre-D-83 artifacts |
| `metrics` | Trade-level and equity-curve metrics (**`win_rate` is a fraction**, e.g. `0.486`; `total_return_pct`, `cagr` and `max_drawdown_pct` are percentages). `sharpe`/`sortino` are **daily-equity** ratios; `cagr` uses **calendar years** |
| `trades` | Every trade with signal/entry/exit dates, R gross/net, P&L, bars held, exit reason and `censored` flag |
| `equity_curve` | Daily marked equity (forward-filled marks; final point is cash) |
| `control_summary` | Per-control `n_runs`, `n_trades_mean`, `r_net_mean_mean`, `r_net_mean_std`, R-sum and Sharpe distributions |
| `p_values` | One-sided p-values on `r_net_mean` for seed 42 (matched/permuted/shifted) |
| `p_values_seed_avg` | The same p-values computed on the **seed-mean** `r_net_mean` (D-83); the report's verdict uses this. Absent in pre-D-83 artifacts |
| `p_values_sharpe` | One-sided p-values on trade-R Sharpe (informational) |

`metrics.pnl_usd_sum` covers strategy exits only; `metrics.pnl_usd_all` includes the
forced `data_end` / `eod_censored` closes and reconciles with `final_equity`:
`final_equity == 100000 + pnl_usd_all`. Reconciliation is computed from **all** trades, so
the evaluation window cannot hide a cash break.

### The D-82 measurement contract

- **No same-day recycling.** An exit detected on date D is applied after D's entries are
  sized; a D exit cannot fund a D entry. `PortfolioRules.allow_same_day_recycling = True`
  restores the pre-D-82 behaviour for comparison and is recorded in the artifact.
- **Warm-up is real.** Every indicator is masked at its own window; `eligible()` requires
  `atr14` in addition to the other columns, so a setup or a control cannot fire on a
  partially formed bar.
- **One sample.** Trade statistics and every control family use `trades_in_window` —
  uncensored trades with `exit_date >= 2016-01-01`. Equity statistics use the full curve.
- **Honest ratios.** `sharpe` is `mean(daily equity return) / std(daily equity return,
  ddof=1) * sqrt(252)`; Sortino uses the RMS of negative daily returns; a flat curve
  returns 0. `cagr` uses elapsed calendar time.

### The D-83 seed-averaged headline

- **The headline is a seed average.** `--n-strategy-seeds` (default 20) runs the strategy
  under seeds `42..42+N-1` on the same signals. The engine seed only shuffles same-date
  candidates when they compete for a slot, so this measures slot-allocation sensitivity.
- **Seed 42 stays the primary run.** `trades`, `equity_curve`, `metrics`, the CIs, the
  per-year tables and the reconciliation are seed 42. The seed mean appears only in the
  report's `Expectancy (mean of N seeds)` column and in `run_info.strategy_seeds`.
- **Both p-values are kept.** `p_values` is seed 42; `p_values_seed_avg` applies the same
  control formula to the seed mean. The verdict uses `p_values_seed_avg` and falls back to
  `p_values` when the artifact predates D-83.
- **Gap and SE.** The control table reports
  `gap = seed_mean - control_mean` and
  `SE = sqrt(se_strategy^2 + control_std^2 / n_control)`. A gap more than 2 SE negative
  prints an informational underperformance line; it does not change the verdict.
- **`std` is population std (`ddof=0`)** to match `scripts/research_diagnostics.py`; the
  daily-equity Sharpe uses sample std (`ddof=1`).

### P-values

`p = mean(control >= real)` with the finite-sample correction `(p_raw*n + 1)/(n + 1)`.
The direction is **never** flipped for negative results: a losing strategy gets a p-value
near 1, not near 0. The matched-random control fires the same number of entries per day
as the strategy, on random symbols that pass `eligible()` on that date. Permutation and
time-shift also apply `eligible()`.

The 95% CI shown in the report is a **month-block bootstrap** (exit year-month resampled
with replacement, 2000 resamples, seed 42); the iid interval is shown for reference only.
The verdict requires the **block** lower bound to be positive.

## Headline result (mechanical, from `BASELINE_REPORT.md`)

Trade statistics use `trades_in_window`; account statistics include every trade. The
headline expectancy is the mean of 20 seeds; the other strategy columns describe seed 42.

| Setup | n | Win rate | Avg win R | Avg loss R | Expectancy net | Expectancy (mean of 20 seeds) | 95% CI (iid) | 95% CI (block) | Expectancy gross | PF | CAGR | Max DD | Reconciliation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| breakout_52week | 1686 | 48.3% | 1.085 | -0.959 | 0.028 | 0.028 | [-0.026, 0.083] | [-0.049, 0.105] | 0.100 | 1.06 | 1.3% | -22.0% | PASS |
| low_vol_setup | 1747 | 48.8% | 1.106 | -1.006 | 0.024 | 0.011 | [-0.029, 0.077] | [-0.065, 0.113] | 0.116 | 1.05 | 1.1% | -33.2% | PASS |
| statistical_mean_reversion | 1677 | 50.4% | 1.017 | -0.919 | 0.057 | 0.017 | [0.002, 0.110] | [-0.016, 0.137] | 0.118 | 1.12 | 2.9% | -23.4% | PASS |
| volume_trend_accumulation | 2147 | 47.0% | 1.091 | -0.982 | -0.007 | 0.004 | [-0.056, 0.042] | [-0.080, 0.065] | 0.066 | 0.99 | -0.9% | -35.6% | PASS |

Matched-random control on per-trade expectancy (`r_net_mean`):

| Setup | Control runs | Control trades (mean) | Control expectancy (mean +/- std) | Strategy expectancy (seed 42) | Strategy seed mean | Gap | SE of gap | p (seed 42) | p (seed-averaged) |
|---|---|---|---|---|---|---|---|---|---|
| breakout_52week | 30 | 1664.2 | 0.036 +/- 0.027 | 0.028 | 0.028 | -0.008 | 0.006 | 0.6452 | 0.6452 |
| low_vol_setup | 30 | 1793.6 | 0.025 +/- 0.026 | 0.024 | 0.011 | -0.015 | 0.006 | 0.5484 | 0.7097 |
| statistical_mean_reversion | 30 | 1870.0 | 0.035 +/- 0.023 | 0.057 | 0.017 | -0.018 | 0.006 | 0.2258 | 0.8065 |
| volume_trend_accumulation | 30 | 2034.2 | 0.050 +/- 0.020 | -0.007 | 0.004 | -0.047 | 0.006 | 1.0000 | 1.0000 |

`Gap` is the strategy seed mean minus the control mean; `SE of gap` is
`sqrt(se_strategy^2 + control_std^2 / 30)`. The p-value in the last column is computed on
the seed mean.

Shadow controls (not used by the verdict), seed-averaged: permuted p-values 0.9091 /
0.9091 / 0.7273 / 1.0000 and shifted 0.3333 / 0.6667 / 1.0000 / 1.0000 for breakout /
low_vol / SMR / volume. Seed-42 shadows were 0.9091 / 0.8182 / 0.2727 / 1.0000 and 0.3333 /
0.6667 / 1.0000 / 1.0000.

Mechanical verdicts:

- **breakout_52week**: NO EVIDENCE OF EDGE
- **low_vol_setup**: NO EVIDENCE OF EDGE
- **statistical_mean_reversion**: NO EVIDENCE OF EDGE
- **volume_trend_accumulation**: NO EVIDENCE OF EDGE

The report prints an informational underperformance line for `low_vol_setup`,
`statistical_mean_reversion` and `volume_trend_accumulation` (gap more than 2 SE negative),
not for `breakout_52week`. The line does not change the verdict.

`low_vol_setup` is not flagged. Its D-81 flag was the report's -40% drawdown guard
(-43.0%), not a p-value. Under the D-82 engine its D-83 max drawdown is -33.2%, and a
drawdown breach alone would print `REVIEW drawdown guard breached (not necessarily a bug)`.

### D-82 vs D-83

D-82 values are from the `*_20261113_*.json` artifacts (panel ends 2026-11-12, revision
`7ed0135`). The D-83 seed-42 and seed-mean columns come from the same run; the cross-version
difference also carries five extra sessions of data.

| Setup | D-82 seed 42 | D-83 seed 42 | D-83 seed mean (std) | Control mean | Gap | SE | p (seed-averaged) |
|---|---|---|---|---|---|---|---|
| breakout_52week | 0.033 | 0.028 | 0.028 (0.0148) | 0.036 | -0.008 | 0.006 | 0.6452 |
| low_vol_setup | 0.028 | 0.024 | 0.011 (0.0185) | 0.025 | -0.015 | 0.006 | 0.7097 |
| statistical_mean_reversion | 0.049 | 0.057 | 0.017 (0.0183) | 0.035 | -0.018 | 0.006 | 0.8065 |
| volume_trend_accumulation | -0.004 | -0.007 | 0.004 (0.0213) | 0.050 | -0.047 | 0.006 | 1.0000 |

For low_vol, SMR and volume the seed-42 expectancy is above the 20-seed mean; for breakout
the two differ by 0.0001 R. The full D-82 -> D-83 comparison and the post-hoc-rule deviation
are in [D-83](../../DECISIONS/D-83-research-baseline-v4-seed-averaged.md).

## How to re-run

```bash
python scripts/run_research_baseline.py \
  --setup statistical_mean_reversion \
  --universe config/replay_universe_sp500.txt \
  --start 2015-01-01 --end 2026-11-17 \
  --cache-dir .cache/research \
  --output-dir docs/backtests/research \
  --n-matched 30 --n-random 0 --n-permuted 10 --n-shifted 2 \
  --n-strategy-seeds 20

python scripts/make_baseline_report.py
```

The runner **refuses to start on a dirty working tree** and points at `--allow-dirty`,
which records the dirt explicitly in `run.code.dirty`. Commit the harness before a run that
is meant to be citable. Defaults are `--start 2015-01-01`, `--end` = today, and
`--n-strategy-seeds 20`; `--n-strategy-seeds 1` reproduces a single-seed headline.

The cache is keyed by `SYMBOL__{start}__{end}` with a manifest, so re-requesting the same
window is fast and cannot mix spans. The runner refuses to write when the actual panel is
more than 10 days short of the request (unless `--allow-partial-panel`), when more than 5%
of tradable symbols end early, when the equity check fails, or when the invariant does not
hold. A completed run always exits 0; significance is printed as `INFO:`.

Fast smoke run (40 symbols, 2019-2020, separate `.cache/research_quick`):

```bash
python scripts/run_research_baseline.py --quick-setup statistical_mean_reversion
```

CI: `.github/workflows/research.yml` runs the nine research/report test files and `ruff` on
`backend/app/research` plus the three research scripts on every push and pull request. It
does **not** run the baseline (that would download 500+ symbols and take ~12 minutes per
setup).

## Superseded files

- `docs/backtests/research/{setup}_20261113_*.json` - the D-82 (v3) baseline. Superseded for
  the headline expectancy and p-value by D-83; the D-82 engine contract and every guarantee
  stand. Kept as the previous baseline.

- `docs/backtests/research/{setup}_20261111_21*.json` — the D-81 baseline. Valid for the
  D-81 contract only; superseded for current use. Kept as the previous baseline.
- `docs/backtests/research/invalid_20261110/` — the 13 moved D-79/D-80 artifacts (the four
  `*_clean.json` files and the nine `*_20261110_*.json` files), produced before the D-80
  cache/data-end fixes and/or the D-81 sizing, marking, control and p-value fixes. Keep
  them as an audit trail; do not cite their returns, drawdowns, CAGR, volatility,
  alpha/beta or p-values. The quarantine [README](invalid_20261110/README.md) lists the
  defects.

## Known limitations

- **Survivorship:** the universe is the *current* index membership. Companies removed
  from the index are absent; recent listings start late and enter only from their first
  bar (37 names).
- **One window, in-sample.** 2015-2026 has no walk-forward split, holdout or
  pre-registered out-of-sample test. `NO EVIDENCE OF EDGE` is the absence of evidence in
  this panel, not proof that a setup cannot work.
- **Fixed research exits.** 2.0 ATR stop, 3.0 ATR target, 15-bar time stop — not the
  deployed template geometry (D-70/D-77). A weak result here does not retire a screen
  from the live mix.
- **The seed-averaged rule was chosen post hoc.** The 20-seed headline, the gap/SE columns
  and the seed-averaged verdict were introduced after the D-82 tables were read. They are
  exploratory, not a pre-registered test.
- **Seed averaging is not signal robustness.** The sweep holds the signals fixed, so it
  measures slot-allocation sensitivity only; it says nothing about parameter, data-revision
  or regime sensitivity.
- **The D-82 v3 control p-values predate the control-eligibility fix.** Those artifacts were
  produced at `7ed0135`; `1fcac93` made permutation and shift apply `eligible()`. The D-83
  v4 artifacts were produced at `3bfb68c`, after that fix, so this limitation does not apply
  to them.
- **Drawdown guard is blunt.** A -40% max drawdown now prints `REVIEW`, which is honest
  about "bad path, not necessarily a bug" but cannot distinguish a bad path from a risk
  setting that is wrong for the strategy.
- **Control floors.** With 30 matched runs the p-value floor is about 0.032; 10 permuted
  runs give 1/11 = 0.091; 2 shifted runs give 1/3 = 0.333. The shifted control is
  descriptive only and cannot establish superiority at p < 0.05.
- **No benchmark comparison in the report.** The generator records the account path but
  does not compute SPY buy-and-hold, so this folder makes no benchmark claim.
- **`DIAGNOSTICS.md` mixes two panels.** Refreshed on 2026-11-16: seed, cost and exit-mix
  sections use the script's default 2015-01-01..2026-11-11 panel, while its
  artifact-derived columns come from the `*_20261116_*_recycle_on.json` ablation runs. It is
  a sensitivity study, not a baseline table. The ablation comparison is in
  [`ABLATION.md`](ABLATION.md).
- **`^VIX` is downloaded** as a benchmark but is not used by any verdict or p-value.
