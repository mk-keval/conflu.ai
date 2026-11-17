# Research discovery work log

Phase 2 analysis tools for the research harness. One entry per task.

---

## E1 — Event study (does the signal carry information, at which horizon?)

- **Date:** 2026-11-17
- **Task:** E1 (Phase 2). New files `backend/app/research/events.py`,
  `scripts/research_event_study.py`, `backend/tests/test_research_events.py`,
  generated `docs/backtests/research/EVENT_STUDY.md` and
  `docs/backtests/research/event_study/event_study_<timestamp>.json`; edit
  `.github/workflows/research.yml`.

### What changed and why

The baseline measures a signal and an exit design together. E1 isolates the
signal: it marks forward returns after every real setup signal with no stops,
targets, position limits or portfolio rules, subtracts the same-date eligible
universe mean, and compares the mean excess with matched-random event sets.

- `backend/app/research/events.py` (pure, no I/O): `forward_return_frame`,
  `eligibility_frame`, `apply_cooldown`, `accepted_event_positions`,
  `collect_events`, `universe_benchmark`, `month_block_bootstrap_ci`,
  `mean_excess`, `event_stats`, `p_values`, `null_distribution`.
- `scripts/research_event_study.py`: loads the panel the same way as the
  baseline runner (`download_daily` on `.cache/research`, requested span
  2015-01-01 -> today, then `add_indicators`), builds the same-date universe
  benchmark, runs the real events and the matched-random null, and writes the
  markdown report plus a JSON under the `event_study/` sub-folder (which the
  top-level-only baseline report loader ignores). Flags: `--setups`,
  `--horizons`, `--cooldown`, `--n-null`, `--report`, `--json-dir`.
- `backend/tests/test_research_events.py`: six synthetic-panel tests —
  forward-return alignment / tail drop, all-eligible event set has zero mean
  excess, cooldown removes back-to-back events, month-block bootstrap is
  deterministic and contains the mean, no future leakage, and null p-values lie
  in `(0, 1]`.
- `.github/workflows/research.yml`: added `scripts/research_event_study.py` to
  the ruff list and `backend/tests/test_research_events.py` to the test list.

### Commands, exact output

Start-of-task gate (pre-existing broad ruff failure documented below):

```text
$ python -m pytest -q backend/tests/test_research_*.py backend/tests/test_make_baseline_report.py
104 passed in 10.35s
TEST_EXIT=0

$ python -m ruff check backend/app/research scripts
W291 [*] Trailing whitespace  --> scripts\run_pytest.py:11:30
W291 [*] Trailing whitespace  --> scripts\run_tests.py:10:30
W291 [*] Trailing whitespace  --> scripts\run_tests.py:11:36
W291 [*] Trailing whitespace  --> scripts\run_tests_final.py:18:36
W291 [*] Trailing whitespace  --> scripts\run_tests_fixed.py:24:40
W291 [*] Trailing whitespace  --> scripts\run_tests_isolated.py:24:40
Found 6 errors.
RUFF_EXIT=1
```

These six warnings are pre-existing in tracked files untouched by Phase 2 (last
changed in `0a09e75`, tree clean before E1). The user approved leaving them and
using the CI ruff scope. The exact CI ruff scope passes.

Event-study unit tests:

```text
$ python -m pytest -q backend/tests/test_research_events.py
......                                                                   [100%]
6 passed in 1.53s
TEST_EXIT=0
```

Full run on all four setups with defaults:

```text
$ python scripts/research_event_study.py
Loading panel 2015-01-01 -> 2026-11-17 from .cache/research
Panel: 2015-01-02 -> 2026-11-17, 501 tradable symbols, 2 dropped (cache hits=503, downloads=0)
Building eligibility and forward-return frames
Universe benchmark dates: 2735
[statistical_mean_reversion] events after cooldown: 9014
[statistical_mean_reversion] h=1: n=9014 mean excess=-1.4 bp p_high=0.8507 p_low=0.1542
[statistical_mean_reversion] h=5: n=9014 mean excess=-9.0 bp p_high=1.0000 p_low=0.0050
[statistical_mean_reversion] h=10: n=9010 mean excess=-15.6 bp p_high=1.0000 p_low=0.0050
[statistical_mean_reversion] h=20: n=8990 mean excess=-26.1 bp p_high=1.0000 p_low=0.0050
[statistical_mean_reversion] h=60: n=8752 mean excess=-51.7 bp p_high=1.0000 p_low=0.0050
[breakout_52week] events after cooldown: 4915
[breakout_52week] h=1: n=4915 mean excess=+1.8 bp p_high=0.1542 p_low=0.8507
[breakout_52week] h=5: n=4910 mean excess=+7.7 bp p_high=0.0547 p_low=0.9502
[breakout_52week] h=10: n=4881 mean excess=+20.9 bp p_high=0.0100 p_low=0.9950
[breakout_52week] h=20: n=4837 mean excess=+14.6 bp p_high=0.0448 p_low=0.9602
[breakout_52week] h=60: n=4813 mean excess=+31.4 bp p_high=0.0398 p_low=0.9652
[low_vol_setup] events after cooldown: 9168
[low_vol_setup] h=1: n=9168 mean excess=-0.8 bp p_high=0.8060 p_low=0.1990
[low_vol_setup] h=5: n=9165 mean excess=-5.2 bp p_high=0.9900 p_low=0.0149
[low_vol_setup] h=10: n=9163 mean excess=-11.5 bp p_high=1.0000 p_low=0.0050
[low_vol_setup] h=20: n=9161 mean excess=-15.4 bp p_high=1.0000 p_low=0.0050
[low_vol_setup] h=60: n=9109 mean excess=-49.2 bp p_high=1.0000 p_low=0.0050
[volume_trend_accumulation] events after cooldown: 14481
[volume_trend_accumulation] h=1: n=14481 mean excess=+1.6 bp p_high=0.0299 p_low=0.9751
[volume_trend_accumulation] h=5: n=14465 mean excess=+5.5 bp p_high=0.0299 p_low=0.9751
[volume_trend_accumulation] h=10: n=14411 mean excess=+3.1 bp p_high=0.1692 p_low=0.8358
[volume_trend_accumulation] h=20: n=14285 mean excess=-11.1 bp p_high=0.9851 p_low=0.0199
[volume_trend_accumulation] h=60: n=14160 mean excess=-11.7 bp p_high=0.8756 p_low=0.1294
Wrote docs\backtests\research\EVENT_STUDY.md and docs\backtests\research\event_study\event_study_20261117_134829.json
RUN_EXIT=0
ELAPSED_MIN=73.3
```

End-of-task gate:

```text
$ python -m pytest -q backend/tests/test_research_*.py backend/tests/test_make_baseline_report.py
110 passed in 10.49s
TEST_EXIT=0

$ python -m ruff check backend/app/research scripts
Found 6 errors.
GATE_RUFF_EXIT=1   # same six pre-existing W291 as above

$ python -m ruff check backend/app/research scripts/run_research_baseline.py scripts/make_baseline_report.py scripts/research_diagnostics.py scripts/research_event_study.py
All checks passed!
CI_RUFF_EXIT=0
```

Exact CI workflow commands run locally:

```text
$ python -m ruff check backend/app/research scripts/run_research_baseline.py scripts/make_baseline_report.py scripts/research_diagnostics.py scripts/research_event_study.py
All checks passed!
CI_RUFF_EXIT=0

$ python -m pytest -v backend/tests/test_research_control.py backend/tests/test_research_data.py backend/tests/test_research_diagnostics.py backend/tests/test_research_engine.py backend/tests/test_research_events.py backend/tests/test_research_indicators.py backend/tests/test_research_metrics.py backend/tests/test_research_runner.py backend/tests/test_research_setups.py backend/tests/test_make_baseline_report.py
...
110 passed in 10.02s
CI_TEST_EXIT=0
```

### Files touched

- `backend/app/research/events.py` (new)
- `scripts/research_event_study.py` (new)
- `backend/tests/test_research_events.py` (new)
- `docs/backtests/research/EVENT_STUDY.md` (generated)
- `docs/backtests/research/event_study/event_study_20261117_134829.json` (generated)
- `.github/workflows/research.yml` (test + ruff lists)
- `docs/SESSIONS/research-discovery-log.md` (this entry)

### Skipped / notes

- Broad `ruff check backend/app/research scripts` still fails on six
  pre-existing `W291` warnings in unrelated `scripts/run_tests*.py` /
  `scripts/run_pytest.py`. Left untouched per user decision; the CI ruff scope
  is clean.
- No network downloads were needed; the full run used the existing cache
  (503 hits, 0 downloads).

---

## E2 — Exit-shape study (are our exits wasting a real signal?)

- **Date:** 2026-11-17
- **Task:** E2 (Phase 2). New files `backend/app/research/exit_study.py`,
  `scripts/research_exit_study.py`, `backend/tests/test_research_exit_study.py`,
  generated `docs/backtests/research/EXIT_STUDY.md` and
  `docs/backtests/research/event_study/exit_study_<timestamp>.json`; edit
  `.github/workflows/research.yml`. Precondition E1 was committed as `687df51`.

### What changed and why

The baseline's exits are tied to one design. E2 applies five exit variants to
the SAME entries (signal at `t`, entry at the open of `t+1`, ATR14 of the signal
bar, skip NaN/<=0) and compares each with matched-random entries under the same
exit, one trade at a time. It ignores portfolio capacity and slot competition,
and it cannot separate signal quality from the shared entries.

- `backend/app/research/exit_study.py` (pure): `ExitVariant`/`VARIANTS` (B0-B4),
  `trailing_stop_path`, `simulate_trade`, `entry_candidates`,
  `simulate_entries`, `trade_stats`, `null_summary`, `mask_ineligible` and
  `null_distributions`. 1R is always `2 * ATR`; costs are 15 bps per side with
  the engine's `r_net`/`r_gross` formulas. Stop order is the engine's (gap stop,
  stop, gap target, target, time; stop wins ties). The trailing stop uses the
  open trade's highs through the previous bar, is never lowered, and does not
  use the current bar's high. Trades running past the panel end are dropped.
- `scripts/research_exit_study.py`: loads the panel exactly as the baseline
  runner does, builds the same eligibility frame, runs B0-B4 on the real
  entries and on 100 matched-random sets (seeds 60000..60099), then writes the
  markdown report and JSON under `event_study/`. Flags: `--setups`, `--n-null`,
  `--report`, `--json-dir`.
- `backend/tests/test_research_exit_study.py`: six deterministic synthetic
  tests — B0 equals `run_portfolio(max_positions=1)` on exit price/reason/r_net,
  trailing stop never decreases, a spike on bar `k` moves only bar `k+1`'s stop,
  a gap below the stop exits at the open, B4 exits at the close of the 20th bar
  including the entry day, and trades past the panel end are dropped.
- `.github/workflows/research.yml`: added `scripts/research_exit_study.py` to
  the ruff list and `backend/tests/test_research_exit_study.py` to the tests.

### Commands, exact output

Unit tests:

```text
$ python -m pytest -q backend/tests/test_research_exit_study.py
......                                                                   [100%]
6 passed in 1.56s
TEST_EXIT=0

$ python -m ruff check backend/app/research/exit_study.py scripts/research_exit_study.py
All checks passed!
RUFF_EXIT=0
```

Full run on all four setups with defaults:

```text
$ python scripts/research_exit_study.py
Loading panel 2015-01-01 -> 2026-11-17 from .cache/research
Panel: 2015-01-02 -> 2026-11-17, 501 tradable symbols, 2 dropped (cache hits=503, downloads=0)
Building eligibility
Eligibility dates: 2987
[statistical_mean_reversion] entries: 16683
[statistical_mean_reversion] B0: n=16659 mean r_net=+0.0494 mean r_gross=+0.1103
[statistical_mean_reversion] B1: n=16651 mean r_net=+0.0331 mean r_gross=+0.0939
[statistical_mean_reversion] B2: n=16593 mean r_net=+0.1545 mean r_gross=+0.2155
[statistical_mean_reversion] B3: n=16668 mean r_net=+0.0453 mean r_gross=+0.1061
[statistical_mean_reversion] B4: n=16639 mean r_net=+0.0649 mean r_gross=+0.1258
[statistical_mean_reversion] null draws 100/100
[statistical_mean_reversion] B0: null mean=+0.0758 gap=-0.0264 gap/std=-3.87 p_high=1.0000 p_low=0.0099
[statistical_mean_reversion] B1: null mean=+0.0715 gap=-0.0384 gap/std=-4.89 p_high=1.0000 p_low=0.0099
[statistical_mean_reversion] B2: null mean=+0.1763 gap=-0.0218 gap/std=-2.22 p_high=0.9901 p_low=0.0198
[statistical_mean_reversion] B3: null mean=+0.0617 gap=-0.0164 gap/std=-2.10 p_high=0.9901 p_low=0.0198
[statistical_mean_reversion] B4: null mean=+0.1191 gap=-0.0542 gap/std=-5.03 p_high=1.0000 p_low=0.0099
[breakout_52week] entries: 6819
[breakout_52week] B0: n=6772 mean r_net=-0.0018 mean r_gross=+0.0760
[breakout_52week] B1: n=6754 mean r_net=+0.0010 mean r_gross=+0.0788
[breakout_52week] B2: n=6754 mean r_net=+0.0127 mean r_gross=+0.0904
[breakout_52week] B3: n=6786 mean r_net=-0.0484 mean r_gross=+0.0292
[breakout_52week] B4: n=6712 mean r_net=+0.0641 mean r_gross=+0.1421
[breakout_52week] null draws 100/100
[breakout_52week] B0: null mean=+0.0250 gap=-0.0268 gap/std=-2.16 p_high=1.0000 p_low=0.0099
[breakout_52week] B1: null mean=+0.0290 gap=-0.0280 gap/std=-2.18 p_high=0.9802 p_low=0.0297
[breakout_52week] B2: null mean=+0.0819 gap=-0.0692 gap/std=-3.90 p_high=1.0000 p_low=0.0099
[breakout_52week] B3: null mean=+0.0016 gap=-0.0500 gap/std=-4.02 p_high=1.0000 p_low=0.0099
[breakout_52week] B4: null mean=+0.0609 gap=+0.0032 gap/std=+0.18 p_high=0.4653 p_low=0.5446
[low_vol_setup] entries: 18346
[low_vol_setup] B0: n=18338 mean r_net=+0.0572 mean r_gross=+0.1568
[low_vol_setup] B1: n=18338 mean r_net=+0.0998 mean r_gross=+0.1994
[low_vol_setup] B2: n=18330 mean r_net=+0.1887 mean r_gross=+0.2883
[low_vol_setup] B3: n=18335 mean r_net=+0.0604 mean r_gross=+0.1599
[low_vol_setup] B4: n=18336 mean r_net=+0.2463 mean r_gross=+0.3462
[low_vol_setup] null draws 100/100
[low_vol_setup] B0: null mean=+0.0616 gap=-0.0044 gap/std=-0.61 p_high=0.7030 p_low=0.3069
[low_vol_setup] B1: null mean=+0.1006 gap=-0.0008 gap/std=-0.09 p_high=0.5347 p_low=0.4752
[low_vol_setup] B2: null mean=+0.1653 gap=+0.0234 gap/std=+2.09 p_high=0.0297 p_low=0.9802
[low_vol_setup] B3: null mean=+0.0511 gap=+0.0093 gap/std=+1.20 p_high=0.1188 p_low=0.8911
[low_vol_setup] B4: null mean=+0.2153 gap=+0.0310 gap/std=+2.66 p_high=0.0099 p_low=1.0000
[volume_trend_accumulation] entries: 20830
[volume_trend_accumulation] B0: n=20696 mean r_net=+0.0161 mean r_gross=+0.0927
[volume_trend_accumulation] B1: n=20635 mean r_net=+0.0085 mean r_gross=+0.0851
[volume_trend_accumulation] B2: n=20633 mean r_net=+0.0554 mean r_gross=+0.1318
[volume_trend_accumulation] B3: n=20750 mean r_net=-0.0095 mean r_gross=+0.0669
[volume_trend_accumulation] B4: n=20536 mean r_net=+0.0809 mean r_gross=+0.1576
[volume_trend_accumulation] null draws 100/100
[volume_trend_accumulation] B0: null mean=+0.0360 gap=-0.0199 gap/std=-2.81 p_high=1.0000 p_low=0.0099
[volume_trend_accumulation] B1: null mean=+0.0497 gap=-0.0412 gap/std=-5.37 p_high=1.0000 p_low=0.0099
[volume_trend_accumulation] B2: null mean=+0.1073 gap=-0.0519 gap/std=-5.05 p_high=1.0000 p_low=0.0099
[volume_trend_accumulation] B3: null mean=+0.0184 gap=-0.0280 gap/std=-3.73 p_high=1.0000 p_low=0.0099
[volume_trend_accumulation] B4: null mean=+0.1164 gap=-0.0355 gap/std=-3.59 p_high=1.0000 p_low=0.0099
Wrote docs\backtests\research\EXIT_STUDY.md and docs\backtests\research\event_study\exit_study_20261117_142553.json
RUN_EXIT=0
ELAPSED_MIN=28.3
```

End-of-task gate (PowerShell does not expand the `test_research_*.py` glob for
native commands, so the same explicit list used by CI was passed to pytest):

```text
$ python -m pytest -q <the CI list, including test_research_exit_study.py>
116 passed in 11.82s
TEST_EXIT=0

$ python -m ruff check backend/app/research scripts
Found 6 errors.
GATE_RUFF_EXIT=1   # same six pre-existing W291 as E1

$ python -m ruff check backend/app/research scripts/run_research_baseline.py scripts/make_baseline_report.py scripts/research_diagnostics.py scripts/research_event_study.py scripts/research_exit_study.py
All checks passed!
CI_RUFF_EXIT=0
```

Exact CI workflow commands run locally:

```text
$ python -m ruff check backend/app/research scripts/run_research_baseline.py scripts/make_baseline_report.py scripts/research_diagnostics.py scripts/research_event_study.py scripts/research_exit_study.py
All checks passed!
CI_RUFF_EXIT=0

$ python -m pytest -v <the CI list, including test_research_exit_study.py>
116 passed in 11.65s
CI_TEST_EXIT=0
```

### Files touched

- `backend/app/research/exit_study.py` (new)
- `scripts/research_exit_study.py` (new)
- `backend/tests/test_research_exit_study.py` (new)
- `docs/backtests/research/EXIT_STUDY.md` (generated)
- `docs/backtests/research/event_study/exit_study_20261117_142553.json` (generated)
- `.github/workflows/research.yml` (test + ruff lists)
- `docs/SESSIONS/research-discovery-log.md` (this entry)

### Skipped / notes

- Broad `ruff check backend/app/research scripts` still fails on the same six
  pre-existing `W291` warnings; left untouched per user decision.
- No network downloads were needed (503 cache hits, 0 downloads).
- During the smoke run the first trailing-stop implementation used highs from
  before entry, which produced stop-outs on the entry bar; it was corrected to
  trail only the open trade and the full run above is from the corrected code.
- No baseline engine/indicator/setup/control/metrics/runner files or committed
  result artifacts were modified.
