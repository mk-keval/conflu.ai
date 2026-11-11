# D-80: Research Baseline Remediation - Span-Keyed Cache, Data-End Closes, Self-Describing Artifacts

**Date:** 2026-11-11
**Status:** Accepted and implemented. The clean re-run recorded here **supersedes the
D-79 baseline results**; the D-79 artifacts remain in the repository only as an audit
trail of the defects.
**Branch:** `research/baseline-backtesting`
**Commit:** `821454e` (fixes + tests). Artifacts and this record: the commit that adds them.
**Related:** D-79 (harness + defect audit), H-10 in
[`docs/backtests/HYPOTHESIS_LOG.md`](../backtests/HYPOTHESIS_LOG.md), D-70 (honest
engine), D-74 (measurement integrity), D-75 (pass bar), D-76 (sample versioning).

## Context

D-79 accepted the research harness but declared its four committed baseline artifacts
**not valid evidence**. Two defects caused that:

1. `download_daily()` reused a cache file based on age and row count, never on the
   requested span. 440 of 498 symbols covered only 2020 while 40 covered 2014-2024.
2. `run_portfolio()` never closed a position whose symbol's data had ended. The cash
   was not returned and the daily mark dropped the position, producing a permanent
   artificial loss. For `low_vol_setup` and `volume_trend_accumulation` the stranded
   positions consumed the account, so no post-2020 position could be sized (`shares < 1`)
   and both books went dormant for four years.

D-79 listed five remediation items before any result could be cited. This record
implements them, verifies the fixes, and records one re-run on a single consistent panel.

## Decision

Adopt a span-keyed cache with a manifest, close any position that outlives its
symbol's data at that symbol's last available close (censored `data_end`), enforce
the equity invariant at write time, and make each artifact self-describing enough to
be audited without the cache. The resulting re-run is the only baseline that may be
cited; the D-79 artifacts remain as an audit trail.

## What changed

| # | D-79 item | Change | Regression test |
|---|---|---|---|
| 1 | Cache correctness | Cache key is `SYMBOL__{start}__{end}`. A `_manifest.json` records the request, fetch time, row count and actual first/last bar per key. A hit requires the **same requested span** *and* age < `max_age_hours`. Cached rows are clipped to the request. Corrupt entries warn and fall through to a fresh download instead of dropping the symbol. | `test_cache_is_keyed_by_requested_span`, `test_same_span_reuses_cache`, `test_force_download_bypasses_cache`, `test_cache_expiry_forces_download`, `test_end_is_inclusive`, `test_manifest_records_the_request`, `test_panel_span_excludes_benchmarks`, `test_load_universe_normalises_symbols` |
| 2 | Equity integrity | Any open position whose symbol has no later bar is closed at that symbol's **last available close** with `exit_reason="data_end"` and `censored=True`. The final-bar sweep still closes the rest as `eod_censored`. The runner refuses to write if `final_equity != start_equity + sum(pnl_usd)`. | `test_data_end_closes_open_position`, `test_final_bar_closes_all_positions`, `test_final_equity_reconciles_with_realized_pnl` |
| 3 | Self-describing artifacts | Artifacts now carry requested vs actual span, per-symbol coverage, universe path + SHA-256, symbols loaded/dropped with reasons, cache counters, costs, exits, seeds, code revision + dirty flag, library versions and limitations. Both p-value sets (`r_net_sum` and `sharpe`) are persisted. | covered by the smoke run and the manifest tests |
| 4 | Re-run on one panel | Four setups, one window (2020-01-03 to 2023-12-29), one cache, same control budget (100/50/5). Recorded below and in H-10. | run-level: `run.invariant.holds == true`, `run.actual_span == run.requested_span` |
| 5 | Survivorship | Recorded in every artifact's `run.limitations` and in the README banner. | - |

Supporting changes made while doing the above:

- `compute_metrics(...)` now regresses the benchmark return series as given instead of
  differencing it a second time. The old path produced `inf` on any flat close and left
  `alpha`/`beta` silently at zero; beta also used a population variance against a sample
  covariance. The alpha/beta fields are populated in the clean artifacts.
- `compute_metrics(..., start_equity=...)` uses the configured starting equity rather
  than the first equity point. A new `pnl_usd_all` counts **every** trade including
  forced closes; `pnl_usd_sum` still covers strategy exits only.
- The span guard (`_validate_panel`) refuses to write when the actual panel is more
  than 10 days short of the request, unless `--allow-partial-panel` is passed, in which
  case the artifact is written with `cache.panel_warnings`.
- The exit code is now `0` only when the best control p-value is < 0.05 **and** the
  real metric is better than that control's mean. Unfavorable significance and
  non-significance both exit `1`.
- Candidate lookup is precomputed once per run (`_candidates_by_date`) instead of
  rebuilding every symbol's bar history for every date and symbol. The original
  implementation made 155 control runs per setup impractical; this is what makes the
  100/50/5 budget affordable (about 6-7 minutes per setup).

## Artifact contract

`run` block, in addition to the existing `metrics` / `trades` / `equity_curve` /
`control_summary` / `p_values`:

| Field | Meaning |
|---|---|
| `requested_span`, `actual_span` | The window asked for and the window delivered |
| `panel.symbol_coverage` | Per-symbol first/last bar, bar count, `ends_early` flag |
| `universe` | File path, SHA-256, symbols requested/loaded, dropped with reasons |
| `cache` | Directory, hits, misses, downloads, failures, span warnings |
| `rules`, `controls` | Sizing/costs/exits and the control budget, including the candidate seed |
| `invariant` | `start_equity`, `pnl_usd_all`, `final_equity`, `holds`, formula |
| `code`, `environment` | Git revision + dirty flag, Python/pandas/numpy/yfinance versions |
| `limitations` | Declared caveats, including survivorship |

## Verification

- **Tests:** `python -m pytest backend/tests/test_research_{data,engine,metrics,setups,indicators}.py -q`
  -> **47 passed** (36 pre-existing + 11 new). `ruff check` clean on the research package,
  the runner and the tests.
- **Determinism:** each setup was run repeatedly on the same cache. Every metric
  other than the alpha/beta fields, every trade count, exit-reason count and p-value
  was identical between runs (same seeds, same panel). The committed artifacts come
  from the final run, whose `run.code.revision` is the clean `821454e` commit.
  Alpha/beta changed only because that regression path was fixed between runs.
- **Span:** all four artifacts record `requested_span == actual_span ==
  2020-01-03 .. 2023-12-29`, and `panel.n_symbols_ending_early == 0`.
- **Invariant:** all four artifacts record `invariant.holds == true`; for example
  `statistical_mean_reversion`: 100,000 + 9,596.77 = 109,596.77.
- **Impact:** `gitnexus_impact` on `run_portfolio`, `download_daily`, `compute_metrics`
  and `save_results` -> LOW risk, no production process. The package is still not
  imported by the API, the gate, the journal, the scorecard or the forward loop.

## Clean re-run design

| Item | Value |
|---|---|
| Window | 2020-01-03 to 2023-12-29 (inclusive, fixed) |
| Universe | `config/replay_universe_sp500.txt` (current S&P 500 snapshot), SHA-256 `a53242f2...9a729080` |
| Symbols | 494 loaded (493 tradable + SPY); 11 dropped |
| Dropped | FDXF, GEV, HONA, KVUE, Q, RDDT, SNDK, SOLV, VYLR (no data in window), VLTO (61 bars), VIX (Yahoo no longer serves it) |
| Cache | `.cache/research_clean`, span-keyed; the 494 symbols were downloaded once, then served from cache (the committed artifacts record 494 hits, 0 downloads and 11 failures each) |
| Exits | 2.0 ATR stop, 3.0 ATR target, 15-bar time stop |
| Portfolio | $100,000 start, 0.5% risk, 8 positions, 20% notional cap, 15 bps/side |
| Controls | random 2%/day (100 runs), permuted signal dates (50), time-shifted +20..+60 bars (5) |
| Code | `821454e`, dirty=false |

Of the 11 dropped symbols, nine are recent listings or index additions that did not
trade in 2020 (FDXF, GEV, HONA, KVUE, Q, RDDT, SNDK, SOLV, VYLR), VLTO has only 61
bars in the window, and VIX is an index symbol Yahoo no longer serves. Excluding them
is correct, but the panel is still the *current* index membership, so **survivorship
bias remains** (companies removed from the index are absent).

## Results (valid for this panel and window)

Trade-level, strategy exits only (censored forced closes excluded from R statistics):

| Setup | Trades | Win rate | Mean net R | R sum | Profit factor | Avg hold | Censored |
|---|---|---|---|---|---|---|---|
| statistical_mean_reversion | 591 | 47.9% | **+0.037** | **+21.93** | 1.08 | 9.7 bars | 5 |
| breakout_52week | 601 | 47.6% | +0.005 | +3.22 | 1.01 | 8.7 bars | 8 |
| low_vol_setup | 613 | 42.4% | **-0.117** | **-71.62** | 0.80 | 8.8 bars | 8 |
| volume_trend_accumulation | 847 | 44.5% | -0.046 | -38.59 | 0.92 | 8.5 bars | 7 |

Equity, all trades including forced closes (invariant reconciled):

| Setup | Final equity | Total return | Max drawdown | CAGR | Vol (ann) | Realized P&L |
|---|---|---|---|---|---|---|
| statistical_mean_reversion | $109,596.77 | +9.6% | -22.0% | 2.3% | 12.6% | +$9,596.77 |
| breakout_52week | $98,391.83 | -1.6% | -19.2% | -0.4% | 11.2% | -$1,608.17 |
| low_vol_setup | $72,824.54 | -27.2% | -37.3% | -7.6% | 11.3% | -$27,175.46 |
| volume_trend_accumulation | $82,550.39 | -17.4% | -32.3% | -4.7% | 14.1% | -$17,449.61 |

For comparison, **SPY buy-and-hold over the same window returned +57.0%** (adjusted
closes, 293.16 -> 460.25). All four setups underperformed the benchmark.

Control p-values on `r_net_sum` (one-sided; small means the control was more extreme
in the direction of the real result):

| Setup | random | permuted | shifted |
|---|---|---|---|
| statistical_mean_reversion | 0.079 | **0.020** | 0.500 |
| breakout_52week | 0.228 | 0.745 | 0.833 |
| low_vol_setup | **0.050** | 0.059 | 0.167 |
| volume_trend_accumulation | 0.337 | 0.157 | 0.167 |

Control p-values on trade-R Sharpe:

| Setup | random | permuted | shifted |
|---|---|---|---|
| statistical_mean_reversion | **0.050** | **0.020** | 0.500 |
| breakout_52week | 0.228 | 0.745 | 0.833 |
| low_vol_setup | **0.020** | **0.020** | 0.167 |
| volume_trend_accumulation | 0.327 | 0.137 | 0.167 |

### Entries per calendar year

The D-79 defect signature (zero entries after 2020 for two setups) is gone:

| Setup | 2020 | 2021 | 2022 | 2023 | Post-2020 |
|---|---|---|---|---|---|
| statistical_mean_reversion | 111 | 143 | 167 | 175 | 485 |
| breakout_52week | 162 | 195 | 92 | 160 | 447 |
| low_vol_setup | 107 | 204 | 110 | 200 | **514** (was 0) |
| volume_trend_accumulation | 212 | 234 | 203 | 205 | **642** (was 0) |

All censored trades are `eod_censored` (positions still open on 2023-12-29). No
`data_end` exit fired because, with the span-keyed cache, every symbol covers the full
window; that path is covered by the ragged-panel unit test.

## Reading the result

- **`statistical_mean_reversion` is the only candidate.** It is the only setup with a
  positive R sum (+21.93) and it beats the permuted control on both metrics (p = 0.020)
  and the random control on Sharpe (p = 0.050) but not on R sum (p = 0.079). It is
  indistinguishable from the shifted control (p = 0.500; shifted mean R sum 17.67 vs
  21.93 real), which is the strongest control here because it keeps the signal shape
  and only moves it in time.
- **`breakout_52week` has no measured edge** (all p >= 0.23, R sum +3.22, -1.6% return).
  The "significantly worse" p-values in D-79 came from the contaminated panel and the
  stranded cash, not from the setup.
- **`low_vol_setup` underperforms consistently.** It is significantly *worse* than
  random on R sum (p = 0.050) and Sharpe (p = 0.020), and worse than permuted on Sharpe
  (p = 0.020). This is unfavorable significance, not an edge.
- **`volume_trend_accumulation` has no measured edge** (all p >= 0.14, R sum -38.59).
- **Multiple comparisons.** 4 setups x 3 controls = 12 tests. The smallest p-value is
  0.0196; a Bonferroni threshold would be 0.0042 and a Holm step-down leaves nothing
  significant. Read every individual p-value as suggestive.
- **The shifted control cannot reach p < 0.05.** With only 5 shifted runs and the
  `(k+1)/(n+1)` correction, the smallest attainable one-sided p is 1/6 = 0.167. "Real
  result not significant vs shifted" is therefore guaranteed for any setup; that control
  can only show a setup is worse than *every* shift, never that it is better. Its value
  here is descriptive: for `statistical_mean_reversion` the real R sum (21.93) sits well
  inside the shifted distribution (mean 17.67, sd 31.87), which is evidence against a
  timing-independent edge.
- **Benchmark.** Even the best setup (+9.6%) is far behind SPY buy-and-hold (+57.0%)
  with a quarter of the capital deployed. A positive control-adjusted result is not a
  reason to prefer the setup to the index.

**Defensible summary:** on one clean 2020-2023 panel of the current S&P 500 snapshot,
no setup beat all three of its controls at p < 0.05 in the favorable direction after
accounting for multiple comparisons. `statistical_mean_reversion` is the only setup with
a favorable signal that survives a single-control test, and it fails the
shape-preserving shifted control.

## What this does not settle

- **Not a verdict on the deployed templates.** These are research implementations with
  fixed ATR exits, not the D-70 replay or the live `config/screens/*.yaml` templates.
  A weak result here does not retire `low-vol-setup` from the screen mix, and a positive
  one does not promote `statistical_mean_reversion`.
- **One window, one universe snapshot.** No walk-forward, no out-of-sample holdout, no
  regime split. The window includes the 2020 crash and recovery, which dominates any
  long-only strategy's benchmark comparison.
- **Trade-R Sharpe.** `sharpe` annualizes per-trade R by `sqrt(252)`; it is not a daily
  equity Sharpe. Cross-setup Sharpe comparisons are only meaningful at similar trade
  counts (they are: 591-847).
- **VIX is missing** (Yahoo no longer serves the symbol), so no volatility-regime
  conditioning is possible from this cache.
- **Artifact schema quirk:** `metrics.win_rate` is a fraction (0.479), while
  `total_return_pct` and `max_drawdown_pct` are already percentages (-22.0). Read the
  field names carefully.
- **Survivorship** remains as described above.

## Consequences

- The D-79 baseline artifacts (`*_20261110_*.json`) are **superseded**. They stay in the
  repository as the audit trail for the defects and must not be cited.
- H-10 is replaced with the clean result and re-labelled exploratory in the recorded
  panel.
- The artifact README banner now states what is valid and why, with the re-run command.
- **No live behavior changed.** No production code path imports the research package; no
  `paper_trades` row, scorecard, gate decision or forward-sample verdict is affected.
  Nothing here enters the D-75 pass bar or the kill rule.

## Alternatives considered

- **Fix only the engine, keep the cache.** Rejected: with mixed spans, `data_end` closes
  would fire on most symbols and the panel would still not be comparable across setups.
- **Require a complete common calendar instead of per-symbol closes.** Rejected for now:
  it would drop every symbol with a single missing bar and shrink the panel. The
  per-symbol close plus the equity invariant gives correct accounting without losing
  names; a common-calendar mode is still the right choice if intraday or index-relative
  work needs it.
- **Raise the control budget to 500/200/20.** Deferred. 100/50/5 is enough to detect
  large effects and keeps a full four-setup re-run near 25 minutes; the p-value floor at
  these counts is 0.0099 for random and 0.0196 for permuted.
