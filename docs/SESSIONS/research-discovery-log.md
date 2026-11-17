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
