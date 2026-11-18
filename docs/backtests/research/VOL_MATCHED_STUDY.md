# Volatility-Matched Re-measurement (E4) — event study (E1) and exit study (E2)

Generated `2026-11-17T18:28:04` by `scripts/research_vol_matched.py`.

Exploratory, in-sample, survivorship-biased universe (today's S&P 500). Not evidence of a live edge.

This analysis ignores portfolio capacity and slot competition: every signal is taken as an independent trade, with no limit on concurrent positions or capital.

## Why

Two flaws were found in E1/E2. (1) The old null (`control.matched_random_signals`) picks random stocks of ANY volatility, so its spread is 2-3.5x smaller than the strategy's own month-block uncertainty. The reported `p_high`/`p_low` and `gap/std` are therefore NOT valid significance tests. (2) The exit study measures R, where 1R = 2*ATR. `low_vol_setup` picks low-ATR stocks, so the same percent move counts as more R. E2 shows `low_vol_setup` B4 beating the null in R (+0.031R) while E1 shows the same signals underperforming the market by 15 bp at h=20. The sign disagreement is probably a volatility/R artifact. This task checks it.

## Pre-declared rule

Any cell that does not pass is NOT evidence of an edge. A passing cell is only a candidate to be pre-registered and tested on the locked 2021-2026 holdout; it is never a result. This study re-measures the same 4 setups on the same data as E1/E2, so cumulative trials are 20+20+20+20 = 80 cells, and none of this is out-of-sample.

## Definitions

- **Volatility bucket:** on each date, the symbols eligible on that date are ranked by `atr_pct` with `rank(pct=True, method="first")` and assigned `bucket = ceil(pct * 10) - 1`, clipped to `0..9`. `--n-buckets 10`. Not eligible or NaN `atr_pct` -> `-1`. An event's bucket is the bucket on its SIGNAL date `t`, so no data after `t` is used.
- **Bucket benchmark (Part 1):** for each entry date `e` and bucket `b`, the mean `ret_h` over all symbols whose bucket on the bar BEFORE `e` was `b` (the bucket series is shifted by one bar per symbol, mirroring `events.universe_benchmark`'s previous-bar eligibility) and that have the forward data. Event excess = event `ret_h` - bucket benchmark at the event's signal-date bucket.
- **Forward return (same as `events.py`):** `ret_h = close[e+h-1] / open[e] - 1` for horizons 1, 5, 10, 20, 60, cooldown `5`. A row without the future close is dropped for that horizon, never filled.
- **Vol-matched random signals:** for every date and every bucket in which the real setup fires `c` times, draw `k = min(c, pool size)` distinct symbols from the symbols that are eligible AND in that bucket on that date. Dates and buckets are visited in sorted order; non-tradable symbols get an all-False series. Shortfalls (`requested > drawn`) are reported, never hidden.
- **Percent returns (Part 2):** `add_pct_returns(trades, cost_bps)` adds `ret_gross_pct = exit_price*(1-c)/(entry_price*(1+c)) - 1` with `c = cost_bps/10000`; `ret_net_pct` carries the same cost-aware value and is the name reported in Part 2. Same entries and the same five variants B0-B4 as E2, 15 bps per side.

> Correction (E6, 2026-11-18): ret_gross_pct is exit/entry-1 (no costs); ret_net_pct is the cost-aware value. The original wording above was wrong. All reported numbers use ret_net_pct and are unchanged.

- **Honest significance:** `block_summary` returns the mean, the 95% month-block bootstrap CI (`events.month_block_bootstrap_ci`, `n_resamples=2000`, seed `42`), `se_block = (ci_high - ci_low)/(2*1.96)`, `reference_in_ci`, and `block_t = (mean - reference)/se_block` (NaN when `se_block` is 0 or NaN). Reference is 0 for the Part 1 bucket excess and the vol-matched null mean for Part 2.
- **Bonferroni:** `z_crit(m) = NormalDist().inv_cdf(1 - 0.05/(2*m))`; `m = 20` cells per part (4 setups x 5 horizons for Part 1, 4 setups x 5 variants for Part 2), so `z_crit(20) = 3.023`. A cell passes only if `|block_t| >= z_crit` AND `reference_in_ci` is False. An E2 cell passes only if BOTH the R metric and the percent metric pass AND their gap signs agree.
- **Null spread:** the null std is the descriptive spread of the null mean, NOT a test. No `p_high`/`p_low` is reported anywhere in this task.
- **Seeds:** Part 1 sanity draws use `70000 + i` (20 draws); Part 2 null draws use `80000 + i` (100 draws).
- **Capacity caveat:** This analysis ignores portfolio capacity and slot competition: every signal is taken as an independent trade, with no limit on concurrent positions or capital.

## Data and provenance

| Item | Value |
|---|---|
| Requested span | 2015-01-01 -> 2026-11-17 |
| Actual panel | 2015-01-02 -> 2026-11-17 |
| Tradable symbols | 501 |
| Dropped at load | 2 |
| Evaluation start | 2016-01-01 |
| Volatility buckets | 10 |
| Git revision | `49cad31b0a2bae03d9f9654f7a3dba6d742fc2ce` |
| Dirty worktree | no |
| Command | `scripts/research_vol_matched.py` |
| Elapsed | 26.6 minutes |

**SANITY WARNING: the vol-matched random event sets show a mean bucket excess whose absolute value exceeds 3 bp in at least one cell:** `breakout_52week` h=20: mean -3.9 bp; `breakout_52week` h=60: mean -8.4 bp.

## Part 1 — event study vs the volatility-bucket benchmark

### `statistical_mean_reversion`

Events after cooldown: 9014.

| h | n | old excess vs universe (bp) | bucket excess (bp) | 95% CI (bp) | hit rate | reference in CI | block t | passes |
|---|---|---|---|---|---|---|---|---|
| 1 | 9014 | -1.4 | 1.2 | [-2.9, 5.5] | 50.2% | yes | 0.54 | no |
| 5 | 9014 | -9.0 | -9.1 | [-19.9, 1.6] | 49.5% | yes | -1.66 | no |
| 10 | 9010 | -15.6 | -17.2 | [-37.8, 3.0] | 49.3% | yes | -1.65 | no |
| 20 | 8990 | -26.1 | -20.8 | [-51.5, 8.4] | 48.5% | yes | -1.36 | no |
| 60 | 8752 | -51.7 | -34.2 | [-92.0, 22.4] | 48.9% | yes | -1.17 | no |

### `breakout_52week`

Events after cooldown: 4915.

| h | n | old excess vs universe (bp) | bucket excess (bp) | 95% CI (bp) | hit rate | reference in CI | block t | passes |
|---|---|---|---|---|---|---|---|---|
| 1 | 4915 | 1.8 | 1.6 | [-4.2, 7.5] | 50.7% | yes | 0.55 | no |
| 5 | 4910 | 7.7 | 7.3 | [-8.0, 23.4] | 50.5% | yes | 0.92 | no |
| 10 | 4881 | 20.9 | 21.6 | [0.1, 45.0] | 50.9% | no | 1.89 | no |
| 20 | 4837 | 14.6 | 22.7 | [-11.3, 58.6] | 48.9% | yes | 1.27 | no |
| 60 | 4813 | 31.4 | 71.9 | [10.9, 135.1] | 50.7% | no | 2.27 | no |

### `low_vol_setup`

Events after cooldown: 9168.

| h | n | old excess vs universe (bp) | bucket excess (bp) | 95% CI (bp) | hit rate | reference in CI | block t | passes |
|---|---|---|---|---|---|---|---|---|
| 1 | 9168 | -0.8 | 0.1 | [-1.6, 1.8] | 50.4% | yes | 0.10 | no |
| 5 | 9165 | -5.2 | 0.3 | [-4.8, 5.2] | 50.7% | yes | 0.12 | no |
| 10 | 9163 | -11.5 | 2.0 | [-5.9, 10.1] | 50.7% | yes | 0.50 | no |
| 20 | 9161 | -15.4 | 9.9 | [-2.3, 21.8] | 51.8% | yes | 1.61 | no |
| 60 | 9109 | -49.2 | 18.9 | [-5.5, 42.9] | 50.8% | yes | 1.53 | no |

### `volume_trend_accumulation`

Events after cooldown: 14481.

| h | n | old excess vs universe (bp) | bucket excess (bp) | 95% CI (bp) | hit rate | reference in CI | block t | passes |
|---|---|---|---|---|---|---|---|---|
| 1 | 14481 | 1.6 | 1.4 | [-1.8, 4.6] | 50.5% | yes | 0.83 | no |
| 5 | 14465 | 5.5 | 6.9 | [-0.4, 14.5] | 50.2% | yes | 1.80 | no |
| 10 | 14411 | 3.1 | 3.7 | [-7.3, 15.8] | 49.4% | yes | 0.63 | no |
| 20 | 14285 | -11.1 | -4.4 | [-25.8, 16.4] | 49.6% | yes | -0.41 | no |
| 60 | 14160 | -11.7 | 23.5 | [-12.6, 61.1] | 49.3% | yes | 1.25 | no |

## Sanity check — vol-matched random event sets

Each draw uses the same per-date/per-bucket counts, cooldown and bucket excess as the real events. Seeds 70000..70019. The mean should be about 0; a value whose absolute size exceeds 3 bp is flagged.

| Setup | h | draws | mean (bp) | std (bp) |
|---|---|---|---|---|
| `statistical_mean_reversion` | 1 | 20 | -0.1 | 1.2 |
| `statistical_mean_reversion` | 5 | 20 | -0.2 | 2.3 |
| `statistical_mean_reversion` | 10 | 20 | -1.0 | 3.8 |
| `statistical_mean_reversion` | 20 | 20 | -0.7 | 4.5 |
| `statistical_mean_reversion` | 60 | 20 | -0.0 | 9.6 |
| `breakout_52week` | 1 | 20 | 0.3 | 1.4 |
| `breakout_52week` | 5 | 20 | -1.1 | 4.8 |
| `breakout_52week` | 10 | 20 | -1.8 | 6.3 |
| `breakout_52week` | 20 | 20 | -3.9 | 10.2 |
| `breakout_52week` | 60 | 20 | -8.4 | 21.5 |
| `low_vol_setup` | 1 | 20 | -0.2 | 0.7 |
| `low_vol_setup` | 5 | 20 | 0.4 | 2.4 |
| `low_vol_setup` | 10 | 20 | -0.2 | 2.8 |
| `low_vol_setup` | 20 | 20 | 0.8 | 3.3 |
| `low_vol_setup` | 60 | 20 | 1.2 | 4.9 |
| `volume_trend_accumulation` | 1 | 20 | -0.1 | 0.9 |
| `volume_trend_accumulation` | 5 | 20 | -0.6 | 2.4 |
| `volume_trend_accumulation` | 10 | 20 | -0.2 | 2.7 |
| `volume_trend_accumulation` | 20 | 20 | 1.6 | 3.5 |
| `volume_trend_accumulation` | 60 | 20 | -2.0 | 8.5 |

## Part 2 — exit study in R and percent units

R means and gaps are in R units; percent means and gaps are in basis points. `null std` is the descriptive spread of the null mean, NOT a test. CI columns are the 95% month-block CI of the real trade mean; `ref in CI` says whether the vol-matched null mean sits inside it. `block t` is `(mean - null mean)/se_block`. An E2 cell passes only if both metrics pass and the two gap signs agree.

### `statistical_mean_reversion`

Real entries: 16683.

| Variant | n | mean r_net | null r mean | null r std | gap R | CI R | ref in CI (R) | block t (R) |
|---|---|---|---|---|---|---|---|---|
| B0 | 16659 | 0.0494 | 0.0758 | 0.0073 | -0.0264 | [-0.0590, 0.1607] | yes | -0.47 |
| B1 | 16651 | 0.0331 | 0.0614 | 0.0084 | -0.0283 | [-0.1146, 0.1825] | yes | -0.37 |
| B2 | 16593 | 0.1545 | 0.1681 | 0.0117 | -0.0135 | [0.0027, 0.3252] | yes | -0.16 |
| B3 | 16668 | 0.0453 | 0.0634 | 0.0070 | -0.0182 | [-0.0475, 0.1439] | yes | -0.37 |
| B4 | 16639 | 0.0649 | 0.1109 | 0.0094 | -0.0460 | [-0.3020, 0.3708] | yes | -0.27 |

| Variant | mean ret_net_pct (bp) | null pct mean (bp) | null pct std (bp) | gap pct (bp) | CI pct (bp) | ref in CI (pct) | block t (pct) | signs agree | passes |
|---|---|---|---|---|---|---|---|---|---|
| B0 | 28.3 | 42.1 | 4.1 | -13.8 | [-31.8, 90.6] | yes | -0.44 | yes | no |
| B1 | 19.8 | 34.0 | 4.6 | -14.2 | [-63.2, 102.5] | yes | -0.34 | yes | no |
| B2 | 85.3 | 92.0 | 6.2 | -6.8 | [-0.3, 181.9] | yes | -0.15 | yes | no |
| B3 | 26.6 | 34.5 | 3.7 | -7.9 | [-23.5, 78.8] | yes | -0.30 | yes | no |
| B4 | 31.6 | 59.3 | 5.3 | -27.8 | [-167.6, 201.1] | yes | -0.30 | yes | no |

### `breakout_52week`

Real entries: 6819.

| Variant | n | mean r_net | null r mean | null r std | gap R | CI R | ref in CI (R) | block t (R) |
|---|---|---|---|---|---|---|---|---|
| B0 | 6772 | -0.0018 | 0.0146 | 0.0125 | -0.0164 | [-0.0648, 0.0628] | yes | -0.50 |
| B1 | 6754 | 0.0010 | 0.0138 | 0.0131 | -0.0128 | [-0.0946, 0.0960] | yes | -0.26 |
| B2 | 6754 | 0.0127 | 0.0504 | 0.0178 | -0.0378 | [-0.0801, 0.1055] | yes | -0.80 |
| B3 | 6786 | -0.0484 | -0.0118 | 0.0136 | -0.0366 | [-0.1027, 0.0050] | yes | -1.33 |
| B4 | 6712 | 0.0641 | 0.0368 | 0.0195 | 0.0273 | [-0.1483, 0.2618] | yes | 0.26 |

| Variant | mean ret_net_pct (bp) | null pct mean (bp) | null pct std (bp) | gap pct (bp) | CI pct (bp) | ref in CI (pct) | block t (pct) | signs agree | passes |
|---|---|---|---|---|---|---|---|---|---|
| B0 | 11.4 | 12.7 | 6.1 | -1.3 | [-18.7, 42.8] | yes | -0.08 | yes | no |
| B1 | 20.1 | 14.0 | 6.7 | 6.0 | [-25.7, 66.9] | yes | 0.26 | no | no |
| B2 | 20.4 | 24.7 | 8.8 | -4.3 | [-23.8, 66.3] | yes | -0.19 | yes | no |
| B3 | -9.6 | -0.3 | 6.8 | -9.3 | [-37.5, 17.5] | yes | -0.66 | yes | no |
| B4 | 56.9 | 32.5 | 9.0 | 24.4 | [-24.9, 137.2] | yes | 0.59 | yes | no |

### `low_vol_setup`

Real entries: 18346.

| Variant | n | mean r_net | null r mean | null r std | gap R | CI R | ref in CI (R) | block t (R) |
|---|---|---|---|---|---|---|---|---|
| B0 | 18338 | 0.0572 | 0.0379 | 0.0073 | 0.0193 | [-0.0265, 0.1459] | yes | 0.44 |
| B1 | 18338 | 0.0998 | 0.0811 | 0.0077 | 0.0187 | [-0.0051, 0.2125] | yes | 0.34 |
| B2 | 18330 | 0.1887 | 0.1559 | 0.0106 | 0.0328 | [0.0586, 0.3201] | yes | 0.49 |
| B3 | 18335 | 0.0604 | 0.0334 | 0.0076 | 0.0270 | [-0.0302, 0.1639] | yes | 0.55 |
| B4 | 18336 | 0.2463 | 0.2069 | 0.0110 | 0.0394 | [0.0914, 0.3995] | yes | 0.50 |

| Variant | mean ret_net_pct (bp) | null pct mean (bp) | null pct std (bp) | gap pct (bp) | CI pct (bp) | ref in CI (pct) | block t (pct) | signs agree | passes |
|---|---|---|---|---|---|---|---|---|---|
| B0 | 16.2 | 11.5 | 2.4 | 4.7 | [-9.5, 42.4] | yes | 0.35 | yes | no |
| B1 | 27.7 | 23.4 | 2.5 | 4.3 | [-3.2, 60.3] | yes | 0.26 | yes | no |
| B2 | 53.3 | 44.2 | 3.4 | 9.1 | [15.3, 91.7] | yes | 0.47 | yes | no |
| B3 | 15.3 | 8.5 | 2.4 | 6.7 | [-11.3, 45.0] | yes | 0.47 | yes | no |
| B4 | 71.9 | 63.1 | 3.4 | 8.8 | [26.8, 117.6] | yes | 0.38 | yes | no |

### `volume_trend_accumulation`

Real entries: 20830.

| Variant | n | mean r_net | null r mean | null r std | gap R | CI R | ref in CI (R) | block t (R) |
|---|---|---|---|---|---|---|---|---|
| B0 | 20696 | 0.0161 | 0.0286 | 0.0061 | -0.0125 | [-0.0372, 0.0731] | yes | -0.44 |
| B1 | 20635 | 0.0085 | 0.0391 | 0.0082 | -0.0306 | [-0.0611, 0.0815] | yes | -0.84 |
| B2 | 20633 | 0.0554 | 0.0914 | 0.0105 | -0.0360 | [-0.0248, 0.1384] | yes | -0.86 |
| B3 | 20750 | -0.0095 | 0.0106 | 0.0073 | -0.0201 | [-0.0631, 0.0441] | yes | -0.73 |
| B4 | 20536 | 0.0809 | 0.0962 | 0.0102 | -0.0153 | [-0.0779, 0.2200] | yes | -0.20 |

| Variant | mean ret_net_pct (bp) | null pct mean (bp) | null pct std (bp) | gap pct (bp) | CI pct (bp) | ref in CI (pct) | block t (pct) | signs agree | passes |
|---|---|---|---|---|---|---|---|---|---|
| B0 | 11.7 | 18.6 | 3.1 | -6.9 | [-13.3, 38.3] | yes | -0.53 | yes | no |
| B1 | 10.8 | 23.1 | 4.0 | -12.3 | [-21.3, 45.3] | yes | -0.72 | yes | no |
| B2 | 28.4 | 45.1 | 5.1 | -16.7 | [-6.5, 68.2] | yes | -0.87 | yes | no |
| B3 | -1.1 | 9.0 | 3.7 | -10.0 | [-24.5, 24.4] | yes | -0.80 | yes | no |
| B4 | 49.4 | 56.3 | 4.7 | -6.8 | [-13.9, 106.8] | yes | -0.22 | yes | no |

## Control shortfall

Requested signals are the real per-date/per-bucket counts; drawn signals are what the vol-matched control could draw from the eligible pool of that bucket.

| Setup | real entries | requested (total) | drawn (total) | mean requested/draw | mean drawn/draw | shortfall (total) |
|---|---|---|---|---|---|---|
| `statistical_mean_reversion` | 16683 | 1685800 | 1685800 | 16,858.00 | 16,858.00 | 0 |
| `breakout_52week` | 6819 | 687200 | 687200 | 6,872.00 | 6,872.00 | 0 |
| `low_vol_setup` | 18346 | 1881200 | 1881200 | 18,812.00 | 18,812.00 | 0 |
| `volume_trend_accumulation` | 20830 | 2116300 | 2116300 | 21,163.00 | 21,163.00 | 0 |

## Cell summary

No cell passes.

## Notes

- Bucket controls match on size (pool size) and volatility, not on sector, industry, beta or liquidity beyond the existing eligibility rule.
- The same four setups are re-used on the same data, so the cumulative trial count is 80 cells and none of this is out-of-sample.
- No holdout was used in this study.
