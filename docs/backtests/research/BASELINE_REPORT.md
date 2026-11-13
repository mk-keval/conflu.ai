# Research Baseline Report

- Run date: 2026-11-13 09:50
- Git commit: `7ed0135`
- Window: 2015-01-01 -> 2026-11-13
- Symbols used: 501
- Dropped symbols: 2
- Costs: 15.0 bps per side
- Exit rules: stop 2.0 ATR, target 3.0 ATR, max hold 15 bars
- Portfolio rules: start equity 100000.0, risk 0.5%/trade, max 8 positions, max position 20.0% of equity

> **Universe = today's S&P 500 members. Survivorship bias flatters old results. In-sample, no walk-forward. Not evidence of a live edge.**

## Main table

| Setup | n | Win rate | Avg win R | Avg loss R | Expectancy net | 95% CI (iid) | 95% CI (block) | Expectancy gross | PF | CAGR | Max DD | Reconciliation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| breakout_52week | 1684 | 48.6% | 1.084 | -0.959 | 0.033 | [-0.022, 0.087] | [-0.044, 0.112] | 0.106 | 1.07 | 1.5% | -21.1% | PASS |
| low_vol_setup | 1746 | 48.4% | 1.121 | -0.998 | 0.028 | [-0.027, 0.084] | [-0.061, 0.120] | 0.119 | 1.05 | 1.6% | -31.6% | PASS |
| statistical_mean_reversion | 1680 | 50.1% | 1.015 | -0.920 | 0.049 | [-0.003, 0.099] | [-0.027, 0.130] | 0.111 | 1.11 | 2.4% | -23.4% | PASS |
| volume_trend_accumulation | 2120 | 47.0% | 1.088 | -0.973 | -0.004 | [-0.053, 0.044] | [-0.076, 0.069] | 0.068 | 0.99 | -0.6% | -35.6% | PASS |

## Per-year tables

### breakout_52week

| Year | n | Expectancy net | PF |
|---|---|---|---|
| 2016 | 126 | 0.064 | 1.14 |
| 2017 | 180 | 0.159 | 1.38 |
| 2018 | 153 | -0.109 | 0.81 |
| 2019 | 144 | 0.009 | 1.02 |
| 2020 | 155 | -0.060 | 0.89 |
| 2021 | 174 | 0.065 | 1.14 |
| 2022 | 89 | 0.003 | 1.01 |
| 2023 | 139 | 0.125 | 1.29 |
| 2024 | 200 | -0.098 | 0.83 |
| 2025 | 169 | 0.124 | 1.28 |
| 2026 | 155 | 0.089 | 1.17 |

### low_vol_setup

| Year | n | Expectancy net | PF |
|---|---|---|---|
| 2016 | 175 | 0.050 | 1.10 |
| 2017 | 179 | 0.258 | 1.65 |
| 2018 | 172 | -0.132 | 0.77 |
| 2019 | 155 | 0.286 | 1.70 |
| 2020 | 121 | 0.088 | 1.18 |
| 2021 | 176 | 0.185 | 1.44 |
| 2022 | 105 | -0.280 | 0.59 |
| 2023 | 173 | -0.284 | 0.57 |
| 2024 | 185 | 0.293 | 1.68 |
| 2025 | 165 | -0.115 | 0.81 |
| 2026 | 140 | -0.197 | 0.67 |

### statistical_mean_reversion

| Year | n | Expectancy net | PF |
|---|---|---|---|
| 2016 | 148 | -0.064 | 0.88 |
| 2017 | 173 | 0.183 | 1.48 |
| 2018 | 184 | -0.145 | 0.74 |
| 2019 | 146 | 0.300 | 1.97 |
| 2020 | 116 | 0.114 | 1.23 |
| 2021 | 135 | 0.150 | 1.39 |
| 2022 | 150 | -0.054 | 0.89 |
| 2023 | 158 | 0.143 | 1.36 |
| 2024 | 163 | -0.046 | 0.91 |
| 2025 | 162 | -0.023 | 0.95 |
| 2026 | 145 | 0.041 | 1.08 |

### volume_trend_accumulation

| Year | n | Expectancy net | PF |
|---|---|---|---|
| 2016 | 190 | 0.018 | 1.04 |
| 2017 | 192 | 0.096 | 1.21 |
| 2018 | 214 | -0.124 | 0.79 |
| 2019 | 161 | 0.173 | 1.45 |
| 2020 | 191 | -0.061 | 0.89 |
| 2021 | 208 | 0.021 | 1.04 |
| 2022 | 189 | -0.279 | 0.57 |
| 2023 | 184 | 0.074 | 1.16 |
| 2024 | 215 | 0.055 | 1.10 |
| 2025 | 204 | -0.072 | 0.87 |
| 2026 | 172 | 0.102 | 1.22 |

## Control comparison

| Setup | Control runs | Control trades (mean) | Control expectancy (mean +/- std) | Strategy expectancy | p (matched_random) |
|---|---|---|---|---|---|
| breakout_52week | 30 | 1667.7 | 0.045 +/- 0.028 | 0.033 | 0.6452 |
| low_vol_setup | 30 | 1783.2 | 0.022 +/- 0.022 | 0.028 | 0.3871 |
| statistical_mean_reversion | 30 | 1870.1 | 0.035 +/- 0.023 | 0.049 | 0.2903 |
| volume_trend_accumulation | 30 | 2042.1 | 0.049 +/- 0.021 | -0.004 | 1.0000 |

The p-value is the fraction of matched-random controls that do at least as well as the real strategy (`mean(control >= real)`), with the finite-sample correction `(p_raw*n + 1)/(n + 1)`; it is never direction-flipped for negative results.

## Sanity checks

### breakout_52week

- Reconciliation: PASS
- No trade enters on or before its signal: PASS
- Max bars held <= max_hold (15): PASS (max 15)
- Stop-gap share: 6.1%
- data_end trades: 0 (info)
- data-coverage early_end: 0
- random-path drawdown scale: 23.3%

### low_vol_setup

- Reconciliation: PASS
- No trade enters on or before its signal: PASS
- Max bars held <= max_hold (15): PASS (max 15)
- Stop-gap share: 5.2%
- data_end trades: 0 (info)
- data-coverage early_end: 0
- random-path drawdown scale: 24.1%

### statistical_mean_reversion

- Reconciliation: PASS
- No trade enters on or before its signal: PASS
- Max bars held <= max_hold (15): PASS (max 15)
- Stop-gap share: 5.6%
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
- random-path drawdown scale: 25.9%

## Deviations

- Trade statistics exclude censored trades (`data_end` / `eod_censored`) and anything exiting before 2016-01-01 (2015 is warm-up).
- `expectancy_gross` and `expectancy_net` are per-trade R averages.
- The p-value metric is per-trade expectancy (`r_net_mean`), not R sum.
- The matched-random control fires the same number of entries per day as the strategy, on random liquid symbols with valid indicators.
- Artifacts without `run_info` are ignored; older artifacts are quarantined in `invalid_20261110/`.
- The verdict rule uses the 95% month-block bootstrap CI lower bound (changed after seeing D-81 results); the iid CI is shown for reference only.
- A drawdown breach alone is labelled REVIEW, not SUSPECTED BUG: a -40% drawdown can be a legitimate outcome of the configured risk, not a code fault.
- CAGR uses elapsed calendar years from the equity curve, not `len(curve)/252`.

## Verdict

- **breakout_52week**: NO EVIDENCE OF EDGE
- **low_vol_setup**: NO EVIDENCE OF EDGE
- **statistical_mean_reversion**: NO EVIDENCE OF EDGE
- **volume_trend_accumulation**: NO EVIDENCE OF EDGE
