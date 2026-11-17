# D-84: Research signal-information and exit-shape studies (E1/E2)

**Date:** 2026-11-17
**Status:** Recorded. Exploratory only. These two tasks add read-only analysis tools and
their generated reports. No engine, indicator, setup, control, metric or runner file
changed; no committed result artifact changed; no live decision changed.
**Branch:** `research/baseline-backtesting`
**Commits:** E1 `687df51` — `research: add event-study tool and baseline signal information report`;
E2 `62abbef` — `research: add exit-shape study (trailing/time exits vs baseline)`; plus this
documentation commit (find it with `git log --oneline -- docs/DECISIONS/D-84-*.md`).
**Related:** [D-83](D-83-research-baseline-v4-seed-averaged.md),
[H-13 / H-14 and the trial ledger](../backtests/HYPOTHESIS_LOG.md),
[EVENT_STUDY.md](../backtests/research/EVENT_STUDY.md),
[EXIT_STUDY.md](../backtests/research/EXIT_STUDY.md),
[BASELINE_REPORT.md](../backtests/research/BASELINE_REPORT.md),
[research discovery work log](../SESSIONS/research-discovery-log.md),
[pre-registration template](../backtests/research/PREREGISTRATION_TEMPLATE.md).

---

## 1. Why these two tasks were run

Copied from the work log (`docs/SESSIONS/research-discovery-log.md`):

- E1: "The baseline measures a signal and an exit design together. E1 isolates the
  signal: it marks forward returns after every real setup signal with no stops,
  targets, position limits or portfolio rules, subtracts the same-date eligible
  universe mean, and compares the mean excess with matched-random event sets."
- E2: "The baseline's exits are tied to one design. E2 applies five exit variants to
  the SAME entries (signal at `t`, entry at the open of `t+1`, ATR14 of the signal
  bar, skip NaN/<=0) and compares each with matched-random entries under the same
  exit, one trade at a time. It ignores portfolio capacity and slot competition,
  and it cannot separate signal quality from the shared entries."

Both use the same D-82/D-83 panel contract: `download_daily` on `.cache/research`
over the requested span 2015-01-01 -> 2026-11-17, then `add_indicators`; `NON_TRADABLE`
excluded; signals from `SETUPS`; eligibility from `eligible()`; entry/evaluation from
2016-01-01.

## 2. Files added by E1 and E2

From the two commit stats and the work log:

| Task | Files |
|---|---|
| E1 (`687df51`) | `backend/app/research/events.py` (new), `scripts/research_event_study.py` (new), `backend/tests/test_research_events.py` (new), `docs/backtests/research/EVENT_STUDY.md` (generated), `docs/backtests/research/event_study/event_study_20261117_134829.json` (generated), `.github/workflows/research.yml` (test + ruff lists), `docs/SESSIONS/research-discovery-log.md` (work log) |
| E2 (`62abbef`) | `backend/app/research/exit_study.py` (new), `scripts/research_exit_study.py` (new), `backend/tests/test_research_exit_study.py` (new), `docs/backtests/research/EXIT_STUDY.md` (generated), `docs/backtests/research/event_study/exit_study_20261117_142553.json` (generated), `.github/workflows/research.yml` (test + ruff lists), `docs/SESSIONS/research-discovery-log.md` (work log) |

The new modules are pure (`backend/app/research/events.py`, `backend/app/research/exit_study.py`);
the scripts call `download_daily`, `add_indicators`, `SETUPS` and
`backend.app.research.control.matched_random_signals`.

## 3. Definitions (copied from the generated reports)

### E1 — `EVENT_STUDY.md`

- **Signal:** `SETUPS[name](df)` is True at the CLOSE of day `t`; entry row `e` is the symbol's NEXT bar (entry at the open of `t+1`).
- **Forward return for horizon `h` (trading days, `h >= 1`):** `ret_h = close[e+h-1] / open[e] - 1`. `h=1` is the entry day open-to-close; `h=5` holds through the 5th bar including the entry day. Horizons: 1, 5, 10, 20, 60. Rows where `close[e+h-1]` does not exist are dropped for that horizon (never filled).
- **Event:** signal at `t` AND `eligible(df)` at `t`, entry row `e` with `entry date >= 2016-01-01`. **Cooldown:** a repeat is dropped when the previous accepted event on the same symbol is at most `5` bars earlier (default 5), so accepted events are more than 5 bars apart.
- **Universe benchmark:** for each entry date `e`, the mean `ret_h` over ALL symbols that were eligible at their signal-day (the bar before `e`) and have the forward data. **Excess return** = event `ret_h` minus that same-date universe mean.
- **Statistics:** n events, n distinct entry dates, event-weighted mean excess (basis points), hit rate (share of events with excess > 0), raw mean return, raw mean minus 30 bps (a 15 bps/side round trip), 95% CI of the mean excess from a month-block bootstrap (resample entry year-months with replacement, 2000 resamples, seed 42), and the mean excess by calendar year for h=5 and h=20.
- **Null:** 200 matched-random event sets per setup from `backend.app.research.control.matched_random_signals` (same number of events per day, random eligible symbols), the same cooldown and statistics; seeds 50000..50199. `p_high = (count(null >= real)+1)/(n+1)`, `p_low = (count(null <= real)+1)/(n+1)` per horizon.
- **Panel:** loaded as the baseline runner does (`download_daily` with the `.cache/research` span 2015-01-01 -> latest, then `add_indicators`); `NON_TRADABLE` symbols are excluded. 2015 is warm-up; entries are evaluated from 2016-01-01.

Flags: `--setups`, `--horizons`, `--cooldown`, `--n-null`, `--report`, `--json-dir`.
Functions recorded in the work log: `forward_return_frame`, `eligibility_frame`,
`apply_cooldown`, `accepted_event_positions`, `collect_events`, `universe_benchmark`,
`month_block_bootstrap_ci`, `mean_excess`, `event_stats`, `p_values`, `null_distribution`.

### E2 — `EXIT_STUDY.md`

- **Entry (same as the engine):** a setup signal is True at the CLOSE of day `t`; the trade enters at the OPEN of `t+1`. ATR is `atr14` of the signal bar; entries with a NaN ATR or `ATR <= 0` are skipped.
- **1R:** always `2 * ATR` (the initial stop distance) for every variant, so R values are comparable even for variants without a stop.
- **Costs:** 15 bps per side using the engine's formula `r_net = (exit*(1-c) - entry*(1+c)) / (2*ATR)` with `c = 0.0015`; `r_gross` has no costs.
- **Stop order (engine rules):** gap stop at the open, then the stop, then the gap target, then the target, then the time exit at the close. The stop wins ties. A gap below the stop exits at the open; otherwise a stop hit exits at the stop price.
- **Trailing stop:** the entry bar uses only the initial stop. Each later bar `k` uses the highest HIGH of the open trade's bars from the entry bar through `k-1` minus the trail distance, never lowered. Bar `k`'s own high cannot move the stop used on bar `k` (no look-ahead); a spike on bar `k` raises the stop on bar `k+1`.
- **Panel end:** a trade whose path would run past the panel end is dropped, never marked to market.
- **Evaluation window:** entry date >= 2016-01-01 (2015 is indicator warm-up).
- **Null:** 100 matched-random entry sets per setup from `backend.app.research.control.matched_random_signals` (same daily count of eligible signals, random eligible symbols), the same entry and exit rules; seeds 60000..60099. Reported are the null mean/std of mean `r_net`, the gap `strategy - null mean`, `gap / null std`, and one-sided `p_high = (count(null >= real)+1)/(n+1)`, `p_low = (count(null <= real)+1)/(n+1)`.
- **Capacity caveat:** This analysis ignores portfolio capacity and slot competition: every signal is taken as an independent trade, with no limit on concurrent positions or capital.

| Variant | Rules |
|---|---|
| B0 | stop 2 ATR, target 3 ATR, max hold 15 (engine rules and order) |
| B1 | stop 2 ATR, no target, max hold 15 |
| B2 | stop 2 ATR plus 3 ATR trailing stop, no target, max hold 60 |
| B3 | stop 2 ATR plus 2 ATR trailing stop, no target, max hold 30 |
| B4 | no stop, no target, exit at the close of the 20th bar including entry (h=20) |

Flags: `--setups`, `--n-null`, `--report`, `--json-dir`.
Functions recorded in the work log: `ExitVariant`, `VARIANTS`, `trailing_stop_path`,
`simulate_trade`, `entry_candidates`, `simulate_entries`, `trade_stats`,
`null_summary`, `mask_ineligible`, `null_distributions`.

## 4. Panel and reference (copied verbatim)

E1:

| Item | Value |
|---|---|
| Requested span | 2015-01-01 -> 2026-11-17 |
| Actual panel | 2015-01-02 -> 2026-11-17 |
| Tradable symbols | 501 |
| Dropped at load | 2 |
| Evaluation start | 2016-01-01 |

| Item | Value |
|---|---|
| Window | 2016-01-04 -> 2026-11-17 |
| CAGR (calendar years) | 14.53% |
| Max drawdown (daily close) | -33.72% |
| Bars | 2735 |

The report labels the SPY row "SPY reference only (not compared to anything in this task)."

E2 panel: the same five rows (requested span, actual panel, 501 tradable, 2 dropped,
evaluation start 2016-01-01).

`BASELINE_REPORT.md` records: run date 2026-11-17 11:01; git commit `3bfb68c`;
window 2015-01-01 -> 2026-11-17; 501 symbols used; 2 dropped; costs 15.0 bps per side;
exit rules stop 2.0 ATR / target 3.0 ATR / max hold 15 bars; portfolio start equity
100000.0, risk 0.5%/trade, max 8 positions, max position 20.0% of equity.

## 5. E1 event results — h=5 and h=20 (copied verbatim)

Mean excess, null mean/std and the CI are in basis points; raw mean and raw mean minus
30 bps are returns. `p_high` tests the strategy against the null from above, `p_low`
from below.

| Setup | h | n | dates | mean excess (bp) | 95% CI (bp) | hit rate | raw mean | raw mean - 30 bp | null mean (bp) | null std (bp) | p_high | p_low |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| statistical_mean_reversion | 5 | 9014 | 1684 | -9.0 | [-21.6, 4.3] | 49.4% | 0.405% | 0.105% | -0.0 | 3.0 | 1.0000 | 0.0050 |
| statistical_mean_reversion | 20 | 8990 | 1673 | -26.1 | [-57.7, 3.4] | 47.6% | 0.995% | 0.695% | -0.1 | 6.0 | 1.0000 | 0.0050 |
| breakout_52week | 5 | 4910 | 1476 | 7.7 | [-9.2, 25.2] | 49.9% | 0.223% | -0.077% | 0.1 | 4.5 | 0.0547 | 0.9502 |
| breakout_52week | 20 | 4837 | 1462 | 14.6 | [-21.5, 52.0] | 48.1% | 0.823% | 0.523% | -0.3 | 9.1 | 0.0448 | 0.9602 |
| low_vol_setup | 5 | 9165 | 1909 | -5.2 | [-13.0, 2.5] | 49.6% | 0.143% | -0.157% | 0.2 | 2.4 | 0.9900 | 0.0149 |
| low_vol_setup | 20 | 9161 | 1906 | -15.4 | [-44.8, 10.2] | 48.8% | 1.008% | 0.708% | -0.1 | 4.9 | 1.0000 | 0.0050 |
| volume_trend_accumulation | 5 | 14465 | 2366 | 5.5 | [-2.8, 13.5] | 49.6% | 0.237% | -0.063% | 0.1 | 2.6 | 0.0299 | 0.9751 |
| volume_trend_accumulation | 20 | 14285 | 2352 | -11.1 | [-35.8, 13.0] | 48.1% | 0.808% | 0.508% | 0.1 | 5.1 | 0.9851 | 0.0199 |

Mean excess by calendar year, h=5 and h=20 (copied verbatim):

| Setup | Year | h=5 n | h=5 mean excess (bp) | h=5 hit rate | h=20 n | h=20 mean excess (bp) | h=20 hit rate |
|---|---|---|---|---|---|---|---|
| statistical_mean_reversion | 2016 | 908 | -13.9 | 48.7% | 908 | -18.4 | 49.3% |
| statistical_mean_reversion | 2017 | 563 | -23.4 | 48.0% | 563 | -60.3 | 46.5% |
| statistical_mean_reversion | 2018 | 1285 | 3.7 | 51.1% | 1285 | 12.2 | 47.5% |
| statistical_mean_reversion | 2019 | 544 | -4.4 | 47.2% | 544 | 81.1 | 51.3% |
| statistical_mean_reversion | 2020 | 624 | 49.8 | 51.9% | 624 | -86.9 | 45.8% |
| statistical_mean_reversion | 2021 | 663 | 17.0 | 51.4% | 663 | 50.5 | 49.5% |
| statistical_mean_reversion | 2022 | 976 | -12.1 | 51.5% | 976 | -49.3 | 46.9% |
| statistical_mean_reversion | 2023 | 1028 | -29.8 | 47.1% | 1028 | -9.3 | 50.1% |
| statistical_mean_reversion | 2024 | 794 | -23.3 | 47.6% | 794 | -76.5 | 43.6% |
| statistical_mean_reversion | 2025 | 896 | -19.8 | 48.3% | 896 | -52.2 | 46.1% |
| statistical_mean_reversion | 2026 | 733 | -28.5 | 49.8% | 709 | -81.7 | 47.1% |
| breakout_52week | 2016 | 309 | -7.8 | 50.2% | 309 | -73.6 | 41.7% |
| breakout_52week | 2017 | 687 | -24.8 | 46.1% | 687 | -60.1 | 45.7% |
| breakout_52week | 2018 | 424 | 5.7 | 50.2% | 424 | -15.0 | 47.9% |
| breakout_52week | 2019 | 425 | 6.6 | 56.0% | 425 | 13.3 | 50.6% |
| breakout_52week | 2020 | 436 | -40.6 | 46.6% | 436 | 65.3 | 50.0% |
| breakout_52week | 2021 | 529 | -0.9 | 47.8% | 529 | -69.6 | 45.9% |
| breakout_52week | 2022 | 146 | 39.9 | 55.5% | 146 | 101.1 | 55.5% |
| breakout_52week | 2023 | 460 | 8.6 | 50.4% | 460 | 16.9 | 48.9% |
| breakout_52week | 2024 | 760 | 9.6 | 48.6% | 760 | 65.1 | 47.5% |
| breakout_52week | 2025 | 342 | 41.2 | 51.5% | 342 | 94.0 | 50.3% |
| breakout_52week | 2026 | 392 | 99.0 | 53.8% | 319 | 124.7 | 51.7% |
| low_vol_setup | 2016 | 1128 | -4.3 | 49.4% | 1128 | -4.0 | 47.2% |
| low_vol_setup | 2017 | 2176 | 3.9 | 52.4% | 2176 | 9.5 | 52.2% |
| low_vol_setup | 2018 | 813 | 19.5 | 50.1% | 813 | 61.3 | 54.4% |
| low_vol_setup | 2019 | 1189 | 5.3 | 53.3% | 1189 | -14.5 | 50.3% |
| low_vol_setup | 2020 | 429 | -14.5 | 48.5% | 429 | -55.5 | 45.7% |
| low_vol_setup | 2021 | 831 | -2.5 | 49.8% | 831 | -14.9 | 47.9% |
| low_vol_setup | 2022 | 209 | -0.5 | 50.2% | 209 | -166.6 | 42.6% |
| low_vol_setup | 2023 | 621 | -21.2 | 45.6% | 621 | -55.5 | 45.6% |
| low_vol_setup | 2024 | 880 | -10.9 | 49.0% | 880 | -0.3 | 49.9% |
| low_vol_setup | 2025 | 650 | -48.3 | 40.2% | 650 | -99.3 | 41.5% |
| low_vol_setup | 2026 | 239 | -44.7 | 45.2% | 235 | -82.2 | 38.7% |
| volume_trend_accumulation | 2016 | 1098 | -9.6 | 48.3% | 1098 | -75.3 | 42.7% |
| volume_trend_accumulation | 2017 | 1721 | -3.4 | 48.3% | 1721 | -42.9 | 46.5% |
| volume_trend_accumulation | 2018 | 1140 | 8.0 | 48.5% | 1140 | 16.6 | 51.9% |
| volume_trend_accumulation | 2019 | 1459 | 1.3 | 52.6% | 1459 | -6.6 | 49.7% |
| volume_trend_accumulation | 2020 | 1368 | -17.4 | 47.5% | 1368 | -14.3 | 45.9% |
| volume_trend_accumulation | 2021 | 1381 | 5.4 | 49.9% | 1381 | -38.5 | 46.3% |
| volume_trend_accumulation | 2022 | 837 | 25.0 | 53.0% | 837 | 13.9 | 53.3% |
| volume_trend_accumulation | 2023 | 1254 | -4.8 | 49.6% | 1254 | -15.4 | 47.9% |
| volume_trend_accumulation | 2024 | 1887 | 12.7 | 48.2% | 1887 | -2.6 | 47.6% |
| volume_trend_accumulation | 2025 | 1181 | 25.8 | 50.5% | 1181 | 68.3 | 51.4% |
| volume_trend_accumulation | 2026 | 1139 | 28.2 | 50.7% | 959 | -6.5 | 48.3% |

Events after cooldown, copied verbatim: `statistical_mean_reversion` 9014;
`breakout_52week` 4915; `low_vol_setup` 9168; `volume_trend_accumulation` 14481.

## 6. E2 exit results — best and worst by mean `r_net` (copied verbatim)

Means, win/loss R and profit factor are in R units; `gap` is strategy mean `r_net`
minus the null mean.

| Rank by mean r_net | Setup | Variant | n | mean r_net | mean r_gross | null mean | null std | gap | gap/std | p_high | p_low |
|---|---|---|---|---|---|---|---|---|---|---|---|
| best | low_vol_setup | B4 | 18336 | 0.2463 | 0.3462 | 0.2153 | 0.0116 | 0.0310 | 2.66 | 0.0099 | 1.0000 |
| worst | breakout_52week | B3 | 6786 | -0.0484 | 0.0292 | 0.0016 | 0.0125 | -0.0500 | -4.02 | 1.0000 | 0.0099 |

B4 exits at the close of the 20th bar including the entry day, the same endpoint as the
event study's `h=20`. Entries considered before exit-variant drops, copied verbatim:
`statistical_mean_reversion` 16683; `breakout_52week` 6819; `low_vol_setup` 18346;
`volume_trend_accumulation` 20830. The full 4 × 5 table is in `EXIT_STUDY.md`.

## 7. Command evidence (copied verbatim from the work log)

E1 unit tests and full run:

```text
$ python -m pytest -q backend/tests/test_research_events.py
......                                                                   [100%]
6 passed in 1.53s
TEST_EXIT=0
```
```text
$ python scripts/research_event_study.py
... Panel: 2015-01-02 -> 2026-11-17, 501 tradable symbols, 2 dropped (cache hits=503, downloads=0)
Wrote docs\backtests\research\EVENT_STUDY.md and docs\backtests\research\event_study\event_study_20261117_134829.json
RUN_EXIT=0
ELAPSED_MIN=73.3
```

E1 end gate and exact CI commands:

```text
$ python -m pytest -q <explicit 10-file CI list + test_research_events.py>
110 passed in 10.49s
TEST_EXIT=0

$ python -m ruff check backend/app/research scripts
Found 6 errors.
GATE_RUFF_EXIT=1   # same six pre-existing W291 as above

$ python -m ruff check backend/app/research scripts/run_research_baseline.py scripts/make_baseline_report.py scripts/research_diagnostics.py scripts/research_event_study.py
All checks passed!
CI_RUFF_EXIT=0

$ python -m pytest -v <the explicit CI list>
110 passed in 10.02s
CI_TEST_EXIT=0
```

E2 unit tests and full run:

```text
$ python -m pytest -q backend/tests/test_research_exit_study.py
......                                                                   [100%]
6 passed in 1.56s
TEST_EXIT=0
```
```text
$ python scripts/research_exit_study.py
... Panel: 2015-01-02 -> 2026-11-17, 501 tradable symbols, 2 dropped (cache hits=503, downloads=0)
Wrote docs\backtests\research\EXIT_STUDY.md and docs\backtests\research\event_study\exit_study_20261117_142553.json
RUN_EXIT=0
ELAPSED_MIN=28.3
```

E2 end gate and exact CI commands:

```text
$ python -m pytest -q <explicit 11-file CI list>
116 passed in 11.82s
TEST_EXIT=0

$ python -m ruff check backend/app/research scripts
Found 6 errors.
GATE_RUFF_EXIT=1   # same six pre-existing W291 as E1

$ python -m ruff check backend/app/research scripts/run_research_baseline.py scripts/make_baseline_report.py scripts/research_diagnostics.py scripts/research_event_study.py scripts/research_exit_study.py
All checks passed!
CI_RUFF_EXIT=0

$ python -m pytest -v <the explicit 11-file CI list>
116 passed in 11.65s
CI_TEST_EXIT=0
```

E3 documentation-only task gates (start `116 passed in 10.40s` / `TEST_EXIT=0`,
`Found 6 errors.` / `GATE_RUFF_EXIT=1`, `All checks passed!` / `CI_RUFF_EXIT=0`;
end gate and exact CI commands below):

```text
=== END GATE: pytest -q (explicit 11-file CI list) ===
....................................................................................................................                                                                                      [100%]
116 passed in 10.21s
TEST_EXIT=0
=== END GATE: ruff check backend/app/research scripts ===
W291 [*] Trailing whitespace  --> scripts\run_pytest.py:11:30
W291 [*] Trailing whitespace  --> scripts\run_tests.py:10:30
W291 [*] Trailing whitespace  --> scripts\run_tests.py:11:36
W291 [*] Trailing whitespace  --> scripts\run_tests_final.py:18:36
W291 [*] Trailing whitespace  --> scripts\run_tests_fixed.py:24:40
W291 [*] Trailing whitespace  --> scripts\run_tests_isolated.py:24:40
Found 6 errors.
[*] 6 fixable with the `--fix` option.
GATE_RUFF_EXIT=1
=== EXACT CI: ruff check (workflow scope) ===
All checks passed!
CI_RUFF_EXIT=0
=== EXACT CI: pytest -v (workflow list) ===
backend/tests/test_make_baseline_report.py::test_verdict_seed_average_can_remove_candidate PASSED  [100%]
============================================================================================= 116 passed in 10.72s =============================================================================================
CI_TEST_EXIT=0
```

The six W291 lines above show locations only (full diagnostics are in the work log);
they are the same pre-existing failures listed in section 8. Full E3 command output is
in `docs/SESSIONS/research-discovery-log.md` (E3 entry).

## 8. Deviations, corrections and known gaps

Copied from the work log and the generated reports:

- "During the smoke run the first trailing-stop implementation used highs from
  before entry, which produced stop-outs on the entry bar; it was corrected to
  trail only the open trade and the full run above is from the corrected code."
- "Broad `ruff check backend/app/research scripts` still fails on six pre-existing
  `W291` warnings in unrelated `scripts/run_tests*.py` / `scripts/run_pytest.py`.
  Left untouched per user decision; the CI ruff scope is clean." The six locations
  recorded in E1 are `scripts\run_pytest.py:11:30`, `scripts\run_tests.py:10:30`,
  `scripts\run_tests.py:11:36`, `scripts\run_tests_final.py:18:36`,
  `scripts\run_tests_fixed.py:24:40`, `scripts\run_tests_isolated.py:24:40`.
- "PowerShell does not expand the `test_research_*.py` glob for native commands,
  so the same explicit list used by CI was passed to pytest."
- "No network downloads were needed; the full run used the existing cache
  (503 hits, 0 downloads)." (E1; E2 also recorded 503 cache hits, 0 downloads.)
- "The universe benchmark uses all eligible symbols, not the setup's candidate
  pool; it is a same-date market/eligibility mean, not a sector- or size-matched
  benchmark."
- "The event study has no stops, targets, position limits, slot competition or
  capital constraint; it cannot be read as a portfolio result."
- "This analysis ignores portfolio capacity and slot competition: every signal is
  taken as an independent trade, with no limit on concurrent positions or capital."
- "Variants share the same entries and the same signals are reused across variants
  and null draws, so the cells are not independent trials."
- "B0 must reproduce the engine's exit price, reason and `r_net` for the same entry;
  the unit tests check this against `run_portfolio` with `max_positions=1`."
- "Exploratory, in-sample, survivorship-biased universe (today's S&P 500). Not
  evidence of a live edge." (E1; E2 says "Exploratory, in-sample,
  survivorship-biased. Not evidence of a live edge.")
- "All four accounts reconcile / NO EVIDENCE OF EDGE" belongs to D-83's 20-seed
  baseline; D-84 does not replace that headline.

## 9. Not recorded

- Pre-registration written before E1 or E2: **not recorded**. The template added in
  E3 (`docs/backtests/research/PREREGISTRATION_TEMPLATE.md`) was written after both
  runs; H-13 and H-14 are therefore logged as EXPLORATORY.
- Code revision and dirty flag inside the two new JSON artifacts: **not recorded** in
  the generated markdown reports; only the D-83 baseline artifacts' `3bfb68c` /
  `dirty = false` are recorded in `BASELINE_REPORT.md` and D-83.
- Walk-forward or out-of-sample result for E1/E2: **not recorded**.
- Sector- or size-matched benchmark for E1: **not recorded** (the same-date eligible
  universe mean is the only benchmark used).
- Portfolio capacity / slot-competition result for E2: **not recorded**.
- Change to the D-75 pass bar, kill rule, scorecard or any FWD-v0.2 verdict:
  **not recorded** (none was made).

## 10. Decision

Record the two tools, their definitions, their generated numbers and their limits as
EXPLORATORY research (H-13, H-14). Do not wire either script into a live decision,
the D-75 pass bar, the kill rule, the forward scorecard or a FWD-v0.2 verdict. No
engine, indicator, setup, control, metric, runner or committed result artifact is
changed by D-84.
