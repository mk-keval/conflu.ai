# Research Baseline Report

- Run date: 2026-11-12 09:30
- Git commit: `dcc9565`
- Window: 2015-01-01 -> 2026-11-11
- Symbols used: 501
- Dropped symbols: 2
- Costs: 15.0 bps per side
- Exit rules: stop 2.0 ATR, target 3.0 ATR, max hold 15 bars
- Portfolio rules: start equity 100000.0, risk 0.5%/trade, max 8 positions, max position 20.0% of equity

> **Universe = today's S&P 500 members. Survivorship bias flatters old results. In-sample, no walk-forward. Not evidence of a live edge.**

## Main table

| Setup | n | Win rate | Avg win R | Avg loss R | Expectancy net | 95% CI | Expectancy gross | PF | CAGR | Max DD | Reconciliation |
|---|---|---|---|---|---|---|---|---|---|---|---|
| breakout_52week | 1876 | 47.2% | 1.086 | -0.986 | -0.008 | [-0.059, 0.046] | 0.064 | 0.98 | -1.6% | -36.0% | PASS |
| low_vol_setup | 1982 | 47.5% | 1.132 | -1.025 | 0.000 | [-0.052, 0.051] | 0.092 | 1.00 | -0.7% | -43.0% | PASS |
| statistical_mean_reversion | 1860 | 47.7% | 1.012 | -0.926 | -0.001 | [-0.051, 0.050] | 0.060 | 1.00 | -0.9% | -35.2% | PASS |
| volume_trend_accumulation | 2373 | 47.8% | 1.108 | -0.982 | 0.018 | [-0.028, 0.063] | 0.091 | 1.03 | 0.2% | -37.8% | PASS |

## Per-year tables

### breakout_52week

| Year | n | Expectancy net | PF |
|---|---|---|---|
| 2016 | 140 | 0.036 | 1.08 |
| 2017 | 193 | 0.026 | 1.05 |
| 2018 | 177 | -0.193 | 0.69 |
| 2019 | 146 | 0.024 | 1.05 |
| 2020 | 184 | -0.195 | 0.69 |
| 2021 | 194 | 0.061 | 1.12 |
| 2022 | 96 | -0.078 | 0.85 |
| 2023 | 154 | 0.140 | 1.32 |
| 2024 | 229 | -0.015 | 0.97 |
| 2025 | 197 | 0.046 | 1.09 |
| 2026 | 166 | 0.057 | 1.11 |

### low_vol_setup

| Year | n | Expectancy net | PF |
|---|---|---|---|
| 2016 | 198 | 0.000 | 1.00 |
| 2017 | 201 | 0.269 | 1.65 |
| 2018 | 201 | -0.096 | 0.83 |
| 2019 | 176 | 0.276 | 1.67 |
| 2020 | 134 | 0.018 | 1.03 |
| 2021 | 207 | 0.031 | 1.06 |
| 2022 | 110 | -0.269 | 0.60 |
| 2023 | 201 | -0.235 | 0.63 |
| 2024 | 216 | 0.146 | 1.29 |
| 2025 | 188 | -0.124 | 0.80 |
| 2026 | 150 | -0.153 | 0.74 |

### statistical_mean_reversion

| Year | n | Expectancy net | PF |
|---|---|---|---|
| 2016 | 163 | -0.043 | 0.92 |
| 2017 | 177 | 0.028 | 1.06 |
| 2018 | 211 | -0.257 | 0.57 |
| 2019 | 159 | 0.250 | 1.72 |
| 2020 | 131 | -0.015 | 0.97 |
| 2021 | 142 | 0.084 | 1.21 |
| 2022 | 164 | -0.036 | 0.93 |
| 2023 | 178 | 0.114 | 1.28 |
| 2024 | 184 | -0.067 | 0.87 |
| 2025 | 185 | 0.003 | 1.01 |
| 2026 | 166 | 0.010 | 1.02 |

### volume_trend_accumulation

| Year | n | Expectancy net | PF |
|---|---|---|---|
| 2016 | 218 | -0.054 | 0.90 |
| 2017 | 203 | 0.066 | 1.14 |
| 2018 | 247 | -0.135 | 0.77 |
| 2019 | 188 | 0.212 | 1.55 |
| 2020 | 224 | -0.075 | 0.86 |
| 2021 | 233 | 0.124 | 1.27 |
| 2022 | 206 | -0.273 | 0.58 |
| 2023 | 200 | 0.054 | 1.11 |
| 2024 | 238 | 0.216 | 1.47 |
| 2025 | 225 | -0.013 | 0.97 |
| 2026 | 191 | 0.100 | 1.21 |

## Control comparison

| Setup | Control runs | Control trades (mean) | Control expectancy (mean +/- std) | Strategy expectancy | p (matched_random) |
|---|---|---|---|---|---|
| breakout_52week | 30 | 1979.0 | 0.014 +/- 0.023 | -0.008 | 0.9355 |
| low_vol_setup | 30 | 2156.9 | 0.006 +/- 0.017 | 0.000 | 0.6774 |
| statistical_mean_reversion | 30 | 2260.1 | 0.006 +/- 0.024 | -0.001 | 0.6129 |
| volume_trend_accumulation | 30 | 2468.3 | 0.019 +/- 0.027 | 0.018 | 0.7742 |

The p-value is the fraction of matched-random controls that do at least as well as the real strategy (`mean(control >= real)`), with the finite-sample correction `(p_raw*n + 1)/(n + 1)`; it is never direction-flipped for negative results.

## Sanity checks

### breakout_52week

- Reconciliation: PASS
- No trade enters on or before its signal: PASS
- Max bars held <= max_hold (15): PASS (max 15)
- Stop-gap share: 6.7%
- data_end trades: 0 (info)
- data-coverage early_end: 0

### low_vol_setup

- Reconciliation: PASS
- No trade enters on or before its signal: PASS
- Max bars held <= max_hold (15): PASS (max 15)
- Stop-gap share: 6.0%
- data_end trades: 0 (info)
- data-coverage early_end: 0

### statistical_mean_reversion

- Reconciliation: PASS
- No trade enters on or before its signal: PASS
- Max bars held <= max_hold (15): PASS (max 15)
- Stop-gap share: 6.1%
- data_end trades: 0 (info)
- data-coverage early_end: 0

### volume_trend_accumulation

- Reconciliation: PASS
- No trade enters on or before its signal: PASS
- Max bars held <= max_hold (15): PASS (max 15)
- Stop-gap share: 5.4%
- data_end trades: 0 (info)
- data-coverage early_end: 0

## Deviations

- Trade statistics exclude censored trades (`data_end` / `eod_censored`) and anything exiting before 2016-01-01 (2015 is warm-up).
- `expectancy_gross` and `expectancy_net` are per-trade R averages.
- The p-value metric is per-trade expectancy (`r_net_mean`), not R sum.
- The matched-random control fires the same number of entries per day as the strategy, on random liquid symbols with valid indicators.
- Artifacts without `run_info` are ignored; older artifacts are quarantined in `invalid_20261110/`.

## Verdict

- **breakout_52week**: NO EVIDENCE OF EDGE
- **low_vol_setup**: SUSPECTED BUG investigate before trusting
- **statistical_mean_reversion**: NO EVIDENCE OF EDGE
- **volume_trend_accumulation**: NO EVIDENCE OF EDGE
