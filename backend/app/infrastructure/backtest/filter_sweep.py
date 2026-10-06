"""Filter Sweep Configuration — defines parameter space for filter sweeps.

This module defines the parameter space for sweeping filter configurations
to find optimal filter combinations via backtesting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class FilterParamRange(BaseModel):
    """Defines a parameter range for sweeping."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    display_name: str
    param_type: Literal["int", "float", "categorical"]
    low: float | int | None = None
    high: float | int | None = None
    step: float | int | None = None
    choices: list[str] | None = None
    description: str = ""


class FilterSweepConfig(BaseModel):
    """Configuration for a filter parameter sweep."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Sweep identification
    sweep_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""

    # Screen configuration
    screen_name: str  # e.g., "trend-follower", "high-conviction-stack"

    # Parameter grid to sweep
    param_grid: dict[str, FilterParamRange] = Field(default_factory=dict)

    # Backtest configuration
    symbols: list[str] = Field(default_factory=lambda: ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"])
    timeframe: str = "1D"
    start_date: str  # YYYY-MM-DD
    end_date: str | None = None
    initial_cash: float = 100_000.0
    fees_bps: float = 10.0
    slippage_bps: float = 5.0
    position_sizing: Literal["fixed", "atr", "kelly"] = "fixed"
    sizing_params: dict[str, Any] = Field(default_factory=dict)

    # Optimization settings
    optimization_metric: Literal["sharpe", "sortino", "calmar", "win_rate", "profit_factor", "expectancy"] = "expectancy"
    min_trades: int = 10  # Minimum trades for valid result

    # Execution settings
    max_combinations: int = 5000  # Safety limit
    parallel_jobs: int = 1

    # Metadata
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    tags: list[str] = Field(default_factory=list)


class FilterSweepResult(BaseModel):
    """Results from a single filter parameter combination backtest."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    # Parameter combination
    params: dict[str, Any]

    # Backtest metrics
    total_return: float | None = None
    annualized_return: float | None = None
    sharpe: float | None = None
    sortino: float | None = None
    calmar: float | None = None
    max_drawdown: float | None = None
    win_rate: float | None = None
    profit_factor: float | None = None
    expectancy: float | None = None  # (win_rate * avg_win) - ((1-win_rate) * avg_loss)
    avg_win: float | None = None
    avg_loss: float | None = None
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_hold_days: float | None = None
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    max_drawdown_pct: float | None = None
    recovery_factor: float | None = None
    payoff_ratio: float | None = None

    # Trade distribution
    avg_hold_days: float | None = None
    best_trade: float | None = None
    worst_trade: float | None = None

    # Metadata
    run_id: str = ""
    config_hash: str = ""
    valid: bool = True  # False if below min_trades or other validation failed
    error_message: str | None = None
    duration_ms: float = 0.0


class FilterSweepSummary(BaseModel):
    """Summary of a completed filter sweep."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    sweep_id: str
    name: str
    screen_name: str
    total_combinations: int
    valid_results: int
    failed_results: int

    # Best results by different metrics
    best_by_sharpe: dict[str, Any] | None = None
    best_by_expectancy: dict[str, Any] | None = None
    best_by_win_rate: dict[str, Any] | None = None
    best_by_profit_factor: dict[str, Any] | None = None
    best_by_calmar: dict[str, Any] | None = None

    # Parameter sensitivity (how much each param affects metric)
    param_sensitivity: dict[str, dict[str, float]] = Field(default_factory=dict)

    # All results (can be large)
    all_results: list[dict[str, Any]] = Field(default_factory=list)

    # Metadata
    sweep_config: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    duration_ms: float = 0.0

    # Status
    status: Literal["running", "completed", "failed"] = "completed"
    error_message: str | None = None


# Pre-defined parameter ranges for common filters
# These match the actual TV screener FILTER_MAP indicator names
DEFAULT_FILTER_PARAM_RANGES: dict[str, FilterParamRange] = {
    "market_cap_gt": FilterParamRange(
        name="market_cap_gt",
        display_name="Market Cap Min ($)",
        param_type="int",
        low=500_000_000,
        high=10_000_000_000,
        step=500_000_000,
        description="Minimum market cap for institutional quality.",
    ),
    "avg_volume_gt": FilterParamRange(
        name="avg_volume_gt",
        display_name="Min Avg Daily Volume",
        param_type="int",
        low=500_000,
        high=5_000_000,
        step=500_000,
        description="Minimum average daily volume (shares).",
    ),
    "rvol_high": FilterParamRange(
        name="rvol_high",
        display_name="Relative Volume Min",
        param_type="float",
        low=1.0,
        high=2.5,
        step=0.2,
        description="Minimum relative volume vs 10-day average.",
    ),
    "close_above": FilterParamRange(
        name="close_above",
        display_name="Min Price",
        param_type="float",
        low=5.0,
        high=50.0,
        step=5.0,
        description="Minimum stock price.",
    ),
    "pe_max": FilterParamRange(
        name="pe_max",
        display_name="Max P/E Ratio",
        param_type="int",
        low=20,
        high=80,
        step=10,
        description="Maximum P/E ratio (avoid overvalued).",
    ),
    "adx_trending": FilterParamRange(
        name="adx_trending",
        display_name="ADX Threshold",
        param_type="int",
        low=15,
        high=35,
        step=5,
        description="Minimum ADX for trending strength.",
    ),
    "rsi_in_range": FilterParamRange(
        name="rsi_in_range",
        display_name="RSI Range Min",
        param_type="int",
        low=40,
        high=60,
        step=5,
        description="Minimum RSI for momentum range.",
    ),
    "rsi_in_range_max": FilterParamRange(
        name="rsi_in_range_max",
        display_name="RSI Range Max",
        param_type="int",
        low=70,
        high=90,
        step=5,
        description="Maximum RSI for momentum range.",
    ),
    "rsi_oversold": FilterParamRange(
        name="rsi_oversold",
        display_name="RSI Oversold Threshold",
        param_type="int",
        low=25,
        high=40,
        step=5,
        description="RSI threshold for oversold mean reversion.",
    ),
    "cci_oversold": FilterParamRange(
        name="cci_oversold",
        display_name="CCI Oversold Threshold",
        param_type="int",
        low=-150,
        high=-50,
        step=25,
        description="CCI threshold for oversold mean reversion.",
    ),
    "atr_pct_below": FilterParamRange(
        name="atr_pct_below",
        display_name="ATR% Max",
        param_type="float",
        low=0.02,
        high=0.08,
        step=0.01,
        description="Maximum ATR as % of price (volatility filter).",
    ),
    "price_above_ema": FilterParamRange(
        name="price_above_ema",
        display_name="EMA Period",
        param_type="categorical",
        choices=["20", "50", "200"],
        description="EMA period for price above MA filter.",
    ),
    "bb_squeeze": FilterParamRange(
        name="bb_squeeze",
        display_name="BB Squeeze Threshold",
        param_type="float",
        low=1.03,
        high=1.15,
        step=0.02,
        description="BB width threshold for squeeze detection.",
    ),
    "volume_gt": FilterParamRange(
        name="volume_gt",
        display_name="Min Current Volume",
        param_type="int",
        low=500_000,
        high=5_000_000,
        step=500_000,
        description="Minimum current volume (shares).",
    ),
    "rs_rank_min": FilterParamRange(
        name="rs_rank_min",
        display_name="RS Rank Min",
        param_type="int",
        low=90,
        high=98,
        step=2,
        description="Minimum relative strength rank (top 4% = 96).",
    ),
    "price_near_52w_high": FilterParamRange(
        name="price_near_52w_high",
        display_name="52w High Proximity",
        param_type="int",
        low=3,
        high=10,
        step=1,
        description="Within X% of 52-week high (VCP: ≤5%).",
    ),
    "price_above_52w_low": FilterParamRange(
        name="price_above_52w_low",
        display_name="Above 52w Low %",
        param_type="int",
        low=20,
        high=50,
        step=5,
        description="Percentage above 52-week low (VCP: ≥30%).",
    ),
    "price_near_ema": FilterParamRange(
        name="price_near_ema",
        display_name="EMA Proximity %",
        param_type="int",
        low=1,
        high=5,
        step=1,
        description="Within X% of EMA for pullback entry.",
    ),
    "price_above_52w_low": FilterParamRange(
        name="price_above_52w_low",
        display_name="Above 52w Low %",
        param_type="int",
        low=20,
        high=50,
        step=5,
        description="Percentage above 52-week low (VCP: ≥30%).",
    ),
    "price_near_ema": FilterParamRange(
        name="price_near_ema",
        display_name="EMA Proximity %",
        param_type="int",
        low=1,
        high=5,
        step=1,
        description="Within X% of EMA for pullback entry.",
    ),
}


# Pre-built sweep configurations for common use cases
# Each sweep uses parameter names that match the actual filter indicators in the screen template
PRESET_SWEEPS: dict[str, FilterSweepConfig] = {
    "trend_follower_optimization": FilterSweepConfig(
        name="Trend Follower Optimization",
        description="Optimize trend follower screen parameters for max expectancy",
        screen_name="trend-follower",
        param_grid={
            "market_cap_gt": DEFAULT_FILTER_PARAM_RANGES["market_cap_gt"],
            "avg_volume_gt": DEFAULT_FILTER_PARAM_RANGES["avg_volume_gt"],
            "rvol_high": DEFAULT_FILTER_PARAM_RANGES["rvol_high"],
            "close_above": DEFAULT_FILTER_PARAM_RANGES["close_above"],
            "adx_trending": DEFAULT_FILTER_PARAM_RANGES["adx_trending"],
            "price_above_ema": DEFAULT_FILTER_PARAM_RANGES["price_above_ema"],
        },
        symbols=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"],
        timeframe="1D",
        start_date="2025-07-01",
        end_date="2026-06-01",
        optimization_metric="expectancy",
        max_combinations=20,
    ),
    "high_conviction_optimization": FilterSweepConfig(
        name="High Conviction Stack Optimization",
        description="Optimize high conviction stack parameters",
        screen_name="high-conviction-stack",
        param_grid={
            "market_cap_gt": DEFAULT_FILTER_PARAM_RANGES["market_cap_gt"],
            "avg_volume_gt": DEFAULT_FILTER_PARAM_RANGES["avg_volume_gt"],
            "close_above": DEFAULT_FILTER_PARAM_RANGES["close_above"],
            "pe_max": DEFAULT_FILTER_PARAM_RANGES["pe_max"],
            "rsi_in_range": DEFAULT_FILTER_PARAM_RANGES["rsi_in_range"],
            "rsi_in_range_max": DEFAULT_FILTER_PARAM_RANGES["rsi_in_range_max"],
            "rvol_high": DEFAULT_FILTER_PARAM_RANGES["rvol_high"],
            "adx_trending": DEFAULT_FILTER_PARAM_RANGES["adx_trending"],
        },
        symbols=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "ORCL", "CRM"],
        timeframe="1D",
        start_date="2022-01-01",
        end_date="2024-01-01",
        optimization_metric="expectancy",
        max_combinations=2000,
    ),
    "breakout_optimization": FilterSweepConfig(
        name="Breakout Optimization",
        description="Optimize breakout screen parameters",
        screen_name="bull-flag-continuation",
        param_grid={
            "market_cap_gt": DEFAULT_FILTER_PARAM_RANGES["market_cap_gt"],
            "avg_volume_gt": DEFAULT_FILTER_PARAM_RANGES["avg_volume_gt"],
            "close_above": DEFAULT_FILTER_PARAM_RANGES["close_above"],
            "price_above_ema": DEFAULT_FILTER_PARAM_RANGES["price_above_ema"],
            "macd_bullish": DEFAULT_FILTER_PARAM_RANGES["rsi_in_range"],  # boolean - no params
            "rvol_high": DEFAULT_FILTER_PARAM_RANGES["rvol_high"],
            "bb_squeeze": DEFAULT_FILTER_PARAM_RANGES["bb_squeeze"],
            "adx_trending": DEFAULT_FILTER_PARAM_RANGES["adx_trending"],
            "volume_gt": DEFAULT_FILTER_PARAM_RANGES["volume_gt"],
        },
        symbols=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "ORCL", "CRM"],
        timeframe="1D",
        start_date="2022-01-01",
        end_date="2024-01-01",
        optimization_metric="expectancy",
        max_combinations=2000,
    ),
    "pullback_optimization": FilterSweepConfig(
        name="Pullback Optimization",
        description="Optimize pullback/mean reversion screen parameters",
        screen_name="statistical-mean-reversion",
        param_grid={
            "market_cap_gt": DEFAULT_FILTER_PARAM_RANGES["market_cap_gt"],
            "avg_volume_gt": DEFAULT_FILTER_PARAM_RANGES["avg_volume_gt"],
            "close_above": DEFAULT_FILTER_PARAM_RANGES["close_above"],
            "rsi_oversold": DEFAULT_FILTER_PARAM_RANGES["rsi_oversold"],
            "cci_oversold": DEFAULT_FILTER_PARAM_RANGES["cci_oversold"],
            "atr_pct_below": DEFAULT_FILTER_PARAM_RANGES["atr_pct_below"],
            "rvol_high": DEFAULT_FILTER_PARAM_RANGES["rvol_high"],
        },
        symbols=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "ORCL", "CRM"],
        timeframe="1D",
        start_date="2022-01-01",
        end_date="2024-01-01",
        optimization_metric="expectancy",
        max_combinations=2000,
    ),
    "institutional_quality_optimization": FilterSweepConfig(
        name="Institutional Quality Optimization",
        description="Optimize institutional quality screen parameters",
        screen_name="institutional-swing-quality",
        param_grid={
            "market_cap_gt": DEFAULT_FILTER_PARAM_RANGES["market_cap_gt"],
            "avg_volume_gt": DEFAULT_FILTER_PARAM_RANGES["avg_volume_gt"],
            "close_above": DEFAULT_FILTER_PARAM_RANGES["close_above"],
            "pe_max": DEFAULT_FILTER_PARAM_RANGES["pe_max"],
            "rsi_in_range": DEFAULT_FILTER_PARAM_RANGES["rsi_in_range"],
            "rsi_in_range_max": DEFAULT_FILTER_PARAM_RANGES["rsi_in_range_max"],
            "rvol_high": DEFAULT_FILTER_PARAM_RANGES["rvol_high"],
            "adx_trending": DEFAULT_FILTER_PARAM_RANGES["adx_trending"],
        },
        symbols=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "ORCL", "CRM"],
        timeframe="1D",
        start_date="2022-01-01",
        end_date="2024-01-01",
        optimization_metric="expectancy",
        max_combinations=2000,
    ),
    "vcp_breakout_optimization": FilterSweepConfig(
        name="VCP Breakout Optimization",
        description="Optimize VCP breakout screen parameters (Minervini) — highest profit factor (4.5)",
        screen_name="vcp-breakout",
        param_grid={
            "market_cap_gt": DEFAULT_FILTER_PARAM_RANGES["market_cap_gt"],
            "avg_volume_gt": DEFAULT_FILTER_PARAM_RANGES["avg_volume_gt"],
            "rvol_high": DEFAULT_FILTER_PARAM_RANGES["rvol_high"],
            "close_above": DEFAULT_FILTER_PARAM_RANGES["close_above"],
            "adx_trending": DEFAULT_FILTER_PARAM_RANGES["adx_trending"],
            "price_above_ema": DEFAULT_FILTER_PARAM_RANGES["price_above_ema"],
            "price_near_52w_high": FilterParamRange(
                name="price_near_52w_high",
                display_name="52w High Proximity",
                param_type="int",
                low=3,
                high=10,
                step=1,
                description="Within X% of 52-week high",
            ),
            "price_above_52w_low": FilterParamRange(
                name="price_above_52w_low",
                display_name="Above 52w Low %",
                param_type="int",
                low=20,
                high=50,
                step=5,
                description="Percentage above 52-week low",
            ),
        },
        symbols=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"],
        timeframe="1D",
        start_date="2022-01-01",
        end_date="2024-01-01",
        optimization_metric="expectancy",
        max_combinations=2000,
    ),
    "trend_follower_v2_optimization": FilterSweepConfig(
        name="Trend Follower V2 Optimization",
        description="Optimize VCP-enhanced trend follower with RS≥96 and 52w-high proximity",
        screen_name="trend-follower-v2",
        param_grid={
            "market_cap_gt": DEFAULT_FILTER_PARAM_RANGES["market_cap_gt"],
            "avg_volume_gt": DEFAULT_FILTER_PARAM_RANGES["avg_volume_gt"],
            "rvol_high": DEFAULT_FILTER_PARAM_RANGES["rvol_high"],
            "close_above": DEFAULT_FILTER_PARAM_RANGES["close_above"],
            "adx_trending": DEFAULT_FILTER_PARAM_RANGES["adx_trending"],
            "price_above_ema": DEFAULT_FILTER_PARAM_RANGES["price_above_ema"],
            "rs_rank_min": FilterParamRange(
                name="rs_rank_min",
                display_name="RS Rank Min",
                param_type="int",
                low=90,
                high=98,
                step=2,
                description="Minimum relative strength rank",
            ),
            "price_near_52w_high": FilterParamRange(
                name="price_near_52w_high",
                display_name="52w High Proximity",
                param_type="int",
                low=3,
                high=10,
                step=1,
                description="Within X% of 52-week high",
            ),
        },
        symbols=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"],
        timeframe="1D",
        start_date="2022-01-01",
        end_date="2024-01-01",
        optimization_metric="expectancy",
        max_combinations=2000,
    ),
    "trend_pullback_v2_optimization": FilterSweepConfig(
        name="Trend Pullback V2 Optimization",
        description="Optimize Connors-style pullback with strict RS gate",
        screen_name="trend-pullback-v2",
        param_grid={
            "market_cap_gt": DEFAULT_FILTER_PARAM_RANGES["market_cap_gt"],
            "avg_volume_gt": DEFAULT_FILTER_PARAM_RANGES["avg_volume_gt"],
            "close_above": DEFAULT_FILTER_PARAM_RANGES["close_above"],
            "adx_trending": DEFAULT_FILTER_PARAM_RANGES["adx_trending"],
            "price_near_ema": FilterParamRange(
                name="price_near_ema",
                display_name="EMA20 Proximity %",
                param_type="int",
                low=1,
                high=5,
                step=1,
                description="Within X% of EMA20",
            ),
            "rs_rank_min": FilterParamRange(
                name="rs_rank_min",
                display_name="RS Rank Min",
                param_type="int",
                low=90,
                high=98,
                step=2,
                description="Minimum relative strength rank",
            ),
        },
        symbols=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"],
        timeframe="1D",
        start_date="2022-01-01",
        end_date="2024-01-01",
        optimization_metric="expectancy",
        max_combinations=2000,
    ),
    "rsi2_reversion_optimization": FilterSweepConfig(
        name="RSI(2) Reversion Optimization",
        description="Optimize Connors RSI(2) mean reversion setup",
        screen_name="rsi2-reversion",
        param_grid={
            "market_cap_gt": DEFAULT_FILTER_PARAM_RANGES["market_cap_gt"],
            "avg_volume_gt": DEFAULT_FILTER_PARAM_RANGES["avg_volume_gt"],
            "close_above": DEFAULT_FILTER_PARAM_RANGES["close_above"],
            "rsi_oversold": FilterParamRange(
                name="rsi_oversold",
                display_name="RSI(2) Oversold",
                param_type="int",
                low=5,
                high=15,
                step=2,
                description="RSI(2) oversold threshold",
            ),
        },
        symbols=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"],
        timeframe="1D",
        start_date="2022-01-01",
        end_date="2024-01-01",
        optimization_metric="expectancy",
        max_combinations=2000,
    ),
    "institutional_quality_v2_optimization": FilterSweepConfig(
        name="Institutional Quality v2 Optimization",
        description="Optimize MR Swing-inspired regime-aware quality swing trade",
        screen_name="institutional-quality-v2",
        param_grid={
            "market_cap_gt": DEFAULT_FILTER_PARAM_RANGES["market_cap_gt"],
            "avg_volume_gt": DEFAULT_FILTER_PARAM_RANGES["avg_volume_gt"],
            "close_above": DEFAULT_FILTER_PARAM_RANGES["close_above"],
            "pe_max": DEFAULT_FILTER_PARAM_RANGES["pe_max"],
            "rsi_in_range": DEFAULT_FILTER_PARAM_RANGES["rsi_in_range"],
            "rsi_in_range_max": DEFAULT_FILTER_PARAM_RANGES["rsi_in_range_max"],
            "rvol_high": DEFAULT_FILTER_PARAM_RANGES["rvol_high"],
            "adx_trending": DEFAULT_FILTER_PARAM_RANGES["adx_trending"],
            "price_above_ema": DEFAULT_FILTER_PARAM_RANGES["price_above_ema"],
        },
        symbols=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "ORCL", "CRM"],
        timeframe="1D",
        start_date="2022-01-01",
        end_date="2024-01-01",
        optimization_metric="expectancy",
        max_combinations=2000,
    ),
}