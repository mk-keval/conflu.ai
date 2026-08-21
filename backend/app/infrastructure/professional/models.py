"""Pydantic models for Professional Mode services.

All request/response models for Morning Brief, Regime Selection,
Position Sizing, Education, and Alert services.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


# ═══════════════════════════════════════════
# Morning Brief
# ═══════════════════════════════════════════


class MorningBriefRequest(BaseModel):
    """Request to generate a morning brief — optional regime override."""
    model_config = ConfigDict(extra="forbid")

    regime: str | None = None  # auto-detect if None


class TickerBrief(BaseModel):
    """A single ticker result within a morning brief screen section."""
    model_config = ConfigDict(extra="forbid")

    symbol: str
    screen_name: str
    screen_score: float
    confluence_score: int
    entry: float
    stop_loss: float
    targets: list[float]
    verdict: str  # STRONG_BUY / BUY / WATCH / AVOID
    conviction: int  # 1-10
    live_price: float | None = None
    premarket_change_pct: float | None = None
    education_hints: dict[str, str] = {}  # metric -> plain english
    # P1.4 Catalyst-Breakout badge: recent EPS beat + rvol > 1.2 + within
    # 3% of the 52-week high. Structural parts come from TV snapshot data;
    # the EPS-beat confirmation arrives from yfinance info (already fetched
    # for premarket quotes — zero extra upstream calls).
    catalyst_breakout: bool = False
    catalyst_breakout_reason: str | None = None
    # P1.5 earnings-proximity warning chip (calendar days; negative = last
    # print in the past). None when yfinance has no scheduled date.
    days_to_earnings: int | None = None


class ScreenSection(BaseModel):
    """A screen section within the morning brief — one of the top 3 screens."""
    model_config = ConfigDict(extra="forbid")

    screen_name: str
    screen_label: str
    regime_match_score: float
    tickers: list[TickerBrief]


class MarketInternals(BaseModel):
    """Macro market internals for the morning brief header."""
    model_config = ConfigDict(extra="forbid")

    vix: float | None = None
    advance_decline_ratio: float | None = None
    dollar_index: float | None = None
    sp500_futures: float | None = None
    nasdaq_futures: float | None = None


class SectorRotationSummary(BaseModel):
    """Sector rotation context for the morning brief."""
    model_config = ConfigDict(extra="forbid")

    leading_sectors: list[str]
    lagging_sectors: list[str]
    regime_alignment: str  # "risk_on" / "risk_off" / "mixed"


class MorningBriefResponse(BaseModel):
    """Complete morning brief with regime, sectors, market internals, and screen results."""
    model_config = ConfigDict(extra="forbid")

    date: str  # ISO date
    regime: str
    regime_description: str
    market_internals: MarketInternals
    sector_rotation: SectorRotationSummary
    sectors: list[dict]  # [{symbol, name, change_pct, rs_rank}]
    screen_sections: list[ScreenSection]
    generated_at: str  # ISO datetime


# ═══════════════════════════════════════════
# Simplified Verdict
# ═══════════════════════════════════════════


class SimplifiedVerdictRequest(BaseModel):
    """Request a simplified one-click verdict for a ticker."""
    model_config = ConfigDict(extra="forbid")

    symbol: str


class SimplifiedVerdictResponse(BaseModel):
    """Simplified verdict — the essential info a working pro needs."""
    model_config = ConfigDict(extra="forbid")

    symbol: str
    action: str
    conviction: int
    verdict_summary: str
    key_metrics: dict[str, Any]
    entry_zone: str
    stop_loss: float
    targets: list[float]
    position_size: dict[str, Any] | None = None
    max_hold_days: int | None = None
    education: list[dict[str, str]] = []  # [{metric, explanation}]


# ═══════════════════════════════════════════
# Batch Watchlist
# ═══════════════════════════════════════════


class WatchlistAnalyzeRequest(BaseModel):
    """Batch analyze a list of tickers."""
    model_config = ConfigDict(extra="forbid")

    symbols: list[str]


class WatchlistItemResponse(BaseModel):
    """Individual watchlist item verdict."""
    model_config = ConfigDict(extra="forbid")

    symbol: str
    verdict: str
    conviction: int
    position_size: dict[str, float] | None = None
    # P1.5 earnings-proximity warning chip (calendar days).
    days_to_earnings: int | None = None


class WatchlistAnalyzeResponse(BaseModel):
    """Batch watchlist analysis result."""
    model_config = ConfigDict(extra="forbid")

    items: list[WatchlistItemResponse]


# ═══════════════════════════════════════════
# Education
# ═══════════════════════════════════════════


class EducationRequest(BaseModel):
    """Request an explanation for a metric."""
    model_config = ConfigDict(extra="forbid")

    metric: str
    symbol: str | None = None


class EducationResponse(BaseModel):
    """Plain-English explanation of a financial metric."""
    model_config = ConfigDict(extra="forbid")

    metric: str
    symbol: str | None = None
    plain_english: str
    value_context: str | None = None
    actionable: str | None = None
    source: str  # "template" | "llm" | "combined"
    cached: bool = False


# ═══════════════════════════════════════════
# Position Sizing
# ═══════════════════════════════════════════


class PositionSizeRequest(BaseModel):
    """Request a position size calculation."""
    model_config = ConfigDict(extra="forbid")

    symbol: str
    account_equity: float
    entry: float
    stop_loss: float
    conviction: str  # "high" | "medium" | "low"
    max_position_pct: float = 0.05
    max_sector_pct: float = 0.15
    risk_per_trade_pct: float = 0.015


class PositionSizeResponse(BaseModel):
    """Position size calculation result."""
    model_config = ConfigDict(extra="forbid")

    position_size: float  # dollar amount
    shares: int
    risk_amount: float
    risk_pct: float
    conviction_multiplier: float
    capped_by: str  # "position" | "sector" | "kelly"


# ═══════════════════════════════════════════
# Alert Preferences
# ═══════════════════════════════════════════


class AlertPreferences(BaseModel):
    """User alert notification preferences."""
    model_config = ConfigDict(extra="forbid")

    email_morning_brief: bool = True
    email_stop_hit: bool = True
    push_stop_hit: bool = True
    push_target_hit: bool = True
    email_earnings_alert: bool = True
    email_regime_change: bool = True
    email_weekly_review: bool = False
