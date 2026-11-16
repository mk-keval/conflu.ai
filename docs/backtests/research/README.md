# Research Backtest Artifacts

**Status: the `*_20261113_*.json` files are valid for the panel and window described
below — one run of the current S&P 500 snapshot over 2015-01-01..2026-11-13 under the D-82
engine contract.** They are **exploratory**: no result here enters the D-75 pass bar, the
kill rule, the forward scorecard or any FWD-v0.2 verdict. The generated summary is
[`BASELINE_REPORT.md`](BASELINE_REPORT.md). See
[D-82](../../DECISIONS/D-82-research-baseline-v3-engine-realism.md),
[D-81](../../DECISIONS/D-81-research-baseline-v2-honesty-and-controls.md),
[D-80](../../DECISIONS/D-80-research-baseline-remediation.md) and
[H-11](../HYPOTHESIS_LOG.md).

Validity caveats for these setups — research conditions vs deployed YAML, setup naming, control design and known simplifications — are in [`VALIDITY_NOTES.md`](VALIDITY_NOTES.md).

Sensitivity studies (seed, cost, data integrity, exit mix) are in
[`DIAGNOSTICS.md`](DIAGNOSTICS.md); they were refreshed on 2026-11-16 under the D-82 engine
(commit `7628660`), with artifact-derived columns taken from the same-day-recycling runs.
The same-day-recycling ablation (D-82 default vs recycle on) is in
[`ABLATION.md`](ABLATION.md).

The **D-81** `*_20261111_21*.json` artifacts are **superseded**. They stay in this folder
as the previous baseline and must not be cited as current. The 13 older D-79/D-80 artifacts
are quarantined in [`invalid_20261110/`](invalid_20261110/) and must not be cited at all.

## Provenance of the current files

| Item | Value |
|---|---|
| Harness | `scripts/run_research_baseline.py` + `backend/app/research` |
| Report generator | `scripts/make_baseline_report.py` (standard library only) |
| Diagnostics | `scripts/research_diagnostics.py` (read-only; refreshed 2026-11-16, see above) |
| Code revision | `7ed0135` in all four; the first run records `run.code.dirty = false`, the next three `dirty = true` (the preceding run's untracked artifact; no source difference) |
| Window | requested 2015-01-01..2026-11-13; actual 2015-01-02..2026-11-12 |
| Universe | `config/replay_universe_sp500.txt` (current snapshot), SHA-256 `a53242f2...9a729080` |
| Symbols | 501 tradable; 503 loaded with SPY + ^VIX; 2 dropped (KVUE: 1 row, VYLR: 31 rows) |
| Coverage | `panel.n_symbols_ending_early = 0`; 37 symbols start late (recent listings) |
| Cache | span-keyed `.cache/research` (`2015-01-01__2026-11-13`); 503 downloaded once (2 failures), then 503 hits per setup |
| Controls | matched-random 30, permuted dates 10, time-shifted +20..+60 bars 2, unmatched random 0 |
| Exits | 2.0 ATR stop, 3.0 ATR target, 15-bar time stop |
| Portfolio | $100,000 start, 0.5% risk, 8 positions, 20% notional cap, 15 bps/side, `allow_same_day_recycling = false` |
| Evaluation window | `run_info.eval_start = "2016-01-01"` — uncensored trades with exit date >= that date |
| Evidence label | `exploratory_research` |

Files:

```
statistical_mean_reversion_20261113_093317.json
breakout_52week_20261113_093833.json
low_vol_setup_20261113_094423.json
volume_trend_accumulation_20261113_095014.json
```

## What the files are

Each artifact carries the D-80 `run` block and a D-81 `run_info` block:

| Field | Meaning |
|---|---|
| `setup`, `timestamp` | Setup name and run start |
| `run` | Requested vs actual span, panel coverage, universe path + SHA, cache counters, rules, control seeds, equity invariant, code revision, library versions, declared limitations |
| `run_info` | Requested `start`/`end`, `universe_path`, `n_symbols_used`, `dropped`, exit and portfolio rules (including `allow_same_day_recycling`), control budget, short `git_commit`, `quick` flag, **`eval_start`** |
| `metrics` | Trade-level and equity-curve metrics (**`win_rate` is a fraction**, e.g. `0.486`; `total_return_pct`, `cagr` and `max_drawdown_pct` are percentages). `sharpe`/`sortino` are **daily-equity** ratios; `cagr` uses **calendar years** |
| `trades` | Every trade with signal/entry/exit dates, R gross/net, P&L, bars held, exit reason and `censored` flag |
| `equity_curve` | Daily marked equity (forward-filled marks; final point is cash) |
| `control_summary` | Per-control `n_runs`, `n_trades_mean`, `r_net_mean_mean`, `r_net_mean_std`, R-sum and Sharpe distributions |
| `p_values` | One-sided p-values on `r_net_mean` (matched/permuted/shifted) |
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

Trade statistics use `trades_in_window`; account statistics include every trade.

| Setup | n | Win rate | Avg win R | Avg loss R | Expectancy net | 95% CI (iid) | 95% CI (block) | Expectancy gross | PF | CAGR | Max DD | Reconciliation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| breakout_52week | 1684 | 48.6% | 1.084 | -0.959 | 0.033 | [-0.022, 0.087] | [-0.044, 0.112] | 0.106 | 1.07 | 1.5% | -21.1% | PASS |
| low_vol_setup | 1746 | 48.4% | 1.121 | -0.998 | 0.028 | [-0.027, 0.084] | [-0.061, 0.120] | 0.119 | 1.05 | 1.6% | -31.6% | PASS |
| statistical_mean_reversion | 1680 | 50.1% | 1.015 | -0.920 | 0.049 | [-0.003, 0.099] | [-0.027, 0.130] | 0.111 | 1.11 | 2.4% | -23.4% | PASS |
| volume_trend_accumulation | 2120 | 47.0% | 1.088 | -0.973 | -0.004 | [-0.053, 0.044] | [-0.076, 0.069] | 0.068 | 0.99 | -0.6% | -35.6% | PASS |

Matched-random control on per-trade expectancy (`r_net_mean`):

| Setup | Control runs | Control trades (mean) | Control expectancy (mean +/- std) | Strategy expectancy | p (matched_random) |
|---|---|---|---|---|---|
| breakout_52week | 30 | 1667.7 | 0.045 +/- 0.028 | 0.033 | 0.6452 |
| low_vol_setup | 30 | 1783.2 | 0.022 +/- 0.022 | 0.028 | 0.3871 |
| statistical_mean_reversion | 30 | 1870.1 | 0.035 +/- 0.023 | 0.049 | 0.2903 |
| volume_trend_accumulation | 30 | 2042.1 | 0.049 +/- 0.021 | -0.004 | 1.0000 |

Shadow controls (not used by the verdict): permuted p-values 1.0000 / 0.8182 / 0.2727 /
1.0000 and shifted 0.3333 / 0.6667 / 1.0000 / 1.0000 for breakout / low_vol / SMR / volume.

Mechanical verdicts:

- **breakout_52week**: NO EVIDENCE OF EDGE
- **low_vol_setup**: NO EVIDENCE OF EDGE
- **statistical_mean_reversion**: NO EVIDENCE OF EDGE
- **volume_trend_accumulation**: NO EVIDENCE OF EDGE

`low_vol_setup` is no longer flagged. Its D-81 flag was the report's -40% drawdown guard
(-43.0%), not a p-value. Under the D-82 engine its max drawdown is -31.6%, and a drawdown
breach alone would now print `REVIEW drawdown guard breached (not necessarily a bug)`.

### D-81 vs D-82

| Setup | n | Expectancy net | PF | Max DD | p (matched) |
|---|---|---|---|---|---|
| breakout_52week | 1876 → 1684 | -0.008 → 0.033 | 0.98 → 1.07 | -36.0% → -21.1% | 0.9355 → 0.6452 |
| low_vol_setup | 1982 → 1746 | 0.000 → 0.028 | 1.00 → 1.05 | -43.0% → -31.6% | 0.6774 → 0.3871 |
| statistical_mean_reversion | 1860 → 1680 | -0.001 → 0.049 | 1.00 → 1.11 | -35.2% → -23.4% | 0.6129 → 0.2903 |
| volume_trend_accumulation | 2373 → 2120 | 0.018 → -0.004 | 1.03 → 0.99 | -37.8% → -35.6% | 0.7742 → 1.0000 |

Fewer trades everywhere is the expected direction: masking removes early signals, and
no-recycling removes entries that were funded by the same day's exits.

## How to re-run

```bash
python scripts/run_research_baseline.py \
  --setup statistical_mean_reversion \
  --universe config/replay_universe_sp500.txt \
  --start 2015-01-01 --end 2026-11-13 \
  --cache-dir .cache/research \
  --output-dir docs/backtests/research \
  --n-matched 30 --n-random 0 --n-permuted 10 --n-shifted 2

python scripts/make_baseline_report.py
```

The runner **refuses to start on a dirty working tree** and points at `--allow-dirty`,
which records the dirt explicitly in `run.code.dirty`. Commit the harness before a run that
is meant to be citable. Defaults are `--start 2015-01-01` and `--end` = today.

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
- **The control p-values predate the control-eligibility fix.** The artifacts were produced
  at `7ed0135`; `1fcac93` made permutation and shift apply `eligible()`. The effect is
  strictly fewer ineligible control trades (a marginally tighter comparison). Re-running
  is a deliberate act, so the artifacts were not patched up.
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
