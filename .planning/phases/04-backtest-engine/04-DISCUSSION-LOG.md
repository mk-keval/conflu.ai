# Phase 4: Backtest Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-19
**Phase:** 4-backtest-engine
**Areas discussed:** VectorBT Portfolio Config, Signal Interface, Walk-Forward Optimization, Monte Carlo, Metrics & Ledger

---

## VectorBT Portfolio Configuration

| Option | Description | Selected |
|--------|-------------|----------|
| vbt.Portfolio.from_signals() | Native vectorbt entry point, all features native | ✓ |
| Custom portfolio loop | Manual position management | |
| Hybrid: vectorbt + custom | Override specific methods | |

**User's choice:** vbt.Portfolio.from_signals() — native position sizing, fees, slippage, all vectorized
**Notes:** Three position sizing modes: Fixed, ATR-based, Kelly. Fees/slippage as bps. Long-only + long-short.

---

## Signal Interface & Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Direct DataFrame from screener | ScreenEngine output → vectorbt format | ✓ |
| Signal service API | HTTP/gRPC service | |
| File-based signals | Parquet files | |

**User's choice:** Direct DataFrame from Phase 3 screener output
**Notes:** Signal timestamps aligned via broadcast_timeframe(). Signal metadata (confidence, source, TF) stored in ledger.

---

## Walk-Forward Optimization

| Option | Description | Selected |
|--------|-------------|----------|
| Expanding + Rolling windows | Both modes supported | ✓ |
| Expanding only | Train grows, test fixed | |
| Rolling only | Fixed windows slide | |

**User's choice:** Both expanding and rolling modes
**Notes:** 70/30 split default, min 252 bars train. Grid + Bayesian optimization. Metric: Sharpe default.

---

## Monte Carlo Simulation

| Option | Description | Selected |
|--------|-------------|----------|
| 1000+ paths, bootstrap + block bootstrap | Resample returns, preserve autocorrelation | ✓ |
| Pure bootstrap | Returns with replacement | |
| Parametric Monte Carlo | Fit distribution, sample | |

**User's choice:** 1000+ paths, bootstrap + block bootstrap (block=20)
**Notes:** 95%/99% CI, percentiles for equity, DD, Sharpe, CAGR. Ruin probability tracked.

---

## Metrics & Trade Ledger

| Option | Description | Selected |
|--------|-------------|----------|
| Full vectorbt metrics + custom | Sharpe, Sortino, Calmar, Max DD, Win Rate, Expectancy, PF, SQN, Ulcer, CAGR | ✓ |
| Minimal metrics | Sharpe, Max DD, Win Rate only | |
| Extended only | Add custom metrics | |

**User's choice:** Full metric suite + detailed trade ledger with MAE/MFE
**Notes:** MAE/MFE from intraday if available, else daily OHLC. Exit reason tracked.

---

## Configuration & Output

| Option | Description | Selected |
|--------|-------------|----------|
| Pydantic BacktestConfig + DuckDB cache | Type-safe config, cached results | ✓ |
| JSON file config + JSON output | Simple files | |
| Database-only config | PostgreSQL | |

**User's choice:** Pydantic BacktestConfig + DuckDB cache
**Notes:** Results cached with config_hash for idempotency. Output: JSON, CSV, Parquet.

---

## OpenCode's Discretion

- Exact module structure for backtest package
- VectorBT version pinning strategy
- Async execution for long-running tasks (deferred to Phase 6)

---

## Deferred Ideas

- Bayesian optimization with Optuna (Phase 9)
- Multi-asset portfolio optimization (correlation-aware sizing)
- Real-time paper trading bridge (Phase 10)
- Alternative data integration for signal enhancement (future)