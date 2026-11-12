# 2026-11-11 - D-79 Remediation + Clean Baseline Re-Run (D-80)

> **Results superseded 2026-11-12 by [D-81](../DECISIONS/D-81-research-baseline-v2-honesty-and-controls.md).**
> The span-keyed cache, `data_end` closes and equity-invariant fixes recorded here stand
> and are still enforced. The 2020-2023 return/drawdown/p-value figures are historical;
> the citable baseline is the 2015-2026 re-run in
> [the D-81 session log](2026-11-12_research-baseline-v2-d81.md).

**Branch:** `research/baseline-backtesting`
**Commit documented:** `821454e` - `fix(research): enforce span-keyed cache and close stranded positions (D-79)`
**Decision:** [D-80](../DECISIONS/D-80-research-baseline-remediation.md)
**Supersedes:** [D-79](../DECISIONS/D-79-research-baseline-harness.md) results (harness decision stands)
**Experiment:** H-10 in [`docs/backtests/HYPOTHESIS_LOG.md`](../backtests/HYPOTHESIS_LOG.md)
**Documented:** 2026-11-11

---

## Summary

D-79 accepted the research harness but declared its four committed baseline artifacts
invalid: the cache served mixed history spans and positions stranded at a symbol's data
end corrupted the equity curve. This session implemented the five D-79 remediation items,
added regression tests for both defects, and re-ran all four setups on one clean panel.

Outcome: cache and equity defects are closed (47 tests pass, equity invariant enforced,
span enforcement at write time), and the clean result **changes the reading** of the
baseline. `breakout_52week`'s "significantly worse" p-values were an artifact of the
defect and disappear. `statistical_mean_reversion` is the only setup with a favorable
control-adjusted signal (+9.6% return, +21.93 R, p = 0.020 vs permuted), but it does not
beat the random control on R sum (p = 0.079), fails the shape-preserving shifted control,
and loses badly to SPY buy-and-hold (+57.0%). Nothing survives multiple-comparison
correction. `low_vol_setup` is significantly *worse* than its controls.

No production code path is involved. No live trading rule, sample, scorecard or gate
decision changed.

---

## The two defects and their fixes

### 1. Cache served a different window than requested

`download_daily()` reused any cache file younger than 20 hours with at least 100 rows.
Observed state: 440/498 files covered only 2020, 40 covered 2014-2024, 18 were partial.
The artifacts' equity calendar was 2014-01-02 to 2024-12-30 while the commit message
claimed 2020-2023.

Fix: the cache key is now `SYMBOL__{start}__{end}` with a `_manifest.json` entry per key
(requested span, fetch time, rows, actual first/last bar). A hit requires the same
requested span and an age below `max_age_hours`; cached rows are clipped to the request.
Corrupt entries warn and re-download instead of dropping the symbol.

Tests: `backend/tests/test_research_data.py` (8 tests) covers cold -> narrow -> wide
window, same-span reuse, forced download, expiry, inclusive `end`, manifest contents,
`panel_span` benchmark exclusion and universe normalisation.

### 2. Stranded positions corrupted the equity curve

When a symbol's data ended, its open position was never exited: cash was never returned
and the daily mark dropped it, producing a permanent artificial loss. For
`low_vol_setup` and `volume_trend_accumulation` the stranded positions consumed the
account, so no post-2020 position could be sized; both books recorded zero entries after
2020 despite 395 and 859 post-2020 signals in the same cache.

Fix: a position whose symbol has no later bar is closed at that symbol's last close with
`exit_reason="data_end"`, `censored=True`, `exit_date` = that bar. The final-bar sweep
still closes the rest as `eod_censored`, so every opened position is closed. The runner
refuses to write unless `final_equity == start_equity + sum(pnl_usd)`.

Tests: three added to `backend/tests/test_research_engine.py` - ragged-panel `data_end`
close, final-bar sweep, and the equity/P&L invariant with ten symbols of different
lengths.

---

## Supporting changes

- `compute_metrics(...)` regresses the benchmark return series as given; the old code
  differenced it again, produced `inf` on flat closes and left `alpha`/`beta` at zero.
  Beta now uses a sample variance to match `np.cov`.
- `compute_metrics(..., start_equity=...)`; new `pnl_usd_all` (all trades, including
  forced closes) alongside `pnl_usd_sum` (strategy exits only).
- Self-describing artifacts: requested/actual span, per-symbol coverage, universe path +
  SHA-256, symbols loaded/dropped with reasons, cache counters, costs, exits, seeds, code
  revision + dirty flag, library versions, declared limitations, and both p-value sets.
- `_validate_panel` refuses to write when the panel is more than 10 days short of the
  request (`--allow-partial-panel` overrides and records the warning).
- Exit code `0` now requires significance **and** a favorable direction.
- `_candidates_by_date` precomputes the signal-to-date index once; the previous
  per-date/per-symbol history rebuild made 155 control runs per setup impractical.

---

## Verification

| Check | Result |
|---|---|
| Research tests | **47 passed** (36 existing + 11 new) |
| `ruff check` (research pkg, runner, tests) | clean |
| Equity invariant | holds in all four artifacts |
| Span check | requested == actual == 2020-01-03 .. 2023-12-29 |
| Symbols ending early | 0 in all four artifacts |
| Determinism | repeated full runs on the same cache produced identical metrics, trade counts, exit reasons and p-values (only alpha/beta changed, and only because that path was fixed between runs) |
| GitNexus impact | LOW risk; all 9 affected processes are research entry points, none production |
| `gitnexus_detect_changes` | flags "high" breadth (whole-file rewrites); no API route, gate, journal or forward process reachable |

---

## Clean re-run

| Item | Value |
|---|---|
| Window | 2020-01-03 to 2023-12-29 |
| Universe | current S&P 500 snapshot, SHA-256 `a53242f2...9a729080` |
| Symbols | 494 loaded (493 tradable + SPY), 11 dropped (9 not listed in window, VLTO 61 bars, VIX unavailable) |
| Cache | span-keyed `.cache/research_clean`; 494 symbols downloaded once, then 494 hits per setup (11 always fail) |
| Controls | 100 random / 50 permuted / 5 shifted |
| Code | `821454e`, dirty=false |

---

## Results

| Setup | Trades | Win rate | Mean net R | R sum | PF | Return | Max DD | Realized P&L | Final equity |
|---|---|---|---|---|---|---|---|---|---|
| statistical_mean_reversion | 591 | 47.9% | +0.037 | **+21.93** | 1.08 | **+9.6%** | -22.0% | +$9,596.77 | $109,596.77 |
| breakout_52week | 601 | 47.6% | +0.005 | +3.22 | 1.01 | -1.6% | -19.2% | -$1,608.17 | $98,391.83 |
| low_vol_setup | 613 | 42.4% | -0.117 | **-71.62** | 0.80 | -27.2% | -37.3% | -$27,175.46 | $72,824.54 |
| volume_trend_accumulation | 847 | 44.5% | -0.046 | -38.59 | 0.92 | -17.4% | -32.3% | -$17,449.61 | $82,550.39 |

SPY buy-and-hold over the same window: **+57.0%**.

Control p-values on `r_net_sum` / on trade-R Sharpe:

| Setup | random | permuted | shifted |
|---|---|---|---|
| statistical_mean_reversion | 0.079 / **0.050** | **0.020** / **0.020** | 0.500 / 0.500 |
| breakout_52week | 0.228 / 0.228 | 0.745 / 0.745 | 0.833 / 0.833 |
| low_vol_setup | **0.050** / **0.020** | 0.059 / **0.020** | 0.167 / 0.167 |
| volume_trend_accumulation | 0.337 / 0.327 | 0.157 / 0.137 | 0.167 / 0.167 |

Entries per year confirm the dormancy bug is gone: `low_vol_setup` 107/204/110/200 and
`volume_trend_accumulation` 212/234/203/205 (previously zero after 2020). All censored
trades are `eod_censored`; no `data_end` fired because every symbol now covers the whole
window (that path is unit-tested).

---

## Reading

- `statistical_mean_reversion` is the only setup with a favorable single-control result
  and the only one with a positive R sum. It is not established: p = 0.079 vs random on
  R sum, and the shifted control (which preserves signal shape) is centered on 17.67 R
  vs the real 21.93.
- `breakout_52week` and `volume_trend_accumulation` show no measurable edge. D-79's
  "significantly worse" reading for breakout was the defect talking.
- `low_vol_setup` is significantly worse than random and permuted on Sharpe (p = 0.020)
  and worse than random on R sum (p = 0.050). Consistent underperformance, not an edge.
- 12 tests, smallest p = 0.0196. Bonferroni threshold 0.0042; nothing survives. The
  shifted control is capped at p = 0.167 with 5 runs and cannot establish superiority at
  all.
- Even the best setup (+9.6%) trails SPY (+57.0%) by a wide margin.

---

## Files

```
backend/app/research/data.py
backend/app/research/engine.py
backend/app/research/metrics.py
backend/tests/test_research_data.py        (new)
backend/tests/test_research_engine.py
scripts/run_research_baseline.py
docs/backtests/research/{setup}_20261111_*_clean.json   (new artifacts)
```

## Documentation updates

- Created `docs/DECISIONS/D-80-research-baseline-remediation.md`.
- Created this session log.
- Rewrote the `docs/backtests/research/README.md` banner: valid-for-this-panel, provenance,
  schema, re-run command, superseded files, known quirks.
- Replaced H-10 in `docs/backtests/HYPOTHESIS_LOG.md` with the clean result; added a D-79
  banner pointing to D-80.
- Updated `docs/DECISIONS/index.md`, `docs/index.md` and root `INDEX.md`.
- `ARCHITECTURE.md` and `API.md` intentionally unchanged: no production wiring.

---

## Next steps

1. Decide whether `statistical_mean_reversion` earns a **pre-registered** forward test
   (H-11) with a fixed window, fixed controls and a hit/miss bar written before the run.
   Not a deployment decision.
2. If the screen mix needs a verdict on the deployed templates, use the D-70 replay
   engine on the same window rather than this harness's fixed ATR exits.
3. Optional: raise shifted runs to >= 20 so that control can reach p < 0.05, and add a
   walk-forward split (2015-2019 fit, 2020-2023 test) before any further claims.
4. Keep the D-79 artifacts committed but uncited.

---

## Status

| Item | Status |
|---|---|
| Cache span defect | Fixed + tested |
| Data-end / equity defect | Fixed + tested |
| Self-describing artifacts | Implemented |
| Research tests | 47 passed |
| Clean baseline re-run | Done, deterministic, spans verified |
| D-79 artifacts | Superseded, retained as audit trail |
| H-10 | Replaced with clean result (exploratory) |
| Production impact | None |
| Live trading rules | Unchanged |
