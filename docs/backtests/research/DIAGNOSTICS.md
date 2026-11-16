# Research Baseline Diagnostics (D-82)

- Generated: 2026-11-16 18:10
- Engine: commit `7628660` — D-82 engine code (`bd93d02`, `7ed0135`, `1fcac93`) plus the
  T8 clean-tree guard; no engine, indicator or control code was changed for this refresh.
- Artifacts: the newest artifact per setup selected by the script, i.e. the four
  same-day-recycling ablation runs (all record `run.code.dirty = false`):
  `statistical_mean_reversion_20261116_175221_recycle_on.json`,
  `breakout_52week_20261116_174053_recycle_on.json`,
  `low_vol_setup_20261116_174638_recycle_on.json`,
  `volume_trend_accumulation_20261116_175828_recycle_on.json`.
- Panel note: sections (a), (b) and (d) are computed on this document's 2015-01-01 ->
  2026-11-11 cache span (the script's default `--end`), not on the artifacts' 2026-11-16
  panel; the artifact-derived columns and section (c) trade scan use the artifacts above.
- Window: 2015-01-01 -> 2026-11-11 (panel 2015-01-02 -> 2026-11-10)
- Setups: statistical_mean_reversion, breakout_52week, low_vol_setup, volume_trend_accumulation
- Candidate seeds: 42..61 (20 seeds)
- Evaluation window for trade statistics: exit date >= 2016-01-01 and `censored == False`

## (a) Seed sensitivity

Each row re-runs the same signals with a different candidate-shuffle seed.

| Setup | Seeds | Mean of r_net mean | Std | Min | Max | Matched-control std (newest artifact) |
|---|---|---|---|---|---|---|
| statistical_mean_reversion | 20 | +0.0161 | 0.0188 | -0.0303 | +0.0524 | 0.0222 |
| breakout_52week | 20 | +0.0308 | 0.0140 | +0.0092 | +0.0566 | 0.0229 |
| low_vol_setup | 20 | +0.0073 | 0.0198 | -0.0293 | +0.0506 | 0.0232 |
| volume_trend_accumulation | 20 | +0.0089 | 0.0230 | -0.0458 | +0.0380 | 0.0167 |

## (b) Cost sensitivity

Per-side cost stepped over 0, 7.5, 15 and 30 bps on the same signals.

| Setup | Cost bps/side | n | Expectancy net | Expectancy gross | CAGR % | Max DD % |
|---|---|---|---|---|---|---|
| statistical_mean_reversion | 0 | 1683 | +0.1122 | +0.1122 | +7.34 | -19.72 |
| statistical_mean_reversion | 7.5 | 1683 | +0.0813 | +0.1122 | +4.82 | -21.61 |
| statistical_mean_reversion | 15 | 1681 | +0.0524 | +0.1142 | +2.59 | -23.44 |
| statistical_mean_reversion | 30 | 1682 | -0.0104 | +0.1132 | -2.21 | -32.62 |
| breakout_52week | 0 | 1682 | +0.1026 | +0.1026 | +6.61 | -15.78 |
| breakout_52week | 7.5 | 1677 | +0.0743 | +0.1107 | +4.57 | -16.78 |
| breakout_52week | 15 | 1679 | +0.0299 | +0.1026 | +1.22 | -19.10 |
| breakout_52week | 30 | 1676 | -0.0380 | +0.1073 | -3.01 | -41.47 |
| low_vol_setup | 0 | 1762 | +0.1105 | +0.1105 | +6.76 | -24.55 |
| low_vol_setup | 7.5 | 1738 | +0.0601 | +0.1057 | +3.87 | -28.20 |
| low_vol_setup | 15 | 1738 | +0.0275 | +0.1183 | +1.52 | -32.85 |
| low_vol_setup | 30 | 1747 | -0.0719 | +0.1100 | -4.97 | -50.86 |
| volume_trend_accumulation | 0 | 2136 | +0.0850 | +0.0850 | +7.25 | -20.82 |
| volume_trend_accumulation | 7.5 | 2136 | +0.0446 | +0.0808 | +3.80 | -24.21 |
| volume_trend_accumulation | 15 | 2133 | +0.0062 | +0.0789 | +0.04 | -29.22 |
| volume_trend_accumulation | 30 | 2134 | -0.0667 | +0.0789 | -6.18 | -56.96 |

| Setup | Cost where expectancy_net crosses 0 |
|---|---|
| statistical_mean_reversion | 27.51 bps/side |
| breakout_52week | 21.60 bps/side |
| low_vol_setup | 19.15 bps/side |
| volume_trend_accumulation | 16.28 bps/side |

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
| low_vol_setup | KO | 2016-02-03 | 2016-02-25 | time | 1 | 2016-02-19 |
| low_vol_setup | CB | 2019-02-12 | 2019-03-06 | time | 1 | 2019-02-27 |
| low_vol_setup | PLD | 2019-05-23 | 2019-05-29 | stop | 1 | 2019-05-28 |
| volume_trend_accumulation | WTW | 2016-01-04 | 2016-01-07 | stop_gap | 1 | 2016-01-06 |
| volume_trend_accumulation | DGX | 2016-05-24 | 2016-06-15 | time | 1 | 2016-06-02 |
| volume_trend_accumulation | RDDT | 2024-10-29 | 2024-10-30 | target_gap | 1 | 2024-10-30 |

## (d) Exit mix and win rate

Strategy is one run (seed 42); the control is five matched-random runs (seeds 30042..30046), averaged.

| Setup | Book | n | Win rate | stop | stop_gap | target | target_gap | time | Mean bars held |
|---|---|---|---|---|---|---|---|---|---|
| statistical_mean_reversion | strategy | 1681 | 0.504 | 0.309 | 0.055 | 0.216 | 0.042 | 0.378 | 10.01 |
| statistical_mean_reversion | matched_random | 1872.4 | 0.481 | 0.355 | 0.062 | 0.246 | 0.047 | 0.290 | 9.11 |
| breakout_52week | strategy | 1679 | 0.483 | 0.345 | 0.060 | 0.229 | 0.051 | 0.314 | 8.82 |
| breakout_52week | matched_random | 1668.6 | 0.483 | 0.349 | 0.064 | 0.241 | 0.045 | 0.301 | 9.25 |
| low_vol_setup | strategy | 1738 | 0.488 | 0.375 | 0.054 | 0.269 | 0.036 | 0.266 | 9.20 |
| low_vol_setup | matched_random | 1790.4 | 0.470 | 0.354 | 0.060 | 0.232 | 0.041 | 0.314 | 9.47 |
| volume_trend_accumulation | strategy | 2133 | 0.476 | 0.370 | 0.051 | 0.237 | 0.032 | 0.310 | 8.79 |
| volume_trend_accumulation | matched_random | 2048.8 | 0.490 | 0.344 | 0.062 | 0.245 | 0.045 | 0.303 | 9.28 |

