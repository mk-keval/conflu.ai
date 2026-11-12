# Research Baseline Diagnostics (D-82)

- Generated: 2026-11-12 18:18
- Window: 2015-01-01 -> 2026-11-11 (panel 2015-01-02 -> 2026-11-10)
- Setups: statistical_mean_reversion, breakout_52week, low_vol_setup, volume_trend_accumulation
- Candidate seeds: 42..61 (20 seeds)
- Evaluation window for trade statistics: exit date >= 2016-01-01 and `censored == False`

## (a) Seed sensitivity

Each row re-runs the same signals with a different candidate-shuffle seed.

| Setup | Seeds | Mean of r_net mean | Std | Min | Max | Matched-control std (newest artifact) |
|---|---|---|---|---|---|---|
| statistical_mean_reversion | 20 | -0.0093 | 0.0136 | -0.0395 | +0.0134 | 0.0243 |
| breakout_52week | 20 | +0.0151 | 0.0170 | -0.0117 | +0.0498 | 0.0233 |
| low_vol_setup | 20 | -0.0171 | 0.0175 | -0.0530 | +0.0114 | 0.0174 |
| volume_trend_accumulation | 20 | -0.0062 | 0.0219 | -0.0457 | +0.0327 | 0.0268 |

## (b) Cost sensitivity

Per-side cost stepped over 0, 7.5, 15 and 30 bps on the same signals.

| Setup | Cost bps/side | n | Expectancy net | Expectancy gross | CAGR % | Max DD % |
|---|---|---|---|---|---|---|
| statistical_mean_reversion | 0 | 1857 | +0.0625 | +0.0625 | +4.43 | -21.29 |
| statistical_mean_reversion | 7.5 | 1857 | +0.0319 | +0.0625 | +1.82 | -28.03 |
| statistical_mean_reversion | 15 | 1860 | -0.0012 | +0.0600 | -0.93 | -35.25 |
| statistical_mean_reversion | 30 | 1860 | -0.0624 | +0.0602 | -5.87 | -58.39 |
| breakout_52week | 0 | 1879 | +0.0693 | +0.0693 | +4.38 | -18.25 |
| breakout_52week | 7.5 | 1883 | +0.0301 | +0.0662 | +1.38 | -24.53 |
| breakout_52week | 15 | 1876 | -0.0083 | +0.0639 | -1.65 | -36.00 |
| breakout_52week | 30 | 1881 | -0.0770 | +0.0674 | -7.02 | -63.03 |
| low_vol_setup | 0 | 1975 | +0.0984 | +0.0984 | +6.86 | -27.21 |
| low_vol_setup | 7.5 | 1969 | +0.0504 | +0.0957 | +3.38 | -33.33 |
| low_vol_setup | 15 | 1982 | +0.0004 | +0.0916 | -0.70 | -42.96 |
| low_vol_setup | 30 | 1975 | -0.0811 | +0.1009 | -6.65 | -60.87 |
| volume_trend_accumulation | 0 | 2373 | +0.0904 | +0.0904 | +7.44 | -24.63 |
| volume_trend_accumulation | 7.5 | 2375 | +0.0553 | +0.0918 | +4.12 | -28.98 |
| volume_trend_accumulation | 15 | 2373 | +0.0178 | +0.0907 | +0.17 | -37.85 |
| volume_trend_accumulation | 30 | 2374 | -0.0588 | +0.0870 | -7.27 | -69.16 |

| Setup | Cost where expectancy_net crosses 0 |
|---|---|
| statistical_mean_reversion | 14.72 bps/side |
| breakout_52week | 13.37 bps/side |
| low_vol_setup | 15.08 bps/side |
| volume_trend_accumulation | 18.49 bps/side |

## (c) Data integrity scan

Counts are over every loaded tradable bar in the panel.

| Metric | Count |
|---|---|
| Bars | 1441683 |
| Bars with any flag | 3649 |
| |close-to-close return| > 40% | 31 |
| high < low | 0 |
| open or close outside [low, high] | 419 |
| price <= 0 | 0 |
| volume == 0 | 3377 |
| Duplicate dates | 0 |
| Gaps > 5 business days | 0 |

Worst 20 symbols by flagged bars:

| Symbol | Bars | Flagged | >40% ret | high<low | out of range | price<=0 | vol==0 | dup dates | gap>5bd |
|---|---|---|---|---|---|---|---|---|---|
| SW | 2982 | 1395 | 0 | 0 | 36 | 0 | 1381 | 0 | 0 |
| FERG | 2982 | 1042 | 0 | 0 | 40 | 0 | 1033 | 0 | 0 |
| AMCR | 2982 | 909 | 0 | 0 | 136 | 0 | 897 | 0 | 0 |
| HWM | 2520 | 35 | 0 | 0 | 0 | 0 | 35 | 0 | 0 |
| VRT | 2080 | 12 | 0 | 0 | 0 | 0 | 12 | 0 | 0 |
| F | 2982 | 10 | 0 | 0 | 10 | 0 | 0 | 0 | 0 |
| T | 2982 | 9 | 0 | 0 | 9 | 0 | 0 | 0 | 0 |
| XOM | 2982 | 8 | 0 | 0 | 8 | 0 | 0 | 0 | 0 |
| HBAN | 2982 | 7 | 0 | 0 | 7 | 0 | 0 | 0 | 0 |
| CVNA | 2398 | 6 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| KO | 2982 | 6 | 0 | 0 | 6 | 0 | 0 | 0 | 0 |
| RF | 2982 | 5 | 0 | 0 | 5 | 0 | 0 | 0 | 0 |
| BE | 2086 | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| FITB | 2982 | 4 | 0 | 0 | 4 | 0 | 0 | 0 | 0 |
| SPG | 2982 | 4 | 0 | 0 | 4 | 0 | 0 | 0 | 0 |
| VZ | 2982 | 4 | 0 | 0 | 4 | 0 | 0 | 0 | 0 |
| ARES | 2982 | 3 | 0 | 0 | 3 | 0 | 0 | 0 | 0 |
| HST | 2982 | 3 | 0 | 0 | 3 | 0 | 0 | 0 | 0 |
| KEY | 2982 | 3 | 0 | 0 | 3 | 0 | 0 | 0 | 0 |
| MET | 2982 | 3 | 0 | 0 | 3 | 0 | 0 | 0 | 0 |

Artifact trades whose entry-to-exit window touches a flagged bar:

| Setup | Symbol | Entry | Exit | Exit reason | Flagged bars | First flag |
|---|---|---|---|---|---|---|
| statistical_mean_reversion | HUBB | 2017-08-22 | 2017-09-13 | target | 1 | 2017-09-01 |
| statistical_mean_reversion | RTX | 2017-09-07 | 2017-09-27 | target | 1 | 2017-09-19 |
| statistical_mean_reversion | GIS | 2018-05-04 | 2018-05-25 | time | 1 | 2018-05-16 |
| statistical_mean_reversion | STZ | 2025-10-31 | 2025-11-21 | time | 1 | 2025-11-12 |
| breakout_52week | WTW | 2016-01-05 | 2016-01-07 | stop_gap | 1 | 2016-01-06 |
| breakout_52week | OMC | 2021-03-22 | 2021-04-13 | time | 1 | 2021-04-01 |
| breakout_52week | RDDT | 2024-10-29 | 2024-10-30 | target_gap | 1 | 2024-10-30 |
| breakout_52week | RDDT | 2024-10-30 | 2024-10-30 | target | 1 | 2024-10-30 |
| low_vol_setup | KO | 2016-02-03 | 2016-02-25 | time | 1 | 2016-02-19 |
| low_vol_setup | CB | 2019-02-12 | 2019-03-06 | time | 1 | 2019-02-27 |
| low_vol_setup | PLD | 2019-05-23 | 2019-05-29 | stop | 1 | 2019-05-28 |
| volume_trend_accumulation | WTW | 2016-01-04 | 2016-01-07 | stop_gap | 1 | 2016-01-06 |
| volume_trend_accumulation | DGX | 2016-05-24 | 2016-06-15 | time | 1 | 2016-06-02 |

## (d) Exit mix and win rate

Strategy is one run (seed 42); the control is five matched-random runs (seeds 30042..30046), averaged.

| Setup | Book | n | Win rate | stop | stop_gap | target | target_gap | time | Mean bars held |
|---|---|---|---|---|---|---|---|---|---|
| statistical_mean_reversion | strategy | 1860 | 0.477 | 0.323 | 0.061 | 0.211 | 0.038 | 0.368 | 9.70 |
| statistical_mean_reversion | matched_random | 2063.0 | 0.479 | 0.353 | 0.068 | 0.242 | 0.043 | 0.293 | 9.02 |
| breakout_52week | strategy | 1876 | 0.472 | 0.364 | 0.067 | 0.222 | 0.052 | 0.295 | 8.60 |
| breakout_52week | matched_random | 1836.8 | 0.474 | 0.357 | 0.063 | 0.235 | 0.046 | 0.298 | 9.18 |
| low_vol_setup | strategy | 1982 | 0.475 | 0.384 | 0.060 | 0.271 | 0.036 | 0.249 | 8.80 |
| low_vol_setup | matched_random | 1969.6 | 0.474 | 0.357 | 0.060 | 0.238 | 0.039 | 0.307 | 9.43 |
| volume_trend_accumulation | strategy | 2373 | 0.478 | 0.370 | 0.054 | 0.238 | 0.043 | 0.295 | 8.69 |
| volume_trend_accumulation | matched_random | 2272.2 | 0.490 | 0.347 | 0.058 | 0.246 | 0.043 | 0.307 | 9.20 |

