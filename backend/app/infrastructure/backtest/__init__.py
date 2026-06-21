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
- BacktestOptimizer — Parameter optimization (grid, random, bayesian)
- RegimeDetector — Market regime detection (HMM, volatility quantile)
- ReportGenerator — Automated report generation (HTML, PDF, JSON)
- StrategyComparator — Strategy comparison engine
"""

from __future__ import annotations

from backend.app.infrastructure.backtest.comparison import StrategyComparator
from backend.app.infrastructure.backtest.engine import BacktestEngine, run_backtest
from backend.app.infrastructure.backtest.models import (
    BacktestRunConfig,
    BacktestRunRecord,
    ComparisonConfig,
    MCSimulationResult,
    MonteCarloConfig,
    OptimizationConfig,
    OptimizationResult,
    OptimizationResultV2,
    OptimizationSearchSpace,
    RegimeConfig,
    RegimeResult,
    RegimeSeries,
    ReportConfig,
    ReportResult,
    SignalSource,
    StrategyComparisonResult,
    TrialResult,
)
from backend.app.infrastructure.backtest.optimization import BacktestOptimizer
from backend.app.infrastructure.backtest.regimes import RegimeDetector
from backend.app.infrastructure.backtest.reporting import ReportGenerator

__all__ = [
    "BacktestEngine",
    "BacktestOptimizer",
    "BacktestRunConfig",
    "BacktestRunRecord",
    "ComparisonConfig",
    "MCSimulationResult",
    "MonteCarloConfig",
    "OptimizationConfig",
    "OptimizationResult",
    "OptimizationResultV2",
    "OptimizationSearchSpace",
    "RegimeConfig",
    "RegimeDetector",
    "RegimeResult",
    "RegimeSeries",
    "ReportConfig",
    "ReportGenerator",
    "ReportResult",
    "SignalSource",
    "StrategyComparator",
    "StrategyComparisonResult",
    "TrialResult",
    "run_backtest",
]
