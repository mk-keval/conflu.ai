# 2026-11-17 - Research Baseline v4: Seed-Averaged Headline and P-Value (D-83)

**Branch:** `research/baseline-backtesting`
**Commits documented:** `3bfb68c` (code + tests), `8db1c25` (four v4 artifacts +
regenerated `BASELINE_REPORT.md`), plus this documentation commit (find it with
`git log --oneline -- docs/SESSIONS/2026-11-17_research-baseline-v4-d83.md`).
**Decision:** [D-83](../DECISIONS/D-83-research-baseline-v4-seed-averaged.md)
**Supersedes:** [D-82](../DECISIONS/D-82-research-baseline-v3-engine-realism.md) headline
expectancy and p-value (every D-82 engine guarantee stands and is still enforced)
**Experiment:** H-12 in [`docs/backtests/HYPOTHESIS_LOG.md`](../backtests/HYPOTHESIS_LOG.md)
**Documented:** 2026-11-17

---

## Summary

D-82's headline came from one engine seed (42). The engine seed does not change the
signals; it only shuffles same-date candidates when more than one competes for a slot. It
nevertheless moves the measured per-trade expectancy: `DIAGNOSTICS.md` already recorded a
20-seed spread (std 0.0140-0.0230 R) around the D-82 numbers.

T10 makes the headline and the test use a seed-averaged strategy:

1. `scripts/run_research_baseline.py` gains `--n-strategy-seeds` (default 20) and runs the
   same signals under seeds 42..42+N-1. Seed 42 remains the primary artifact run, so
   trades, equity, metrics, account statistics and every existing field are unchanged.
2. `run_info.strategy_seeds` records `{seeds, r_net_mean[], mean, std, se}`; `std` is
   population std (`ddof=0`, matching `research_diagnostics.py`), `se = std/sqrt(N)`.
3. `p_values_seed_avg` applies `compute_control_pvalues` to the seed-mean `r_net_mean`
   against the same 30 matched-random / 10 permuted / 2 shifted control runs. `p_values`
   (seed 42) is untouched.
4. `scripts/make_baseline_report.py` adds `Expectancy (mean of N seeds)`, the control-table
   `Strategy seed mean` / `Gap vs control` / `SE of gap` / `p (seed-averaged)` columns,
   uses the seed-averaged p for the verdict, and prints an informational line when the gap
   is more than 2 SE negative. Older artifacts render `n/a` and fall back to seed 42.
   (The flag rule was corrected in T11 to `Gap / control std < -2.0`; see the T11 note
   below.)
5. All four setups were re-run with defaults on the 2015-01-01..2026-11-17 panel and
   `BASELINE_REPORT.md` was regenerated. All four verdicts remain
   **NO EVIDENCE OF EDGE**.

## Code changes (commit `3bfb68c`)

- `scripts/run_research_baseline.py`
  - new `strategy_seed_summary`, `strategy_seed_r_net_mean`, `run_strategy_seeds`;
  - `run_backtest(..., n_strategy_seeds=20)` sweeps seeds and uses seed 42's
    `trades`/`equity` as the primary result;
  - `save_results` gains `pvalues_seed_avg` (between `pvalues_sharpe` and `metadata`) and
    writes `p_values_seed_avg`;
  - `--n-strategy-seeds` CLI flag with a `>= 1` validation;
  - console INFO significance line now uses the seed mean and labels it
    "strategy seed mean".
- `scripts/make_baseline_report.py`
  - `seed_stats` / `gap_stats` helpers; `CONTROL_NOTE` mentions the seed-averaged formula;
  - main-table seed-mean column (header says `mean of N seeds` when every artifact agrees
    on N);
  - control table gains seed-mean, gap, SE and seed-averaged p columns;
  - verdict uses `p_matched_seed_avg` with fallback to `p_matched`;
  - informational underperformance lines and two new deviation bullets.
- Tests (9 new): `test_strategy_seed_summary_reports_list_and_stats`,
  `test_run_strategy_seeds_on_synthetic_panel`, `test_artifact_contains_strategy_seeds`,
  `test_main_table_renders_seed_mean_column`,
  `test_control_table_renders_gap_se_and_seed_averaged_p`,
  `test_underperformance_line_when_gap_below_two_se`,
  `test_no_underperformance_line_when_gap_is_inside_two_se`,
  `test_verdict_uses_seed_averaged_p_value`,
  `test_verdict_seed_average_can_remove_candidate`.

## Commands and exact output

```text
$ pytest -q backend/tests/test_research_control.py backend/tests/test_research_data.py backend/tests/test_research_diagnostics.py backend/tests/test_research_engine.py backend/tests/test_research_indicators.py backend/tests/test_research_metrics.py backend/tests/test_research_runner.py backend/tests/test_research_setups.py backend/tests/test_make_baseline_report.py
....................................................................................................... [100%]
103 passed in 11.42s
TEST_EXIT=0

$ ruff check scripts/run_research_baseline.py scripts/make_baseline_report.py backend/tests/test_research_runner.py backend/tests/test_make_baseline_report.py
All checks passed!
RUFF_EXIT=0
```

```text
$ python scripts/run_research_baseline.py --quick --n-strategy-seeds 2 --setup statistical_mean_reversion
Strategy seeds:2 (42..43)
Running portfolio backtest (strategy seeds 42..43, n=2)...
Strategy seed sweep: mean=-0.0436 std=0.0119 se=0.0084
P-VALUES (vs R-net Mean, seed 42)
  matched_random: p = 1.0000
P-VALUES (vs R-net Mean, strategy seed mean)
  matched_random: p = 1.0000
Results saved to: .cache/research_quick/out\statistical_mean_reversion_20261117_094331.json
INFO: NOT statistically significant vs controls (seed-averaged best p=0.5000 on shifted)
```

Artifact from the smoke run:

```text
{'seeds': [42, 43], 'r_net_mean': [-0.05554465933559563, -0.03167169808908953],
 'mean': -0.043608178712342585, 'std': 0.01193648062325305, 'se': 0.008440366392204057}
p_values {'matched_random': 1.0, 'random': 1.0, 'permuted': 1.0, 'shifted': 0.5}
p_values_seed_avg {'matched_random': 1.0, 'random': 1.0, 'permuted': 1.0, 'shifted': 0.5}
```

## Four v4 baseline runs (default flags)

Each run was preceded by the guard's own check; every check printed
`GUARD_BEFORE <setup> : 3bfb68c False`.

| Setup | Timestamp | n | Seed 42 | 20-seed mean (std / se) | Control mean | Gap | SE | p seed 42 | p seed-avg | INFO tail |
|---|---|---|---|---|---|---|---|---|---|---|
| `breakout_52week` | 20261117_095332 | 1686 | +0.027659 | +0.027783 (0.014752 / 0.003299) | +0.035506 | -0.007723 | 0.005951 | 0.6452 | 0.6452 | best p=0.3333 on shifted |
| `low_vol_setup` | 20261117_100100 | 1747 | +0.024281 | +0.010719 (0.018492 / 0.004135) | +0.025300 | -0.014581 | 0.006248 | 0.5484 | 0.7097 | best p=0.6667 on shifted |
| `statistical_mean_reversion` | 20261117_100839 | 1677 | +0.056569 | +0.016732 (0.018265 / 0.004084) | +0.034889 | -0.018157 | 0.005874 | 0.2258 | 0.8065 | best p=0.7273 on permuted |
| `volume_trend_accumulation` | 20261117_101631 | 2147 | -0.006896 | +0.003598 (0.021337 / 0.004771) | +0.050210 | -0.046611 | 0.006024 | 1.0000 | 1.0000 | best p=1.0000 on matched_random |

Panel for all four: requested 2015-01-01..2026-11-17; actual 2015-01-02..2026-11-17; 501
tradable; 2 dropped (KVUE 1 row, VYLR 34 rows). Cache: breakout downloaded 503 (2
failed), the other three reused it (503 hits each). Every artifact records
`run.code.revision = 3bfb68c`, `dirty = false`, `allow_same_day_recycling = false`,
`eval_start = "2016-01-01"`, and 20 seeds 42..61.

Seed lists (all four, by construction): 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53,
54, 55, 56, 57, 58, 59, 60, 61.

Per-seed `r_net_mean` (breakout, 20 values): 0.027659, 0.047358, 0.035895, 0.048274,
0.005165, 0.007304, 0.009124, 0.014831, 0.018729, 0.053073, 0.034587, 0.046694, 0.030402,
0.037665, 0.002623, 0.028608, 0.027436, 0.028005, 0.016966, 0.035264.

## Report regeneration

```text
$ python scripts/make_baseline_report.py
Wrote docs/backtests/research\BASELINE_REPORT.md (4 setups)
REPORT_EXIT=0
```

Rendered control table (verbatim):

```text
| Setup | Control runs | Control trades (mean) | Control expectancy (mean +/- std) | Strategy expectancy (seed 42) | Strategy seed mean | Gap vs control (strategy seed-mean - control mean) | SE of gap | p (seed 42) | p (seed-averaged) |
| breakout_52week | 30 | 1664.2 | 0.036 +/- 0.027 | 0.028 | 0.028 | -0.008 | 0.006 | 0.6452 | 0.6452 |
| low_vol_setup | 30 | 1793.6 | 0.025 +/- 0.026 | 0.024 | 0.011 | -0.015 | 0.006 | 0.5484 | 0.7097 |
| statistical_mean_reversion | 30 | 1870.0 | 0.035 +/- 0.023 | 0.057 | 0.017 | -0.018 | 0.006 | 0.2258 | 0.8065 |
| volume_trend_accumulation | 30 | 2034.2 | 0.050 +/- 0.020 | -0.007 | 0.004 | -0.047 | 0.006 | 1.0000 | 1.0000 |
```

Underperformance lines printed for `low_vol_setup`, `statistical_mean_reversion` and
`volume_trend_accumulation`, not `breakout_52week`.

**T11 correction (2026-11-17):** the `gap < -2 SE` rule was replaced by
`Gap / control std < -2.0`, because the SE ignores selection variability and overstated
significance by roughly 4x. The report was regenerated from the same four artifacts (no
re-run). Only `volume_trend_accumulation` remains flagged (-2.31); breakout (-0.28),
low_vol (-0.57) and SMR (-0.79) are not. The two underperformance tests were renamed and a
new `test_old_se_rule_flags_but_control_std_rule_does_not` was added; p-values and verdicts
are unchanged. See the T11 entry in
[`research-harden-d82-1og.md`](research-harden-d82-1og.md).

## Commits

| Commit | Contents |
|---|---|
| `3bfb68c` | `feat(research): seed-averaged headline and p-value (D-83)` - two scripts + two test files |
| `8db1c25` | `research baseline v4 artifacts with seed-averaged headline (D-83)` - four artifacts + regenerated report |
| this commit | `docs(research): record D-83 seed-averaged baseline` |

## Deviations and notes

- The headline and p-value rule changed **after** the D-82 tables and the DIAGNOSTICS seed
  sweep were read. The record labels the result exploratory for that reason (D-83,
  "Deviations").
- The four v4 runs used the default `--end` (2026-11-17), so their panel ends five sessions
  after the D-82 artifacts. The D-82/D-83 columns in D-83 are therefore not a
  one-variable comparison; the within-run seed-42 vs seed-mean columns are.
- Old artifacts still render: the report falls back to the seed-42 p-value and prints
  `n/a` in the seed columns. Verified against the D-82 artifacts during development, before
  the v4 artifacts replaced them as the newest per setup.
- The `p_values_seed_avg` test treats the seed mean as a single realized strategy value;
  the seed standard error is reported separately as the gap SE, not folded into p.
- PowerShell globs for pytest are unreliable here, so the nine test files were listed
  explicitly.
- No engine, indicator, control, data or metrics code changed in T10. The cache was reused
  where the span already covered 2026-11-17; breakout downloaded because its cached span
  ended earlier.

## Post-task documentation coverage

- `docs/DECISIONS/D-83-research-baseline-v4-seed-averaged.md` (this decision).
- `docs/backtests/HYPOTHESIS_LOG.md`: H-12 row, H-12 section, change-log row; H-11 marked
  superseded for the headline.
- `docs/backtests/research/README.md`: v4 artifact banner, provenance table, schema
  additions, report pointer.
- `docs/DECISIONS/D-82-research-baseline-v3-engine-realism.md`: banner stating the
  headline is superseded by D-83.
- `docs/DECISIONS/index.md`, `docs/index.md`, `INDEX.md`: index entries.
- `docs/SESSIONS/research-harden-d82-1og.md`: T10 work-log entry with the exact commands.
