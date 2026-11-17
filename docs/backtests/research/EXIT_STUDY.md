# Exit Study — same entries, different exits

Generated `2026-11-17T13:57:35` by `scripts/research_exit_study.py`.

Exploratory, in-sample, survivorship-biased. Not evidence of a live edge.

This analysis ignores portfolio capacity and slot competition: every signal is taken as an independent trade, with no limit on concurrent positions or capital.

## Definitions

- **Entry (same as the engine):** a setup signal is True at the CLOSE of day `t`; the trade enters at the OPEN of `t+1`. ATR is `atr14` of the signal bar; entries with a NaN ATR or `ATR <= 0` are skipped.
- **1R:** always `2 * ATR` (the initial stop distance) for every variant, so R values are comparable even for variants without a stop.
- **Costs:** 15 bps per side using the engine's formula `r_net = (exit*(1-c) - entry*(1+c)) / (2*ATR)` with `c = 0.0015`; `r_gross` has no costs.
- **Stop order (engine rules):** gap stop at the open, then the stop, then the gap target, then the target, then the time exit at the close. The stop wins ties. A gap below the stop exits at the open; otherwise a stop hit exits at the stop price.
- **Trailing stop:** the entry bar uses only the initial stop. Each later bar `k` uses the highest HIGH of the open trade's bars from the entry bar through `k-1` minus the trail distance, never lowered. Bar `k`'s own high cannot move the stop used on bar `k` (no look-ahead); a spike on bar `k` raises the stop on bar `k+1`.
- **Panel end:** a trade whose path would run past the panel end is dropped, never marked to market.
- **Evaluation window:** entry date >= 2016-01-01 (2015 is indicator warm-up).
- **Null:** 100 matched-random entry sets per setup from `backend.app.research.control.matched_random_signals` (same daily count of eligible signals, random eligible symbols), the same entry and exit rules; seeds 60000..60099. Reported are the null mean/std of mean `r_net`, the gap `strategy - null mean`, `gap / null std`, and one-sided `p_high = (count(null >= real)+1)/(n+1)`, `p_low = (count(null <= real)+1)/(n+1)`.
- **Capacity caveat:** This analysis ignores portfolio capacity and slot competition: every signal is taken as an independent trade, with no limit on concurrent positions or capital.

### Exit variants

| Variant | Rules |
|---|---|
| B0 | stop 2 ATR, target 3 ATR, max hold 15 (engine rules and order) |
| B1 | stop 2 ATR, no target, max hold 15 |
| B2 | stop 2 ATR plus 3 ATR trailing stop, no target, max hold 60 |
| B3 | stop 2 ATR plus 2 ATR trailing stop, no target, max hold 30 |
| B4 | no stop, no target, exit at the close of the 20th bar including entry (h=20) |

## Panel

| Item | Value |
|---|---|
| Requested span | 2015-01-01 -> 2026-11-17 |
| Actual panel | 2015-01-02 -> 2026-11-17 |
| Tradable symbols | 501 |
| Dropped at load | 2 |
| Evaluation start | 2016-01-01 |

## Results

Means, win/loss R and profit factor are in R units; `gap` is strategy mean `r_net` minus the null mean. Exit shares are of that variant's closed trades.

### `statistical_mean_reversion`

Entries considered before exit-variant drops: 16683.

| Variant | n | mean r_net | mean r_gross | win rate | avg win R | avg loss R | profit factor | mean bars | exits | null mean | null std | gap | gap/std | p_high | p_low |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | 16659 | 0.0494 | 0.1103 | 50.0% | 1.0719 | -0.9713 | 1.10 | 9.19 | stop 32.1%; stop_gap 7.6%; target 23.3%; target_gap 4.4%; time 32.6% | 0.0758 | 0.0068 | -0.0264 | -3.87 | 1.0000 | 0.0099 |
| B1 | 16651 | 0.0331 | 0.0939 | 47.2% | 1.1555 | -0.9713 | 1.06 | 11.11 | stop 33.3%; stop_gap 8.2%; time 58.5% | 0.0715 | 0.0079 | -0.0384 | -4.89 | 1.0000 | 0.0099 |
| B2 | 16593 | 0.1545 | 0.2155 | 38.8% | 1.7556 | -0.8608 | 1.29 | 20.22 | stop 75.8%; stop_gap 16.1%; time 8.2% | 0.1763 | 0.0098 | -0.0218 | -2.22 | 0.9901 | 0.0198 |
| B3 | 16668 | 0.0453 | 0.1061 | 39.7% | 1.1154 | -0.6596 | 1.11 | 9.74 | stop 77.5%; stop_gap 15.9%; time 6.6% | 0.0617 | 0.0078 | -0.0164 | -2.10 | 0.9901 | 0.0198 |
| B4 | 16639 | 0.0649 | 0.1258 | 56.2% | 1.2614 | -1.4685 | 1.10 | 19.00 | time 100.0% | 0.1191 | 0.0108 | -0.0542 | -5.03 | 1.0000 | 0.0099 |

### `breakout_52week`

Entries considered before exit-variant drops: 6819.

| Variant | n | mean r_net | mean r_gross | win rate | avg win R | avg loss R | profit factor | mean bars | exits | null mean | null std | gap | gap/std | p_high | p_low |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | 6772 | -0.0018 | 0.0760 | 47.2% | 1.0959 | -0.9847 | 1.00 | 8.72 | stop 36.9%; stop_gap 5.9%; target 23.5%; target_gap 4.8%; time 28.9% | 0.0250 | 0.0124 | -0.0268 | -2.16 | 1.0000 | 0.0099 |
| B1 | 6754 | 0.0010 | 0.0788 | 44.0% | 1.2475 | -0.9768 | 1.00 | 10.87 | stop 38.8%; stop_gap 6.2%; time 55.0% | 0.0290 | 0.0128 | -0.0280 | -2.18 | 0.9802 | 0.0297 |
| B2 | 6754 | 0.0127 | 0.0904 | 34.9% | 1.6478 | -0.8644 | 1.02 | 15.90 | stop 82.6%; stop_gap 14.5%; time 2.9% | 0.0819 | 0.0178 | -0.0692 | -3.90 | 1.0000 | 0.0099 |
| B3 | 6786 | -0.0484 | 0.0292 | 36.5% | 1.0489 | -0.6795 | 0.89 | 8.20 | stop 82.3%; stop_gap 15.0%; time 2.7% | 0.0016 | 0.0125 | -0.0500 | -4.02 | 1.0000 | 0.0099 |
| B4 | 6712 | 0.0641 | 0.1421 | 52.8% | 1.3359 | -1.3603 | 1.10 | 19.00 | time 100.0% | 0.0609 | 0.0181 | 0.0032 | 0.18 | 0.4653 | 0.5446 |

### `low_vol_setup`

Entries considered before exit-variant drops: 18346.

| Variant | n | mean r_net | mean r_gross | win rate | avg win R | avg loss R | profit factor | mean bars | exits | null mean | null std | gap | gap/std | p_high | p_low |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | 18338 | 0.0572 | 0.1568 | 50.0% | 1.1226 | -1.0075 | 1.11 | 9.29 | stop 35.9%; stop_gap 5.3%; target 27.8%; target_gap 4.0%; time 27.0% | 0.0616 | 0.0072 | -0.0044 | -0.61 | 0.7030 | 0.3069 |
| B1 | 18338 | 0.0998 | 0.1994 | 47.7% | 1.3015 | -0.9954 | 1.19 | 11.35 | stop 36.8%; stop_gap 5.5%; time 57.7% | 0.1006 | 0.0085 | -0.0008 | -0.09 | 0.5347 | 0.4752 |
| B2 | 18330 | 0.1887 | 0.2883 | 39.9% | 1.8304 | -0.8994 | 1.35 | 17.96 | stop 82.6%; stop_gap 13.7%; time 3.7% | 0.1653 | 0.0112 | 0.0234 | 2.09 | 0.0297 | 0.9802 |
| B3 | 18335 | 0.0604 | 0.1599 | 39.0% | 1.2322 | -0.6883 | 1.14 | 9.71 | stop 83.2%; stop_gap 12.9%; time 3.9% | 0.0511 | 0.0078 | 0.0093 | 1.20 | 0.1188 | 0.8911 |
| B4 | 18336 | 0.2463 | 0.3462 | 57.2% | 1.4390 | -1.3465 | 1.43 | 19.00 | time 100.0% | 0.2153 | 0.0116 | 0.0310 | 2.66 | 0.0099 | 1.0000 |

### `volume_trend_accumulation`

Entries considered before exit-variant drops: 20830.

| Variant | n | mean r_net | mean r_gross | win rate | avg win R | avg loss R | profit factor | mean bars | exits | null mean | null std | gap | gap/std | p_high | p_low |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | 20696 | 0.0161 | 0.0927 | 47.8% | 1.1016 | -0.9785 | 1.03 | 8.91 | stop 36.2%; stop_gap 5.8%; target 24.1%; target_gap 4.3%; time 29.5% | 0.0360 | 0.0071 | -0.0199 | -2.81 | 1.0000 | 0.0099 |
| B1 | 20635 | 0.0085 | 0.0851 | 44.9% | 1.2104 | -0.9700 | 1.02 | 10.99 | stop 37.6%; stop_gap 6.2%; time 56.3% | 0.0497 | 0.0077 | -0.0412 | -5.37 | 1.0000 | 0.0099 |
| B2 | 20633 | 0.0554 | 0.1318 | 36.6% | 1.6615 | -0.8725 | 1.10 | 17.04 | stop 81.4%; stop_gap 14.8%; time 3.8% | 0.1073 | 0.0103 | -0.0519 | -5.05 | 1.0000 | 0.0099 |
| B3 | 20750 | -0.0095 | 0.0669 | 37.7% | 1.0966 | -0.6795 | 0.98 | 8.86 | stop 80.9%; stop_gap 15.1%; time 4.0% | 0.0184 | 0.0075 | -0.0280 | -3.73 | 1.0000 | 0.0099 |
| B4 | 20536 | 0.0809 | 0.1576 | 53.9% | 1.3109 | -1.3548 | 1.13 | 19.00 | time 100.0% | 0.1164 | 0.0099 | -0.0355 | -3.59 | 1.0000 | 0.0099 |

## Notes

- Command: `scripts/research_exit_study.py`.
- Null base seed 60000; costs 15 bps per side.
- B0 must reproduce the engine's exit price, reason and `r_net` for the same entry; the unit tests check this against `run_portfolio` with `max_positions=1`.
- B4 exits at the close of the 20th bar including the entry day, the same endpoint as the event study's `h=20`.
- Variants share the same entries and the same signals are reused across variants and null draws, so the cells are not independent trials.
