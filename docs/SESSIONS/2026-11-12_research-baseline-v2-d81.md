# 2026-11-12 - Research Baseline v2: Sizing, Marking, Matched Control, 2015-2026 Re-Run (D-81)

**Branch:** `research/baseline-backtesting`
**Commit documented:** Uncommitted. HEAD is `dcc9565`; the artifacts record
`run.code.dirty = true`.
**Decision:** [D-81](../DECISIONS/D-81-research-baseline-v2-honesty-and-controls.md)
**Supersedes:** [D-80](../DECISIONS/D-80-research-baseline-remediation.md) results (the
cache, data-end and invariant fixes stand)
**Experiment:** H-10 in [`docs/backtests/HYPOTHESIS_LOG.md`](../backtests/HYPOTHESIS_LOG.md)
**Documented:** 2026-11-12

---

## Summary

D-80 made the research harness's cache and position lifecycle honest. A follow-up audit
of the same harness found four more ways the baseline could mislead: entries were sized
from a price that filled later (look-ahead), a missing bar could drop an open position
from the equity mark, the random control traded a different opportunity set from the
strategy, and the p-value flipped direction for negative results so a losing strategy
could look significant.

This session fixed all four, replaced the default random control with a size-matched one,
added a coverage gate and a hard equity reconciliation, moved the default window to
2015-2026, re-ran all four setups on one clean panel, quarantined the 13 superseded
artifacts, and generated `BASELINE_REPORT.md` from the new artifacts with a stdlib-only
script.

Outcome: **58 tests pass**, `ruff` clean, all four accounts reconcile, and the mechanical
report verdict is `NO EVIDENCE OF EDGE` for `breakout_52week`,
`statistical_mean_reversion` and `volume_trend_accumulation`, with `low_vol_setup`
flagged `SUSPECTED BUG investigate before trusting` because its max drawdown (-43.0%)
breaches the report's -40% guard. No production code path is involved.

---

## The four defects and their fixes

### 1. Look-ahead position sizing

Entries fill at the next open, but size came from equity marked at **today's close**.
On a gap the size used a price that was not available at the fill.

Fix: keep `last_equity` from the end of the previous iteration and size from it. The
in-loop `mark_price` equity recomputation is gone.

Test: `test_sizing_uses_previous_close_equity` asserts the share count implied by the
prior day's equity, not today's close.

### 2. Missing-bar marking and the final-bar sweep

If an open position's symbol had no bar on a date, the equity mark skipped it entirely -
the position's value silently vanished for that day. The final-bar sweep also closed at
each symbol's own last close/date, which could be before the panel's final bar.

Fix: precompute forward-filled closes (`close_ff`) and mark every open position through
them. A symbol with no later bar is closed at its last close (`data_end`, censored). The
final bar closes everything that remains (`eod_censored`) at the panel's last date, then
`assert not positions`. The last equity point is cash.

Tests: `test_missing_bar_does_not_drop_equity`,
`test_position_closed_when_data_ends`, `test_final_bar_closes_all_positions`.

### 3. Mismatched random control

The control fired on 2% of every symbol every day, ignoring liquidity and indicator
warm-up. It traded a different set of names and a different number of trades from the
strategy, so the p-value compared incomparable populations.

Fix: `matched_random_signals()` counts the strategy's entries per date and fires the same
number on a random sample of `eligible()` symbols (liquid and all required indicators
non-NaN) for that date. Eligibility is built once per control suite. Default budget is
30 matched / 10 permuted / 2 shifted / 0 unmatched-random; the old random control remains
available via `--n-random`.

Tests: `test_matched_random_matches_daily_count_and_is_reproducible`,
`test_matched_random_respects_eligibility`.

### 4. Sign-flipped p-value

For a negative real value the code computed `mean(control <= real)`. A losing strategy
therefore produced a small p-value that read as favorable significance.

Fix: always `p_raw = mean(control >= real)` with `(p_raw*n + 1)/(n + 1)`. The metric is
per-trade expectancy (`r_net_mean`), not R sum. The direction is never flipped.

Tests: `test_pvalue_negative_real_is_not_flipped`,
`test_pvalue_beats_every_control`, `test_pvalue_control_better_gives_one`.

### Smaller fixes

- `NON_TRADABLE = frozenset({"SPY", "^VIX", "VIX"})` replaces the scattered
  `("SPY", "VIX")` checks. `download_daily()` now requests `^VIX` (Yahoo no longer serves
  `VIX`), so the benchmark is actually present.
- `coverage_report()` records `n_symbols`, `late_start` and `early_end`; the runner
  refuses a panel with more than 5% `early_end`.
- The runner repeats the `final_equity == start_equity + sum(pnl_usd)` check and refuses
  to write on failure; `run_portfolio()` raises `RuntimeError` on the same condition.
- `run_info` is added to every artifact (window, symbol count, dropped, rules, controls,
  git commit, quick flag). `run` keeps the D-80 metadata.
- `--quick` / `--quick-setup` run 40 symbols over 2019-2020 in a separate cache.
- A completed run always exits 0; significance is printed as `INFO:`.
- `scripts/make_baseline_report.py` generates `BASELINE_REPORT.md` from artifacts using
  only the standard library.

---

## Verification

| Check | Result |
|---|---|
| Research tests | **58 passed** (47 existing + 11 new) |
| `ruff check` (research pkg, runner, report script, tests) | clean |
| Equity invariant | `holds = true` in all four artifacts |
| Reconciliation | `Reconciliation: OK` in all four runs; report `PASS` |
| Panel coverage | `n_symbols_ending_early = 0` in all four; 37 `late_start` (recent listings) |
| Requested vs actual span | 2015-01-01..2026-11-11 requested; 2015-01-02..2026-11-10 actual |
| Cache | 503 downloaded once (2 failures); 503 hits on each of the next three runs |
| No look-ahead entry | PASS in all four (entry date strictly after signal date) |
| Max bars held | 15 in all four (`<= max_hold`) |
| `data_end` trades | 0 in all four (clean panel) |
| Quick smoke | exit 0, `Reconciliation: OK`, `INFO: NOT statistically significant ... p=0.6667` |

---

## Re-run design

| Item | Value |
|---|---|
| Window | 2015-01-01 to 2026-11-11 (actual 2015-01-02..2026-11-10) |
| Universe | current S&P 500 snapshot, SHA-256 `a53242f2...9a729080` |
| Symbols | 501 tradable; 503 loaded with SPY + ^VIX; 2 dropped (KVUE 1 row, VYLR 29 rows) |
| Cache | `.cache/research`, span-keyed; 503 downloaded, then 503 hits per setup |
| Exits | 2.0 ATR stop, 3.0 ATR target, 15-bar time stop |
| Portfolio | $100,000 start, 0.5% risk, 8 positions, 20% notional cap, 15 bps/side |
| Controls | 30 matched-random, 10 permuted, 2 shifted; 0 unmatched random |
| Code | HEAD `dcc9565`, dirty |

Trade statistics in the report exclude censored trades (forced `data_end` /
`eod_censored` closes) and exits before 2016-01-01 (2015 is indicator warm-up). Account
statistics include every trade.

---

## Results

Main table, verbatim from `BASELINE_REPORT.md`:

| Setup | n | Win rate | Avg win R | Avg loss R | Expectancy net | 95% CI | Expectancy gross | PF | CAGR | Max DD | Reconciliation |
|---|---|---|---|---|---|---|---|---|---|---|---|
| breakout_52week | 1876 | 47.2% | 1.086 | -0.986 | -0.008 | [-0.059, 0.046] | 0.064 | 0.98 | -1.6% | -36.0% | PASS |
| low_vol_setup | 1982 | 47.5% | 1.132 | -1.025 | 0.000 | [-0.052, 0.051] | 0.092 | 1.00 | -0.7% | -43.0% | PASS |
| statistical_mean_reversion | 1860 | 47.7% | 1.012 | -0.926 | -0.001 | [-0.051, 0.050] | 0.060 | 1.00 | -0.9% | -35.2% | PASS |
| volume_trend_accumulation | 2373 | 47.8% | 1.108 | -0.982 | 0.018 | [-0.028, 0.063] | 0.091 | 1.03 | 0.2% | -37.8% | PASS |

Matched-random control on `r_net_mean`:

| Setup | Control runs | Control trades (mean) | Control expectancy (mean +/- std) | Strategy expectancy | p (matched_random) |
|---|---|---|---|---|---|
| breakout_52week | 30 | 1979.0 | 0.014 +/- 0.023 | -0.008 | 0.9355 |
| low_vol_setup | 30 | 2156.9 | 0.006 +/- 0.017 | 0.000 | 0.6774 |
| statistical_mean_reversion | 30 | 2260.1 | 0.006 +/- 0.024 | -0.001 | 0.6129 |
| volume_trend_accumulation | 30 | 2468.3 | 0.019 +/- 0.027 | 0.018 | 0.7742 |

Shadow controls (not used by the verdict, recorded for context): permuted p-values are
1.0000 / 0.7273 / 0.8182 / 0.7273 and shifted p-values are 0.6667 / 0.3333 / 1.0000 /
0.3333 for breakout / low_vol / SMR / volume respectively. With 10 and 2 runs, their
floors are 1/11 = 0.091 and 1/3 = 0.333.

Mechanical verdicts, verbatim:

- **breakout_52week**: NO EVIDENCE OF EDGE
- **low_vol_setup**: SUSPECTED BUG investigate before trusting
- **statistical_mean_reversion**: NO EVIDENCE OF EDGE
- **volume_trend_accumulation**: NO EVIDENCE OF EDGE

The `low_vol_setup` flag is the max-drawdown rule (`-43.0% < -40%`), not a p-value
result. It is a mechanical request to inspect the account path.

---

## Reading (mechanical only)

- No setup reached a favorable matched-control p-value; the smallest is 0.6129.
- The matched control's trade counts (1979-2468) are close to the strategies' closed
  counts (1876-2373), which is the intended comparability property.
- `low_vol_setup` has near-zero expectancy and the worst drawdown, so the report's
  `SUSPECTED BUG` guard fires. Investigate; do not infer a cause from this table.
- Do not compare these figures with D-80: the window, control and p-value metric all
  changed.
- These are research implementations with fixed ATR exits, not the deployed templates.
  No result here changes a screen, weight, gate, sample or forward verdict.

---

## Files

```
backend/app/research/control.py
backend/app/research/data.py
backend/app/research/engine.py
backend/tests/test_research_control.py        (new)
backend/tests/test_research_data.py
backend/tests/test_research_engine.py
scripts/run_research_baseline.py
scripts/make_baseline_report.py               (new)
docs/backtests/research/BASELINE_REPORT.md    (new)
docs/backtests/research/{setup}_20261111_21*.json   (new artifacts)
docs/backtests/research/invalid_20261110/     (13 quarantined artifacts + README)
```

## Documentation updates

- Created `docs/DECISIONS/D-81-research-baseline-v2-honesty-and-controls.md`.
- Created this session log.
- Rewrote `docs/backtests/research/README.md` for the 2015-2026 artifacts, the matched
  control, the new schema fields and the quarantine.
- Replaced H-10 in `docs/backtests/HYPOTHESIS_LOG.md` with the D-81 result; the D-80 row
  remains as superseded history.
- Updated `docs/DECISIONS/index.md`, `docs/index.md` and root `INDEX.md`.
- Added a superseded-results banner to D-80; its fixes remain in force.
- `ARCHITECTURE.md` and `API.md` intentionally unchanged: no production wiring.

---

## Next steps

1. Investigate the `low_vol_setup` account path before treating its expectancy as
   meaningful (the report asks for this explicitly).
2. If any setup is to be pursued, pre-register the window, controls and hit/miss bar
   before a new run; do not re-run on a different window until it passes.
3. Optional: raise `--n-shifted` above 20 so that control can reach p < 0.05, and add a
   walk-forward split (e.g. 2015-2020 fit, 2021-2026 test).
4. Optional: store `coverage_report` counts in `run_info` so future artifacts carry them
   directly (the report currently falls back to `run.panel`).
5. Commit the uncommitted code, tests, artifacts, quarantine and docs when approved.

---

## Status

| Item | Status |
|---|---|
| Look-ahead sizing | Fixed + tested |
| Missing-bar marking / final sweep | Fixed + tested |
| Matched-random control | Implemented + tested |
| One-sided p-value | Fixed + tested |
| `^VIX` benchmark | Fixed |
| Coverage gate / `coverage_report` | Implemented + tested |
| Hard equity reconciliation | Enforced in engine and runner |
| `run_info` / quick mode / INFO exit code | Implemented |
| Superseded artifacts | Quarantined under `invalid_20261110/` (moved, not deleted) |
| 2015-2026 re-run | Done, 4/4 reconcile, report generated |
| Production impact | None |
| Live trading rules | Unchanged |
