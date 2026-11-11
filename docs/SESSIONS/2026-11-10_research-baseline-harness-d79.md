# 2026-11-10 - Research Backtesting Harness + Baseline (D-79)

**Branch:** `research/baseline-backtesting`
**Commits documented:** `c7f9a22` (harness), `7960cb7` (baseline artifacts)
**Decision:** [D-79](../DECISIONS/D-79-research-baseline-harness.md)
**Experiment:** H-10 in [`docs/backtests/HYPOTHESIS_LOG.md`](../backtests/HYPOTHESIS_LOG.md)
**Documented:** 2026-11-11

---

## Summary

Two commits added a standalone research backtesting harness and four baseline
artifacts:

1. `c7f9a22 feat(research): add standalone backtesting harness for screen
   validation` - 17 files, ~8.5k lines including four test files and the first
   quick-run artifacts.
2. `7960cb7 research: add baseline backtest results for all 4 setups on S&P 500
   (2020-2023)` - 5 JSON artifacts, ~90.5k lines.

The harness is **accepted**: 36 unit tests pass and it is not wired into
production. The four committed baseline artifacts are **not valid evidence** as
recorded. Verification during documentation found that the cache served mixed
history spans (440/498 symbols cover only 2020) and that positions stranded at a
symbol's data end corrupt the equity curve. The committed equity returns,
drawdowns, CAGR and alpha/beta must not be cited. The narrow provisional reading
is that no setup beat its controls at p < 0.05 in the favorable direction.

---

## Commits

| Commit | Subject | Scope |
|---|---|---|
| `c7f9a22` | feat(research): add standalone backtesting harness for screen validation | `backend/app/research/*` (6 modules), `backend/tests/test_research_*.py` (4 files, 36 tests), `scripts/run_research_baseline.py`, `config/replay_universe_test.txt`, 4 quick-run JSONs |
| `7960cb7` | research: add baseline backtest results for all 4 setups on S&P 500 (2020-2023) | 5 JSON artifacts in `docs/backtests/research/` |

Neither commit changed the API, the gate, the journal schema, the scorecard, the
forward loop or any live trading rule.

---

## What was built

| Module | Responsibility |
|---|---|
| `backend/app/research/data.py` | Universe loading (`config/replay_universe_*.txt`), cached yfinance daily bars (`.cache/research/*.csv.gz`), cleaning |
| `backend/app/research/indicators.py` | EMA20/50/200, SMA20, RSI14, ATR14/`atr_pct`, ADX14, MACD, CCI20, Bollinger(20,2), `rvol10`, `adv_usd20` |
| `backend/app/research/setups.py` | Liquidity gate + four setup signal functions (`statistical_mean_reversion`, `breakout_52week`, `low_vol_setup`, `volume_trend_accumulation`) |
| `backend/app/research/engine.py` | Next-open portfolio engine: 2.0 ATR stop, 3.0 ATR target, 15-bar hold, 0.5% risk, 8 positions, 20% notional cap, 15 bps/side, same-session stop/target, EOD censoring |
| `backend/app/research/metrics.py` | Trade and equity metrics, alpha/beta vs SPY |
| `backend/app/research/control.py` | Random (2%/day), permuted (signal-date shuffle) and time-shifted (+20..+60 bars) controls; one-sided p on `r_net_sum` |
| `scripts/run_research_baseline.py` | CLI runner, artifact writer, control orchestration, exit code by significance |

CLI defaults: S&P 500 universe, `2015-01-01` to `2024-12-31`, stop 2.0 ATR,
target 3.0 ATR, 15-bar hold, 0.5% risk, 8 positions, 15 bps/side, 100/50/5
control runs, output `docs/backtests/research/`.

---

## Recorded results (artifact values)

Trade-level metrics (internally consistent, but on a mixed panel):

| Setup | Trades | Win rate | Mean net R | Profit factor | Avg hold | Censored |
|---|---|---|---|---|---|---|
| statistical_mean_reversion | 700 | 49.0% | **+0.038** | 1.076 | 8.8 bars | 3 |
| breakout_52week | 583 | 43.9% | -0.047 | 0.915 | 8.0 bars | 0 |
| low_vol_setup | 589 | 46.3% | -0.034 | 0.937 | 9.1 bars | 0 |
| volume_trend_accumulation | 748 | 48.3% | +0.012 | 1.024 | 8.9 bars | 0 |

Control p-values on `r_net_sum`:

| Setup | random | permuted | shifted |
|---|---|---|---|
| statistical_mean_reversion | 0.524 | 0.286 | 0.476 |
| breakout_52week | 0.143 | **0.048** | **0.048** |
| low_vol_setup | **0.048** | 0.190 | 0.095 |
| volume_trend_accumulation | 0.762 | 0.905 | 0.667 |

The two significant results are **unfavorable** (the controls were better). The
commit message's `p=0.048` for breakout comes from the permuted/shifted controls
(random is 0.143); low-vol's 0.048 is the random control.

Equity-curve figures as recorded (invalid - see audit):

| Setup | Total return | Max drawdown | Final equity |
|---|---|---|---|
| statistical_mean_reversion | -47.4% | -58.8% | $52,552 |
| breakout_52week | -62.3% | -67.8% | $37,707 |
| low_vol_setup | -97.7% | -97.8% | $2,285 |
| volume_trend_accumulation | -77.8% | -80.5% | $22,246 |

---

## Verification

- `python -m pytest backend/tests/test_research_engine.py
  backend/tests/test_research_indicators.py backend/tests/test_research_metrics.py
  backend/tests/test_research_setups.py -q` -> **36 passed** (re-run 2026-11-11).
- The tests cover indicators, setups, engine mechanics (next-open, stop-first,
  time stop, sizing caps) and metrics. They do not cover cache range validity or
  the equity-vs-realized-P&L invariant.
- No production test suite was affected; the package is not imported by the app.

---

## Documentation audit of the committed artifacts

Performed 2026-11-11 while writing D-79. Evidence is in the local cache and the
committed JSONs.

### Finding 1 - cache served mixed spans

`download_daily()` reuses a cache file if it is < 20 hours old and has >= 100
rows, without checking that it covers the requested start/end. Observed cache:

- 440/498 files: **2020-01-02 to 2020-12-30** (252 bars)
- 40/498 files: **2014-01-02 to 2024-12-30** (2,767 bars)
- 18/498 files: shorter IPO histories ending 2024-12-30

The artifacts' equity calendar is therefore **2014-01-02 to 2024-12-30**, not
2020-2023. Entry distribution confirms the blend:

| Setup | before 2020 | 2020 | after 2020 |
|---|---|---|---|
| statistical_mean_reversion | 414 | 112 | 177 |
| breakout_52week | 230 | 176 | 177 |
| low_vol_setup | 485 | 104 | 0 |
| volume_trend_accumulation | 554 | 194 | 0 |

### Finding 2 - stranded positions corrupt equity

Positions in a symbol whose data ends are never exited (the main loop skips
missing bars; the final force-close only covers the global last date). Their cash
is never returned, so the equity curve takes a permanent artificial loss.

| Setup | Realized `pnl_usd` sum | Final equity | Equity return |
|---|---|---|---|
| statistical_mean_reversion | **+$10,977** | $52,552 | **-47.4%** |
| breakout_52week | -$12,903 | $37,707 | -62.3% |
| low_vol_setup | -$9,301 | $2,285 | **-97.7%** |
| volume_trend_accumulation | +$4,860 | $22,246 | -77.8% |

The low-vol final equity is consistent with ~8 positions stranded at
2020-12-30. The decisive confirmation: the same cache contains **395 post-2020
low-vol signals** and **859 post-2020 volume-trend signals** across the
long-history symbols, yet both artifacts record **zero** post-2020 trades. The
stranded positions consumed the cash, so no new position could be sized
(`shares < 1`) for the remaining four years. The +$11k realized / -47% equity
combination for statistical mean reversion cannot arise from the recorded costs
and sizing.

### Finding 3 - artifacts are not self-describing

No requested/actual span, universe hash, cache statistics, costs, seeds or code
revision in the JSON. The printed Sharpe p-values are not saved. The window
claim in the commit message cannot be checked from the artifact alone.

### Minor notes

- `total_return_pct` uses the first equity point as the start, not the
  configured `start_equity`.
- `sharpe` is a per-trade R Sharpe annualized by `sqrt(252)`, not a daily equity
  Sharpe.
- Exit code 0 on `min_p < 0.05` is direction-blind; unfavorable significance also
  exits 0.

---

## Files changed by these commits

```
backend/app/research/__init__.py
backend/app/research/data.py
backend/app/research/indicators.py
backend/app/research/setups.py
backend/app/research/engine.py
backend/app/research/metrics.py
backend/app/research/control.py
backend/tests/test_research_engine.py
backend/tests/test_research_indicators.py
backend/tests/test_research_metrics.py
backend/tests/test_research_setups.py
scripts/run_research_baseline.py
config/replay_universe_test.txt
docs/backtests/research/statistical_mean_reversion_20261110_123729.json
docs/backtests/research/statistical_mean_reversion_20261110_123745.json
docs/backtests/research/statistical_mean_reversion_20261110_123929.json
docs/backtests/research/statistical_mean_reversion_20261110_162716.json
docs/backtests/research/statistical_mean_reversion_20261110_162853.json
docs/backtests/research/statistical_mean_reversion_20261110_201238.json
docs/backtests/research/breakout_52week_20261110_204613.json
docs/backtests/research/low_vol_setup_20261110_211920.json
docs/backtests/research/volume_trend_accumulation_20261110_215337.json
```

## Documentation updates made for this record

- Created `docs/DECISIONS/D-79-research-baseline-harness.md` (this decision).
- Created this session log.
- Created `docs/backtests/research/README.md` with the artifact validity banner.
- Added H-10 to `docs/backtests/HYPOTHESIS_LOG.md`; backfilled the missing H-09
  row for D-78.
- Updated `docs/DECISIONS/index.md`, `docs/index.md` and root `INDEX.md`.
- `ARCHITECTURE.md` and `API.md` intentionally unchanged: the research package
  is not wired into the app or any route.

---

## Next steps

1. Fix the cache contract: cache key or coverage validation by requested span;
   regression test narrow -> wide window.
2. Fix the engine's data-end handling: close positions at the symbol's last bar
   (or require a complete common calendar); add the `final_equity == start +
   sum(pnl)` invariant test.
3. Persist full run metadata (requested/actual span, universe hash, costs,
   seeds, cache stats, code SHA) and refuse to write when the span mismatches.
4. Re-run all four setups on a clean cache and one fixed window (for example
   2020-01-03 to 2023-12-29), then replace the H-10 result.
5. Do not cite the committed returns, drawdowns, CAGR or alpha/beta anywhere.

---

## Status

| Item | Status |
|---|---|
| Harness code | Accepted |
| Harness tests | 36 passed |
| Production impact | None |
| Committed baseline artifacts | **Not valid evidence - re-run required** |
| Live trading rules | Unchanged |
| D-79 decision record | Written |
| H-10 experiment log | Written (invalid as recorded) |
