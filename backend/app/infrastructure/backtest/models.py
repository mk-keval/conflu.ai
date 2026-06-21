"""Backtest-specific Pydantic models for configuration and results.

This module contains models specific to the backtest engine.
Cross-cutting domain models (Trade, Metrics) live in backend/app/domain/models.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.models import Metrics


class SignalSource(BaseModel):
    """Defines how signals are generated for the backtest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["screen_config", "filter_list", "indicator_crossing"] = "filter_list"
    screen_name: str | None = Field(
        default=None,
        description="Name of screen template (if type=screen_config)",
    )
    filters: list[str] | None = Field(
        default=None,
        description="Filter names to apply (if type=filter_list)",
    )
    indicator_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Indicator crossing thresholds (if type=indicator_crossing)",
    )


class OptimizationConfig(BaseModel):
    """Walk-forward optimization configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    method: Literal["expanding", "rolling"] = "expanding"
    train_pct: float = Field(default=0.7, ge=0.5, le=0.9)
    min_train_bars: int = Field(default=252, ge=50)
    metric: Literal["sharpe", "sortino", "calmar", "custom"] = "sharpe"
    param_grid: dict[str, list[Any]] = Field(default_factory=dict)


class MonteCarloConfig(BaseModel):
    """Monte Carlo simulation configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    n_paths: int = Field(default=1000, ge=100, le=10_000)
    method: Literal["bootstrap", "block_bootstrap"] = "bootstrap"
    block_size: int = Field(default=20, ge=5, le=100)
    confidence: float = Field(default=0.95, ge=0.8, le=0.999)


class BacktestRunConfig(BaseModel):
    """Complete configuration for a single backtest run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    symbols: list[str]
    asset_class: str = "equities"
    timeframe: str = "1D"
    start: datetime
    end: datetime
    initial_cash: float = Field(default=100_000.0, gt=0)
    fees_bps: float = Field(default=10.0, ge=0.0, description="Fee in basis points per trade side")
    slippage_bps: float = Field(default=5.0, ge=0.0, description="Slippage in basis points per trade side")
    position_sizing: Literal["fixed", "atr", "kelly"] = "fixed"
    sizing_params: dict[str, Any] = Field(default_factory=dict)
    signal_source: SignalSource = Field(default_factory=lambda: SignalSource(type="filter_list"))
    optimization: OptimizationConfig = Field(default_factory=OptimizationConfig)
    monte_carlo: MonteCarloConfig = Field(default_factory=MonteCarloConfig)

    # Computed properties
    @property
    def fees_decimal(self) -> float:
        """Convert bps to decimal fraction for vectorbt."""
        return self.fees_bps / 10_000

    @property
    def slippage_decimal(self) -> float:
        """Convert bps to decimal fraction for vectorbt."""
        return self.slippage_bps / 10_000


class BacktestRunRecord(BaseModel):
    """Complete results from a single backtest run."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    config_hash: str
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    initial_cash: float
    position_sizing: str
    metrics: Metrics | None = None
    stats_json: str | None = None
    trades_count: int = 0
    total_fees: float = 0.0
    duration_ms: float = 0.0
    created_at: datetime | None = None


@dataclass
class FoldResult:
    """Results from a single walk-forward fold."""

    fold_index: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    best_params: dict[str, Any]
    in_sample_metrics: Metrics
    out_of_sample_metrics: Metrics
    oos_equity_curve: pd.Series  # pandas Series with datetime index


class OptimizationResult(BaseModel):
    """Complete walk-forward optimization results."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    symbol: str
    param_grid: dict[str, list[Any]]
    optimization_metric: Literal["sharpe", "sortino", "calmar", "custom"] = "sharpe"
    folds: list[FoldResult] = Field(default_factory=list)
    best_params_overall: dict[str, Any] = Field(default_factory=dict)
    oos_metrics_aggregated: Metrics | None = None
    parameter_sensitivity: dict[str, list[float]] = Field(default_factory=dict)


class MCSimulationResult(BaseModel):
    """Results from a Monte Carlo simulation."""

    model_config = ConfigDict(frozen=True)

    n_paths: int
    method: str
    final_equity_p5: float | None = None
    final_equity_p50: float | None = None
    final_equity_mean: float | None = None
    final_equity_p95: float | None = None
    max_drawdown_p50: float | None = None
    sharpe_p50: float | None = None
    cagr_p50: float | None = None
    ruin_probability: float | None = None
    equity_curves: list[list[float]] | None = Field(
        default=None,
        description="2D array of equity curves (n_paths × n_bars), stored as list-of-lists for serialization",
    )


# ── Phase 9: Advanced Backtest Models ──


class OptimizationSearchSpace(BaseModel):
    """Defines search space for parameter optimization.

    Supports grid, random, and bayesian (Optuna TPE) methods.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    method: Literal["grid", "random", "bayesian"] = "grid"
    grid_params: dict[str, list[Any]] = Field(default_factory=dict)
    param_distributions: dict[str, dict[str, Any]] = Field(default_factory=dict)
    objectives: list[str] = Field(default_factory=lambda: ["sharpe"])
    objective_weights: list[float] | None = Field(default=None)
    max_trials: int = Field(default=100, ge=1, le=1_000_000)
    timeout_s: int | None = Field(default=None, ge=10)
    n_jobs: int = Field(default=1, ge=1, le=32)
    early_stopping: bool = True
    min_improvement: float = Field(default=0.01, ge=0.0, le=1.0)
    multi_objective: bool = False


class RegimeConfig(BaseModel):
    """Market regime detection configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    method: Literal["hmm", "volatility_quantile"] = "hmm"
    n_states: int = Field(default=3, ge=2, le=4)
    window_days: int = Field(default=252, ge=63, le=1260)
    n_quantiles: int = Field(default=4, ge=2, le=5)
    vol_window_days: int = Field(default=21, ge=5, le=252)
    features: list[str] = Field(default_factory=lambda: ["returns", "volatility"])


class ReportConfig(BaseModel):
    """Report generation configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    formats: list[Literal["html", "pdf", "json"]] = Field(default_factory=lambda: ["html"])
    template_name: str = "backtest_report.html"
    include_equity_curve: bool = True
    include_drawdown: bool = True
    include_trade_analysis: bool = True
    include_regime_analysis: bool = False
    include_parameter_sensitivity: bool = True


class ComparisonConfig(BaseModel):
    """Strategy comparison configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    run_ids: list[str] = Field(default_factory=list, min_length=2, max_length=50)
    labels: list[str] | None = Field(default=None)
    include_significance: bool = True
    bootstrap_samples: int = Field(default=1000, ge=100, le=10000)


class TrialResult(BaseModel):
    """Result from a single optimization trial."""

    model_config = ConfigDict(frozen=True)

    trial_number: int
    params: dict[str, Any]
    objectives: dict[str, float | None]
    is_pareto: bool = False
    state: str = "complete"
    duration_ms: float | None = None


class OptimizationResultV2(BaseModel):
    """Enhanced optimization result with Optuna integration."""

    model_config = ConfigDict(frozen=True)

    study_id: str
    symbol: str
    method: str
    search_space: OptimizationSearchSpace | None = None
    best_params: dict[str, Any]
    best_objectives: dict[str, float | None]
    trials: list[TrialResult] = Field(default_factory=list)
    n_trials: int = 0
    duration_ms: float = 0.0
    param_importance: dict[str, float] = Field(default_factory=dict)


class RegimeResult(BaseModel):
    """Results from regime detection."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    method: str
    n_states: int
    regime_labels: list[int]
    regime_names: list[str]
    transition_matrix: list[list[float]] | None = None
    state_means: list[float] | None = None
    state_stds: list[float] | None = None
    timestamps: list[str]
    features_json: str | None = None


@dataclass
class RegimeSeries:
    """Regime labels aligned with DatetimeIndex for chart overlay."""

    timestamps: pd.DatetimeIndex
    labels: list[int]
    names: list[str]
    confidence: list[float] | None = None


class ReportResult(BaseModel):
    """Result from report generation."""

    model_config = ConfigDict(frozen=True)

    report_id: str
    run_id: str
    format: str
    template: str
    report_path: str | None = None
    size_bytes: int = 0
    created_at: str = ""


class StrategyComparisonResult(BaseModel):
    """Results from comparing multiple backtest runs."""

    model_config = ConfigDict(frozen=True)

    comparison_id: str
    run_ids: list[str]
    labels: list[str]
    n_strategies: int
    best_by_metric: dict[str, str] = Field(default_factory=dict)
    metrics_table: list[dict[str, Any]] = Field(default_factory=list)
    significance_matrix: list[list[float | None]] = Field(default_factory=list)
    equity_curves: dict[str, list[dict[str, float]]] = Field(default_factory=dict)
    drawdown_curves: dict[str, list[dict[str, float]]] = Field(default_factory=dict)
    rolling_metrics: dict[str, dict[str, list[float]]] = Field(default_factory=dict)
