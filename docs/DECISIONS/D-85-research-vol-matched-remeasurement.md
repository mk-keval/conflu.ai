# D-85: Volatility-matched re-measurement of the E1/E2 studies (E4)

**Date:** 2026-11-17
**Status:** Recorded. Exploratory only. This task adds a pure measurement module, its
tests, a study script and their generated artifacts. No engine, indicator, setup,
control, metric or runner file changed; `events.py`, `exit_study.py`, the two earlier
study scripts and every committed result artifact are reused by import and untouched.
No live decision changed.
**Branch:** `research/baseline-backtesting`
**Commits:** E4 code `49cad31` —
`research: add vol-matched control and percent-return measurement module`; E4
generated artifacts and work log `84c7f8d` —
`research: vol-matched re-measurement of event and exit studies (E4)`.
**Related:** [D-84](D-84-research-signal-information-and-exit-shape.md),
[D-83](D-83-research-baseline-v4-seed-averaged.md),
[H-15 and the trial ledger](../backtests/HYPOTHESIS_LOG.md),
[VOL_MATCHED_STUDY.md](../backtests/research/VOL_MATCHED_STUDY.md),
[EVENT_STUDY.md](../backtests/research/EVENT_STUDY.md),
[EXIT_STUDY.md](../backtests/research/EXIT_STUDY.md),
[pre-registration template](../backtests/research/PREREGISTRATION_TEMPLATE.md),
[research discovery work log](../SESSIONS/research-discovery-log.md).

---

## 1. Why this task was run

Copied from the generated report (`VOL_MATCHED_STUDY.md`, "Why"):

> Two flaws were found in E1/E2. (1) The old null
> (`control.matched_random_signals`) picks random stocks of ANY volatility, so its
> spread is 2-3.5x smaller than the strategy's own month-block uncertainty. The
> reported `p_high`/`p_low` and `gap/std` are therefore NOT valid significance tests.
> (2) The exit study measures R, where 1R = 2*ATR. `low_vol_setup` picks low-ATR
> stocks, so the same percent move counts as more R. E2 shows `low_vol_setup` B4
> beating the null in R (+0.031R) while E1 shows the same signals underperforming the
> market by 15 bp at h=20. The sign disagreement is probably a volatility/R artifact.
> This task checks it.

The E1/E2 values referenced in that paragraph, copied verbatim from D-84:

| Study | Cell | Value |
|---|---|---|
| E2 | `low_vol_setup` B4 | mean `r_net` 0.2463, null mean 0.2153, gap `0.0310`, gap/std `2.66`, `p_high` 0.0099 |
| E1 | `low_vol_setup` h=20 | mean excess -15.4 bp, 95% CI [-44.8, 10.2] bp |

E4 therefore treats the E2 R-vs-percent sign disagreement as the artifact under test,
not as a conclusion.

## 2. Pre-declared rule

Copied verbatim from the report header:

> Any cell that does not pass is NOT evidence of an edge. A passing cell is only a
> candidate to be pre-registered and tested on the locked 2021-2026 holdout; it is
> never a result. This study re-measures the same 4 setups on the same data as E1/E2,
> so cumulative trials are 20+20+20+20 = 80 cells, and none of this is out-of-sample.

## 3. What E4 added

| File | Role |
|---|---|
| `backend/app/research/matched_control.py` (new) | Pure measurement layer: volatility buckets, bucket benchmark, vol-matched random signals, event bucket join, bucket excess, cost-aware percent returns, block summary and `z_crit` |
| `backend/tests/test_research_matched_control.py` (new) | 8 deterministic synthetic tests |
| `scripts/research_vol_matched.py` (new) | Part 1 event study vs the bucket benchmark; Part 2 exit study in R and percent units; report and JSON I/O |
| `.github/workflows/research.yml` | New test and new script added to the CI pytest and ruff lists in the same commit |
| `docs/backtests/research/VOL_MATCHED_STUDY.md` (generated) | Report |
| `docs/backtests/research/event_study/vol_matched_20261117_185439.json` (generated) | Full artifact (parameters, seeds, every cell) |
| `docs/SESSIONS/research-discovery-log.md` | E4 work-log entry |

Reused by import, not copied and not modified: `events.month_block_bootstrap_ci`,
`events.forward_return_frame`, `events.collect_events`, `events.eligibility_frame`,
`events.universe_benchmark`, `events.event_stats`, `exit_study.VARIANTS`,
`exit_study.mask_ineligible`, `exit_study.entry_candidates`,
`exit_study.simulate_entries`, `exit_study.DEFAULT_COST_BPS`, `SETUPS`,
`download_daily`, `load_universe`, `panel_span`, `add_indicators`.

Script flags: `--setups`, `--horizons` (default `1,5,10,20,60`), `--n-buckets`
(default 10), `--n-sanity` (default 20), `--n-null` (default 100), `--report`,
`--json-dir`. Part 1 sanity seeds are `70000 + i`; Part 2 null seeds are `80000 + i`.

Module functions recorded by the self-check: `vol_bucket_frame`,
`vol_matched_random_signals`, `bucket_benchmark`, `add_event_bucket`,
`bucket_excess_frame`, `add_pct_returns`, `block_summary`, `z_crit`, `cell_passes`.

## 4. Definitions (copied from the generated report)

- **Volatility bucket:** on each date, the symbols eligible on that date are ranked by
  `atr_pct` with `rank(pct=True, method="first")` and assigned
  `bucket = ceil(pct * 10) - 1`, clipped to `0..9`. `--n-buckets 10`. Not eligible or
  NaN `atr_pct` -> `-1`. An event's bucket is the bucket on its SIGNAL date `t`, so no
  data after `t` is used.
- **Bucket benchmark (Part 1):** for each entry date `e` and bucket `b`, the mean
  `ret_h` over all symbols whose bucket on the bar BEFORE `e` was `b` (the bucket
  series is shifted by one bar per symbol, mirroring `events.universe_benchmark`'s
  previous-bar eligibility) and that have the forward data. Event excess = event
  `ret_h` - bucket benchmark at the event's signal-date bucket.
- **Forward return (same as `events.py`):** `ret_h = close[e+h-1] / open[e] - 1` for
  horizons 1, 5, 10, 20, 60, cooldown `5`. A row without the future close is dropped
  for that horizon, never filled.
- **Vol-matched random signals:** for every date and every bucket in which the real
  setup fires `c` times, draw `k = min(c, pool size)` distinct symbols from the
  symbols that are eligible AND in that bucket on that date. Dates and buckets are
  visited in sorted order; non-tradable symbols get an all-False series. Shortfalls
  (`requested > drawn`) are reported, never hidden.
- **Percent returns (Part 2):** `add_pct_returns(trades, cost_bps)` adds
  `ret_gross_pct = exit_price*(1-c)/(entry_price*(1+c)) - 1` with `c = cost_bps/10000`;
  `ret_net_pct` carries the same cost-aware value and is the name reported in Part 2.
  Same entries and the same five variants B0-B4 as E2, 15 bps per side.

> Correction (E6, 2026-11-18): ret_gross_pct is exit/entry-1 (no costs); ret_net_pct is the cost-aware value. The original wording above was wrong. All reported numbers use ret_net_pct and are unchanged. The generated JSON artifact's definitions string keeps the old wording.

- **Honest significance:** `block_summary` returns the mean, the 95% month-block
  bootstrap CI (`events.month_block_bootstrap_ci`, `n_resamples=2000`, seed `42`),
  `se_block = (ci_high - ci_low)/(2*1.96)`, `reference_in_ci`, and
  `block_t = (mean - reference)/se_block` (NaN when `se_block` is 0 or NaN). Reference
  is 0 for the Part 1 bucket excess and the vol-matched null mean for Part 2.
- **Bonferroni:** `z_crit(m) = NormalDist().inv_cdf(1 - 0.05/(2*m))`; `m = 20` cells
  per part (4 setups x 5 horizons for Part 1, 4 setups x 5 variants for Part 2), so
  `z_crit(20) = 3.023`. A cell passes only if `|block_t| >= z_crit` AND
  `reference_in_ci` is False. An E2 cell passes only if BOTH the R metric and the
  percent metric pass AND their gap signs agree.
- **Null spread:** the null std is the descriptive spread of the null mean, NOT a test.
  No `p_high`/`p_low` is reported anywhere in this task.
- **Seeds:** Part 1 sanity draws use `70000 + i` (20 draws); Part 2 null draws use
  `80000 + i` (100 draws).
- **Capacity caveat:** This analysis ignores portfolio capacity and slot competition:
  every signal is taken as an independent trade, with no limit on concurrent positions
  or capital.

## 5. Panel and provenance (copied from the report)

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
| Cells per part | 20 |
| `z_crit(20)` | 3.0233414397391534 (JSON `params.z_crit`) |
| Cell summary (JSON) | `e1_passing = []`, `e2_passing = []`, `e1_total = 20`, `e2_total = 20`, `no_cell_passes = true` |

The run used the existing cache (503 hits, 0 downloads). No holdout was used.

## 6. Part 1 — event study vs the volatility-bucket benchmark

Copied verbatim from `VOL_MATCHED_STUDY.md`. `old` is the same-date eligible-universe
excess from E1 and is descriptive here; `bucket` is the volatility-bucket excess.

### `statistical_mean_reversion` — 9014 events after cooldown

| h | n | old excess (bp) | bucket excess (bp) | 95% CI (bp) | hit rate | reference in CI | block t | passes |
|---|---|---|---|---|---|---|---|---|
| 1 | 9014 | -1.4 | 1.2 | [-2.9, 5.5] | 50.2% | yes | 0.54 | no |
| 5 | 9014 | -9.0 | -9.1 | [-19.9, 1.6] | 49.5% | yes | -1.66 | no |
| 10 | 9010 | -15.6 | -17.2 | [-37.8, 3.0] | 49.3% | yes | -1.65 | no |
| 20 | 8990 | -26.1 | -20.8 | [-51.5, 8.4] | 48.5% | yes | -1.36 | no |
| 60 | 8752 | -51.7 | -34.2 | [-92.0, 22.4] | 48.9% | yes | -1.17 | no |

### `breakout_52week` — 4915 events after cooldown

| h | n | old excess (bp) | bucket excess (bp) | 95% CI (bp) | hit rate | reference in CI | block t | passes |
|---|---|---|---|---|---|---|---|---|
| 1 | 4915 | 1.8 | 1.6 | [-4.2, 7.5] | 50.7% | yes | 0.55 | no |
| 5 | 4910 | 7.7 | 7.3 | [-8.0, 23.4] | 50.5% | yes | 0.92 | no |
| 10 | 4881 | 20.9 | 21.6 | [0.1, 45.0] | 50.9% | no | 1.89 | no |
| 20 | 4837 | 14.6 | 22.7 | [-11.3, 58.6] | 48.9% | yes | 1.27 | no |
| 60 | 4813 | 31.4 | 71.9 | [10.9, 135.1] | 50.7% | no | 2.27 | no |

### `low_vol_setup` — 9168 events after cooldown

| h | n | old excess (bp) | bucket excess (bp) | 95% CI (bp) | hit rate | reference in CI | block t | passes |
|---|---|---|---|---|---|---|---|---|
| 1 | 9168 | -0.8 | 0.1 | [-1.6, 1.8] | 50.4% | yes | 0.10 | no |
| 5 | 9165 | -5.2 | 0.3 | [-4.8, 5.2] | 50.7% | yes | 0.12 | no |
| 10 | 9163 | -11.5 | 2.0 | [-5.9, 10.1] | 50.7% | yes | 0.50 | no |
| 20 | 9161 | -15.4 | 9.9 | [-2.3, 21.8] | 51.8% | yes | 1.61 | no |
| 60 | 9109 | -49.2 | 18.9 | [-5.5, 42.9] | 50.8% | yes | 1.53 | no |

### `volume_trend_accumulation` — 14481 events after cooldown

| h | n | old excess (bp) | bucket excess (bp) | 95% CI (bp) | hit rate | reference in CI | block t | passes |
|---|---|---|---|---|---|---|---|---|
| 1 | 14481 | 1.6 | 1.4 | [-1.8, 4.6] | 50.5% | yes | 0.83 | no |
| 5 | 14465 | 5.5 | 6.9 | [-0.4, 14.5] | 50.2% | yes | 1.80 | no |
| 10 | 14411 | 3.1 | 3.7 | [-7.3, 15.8] | 49.4% | yes | 0.63 | no |
| 20 | 14285 | -11.1 | -4.4 | [-25.8, 16.4] | 49.6% | yes | -0.41 | no |
| 60 | 14160 | -11.7 | 23.5 | [-12.6, 61.1] | 49.3% | yes | 1.25 | no |

## 7. Sanity check — vol-matched random event sets

Copied verbatim. Each draw uses the same per-date/per-bucket counts, cooldown and bucket
excess as the real events; 20 draws, seeds 70000..70019. Mean and std are in bp.

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

The report flags `breakout_52week` h=20 at -3.9 bp (draw std 10.2 bp) and h=60 at
-8.4 bp (draw std 21.5 bp) in its header. With 20 draws those are about 1.7 and 1.8
standard errors from zero; the other 18 cells are within +/-2.0 bp. The deviation is
reported, not hidden; it is inside the draw-to-draw noise of this control and was not
treated as a code-level bias.

## 8. Part 2 — exit study in R and percent units

Copied verbatim. `gap` is strategy mean minus the vol-matched null mean; `CI` is the
95% month-block CI of the real trade mean and `ref` says whether the null mean sits
inside it; `block t = (mean - null mean)/se_block`; `signs` says the R and percent gap
signs agree. Percent columns are basis points. All four setups: `ref` is `yes` in every
R cell and every percent cell.

### `statistical_mean_reversion` — 16683 real entries

| Var | n | mean r_net | null r mean | gap R | CI R | block t (R) | mean pct (bp) | null pct mean (bp) | gap pct (bp) | CI pct (bp) | block t (pct) | signs | passes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | 16659 | 0.0494 | 0.0758 | -0.0264 | [-0.0590, 0.1607] | -0.47 | 28.3 | 42.1 | -13.8 | [-31.8, 90.6] | -0.44 | yes | no |
| B1 | 16651 | 0.0331 | 0.0614 | -0.0283 | [-0.1146, 0.1825] | -0.37 | 19.8 | 34.0 | -14.2 | [-63.2, 102.5] | -0.34 | yes | no |
| B2 | 16593 | 0.1545 | 0.1681 | -0.0135 | [0.0027, 0.3252] | -0.16 | 85.3 | 92.0 | -6.8 | [-0.3, 181.9] | -0.15 | yes | no |
| B3 | 16668 | 0.0453 | 0.0634 | -0.0182 | [-0.0475, 0.1439] | -0.37 | 26.6 | 34.5 | -7.9 | [-23.5, 78.8] | -0.30 | yes | no |
| B4 | 16639 | 0.0649 | 0.1109 | -0.0460 | [-0.3020, 0.3708] | -0.27 | 31.6 | 59.3 | -27.8 | [-167.6, 201.1] | -0.30 | yes | no |

### `breakout_52week` — 6819 real entries

| Var | n | mean r_net | null r mean | gap R | CI R | block t (R) | mean pct (bp) | null pct mean (bp) | gap pct (bp) | CI pct (bp) | block t (pct) | signs | passes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | 6772 | -0.0018 | 0.0146 | -0.0164 | [-0.0648, 0.0628] | -0.50 | 11.4 | 12.7 | -1.3 | [-18.7, 42.8] | -0.08 | yes | no |
| B1 | 6754 | 0.0010 | 0.0138 | -0.0128 | [-0.0946, 0.0960] | -0.26 | 20.1 | 14.0 | 6.0 | [-25.7, 66.9] | 0.26 | no | no |
| B2 | 6754 | 0.0127 | 0.0504 | -0.0378 | [-0.0801, 0.1055] | -0.80 | 20.4 | 24.7 | -4.3 | [-23.8, 66.3] | -0.19 | yes | no |
| B3 | 6786 | -0.0484 | -0.0118 | -0.0366 | [-0.1027, 0.0050] | -1.33 | -9.6 | -0.3 | -9.3 | [-37.5, 17.5] | -0.66 | yes | no |
| B4 | 6712 | 0.0641 | 0.0368 | 0.0273 | [-0.1483, 0.2618] | 0.26 | 56.9 | 32.5 | 24.4 | [-24.9, 137.2] | 0.59 | yes | no |

### `low_vol_setup` — 18346 real entries

| Var | n | mean r_net | null r mean | gap R | CI R | block t (R) | mean pct (bp) | null pct mean (bp) | gap pct (bp) | CI pct (bp) | block t (pct) | signs | passes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | 18338 | 0.0572 | 0.0379 | 0.0193 | [-0.0265, 0.1459] | 0.44 | 16.2 | 11.5 | 4.7 | [-9.5, 42.4] | 0.35 | yes | no |
| B1 | 18338 | 0.0998 | 0.0811 | 0.0187 | [-0.0051, 0.2125] | 0.34 | 27.7 | 23.4 | 4.3 | [-3.2, 60.3] | 0.26 | yes | no |
| B2 | 18330 | 0.1887 | 0.1559 | 0.0328 | [0.0586, 0.3201] | 0.49 | 53.3 | 44.2 | 9.1 | [15.3, 91.7] | 0.47 | yes | no |
| B3 | 18335 | 0.0604 | 0.0334 | 0.0270 | [-0.0302, 0.1639] | 0.55 | 15.3 | 8.5 | 6.7 | [-11.3, 45.0] | 0.47 | yes | no |
| B4 | 18336 | 0.2463 | 0.2069 | 0.0394 | [0.0914, 0.3995] | 0.50 | 71.9 | 63.1 | 8.8 | [26.8, 117.6] | 0.38 | yes | no |

### `volume_trend_accumulation` — 20830 real entries

| Var | n | mean r_net | null r mean | gap R | CI R | block t (R) | mean pct (bp) | null pct mean (bp) | gap pct (bp) | CI pct (bp) | block t (pct) | signs | passes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 | 20696 | 0.0161 | 0.0286 | -0.0125 | [-0.0372, 0.0731] | -0.44 | 11.7 | 18.6 | -6.9 | [-13.3, 38.3] | -0.53 | yes | no |
| B1 | 20635 | 0.0085 | 0.0391 | -0.0306 | [-0.0611, 0.0815] | -0.84 | 10.8 | 23.1 | -12.3 | [-21.3, 45.3] | -0.72 | yes | no |
| B2 | 20633 | 0.0554 | 0.0914 | -0.0360 | [-0.0248, 0.1384] | -0.86 | 28.4 | 45.1 | -16.7 | [-6.5, 68.2] | -0.87 | yes | no |
| B3 | 20750 | -0.0095 | 0.0106 | -0.0201 | [-0.0631, 0.0441] | -0.73 | -1.1 | 9.0 | -10.0 | [-24.5, 24.4] | -0.80 | yes | no |
| B4 | 20536 | 0.0809 | 0.0962 | -0.0153 | [-0.0779, 0.2200] | -0.20 | 49.4 | 56.3 | -6.8 | [-13.9, 106.8] | -0.22 | yes | no |

### Control shortfall

Copied verbatim. Requested signals are the real per-date/per-bucket counts; drawn
signals are what the vol-matched control could draw from the eligible pool of that
bucket.

| Setup | real entries | requested (total) | drawn (total) | mean requested/draw | mean drawn/draw | shortfall (total) |
|---|---|---|---|---|---|---|
| `statistical_mean_reversion` | 16683 | 1685800 | 1685800 | 16,858.00 | 16,858.00 | 0 |
| `breakout_52week` | 6819 | 687200 | 687200 | 6,872.00 | 6,872.00 | 0 |
| `low_vol_setup` | 18346 | 1881200 | 1881200 | 18,812.00 | 18,812.00 | 0 |
| `volume_trend_accumulation` | 20830 | 2116300 | 2116300 | 21,163.00 | 21,163.00 | 0 |

## 9. Result

Copied verbatim from the report's cell summary: **No cell passes.**

- Part 1 (E1 re-measurement): 0 of 20 cells pass.
- Part 2 (E2 re-measurement): 0 of 20 cells pass.
- No `block_t` in either part reaches `z_crit(20) = 3.023`.
- `low_vol_setup` B4 still shows a positive R gap (+0.0394) and a positive percent gap
  (+8.8 bp) against the vol-matched control, but its `block_t` is 0.50 (R) and 0.38
  (percent) and the null mean is inside both CIs. The E2 vs E1 sign disagreement does
  not survive the measurement fix as a passing cell.
- `breakout_52week` B1 is the only cell whose R and percent gap signs disagree
  (R -0.0128, percent +6.0 bp); it fails both metrics.
- Cumulative trials after this re-measurement: 20 (E1) + 20 (E2) + 20 (E4 Part 1) +
  20 (E4 Part 2) = 80 cells. None is out-of-sample.

## 10. Command evidence (copied verbatim from the work log)

E4 start gate (before any E4 edit; explicit 11-file CI list at that time):

```text
=== START GATE pytest ===
116 passed in 11.39s
TEST_EXIT=0
=== START GATE ruff (CI scope) ===
All checks passed!
RUFF_EXIT=0
```

New module tests:

```text
........                                                                   [100%]
8 passed in 1.71s
TEST_EXIT=0
```

Smoke run into a temp folder outside the repo (`breakout_52week`, 2 sanity draws,
2 null draws; `dirty=True` expected because the four code/workflow files were not
committed yet): exit 0, 1.5 minutes, report and JSON written. The full-run command:

```text
python scripts/research_vol_matched.py
```

Full run: exit 0, 26.6 minutes, `dirty=False`, revision
`49cad31b0a2bae03d9f9654f7a3dba6d742fc2ce`. It wrote
`docs/backtests/research/VOL_MATCHED_STUDY.md` and
`docs/backtests/research/event_study/vol_matched_20261117_185439.json`.

E4 end gate before COMMIT 2:

```text
=== END GATE pytest ===
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
124 passed in 10.96s
PYTEST_EXIT=0
```

`git diff --stat HEAD~2..HEAD` for the two E4 commits (plus-run lengths trimmed for
readability; file counts and the 3298 total are exact):

```text
 .github/workflows/research.yml                 |    2 +
 backend/app/research/matched_control.py        |  409 ++++++++
 backend/tests/test_research_matched_control.py |  317 +++++++
 docs/SESSIONS/research-discovery-log.md        |  218 ++++
 docs/backtests/research/VOL_MATCHED_STUDY.md   |  227 ++++
 docs/backtests/research/event_study/vol_matched_20261117_185439.json | 1292 ++++
 scripts/research_vol_matched.py                |  833 ++++++++
 7 files changed, 3298 insertions(+)
```

Per-commit: COMMIT 1 `49cad31` changed 4 files with 1561 insertions; COMMIT 2 `84c7f8d`
changed 3 files with 1737 insertions.

## 11. Deviations, corrections and known gaps

- `add_pct_returns` follows the task text literally: the cost-aware formula
  `exit*(1-c)/(entry*(1+c)) - 1` is stored in `ret_gross_pct` and mirrored in
  `ret_net_pct`, which Part 2 reports. This is stated in the module docstring and in
  the report definitions.

> Correction (E6, 2026-11-18): ret_gross_pct is exit/entry-1 (no costs); ret_net_pct is the cost-aware value. The original wording above was wrong. All reported numbers use ret_net_pct and are unchanged.

- The vol-matched control matches on volatility bucket and pool size only. It does not
  match on sector, industry, beta or liquidity beyond the existing eligibility rule.
- The bucket benchmark shifts the bucket series one bar per symbol, mirroring
  `events.universe_benchmark`; the event bucket itself is the signal-date bucket.
- Variants share the same entries and the same signals are reused across variants and
  null draws, so the 20 cells are not independent trials.
- The sanity check is descriptive: 20 draws, and the two `breakout_52week` cells
  flagged above are inside draw-to-draw noise.
- No portfolio capacity, slot competition, stops or capital constraint is modelled in
  Part 1; Part 2 is one trade at a time and ignores capacity.
- The old E1/E2 `p_high`/`p_low` and `gap/std` values are descriptive only because the
  old null's spread is 2-3.5x smaller than the strategy's month-block uncertainty.
  E4 produces no `p_high`/`p_low`.
- No network downloads were needed; the cache supplied 503 hits and 0 downloads.
- PowerShell does not expand `backend/tests/test_research_*.py`; the explicit CI list
  was passed to pytest.
- Broad `ruff check backend/app/research scripts` still fails on the same six
  pre-existing `W291` warnings in unrelated files and was not run as a gate; the exact
  CI ruff scope is clean.
- No engine, indicator, setup, control, metric, runner, `events.py`, `exit_study.py`,
  earlier study script or committed result artifact was edited.
- No push and no squash.

## 12. Universe and biases

- Exploratory, in-sample, survivorship-biased universe (today's S&P 500). Not evidence
  of a live edge.
- Controls must be matched on volatility (see
  `backend/app/research/matched_control.py`), because the strategy pools are not
  volatility-neutral and the old any-volatility null understated the strategy's own
  month-block uncertainty.
- The same four setups are re-used on the same data; cumulative trials are 80 cells and
  none of this is out-of-sample.
- No holdout was used. A passing cell would only be a candidate for the locked
  2021-2026 holdout, and no cell passes.

## 13. Not recorded

- Pre-registration written before E4: **not recorded** (none; the study is post-hoc and
  is labelled EXPLORATORY for that reason).
- Out-of-sample or walk-forward result for E4: **not recorded**.
- Sector- or size-matched control for E4: **not recorded** (volatility bucket and pool
  size only).
- Portfolio capacity / slot-competition result for E4: **not recorded** (ignored by
  design).
- Change to the D-75 pass bar, kill rule, scorecard or any FWD-v0.2 verdict:
  **not recorded** (none was made).

## 14. Decision

Record the measurement module, its tests, the study script, the definitions, the copied
numbers and the limits as EXPLORATORY research (H-15). Do not wire any part of E4 into
a live decision, the D-75 pass bar, the kill rule, the forward scorecard or a FWD-v0.2
verdict. The pre-registration template now uses the vol-matched CI plus
`|block_t| >= z_crit(m)` rule as its pass criterion; the old any-volatility
`p_high`/`p_low` rule is not a valid test and is no longer the template default.
