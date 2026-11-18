# Pre-2016 Window Study (H-16) — breakout 52week h=60

Generated `2026-11-18T15:57:45` by `scripts/research_window_study.py`.

## 1. Pre-registration quote

Verbatim from `docs/backtests/research/PREREGISTRATION-H-16-v1.md`:

> Research question (one sentence): Does `breakout_52week` have mean excess return at horizon 60 versus the volatility-bucket benchmark that is greater than 0 on entries 2006-01-01..2015-12-31, a window not used by E1/E2/E4?
> Primary threshold: bucket excess at h=60 `> 0` bp
> Direction: `higher`
> Significance rule: 95% month-block CI lower bound `> 0` AND `block_t >= z_crit(1) = 1.96` (use `matched_control.cell_passes` with `z = z_crit(1)`)

## 2. Primary cell

Setup `breakout_52week`, horizon 60, entries from 2006-01-01.

| Item | Value |
|---|---|
| n | 3208 |
| Mean bucket excess (bp) | 31.5 |
| 95% month-block CI (bp) | [-28.8, 102.8] |
| block_t | 0.94 |
| z_crit(1) | 1.96 |

PRE-REGISTERED PRIMARY CELL: FAIL

## 3. Data and provenance

| Item | Value |
|---|---|
| Requested span | 2005-01-01 -> 2015-12-31 |
| Actual panel | 2005-01-03 -> 2015-12-31 |
| Tradable symbols | 461 |
| Dropped at load | 42 |
| Evaluation start | 2006-01-01 |
| Git revision | `1cc53dff59073b63bbe3b51d5882edf50c2e45e1` |
| Dirty worktree | no |
| Matches pre-registration | yes |
| Command | `scripts/research_window_study.py` |
| Elapsed | 7.1 minutes |

## 4. Panel thinning

Eligible symbols are those passing the liquidity gate on at least one day of the year.

| Year | Eligible symbols |
|---|---|
| 2005 | 244 |
| 2006 | 286 |
| 2007 | 333 |
| 2008 | 336 |
| 2009 | 309 |
| 2010 | 330 |
| 2011 | 359 |
| 2012 | 363 |
| 2013 | 395 |
| 2014 | 419 |
| 2015 | 426 |

## 5. Descriptive cells (no pass/fail)

### `statistical_mean_reversion`

Events after cooldown: 4764.

| h | n | raw mean (bp) | bucket excess (bp) | 95% CI (bp) | hit rate | block_t |
|---|---|---|---|---|---|---|
| 1 | 4764 | -3.6 | 6.1 | [-0.5, 12.5] | 52.4% | 1.85 |
| 5 | 4764 | 45.6 | 6.0 | [-7.0, 18.2] | 50.5% | 0.93 |
| 10 | 4748 | 55.1 | 6.4 | [-9.7, 21.4] | 51.1% | 0.80 |
| 20 | 4709 | 153.5 | 4.4 | [-20.5, 26.1] | 50.1% | 0.37 |
| 60 | 4656 | 303.5 | -27.3 | [-77.8, 23.0] | 49.2% | -1.06 |

### `breakout_52week`

Events after cooldown: 3247.

| h | n | raw mean (bp) | bucket excess (bp) | 95% CI (bp) | hit rate | block_t |
|---|---|---|---|---|---|---|
| 1 | 3247 | -5.6 | -6.3 | [-11.9, -1.1] | 47.2% | -2.28 |
| 5 | 3246 | -0.7 | -6.9 | [-19.0, 6.2] | 48.6% | -1.07 |
| 10 | 3242 | 17.3 | -5.9 | [-25.0, 15.6] | 48.0% | -0.57 |
| 20 | 3239 | 54.9 | -3.8 | [-33.0, 27.6] | 48.6% | -0.25 |
| 60 | 3208 | 294.1 | 31.5 | [-28.8, 102.8] | 50.1% | 0.94 |

### `low_vol_setup`

Events after cooldown: 7784.

| h | n | raw mean (bp) | bucket excess (bp) | 95% CI (bp) | hit rate | block_t |
|---|---|---|---|---|---|---|
| 1 | 7784 | -0.4 | -0.8 | [-2.3, 0.7] | 49.0% | -1.04 |
| 5 | 7760 | 23.0 | 2.2 | [-2.1, 6.8] | 49.8% | 0.98 |
| 10 | 7717 | 43.5 | 6.7 | [-0.3, 13.8] | 51.4% | 1.85 |
| 20 | 7682 | 90.3 | 7.8 | [-2.2, 18.0] | 50.5% | 1.52 |
| 60 | 7564 | 262.3 | 8.1 | [-9.3, 25.5] | 50.4% | 0.91 |

### `volume_trend_accumulation`

Events after cooldown: 9563.

| h | n | raw mean (bp) | bucket excess (bp) | 95% CI (bp) | hit rate | block_t |
|---|---|---|---|---|---|---|
| 1 | 9563 | 2.2 | -1.6 | [-4.8, 1.8] | 48.6% | -0.95 |
| 5 | 9563 | 13.6 | -3.2 | [-11.3, 4.8] | 48.6% | -0.77 |
| 10 | 9556 | 33.3 | -4.6 | [-16.1, 7.5] | 48.7% | -0.76 |
| 20 | 9526 | 72.4 | -7.1 | [-22.8, 9.3] | 48.7% | -0.87 |
| 60 | 9340 | 253.3 | -17.9 | [-46.7, 11.4] | 47.7% | -1.21 |

## 6. Per-year bucket excess for `breakout_52week`

### h=10

| Year | n | mean bucket excess (bp) | hit rate |
|---|---|---|---|
| 2006 | 292 | -30.3 | 46.2% |
| 2007 | 329 | 80.3 | 54.1% |
| 2008 | 53 | -89.2 | 49.1% |
| 2009 | 156 | -82.7 | 41.0% |
| 2010 | 328 | -68.8 | 44.2% |
| 2011 | 250 | 14.9 | 51.2% |
| 2012 | 350 | 18.1 | 50.6% |
| 2013 | 690 | -20.9 | 46.5% |
| 2014 | 550 | 4.1 | 46.7% |
| 2015 | 244 | 22.6 | 50.8% |

### h=20

| Year | n | mean bucket excess (bp) | hit rate |
|---|---|---|---|
| 2006 | 292 | -39.2 | 50.0% |
| 2007 | 329 | 142.2 | 54.7% |
| 2008 | 53 | -138.7 | 39.6% |
| 2009 | 156 | -102.4 | 42.3% |
| 2010 | 328 | -83.0 | 47.6% |
| 2011 | 250 | 43.1 | 52.0% |
| 2012 | 350 | 32.0 | 53.1% |
| 2013 | 690 | -13.0 | 48.4% |
| 2014 | 550 | -27.8 | 42.7% |
| 2015 | 241 | 21.4 | 50.2% |

### h=60

| Year | n | mean bucket excess (bp) | hit rate |
|---|---|---|---|
| 2006 | 292 | 20.6 | 49.7% |
| 2007 | 329 | 287.3 | 54.1% |
| 2008 | 53 | -269.3 | 45.3% |
| 2009 | 156 | -54.2 | 48.7% |
| 2010 | 328 | -136.2 | 45.1% |
| 2011 | 250 | 114.6 | 52.8% |
| 2012 | 350 | 113.7 | 52.6% |
| 2013 | 690 | -53.2 | 46.7% |
| 2014 | 550 | 27.8 | 52.2% |
| 2015 | 210 | 99.1 | 52.4% |

## 7. Sanity check — vol-matched random event sets

Seeds 90000..90019. The mean should be about 0; a value whose absolute size exceeds 3 bp is flagged.

| Setup | h | draws | mean (bp) | std (bp) | flagged |
|---|---|---|---|---|---|
| `statistical_mean_reversion` | 1 | 20 | 0.2 | 1.4 | no |
| `statistical_mean_reversion` | 5 | 20 | -1.2 | 3.5 | no |
| `statistical_mean_reversion` | 10 | 20 | -0.9 | 5.4 | no |
| `statistical_mean_reversion` | 20 | 20 | -1.4 | 7.0 | no |
| `statistical_mean_reversion` | 60 | 20 | -3.1 | 15.5 | yes |
| `breakout_52week` | 1 | 20 | 0.1 | 1.9 | no |
| `breakout_52week` | 5 | 20 | -0.3 | 3.4 | no |
| `breakout_52week` | 10 | 20 | -1.0 | 6.4 | no |
| `breakout_52week` | 20 | 20 | -2.2 | 7.6 | no |
| `breakout_52week` | 60 | 20 | -1.5 | 9.0 | no |
| `low_vol_setup` | 1 | 20 | -0.1 | 0.7 | no |
| `low_vol_setup` | 5 | 20 | -0.1 | 1.7 | no |
| `low_vol_setup` | 10 | 20 | 0.5 | 2.4 | no |
| `low_vol_setup` | 20 | 20 | 1.2 | 3.3 | no |
| `low_vol_setup` | 60 | 20 | 2.2 | 4.7 | no |
| `volume_trend_accumulation` | 1 | 20 | -0.4 | 0.7 | no |
| `volume_trend_accumulation` | 5 | 20 | 0.3 | 2.5 | no |
| `volume_trend_accumulation` | 10 | 20 | -0.3 | 2.7 | no |
| `volume_trend_accumulation` | 20 | 20 | -0.1 | 4.2 | no |
| `volume_trend_accumulation` | 60 | 20 | -1.6 | 8.9 | no |

## 8. Limits

- In-sample, survivorship-biased universe; no walk-forward.
- The universe is today's S&P 500 snapshot; the bias is larger for 2006-2015 than for later windows, and there is no point-in-time membership; results cannot rule out survivorship.
- The liquidity gate is evaluated on dividend-adjusted prices, which is stricter in older years.
- Exploratory: never the scorecard, D-75 pass bar, kill rule or any forward verdict.
- Capacity and slot competition are ignored.
- The descriptive cells share signals and are not independent trials.
- The bucket benchmark is a same-date eligibility mean, not sector- or size-matched.
