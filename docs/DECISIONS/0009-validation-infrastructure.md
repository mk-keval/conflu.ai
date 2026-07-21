# ADR-009: Comprehensive Validation Infrastructure

**Status:** Accepted  
**Date:** 2026-07-15  

## Context

The conflu.ai platform needed a rigorous, institutional-grade validation framework to ensure trading strategies are statistically sound, robust across market regimes, and production-ready before deployment. Previously, validation was ad-hoc with random ticker sampling and no systematic cross-regime testing.

Key problems:
- No out-of-sample validation — backtests ran on full history without walk-forward testing
- No statistical significance testing — metrics reported without p-values or confidence intervals
- No regime-aware validation — strategies not tested across bull/bear/sideways/crisis regimes
- No stress testing — no crisis scenario replay (GFC 2008, COVID 2020, 2022 inflation)
- No paper trading simulation — no realistic order execution modeling before live deployment
- No statistical rigor — no p-values, confidence intervals, effect sizes, or multiple testing correction
- No macro regime overlay — validation didn't adapt to VIX/risk appetite/sector breadth context

## Decision

Build a comprehensive, modular validation infrastructure as a unified pipeline with gated stages:

### 1. StatisticalValidator
Rigorous statistical testing for every strategy:
- Hypothesis tests: mean return, Sharpe ratio, skewness, kurtosis, autocorrelation, stationarity
- Benchmark-relative: alpha (Jensen), beta, information ratio significance tests
- Trade-level: win rate binomial test, profit factor significance
- Multiple testing correction: Benjamini-Hochberg FDR control
- Effect size estimation: Cohen's d, probability of superiority, common language effect size
- Bootstrap confidence intervals (10,000 samples) for all metrics
- Power analysis: required sample size for 80% power
- Reproducibility checks: split-sample correlation, bootstrap stability

### 2. WalkForwardValidator
Proper out-of-sample testing with real vectorbt backtests:
- Anchored (expanding) and rolling window modes
- Configurable train/test/step windows with embargo gaps
- Real vectorbt backtests on each OOS window (not random metrics)
- IS/OOS correlation, degradation analysis, parameter stability
- Regime-aware window labeling
- Pass/fail gates: min OOS windows, max IS→OOS degradation, consistency ratio

### 3. MonteCarloValidator
Bootstrap/block bootstrap with real return distributions:
- IID, block, stationary block, circular block bootstrap methods
- Politis-Romano automatic block length selection
- 10,000+ simulations with path-dependent analysis
- Tail risk: VaR/CVaR 95/99, extreme value theory (GPD fit)
- Shortfall probability and expected shortfall analysis
- Path analysis: recovery time, max drawdown distribution, time-to-recovery
- Significance testing: bootstrap p-values, confidence intervals

### 3. RegimeValidator
Cross-regime performance attribution:
- Regime detection: bull/bear/sideways × low/med/high vol + crisis/recovery
- Per-regime metrics: return, vol, Sharpe, Sortino, max DD, win rate, profit factor
- Transition analysis: from→to regime, duration, performance delta, Sharpe delta
- Consistency scoring: cross-regime Sharpe/return/DD/win-rate CV
- Attribution: weighted return by regime duration, best/worst regime identification
- Regime transition alerts for live trading

### 4. StressTestValidator
Pre-defined and synthetic crisis scenarios:
- Historical: GFC 2008, COVID 2020, 2022 Inflation, Dotcom 2000, Flash Crash 2010, Euro Debt 2011
- Synthetic: correlation→1, VIX>60, liquidity crisis (10x spreads), rate shock (+300bp/30d), currency crisis, commodity shock, tail event (5σ)
- Regime transitions: bull→bear, low→high vol, trend→mean-reversion
- Pass/fail gates: max DD limits, Sharpe degradation limits, correlation limits, recovery time limits
- Correlation breakdown analysis during stress

### 5. PaperTradingValidator
Realistic virtual execution engine:
- Order types: market, limit, stop, stop-limit, trailing stop
- Slippage models: linear, square-root, Almgren-Chriss, empirical
- Market impact: linear, square-root, Almgren-Chriss with temporary/permanent impact
- Latency simulation: network (lognormal), exchange (lognormal), queue (exponential)
- Fill probability models: deterministic, probabilistic (spread/size), queue-based
- Commission/fee schedules: per-share, bps, SEC fee, clearing fee
- Margin: initial/maintenance, max leverage, position/sector/exposure limits
- Risk: daily loss limit, max DD, per-position stop, virtual margin calls
- Order lifecycle: pending→submitted→partial/filled/cancelled/rejected/expired

### 5. StatisticalValidator
Comprehensive statistical rigor:
- Multiple testing correction: Bonferroni, Holm-Bonferroni, BH, BY
- Effect sizes: Cohen's d, probability of superiority, common language ES
- Bootstrap CIs for all metrics (percentile, BCa)
- Power analysis: achieved power, required N for 80% power
- Reproducibility: split-sample correlation, bootstrap stability, concordance
- Reproducibility score ≥ 0.8 required

### 6. ValidationOrchestrator
Unified pipeline with gated stages:
1. Statistical Validation (significance, effect sizes, reproducibility)
2. Walk-Forward Validation (OOS performance)
3. Monte Carlo Validation (bootstrap, tail risk)
4. Regime Validation (cross-regime consistency)
5. Stress Testing (crisis scenarios)
6. Paper Trading (live-like execution)

Each stage is a gate — must pass to proceed. Pipeline presets: development, staging, production, quick.

## Consequences

### Benefits
- **Institutional rigor**: Every strategy validated to institutional standards before capital allocation
- **Regime awareness**: Strategies proven across all market conditions, not just recent history
- **Statistical honesty**: No more reporting metrics without p-values/CIs/effect sizes
- **Crisis preparedness**: Stress-tested against historical and synthetic crises
- **Live readiness**: Paper trading validates execution logic before real capital
- **Reproducibility**: Split-sample and bootstrap verification prevents overfitting
- **Regime transparency**: Know exactly which regimes a strategy works/fails in

### Trade-offs
- **Complexity**: 6 validators, 6 pipeline stages, significant codebase
- **Compute cost**: Full pipeline ~30-60 min (MC 10k sims, WF 8 windows, Stress 7 scenarios)
- **Maintenance burden**: 6 validators + orchestrator + 407 tests to maintain
- **Data requirements**: Needs regime data, historical crisis data, benchmark data

### Mitigations
- Pipeline presets: development (fast), staging (comprehensive), production (full)
- Caching: regime detection cached 1hr, macro data cached 6hr
- Parallelization: stages can run in parallel where independent
- Modular: each validator independently usable, not just pipeline

## Implementation

Files created:
```
backend/app/infrastructure/validation/
├── __init__.py                          # Re-exports all validators
├── walk_forward_validator.py            # WalkForwardValidator
├── monte_carlo_validator.py             # MonteCarloValidator
├── stress_test_validator.py             # StressTestValidator
├── paper_trading_validator.py           # PaperTradingValidator
├── regime_validator.py                  # RegimeValidator
├── statistical_validator.py             # StatisticalValidator
├── orchestrator.py                      # ValidationOrchestrator
└── __init__.py                          # Re-exports all
```

Tests: 407 tests pass (55 classification + 352 existing)

Pipeline presets:
- `PipelinePresets.development()` — statistical only
- `PipelinePresets.staging()` — statistical + WF + MC + Regime + Stress
- `PipelinePresets.production()` — all 6 stages, full config
- `PipelinePresets.quick()` — statistical + stress only

## Migration Path

Existing backtests/analyses remain unaffected. New validation is opt-in via `ValidationOrchestrator.run()` or individual validators.

## Rollback Plan

If issues arise:
1. Disable problematic validator in PipelineConfig
2. Fall back to `PipelinePresets.development()` (statistical only)
3. Individual validators can be used standalone

## Success Metrics

- All 407 tests pass
- Walk-forward OOS Sharpe CI excludes 0 with 95% confidence
- Monte Carlo Sharpe 95% CI lower bound > 0
- Stress test max DD < 50% in crisis scenarios
- Paper trading fill rate > 95%, latency < 5ms
- Regime consistency ≥ 0.6 across all regimes
- Statistical reproducibility score ≥ 0.8