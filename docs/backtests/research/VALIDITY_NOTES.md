# Validity Notes — Research Harness vs Deployed Screens

**Date:** 2026-11-12 (D-82, task T5)
**Status:** descriptive only. This file changes no code, no YAML and no artifact.

Sources read for this note: `backend/app/research/setups.py`, `backend/app/research/indicators.py`,
`backend/app/research/control.py`, `config/screens/52week-breakout.yaml`,
`config/screens/low-vol-setup.yaml`, `config/screens/statistical-mean-reversion.yaml`,
`config/screens/volume-trend-accumulation.yaml`, `config/regime_screens.yaml`,
`backend/app/infrastructure/backtest/external_backtest.py`,
`docs/DECISIONS/D-61-elite-template-deployment.md`, `docs/backtests/VALIDATION_REPORT.md`.

Research conditions are evaluated on daily bars built by
`backend/app/research/indicators.py`. Deployed conditions are the YAML rule sets evaluated by
`backend/app/infrastructure/backtest/external_backtest.py` (the D-61 engine) or by
`backend/app/infrastructure/screener/tv_specialist.py` (live screener). The two are separate
code paths and do not share an indicator implementation.

## 1. Research conditions vs deployed YAML conditions

### 1.1 `statistical_mean_reversion` vs `config/screens/statistical-mean-reversion.yaml`

| Condition | Research (`setups.statistical_mean_reversion`) | Deployed YAML | Status |
|---|---|---|---|
| Liquidity | `close >= 10` **and** `adv_usd20 >= 20,000,000` | none of this form; has `close_above 5.0` | different |
| RSI | `rsi14 < 32` | `rsi_oversold` threshold `32` | same threshold, different implementation |
| CCI | `cci20 < -100` | `cci_oversold` threshold `-100` | same threshold |
| ATR % | `atr_pct < 0.04` | `atr_pct_below` threshold `0.04` | same threshold |
| Relative volume | `rvol10 > 1.2` | `rvol_high` threshold `1.2` (`relative_volume_10d_calc`) | same threshold |
| Market cap | absent | `market_cap_gt 500,000,000` | deployed only |
| Exchange | absent | `exchange_in [NYSE, NASDAQ]` | deployed only |
| Country | absent | `country_in [United States]` | deployed only |
| Average volume | absent | `avg_volume_gt 500,000` | deployed only |
| Single-day volume | absent | `volume_gt 500,000` | deployed only |
| Asset classes | equities only (universe file) | `equities`, `crypto` declared | different |

### 1.2 `breakout_52week` vs `config/screens/52week-breakout.yaml`

| Condition | Research (`setups.breakout_52week`) | Deployed YAML | Status |
|---|---|---|---|
| 52-week high / proximity | **absent** | **absent** | both missing |
| Price vs EMA200 | `close > ema200` | `price_above_ema period 200` (`1D`) | same |
| EMA stack | `ema20 > ema50` and `ema50 > ema200` | `ema_stack_bullish` = `EMA20 > EMA50 > EMA200` (`1D`) | same |
| MACD | `macd > macd_signal` | `macd_bullish` | same |
| ADX | `adx14 > 30` | `adx_trending` threshold `30` (`1D`) | same |
| Relative volume | `rvol10 > 1.5` (10-day, daily bars) | `rvol_high` threshold `1.5` on **`4h`** timeframe | different timeframe |
| Price vs VWAP | absent | `price_above_vwap` (`1D`) | deployed only |
| Liquidity | `close >= 10` and `adv_usd20 >= 20,000,000` | `close_above 5.0`, `avg_volume_gt 1,000,000`, `volume_gt 500,000` | different |
| Market cap | absent | `market_cap_gt 500,000,000` | deployed only |
| Exchange | absent | `exchange_in [NYSE, NASDAQ]` | deployed only |
| Country | absent | `country_in [United States]` | deployed only |

### 1.3 `low_vol_setup` vs `config/screens/low-vol-setup.yaml`

| Condition | Research (`setups.low_vol_setup`) | Deployed YAML | Status |
|---|---|---|---|
| Price vs EMA50 | `close > ema50` | `price_above_ema period 50` (`1D`) | same |
| Bollinger squeeze | `bb_upper / bb_lower < 1.05` | `bb_squeeze` threshold `1.05` (`1D`) | same |
| RSI | `45 < rsi14 < 60` | `rsi_in_range min 45 max 60` (`1D`) | same |
| ATR % | `atr_pct < 0.03` | `atr_pct_below` threshold `0.03` (`1D`) | same |
| Relative volume | `rvol10 < 0.8` | `rvol_low` threshold `0.8` (`1D`) | same threshold |
| Liquidity | `close >= 10` and `adv_usd20 >= 20,000,000` | **none** | research only |
| Fundamentals | absent | absent | — |
| Timeframes | daily only | `1D` only | same |

### 1.4 `volume_trend_accumulation` vs `config/screens/volume-trend-accumulation.yaml`

| Condition | Research (`setups.volume_trend_accumulation`) | Deployed YAML | Status |
|---|---|---|---|
| Accumulation measure (OBV / A-D) | **absent** | `obv_rising` (`min_rvol 1.0`) | deployed only |
| Price vs SMA20 | `close > sma20` | absent | research only |
| Price vs EMA50 | `close > ema50` | `price_above_ema period 50` (`1D`) | same |
| Relative volume | `rvol10 > 1.3` | `rvol_high` threshold `1.3` (`1D`) | same threshold |
| RSI | `55 < rsi14 < 70` | `rsi_in_range min 55 max 70` (`1D`) | same |
| ADX | `adx14 > 25` | `adx_trending` threshold `25` (`1D`) | same |
| Price vs VWAP | absent | `price_above_vwap` (`1D`) | deployed only |
| Market cap | absent | `market_cap_gt 2,000,000,000` | deployed only |
| Exchange | absent | `exchange_in [NYSE, NASDAQ]` | deployed only |
| Price floor | `close >= 10` (liquidity gate) | `close_above 5.0` | different |
| EPS | absent | `eps_positive` | deployed only |
| P/E cap | absent | `pe_max 60` | deployed only |
| Analyst rating | absent | `analyst_rating_in [StrongBuy, Buy]` | deployed only |
| Liquidity | `adv_usd20 >= 20,000,000` | none | research only |

## 2. What each name does and does not test

- **`breakout_52week` contains no 52-week-high condition.** The research rule is
  `close > ema200`, `ema20 > ema50`, `ema50 > ema200`, `macd > macd_signal`, `adx14 > 30`,
  `rvol10 > 1.5`, under a liquidity gate. It measures a bullish EMA stack with momentum and
  volume expansion, not proximity to a 52-week high. The deployed
  `config/screens/52week-breakout.yaml` also has no 52-week-high rule (no
  `price_near_52w_high` entry), so the mismatch exists in both places. A name that describes
  what is actually tested: `ema_stack_momentum_breakout`. Nothing is renamed here.
- **`volume_trend_accumulation` contains no accumulation measure.** No OBV and no
  accumulation/distribution line is computed in `backend/app/research/indicators.py` or used
  in the setup. It tests above-average volume (`rvol10 > 1.3`) plus an uptrend
  (`close > sma20`, `close > ema50`, `adx14 > 25`) and an RSI band (55-70). The deployed YAML
  does contain `obv_rising`, so "accumulation" is only true of the deployed version. A name
  that describes the research rule: `high_relative_volume_uptrend`. Nothing is renamed here.
- **`statistical_mean_reversion`** tests four oversold thresholds (RSI < 32, CCI < -100,
  ATR% < 0.04, RVOL > 1.2) on liquid names. The name is accurate; the "statistical" part is
  thresholds, not a fitted model.
- **`low_vol_setup`** tests low realized volatility (ATR% < 0.03, RVOL < 0.8) inside a
  Bollinger squeeze with price above EMA50. The name is accurate.

## 3. Matched-random control design

`control.matched_random_signals` counts the strategy's signals per date, then places the same
number of signals on that date on a random sample of symbols that pass `eligible()` (liquidity
plus non-NaN indicators). It therefore matches the strategy's **daily entry count**, its
eligibility universe and its entry dates, and randomises only **which stock** is bought.

Consequence: the matched-random control tests **stock selection**, not market timing. A
positive p-value comparison means "the strategy's chosen symbols did not beat random eligible
symbols entering on the same days." It cannot show whether the entry dates carry information.
`control.permuted_signals` (same per-symbol signal count, dates permuted) and
`control.time_shifted_signals` (+20 to +60 bars) are the controls that disturb timing, and both
are run at much smaller counts (10 permuted, 2 shifted in the D-81/D-82 budget), so their
p-value floors are about 0.091 and 0.333 respectively.

## 4. Provenance of "74.3% WR, 5.92 PF"

`config/regime_screens.yaml:29` carries the comment `# 74.3% WR, 5.92 PF` on the
`52week-breakout` entry.

- **Source file:** `docs/DECISIONS/D-61-elite-template-deployment.md`, line 43, table
  "Results — Elite Templates": `| **52week-breakout** | 74.3% | 5.92 | 0.51 | 10/10 | 55.9 |`
  (win rate, profit factor, Sharpe, valid symbols, trades/symbol).
- **Commit:** `a8d7983` — "fix: Ticker analysis data accuracy fixes (D-65)". The same commit
  introduced the comment in `config/regime_screens.yaml`.
- **Repeated in:** `docs/DECISIONS/D-63-morning-brief-elite-templates.md` line 32.
- **Method stated in D-61:** 21 templates x 10 large-cap symbols (AAPL, MSFT, GOOGL, AMZN,
  NVDA, META, TSLA, AVGO, ORCL, CRM), 2023-01-01 to 2024-12-31, output
  `backtest_results_20260926_060935.json`. That file is present in the repository root.

Status of the claim:

- `docs/DECISIONS/D-61-elite-template-deployment.md` carries a **SUPERSEDED (2026-10-19)**
  banner: the D-61 engine had a 4h-timeframe blind spot, silently skipped unavailable filters,
  and used look-ahead/collapsed exits; the re-validation found the numbers "inflated by an
  order of magnitude".
- `config/regime_screens.yaml` carries a **CAVEAT (2026-10-19)** saying the inline WR/PF stats
  are superseded, with no re-tuning yet.
- The corrected re-validation (`docs/backtests/VALIDATION_REPORT.md`, line 53) reports
  `52week-breakout` at 53.3% win rate, PF 1.57, on 30 trades.
- The D-82 baseline reports `breakout_52week` at 47.2% win rate, PF 0.98.

The 74.3% / 5.92 claim is **unreconciled**: no artifact produced by the current harness
reproduces it. The D-82 baseline is **not directly comparable** to it because the exits
(2.0 ATR stop, 3.0 ATR target, 15-bar time stop), the universe (current S&P 500 snapshot,
501 tradable symbols), the window (2015-2026) and the cost model (15 bps per side) all differ
from the D-61 sweep.

## 5. Known simplifications

- **Fills at exact stop/target within a bar.** `engine.py` handles an opening gap through the
  stop or target at the open price (`stop_gap`, `target_gap`). If the bar opens between stop
  and target and then trades through a level, the fill is exactly at the stop or target price,
  with no intrabar slippage beyond the fixed cost. When both levels are touched in the same
  bar, the stop wins (`engine.py` lines 196-211).
- **Survivorship.** The universe is `config/replay_universe_sp500.txt`, a snapshot of current
  index membership. Companies removed from the index are absent; recent listings start at
  their first available bar.
- **Liquidity gate on dividend-adjusted prices.** `backend/app/research/data.py` downloads with
  `auto_adjust=True`, so `close >= 10` and `adv_usd20 >= 20,000,000` are evaluated on
  split- and dividend-adjusted prices, which can differ from the prices a trader saw.
- **Single candidate-shuffle seed for the real run.** The strategy is run once with
  `seed=42`; the shuffle only reorders candidates when more are available than slots. The
  D-82 diagnostics (`docs/backtests/research/DIAGNOSTICS.md`) report across-seed std of the
  mean net R of 0.0136-0.0219, which is the size of the seed-to-seed variation that single
  seed carries.
- **Daily bars only.** The research harness has no 4h path, so any YAML rule declared on a 4h
  timeframe (for example `rvol_high` in `52week-breakout.yaml`) has no research equivalent.
