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

---

## E3 — Documentation record (D-84, H-13/H-14, trial ledger, pre-registration template)

- **Date:** 2026-11-17
- **Task:** E3 (Phase 2). Docs-only. Preconditions E1 `687df51` and E2 `62abbef` are
  committed locally; no push.
- **What changed and why:** record the two Phase 2 studies in one decision record
  (D-84), log the two questions as H-13/H-14 with EXPLORATORY labels, add a trial
  ledger (E1 `4 setups × 5 horizons = 20` cells; E2 `4 setups × 5 variants = 20`
  cells), add a fill-in pre-registration template for future runs, and add one-line
  pointers from the five existing indexes/notes. Every number is copied verbatim from
  `EVENT_STUDY.md`, `EXIT_STUDY.md`, `BASELINE_REPORT.md` or this work log; fields with
  no recorded value say "not recorded"; no interpretation was added. No code, test,
  workflow or committed artifact changed.

### Files touched

- `docs/DECISIONS/D-84-research-signal-information-and-exit-shape.md` (new)
- `docs/backtests/HYPOTHESIS_LOG.md` (H-13/H-14 rows + details, trial ledger, change log)
- `docs/backtests/research/PREREGISTRATION_TEMPLATE.md` (new)
- `docs/backtests/research/README.md` (pointer)
- `docs/backtests/research/VALIDITY_NOTES.md` (pointer)
- `docs/DECISIONS/index.md` (D-84 pointer)
- `docs/index.md` (D-84 pointer)
- `INDEX.md` (D-84 pointer)
- `docs/SESSIONS/research-discovery-log.md` (this entry)

### Commands, exact output

Start-of-task gate (broad ruff failure is the same pre-existing six `W291` warnings):

```text
....................................................................................................................                                                                                      [100%]
116 passed in 10.40s
TEST_EXIT=0
help: Remove trailing whitespace

Found 6 errors.
[*] 6 fixable with the `--fix` option.
GATE_RUFF_EXIT=1
All checks passed!
CI_RUFF_EXIT=0
```

End-of-task gate and exact CI workflow commands (PowerShell does not expand the
`test_research_*.py` glob, so the explicit 11-file list from `.github/workflows/research.yml`
was used for pytest):

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
backend/tests/test_make_baseline_report.py::test_control_table_renders_gap_se_and_seed_averaged_p PASSED                                                                                                  [ 95%]
backend/tests/test_make_baseline_report.py::test_underperformance_line_when_gap_below_two_control_std PASSED                                                                                              [ 96%]
backend/tests/test_make_baseline_report.py::test_no_underperformance_line_when_gap_is_inside_two_control_std PASSED                                                                                       [ 97%]
backend/tests/test_make_baseline_report.py::test_old_se_rule_flags_but_control_std_rule_does_not PASSED                                                                                                   [ 98%]
backend/tests/test_make_baseline_report.py::test_verdict_uses_seed_averaged_p_value PASSED                                                                                                                [ 99%]
backend/tests/test_make_baseline_report.py::test_verdict_seed_average_can_remove_candidate PASSED                                                                                                         [100%]

============================================================================================= 116 passed in 10.72s =============================================================================================
CI_TEST_EXIT=0
```

The six W291 diagnostics above were shortened to their locations for this log; the
full diagnostics were printed by the command and are unchanged from E1/E2.

Self-check — every file path, flag and function name mentioned in the E3 docs
(`Test-Path` for paths; `Select-String -SimpleMatch` over
`backend/app/research`, `backend/tests`, `scripts`, `.github/workflows`, `docs` and
root `INDEX.md` for content):

```text
=== PATH CHECK (Test-Path) ===
PATH FOUND      docs/DECISIONS/D-84-research-signal-information-and-exit-shape.md
PATH FOUND      docs/backtests/research/EVENT_STUDY.md
PATH FOUND      docs/backtests/research/EXIT_STUDY.md
PATH FOUND      docs/backtests/research/event_study/event_study_20261117_134829.json
PATH FOUND      docs/backtests/research/event_study/exit_study_20261117_142553.json
PATH FOUND      docs/backtests/research/BASELINE_REPORT.md
PATH FOUND      docs/backtests/research/PREREGISTRATION_TEMPLATE.md
PATH FOUND      docs/backtests/HYPOTHESIS_LOG.md
PATH FOUND      docs/SESSIONS/research-discovery-log.md
PATH FOUND      docs/DECISIONS/index.md
PATH FOUND      docs/index.md
PATH FOUND      INDEX.md
PATH FOUND      backend/app/research/events.py
PATH FOUND      backend/app/research/exit_study.py
PATH FOUND      scripts/research_event_study.py
PATH FOUND      scripts/research_exit_study.py
PATH FOUND      backend/tests/test_research_events.py
PATH FOUND      backend/tests/test_research_exit_study.py
PATH FOUND      .github/workflows/research.yml
PATH FOUND      docs/DECISIONS/D-83-research-baseline-v4-seed-averaged.md
=== CONTENT CHECK (Select-String, first match shown) ===
CONTENT FOUND      --setups -> C:\_Code\conflu.ai\scripts\research_diagnostics.py:17
CONTENT FOUND      --horizons -> C:\_Code\conflu.ai\scripts\research_event_study.py:275
CONTENT FOUND      --cooldown -> C:\_Code\conflu.ai\scripts\research_event_study.py:277
CONTENT FOUND      --n-null -> C:\_Code\conflu.ai\scripts\research_event_study.py:15
CONTENT FOUND      --report -> C:\_Code\conflu.ai\scripts\research_diagnostics.py:546
CONTENT FOUND      --json-dir -> C:\_Code\conflu.ai\scripts\research_event_study.py:280
CONTENT FOUND      --n-strategy-seeds -> C:\_Code\conflu.ai\scripts\run_research_baseline.py:732
CONTENT FOUND      forward_return_frame -> C:\_Code\conflu.ai\backend\app\research\events.py:42
CONTENT FOUND      eligibility_frame -> C:\_Code\conflu.ai\backend\app\research\events.py:67
CONTENT FOUND      apply_cooldown -> C:\_Code\conflu.ai\backend\app\research\events.py:85
CONTENT FOUND      accepted_event_positions -> C:\_Code\conflu.ai\backend\app\research\events.py:103
CONTENT FOUND      collect_events -> C:\_Code\conflu.ai\backend\app\research\events.py:113
CONTENT FOUND      universe_benchmark -> C:\_Code\conflu.ai\backend\app\research\events.py:183
CONTENT FOUND      month_block_bootstrap_ci -> C:\_Code\conflu.ai\backend\app\research\events.py:217
CONTENT FOUND      mean_excess -> C:\_Code\conflu.ai\backend\app\research\events.py:265
CONTENT FOUND      event_stats -> C:\_Code\conflu.ai\backend\app\research\events.py:126
CONTENT FOUND      p_values -> C:\_Code\conflu.ai\backend\app\research\events.py:338
CONTENT FOUND      null_distribution -> C:\_Code\conflu.ai\backend\app\research\events.py:359
CONTENT FOUND      ExitVariant -> C:\_Code\conflu.ai\backend\app\research\exit_study.py:49
CONTENT FOUND      VARIANTS -> C:\_Code\conflu.ai\backend\app\research\exit_study.py:66
CONTENT FOUND      trailing_stop_path -> C:\_Code\conflu.ai\backend\app\research\exit_study.py:100
CONTENT FOUND      simulate_trade -> C:\_Code\conflu.ai\backend\app\research\exit_study.py:129
CONTENT FOUND      entry_candidates -> C:\_Code\conflu.ai\backend\app\research\exit_study.py:255
CONTENT FOUND      simulate_entries -> C:\_Code\conflu.ai\backend\app\research\exit_study.py:294
CONTENT FOUND      trade_stats -> C:\_Code\conflu.ai\backend\app\research\exit_study.py:341
CONTENT FOUND      null_summary -> C:\_Code\conflu.ai\backend\app\research\exit_study.py:383
CONTENT FOUND      mask_ineligible -> C:\_Code\conflu.ai\backend\app\research\exit_study.py:414
CONTENT FOUND      null_distributions -> C:\_Code\conflu.ai\backend\app\research\exit_study.py:440
CONTENT FOUND      matched_random_signals -> C:\_Code\conflu.ai\backend\app\research\control.py:178
CONTENT FOUND      run_portfolio -> C:\_Code\conflu.ai\backend\app\research\control.py:9
```

Unconfirmed items: **none** (all 20 paths and all 30 flags/function names were found).

GitNexus change detection before commit (`detect_changes(scope="all", repo="conflu.ai")`):

```text
{
  "summary": {
    "changed_count": 4,
    "affected_count": 0,
    "changed_files": 6,
    "risk_level": "low"
  },
  "changed_symbols": [ INDEX.md "conflu.ai — Trading Intelligence Platform"/"Project Index",
                       docs/backtests/research/README.md "Research Backtest Artifacts",
                       docs/backtests/research/VALIDITY_NOTES.md "Validity Notes — Research Harness vs Deployed Screens" ],
  "affected_processes": []
}
```

### Skipped / notes

- No code, test, workflow, engine, indicator, setup, control, metric, runner or
  committed result artifact was modified (docs only). No symbol was edited, so no
  GitNexus impact analysis on a symbol was required; `detect_changes` returned
  `risk_level = low` and `affected_processes = []`.
- No push; one commit for E3 only.
- Broad `ruff check backend/app/research scripts` still fails on the same six
  pre-existing `W291` warnings; left untouched per user decision, CI ruff scope clean.
- No pre-registration existed before E1/E2; D-84 records that as "not recorded" and
  H-13/H-14 are labelled EXPLORATORY. The template added here applies to future runs.

---

## E4 - Volatility-matched re-measurement of E1 and E2

- **Date:** 2026-11-17
- **Task:** E4 (Phase 2). Precondition D-84 at `be499e5` (or later) confirmed on
  `research/baseline-backtesting`; branch pulled with `Already up to date.`
- **Commits:** COMMIT 1 `49cad31` (code only); COMMIT 2 for this entry and the
  generated artifacts.
- **What changed and why:** E1/E2 had two measurement flaws. (1) The old null
  (`control.matched_random_signals`) sampled random eligible stocks of any
  volatility, so its spread was 2-3.5x smaller than the strategy's own month-block
  uncertainty; `p_high`/`p_low` and `gap/std` were not valid significance tests.
  (2) E2 measures R with `1R = 2*ATR`, so `low_vol_setup`'s low-ATR names turn the
  same percent move into more R. E4 adds a volatility-bucket control (`atr_pct`
  rank per date, previous-bar bucket benchmark, per-date/per-bucket matched
  random draws), cost-aware percent returns, and an honest month-block CI +
  Bonferroni `block_t >= z_crit(20)` rule. No `p_high`/`p_low` is produced.
  New pure module `backend/app/research/matched_control.py`, 8 deterministic
  tests, and `scripts/research_vol_matched.py` (Part 1 event study against the
  bucket benchmark, Part 2 exit study in R and percent units). Old engine,
  indicators, setups, controls, metrics, runner, `events.py`, `exit_study.py`,
  the two earlier study scripts and all committed result artifacts were reused by
  import and not modified.

### Files touched

COMMIT 1 (code):

- `backend/app/research/matched_control.py` (new)
- `backend/tests/test_research_matched_control.py` (new)
- `scripts/research_vol_matched.py` (new)
- `.github/workflows/research.yml` (new test + new script in the CI ruff and pytest lists)

COMMIT 2 (generated + log):

- `docs/backtests/research/VOL_MATCHED_STUDY.md` (generated)
- `docs/backtests/research/event_study/vol_matched_20261117_185439.json` (generated)
- `docs/SESSIONS/research-discovery-log.md` (this entry)

### Commands, exact output

Start-of-task gate (before any E4 edit; explicit 11-file CI list):

```text
=== START GATE pytest ===
....................................................................................................................                                                                                      [100%]
116 passed in 11.39s
TEST_EXIT=0
=== START GATE ruff (CI scope) ===
All checks passed!
RUFF_EXIT=0
```

New module tests:

```text
........                                                                                                                                                                                                  [100%]
8 passed in 1.71s
TEST_EXIT=0
```

Smoke run into a temp folder OUTSIDE the repo (`breakout_52week`, 2 sanity draws,
2 null draws). `dirty=True` is expected: the workflow edit and the three new files
were not committed yet.

```text
Loading panel 2015-01-01 -> 2026-11-17 from .cache/research
Panel: 2015-01-02 -> 2026-11-17, 501 tradable symbols, 2 dropped (cache hits=503, downloads=0)
Building eligibility, forward returns and benchmarks
Universe benchmark dates: 2735
Bucket benchmark rows: 30056
[E1 breakout_52week] building signals and events
[E1 breakout_52week] events after cooldown: 4915
[E1 breakout_52week] h=1: n=4915 old=+1.8 bp bucket=+1.6 bp block_t=0.55 pass=False
[E1 breakout_52week] h=5: n=4910 old=+7.7 bp bucket=+7.3 bp block_t=0.92 pass=False
[E1 breakout_52week] h=10: n=4881 old=+20.9 bp bucket=+21.6 bp block_t=1.89 pass=False
[E1 breakout_52week] h=20: n=4837 old=+14.6 bp bucket=+22.7 bp block_t=1.27 pass=False
[E1 breakout_52week] h=60: n=4813 old=+31.4 bp bucket=+71.9 bp block_t=2.27 pass=False
[E1 breakout_52week] sanity draws 2/2
[E2 breakout_52week] building signals and entries
[E2 breakout_52week] real entries: 6819
[E2 breakout_52week] B0: n=6772 mean r_net=-0.0018 mean pct=+11.4 bp
[E2 breakout_52week] B1: n=6754 mean r_net=+0.0010 mean pct=+20.1 bp
[E2 breakout_52week] B2: n=6754 mean r_net=+0.0127 mean pct=+20.4 bp
[E2 breakout_52week] B3: n=6786 mean r_net=-0.0484 mean pct=-9.6 bp
[E2 breakout_52week] B4: n=6712 mean r_net=+0.0641 mean pct=+56.9 bp
[E2 breakout_52week] null draws 2/2
[E2 breakout_52week] B0: gapR=-0.0316 gapPct=-8.6 bp signs=True block_t(R)=-0.97 block_t(pct)=-0.55 pass=False
[E2 breakout_52week] B1: gapR=-0.0260 gapPct=-0.4 bp signs=True block_t(R)=-0.53 block_t(pct)=-0.02 pass=False
[E2 breakout_52week] B2: gapR=-0.0508 gapPct=-11.0 bp signs=True block_t(R)=-1.07 block_t(pct)=-0.48 pass=False
[E2 breakout_52week] B3: gapR=-0.0618 gapPct=-21.2 bp signs=True block_t(R)=-2.25 block_t(pct)=-1.51 pass=False
[E2 breakout_52week] B4: gapR=+0.0050 gapPct=+12.7 bp signs=True block_t(R)=0.05 block_t(pct)=0.31 pass=False
Wrote C:\Users\keval\AppData\Local\Temp\vm\VOL_MATCHED_STUDY.md and C:\Users\keval\AppData\Local\Temp\vm\vol_matched_20261117_182653.json
Elapsed: 1.5 minutes; dirty=True
EXIT=0
```

End-of-task gate for COMMIT 1 (explicit 12-file CI list including
`test_research_matched_control.py`; ruff includes `research_vol_matched.py`):

```text
=== END GATE pytest ===
............................................................................................................................                                                                              [100%]
124 passed in 10.67s
TEST_EXIT=0
=== END GATE ruff (CI scope incl new script) ===
All checks passed!
RUFF_EXIT=0
```

Exact two CI workflow commands:

```text
=== WORKFLOW STEP: Ruff (research harness) ===
All checks passed!
RUFF_EXIT=0
=== WORKFLOW STEP: Research tests ===
...
============================================================================================= 124 passed in 10.96s =============================================================================================
PYTEST_EXIT=0
```

COMMIT 1 was created from a tree containing only the four code/workflow files:

```text
[research/baseline-backtesting 49cad31] research: add vol-matched control and percent-return measurement module
 4 files changed, 1561 insertions(+)
 create mode 100644 backend/app/research/matched_control.py
 create mode 100644 backend/tests/test_research_matched_control.py
 create mode 100644 scripts/research_vol_matched.py
COMMIT_EXIT=0
```

`git status --porcelain` was empty after the commit, so the full study ran from a
clean tree with the default command:

```text
python scripts/research_vol_matched.py
```

Full-run console (first lines and last 40 lines; 131 lines total, 26.6 minutes,
`dirty=False`):

```text
Loading panel 2015-01-01 -> 2026-11-17 from .cache/research
Panel: 2015-01-02 -> 2026-11-17, 501 tradable symbols, 2 dropped (cache hits=503, downloads=0)
Building eligibility, forward returns and benchmarks
Universe benchmark dates: 2735
Bucket benchmark rows: 30056
...
[E2 low_vol_setup] B4: n=18336 mean r_net=+0.2463 mean pct=+71.9 bp
[E2 low_vol_setup] null draws 10/100
[E2 low_vol_setup] null draws 20/100
[E2 low_vol_setup] null draws 30/100
[E2 low_vol_setup] null draws 40/100
[E2 low_vol_setup] null draws 50/100
[E2 low_vol_setup] null draws 60/100
[E2 low_vol_setup] null draws 70/100
[E2 low_vol_setup] null draws 80/100
[E2 low_vol_setup] null draws 90/100
[E2 low_vol_setup] null draws 100/100
[E2 low_vol_setup] B0: gapR=+0.0193 gapPct=+4.7 bp signs=True block_t(R)=0.44 block_t(pct)=0.35 pass=False
[E2 low_vol_setup] B1: gapR=+0.0187 gapPct=+4.3 bp signs=True block_t(R)=0.34 block_t(pct)=0.26 pass=False
[E2 low_vol_setup] B2: gapR=+0.0328 gapPct=+9.1 bp signs=True block_t(R)=0.49 block_t(pct)=0.47 pass=False
[E2 low_vol_setup] B3: gapR=+0.0270 gapPct=+6.7 bp signs=True block_t(R)=0.55 block_t(pct)=0.47 pass=False
[E2 low_vol_setup] B4: gapR=+0.0394 gapPct=+8.8 bp signs=True block_t(R)=0.50 block_t(pct)=0.38 pass=False
[E2 volume_trend_accumulation] building signals and entries
[E2 volume_trend_accumulation] real entries: 20830
[E2 volume_trend_accumulation] B0: n=20696 mean r_net=+0.0161 mean pct=+11.7 bp
[E2 volume_trend_accumulation] B1: n=20635 mean r_net=+0.0085 mean pct=+10.8 bp
[E2 volume_trend_accumulation] B2: n=20633 mean r_net=+0.0554 mean pct=+28.4 bp
[E2 volume_trend_accumulation] B3: n=20750 mean r_net=-0.0095 mean pct=-1.1 bp
[E2 volume_trend_accumulation] B4: n=20536 mean r_net=+0.0809 mean pct=+49.4 bp
[E2 volume_trend_accumulation] null draws 10/100
[E2 volume_trend_accumulation] null draws 20/100
[E2 volume_trend_accumulation] null draws 30/100
[E2 volume_trend_accumulation] null draws 40/100
[E2 volume_trend_accumulation] null draws 50/100
[E2 volume_trend_accumulation] null draws 60/100
[E2 volume_trend_accumulation] null draws 70/100
[E2 volume_trend_accumulation] null draws 80/100
[E2 volume_trend_accumulation] null draws 90/100
[E2 volume_trend_accumulation] null draws 100/100
[E2 volume_trend_accumulation] B0: gapR=-0.0125 gapPct=-6.9 bp signs=True block_t(R)=-0.44 block_t(pct)=-0.53 pass=False
[E2 volume_trend_accumulation] B1: gapR=-0.0306 gapPct=-12.3 bp signs=True block_t(R)=-0.84 block_t(pct)=-0.72 pass=False
[E2 volume_trend_accumulation] B2: gapR=-0.0360 gapPct=-16.7 bp signs=True block_t(R)=-0.86 block_t(pct)=-0.87 pass=False
[E2 volume_trend_accumulation] B3: gapR=-0.0201 gapPct=-10.0 bp signs=True block_t(R)=-0.73 block_t(pct)=-0.80 pass=False
[E2 volume_trend_accumulation] B4: gapR=-0.0153 gapPct=-6.8 bp signs=True block_t(R)=-0.20 block_t(pct)=-0.22 pass=False
Wrote docs\backtests\research\VOL_MATCHED_STUDY.md and docs\backtests\research\event_study\vol_matched_20261117_185439.json
Elapsed: 26.6 minutes; dirty=False
```

Sanity-check bias, stated prominently as required: the report flags
`breakout_52week` h=20 at -3.9 bp (draw std 10.2 bp) and h=60 at -8.4 bp (draw
std 21.5 bp). With 20 draws that is about 1.7 and 1.8 standard errors from zero;
the other 18 cells are within +/-2.0 bp. It is reported in the report header and
in the sanity table, not hidden. The run was not stopped because the deviation is
inside the draw-to-draw noise of this control, not a code-level systematic bias
(the control draws from the same eligible per-bucket pool that defines the
benchmark, so its expectation is zero). Result recorded in the report:
**No cell passes.** (E1 0/20, E2 0/20.)

### Skipped / notes

- `add_pct_returns` follows the task text literally: the cost-aware formula
  `exit*(1-c)/(entry*(1+c)) - 1` is stored in `ret_gross_pct` and mirrored in
  `ret_net_pct`, which Part 2 reports. This is stated in the module docstring and
  in the report definitions.
- The 20 E1 cells and 20 E2 cells are re-measurements of the same hypotheses and
  data; the cumulative trial count is 80 and no holdout was used.
- No engine, indicator, setup, control, metric, runner, `events.py`,
  `exit_study.py`, earlier study script or committed result artifact was edited.
- No push and no squash. One code commit (COMMIT 1) plus one generated-artifact/log
  commit (COMMIT 2).
- Broad `ruff check backend/app/research scripts` was not run (six known
  pre-existing `W291` warnings in unrelated files); the CI ruff scope is clean.

## E5 - Documentation record (D-85, H-15, trial ledger, pre-registration significance rule)

- **Date:** 2026-11-17
- **Task:** E5 (Phase 2). Precondition E4 at `84c7f8d` (or later) confirmed on
  `research/baseline-backtesting`; `git log --oneline -3` showed
  `84c7f8d` / `49cad31` / `be499e5` and the worktree was clean.
- **Commit:** docs only; find it with
  `git log --oneline -- docs/DECISIONS/D-85-*.md`. Message:
  `docs (research): record D-85 vol-matched re-measurement, fix preregistration significance rule`.
- **What changed and why:** E4 produced a measurement module, tests, a study
  script and generated artifacts but was not recorded in the decision log. E5
  writes `docs/DECISIONS/D-85-research-vol-matched-remeasurement.md` (why, the
  pre-declared rule verbatim, definitions, panel/provenance, Part 1/Part 2
  tables copied from `VOL_MATCHED_STUDY.md`, the sanity bias, shortfall, test and
  lint evidence, deviations and known gaps), appends the D-85 addendum to D-84,
  adds H-15 and the E4 trial-ledger rows (E1 20 + E2 20 + E4 Part 1 20 + E4
  Part 2 20 = 80 cells) to `HYPOTHESIS_LOG.md`, replaces the pre-registration
  template's any-volatility `p <= 0.01` / `gap/std` rule with the vol-matched
  95% month-block CI plus `|block_t| >= z_crit(m)`, adds the volatility-matching
  limit, and adds D-85 pointers to the research README, DECISIONS index,
  `docs/index.md` and root `INDEX.md`. No code, test, workflow or committed
  result artifact changed.

### Files touched

- `docs/DECISIONS/D-85-research-vol-matched-remeasurement.md` (new)
- `docs/DECISIONS/D-84-research-signal-information-and-exit-shape.md` (append-only addendum)
- `docs/DECISIONS/index.md`
- `docs/backtests/HYPOTHESIS_LOG.md`
- `docs/backtests/research/PREREGISTRATION_TEMPLATE.md`
- `docs/backtests/research/README.md`
- `docs/index.md`
- `INDEX.md`
- `docs/SESSIONS/research-discovery-log.md` (this entry)

### Commands, exact output

Start gate (before any E5 edit):

```text
=== E5 START GATE pytest (explicit 12-file CI list) ===
124 passed in 10.25s
TEST_EXIT=0
=== E5 START GATE ruff (exact CI scope) ===
All checks passed!
RUFF_EXIT=0
```

Self-check of every path, flag and function named in the new text
(`Test-Path` / `Select-String -SimpleMatch`):

```text
=== paths ===
True   docs/DECISIONS/D-85-research-vol-matched-remeasurement.md
True   docs/DECISIONS/D-84-research-signal-information-and-exit-shape.md
True   docs/DECISIONS/D-83-research-baseline-v4-seed-averaged.md
True   docs/backtests/HYPOTHESIS_LOG.md
True   docs/backtests/research/VOL_MATCHED_STUDY.md
True   docs/backtests/research/EVENT_STUDY.md
True   docs/backtests/research/EXIT_STUDY.md
True   docs/backtests/research/PREREGISTRATION_TEMPLATE.md
True   docs/SESSIONS/research-discovery-log.md
True   backend/app/research/matched_control.py
True   backend/tests/test_research_matched_control.py
True   scripts/research_vol_matched.py
True   docs/backtests/research/event_study/vol_matched_20261117_185439.json
True   .github/workflows/research.yml
=== flags in script ===
True   --setups
True   --horizons
True   --n-buckets
True   --n-sanity
True   --n-null
True   --report
True   --json-dir
=== functions in matched_control.py ===
True   def vol_bucket_frame
True   def vol_matched_random_signals
True   def bucket_benchmark
True   def add_event_bucket
True   def bucket_excess_frame
True   def add_pct_returns
True   def block_summary
True   def z_crit
True   def cell_passes
```

Imported symbols were also confirmed by their definitions: `events.py` has
`forward_return_frame`, `eligibility_frame`, `collect_events`,
`universe_benchmark`, `month_block_bootstrap_ci` and `event_stats`;
`exit_study.py` has `DEFAULT_COST_BPS`, `VARIANTS`, `entry_candidates`,
`simulate_entries` and `mask_ineligible`. Nothing named in D-85 was unconfirmed.

End gate (after all E5 edits):

```text
=== E5 END GATE pytest (explicit 12-file CI list) ===
124 passed in 11.26s
TEST_EXIT=0
=== E5 END GATE ruff (exact CI scope) ===
All checks passed!
RUFF_EXIT=0
```

`git diff --stat` before the commit (the new D-85 file is untracked at this point, so
it is not in this output; `git status --porcelain` listed it as `??`):

```text
 INDEX.md                                                          |   2 ++
 docs/DECISIONS/D-84-research-signal-information-and-exit-shape.md |   6 ++++++
 docs/DECISIONS/index.md                                           |   1 +
 docs/backtests/HYPOTHESIS_LOG.md                                  | 116 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++---
 docs/backtests/research/PREREGISTRATION_TEMPLATE.md               |  24 +++++++++++++++---------
 docs/backtests/research/README.md                                 |   2 ++
 docs/index.md                                                     |   1 +
 7 files changed, 140 insertions(+), 12 deletions(-)
```

### Skipped / notes

- The template uses "vol-matched CI plus `|block_t| >= z_crit(m)`" in place of
  the old any-volatility rule. The exact old placeholder lines
  (`Primary threshold ... gap / null std > 2`, `p-value definition`,
  `p-value threshold ... p_high < 0.05`) were replaced, and the amendment log
  records the change with `still EXPLORATORY`.
- No "Universe and biases" heading exists in the template; the volatility-matching
  line was added to section 7 ("Limits to restate with any result"), which is the
  template's bias-restatement section. D-85 itself has a "Universe and biases"
  section.
- Numbers were copied verbatim from `VOL_MATCHED_STUDY.md`, `EVENT_STUDY.md`,
  `EXIT_STUDY.md` and D-84; no run was repeated and no value was recomputed.
- The `git diff --stat` command was followed by a stray `timeout=900000` line in
  PowerShell, which produced a `CommandNotFoundException`; the gates had already
  completed and both exits are recorded above. No other command failed.
- Nothing was pushed and nothing was squashed. Broad
  `ruff check backend/app/research scripts` was not run (six known pre-existing
  `W291` warnings in unrelated files); the exact CI ruff scope is clean.

## E6 - Fix `add_pct_returns` gross column and the E4 wording

- **Date:** 2026-11-18
- **Task:** E6 (Phase 3 correction commit). Precondition confirmed: `49cad31`,
  `84c7f8d` and `f5c9f05` are on `research/baseline-backtesting`; `git pull
  --ff-only` said `Already up to date.` No study was re-run.
- **What changed and why:** the E4 task defined
  `ret_gross_pct = exit_price/entry_price - 1` (no costs) and
  `ret_net_pct = exit_price*(1-c)/(entry_price*(1+c)) - 1`, but
  `add_pct_returns` stored the cost-aware formula in both columns and the
  docstring, test, script text, report and D-85 said this was "as specified".
  E6 makes `ret_gross_pct` cost-free, keeps `ret_net_pct` cost-aware, and adds
  an insert-only correction blockquote to the report and D-85. Only
  `ret_net_pct` is reported and `ret_gross_pct` is used nowhere else (grep
  below), so no reported number changes.
- **`git grep -n ret_gross_pct` before editing:** hits were the definition in
  `matched_control.py` (docstring plus the two column assignments), the test
  and empty-frame assertions, the D-85 definitions and section 11 wording, the
  E4 work-log entry, the report definitions bullet, the JSON definitions
  string, and `scripts/research_vol_matched.py` line 170. No computation or
  report table reads `ret_gross_pct`.
- **Files touched:** `backend/app/research/matched_control.py`,
  `backend/tests/test_research_matched_control.py`,
  `scripts/research_vol_matched.py`,
  `docs/backtests/research/VOL_MATCHED_STUDY.md`,
  `docs/DECISIONS/D-85-research-vol-matched-remeasurement.md`,
  `docs/backtests/research/VALIDITY_NOTES.md`, this work log.

### Commands, exact output

Start gate:

```text
=== E6 START GATE pytest ===
124 passed in 14.26s
TEST_EXIT=0
=== E6 START GATE ruff ===
All checks passed!
RUFF_EXIT=0
```

End gate:

```text
=== E6 END GATE pytest ===
124 passed in 16.87s
TEST_EXIT=0
=== E6 END GATE ruff ===
All checks passed!
RUFF_EXIT=0
```

`git diff -U0 -- docs/backtests/research/VOL_MATCHED_STUDY.md` (pure insertion;
no table line changed):

```text
@@ -23,0 +24,3 @@ Any cell that does not pass is NOT evidence of an edge. A passing cell is only a
+
+> Correction (E6, 2026-11-18): ret_gross_pct is exit/entry-1 (no costs); ret_net_pct is the cost-aware value. The original wording above was wrong. All reported numbers use ret_net_pct and are unchanged.
+
```

`git diff --name-only | grep -i json` printed nothing (`JSON_MATCH_COUNT=0`).

```text
git diff --stat
 backend/app/research/matched_control.py                   | 14 ++++++--------
 backend/tests/test_research_matched_control.py            | 25 +++++++++++++++++++++----
 docs/DECISIONS/D-85-research-vol-matched-remeasurement.md |  6 ++++++
 docs/backtests/research/VALIDITY_NOTES.md                 |  2 ++
 docs/backtests/research/VOL_MATCHED_STUDY.md              |  3 +++
 scripts/research_vol_matched.py                           |  5 +++--
 6 files changed, 41 insertions(+), 14 deletions(-)
```

### Skipped / notes

- Task text said "with `cost_bps=8` the two columns are equal". That is not
  true for the formulas E6 defines: at 8 bps the net column is below gross.
  The test therefore checks equality at `cost_bps=0` (the only cost at which
  the two formulas coincide) and additionally checks `net < gross` at 8 bps
  and at 15 bps. No test was weakened and no formula was bent to match the
  sentence.
- The generated JSON artifact was not edited; its definitions string keeps the
  old wording, and the D-85 definitions blockquote says so.
- No study was re-run, no download was made, and no report or JSON number was
  edited.

## E7 - Pre-register the pre-2016 test of breakout 52week (H-16)

- **Date:** 2026-11-18
- **Task:** E7 (Phase 3 pre-registration). Docs only: no code, no download, no
  study run. Precondition confirmed: E6 is committed (`f37cbed`), working tree
  clean, `git pull --ff-only` said `Already up to date.`
- **What changed and why:** copied `PREREGISTRATION_TEMPLATE.md` to
  `docs/backtests/research/PREREGISTRATION-H-16-v1.md` and filled every field
  before any download: H-16, task E8, one primary cell (`breakout_52week` h=60
  bucket excess > 0 with 95% month-block CI low > 0 and
  `block_t >= z_crit(1) = 1.96`), 19 descriptive cells, m = 1, window
  2006-01-01..2015-12-31 with 2005 as indicator warm-up, 20 sanity draws
  seeds 90000..90019, bootstrap 2000 resamples seed 42. Status `frozen`.
  Run-filled fields (`Actual panel`, `Symbols tradable / dropped`,
  `Code revision / dirty flag`, `Commit hash(es) of the run`) are `pending`.
  Added the H-16 row and the ledger line to `HYPOTHESIS_LOG.md`; no other row
  changed.
- **Files touched:** `docs/backtests/research/PREREGISTRATION-H-16-v1.md`
  (new), `docs/backtests/HYPOTHESIS_LOG.md`, this work log.

### Commands, exact output

Start gate:

```text
=== E7 START GATE pytest ===
124 passed in 15.16s
TEST_EXIT=0
=== E7 START GATE ruff ===
All checks passed!
RUFF_EXIT=0
```

End gate (after the E7 edits, before the E7 commit):

```text
=== E7 END GATE pytest ===
124 passed in 10.25s
TEST_EXIT=0
=== E7 END GATE ruff ===
All checks passed!
RUFF_EXIT=0
```

### Skipped / notes

- No code, test, workflow or artifact changed; no download was made and no
  study was run.
- The frozen-commit hash is not written into the pre-registration file. It is
  recorded in the follow-up work-log entry committed as
  `docs(log): record H-16 pre-registration hash`.

### E7 frozen pre-registration hash

`git log -1 --format=%H` of the E7 commit:

```text
cf25477b03e9742a07531c326fecb613c571aca0
```

The pre-registration file was committed unchanged in that commit and is not
edited again by E7 or later documentation tasks.

## E8 - Pre-2016 window study for H-16 (code, then the run)

- **Date:** 2026-11-18
- **Task:** E8 (Phase 3 run of the frozen H-16 pre-registration). Precondition
  confirmed: the E7 commit exists (`cf25477`, plus the hash note `285ce7b`) and
  `docs/backtests/research/PREREGISTRATION-H-16-v1.md` is present and frozen.
  Downloads used only `backend.app.research.data.download_daily` on
  `.cache/research`, span `2005-01-01 -> 2015-12-31`.
- **What changed and why:** added the pure helpers
  `backend/app/research/window_study.py` (`by_year_excess`,
  `eligible_symbols_by_year`, `assert_no_data_after`,
  `primary_cell_passes`), 5 synthetic tests, and
  `scripts/research_window_study.py` with pre-registered defaults. The script
  reuses `events`, `exit_study`, `matched_control` and `indicators` by import;
  no frozen module was edited. Added the new test file and script to
  `.github/workflows/research.yml` (pytest list and ruff scope). The report and
  JSON are generated by the script; no number was hand-edited.
- **Files touched (COMMIT 1):** `backend/app/research/window_study.py` (new),
  `backend/tests/test_research_window_study.py` (new),
  `scripts/research_window_study.py` (new), `.github/workflows/research.yml`.
- **Files touched (COMMIT 2):**
  `docs/backtests/research/WINDOW_STUDY_H16.md` (generated),
  `docs/backtests/research/event_study/window_study_20261118_160453.json`
  (generated), this work log.

### Commands, exact output

Start gate:

```text
=== E8 START GATE pytest ===
124 passed in 10.03s
TEST_EXIT=0
=== E8 START GATE ruff ===
All checks passed!
RUFF_EXIT=0
```

New module tests and lint:

```text
5 passed in 2.52s
TEST_EXIT=0
All checks passed!
RUFF_EXIT=0
```

Smoke run (output outside the repo), panel line:

```text
Panel: 2005-01-03 -> 2015-12-31, 461 tradable symbols, 42 dropped (cache hits=0, downloads=463)
```

Smoke report head (temp copy; the full default run below is the recorded
result; the smoke subset printed 31.1 bp versus 31.5 bp in the full run):

```text
## 1. Pre-registration quote

> Research question (one sentence): Does `breakout_52week` have mean excess return at horizon 60 versus the volatility-bucket benchmark that is greater than 0 on entries 2006-01-01..2015-12-31, a window not used by E1/E2/E4?
> Primary threshold: bucket excess at h=60 `> 0` bp
> Direction: `higher`
> Significance rule: 95% month-block CI lower bound `> 0` AND `block_t >= z_crit(1) = 1.96` (use `matched_control.cell_passes` with `z = z_crit(1)`)

## 2. Primary cell

| Item | Value |
|---|---|
| n | 3208 |
| Mean bucket excess (bp) | 31.1 |
| 95% month-block CI (bp) | [-28.8, 102.4] |
| block_t | 0.93 |
| z_crit(1) | 1.96 |

PRE-REGISTERED PRIMARY CELL: FAIL
```

Code end gate (before COMMIT 1):

```text
=== E8 CODE END GATE pytest ===
129 passed in 14.04s
TEST_EXIT=0
=== E8 CODE END GATE ruff (exact CI scope) ===
All checks passed!
RUFF_EXIT=0
```

COMMIT 1: `1cc53df` `research: add pre-2016 window study module and script (E8)`,
`git status` clean afterwards.

Full default run console, last 40 lines:

```text
Bucket benchmark rows: 27687
[H-16 statistical_mean_reversion] building signals and events
[H-16 statistical_mean_reversion] events after cooldown: 4764
[H-16 statistical_mean_reversion] h=1: n=4764 raw=-3.6 bp excess=+6.1 bp block_t=1.85
[H-16 statistical_mean_reversion] h=5: n=4764 raw=+45.6 bp excess=+6.0 bp block_t=0.93
[H-16 statistical_mean_reversion] h=10: n=4748 raw=+55.1 bp excess=+6.4 bp block_t=0.80
[H-16 statistical_mean_reversion] h=20: n=4709 raw=+153.5 bp excess=+4.4 bp block_t=0.37
[H-16 statistical_mean_reversion] h=60: n=4656 raw=+303.5 bp excess=-27.3 bp block_t=-1.06
[H-16 statistical_mean_reversion] sanity draws 10/20
[H-16 statistical_mean_reversion] sanity draws 20/20
[H-16 breakout_52week] building signals and events
[H-16 breakout_52week] events after cooldown: 3247
[H-16 breakout_52week] h=1: n=3247 raw=-5.6 bp excess=-6.3 bp block_t=-2.28
[H-16 breakout_52week] h=5: n=3246 raw=-0.7 bp excess=-6.9 bp block_t=-1.07
[H-16 breakout_52week] h=10: n=3242 raw=+17.3 bp excess=-5.9 bp block_t=-0.57
[H-16 breakout_52week] h=20: n=3239 raw=+54.9 bp excess=-3.8 bp block_t=-0.25
[H-16 breakout_52week] h=60: n=3208 raw=+294.1 bp excess=+31.5 bp block_t=0.94
[H-16 breakout_52week] sanity draws 10/20
[H-16 breakout_52week] sanity draws 20/20
[H-16 low_vol_setup] building signals and events
[H-16 low_vol_setup] events after cooldown: 7784
[H-16 low_vol_setup] h=1: n=7784 raw=-0.4 bp excess=-0.8 bp block_t=-1.04
[H-16 low_vol_setup] h=5: n=7760 raw=+23.0 bp excess=+2.2 bp block_t=0.98
[H-16 low_vol_setup] h=10: n=7717 raw=+43.5 bp excess=+6.7 bp block_t=1.85
[H-16 low_vol_setup] h=20: n=7682 raw=+90.3 bp excess=+7.8 bp block_t=1.52
[H-16 low_vol_setup] h=60: n=7564 raw=+262.3 bp excess=+8.1 bp block_t=0.91
[H-16 low_vol_setup] sanity draws 10/20
[H-16 low_vol_setup] sanity draws 20/20
[H-16 volume_trend_accumulation] building signals and events
[H-16 volume_trend_accumulation] events after cooldown: 9563
[H-16 volume_trend_accumulation] h=1: n=9563 raw=+2.2 bp excess=-1.6 bp block_t=-0.95
[H-16 volume_trend_accumulation] h=5: n=9563 raw=+13.6 bp excess=-3.2 bp block_t=-0.77
[H-16 volume_trend_accumulation] h=10: n=9556 raw=+33.3 bp excess=-4.6 bp block_t=-0.76
[H-16 volume_trend_accumulation] h=20: n=9526 raw=+72.4 bp excess=-7.1 bp block_t=-0.87
[H-16 volume_trend_accumulation] h=60: n=9340 raw=+253.3 bp excess=-17.9 bp block_t=-1.21
[H-16 volume_trend_accumulation] sanity draws 10/20
[H-16 volume_trend_accumulation] sanity draws 20/20
PRIMARY CELL: n=3208 mean=+31.5 bp ci=[-28.8, +102.8] block_t=0.94 z=1.96 -> FAIL
Wrote docs\backtests\research\WINDOW_STUDY_H16.md and docs\backtests\research\event_study\window_study_20261118_160453.json
Elapsed: 7.1 minutes; dirty=False; matches=True
```

End gate (after the run, before COMMIT 2):

```text
=== E8 END GATE pytest ===
129 passed in 16.50s
TEST_EXIT=0
=== E8 END GATE ruff (exact CI scope) ===
All checks passed!
RUFF_EXIT=0
```

Report primary block and provenance (from the generated file):

```text
| n | 3208 |
| Mean bucket excess (bp) | 31.5 |
| 95% month-block CI (bp) | [-28.8, 102.8] |
| block_t | 0.94 |
| z_crit(1) | 1.96 |

PRE-REGISTERED PRIMARY CELL: FAIL

| Requested span | 2005-01-01 -> 2015-12-31 |
| Actual panel | 2005-01-03 -> 2015-12-31 |
| Tradable symbols | 461 |
| Dropped at load | 42 |
| Git revision | `1cc53dff59073b63bbe3b51d5882edf50c2e45e1` |
| Dirty worktree | no |
| Matches pre-registration | yes |
| Elapsed | 7.1 minutes |
```

### Skipped / notes

- COMMIT 2: `research: H-16 pre-2016 window study results (E8)`.
- 42 of 503 requested symbols were dropped at load (`insufficient rows after
  cleaning` / `no data returned`): they are current constituents whose price
  history starts after 2015 (e.g. recent IPOs), so the 2005-2015 panel has 461
  tradable symbols. The 8.3% drop rate is below the 40% stop threshold and is
  reported, not hidden.
- Stop conditions were checked: 461 >= 250 tradable symbols; drop rate 8.3% <=
  40%; `assert_no_data_after` passed; 129 tests passed; `dirty=False` on the
  full run.
- The two generated files were committed together with this entry. No engine,
  indicator, setup, control, metric, runner, `events.py`, `exit_study.py`,
  `matched_control.py`, earlier script or earlier artifact was modified.

## E9 - Survivorship / current-membership size estimate (MEASUREMENT)

- **Date:** 2026-11-18
- **Task:** E9. Preconditions confirmed: E6/E7/E8 are committed and the tree was
  clean before the recorded run. Downloads used only
  `backend.app.research.data.download_daily` with cache `.cache/research`, span
  `2015-01-01 -> 2026-11-17` (the latest complete session present in the
  span-keyed cache).
- **What changed and why:** added the pure helpers
  `backend/app/research/survivorship.py` (equal-weight daily returns,
  calendar-year compounding, per-year symbols with data, annual gap table,
  average annual gap, cumulative return), 5 synthetic tests, and
  `scripts/research_survivorship.py`. The script loads the 501 cached
  current-constituent symbols and compares their daily-rebalanced equal-weight
  return with RSP and SPY. Added the new test file and script to
  `.github/workflows/research.yml`. No frozen module was edited and no number
  was hand-edited.
- **Files touched (COMMIT 1):** `backend/app/research/survivorship.py` (new),
  `backend/tests/test_research_survivorship.py` (new),
  `scripts/research_survivorship.py` (new), `.github/workflows/research.yml`.
- **Files touched (COMMIT 2):**
  `docs/backtests/research/SURVIVORSHIP_ESTIMATE.md` (generated),
  `docs/backtests/research/event_study/survivorship_20261118_161329.json`
  (generated), this work log.

### Commands, exact output

Start gate:

```text
=== E9 START GATE pytest ===
129 passed in 12.42s
TEST_EXIT=0
=== E9 START GATE ruff ===
All checks passed!
RUFF_EXIT=0
```

New module tests and lint:

```text
5 passed in 1.60s
TEST_EXIT=0
All checks passed!
RUFF_EXIT=0
```

Code end gate (before COMMIT 1):

```text
=== E9 CODE END GATE pytest ===
134 passed in 20.23s
TEST_EXIT=0
=== E9 CODE END GATE ruff (exact CI scope) ===
All checks passed!
RUFF_EXIT=0
```

COMMIT 1: `5808d4f` `research: add survivorship size-estimate module and script (E9)`,
`git status` clean afterwards.

Recorded run console (clean tree):

```text
Loading panel and benchmarks 2015-01-01 -> 2026-11-17 from .cache/research
Universe symbols: 503; cached for span: 501; not loaded (no cache, never downloaded): ['KVUE', 'VYLR']
Wrote docs\backtests\research\SURVIVORSHIP_ESTIMATE.md and docs\backtests\research\event_study\survivorship_20261118_161329.json
Panel 2015-01-02 -> 2026-11-17, 501 symbols; average annual gap +6.32 pp; dirty=False
Elapsed: 0.6 minutes
RUN_EXIT=0
```

End gate (after the run, before COMMIT 2):

```text
=== E9 END GATE pytest ===
134 passed in 14.86s
TEST_EXIT=0
=== E9 END GATE ruff (exact CI scope) ===
All checks passed!
RUFF_EXIT=0
```

Generated numbers (MEASUREMENT, no pass/fail), copied from
`SURVIVORSHIP_ESTIMATE.md`:

```text
| 2016 | 21.41% | 15.79% | +5.62 pp | 13.59% | 469 |
| 2017 | 27.21% | 18.52% | +8.69 pp | 21.71% | 472 |
| 2018 | -2.00% | -7.84% | +5.84 pp | -4.57% | 476 |
| 2019 | 35.06% | 28.91% | +6.15 pp | 31.22% | 482 |
| 2020 | 23.51% | 12.66% | +10.85 pp | 18.33% | 487 |
| 2021 | 32.52% | 29.41% | +3.11 pp | 28.73% | 491 |
| 2022 | -10.13% | -11.62% | +1.49 pp | -18.18% | 493 |
| 2023 | 23.34% | 13.70% | +9.64 pp | 26.18% | 494 |
| 2024 | 21.01% | 12.79% | +8.22 pp | 24.89% | 497 |
| 2025 | 17.23% | 11.21% | +6.02 pp | 17.72% | 499 |
| 2026 | 17.86% | 13.98% | +3.88 pp | 9.15% | 501 |

Panel EW cumulative 520.03%; RSP 241.49%; gap +278.54 pp; SPY 336.88%.
Average annual gap +6.32 pp (11 of 11 years positive).
```

### Skipped / notes / deviations

- COMMIT 2: `research: survivorship size estimate results (E9)`.
- The first code draft passed the full universe to `download_daily`, which
  attempted a fetch of the uncached constituent `KVUE` (it failed, no data) and
  would have attempted `VYLR`. That conflicts with the task's "only for symbols
  RSP and SPY". Before the recorded run, COMMIT 1 was amended to restrict the
  request to symbols that already have a cache entry for the exact span (plus
  RSP) and to print the two uncached universe symbols. The recorded run made no
  non-RSP/SPY request; `KVUE` and `VYLR` have no data and are not in the panel.
  COMMIT 1 was also amended once to add the `Universe symbols / Cached for span
  / Not loaded` provenance rows. Both amendments happened before COMMIT 2; the
  final COMMIT 1 hash is `5808d4f`.
- 503 universe symbols, 501 cached for the span, 501 loaded, 0 dropped by the
  loader. Downloads: 0 in the recorded run (RSP was fetched by the earlier
  `download_daily` call and reused from `.cache/research`; SPY from cache).
- No pass/fail rule applies: this is a size estimate, and the report carries the
  four required caveats verbatim. No interpretation was added.

## E10 - Record D-86: H-16 pre-2016 check and the survivorship size estimate

- **Date:** 2026-11-18
- **Task:** E10 (Phase 3 documentation). Precondition confirmed: E7 `cf25477` /
  `285ce7b`, E8 `1cc53df` / `2f9a1f5` and E9 `5808d4f` / `6806a49` are committed and
  `git status` was clean before any E10 edit.
- **What changed and why:** documentation only. Added
  `docs/DECISIONS/D-86-research-pre2016-check-and-survivorship-estimate.md`; updated
  the H-16 row and appended one change-log row in `docs/backtests/HYPOTHESIS_LOG.md`;
  filled only the five run-filled fields in
  `docs/backtests/research/PREREGISTRATION-H-16-v1.md` (Status -> `run`, actual panel,
  symbols tradable/dropped, code revision/dirty, run commits) and added one section 8
  amendment row stating "post-run fill, no criterion changed"; added one pointer line
  each to `docs/DECISIONS/index.md`, `docs/index.md`, `INDEX.md`,
  `docs/backtests/research/README.md` and `docs/backtests/research/VALIDITY_NOTES.md`.
  No code, test, workflow, report, JSON or earlier work-log entry was touched, and no
  pass/fail criterion was changed after the run.
- **Files touched:** the D-86 file (new), `docs/backtests/HYPOTHESIS_LOG.md`,
  `docs/backtests/research/PREREGISTRATION-H-16-v1.md`, `docs/DECISIONS/index.md`,
  `docs/index.md`, `INDEX.md`, `docs/backtests/research/README.md`,
  `docs/backtests/research/VALIDITY_NOTES.md`, this work log.

### Commands, exact output

Start gate:

```text
=== E10 START GATE pytest ===
134 passed in 14.63s
TEST_EXIT=0
=== E10 START GATE ruff ===
All checks passed!
RUFF_EXIT=0
```

Self-check (`Test-Path` and `Select-String -SimpleMatch`), all 13 paths, all 10 module
functions, all 9 window-study flags and all 4 workflow entries found:

```text
=== PATH CHECKS ===
OK   docs/DECISIONS/D-86-research-pre2016-check-and-survivorship-estimate.md
OK   backend/app/research/window_study.py
OK   backend/tests/test_research_window_study.py
OK   scripts/research_window_study.py
OK   docs/backtests/research/WINDOW_STUDY_H16.md
OK   docs/backtests/research/event_study/window_study_20261118_160453.json
OK   docs/backtests/research/PREREGISTRATION-H-16-v1.md
OK   backend/app/research/survivorship.py
OK   backend/tests/test_research_survivorship.py
OK   scripts/research_survivorship.py
OK   docs/backtests/research/SURVIVORSHIP_ESTIMATE.md
OK   docs/backtests/research/event_study/survivorship_20261118_161329.json
OK   .github/workflows/research.yml
=== FUNCTION CHECKS (module definitions) ===
OK   backend/app/research/window_study.py :: def by_year_excess (line 24)
OK   backend/app/research/window_study.py :: def eligible_symbols_by_year (line 52)
OK   backend/app/research/window_study.py :: def assert_no_data_after (line 71)
OK   backend/app/research/window_study.py :: def primary_cell_passes (line 88)
OK   backend/app/research/survivorship.py :: def equal_weight_returns (line 25)
OK   backend/app/research/survivorship.py :: def calendar_year_returns (line 40)
OK   backend/app/research/survivorship.py :: def symbols_with_data_by_year (line 56)
OK   backend/app/research/survivorship.py :: def cumulative_return (line 68)
OK   backend/app/research/survivorship.py :: def annual_gap_table (line 79)
OK   backend/app/research/survivorship.py :: def average_annual_gap (line 103)
=== FLAG CHECKS ===
OK   flag --start
OK   flag --end
OK   flag --eval-start
OK   flag --setups
OK   flag --horizons
OK   flag --n-buckets
OK   flag --n-sanity
OK   flag --report
OK   flag --json-dir
=== WORKFLOW CHECKS ===
OK   workflow backend/tests/test_research_window_study.py (line 54)
OK   workflow backend/tests/test_research_survivorship.py (line 55)
OK   workflow scripts/research_window_study.py (line 38)
OK   workflow scripts/research_survivorship.py (line 39)
=== PENDING CHECK (must be empty) ===
=== END PENDING CHECK ===
=== STATUS / FILLED FIELDS ===
27: | Status | `run` |
47: | Actual panel | `2005-01-03 -> 2015-12-31` |
54: | Symbols tradable / dropped | `461 / 42` |
55: | Code revision / dirty flag | `1cc53df / false` |
105: | Commit hash(es) of the run | `1cc53df` (code) / `2f9a1f5` (results) |
=== OUTCOME STRING CHECKS ===
OK   report PRE-REGISTERED PRIMARY CELL: FAIL
OK   report | n | 3208 |
OK   report | block_t | 0.94 |
OK   H-16 row FAIL (line 51)
OK   E9 average gap line
```

End gate (after every E10 edit, before the E10 commit):

```text
=== E10 END GATE pytest (exact CI list) ===
134 passed in 12.40s
TEST_EXIT=0
=== E10 END GATE ruff (exact CI scope) ===
All checks passed!
RUFF_EXIT=0
```

### Skipped / notes

- Documentation only: no study was re-run, no download was made, no number was
  recomputed or hand-edited. Every number in D-86 is copied verbatim from
  `WINDOW_STUDY_H16.md`, `SURVIVORSHIP_ESTIMATE.md` or the work log; fields with no
  recorded value say "not recorded".
- `pending` no longer appears anywhere in `PREREGISTRATION-H-16-v1.md`; the only
  post-run change to that file is the five run-filled fields plus the section 8
  amendment row. The pass/fail rule, threshold, window and seeds are unchanged.
- The 0.4 bp smoke-vs-full difference (31.1 vs 31.5) is documented with its cause
  "not recorded"; the full default run with `matches_preregistration=true` is the
  recorded result.
- The E9 loader restriction (only cached-span symbols plus RSP; `KVUE` and `VYLR`
  never downloaded) is recorded in D-86 and the E9 work log.
- No push and no squash.

## E6 (correction) - `cost_bps=8` in the task text was a typo for `cost_bps=0`

- **Date:** 2026-11-18
- **Task:** documentation correction to the E6 record only. Precondition
  confirmed: HEAD `4503060` on `research/baseline-backtesting`, working tree
  clean, start gate `134 passed` (matches the E10 end count) and
  `All checks passed!`.
- **What changed and why:** the E6 task text said "with `cost_bps=8` the two
  columns are equal". The author has confirmed that was a typo: the intended
  value is `cost_bps=0`, the only cost at which `ret_gross_pct` and
  `ret_net_pct` coincide. The E6 "Skipped / notes" bullet above therefore
  describes a deviation that never existed. This entry supersedes that framing;
  the E6 entry itself is left untouched (append-only log).
- **What was already correct:** the shipped test
  `test_add_pct_returns_matches_the_specified_formula` asserts equality at
  `cost_bps=0` (`free = add_pct_returns(trades, 0.0)`, then
  `np.allclose(free["ret_net_pct"], free["ret_gross_pct"])`) and additionally
  keeps the valid checks `net < gross` at 8 bps and at 15 bps. Those extra
  checks are correct assertions about the formulas, not a workaround.
- **What did not change:** no code, formula, test, script, JSON, report or
  number. Only this work log was appended to; no earlier entry was edited and
  no artifact was regenerated. The correction commit therefore changes this
  file only (`1 file changed`, insertions only).
- **Commands, exact output:**

```text
=== E6-CORR START GATE pytest (exact CI list) ===
134 passed in 15.94s
TEST_EXIT=0
=== E6-CORR START GATE ruff (exact CI scope) ===
All checks passed!
RUFF_EXIT=0
```

End gate (run after this entry was appended):

```text
=== E6-CORR END GATE pytest (exact CI list) ===
134 passed in 12.84s
TEST_EXIT=0
=== E6-CORR END GATE ruff (exact CI scope) ===
All checks passed!
RUFF_EXIT=0
```
