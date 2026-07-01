# TV Screener Models — Pydantic models for TV Screener API
"""
Request/Response models for TV Screener endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


@dataclass
class TVDiscoveryResult:
    """Result from TradingView Screener discovery phase."""
    screen_name: str
    total_matches: int
    tickers: list[str]
    execution_ms: int
    raw_data: Any  # pd.DataFrame with all TV columns
    timeframe: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ScoredTicker:
    """Ticker with confluence score from TV data."""
    symbol: str
    tv_data: dict[str, Any]
    confluence: 'ConfluenceScore'


@dataclass
class ConfluenceScore:
    total: int
    breakdown: dict[str, int]
    entry: float
    stop_loss: float
    targets: list[float]
    risk_reward: float
    rating: str


# =========================================================================
# Pydantic Models for API
# =========================================================================

class TVScreenRequest(BaseModel):
    """Request for TV Screener discovery.
    
    `config` can be a dict (inline ScreenConfig) or a string (template name).
    """
    model_config = ConfigDict(extra="forbid")

    config: dict[str, Any] | str
    limit: int = Field(default=500, ge=1, le=2000)
    multi_timeframe: bool = False


class ScoredTickerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    score: int
    breakdown: dict[str, int]
    entry: float
    stop_loss: float
    targets: list[float]
    risk_reward: float
    rating: str
    tv_data: dict[str, Any]


class TVScreenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    screen_name: str
    total_matches: int
    execution_ms: int
    timeframe: str
    results: list[ScoredTickerResponse]


class DeepAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    timeframe: str = "1D"
    include_backtest: bool = True
    include_risk: bool = True
    tv_data: dict[str, Any] | None = None  # Fallback data from TV screener row


class DeepAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    timeframe: str
    tv_discovery: dict[str, Any]
    confluence: Optional[dict[str, Any]] = None
    backtest: Optional[dict[str, Any]] = None
    risk: Optional[dict[str, Any]] = None
    execution_ms: int


# =========================================================================
# Helpers
# =========================================================================

def dict_to_screen_config(data: dict[str, Any]) -> Any:
    """Convert API request dict to ScreenConfig.

    Lazy-imports configs to avoid pulling in FastAPI dependencies at import time.
    """
    from backend.app.infrastructure.screener.configs import FilterRule, ScreenConfig, UniverseConfig

    filters = []
    for flt in data.get("filters", []):
        filters.append(FilterRule(
            category=flt.get("category", ""),
            indicator=flt.get("indicator", ""),
            params=flt.get("params", {}),
            operator=flt.get("operator", "gt"),
            timeframe=flt.get("timeframe", "1D"),
            negate=flt.get("negate", False),
            compare_timeframe=flt.get("compare_timeframe"),
        ))

    universe_data = data.get("universe")
    if universe_data:
        universe = UniverseConfig(**universe_data)
    else:
        universe = UniverseConfig()

    return ScreenConfig(
        name=data.get("name", "Custom Screen"),
        description=data.get("description", ""),
        asset_classes=data.get("asset_classes", ["equities"]),
        timeframes=data.get("timeframes", ["1D"]),
        filters=filters,
        universe=universe,
        limit=data.get("limit", 500),
    )