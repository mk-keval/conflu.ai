"""Domain models for the trading platform.

All models are frozen (immutable) and forbid extra fields.
Timestamps are UTC-aware datetime objects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OHLCV(BaseModel):
    """Raw OHLCV price data point."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str
    asset_class: str

    @field_validator("timestamp")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return v.astimezone(timezone.utc)


class Signal(BaseModel):
    """Trading signal (buy/sell/hold)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    timestamp: datetime
    direction: Literal["buy", "sell", "hold"]
    strength: float = Field(default=1.0, ge=0.0, le=1.0)
    source: str = Field(default="", description="Indicator or strategy that generated this signal")

    @field_validator("timestamp")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return v.astimezone(timezone.utc)


class Position(BaseModel):
    """A tracked position from entry to exit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    entry_time: datetime
    exit_time: datetime | None = None
    entry_price: float
    exit_price: float | None = None
    size: float
    pnl: float | None = None

    @field_validator("entry_time", "exit_time")
    @classmethod
    def ensure_utc(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return v.astimezone(timezone.utc) if v is not None else None


class Trade(BaseModel):
    """Full trade record with performance metrics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    entry_time: datetime
    exit_time: datetime | None = None
    entry_price: float
    exit_price: float | None = None
    size: float
    fees: float = 0.0
    pnl: float | None = None
    mae: float | None = None  # Maximum Adverse Excursion
    mfe: float | None = None  # Maximum Favorable Excursion
    hold_duration_bars: int | None = None  # Number of bars the trade was held
    exit_reason: str | None = None  # Reason for exit (e.g., 'stop_loss', 'take_profit', 'signal_close')

    @field_validator("entry_time", "exit_time")
    @classmethod
    def ensure_utc(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return v.astimezone(timezone.utc) if v is not None else None


class Metrics(BaseModel):
    """Portfolio/strategy performance metrics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sharpe: float | None = None
    sortino: float | None = None
    calmar: float | None = None
    max_dd: float | None = None  # Maximum drawdown as decimal (e.g., 0.25 = 25%)
    win_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    expectancy: float | None = None
    profit_factor: float | None = None
    sqn: float | None = None  # System Quality Number
    ulcer: float | None = None  # Ulcer Index
    cagr: float | None = None  # Compound Annual Growth Rate


class ScreenResult(BaseModel):
    """Single row from a screener output."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    score: float = Field(default=0.0, ge=0.0, le=100.0)
    signals: list[Signal] = Field(default_factory=list)
    indicators: dict[str, float] = Field(default_factory=dict)
    matched_filters: list[str] = Field(default_factory=list)
    indicator_values: dict[str, float] = Field(default_factory=dict)
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return v.astimezone(timezone.utc)


class BacktestConfig(BaseModel):
    """Configuration for running a backtest simulation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbols: list[str]
    start: datetime
    end: datetime
    initial_cash: float = Field(default=100_000.0, gt=0)
    fees: float = Field(default=0.001, ge=0.0)  # 0.1% fees
    slippage: float = Field(default=0.001, ge=0.0)  # 0.1% slippage
    position_sizing: Literal["fixed", "atr", "kelly"] = "fixed"
    strategy_params: dict[str, object] = Field(default_factory=dict)

    @field_validator("start", "end")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return v.astimezone(timezone.utc)


class RiskParams(BaseModel):
    """Risk management parameters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    risk_per_trade: float = Field(default=0.01, ge=0.001, le=0.1)  # 1% risk per trade
    max_position_size: float = Field(default=0.25, ge=0.01, le=1.0)  # 25% max allocation
    atr_period: int = Field(default=14, ge=2)
    beta_benchmark: str = Field(default="SPY", description="Benchmark symbol for beta calculation")
    kelly_fraction: float = Field(default=0.5, ge=0.0, le=1.0)  # Half-Kelly default

    # Phase 5 Risk Management extensions
    var_confidence: float = Field(default=0.95, ge=0.8, le=0.999, description="VaR confidence level")
    var_horizon_days: int = Field(default=1, ge=1, le=252, description="VaR time horizon in days")
    var_method: str = Field(default="historical", description="Default VaR method: historical, parametric, monte_carlo")
    max_var_pct: float = Field(default=0.05, ge=0.01, le=1.0, description="Max VaR as fraction of portfolio (5%)")
    max_leverage: float = Field(default=1.0, ge=1.0, le=10.0, description="Max leverage ratio")
    max_correlation: float = Field(default=0.85, ge=0.5, le=1.0, description="Max allowed pairwise correlation")
    hedge_min_effectiveness: float = Field(default=0.5, ge=0.0, le=1.0, description="Min R² for hedge recommendation")
