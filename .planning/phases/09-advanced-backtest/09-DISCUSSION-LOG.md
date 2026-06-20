# Phase 9: Advanced Backtest - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-20
**Phase:** 9-advanced-backtest
**Areas discussed:** Parameter Optimization, Market Regime Detection, Automated Report Generation, Strategy Comparison

---

## Parameter Optimization

| Option | Description | Selected |
|--------|-------------|----------|
| Optuna TPE (Bayesian) | Intelligent parameter search, efficient | ✓ |
| Grid search | Exhaustive, simple | |
| Random search | Simple, parallelizable | |
| CMA-ES / DEAP | Evolutionary, good for complex spaces | |

**User's choice:** Optuna TPE primary, with grid/random as fallbacks
**Notes:** Optuna TPE for efficient search, grid/random as fallbacks. Multi-objective via Pareto. Early stopping with median pruning.

---

## Market Regime Detection

| Option | Description | Selected |
|--------|-------------|----------|
| HMM (hmmlearn) | Full probabilistic, multi-state | ✓ |
| Volatility quantile buckets | Simple, no ML deps | |
| GARCH volatility | Time-varying volatility | |

**User's choice:** HMM primary, volatility buckets fallback
**Notes:** HMM for 2-4 state Gaussian HMM on rolling returns. Volatility bucket fallback. Regime-aware backtest: different params per regime.

---

## Automated Report Generation

| Option | Description | Selected |
|--------|-------------|----------|
| HTML (Jinja2 + Plotly) + PDF (WeasyPrint) | Interactive HTML + static PDF | ✓ |
| ReportLab only | Pure Python PDF | |
| Jinja2 + PDF only | Simpler | |

**User's choice:** HTML + PDF via WeasyPrint
**Notes:** Jinja2 templates + Plotly.js for interactive HTML. WeasyPrint for PDF. User-defined templates, branding.

---

## Strategy Comparison

| Option | Description | Selected |
|--------|-------------|----------|
| Multi-backtest compare | Side-by-side with aligned time axes | ✓ |
| Overlaid equity curves | Normalized + raw | |
| Statistical significance testing | Bootstrap CI, t-test | ✓ |

**User's choice:** Full comparison suite
**Notes:** Overlaid equity curves (normalized), drawdown overlays, rolling metrics, statistical significance (bootstrap CI, t-test).

---

## OpenCode's Discretion

- Optuna storage backend (DuckDB vs SQLite vs PostgreSQL)
- HMM library choice (hmmlearn vs custom vs regime-switching lib)
- Report template system (Jinja2 + WeasyPrint vs ReportLab vs custom)
- Statistical test library (scipy.stats vs pingouin vs custom bootstrap)

---

## Deferred Ideas

- Multi-objective Pareto optimization with interactive frontier
- Genetic algorithm for parameter search (DEAP)
- Factor model risk attribution in reports (Fama-French, PCA)
- Live paper trading integration from optimized params
- Distributed optimization across machines (Ray/Dask)