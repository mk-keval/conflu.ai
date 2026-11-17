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
