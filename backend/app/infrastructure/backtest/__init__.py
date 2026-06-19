"""Backtest engine package.

Provides:
- BacktestEngine — Orchestrator for running backtests
- BacktestRunConfig — Configuration for a single backtest run
- SignalAdapter — Convert indicator/filter data to vectorbt entry/exit arrays
- PositionSizer — Compute position sizes (fixed, ATR, Kelly)
- WalkForwardOptimizer — Walk-forward parameter optimization
- MonteCarloSimulator — Monte Carlo equity path simulation
- MetricsComputer — Compute portfolio metrics (wraps vectorbt + custom)
- TradeLedger — Convert vectorbt trade records to structured Trade models
"""

from __future__ import annotations

from backend.app.infrastructure.backtest.engine import BacktestEngine, run_backtest
from backend.app.infrastructure.backtest.models import (
    BacktestRunConfig,
    BacktestRunRecord,
    MCSimulationResult,
    MonteCarloConfig,
    OptimizationConfig,
    OptimizationResult,
    SignalSource,
)

__all__ = [
    "BacktestEngine",
    "BacktestRunConfig",
    "BacktestRunRecord",
    "MCSimulationResult",
    "MonteCarloConfig",
    "OptimizationConfig",
    "OptimizationResult",
    "SignalSource",
    "run_backtest",
]
