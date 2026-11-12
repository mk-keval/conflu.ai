# D-79: Research Backtesting Harness - Accepted Code, Committed Baseline Not Valid Evidence

> **Superseded by [D-80](D-80-research-baseline-remediation.md) (2026-11-11), whose
> results were in turn superseded by
> [D-81](D-81-research-baseline-v2-honesty-and-controls.md) (2026-11-12).**
> The harness decision and the defect audit below stand. The four committed baseline
> results are invalid and must not be cited. The citable baseline is the 2015-2026
> D-81 re-run; the D-79 figures are retained only as the audit trail for the defects.

**Date:** 2026-11-10 (documented 2026-11-11)
**Status:** Harness **accepted** (code + tests). Committed baseline artifacts are
**not valid evidence** as recorded: cache-range contamination and stranded-position
equity accounting. Re-run required before any result is cited.
**Branch:** `research/baseline-backtesting`
**Commits:** `c7f9a22` (harness), `7960cb7` (baseline artifacts)
**Related:** D-70 (honest engine), D-71 (screen replay), D-74 (measurement
integrity), D-75 (pass bar), D-76 (sample versioning), H-10 in
[`docs/backtests/HYPOTHESIS_LOG.md`](../backtests/HYPOTHESIS_LOG.md).

## Context

The project needed a way to test whether a screen/setup has an edge **before**
deploying it, without coupling the test to the live journal, the production gate,
or the existing `external_backtest`/replay paths. The question is deliberately
narrow: given daily bars, a setup definition, fixed exits and a portfolio, does
the setup's signal stream beat random, permuted and time-shifted controls?

The harness is standalone research code. It writes JSON artifacts to
`docs/backtests/research/`. It does not write `paper_trades`, does not touch the
forward scorecard, and cannot change a live decision.

## Decision

### Standalone package, no production coupling

- `backend/app/research/data.py` - universe loading, cached yfinance downloads,
  cleaning. Symbols are uppercased and `.` is replaced with `-`.
- `backend/app/research/indicators.py` - EMA20/50/200, SMA20, Wilder RSI14,
  ATR14 and `atr_pct`, Wilder ADX14, MACD(12,26,9), CCI20, Bollinger(20,2),
  `vol_sma10`, `rvol10`, `adv_usd20`. Indicators use only past/current bars.
- `backend/app/research/setups.py` - a shared liquidity gate
  (`close >= 10` and `adv_usd20 >= 20_000_000`) plus four setup functions:
  - `statistical_mean_reversion`: `rsi14 < 32`, `cci20 < -100`,
    `atr_pct < 0.04`, `rvol10 > 1.2`
  - `breakout_52week`: `close > ema200`, `ema20 > ema50`, `ema50 > ema200`,
    `macd > macd_signal`, `adx14 > 30`, `rvol10 > 1.5`
  - `low_vol_setup`: `close > ema50`, `bb_upper / bb_lower < 1.05`,
    `45 < rsi14 < 60`, `atr_pct < 0.03`, `rvol10 < 0.8`
  - `volume_trend_accumulation`: `close > sma20`, `close > ema50`,
    `rvol10 > 1.3`, `55 < rsi14 < 70`, `adx14 > 25`
- `backend/app/research/engine.py` - portfolio simulator:
  - signal at a bar's close, entry at the **next** bar's open;
  - stop `2.0 x ATR`, target `3.0 x ATR`, 15-bar max hold;
  - stop checked before target; gap-through fills at the open;
  - same-session stop/target allowed for new positions, time stop is not;
  - 0.5% equity risk per trade, max 8 positions, max 20% notional per position,
    15 bps cost per side;
  - candidates shuffled per date with a seed when more signals exist than slots;
  - open positions force-closed at the final date as `eod_censored`.
- `backend/app/research/metrics.py` - trade counts, win rate, R mean/median/std/
  sum, profit factor, Sharpe and Sortino, max drawdown, CAGR, annualized
  volatility, and alpha/beta versus SPY.
- `backend/app/research/control.py` - three controls:
  - `random`: 2% signal probability per symbol/day (100 runs by default);
  - `permuted`: real signal dates permuted within the symbol (50 runs);
  - `shifted`: real signals shifted +20/+30/+40/+50/+60 bars (5 runs).
  p-values are one-sided on `r_net_sum` with a `(n+1)` finite-sample correction.
- `scripts/run_research_baseline.py` - CLI runner. Defaults: S&P 500 universe,
  2015-01-01 to 2024-12-31, 2.0/3.0 ATR, 15-bar hold, 0.5% risk, 8 positions,
  15 bps/side. Writes `{setup}_{YYYYmmdd_HHMMSS}.json` and exits 0 if the minimum
  control p-value is < 0.05, otherwise 1.

### Evidence status by construction

- The harness answers only "does the signal stream beat these controls on this
  panel?" It is exploratory. A positive result can motivate a pre-registered
  forward test; it cannot enter the D-75 pass bar, the kill rule, `/expectancy`,
  or any FWD-v0.2 verdict.
- The exit code is a significance convention, not a quality verdict. Because
  the p-value direction flips with the sign of the real metric, a small p can
  mean the setup is significantly **worse** than the control.

### Baseline run committed in `7960cb7`

Four setups were run on the S&P 500 snapshot (`config/replay_universe_sp500.txt`,
498 symbols loaded including SPY/VIX) and the JSON artifacts were committed:

| Setup | Trades | Win rate | Mean net R | Profit factor | Censored |
|---|---|---|---|---|---|
| statistical_mean_reversion | 700 | 49.0% | **+0.038** | 1.076 | 3 |
| breakout_52week | 583 | 43.9% | -0.047 | 0.915 | 0 |
| low_vol_setup | 589 | 46.3% | -0.034 | 0.937 | 0 |
| volume_trend_accumulation | 748 | 48.3% | +0.012 | 1.024 | 0 |

Control p-values on `r_net_sum` (one-sided; smaller means "the controls were
more extreme in the direction of the real result"):

| Setup | random | permuted | shifted | Reading |
|---|---|---|---|---|
| statistical_mean_reversion | 0.524 | 0.286 | 0.476 | not distinguishable |
| breakout_52week | 0.143 | **0.048** | **0.048** | significantly **worse** than permuted/shifted |
| low_vol_setup | **0.048** | 0.190 | 0.095 | significantly **worse** than random |
| volume_trend_accumulation | 0.762 | 0.905 | 0.667 | not distinguishable |

The commit message quotes `p=0.048` for `breakout_52week` and `low_vol_setup`.
Those are different controls: breakout's 0.048 is permuted/shifted (its random
p is 0.143); low-vol's 0.048 is random. In both cases significance is in the
**unfavorable** direction.

The commit message also reports equity-curve returns (-47.4%, -62.3%, -97.7%,
-77.8%) and says "all setups lose money vs buy-and-hold". **Those figures are
not valid** - see the audit below.

## Audit of the committed artifacts (2026-11-11)

The artifacts were verified against the cache and the trade records while
writing this record. Three defects invalidate the return/drawdown/alpha figures
and make the panel non-comparable across setups.

### 1. Cache range contamination

`download_daily()` reuses a cache file if it is less than 20 hours old and has at
least 100 rows. It does **not** check that the cached span covers the requested
`start`/`end`. Observed cache state:

| Cached span | Files |
|---|---|
| 2020-01-02 to 2020-12-30 (252 bars) | 440 |
| 2014-01-02 to 2024-12-30 (2,767 bars) | 40 |
| other partial histories (2 end 2020-12-30, 16 end 2024-12-30) | 18 |

All four baseline artifacts therefore have an equity calendar of
**2014-01-02 to 2024-12-30**, not the "2020-2023" claimed in the commit
message. The trade mix confirms the panel is a blend:

| Setup | Entries before 2020 | Entries in 2020 | Entries after 2020 |
|---|---|---|---|
| statistical_mean_reversion | 414 | 112 | 177 |
| breakout_52week | 230 | 176 | 177 |
| low_vol_setup | 485 | 104 | **0** |
| volume_trend_accumulation | 554 | 194 | **0** |

For `low_vol_setup` and `volume_trend_accumulation`, every post-2020 date is a
date on which the few long-history symbols produced no signals; the reported
"multi-year" result is effectively 2014-2020 on ~40 names plus 2020 on ~440
names. The four setups are not run on the same panel and are not comparable.

### 2. Stranded positions corrupt the equity curve

When a symbol's data ends (mostly 2020-12-30), any still-open position in that
symbol is never exited: the main loop skips symbols with no bar on a date, and
the final force-close only runs for positions whose symbol has a bar on the
**global** last date. The position's cash is never returned, and the daily
equity mark stops including it, producing a permanent artificial loss.

Evidence - realized trade P&L versus the equity curve:

| Setup | Sum of realized `pnl_usd` | Final equity | Equity-curve return |
|---|---|---|---|
| statistical_mean_reversion | **+$10,977** | $52,552 | **-47.4%** |
| breakout_52week | -$12,903 | $37,707 | -62.3% |
| low_vol_setup | -$9,301 | $2,285 | **-97.7%** |
| volume_trend_accumulation | +$4,860 | $22,246 | -77.8% |

A +$11k realized result cannot end at -47% from 0.5%-risk trades under the
recorded rules. The gap is stranded positions. The decisive confirmation: the
same cache contains **395 post-2020 `low_vol_setup` signals** and **859
post-2020 `volume_trend_accumulation` signals** across the long-history symbols,
yet both artifacts record **zero** post-2020 trades. Open positions at
2020-12-30 consumed the cash, so `shares < 1` and the runner could not size
another position for the remaining four years. The book goes dormant, and the
equity curve continues at the depleted level.

Consequences: `total_return_pct`, `max_drawdown_pct`, `max_drawdown_usd`, `cagr`,
`volatility_annual`, `alpha` and `beta` are **not usable** in these artifacts.
Trade-level R, win rate, profit factor and exit reasons remain internally
consistent, but they are computed on the mixed panel above.

### 3. Artifacts do not describe themselves

The JSON has `setup`, `timestamp`, `metrics`, `trades`, `equity_curve`,
`control_summary` and `p_values`. It does not record the requested start/end,
the actual data span, the universe path/hash, cache hit/miss counts, costs,
seeds, or the code revision. A reader cannot tell from the artifact that the
panel is mixed. The Sharpe p-values printed by the runner are also not saved.

### Minor notes

- `metrics.total_return_pct` uses `equity_curve.iloc[0]` as the start rather
  than the configured `start_equity` (normally equal, but implicit).
- `sharpe` annualizes per-trade R with `sqrt(252)`; it is a trade-R Sharpe, not
  a daily equity Sharpe. Label it as such.
- The runner's `min_p < 0.05 -> exit 0` convention celebrates unfavorable
  significance. Do not use the exit code as a quality gate.

## Consequences

- **The harness code and its 36 unit tests are accepted.** `pytest` on
  `test_research_{engine,indicators,metrics,setups}.py` -> **36 passed**
  (re-verified 2026-11-11). The unit tests use synthetic frames and do not catch
  the cache/panel defect.
- **The committed baseline artifacts are invalid for inference.** Do not cite
  the equity returns, drawdowns, CAGR, alpha/beta or the "all setups lose money
  vs buy-and-hold" claim. The defensible provisional reading is narrow: on the
  recorded panel, no setup beat its controls at p < 0.05 in the favorable
  direction; two setups had positive trade-level expectancy (+0.038R, +0.012R)
  and two had negative expectancy, but the panel is mixed.
- **No live behavior changed.** The research package is not imported by the API,
  the gate, the journal, the scorecard or the forward loop. No `paper_trades`
  row exists because of this work.

## Required remediation before the next baseline

1. **Cache correctness:** key the cache by symbol + requested span (or validate
   the cached min/max date against the request and re-download on mismatch).
   Add a regression test for cold cache -> narrow window -> wide window.
2. **Equity integrity:** force-close any position whose symbol has no later bar
   at that symbol's last available close (flagged as `data_end`), or require a
   common calendar with complete coverage. Add an invariant test:
   `final_equity == start_equity + sum(pnl_usd)` within tolerance, for both
   fully-closed and EOD-censored runs.
3. **Self-describing artifacts:** persist requested and actual span, universe
   file + hash, symbols loaded/dropped, cache hits/misses, costs, seeds, code
   revision, and per-control p-values for at least `r_net_sum` and `sharpe`.
   Refuse to write (or loudly mark) when actual span != requested span.
4. **Re-run the four setups on a clean cache and a fixed window**
   (for example 2020-01-03 to 2023-12-29) on one consistent panel, then log the
   outcome in H-10. Treat the current artifacts as a harness smoke test only.
5. **Survivorship:** the universe is the current S&P 500 snapshot. Record the
   limitation explicitly in every artifact; do not describe results as
   "S&P 500 2020-2023" without it.

## Alternative considered

- Reuse the D-71 replay engine instead of a standalone package. Rejected because
  the replay engine is coupled to the deployed screen templates, the frozen
  windows and the journal schema. The research harness needs fast, synthetic
  setup iteration and control runs without touching production state.
