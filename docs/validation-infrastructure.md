# Validation Infrastructure

The conflu.ai validation infrastructure provides a comprehensive, institutional-grade validation framework for trading strategies. It replaces ad-hoc testing with statistically rigorous, regime-aware validation suitable for institutional deployment.

## Overview

The validation infrastructure consists of six modular validators coordinated by a unified pipeline orchestrator:

```
┌─────────────────────────────────────────────────────────────────┐
│                    ValidationOrchestrator                        │
├─────────────────────────────────────────────────────────────────┤
│  1. StatisticalValidator    → Significance, effect sizes, repro │
│  2. WalkForwardValidator    → OOS testing with real backtests   │
│  3. MonteCarloValidator     → Bootstrap, tail risk, path analysis│
│  4. RegimeValidator         → Cross-regime consistency          │
│  5. StressTestValidator     → Crisis scenarios, tail risk       │
│  6. PaperTradingValidator   → Live-like execution simulation    │
└─────────────────────────────────────────────────────────────────┘
```

Each validator can be used independently or as part of the unified pipeline with pass/fail gates.

## Pipeline Stages

| Stage | Validator | Purpose | Gate Criteria |
|-------|-----------|---------|---------------|
| 1 | **Statistical** | Significance, effect sizes, reproducibility | 80% tests pass, Sharpe CI > 0 |
| 2 | **Walk-Forward** | OOS performance, IS/OOS degradation | Min 4 OOS windows, <50% IS→OOS degradation |
| 3 | **Monte Carlo** | Bootstrap distributions, tail risk | Sharpe 95% CI > 0, DD 95% CI > -50% |
| 4 | **Regime** | Cross-regime consistency | ≥60% cross-regime consistency |
| 5 | **Stress Test** | Crisis scenarios, tail risk | Max DD < 50% in crisis, recovery < 1yr |
| 6 | **Paper Trading** | Live-like execution, fills, slippage | Fill rate >95%, latency <5ms |

## Quick Start

```python
from backend.app.infrastructure.validation import (
    ValidationOrchestrator,
    PipelineConfig,
    PipelinePresets
)

# Use a preset or create custom config
config = PipelinePresets.production()

# Create orchestrator
orchestrator = ValidationOrchestrator(config)

# Run validation
result = await orchestrator.run(
    strategy_fn=my_strategy,
    symbols=["AAPL", "MSFT", "NVDA", "TSLA"],
    timeframe="1D"
)

if result.overall_passed:
    print("✅ All gates passed - strategy ready for deployment")
else:
    print(f"❌ Failed: {result.summary['failures']}")
```

## Validators Reference

### StatisticalValidator
Rigorous statistical testing for every strategy:
- **Hypothesis tests**: mean return, Sharpe, skewness, kurtosis, autocorrelation, stationarity
- **Benchmark-relative**: alpha (Jensen), beta, information ratio
- **Trade-level**: win rate, profit factor significance
- **Multiple testing correction**: Benjamini-Hochberg FDR
- **Effect sizes**: Cohen's d, probability of superiority, common language ES
- **Bootstrap CIs** (10,000 samples) for all metrics
- **Power analysis**: required sample size for 80% power
- **Reproducibility**: split-sample correlation, bootstrap stability

### WalkForwardValidator
Proper out-of-sample testing with real backtests:
- **Window types**: Anchored (expanding), Rolling, Hybrid
- Real vectorbt backtests on each OOS window
- IS/OOS correlation, degradation analysis, parameter stability
- Regime-aware window labeling
- Gates: min OOS windows, max IS→OOS degradation, consistency ratio

### MonteCarloValidator
Bootstrap/block bootstrap with real return distributions:
- Methods: IID, block, stationary block, circular block
- Politis-Romano automatic block length selection
- 10,000+ simulations with path-dependent analysis
- Tail risk: VaR/CVaR 95/99, extreme value theory (GPD fit)
- Shortfall probability and expected shortfall analysis
- Path analysis: recovery time, max DD distribution, time-to-recovery

### RegimeValidator
Cross-regime performance attribution:
- Regime detection: 8 regimes (bull/bear/sideways × low/med/high vol + crisis/recovery)
- Per-regime metrics: return, vol, Sharpe, Sortino, max DD, win rate, profit factor
- Transition analysis: from→to regime, duration, performance delta, Sharpe delta
- Consistency scoring: cross-regime Sharpe/return/DD/win-rate CV
- Attribution: weighted return by regime duration, best/worst regime identification

### StressTestValidator
Pre-defined and synthetic crisis scenarios:
- **Historical**: GFC 2008, COVID 2020, Inflation 2022, Dotcom 2000, Flash Crash 2010, Euro Debt 2011
- **Synthetic**: correlation→1, VIX>60, liquidity crisis (10x spreads), rate shock, currency crisis, commodity shock, tail event (5σ)
- Regime transitions: bull→bear, low→high vol, trend→mean reversion
- Gates: max DD < 50% in crisis, recovery < 1yr, Sharpe degradation < 50%, correlation increase < 30%

### PaperTradingValidator
Realistic virtual execution engine:
- Order types: market, limit, stop, stop-limit, trailing stop
- Slippage models: linear, sqrt, Almgren-Chriss, empirical
- Market impact: linear, sqrt, Almgren-Chriss
- Latency simulation: network (lognormal), exchange (lognormal), queue (exponential)
- Fill probability models: deterministic, probabilistic, queue-based
- Commission/fee schedules: per-share, bps, SEC fee, clearing fee
- Margin: initial/maintenance, max leverage, position/sector/exposure limits
- Risk: daily loss limit, max DD, per-position stop, virtual margin calls

## Pipeline Presets

```python
# Development - fast, minimal validation
PipelinePresets.development()
# enable_statistical=True, others=False

# Staging - comprehensive but faster
PipelinePresets.staging()
# All stages enabled, faster MC (2000 sims), limited stress scenarios

# Production - full validation
PipelinePresets.production()
# All stages, full MC (10k sims), full stress scenarios, 60-day paper trading

# Quick - just statistical + stress test
PipelinePresets.quick()
```

## Running the Pipeline

```python
# Using the convenience function
result = await run_validation_pipeline(
    strategy_fn=my_strategy,
    symbols=["AAPL", "MSFT", "NVDA", "TSLA"],
    timeframe="1D",
    config=PipelinePresets.production()
)

# Or with custom config
config = PipelineConfig(
    enable_statistical=True,
    enable_walk_forward=True,
    enable_monte_carlo=True,
    enable_regime=True,
    enable_stress_test=True,
    enable_paper_trading=True,
    monte_carlo_n_simulations=10000,
    walk_forward_min_oos_windows=8,
    paper_trading_min_days=60,
)
result = await run_validation_pipeline(strategy_fn, symbols, "1D", config)
```

## Using Individual Validators

```python
# Walk-forward only
wf_validator = WalkForwardValidator(WalkForwardConfig(
    train_months=12, test_months=3, step_months=1, min_oos_windows=4
))
report = wf_validator.run(strategy_fn, symbols)

# Monte Carlo only
mc_validator = MonteCarloValidator(MonteCarloConfig(
    n_simulations=10000,
    method=BootstrapMethod.STATIONARY_BLOCK,
    block_length=20
))
report = mc_validator.run(returns)

# Stress test only
st_validator = StressTestValidator(StressConfig(
    scenarios=[StressScenario.GFC_2008, StressScenario.COVID_2020]
))
report = await st_validator.run(strategy_fn, symbols)

# Paper trading only
pt_validator = PaperTradingValidator(PaperTradingConfig(
    initial_cash=100000,
    commission_bps=1.0,
    slippage=SlippageModel(model="sqrt")
))
pt_validator.reset(100000)
# ... run strategy loop with pt_validator.step() ...
summary = pt_validator.get_account_summary()
```

## Configuration Reference

### PipelineConfig
```python
PipelineConfig(
    # Stage enablement
    enable_statistical=True,
    enable_walk_forward=True,
    enable_monte_carlo=True,
    enable_regime=True,
    enable_stress_test=True,
    enable_paper_trading=True,
    
    # Gate thresholds
    statistical_min_pass=0.8,
    walk_forward_min_oos_windows=4,
    walk_forward_max_degradation=0.5,
    monte_carlo_min_sharpe_ci=0.0,
    monte_carlo_max_drawdown_ci=-0.5,
    regime_min_consistency=0.6,
    stress_test_max_drawdown_crisis=0.50,
    paper_trading_min_days=30,
    
    # Execution
    max_parallel_stages=2,
    timeout_seconds=3600,
    continue_on_failure=False,
    
    # Paper trading
    initial_cash=100000.0,
    slippage_model="sqrt",
    
    # Monte Carlo
    monte_carlo_n_simulations=5000,
    
    # Stress test
    stress_test_scenarios=["gfc_2008", "covid_2020", "inflation_2022",
                          "correlation_breakdown", "vol_spike"],
    
    # Output
    generate_report=True,
    report_format="json",
    save_artifacts=True,
)
```

## Output Artifacts

The pipeline generates:
- **JSON Report**: Complete pipeline result with all stage details
- **HTML Report**: Visual report with charts (equity curves, drawdowns, regime timeline)
- **PDF Report**: Printable summary for stakeholders
- **Artifacts**: Per-stage raw data for further analysis

## Best Practices

1. **Use PipelinePresets** — Start with `PipelinePresets.production()` for production deployment
2. **Run Statistical First** — Always run statistical validation first; it's fast and catches basic issues
3. **Check Walk-Forward Degradation** — IS→OOS degradation >50% indicates overfitting
4. **Review Regime Attribution** — Know which regimes drive performance
5. **Stress Test Before Deploy** — Never deploy without passing crisis scenarios
6. **Paper Trade Before Live** — Minimum 30 days paper trading with realistic fills
7. **Review Monte Carlo Tails** — Check VaR/CVaR 99% and recovery time distributions

## Troubleshooting

| Issue | Likely Cause | Solution |
|-------|--------------|----------|
| Walk-forward OOS windows < 4 | Insufficient history | Reduce train_months or increase data history |
| MC Sharpe CI includes 0 | Strategy not robust | Improve signal quality, add risk management |
| Regime consistency < 60% | Strategy regime-dependent | Add regime-specific logic or avoid weak regimes |
| Stress test max DD > 50% | Crisis vulnerability | Add tail hedging, reduce leverage |
| Paper trading fill rate < 95% | Slippage/liquidity model too aggressive | Tune slippage model, check ADV estimates |
| Statistical reproducibility < 0.8 | Overfitting/non-stationarity | More data, simpler model, regularization |