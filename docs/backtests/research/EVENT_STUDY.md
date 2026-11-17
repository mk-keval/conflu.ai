# Event Study — signal information without exits

Generated `2026-11-17T12:35:13` by `scripts/research_event_study.py`.

Exploratory, in-sample, survivorship-biased universe (today's S&P 500). Not evidence of a live edge.

## Definitions

- **Signal:** `SETUPS[name](df)` is True at the CLOSE of day `t`; entry row `e` is the symbol's NEXT bar (entry at the open of `t+1`).
- **Forward return for horizon `h` (trading days, `h >= 1`):** `ret_h = close[e+h-1] / open[e] - 1`. `h=1` is the entry day open-to-close; `h=5` holds through the 5th bar including the entry day. Horizons: 1, 5, 10, 20, 60. Rows where `close[e+h-1]` does not exist are dropped for that horizon (never filled).
- **Event:** signal at `t` AND `eligible(df)` at `t`, entry row `e` with `entry date >= 2016-01-01`. **Cooldown:** a repeat is dropped when the previous accepted event on the same symbol is at most `5` bars earlier (default 5), so accepted events are more than 5 bars apart.
- **Universe benchmark:** for each entry date `e`, the mean `ret_h` over ALL symbols that were eligible at their signal-day (the bar before `e`) and have the forward data. **Excess return** = event `ret_h` minus that same-date universe mean.
- **Statistics:** n events, n distinct entry dates, event-weighted mean excess (basis points), hit rate (share of events with excess > 0), raw mean return, raw mean minus 30 bps (a 15 bps/side round trip), 95% CI of the mean excess from a month-block bootstrap (resample entry year-months with replacement, 2000 resamples, seed 42), and the mean excess by calendar year for h=5 and h=20.
- **Null:** 200 matched-random event sets per setup from `backend.app.research.control.matched_random_signals` (same number of events per day, random eligible symbols), the same cooldown and statistics; seeds 50000..50199. `p_high = (count(null >= real)+1)/(n+1)`, `p_low = (count(null <= real)+1)/(n+1)` per horizon.
- **Panel:** loaded as the baseline runner does (`download_daily` with the `.cache/research` span 2015-01-01 -> latest, then `add_indicators`); `NON_TRADABLE` symbols are excluded. 2015 is warm-up; entries are evaluated from 2016-01-01.

## Panel and reference

| Item | Value |
|---|---|
| Requested span | 2015-01-01 -> 2026-11-17 |
| Actual panel | 2015-01-02 -> 2026-11-17 |
| Tradable symbols | 501 |
| Dropped at load | 2 |
| Evaluation start | 2016-01-01 |

**SPY reference only (not compared to anything in this task).**

| Item | Value |
|---|---|
| Window | 2016-01-04 -> 2026-11-17 |
| CAGR (calendar years) | 14.53% |
| Max drawdown (daily close) | -33.72% |
| Bars | 2735 |

## Results

Mean excess, null mean/std and the CI are in basis points; raw mean and raw mean minus 30 bps are returns. `p_high` tests the strategy against the null from above, `p_low` from below.

### `statistical_mean_reversion`

Events after cooldown: 9014.

| h | n | dates | mean excess (bp) | 95% CI (bp) | hit rate | raw mean | raw mean - 30 bp | null mean (bp) | null std (bp) | p_high | p_low |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 9014 | 1684 | -1.4 | [-6.8, 4.2] | 49.7% | -0.018% | -0.318% | 0.0 | 1.3 | 0.8507 | 0.1542 |
| 5 | 9014 | 1684 | -9.0 | [-21.6, 4.3] | 49.4% | 0.405% | 0.105% | -0.0 | 3.0 | 1.0000 | 0.0050 |
| 10 | 9010 | 1682 | -15.6 | [-37.6, 5.4] | 49.2% | 0.312% | 0.012% | -0.1 | 4.1 | 1.0000 | 0.0050 |
| 20 | 8990 | 1673 | -26.1 | [-57.7, 3.4] | 47.6% | 0.995% | 0.695% | -0.1 | 6.0 | 1.0000 | 0.0050 |
| 60 | 8752 | 1637 | -51.7 | [-115.2, 16.5] | 48.0% | 4.236% | 3.936% | -0.5 | 9.7 | 1.0000 | 0.0050 |

**Mean excess by calendar year, h=5**

| Year | n | mean excess (bp) | hit rate |
|---|---|---|---|
| 2016 | 908 | -13.9 | 48.7% |
| 2017 | 563 | -23.4 | 48.0% |
| 2018 | 1285 | 3.7 | 51.1% |
| 2019 | 544 | -4.4 | 47.2% |
| 2020 | 624 | 49.8 | 51.9% |
| 2021 | 663 | 17.0 | 51.4% |
| 2022 | 976 | -12.1 | 51.5% |
| 2023 | 1028 | -29.8 | 47.1% |
| 2024 | 794 | -23.3 | 47.6% |
| 2025 | 896 | -19.8 | 48.3% |
| 2026 | 733 | -28.5 | 49.8% |

**Mean excess by calendar year, h=20**

| Year | n | mean excess (bp) | hit rate |
|---|---|---|---|
| 2016 | 908 | -18.4 | 49.3% |
| 2017 | 563 | -60.3 | 46.5% |
| 2018 | 1285 | 12.2 | 47.5% |
| 2019 | 544 | 81.1 | 51.3% |
| 2020 | 624 | -86.9 | 45.8% |
| 2021 | 663 | 50.5 | 49.5% |
| 2022 | 976 | -49.3 | 46.9% |
| 2023 | 1028 | -9.3 | 50.1% |
| 2024 | 794 | -76.5 | 43.6% |
| 2025 | 896 | -52.2 | 46.1% |
| 2026 | 709 | -81.7 | 47.1% |

### `breakout_52week`

Events after cooldown: 4915.

| h | n | dates | mean excess (bp) | 95% CI (bp) | hit rate | raw mean | raw mean - 30 bp | null mean (bp) | null std (bp) | p_high | p_low |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 4915 | 1478 | 1.8 | [-4.6, 8.0] | 50.3% | -0.000% | -0.300% | 0.0 | 1.8 | 0.1542 | 0.8507 |
| 5 | 4910 | 1476 | 7.7 | [-9.2, 25.2] | 49.9% | 0.223% | -0.077% | 0.1 | 4.5 | 0.0547 | 0.9502 |
| 10 | 4881 | 1472 | 20.9 | [-2.3, 45.4] | 50.1% | 0.615% | 0.315% | -0.2 | 6.7 | 0.0100 | 0.9950 |
| 20 | 4837 | 1462 | 14.6 | [-21.5, 52.0] | 48.1% | 0.823% | 0.523% | -0.3 | 9.1 | 0.0448 | 0.9602 |
| 60 | 4813 | 1448 | 31.4 | [-37.7, 100.4] | 48.2% | 3.169% | 2.869% | -0.6 | 16.4 | 0.0398 | 0.9652 |

**Mean excess by calendar year, h=5**

| Year | n | mean excess (bp) | hit rate |
|---|---|---|---|
| 2016 | 309 | -7.8 | 50.2% |
| 2017 | 687 | -24.8 | 46.1% |
| 2018 | 424 | 5.7 | 50.2% |
| 2019 | 425 | 6.6 | 56.0% |
| 2020 | 436 | -40.6 | 46.6% |
| 2021 | 529 | -0.9 | 47.8% |
| 2022 | 146 | 39.9 | 55.5% |
| 2023 | 460 | 8.6 | 50.4% |
| 2024 | 760 | 9.6 | 48.6% |
| 2025 | 342 | 41.2 | 51.5% |
| 2026 | 392 | 99.0 | 53.8% |

**Mean excess by calendar year, h=20**

| Year | n | mean excess (bp) | hit rate |
|---|---|---|---|
| 2016 | 309 | -73.6 | 41.7% |
| 2017 | 687 | -60.1 | 45.7% |
| 2018 | 424 | -15.0 | 47.9% |
| 2019 | 425 | 13.3 | 50.6% |
| 2020 | 436 | 65.3 | 50.0% |
| 2021 | 529 | -69.6 | 45.9% |
| 2022 | 146 | 101.1 | 55.5% |
| 2023 | 460 | 16.9 | 48.9% |
| 2024 | 760 | 65.1 | 47.5% |
| 2025 | 342 | 94.0 | 50.3% |
| 2026 | 319 | 124.7 | 51.7% |

### `low_vol_setup`

Events after cooldown: 9168.

| h | n | dates | mean excess (bp) | 95% CI (bp) | hit rate | raw mean | raw mean - 30 bp | null mean (bp) | null std (bp) | p_high | p_low |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 9168 | 1911 | -0.8 | [-3.1, 1.4] | 49.5% | -0.002% | -0.302% | -0.0 | 0.9 | 0.8060 | 0.1990 |
| 5 | 9165 | 1909 | -5.2 | [-13.0, 2.5] | 49.6% | 0.143% | -0.157% | 0.2 | 2.4 | 0.9900 | 0.0149 |
| 10 | 9163 | 1908 | -11.5 | [-26.9, 2.7] | 49.2% | 0.380% | 0.080% | 0.0 | 3.6 | 1.0000 | 0.0050 |
| 20 | 9161 | 1906 | -15.4 | [-44.8, 10.2] | 48.8% | 1.008% | 0.708% | -0.1 | 4.9 | 1.0000 | 0.0050 |
| 60 | 9109 | 1878 | -49.2 | [-104.6, 2.4] | 47.8% | 2.176% | 1.876% | -0.0 | 8.1 | 1.0000 | 0.0050 |

**Mean excess by calendar year, h=5**

| Year | n | mean excess (bp) | hit rate |
|---|---|---|---|
| 2016 | 1128 | -4.3 | 49.4% |
| 2017 | 2176 | 3.9 | 52.4% |
| 2018 | 813 | 19.5 | 50.1% |
| 2019 | 1189 | 5.3 | 53.3% |
| 2020 | 429 | -14.5 | 48.5% |
| 2021 | 831 | -2.5 | 49.8% |
| 2022 | 209 | -0.5 | 50.2% |
| 2023 | 621 | -21.2 | 45.6% |
| 2024 | 880 | -10.9 | 49.0% |
| 2025 | 650 | -48.3 | 40.2% |
| 2026 | 239 | -44.7 | 45.2% |

**Mean excess by calendar year, h=20**

| Year | n | mean excess (bp) | hit rate |
|---|---|---|---|
| 2016 | 1128 | -4.0 | 47.2% |
| 2017 | 2176 | 9.5 | 52.2% |
| 2018 | 813 | 61.3 | 54.4% |
| 2019 | 1189 | -14.5 | 50.3% |
| 2020 | 429 | -55.5 | 45.7% |
| 2021 | 831 | -14.9 | 47.9% |
| 2022 | 209 | -166.6 | 42.6% |
| 2023 | 621 | -55.5 | 45.6% |
| 2024 | 880 | -0.3 | 49.9% |
| 2025 | 650 | -99.3 | 41.5% |
| 2026 | 235 | -82.2 | 38.7% |

### `volume_trend_accumulation`

Events after cooldown: 14481.

| h | n | dates | mean excess (bp) | 95% CI (bp) | hit rate | raw mean | raw mean - 30 bp | null mean (bp) | null std (bp) | p_high | p_low |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 14481 | 2369 | 1.6 | [-2.1, 5.2] | 50.8% | 0.023% | -0.277% | -0.1 | 0.9 | 0.0299 | 0.9751 |
| 5 | 14465 | 2366 | 5.5 | [-2.8, 13.5] | 49.6% | 0.237% | -0.063% | 0.1 | 2.6 | 0.0299 | 0.9751 |
| 10 | 14411 | 2362 | 3.1 | [-9.6, 17.4] | 48.7% | 0.504% | 0.204% | -0.0 | 3.3 | 0.1692 | 0.8358 |
| 20 | 14285 | 2352 | -11.1 | [-35.8, 13.0] | 48.1% | 0.808% | 0.508% | 0.1 | 5.1 | 0.9851 | 0.0199 |
| 60 | 14160 | 2320 | -11.7 | [-57.6, 30.6] | 47.2% | 3.130% | 2.830% | -0.4 | 9.4 | 0.8756 | 0.1294 |

**Mean excess by calendar year, h=5**

| Year | n | mean excess (bp) | hit rate |
|---|---|---|---|
| 2016 | 1098 | -9.6 | 48.3% |
| 2017 | 1721 | -3.4 | 48.3% |
| 2018 | 1140 | 8.0 | 48.5% |
| 2019 | 1459 | 1.3 | 52.6% |
| 2020 | 1368 | -17.4 | 47.5% |
| 2021 | 1381 | 5.4 | 49.9% |
| 2022 | 837 | 25.0 | 53.0% |
| 2023 | 1254 | -4.8 | 49.6% |
| 2024 | 1887 | 12.7 | 48.2% |
| 2025 | 1181 | 25.8 | 50.5% |
| 2026 | 1139 | 28.2 | 50.7% |

**Mean excess by calendar year, h=20**

| Year | n | mean excess (bp) | hit rate |
|---|---|---|---|
| 2016 | 1098 | -75.3 | 42.7% |
| 2017 | 1721 | -42.9 | 46.5% |
| 2018 | 1140 | 16.6 | 51.9% |
| 2019 | 1459 | -6.6 | 49.7% |
| 2020 | 1368 | -14.3 | 45.9% |
| 2021 | 1381 | -38.5 | 46.3% |
| 2022 | 837 | 13.9 | 53.3% |
| 2023 | 1254 | -15.4 | 47.9% |
| 2024 | 1887 | -2.6 | 47.6% |
| 2025 | 1181 | 68.3 | 51.4% |
| 2026 | 959 | -6.5 | 48.3% |

## Notes

- Command: `scripts/research_event_study.py`.
- Null base seed 50000; bootstrap resamples 2000, seed 42.
- The universe benchmark uses all eligible symbols, not the setup's candidate pool; it is a same-date market/eligibility mean, not a sector- or size-matched benchmark.
- The event study has no stops, targets, position limits, slot competition or capital constraint; it cannot be read as a portfolio result.
