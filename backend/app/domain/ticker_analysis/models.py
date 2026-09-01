"""Pydantic models for ticker analysis service."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


# ── Analysis Configuration ──


class TickerAnalysisRequest(BaseModel):
    """Request to analyze a single ticker."""
    model_config = ConfigDict(extra="forbid")

    symbol: str
    timeframe: str = "1D"
    # Optional TV screener row data — if provided, avoids re-fetching price data
    tv_data: dict[str, Any] | None = None
    # Optional regime to use for adaptive weighting
    regime: str | None = None


# ── Module Outputs ──


class TechnicalAnalysis(BaseModel):
    """Technical indicator regime and findings."""
    model_config = ConfigDict(extra="forbid")

    score: float  # -1.0 to 1.0
    ma_alignment: str  # bullish / bearish / mixed
    rsi: float | None = None
    rsi_regime: str  # oversold / neutral / overbought
    adx: float | None = None
    adx_verdict: str  # weak / moderate / strong / extreme
    atr_pct: float | None = None
    volatility_regime: str  # low / normal / high / extreme
    volume_ratio: float | None = None
    bb_position: str | None = None  # below_lower / inside / above_upper
    macd_status: str | None = None  # bullish / bearish / neutral
    # Market structure (new)
    structure: str | None = None  # bullish / bearish / ranging / transition
    swing_highs: list[float] | None = None
    swing_lows: list[float] | None = None
    key_resistance: list[float] | None = None
    key_support: list[float] | None = None
    pullback_quality: str | None = None  # A+ / A / B / C / D / F
    pullback_score: float | None = None  # 0-100
    findings: list[str]
    # Advanced chart reading (optional, populated when OHLCV data available)
    chart_reading: ChartReadingAnalysis | None = None


# ── Chart Reading Analysis Sub-Model ──

from typing import Literal
from dataclasses import dataclass, field


@dataclass
class TimeframeChartReading:
    """Chart reading signals for a single timeframe."""
    timeframe: str  # "daily", "weekly", "4h", "1h"
    
    # Market Structure (structure.py)
    bos_events: list[dict] = field(default_factory=list)
    choch_events: list[dict] = field(default_factory=list)
    structure_label: str | None = None
    
    # Professional Volume Profile TPO (volume_profile.py) - only for daily
    tpo_profiles: list[dict] = field(default_factory=list)
    composite_tpo_profile: dict | None = None
    
    # Smart Money Concepts (smc.py)
    order_blocks: list[dict] = field(default_factory=list)
    fair_value_gaps: list[dict] = field(default_factory=list)
    breaker_blocks: list[dict] = field(default_factory=list)
    liquidity_levels: list[dict] = field(default_factory=list)
    
    # Validated Breakouts (breakout.py)
    breakout_events: list[dict] = field(default_factory=list)
    
    # Metadata
    data_quality_warnings: list[str] = field(default_factory=list)
    timeframes_analyzed: list[str] = field(default_factory=list)


@dataclass
class ChartReadingAnalysis:
    """All advanced chart reading signals across timeframes — separated from core TechnicalAnalysis.
    
    This sub-model groups all institutional-grade chart reading signals:
    - BOS/CHoCH (structure.py)
    - Volume Profile TPO (volume_profile.py)
    - Smart Money Concepts: OB, FVG, Breakers, Liquidity (smc.py)
    - Validated Breakouts (breakout.py)
    - Multi-timeframe Confluence (mtf_confluence.py)
    
    Keeping these separate from TechnicalAnalysis prevents model bloat
    and allows optional computation (only when OHLCV data is available).
    """
    # Per-timeframe chart reading
    daily: TimeframeChartReading | None = None
    weekly: TimeframeChartReading | None = None
    h4: TimeframeChartReading | None = None
    h1: TimeframeChartReading | None = None
    
    # Multi-Timeframe Confluence (mtf_confluence.py) - combines all timeframes
    mtf_confluence: dict | None = None
    
    # Metadata
    computation_time_ms: float = 0.0
    data_quality_warnings: list[str] = field(default_factory=list)
    timeframes_analyzed: list[str] = field(default_factory=list)


class FundamentalAnalysis(BaseModel):
    """Fundamental metrics and quality assessment."""
    model_config = ConfigDict(extra="forbid")

    score: float  # -1.0 to 1.0
    instrument_type: str = "equity"  # equity / spac / etf / etn / mutual_fund / reit / preferred
    listing_exchange: str | None = None  # Raw exchange code from yfinance (NYQ, NMS, OTC, PNK, etc.)
    exchange_category: str = "unknown"  # primary / otc / foreign / unknown
    asset_category: str = "operating"  # operating / treasury_asset / holding_company / ip_royalty
    lifecycle_stage: str = "operating"  # operating / development / clinical_stage / pre_revenue / distressed / cash_shell
    market_cap: float | None = None
    pe_ratio: float | None = None
    eps: float | None = None
    profit_margin: float | None = None
    debt_to_equity: float | None = None
    revenue_growth_yoy: float | None = None
    fcf_yield: float | None = None
    dividend_yield: float | None = None
    return_on_equity: float | None = None
    price_to_book: float | None = None
    operating_margin: float | None = None
    findings: list[str]


class EarningsAnalysis(BaseModel):
    """Earnings quality and surprise history."""
    model_config = ConfigDict(extra="forbid")

    score: float  # -1.0 to 1.0
    last_surprise_pct: float | None = None
    beat_rate: str | None = None  # e.g., "3/4"
    avg_reaction_pct: float | None = None
    next_earnings_date: str | None = None
    # P1.5 earnings-proximity chip: calendar days until the next report
    # (negative when the last print is in the past).
    days_until_earnings: int | None = None
    findings: list[str]


class SentimentAnalysis(BaseModel):
    """Market sentiment and insider activity signals."""
    model_config = ConfigDict(extra="forbid")

    score: float  # -1.0 to 1.0
    analyst_consensus: str = "N/A"
    insider_status: str = "neutral"  # buying / selling / neutral
    short_interest_pct: float | None = None
    days_to_cover: float | None = None
    institutional_ownership: float | None = None
    beta: float | None = None
    target_price: float | None = None
    target_upside_pct: float | None = None
    undervalued: bool = False
    findings: list[str]


class RiskAssessment(BaseModel):
    """Risk and position sizing analysis."""
    model_config = ConfigDict(extra="forbid")

    score: float  # -1.0 to 1.0
    volatility_regime: str  # low / normal / high
    suggested_stop_pct: float
    suggested_position_size_pct: float
    max_risk_per_trade_pct: float = 1.0
    findings: list[str]


# ── Synthesis Output ──


class TradePlan(BaseModel):
    """Dynamic trade management plan — scale in/out, trail stops, breakeven rules."""
    model_config = ConfigDict(extra="forbid")

    # Scale-in plan
    scale_in: list[dict] = []  # [{"price": float, "size_pct": float, "reason": str}]
    
    # Scale-out (partial profit taking)
    scale_out: list[dict] = []  # [{"r_multiple": float, "size_pct": float, "reason": str}]
    
    # Trailing stop rules
    trail_type: str = "atr"  # "atr" / "structure" / "percent"
    trail_value: float = 2.0  # ATR multiplier or percent
    trail_activation_r: float = 1.0  # Start trailing after this R-multiple
    
    # Breakeven rules
    move_to_breakeven_at_r: float = 1.0  # Move stop to entry after this R
    
    # Time-based exit
    max_hold_days: int | None = None  # Optional time stop
    
    # Risk management
    max_position_pct: float = 10.0  # Hard cap on position size
    daily_loss_limit_pct: float = 2.0  # Stop trading if daily loss exceeds this
    
    # Notes
    notes: list[str] = []


class MentorNarration(BaseModel):
    """Deterministic veteran-style reasoning chain (P2.1).

    Template-built from module outputs and plan geometry — fast/free with
    no external calls. ``what_kills_it`` always names a concrete level +
    condition when a plan exists; a refusal without invalidation is not a
    mentor answer.
    """
    model_config = ConfigDict(extra="forbid")

    why_this: list[str] = []       # module confluences backing the setup
    why_now: list[str] = []        # catalyst / liquidity event timing
    what_kills_it: list[str] = []  # invalidation level + condition
    thesis_one_liner: str = ""     # trader-style compression of the above


class AnalysisVerdict(BaseModel):
    """Final actionable verdict synthesised from all modules."""
    model_config = ConfigDict(extra="forbid")

    action: str  # BUY / SELL / HOLD / WATCH
    conviction: int  # 1-10
    entry_zone_low: float | None = None
    entry_zone_high: float | None = None
    stop_loss: float | None = None
    targets: list[float] = []
    risk_reward: float | None = None
    position_size_pct: float = 0
    # Critical issues that override/downgrade the action (distinct from
    # advisory red flags so the UI can render them as blocking conditions).
    dealbreakers: list[str] = []
    key_red_flags: list[str] = []
    buy_triggers: list[str] = []
    sell_triggers: list[str] = []
    thesis: str = ""
    # Dynamic trade management (new)
    trade_plan: TradePlan | None = None
    # P2.1 mentor reasoning chain (additive)
    narration: MentorNarration | None = None
    # D-44: earnings binary risk (G14). True if ticker reports earnings in the
    # next 5 trading days. Conviction is capped at 5 by synthesis when this is set.
    binary_risk: bool = False
    # D-44: ISO date of the imminent earnings event (when binary_risk=True).
    earnings_date: str | None = None


class MultiTimeframeTechnical(BaseModel):
    """Multi-timeframe technical payload.

    Emitted when the technical module ran with include_weekly=True: the daily
    object stays the canonical score source, weekly rides alongside so the
    frontend can render true multi-timeframe columns.
    """
    model_config = ConfigDict(extra="forbid")

    daily: TechnicalAnalysis
    weekly: TechnicalAnalysis | None = None


class TickerAnalysisResponse(BaseModel):
    """Complete ticker analysis response combining all dimensions."""
    model_config = ConfigDict(extra="forbid")

    symbol: str
    price: float | None = None
    change_pct: float | None = None
    sector: str | None = None
    # Flat daily-only (legacy / short-circuit paths) or multi-timeframe payload
    technical: TechnicalAnalysis | MultiTimeframeTechnical | None = None
    fundamental: FundamentalAnalysis | None = None
    earnings: EarningsAnalysis | None = None
    sentiment: SentimentAnalysis | None = None
    risk: RiskAssessment | None = None
    verdict: AnalysisVerdict
    execution_ms: int
    analysis_timestamp: str | None = None
    data_age_hours: float | None = None
    # Data source attribution
    data_sources: dict[str, str] | None = None
    # D-44: human-readable staleness message. Set when data_age_hours exceeds
    # the threshold (36h weekday / 24h weekend). NULL when data is fresh.
    stale_warning: str | None = None
    # D-44: list of data quality issues (e.g. "Only 125 daily bars, need 200+ for SMA200").
    # Empty list when the data is sufficient for all computations.
    data_quality_warnings: list[str] = []
    # D-46: macro context (VIX, SPY/QQQ close, leading/lagging sectors, risk regime).
    # What the elite trader holds in their head when sizing any trade.
    # None if the lightweight fetch failed (the verdict still works without it).
    macro_context: dict[str, Any] | None = None
    # D-46 PR 5: unusual options activity (call/put volume ratio, vol/OI ratio).
    # Smart money leaving a footprint in the options market — the elite trader
    # watches for this to confirm a thesis.
    options_flow: dict[str, Any] | None = None
