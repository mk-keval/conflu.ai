# Research Baseline Report

- Run date: 2026-11-17 11:01
- Git commit: `3bfb68c`
- Window: 2015-01-01 -> 2026-11-17
- Symbols used: 501
- Dropped symbols: 2
- Costs: 15.0 bps per side
- Exit rules: stop 2.0 ATR, target 3.0 ATR, max hold 15 bars
- Portfolio rules: start equity 100000.0, risk 0.5%/trade, max 8 positions, max position 20.0% of equity

> **Universe = today's S&P 500 members. Survivorship bias flatters old results. In-sample, no walk-forward. Not evidence of a live edge.**

## Main table

| Setup | n | Win rate | Avg win R | Avg loss R | Expectancy net | Expectancy (mean of 20 seeds) | 95% CI (iid) | 95% CI (block) | Expectancy gross | PF | CAGR | Max DD | Reconciliation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| breakout_52week | 1686 | 48.3% | 1.085 | -0.959 | 0.028 | 0.028 | [-0.026, 0.083] | [-0.049, 0.105] | 0.100 | 1.06 | 1.3% | -22.0% | PASS |
| low_vol_setup | 1747 | 48.8% | 1.106 | -1.006 | 0.024 | 0.011 | [-0.029, 0.077] | [-0.065, 0.113] | 0.116 | 1.05 | 1.1% | -33.2% | PASS |
| statistical_mean_reversion | 1677 | 50.4% | 1.017 | -0.919 | 0.057 | 0.017 | [0.002, 0.110] | [-0.016, 0.137] | 0.118 | 1.12 | 2.9% | -23.4% | PASS |
| volume_trend_accumulation | 2147 | 47.0% | 1.091 | -0.982 | -0.007 | 0.004 | [-0.056, 0.042] | [-0.080, 0.065] | 0.066 | 0.99 | -0.9% | -35.6% | PASS |

## Per-year tables

### breakout_52week

| Year | n | Expectancy net | PF |
|---|---|---|---|
| 2016 | 126 | 0.064 | 1.14 |
| 2017 | 180 | 0.177 | 1.42 |
| 2018 | 155 | -0.139 | 0.77 |
| 2019 | 145 | -0.015 | 0.97 |
| 2020 | 155 | -0.060 | 0.89 |
| 2021 | 174 | 0.048 | 1.10 |
| 2022 | 89 | 0.003 | 1.01 |
| 2023 | 138 | 0.115 | 1.27 |
| 2024 | 200 | -0.098 | 0.83 |
| 2025 | 169 | 0.124 | 1.28 |
| 2026 | 155 | 0.089 | 1.17 |

### low_vol_setup

| Year | n | Expectancy net | PF |
|---|---|---|---|
| 2016 | 172 | 0.074 | 1.15 |
| 2017 | 187 | 0.285 | 1.73 |
| 2018 | 171 | -0.088 | 0.84 |
| 2019 | 148 | 0.211 | 1.50 |
| 2020 | 120 | 0.057 | 1.11 |
| 2021 | 175 | 0.157 | 1.36 |
| 2022 | 106 | -0.288 | 0.58 |
| 2023 | 173 | -0.270 | 0.59 |
| 2024 | 189 | 0.262 | 1.60 |
| 2025 | 165 | -0.115 | 0.81 |
| 2026 | 141 | -0.195 | 0.67 |

### statistical_mean_reversion

| Year | n | Expectancy net | PF |
|---|---|---|---|
| 2016 | 148 | -0.064 | 0.88 |
| 2017 | 173 | 0.183 | 1.48 |
| 2018 | 180 | -0.076 | 0.85 |
| 2019 | 146 | 0.295 | 1.94 |
| 2020 | 116 | 0.114 | 1.23 |
| 2021 | 135 | 0.150 | 1.39 |
| 2022 | 150 | -0.054 | 0.89 |
| 2023 | 158 | 0.143 | 1.36 |
| 2024 | 163 | -0.046 | 0.91 |
| 2025 | 162 | -0.023 | 0.95 |
| 2026 | 146 | 0.045 | 1.09 |

### volume_trend_accumulation

| Year | n | Expectancy net | PF |
|---|---|---|---|
| 2016 | 192 | -0.010 | 0.98 |
| 2017 | 201 | 0.046 | 1.10 |
| 2018 | 218 | -0.134 | 0.77 |
| 2019 | 164 | 0.220 | 1.59 |
| 2020 | 191 | -0.061 | 0.89 |
| 2021 | 209 | 0.016 | 1.03 |
| 2022 | 188 | -0.228 | 0.64 |
| 2023 | 190 | -0.002 | 1.00 |
| 2024 | 214 | 0.041 | 1.08 |
| 2025 | 204 | -0.011 | 0.98 |
| 2026 | 176 | 0.090 | 1.18 |

## Control comparison

| Setup | Control runs | Control trades (mean) | Control expectancy (mean +/- std) | Strategy expectancy (seed 42) | Strategy seed mean | Gap vs control (strategy seed-mean - control mean) | Gap / control std | SE of means (shuffle + control mean only; not a test) | p (seed 42) | p (seed-averaged) |
|---|---|---|---|---|---|---|---|---|---|---|
| breakout_52week | 30 | 1664.2 | 0.036 +/- 0.027 | 0.028 | 0.028 | -0.008 | -0.28 | 0.006 | 0.6452 | 0.6452 |
| low_vol_setup | 30 | 1793.6 | 0.025 +/- 0.026 | 0.024 | 0.011 | -0.015 | -0.57 | 0.006 | 0.5484 | 0.7097 |
| statistical_mean_reversion | 30 | 1870.0 | 0.035 +/- 0.023 | 0.057 | 0.017 | -0.018 | -0.79 | 0.006 | 0.2258 | 0.8065 |
| volume_trend_accumulation | 30 | 2034.2 | 0.050 +/- 0.020 | -0.007 | 0.004 | -0.047 | -2.31 | 0.006 | 1.0000 | 1.0000 |

- **volume_trend_accumulation**: strategy underperforms matched control (informational)

The p-value is the fraction of matched-random controls that do at least as well as the real strategy (`mean(control >= real)`), with the finite-sample correction `(p_raw*n + 1)/(n + 1)`; it is never direction-flipped for negative results. The seed-averaged p-value applies the same formula to the mean of the strategy's per-seed expectancies (`p_values_seed_avg`).

## Sanity checks

### breakout_52week

- Reconciliation: PASS
- No trade enters on or before its signal: PASS
- Max bars held <= max_hold (15): PASS (max 15)
- Stop-gap share: 6.0%
- data_end trades: 0 (info)
- data-coverage early_end: 0
- random-path drawdown scale: 23.3%

### low_vol_setup

- Reconciliation: PASS
- No trade enters on or before its signal: PASS
- Max bars held <= max_hold (15): PASS (max 15)
- Stop-gap share: 5.6%
- data_end trades: 0 (info)
- data-coverage early_end: 0
- random-path drawdown scale: 23.8%

### statistical_mean_reversion

- Reconciliation: PASS
- No trade enters on or before its signal: PASS
- Max bars held <= max_hold (15): PASS (max 15)
- Stop-gap share: 5.4%
- data_end trades: 0 (info)
- data-coverage early_end: 0
- random-path drawdown scale: 22.1%

### volume_trend_accumulation

- Reconciliation: PASS
- No trade enters on or before its signal: PASS
- Max bars held <= max_hold (15): PASS (max 15)
- Stop-gap share: 5.7%
- data_end trades: 0 (info)
- data-coverage early_end: 0
- random-path drawdown scale: 26.2%

## Deviations

- Trade statistics exclude censored trades (`data_end` / `eod_censored`) and anything exiting before 2016-01-01 (2015 is warm-up).
- `expectancy_gross` and `expectancy_net` are per-trade R averages.
- The p-value metric is per-trade expectancy (`r_net_mean`), not R sum.
- The headline expectancy is the mean of the per-seed net expectancies (seeds 42..42+N-1 on identical signals); the other strategy columns describe seed 42, which is the primary artifact run.
- The matched-random control fires the same number of entries per day as the strategy, on random liquid symbols with valid indicators.
- Artifacts without `run_info` are ignored; older artifacts are quarantined in `invalid_20261110/`.
- The verdict rule uses the 95% month-block bootstrap CI lower bound (changed after seeing D-81 results); the iid CI is shown for reference only.
- The verdict rule uses the seed-averaged p-value (`p_values_seed_avg`, the strategy seed-mean vs the same controls), changed after seeing D-82 results; the seed-42 p-value is shown for comparison.
- The underperformance flag compares the gap with the spread of single matched-control runs (z < -2). With four setups tested, a family-wise threshold would be about z < -2.5; the flag is informational and is not corrected for multiple testing.
- The strategy's own sampling uncertainty is the month-block CI in the main table, which is far wider than the SE of means.
- A drawdown breach alone is labelled REVIEW, not SUSPECTED BUG: a -40% drawdown can be a legitimate outcome of the configured risk, not a code fault.
- CAGR uses elapsed calendar years from the equity curve, not `len(curve)/252`.

## Verdict

- **breakout_52week**: NO EVIDENCE OF EDGE
- **low_vol_setup**: NO EVIDENCE OF EDGE
- **statistical_mean_reversion**: NO EVIDENCE OF EDGE
- **volume_trend_accumulation**: NO EVIDENCE OF EDGE
