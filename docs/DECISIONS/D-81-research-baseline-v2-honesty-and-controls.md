# D-81: Research Baseline v2 - Look-Ahead Sizing, Forward-Fill Marking, Matched-Random Control, and a 2015-2026 Re-Run

**Date:** 2026-11-12
**Status:** Accepted and implemented. **The 2015-2026 re-run recorded here supersedes the
D-80 baseline results.** The D-80 cache, data-end and invariant fixes stand and are still
enforced in the harness.
**Branch:** `research/baseline-backtesting`
**Commit:** Uncommitted at the time of writing. The artifacts record HEAD `dcc9565` with
`run.code.dirty = true`.
**Related:** D-80 (span-keyed cache, data-end closes, invariant), D-79 (harness + defect
audit), H-10 in [`docs/backtests/HYPOTHESIS_LOG.md`](../backtests/HYPOTHESIS_LOG.md),
D-70 (honest engine), D-74 (measurement integrity), D-75 (pass bar), D-76 (sample
versioning).

## Context

D-80 fixed the two defects that invalidated the D-79 artifacts: the cache could serve a
different history span than requested, and positions that outlived their symbol's data
were never closed. A follow-up audit of the same harness found four further measurement
defects, none of which D-80 addressed:

1. **Look-ahead position sizing.** A new entry was sized from equity marked at *today's*
   close, but the entry fills at *today's* open. On a gap day the size uses a price that
   was not knowable when the order filled.
2. **Missing-bar marking and the final-bar sweep.** An open position with no bar on a
   given date could vanish from the daily mark (its value dropped to zero in the equity
   curve), and the final-bar sweep closed positions at each symbol's own last close and
   date instead of the panel's final bar. The last equity point could therefore disagree
   with realized cash.
3. **Mismatched random control.** The "random" control fired on 2% of every symbol every
   day regardless of liquidity or indicator warm-up. It traded a different opportunity
   set, and a different number of trades, from the strategy. The p-value compared
   populations that were not comparable.
4. **Sign-flipped p-value.** For a negative real value the code tested
   `mean(control <= real)`. A losing strategy could therefore produce a small p-value
   that read as significance. The question must always be "how often does a control do
   at least as well as the real strategy?", never the reverse.

Two smaller issues surfaced with the same audit:

- Yahoo no longer serves the index symbol `VIX`; the correct ticker is `^VIX`. The
  benchmark was silently absent from the panel.
- The D-80 window (2020-01-03..2023-12-29) was short and ended in 2023. A longer,
  current panel was requested for the baseline, with coverage checked before the run.

## Decision

Adopt the following harness contract for all research baselines:

1. **One benchmark definition.** `NON_TRADABLE = frozenset({"SPY", "^VIX", "VIX"})` is the
   single source of truth for benchmark/non-tradable symbols in `data.py`, `engine.py`,
   `control.py` and the runner. `download_daily()` requests `^VIX`.
2. **No look-ahead sizing.** New entries size from `last_equity` - the equity marked at
   the end of the previous iteration - never from equity recomputed at today's close.
3. **Every open position is marked and every position is closed.** Daily marking uses
   forward-filled closes (`close_ff`), so a missing bar carries the last known close
   instead of zero. A position whose symbol has no later bar closes at that symbol's last
   close (`data_end`, censored). The final bar closes everything that remains
   (`eod_censored`) at the panel's final date. `assert not positions` runs after the
   sweep. The final equity point is cash.
4. **A hard reconciliation guard.** `run_portfolio()` raises
   `RuntimeError("Equity reconciliation failed: ...")` when
   `abs(cash - (start_equity + sum(pnl_usd))) > 0.5`. The runner repeats the check and
   refuses to write an artifact that fails it.
5. **A matched control, not a different population.** `matched_random_signals()` fires
   the same number of entries per day as the strategy, on a random sample of symbols that
   pass `eligible()` (liquidity + all setup indicators non-NaN) on that date. The default
   control budget becomes 30 matched-random runs, 10 permuted-date runs and 2
   time-shifted runs. The old unmatched 2%/day random control remains available via
   `--n-random` but is not part of the default budget.
6. **One p-value direction.** `compute_control_pvalues()` always computes
   `p_raw = mean(control >= real)` and applies `(p_raw*n + 1)/(n + 1)`. It is never
   flipped. The reported metric is per-trade expectancy (`r_net_mean`), not R sum.
7. **A longer default panel with coverage checks.** Defaults are `--start 2015-01-01` and
   `--end <today>`. `coverage_report()` records `n_symbols`, `late_start` (first bar more
   than 400 days after the start, informational) and `early_end` (last bar more than 10
   days before the end). The runner refuses a panel where more than 5% of tradable
   symbols end early.
8. **Self-describing artifacts.** Each artifact keeps the D-80 `run` block and adds a
   `run_info` block with the requested window, symbol count, dropped symbols, exit and
   portfolio rules, control budget, short git commit and a `quick` flag. `p_values` is
   on `r_net_mean`; the old field name is replaced by `p_value_metric`.
9. **A completed run exits 0.** Significance is diagnostic. The runner prints
   `INFO: ...` and returns 0 whether the result is favorable, unfavorable or not
   significant. A failed reconciliation, coverage gate or span gate is still an error.
10. **A generated report and a quarantine.** `scripts/make_baseline_report.py` (stdlib
    only) reads the newest artifact per setup and writes `BASELINE_REPORT.md` with the
    pre-registered mechanical verdicts. The 13 superseded artifacts are moved, never
    deleted, to `docs/backtests/research/invalid_20261110/`.

## What changed

| # | Defect | Change | Regression test |
|---|---|---|---|
| 1 | Look-ahead sizing | Entries size off `last_equity` from the previous iteration; the `mark_price` recomputation inside the entry loop is removed. | `test_sizing_uses_previous_close_equity` |
| 2 | Missing-bar marking drops equity | Daily marking uses `close_ff` (forward-filled close) for every open position. | `test_missing_bar_does_not_drop_equity` |
| 3 | Final-bar sweep uses stale per-symbol dates | The sweep closes at the panel's final date with `close_ff`; `assert not positions`; final equity point is cash. | `test_final_bar_closes_all_positions` |
| 4 | No hard accounting check | `RuntimeError` when cash does not reconcile within $0.50; the runner refuses to write. | `test_reconciliation_on_random_data`, `test_final_equity_reconciles_with_realized_pnl` |
| 5 | Random control not comparable | `matched_random_signals()` matches the strategy's daily entry count and samples only `eligible()` symbols; eligibility is built once per panel. | `test_matched_random_matches_daily_count_and_is_reproducible`, `test_matched_random_respects_eligibility` |
| 6 | p-value flips for negative results | Always `mean(control >= real)` with `(k+1)/(n+1)`. | `test_pvalue_negative_real_is_not_flipped`, `test_pvalue_beats_every_control`, `test_pvalue_control_better_gives_one` |
| 7 | `VIX` never downloaded | `^VIX` is requested; `NON_TRADABLE` covers `SPY`, `^VIX` and the legacy `VIX`. | `test_panel_span_excludes_benchmarks` (updated) |
| 8 | No coverage visibility | `coverage_report()` + a >5% `early_end` gate. | `test_coverage_report_flags_symbols_that_end_early`, `test_coverage_report_late_start_is_informational` |
| 9 | Cache spans untested at file level | The span test now also asserts two distinct cache files for two spans. | `test_cache_is_keyed_by_requested_span` (extended) |
| 10 | One-off runs only | `--quick` / `--quick-setup`, `run_info`, `BASELINE_REPORT.md`, `invalid_20261110/`. | smoke run + report generation |

Supporting changes:

- `engine.py` precomputes `last_bar` and `last_close` per symbol once, instead of
  rebuilding date ordinals in the loop. The old `date_to_ordinal` map is removed.
- `control.py` builds the eligibility frame once per control suite. The matched
  control reuses it for all 30 runs.
- `run_research_baseline.py` adds `n_trades_mean`, `r_net_mean_mean` and
  `r_net_mean_std` to every control summary, so the report can show the control's trade
  count and expectancy distribution.
- `scripts/make_baseline_report.py` bootstraps the 95% CI of expectancy and applies the
  verdict rules verbatim: `INSUFFICIENT SAMPLE` (<100 trades), `SUSPECTED BUG` (failed
  reconciliation, PF > 2.5, win rate > 65%, or max drawdown worse than -40%),
  `CANDIDATE` (positive CI lower bound, matched p <= 0.05, and at least 75% of years with
  n >= 10 profitable), otherwise `NO EVIDENCE OF EDGE`.

## Verification

- **Tests:** `python -m pytest backend/tests/test_research_data.py
  backend/tests/test_research_engine.py backend/tests/test_research_metrics.py
  backend/tests/test_research_setups.py backend/tests/test_research_indicators.py
  backend/tests/test_research_control.py -q` -> **58 passed** (47 pre-existing + 11 new;
  the data and engine suites were extended in place and a control suite was added).
- **Lint:** `ruff check` clean on `backend/app/research`, all six research test modules,
  `scripts/run_research_baseline.py` and `scripts/make_baseline_report.py`.
- **Panel:** requested 2015-01-01..2026-11-11, actual 2015-01-02..2026-11-10. 503
  symbols loaded (501 tradable + SPY + ^VIX), 2 dropped (KVUE: 1 row; VYLR: 29 rows).
  `run.panel.n_symbols_ending_early = 0` in all four artifacts; 37 symbols start late
  (recent listings, informational).
- **Cache:** `.cache/research`, span-keyed by `SYMBOL__{start}__{end}` and a manifest.
  The first run downloaded 503 and failed 2; the next three runs were served entirely
  from cache (503 hits each).
- **Reconciliation:** all four artifacts record `invariant.holds = true` and the runner
  printed `Reconciliation: OK`; the generated report shows `PASS` for all four.
- **Sanity:** no trade enters on or before its signal in any artifact; max bars held is
  15 in all four; `data_end` trade count is 0 in all four (the clean panel covers every
  symbol end to end).
- **Quick smoke:** `python scripts/run_research_baseline.py --quick-setup
  statistical_mean_reversion` exited 0, printed `Reconciliation: OK`, and returned
  `INFO: NOT statistically significant vs controls (best p=0.6667)`.

## Baseline design (2015-2026)

| Item | Value |
|---|---|
| Window | 2015-01-01 to 2026-11-11 (actual 2015-01-02..2026-11-10) |
| Universe | `config/replay_universe_sp500.txt` (current S&P 500 snapshot), SHA-256 `a53242f2...9a729080` |
| Symbols | 501 tradable; 503 loaded including SPY and ^VIX; 2 dropped (KVUE, VYLR) |
| Cache | `.cache/research`, span-keyed; 503 downloaded once, then 503 hits per setup |
| Exits | 2.0 ATR stop, 3.0 ATR target, 15-bar time stop |
| Portfolio | $100,000 start, 0.5% risk, 8 positions, 20% notional cap, 15 bps/side |
| Controls | 30 matched-random, 10 permuted dates, 2 time-shifted +20..+60 bars; 0 unmatched random |
| Report statistics | Closed trades only (`censored == false`), exit date >= 2016-01-01 (2015 is warm-up) |
| Code | HEAD `dcc9565`, working tree dirty |

## Results (valid for this panel and window)

The table and verdicts below are the verbatim mechanical output of
[`BASELINE_REPORT.md`](../backtests/research/BASELINE_REPORT.md). Trade statistics
exclude censored trades and 2015 exits; account statistics include every trade.

| Setup | n | Win rate | Avg win R | Avg loss R | Expectancy net | 95% CI | Expectancy gross | PF | CAGR | Max DD | Reconciliation |
|---|---|---|---|---|---|---|---|---|---|---|---|
| breakout_52week | 1876 | 47.2% | 1.086 | -0.986 | -0.008 | [-0.059, 0.046] | 0.064 | 0.98 | -1.6% | -36.0% | PASS |
| low_vol_setup | 1982 | 47.5% | 1.132 | -1.025 | 0.000 | [-0.052, 0.051] | 0.092 | 1.00 | -0.7% | -43.0% | PASS |
| statistical_mean_reversion | 1860 | 47.7% | 1.012 | -0.926 | -0.001 | [-0.051, 0.050] | 0.060 | 1.00 | -0.9% | -35.2% | PASS |
| volume_trend_accumulation | 2373 | 47.8% | 1.108 | -0.982 | 0.018 | [-0.028, 0.063] | 0.091 | 1.03 | 0.2% | -37.8% | PASS |

Matched-random control, per-trade expectancy (`r_net_mean`):

| Setup | Control runs | Control trades (mean) | Control expectancy (mean +/- std) | Strategy expectancy | p (matched_random) |
|---|---|---|---|---|---|
| breakout_52week | 30 | 1979.0 | 0.014 +/- 0.023 | -0.008 | 0.9355 |
| low_vol_setup | 30 | 2156.9 | 0.006 +/- 0.017 | 0.000 | 0.6774 |
| statistical_mean_reversion | 30 | 2260.1 | 0.006 +/- 0.024 | -0.001 | 0.6129 |
| volume_trend_accumulation | 30 | 2468.3 | 0.019 +/- 0.027 | 0.018 | 0.7742 |

Mechanical verdicts (verbatim):

- **breakout_52week**: NO EVIDENCE OF EDGE
- **low_vol_setup**: SUSPECTED BUG investigate before trusting
- **statistical_mean_reversion**: NO EVIDENCE OF EDGE
- **volume_trend_accumulation**: NO EVIDENCE OF EDGE

The `low_vol_setup` verdict is triggered by the max-drawdown guard
(`-43.0% < -40%`). It is a request to investigate, not a diagnosis, and it is not a
comment on the deployed `low-vol-setup` screen.

## Reading the result

- **No setup produced a favorable significance result.** The smallest matched-control
  p-value is 0.6129; all four are well above 0.05. The mechanical verdict is
  `NO EVIDENCE OF EDGE` for three setups.
- **`low_vol_setup` hit the drawdown guard, not the p-value test.** Its expectancy is
  effectively zero (0.000, CI spanning zero), but the account path drew down 43.0%, over
  the report's -40% `SUSPECTED BUG` threshold. The correct next action is the one the
  verdict states: investigate the account path before trusting any reading.
- **The control now matches the strategy's opportunity set.** Matched control trade
  counts (1979-2468) are close to the strategies' (1876-2373 closed trades), and both
  expectancies sit within roughly 0.02R of each other. That is the expected shape when
  neither the setup nor a size-matched random book has an edge over this window.
- **Do not compare these numbers to D-80.** The window, the control and the p-value
  metric all changed. The D-80 2020-2023 figures are superseded and quarantined.

## What this does not settle

- **Survivorship.** The universe is the current S&P 500 membership. Companies removed
  from the index are absent; recent listings start late (37 symbols) and are included
  only from their first bar.
- **One window, in-sample.** 2015-2026 includes several regimes, but there is no
  walk-forward split, holdout or pre-registered out-of-sample test. A mechanical
  `NO EVIDENCE OF EDGE` is not proof that a setup cannot work; it is the absence of
  evidence in this panel.
- **Not a verdict on the deployed templates.** These are research implementations with
  fixed ATR exits, not the D-70 replay or the live `config/screens/*.yaml` templates.
- **The drawdown guard is blunt.** A -40% max drawdown triggers `SUSPECTED BUG` even
  when the reconciliation passes. It cannot distinguish a coding defect from a genuinely
  bad equity path.
- **Control budget.** 30 matched runs give a p-value floor of about 1/31 = 0.032; 10
  permuted runs give 1/11 = 0.091; 2 shifted runs give 1/3 = 0.333. The shifted control
  cannot establish superiority at 0.05 and is descriptive only.
- **No SPY comparison in the report.** The generated report records the account path but
  does not compute a buy-and-hold benchmark, so this record makes no benchmark claim.

## Consequences

- The D-80 result tables are **superseded**. The four `*_20261111_*_clean.json`
  artifacts and the nine earlier D-79/D-80 files are quarantined under
  `docs/backtests/research/invalid_20261110/` (moved, not deleted).
- `BASELINE_REPORT.md` becomes the citable summary for this panel. The four
  `*_20261111_21*.json` artifacts are the underlying evidence.
- H-10 is replaced with the D-81 result; the D-80 row remains as superseded history.
- The research README, decision index, docs index and root index are updated to point at
  D-81 and the new artifacts.
- **No live behavior changed.** The research package is not imported by the API, the
  gate, the journal, the scorecard or the forward loop. Nothing here enters the D-75 pass
  bar, the kill rule or any FWD-v0.2 verdict.

## Alternatives considered

- **Keep the unmatched 2%/day random control and add matched as an extra.** Rejected as
  the default: the unmatched control trades a different number of names for a different
  reason, so its p-value answers a different question. It remains available with
  `--n-random` for continuity.
- **Keep `r_net_sum` as the p-value metric.** Rejected: R sum grows with trade count, and
  the matched control can trade a different count on a given run. Per-trade expectancy is
  the size-independent comparison.
- **Flip the p-value direction for negative results.** Rejected: it makes a losing
  strategy look significant. A single direction is the only honest test.
- **Re-run only the engine fix on the D-80 2020-2023 window.** Rejected: the window was
  short, the cache was already being rebuilt, and the request was a current panel. One
  clean 2015-2026 run replaces the superseded 2020-2023 numbers.
- **Delete the superseded artifacts.** Rejected: they are the audit trail for the four
  defects. They are moved to a quarantine directory with a README that says not to cite
  them.
