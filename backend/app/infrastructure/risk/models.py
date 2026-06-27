"""Risk-specific Pydantic models for beta, correlation, VaR, Kelly, and hedging results.

All models are frozen (immutable) and use strict type validation.
Timestamps are UTC-aware datetime objects.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _ensure_utc(v: datetime | None) -> datetime | None:
    """Validate and convert timestamp to UTC."""
    if v is not None and v.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return v.astimezone(UTC) if v is not None else None


class BetaResult(BaseModel):
    """Rolling OLS beta regression results for a single symbol vs benchmark."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    benchmark: str
    beta: float | None = None
    alpha: float | None = None
    r_squared: float | None = None
    std_err: float | None = None
    p_value: float | None = None
    tracking_error: float | None = None
    window_days: int = 60
    n_observations: int = 0
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("computed_at")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        return _ensure_utc(v)  # type: ignore[return-value]


class PortfolioBetaResult(BaseModel):
    """Market-value-weighted portfolio beta aggregated across all positions."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: str
    benchmark: str
    weighted_beta: float | None = None
    symbol_betas: dict[str, float] = Field(default_factory=dict)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("computed_at")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        return _ensure_utc(v)  # type: ignore[return-value]


class CorrelationResult(BaseModel):
    """Rolling Pearson correlation matrix with sector aggregation."""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    window_days: int = 30
    symbols: list[str] = Field(default_factory=list)
    matrix: list[list[float]] = Field(default_factory=list)
    sector_matrix: list[list[float]] | None = None
    sector_labels: list[str] | None = None
    high_correlation_pairs: list[dict[str, Any]] = Field(default_factory=list)
    diversification_score: float | None = None

    @field_validator("timestamp")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        return _ensure_utc(v)  # type: ignore[return-value]


class VaRResult(BaseModel):
    """Value at Risk and Conditional VaR result for a portfolio."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: str
    method: str
    confidence: float
    horizon_days: int = 1
    var: float
    cvar: float | None = None
    component_var: list[float] | None = None
    marginal_var: list[float] | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None
    n_simulations: int | None = None
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("computed_at")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        return _ensure_utc(v)  # type: ignore[return-value]


class KellyRecommendation(BaseModel):
    """Kelly Criterion optimal position sizing recommendation from backtest results."""

    model_config = ConfigDict(frozen=True)

    backtest_run_id: str | None = None
    asset_class: str = "unknown"
    win_rate: float | None = None
    avg_win_loss_ratio: float | None = None
    full_kelly: float | None = None
    constrained_kelly: float | None = None
    recommended_kelly: float | None = None
    max_dd_target: float = 0.25
    is_valid: bool = True
    suggested_position_sizing: str = "kelly"
    suggested_params: dict[str, float] = Field(default_factory=lambda: {"risk_per_trade": 0.01, "kelly_fraction": 0.5})


class HedgeRecommendation(BaseModel):
    """Hedge recommendation for a single position."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    asset_class: str = "unknown"
    beta: float | None = None
    r_squared: float | None = None
    tracking_error: float | None = None
    hedge_ratio: float | None = None
    hedge_value: float | None = None
    hedge_units: float | None = None
    hedge_instrument: str | None = None
    recommendation: str = "none"
    hedge_cost_annual_pct: float | None = None
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("computed_at")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        return _ensure_utc(v)  # type: ignore[return-value]


class RiskAlert(BaseModel):
    """Alert for risk limit breaches."""

    model_config = ConfigDict(frozen=True)

    severity: Literal["info", "warning", "critical"]
    category: Literal["var", "correlation", "concentration", "leverage", "beta"]
    message: str
    symbol: str | None = None
    current_value: float | None = None
    threshold: float | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("timestamp")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        return _ensure_utc(v)  # type: ignore[return-value]


class RiskAssessment(BaseModel):
    """Complete risk assessment for a portfolio, combining all metrics."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    var_95: VaRResult | None = None
    var_99: VaRResult | None = None
    portfolio_beta: PortfolioBetaResult | None = None
    correlation: CorrelationResult | None = None
    kelly: KellyRecommendation | None = None
    hedge_recommendations: list[HedgeRecommendation] = Field(default_factory=list)
    risk_score: float | None = None
    alerts: list[RiskAlert] = Field(default_factory=list)

    @field_validator("timestamp")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        return _ensure_utc(v)  # type: ignore[return-value]
