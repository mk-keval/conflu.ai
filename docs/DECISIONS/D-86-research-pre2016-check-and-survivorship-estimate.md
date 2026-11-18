# D-86: Pre-2016 window check of `breakout_52week` h=60 (H-16) and a survivorship size estimate (E9)

**Date:** 2026-11-18
**Status:** Recorded. Exploratory only. Phase 3 adds one pre-registered window study
(`window_study.py`, its tests and script) and one measurement module
(`survivorship.py`, its tests and script) with their generated artifacts. No engine,
indicator, setup, control, metric or runner file changed; `events.py`,
`exit_study.py`, `matched_control.py` (beyond E6's named function, committed earlier),
the earlier scripts and every committed result artifact are reused by import and
untouched. No live decision changed and no pass bar moved.
**Branch:** `research/baseline-backtesting`
**Commits:**

| Task | Commit | Message |
|---|---|---|
| E7 | `cf25477` | `docs(research): pre-register H-16 pre-2016 check of breakout 52week (E7)` |
| E7 | `285ce7b` | `docs(log): record H-16 pre-registration hash` |
| E8 | `1cc53df` | `research: add pre-2016 window study module and script (E8)` |
| E8 | `2f9a1f5` | `research: H-16 pre-2016 window study results (E8)` |
| E9 | `5808d4f` | `research: add survivorship size-estimate module and script (E9)` |
| E9 | `6806a49` | `research: survivorship size estimate results (E9)` |

**Related:** [D-83](D-83-research-baseline-v4-seed-averaged.md),
[D-84](D-84-research-signal-information-and-exit-shape.md),
[D-85](D-85-research-vol-matched-remeasurement.md),
[D-82](D-82-research-baseline-v3-engine-realism.md),
[H-16 and the trial ledger](../backtests/HYPOTHESIS_LOG.md),
[PREREGISTRATION-H-16-v1.md](../backtests/research/PREREGISTRATION-H-16-v1.md),
[WINDOW_STUDY_H16.md](../backtests/research/WINDOW_STUDY_H16.md),
[SURVIVORSHIP_ESTIMATE.md](../backtests/research/SURVIVORSHIP_ESTIMATE.md),
[VALIDITY_NOTES.md](../backtests/research/VALIDITY_NOTES.md),
[research discovery work log](../SESSIONS/research-discovery-log.md).

---

## 1. Why this task was run

Two gaps were open after E4/D-85.

1. **Survivorship was asserted but never sized.** D-83 states the caveat plainly:

   > **Survivorship.** The universe is today's S&P 500 membership. Names that were delisted
   > or removed are absent, which flatters historical results for every setup and control.

   That sentence explains the direction but gives no scale. Every E1/E2/E4 result is
   measured on a panel that contains only companies still listed in 2026.

2. **The largest E4 cell had no unseen data.** E4 measured `breakout_52week` h=60 bucket
   excess at **71.9 bp** with **`block_t` 2.27**, the largest absolute `block_t` in the
   study (D-85 section 6). It still failed because `z_crit(20) = 3.023`, and it was
   measured on the same evaluation window as E1/E2/E4 (entries from 2016-01-01). There
   was no second window on which the same cell could be checked.

E7 therefore froze a single primary cell and its pass rule **before** any download
(H-16), E8 ran that cell on entries 2006-01-01..2015-12-31 — a window not used by
E1/E2/E4 — and E9 measured how large the survivorship/current-membership gap actually
is on the existing panel. E9 is a measurement with no pass/fail; the H-16 rule was not
changed after the result.

## 2. What Phase 3 added

| Task | File | Role |
|---|---|---|
| E7 | `docs/backtests/research/PREREGISTRATION-H-16-v1.md` (new, `cf25477`) | Frozen question, metric, design, one primary cell, pass rule, amendment log |
| E7 | `docs/backtests/HYPOTHESIS_LOG.md` | H-16 row and one trial-ledger line; no other row changed |
| E8 | `backend/app/research/window_study.py` (new) | Pure helpers: `by_year_excess`, `eligible_symbols_by_year`, `assert_no_data_after`, `primary_cell_passes` |
| E8 | `backend/tests/test_research_window_study.py` (new) | 5 deterministic synthetic tests |
| E8 | `scripts/research_window_study.py` (new) | The study; every default is a pre-registered value |
| E8 | `docs/backtests/research/WINDOW_STUDY_H16.md` (generated) | Report |
| E8 | `docs/backtests/research/event_study/window_study_20261118_160453.json` (generated) | Full artifact |
| E9 | `backend/app/research/survivorship.py` (new) | Pure helpers: equal-weight returns, calendar-year compounding, symbols/year, gap table, average gap, cumulative return |
| E9 | `backend/tests/test_research_survivorship.py` (new) | 5 deterministic synthetic tests |
| E9 | `scripts/research_survivorship.py` (new) | The measurement |
| E9 | `docs/backtests/research/SURVIVORSHIP_ESTIMATE.md` (generated) | Report |
| E9 | `docs/backtests/research/event_study/survivorship_20261118_161329.json` (generated) | Full artifact |
| E8/E9 | `.github/workflows/research.yml` | New test files and scripts added to the CI pytest list and ruff scope in the same commit |

Reused by import, not copied and not modified: `events.eligibility_frame`,
`events.forward_return_frame`, `events.collect_events`, `events.TRADABLE_BENCHMARK`,
`exit_study.mask_ineligible`, `matched_control.vol_bucket_frame`,
`matched_control.vol_matched_random_signals`, `matched_control.bucket_benchmark`,
`matched_control.add_event_bucket`, `matched_control.bucket_excess_frame`,
`matched_control.block_summary`, `matched_control.z_crit`, `SETUPS`, `add_indicators`,
`download_daily`, `load_universe`, `panel_span`, `NON_TRADABLE`.

**H-16 flags (defaults only):** `--start 2005-01-01 --end 2015-12-31
--eval-start 2006-01-01 --setups` all four `--horizons 1,5,10,20,60 --n-buckets 10
--n-sanity 20 --report docs/backtests/research/WINDOW_STUDY_H16.md --json-dir
docs/backtests/research/event_study`.
**E9 flags (defaults only):** `--start 2015-01-01 --end 2026-11-17` (the latest
complete span already in the cache manifest), `--report`, `--json-dir`.

**Module functions recorded by the self-check:** `window_study.by_year_excess`,
`window_study.eligible_symbols_by_year`, `window_study.assert_no_data_after`,
`window_study.primary_cell_passes`; `survivorship.equal_weight_returns`,
`survivorship.calendar_year_returns`, `survivorship.symbols_with_data_by_year`,
`survivorship.cumulative_return`, `survivorship.annual_gap_table`,
`survivorship.average_annual_gap`.

## 3. Pre-registered rule (copied verbatim from `PREREGISTRATION-H-16-v1.md`)

| Field | Value |
|---|---|
| Hypothesis ID | `H-16` |
| Task / experiment ID | `E8` |
| Research question | Does `breakout_52week` have mean excess return at horizon 60 versus the volatility-bucket benchmark that is greater than 0 on entries 2006-01-01..2015-12-31, a window not used by E1/E2/E4? |
| Single primary metric | mean bucket excess at h=60 in bp |
| Primary threshold | bucket excess at h=60 `> 0` bp |
| Direction | `higher` |
| Significance rule | 95% month-block CI lower bound `> 0` AND `block_t >= z_crit(1) = 1.96` (use `matched_control.cell_passes` with `z = z_crit(1)`) |
| p-value | `not used — no p_high / p_low; the spread of one control run is descriptive, not a test` |
| Multiple-comparison handling | `m = 1`: exactly one cell is tested on this data |
| Cell count | 1 primary cell (`breakout_52week` h=60) plus 19 descriptive cells |
| Fail action | record and stop; do **not** re-run with another horizon, bucket count, cooldown, window or setup |
| Evidence label | `EXPLORATORY` (research harness) |

The pre-registration was committed as `cf25477`, its hash was recorded in the work log
as `285ce7b`, and no field of the rule changed after the run. Section 8 of the file
records the post-run provenance fill only.

## 4. Data and provenance (copied from the generated reports)

### H-16 (`WINDOW_STUDY_H16.md`)

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

The 42 drops are current constituents whose price history starts after 2015 (recent
IPOs, e.g. `TWLO`, `UBER`, `VICI`, `VLTO`, `VRT`, `VYLR`). The drop rate is 8.3%,
below the script's 40% stop threshold; the run reports it, it does not hide it.

### E9 (`SURVIVORSHIP_ESTIMATE.md`)

| Item | Value |
|---|---|
| Requested span | 2015-01-01 -> 2026-11-17 |
| Actual panel | 2015-01-02 -> 2026-11-17 |
| Universe symbols | 503 |
| Cached for span | 501 |
| Not loaded (no cache, never downloaded) | 2 (KVUE, VYLR) |
| Panel symbols loaded | 501 |
| Dropped by loader | 0 |
| Cache hits / downloads | 504 / 0 |
| Git revision | `5808d4f0e955cd835509192a5dffcbfdddae1d0a` |
| Dirty worktree | no |
| Command | `scripts/research_survivorship.py` |
| Elapsed | 0.6 minutes |

## 5. H-16 primary cell (copied verbatim from the report)

Setup `breakout_52week`, horizon 60, entries from 2006-01-01.

| Item | Value |
|---|---|
| n | 3208 |
| Mean bucket excess (bp) | 31.5 |
| 95% month-block CI (bp) | [-28.8, 102.8] |
| block_t | 0.94 |
| z_crit(1) | 1.96 |

PRE-REGISTERED PRIMARY CELL: FAIL

The point estimate is positive (+31.5 bp, console prints `mean=+31.5 bp`), but the
month-block CI spans zero and `block_t` is 0.94 against a 1.96 threshold. Under the
frozen rule the cell fails on two of the three conditions. This is not a near miss that
justifies another horizon: the fail action forbids selecting another horizon, bucket
count, cooldown, window or setup on this data.

## 6. Descriptive cells for `breakout_52week` (no pass/fail)

Copied verbatim from section 5 of the report. Events after cooldown: 3247.

| h | n | raw mean (bp) | bucket excess (bp) | 95% CI (bp) | hit rate | block_t |
|---|---|---|---|---|---|---|
| 1 | 3247 | -5.6 | -6.3 | [-11.9, -1.1] | 47.2% | -2.28 |
| 5 | 3246 | -0.7 | -6.9 | [-19.0, 6.2] | 48.6% | -1.07 |
| 10 | 3242 | 17.3 | -5.9 | [-25.0, 15.6] | 48.0% | -0.57 |
| 20 | 3239 | 54.9 | -3.8 | [-33.0, 27.6] | 48.6% | -0.25 |
| 60 | 3208 | 294.1 | 31.5 | [-28.8, 102.8] | 50.1% | 0.94 |

Only h=60 is positive. The four shorter horizons are negative or near zero, and h=1 is
-2.28 `block_t` with a CI that excludes zero on the negative side — a descriptive
observation, not a tested cell. The raw mean rises with the horizon (294.1 bp at h=60)
while bucket excess is 31.5 bp, so most of the raw return is market exposure, not
signal.

Per-year bucket excess at h=60 (copied from section 6 of the report):

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

Six of ten years are positive, but the sign flips repeatedly and the two largest
magnitudes are 2007 (+287.3 bp) and 2008 (-269.3 bp), the smallest year by events
(n=53 in 2008). The year-level dispersion is the reason the pooled CI is wide.

## 7. Panel thinning (copied verbatim)

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

The panel is thinnest in the oldest years, which is where the survivorship bias is
strongest. Any 2006-2015 comparison is therefore measured on a different, smaller and
more survivor-selected cross-section than the 2016-2025 window.

## 8. Sanity check — vol-matched random event sets (copied verbatim)

Seeds 90000..90019, 20 draws per cell. The mean should be about 0; a value whose
absolute size exceeds 3 bp is flagged.

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

One cell is flagged (`statistical_mean_reversion` h=60, -3.1 bp, draw std 15.5 bp). The
primary cell's own control mean is -1.5 bp with a draw std of 9.0 bp, so the real 31.5 bp
sits about 3.7 draw standard errors above its own sanity control. This is descriptive
only: the sanity draws are not the test, and the cell's binding constraint is the wide
month-block CI.

## 9. Survivorship / current-membership size estimate (MEASUREMENT)

No pass/fail. Definitions copied from `SURVIVORSHIP_ESTIMATE.md`:

- The panel = the 501 current-constituent symbols loaded exactly as in the other scripts.
- For each trading day d from 2016-01-01, `ew_ret[d] = mean` over panel symbols that have both `close[d]` and `close[d-1]` of `close[d]/close[d-1] - 1` (daily-rebalanced equal weight; no eligibility filter).
- Calendar-year return = `product(1 + ew_ret) - 1`.
- Benchmarks: RSP (equal-weight S&P 500 ETF, point-in-time membership, ~0.20%/yr fee) and SPY, same adjusted-close method.

Per-year returns and gap (copied verbatim):

| Year | Panel EW return | RSP return | Gap (panel - RSP) | SPY return | Symbols with data |
|---|---|---|---|---|---|
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

Cumulative 2016 -> latest (copied verbatim):

| Series | Cumulative return |
|---|---|
| Panel EW | 520.03% |
| RSP | 241.49% |
| Gap (panel - RSP) | +278.54 pp |
| SPY | 336.88% |

Average annual gap: **+6.32 pp** (11 of 11 years positive).

Caveats, copied verbatim from the report and repeated here because they bound any use
of the number:

- Gap = survivorship + current-membership selection + RSP fees + rebalancing-method differences.
- It is an indicator of size, NOT a corrected estimate.
- It says nothing about the sign of the bias on any one signal.
- Daily-rebalanced equal weight is not RSP's quarterly rebalance.

The gap is positive in every year and averages +6.32 pp per year; the cumulative panel
series ends 278.54 pp above RSP. That is a large number, but it is a mixture of at least
four causes and it is not a correction that can be subtracted from any E1/E2/E4 cell.

## 10. Test, lint and CI evidence (copied verbatim from the work log)

Gates use the explicit pytest list and the exact CI ruff scope from
`.github/workflows/research.yml`. New test files and scripts were added to that workflow
in the same commit as the code.

E7:

```text
=== E7 START GATE pytest ===
124 passed in 15.16s
TEST_EXIT=0
=== E7 START GATE ruff ===
All checks passed!
RUFF_EXIT=0
```

```text
=== E7 END GATE pytest ===
124 passed in 10.25s
TEST_EXIT=0
=== E7 END GATE ruff ===
All checks passed!
RUFF_EXIT=0
```

E8:

```text
=== E8 START GATE pytest ===
124 passed in 10.03s
TEST_EXIT=0
=== E8 START GATE ruff ===
All checks passed!
RUFF_EXIT=0
```

```text
5 passed in 2.52s
TEST_EXIT=0
All checks passed!
RUFF_EXIT=0
```

```text
=== E8 CODE END GATE pytest ===
129 passed in 14.04s
TEST_EXIT=0
=== E8 CODE END GATE ruff (exact CI scope) ===
All checks passed!
RUFF_EXIT=0
```

```text
=== E8 END GATE pytest ===
129 passed in 16.50s
TEST_EXIT=0
=== E8 END GATE ruff (exact CI scope) ===
All checks passed!
RUFF_EXIT=0
```

E9:

```text
=== E9 START GATE pytest ===
129 passed in 12.42s
TEST_EXIT=0
=== E9 START GATE ruff ===
All checks passed!
RUFF_EXIT=0
```

```text
5 passed in 1.60s
TEST_EXIT=0
All checks passed!
RUFF_EXIT=0
```

```text
=== E9 CODE END GATE pytest ===
134 passed in 20.23s
TEST_EXIT=0
=== E9 CODE END GATE ruff (exact CI scope) ===
All checks passed!
RUFF_EXIT=0
```

```text
=== E9 END GATE pytest ===
134 passed in 14.86s
TEST_EXIT=0
=== E9 END GATE ruff (exact CI scope) ===
All checks passed!
RUFF_EXIT=0
```

E10 start gate:

```text
=== E10 START GATE pytest ===
134 passed in 14.63s
TEST_EXIT=0
=== E10 START GATE ruff ===
All checks passed!
RUFF_EXIT=0
```

The run console for H-16 ends with:

```text
PRIMARY CELL: n=3208 mean=+31.5 bp ci=[-28.8, +102.8] block_t=0.94 z=1.96 -> FAIL
Wrote docs\backtests\research\WINDOW_STUDY_H16.md and docs\backtests\research\event_study\window_study_20261118_160453.json
Elapsed: 7.1 minutes; dirty=False; matches=True
```

The run console for E9 ends with:

```text
Loading panel and benchmarks 2015-01-01 -> 2026-11-17 from .cache/research
Universe symbols: 503; cached for span: 501; not loaded (no cache, never downloaded): ['KVUE', 'VYLR']
Wrote docs\backtests\research\SURVIVORSHIP_ESTIMATE.md and docs\backtests\research\event_study\survivorship_20261118_161329.json
Panel 2015-01-02 -> 2026-11-17, 501 symbols; average annual gap +6.32 pp; dirty=False
Elapsed: 0.6 minutes
RUN_EXIT=0
```

## 11. Deviations, corrections and known gaps

- **E8 smoke vs full run.** A smoke run (one setup, 2 sanity draws, output outside the
  repo in `$env:TEMP\ws`) printed 31.1 bp / CI [-28.8, 102.4] / `block_t` 0.93. The
  recorded result is the full default run: 31.5 bp / [-28.8, 102.8] / 0.94. The smoke
  output is not committed and is not the result. The cause of the 0.4 bp difference was
  **not recorded**; the recorded run is the authoritative one because it is the full
  default run on a clean tree with `matches_preregistration=true`.
- **E9 loader restriction.** The first code draft passed the whole universe to
  `download_daily`, which attempted a fetch of the uncached constituent `KVUE` (it
  failed, no data) and would have attempted `VYLR`. That conflicts with the task rule
  "downloads only for RSP and SPY". Before the recorded run, the code commit was amended
  to restrict the request to symbols that already have a cache entry for the exact span
  (plus RSP) and to print the two uncached symbols. The recorded run made no
  non-RSP/SPY request; `KVUE` and `VYLR` are not in the panel. The same commit was also
  amended once to add the `Universe symbols / Cached for span / Not loaded` provenance
  rows. Both amendments happened before the results commit; the final code hash is
  `5808d4f`.
- **H-16 is a new window, not a new hypothesis.** The cell was chosen because E4's
  largest `block_t` was on it. That choice is why H-16 exists and why the window had to
  be pre-registered; it is still a selection effect and the result is labelled
  EXPLORATORY.
- **Survivorship is not removed.** Both studies use today's S&P 500 snapshot. The 2006-2015
  window is more biased than 2016-2025, and the panel thins to 244 eligible symbols in
  2005. E9 sizes the gap on 2016-2026 only; it does not measure the older window's gap.
- **No walk-forward, no holdout.** Every number is in-sample on one panel. H-16 reaching a
  second window is not an out-of-sample test of a live strategy.
- **Descriptive cells are not independent.** All 19 non-primary cells share signals,
  benchmark and events with the primary cell. They are reported, not tested.
- **The bucket benchmark** is a same-date eligibility mean, not sector- or size-matched.
- **Capacity and slot competition** are ignored in both studies.
- **E9 is not a correction.** The +6.32 pp average gap bundles survivorship,
  current-membership selection, RSP fees and rebalancing differences. It cannot be
  subtracted from any cell and says nothing about the sign of the bias on any one signal.
- **PowerShell wildcard caveat.** PowerShell does not expand
  `backend/tests/test_research_*.py`; the explicit 14-file list was passed to pytest every
  time.
- **Broad ruff was not used as a gate.** `ruff check backend/app/research scripts` still
  fails on six pre-existing `W291` warnings in unrelated `scripts/run_*.py` files. They
  were deliberately left untouched; the exact CI ruff scope is clean.
- **No push and no squash.** The six Phase 3 commits are local on
  `research/baseline-backtesting`; nothing after `f5c9f05` was pushed.
- **No frozen file edited.** No engine, indicator, setup, control, metric, runner,
  `events.py`, `exit_study.py`, `matched_control.py`, earlier study script or committed
  result artifact was edited. E8/E9 reuse `matched_control` by import.

## 12. Not recorded

- Out-of-sample or walk-forward result for H-16: **not recorded**.
- Point-in-time index membership data for 2005-2015: **not recorded** (not available in
  this harness).
- Sector- or size-matched benchmark for H-16: **not recorded** (volatility bucket only).
- Survivorship gap measured on the 2006-2015 panel: **not recorded** (E9 measures
  2016-2026 only).
- Portfolio capacity / slot-competition result for either study: **not recorded**
  (ignored by design).
- Any change to the D-75 pass bar, the kill rule, the scorecard or a FWD-v0.2 verdict:
  **not recorded** (none was made).
- Any re-run of H-16 with a different horizon, bucket count, cooldown, window or setup:
  **not recorded** (forbidden by the frozen fail action).

## 13. Decision

Record Phase 3 as EXPLORATORY research (H-16 plus the E9 measurement).

- **H-16 fails its pre-registered primary cell.** `breakout_52week` h=60 bucket excess on
  2006-2015 is +31.5 bp with a 95% month-block CI of [-28.8, 102.8] and `block_t` 0.94;
  the rule required a positive CI lower bound and `block_t >= 1.96`. The fail action is
  recorded and the study stops: no alternative horizon, bucket count, cooldown, window or
  setup will be tried on this data.
- **The E4 `breakout_52week` h=60 result does not replicate as a passing cell on the
  earlier window.** E4 measured +71.9 bp on the 2016-onward window (block_t 2.27, not
  passing); H-16 measures +31.5 bp on 2006-2015 (block_t 0.94, failing). The direction
  agrees, the magnitude roughly halves, and neither passes its rule.
- **The survivorship gap is large.** The current-membership equal-weight panel beats RSP
  by an average of +6.32 pp per year and by 278.54 pp cumulatively over 2016-2026. This is
  an indicator of the size of the problem, not a correction to any result.
- **Do not** wire any part of Phase 3 into a live decision, the D-75 pass bar, the kill
  rule, the forward scorecard or a FWD-v0.2 verdict. The next step remains point-in-time
  membership data and a forward sample; until then the survivorship caveat stands with a
  measured scale attached.
