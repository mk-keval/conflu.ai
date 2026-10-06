# D-63: Morning Brief / Pro Page — Regime Screens Updated to Elite Templates

**Date**: 2026-09-26
**Status**: Implemented
**Branch**: `fix/technical-tab-empty`

## Summary

Updated `config/regime_screens.yaml` to use elite templates validated in D-61 backtest (>55% WR, >1.5 PF). The Morning Brief (`/pro`) now uses templates proven to pick quality tickers.

## Changes Made

### `config/regime_screens.yaml` (v2)

| Regime | Old Templates (Removed) | New Elite Templates |
|--------|------------------------|---------------------|
| **strong_trend** | trend-follower, 52week-breakout, institutional-trend-follower-mtf, quality-trend-fundamentals, high-conviction-stack | **52week-breakout (74.3% WR)**, **trend-follower-v2 (71.3%)**, **vcp-breakout (71.0%)**, **trend-pullback-v2 (59.7%)**, institutional-trend-follower-mtf (defensive) |
| **neutral** | 52week-breakout, **short-squeeze (removed)**, volume-trend-accumulation, bull-flag-continuation, statistical-mean-reversion | **52week-breakout**, **volume-trend-accumulation**, **bull-flag-continuation**, **trend-follower-v2**, statistical-mean-reversion (defensive) |
| **choppy** | bull-flag-continuation, short-squeeze, volatility-expansion, low-vol-setup, statistical-mean-reversion | **bull-flag-continuation**, **trend-pullback-v2**, **volume-trend-accumulation**, **low-vol-setup**, statistical-mean-reversion (defensive) |
| **ranging** | statistical-mean-reversion, mean-reversion, volume-trend-accumulation, low-vol-setup | **statistical-mean-reversion**, **mean-reversion**, **volume-trend-accumulation**, **low-vol-setup** (defensive) |
| **high_vol** | institutional-swing-quality, volatility-expansion, short-squeeze, quality-trend-fundamentals | **institutional-swing-quality**, **volatility-expansion**, **institutional-quality-v2**, **distribution** (defensive) |

### Removed
- `short-squeeze` — 0 trades in backtest (removed in D-61)
- `trend-follower` → replaced by `trend-follower-v2` (71.3% WR)
- `quality-trend-fundamentals` → lower quality
- `high-conviction-stack` → lower quality

### Added Elite Templates (D-61 Validated)
| Template | Win Rate | Profit Factor | Sharpe | Regime |
|----------|----------|---------------|--------|--------|
| 52week-breakout | 74.3% | 5.92 | 0.51 | strong_trend, neutral |
| trend-follower-v2 | 71.3% | 4.50 | 0.39 | strong_trend, neutral |
| vcp-breakout | 71.0% | 4.40 | 0.39 | strong_trend |
| trend-pullback-v2 | 59.7% | 5.13 | 0.90 | strong_trend, choppy |
| institutional-trend-follower-mtf | 67.9% | 3.83 | 0.36 | strong_trend (defensive) |
| mean-reversion | 67.2% | 26.83 | 0.89 | ranging |
| volume-trend-accumulation | 66.3% | 3.35 | 0.54 | neutral, choppy, ranging |
| institutional-quality-v2 | 64.0% | 2.90 | 0.34 | high_vol |
| low-vol-setup | 55.1% | 7.25 | 0.57 | choppy, ranging (defensive) |
| statistical-mean-reversion | 74.2% | 52.76 | 0.66 | neutral, ranging (defensive) |
| mean-reversion | 67.2% | 26.83 | 0.89 | ranging |
| distribution | 59.2% | 23.04 | 0.57 | high_vol (defensive) |
| breakdown | 56.4% | 44.30 | 0.53 | (available) |

## Verification

- ✅ Backend screener tests: 60/60 pass
- ✅ Playwright E2E: 10/10 pass (workflow, simple-backtest, filter-sweep)
- ✅ Frontend build: `npm run typecheck` + `npm run build` pass
- ✅ Config validates: All 19 templates available via API

## Impact

**Morning Brief (`/pro`)** now surfaces tickers using battle-tested templates with proven edge:
- Strong trend regimes → momentum/breakout with strict RS filters
- Neutral/choppy → balanced momentum + quality
- Ranging → mean-reversion with statistical edge
- High vol → institutional quality + distribution detection

**Pro Page One-Click Verdict** unchanged — uses deep analysis per symbol.

**Workflow Mode** unchanged — user-driven, no template selection.