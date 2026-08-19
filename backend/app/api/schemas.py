"""API Pydantic schemas for request/response models.

All request models use extra="forbid" to reject unknown fields.
All models prefer frozen=True for immutability.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


# ── Response Envelope Models ──


class MetaInfo(BaseModel):
    """Metadata attached to every API response."""

    model_config = ConfigDict(frozen=True)

    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    request_id: str = ""
    duration_ms: float | None = None


class ApiResponse(BaseModel, Generic[T]):
    """Standard API response envelope.

    All successful responses use this structure.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: T
    meta: MetaInfo


class ErrorDetail(BaseModel):
    """Machine-readable error details."""

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    details: dict[str, Any] | None = None
    request_id: str | None = None


class ApiErrorResponse(BaseModel):
    """Standard error response envelope.

    Per D-19: {error: {code, message, details}}
    """

    model_config = ConfigDict(frozen=True)

    error: ErrorDetail


# ── Screener Schemas ──


class FilterRuleRequest(BaseModel):
    """A single filter rule in a custom screen configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: str
    indicator: str
    params: dict[str, Any] = Field(default_factory=dict)
    operator: Literal["gt", "lt", "eq", "crosses_above", "crosses_below"] = "gt"
    timeframe: str = "1D"
    negate: bool = False
    compare_timeframe: str | None = None


class CustomScreenConfig(BaseModel):
    """Custom screen configuration (alternative to predefined template)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = "Custom Screen"
    description: str = ""
    asset_classes: list[str] = Field(default_factory=lambda: ["equities", "crypto"])
    timeframes: list[str] = Field(default_factory=lambda: ["1D", "4h"])
    filters: list[FilterRuleRequest] = Field(default_factory=list)


class ScreenRequest(BaseModel):
    """POST /api/v1/screen request body.

    Can specify either a predefined template name (config: str)
    or a full custom configuration (config: CustomScreenConfig).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    config: str | CustomScreenConfig
    symbols: list[str] | None = None
    timeframes: list[str] | None = None
    export_format: Literal["json", "csv"] | None = None


class ScreenSymbolResult(BaseModel):
    """Single symbol result from a screen run."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    score: float
    matched_filters: list[str] = Field(default_factory=list)
    indicator_values: dict[str, float] = Field(default_factory=dict)


# ── Backtest Schemas ──


class BacktestRequest(BaseModel):
    """POST /api/v1/backtest request body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbols: list[str]
    start: datetime
    end: datetime
    initial_cash: float = 100_000.0
    fees_bps: float = 10.0
    slippage_bps: float = 5.0
    position_sizing: Literal["fixed", "atr", "kelly"] = "fixed"
    sizing_params: dict[str, Any] = Field(default_factory=dict)
    signal_params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("start", "end")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return v.astimezone(UTC)


class BacktestResultData(BaseModel):
    """Backtest result summary."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    symbol: str
    timeframe: str
    metrics: Any | None = None
    trades_count: int = 0
    duration_ms: float = 0.0


# ── Phase 9: Advanced Backtest Schemas ──


class OptimizeRequest(BaseModel):
    """POST /api/v1/backtest/optimize-v2 request body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbols: list[str]
    start: datetime
    end: datetime
    initial_cash: float = 100_000.0
    fees_bps: float = 10.0
    slippage_bps: float = 5.0
    position_sizing: Literal["fixed", "atr", "kelly"] = "fixed"
    sizing_params: dict[str, Any] = Field(default_factory=dict)
    signal_params: dict[str, Any] = Field(default_factory=dict)
    method: Literal["grid", "random", "bayesian"] = "bayesian"
    grid_params: dict[str, list[Any]] = Field(default_factory=dict)
    param_distributions: dict[str, dict[str, Any]] = Field(default_factory=dict)
    objectives: list[str] = Field(default_factory=lambda: ["sharpe"])
    max_trials: int = Field(default=100, ge=1, le=100_000)
    timeout_s: int | None = Field(default=None, ge=10)
    n_jobs: int = Field(default=1, ge=1, le=32)
    early_stopping: bool = True

    @field_validator("start", "end")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return v.astimezone(UTC)


class OptimizeResponse(BaseModel):
    """Optimize-v2 response."""

    model_config = ConfigDict(frozen=True)

    study_id: str
    symbol: str
    method: str
    best_params: dict[str, Any]
    best_objectives: dict[str, float | None]
    n_trials: int
    duration_ms: float
    param_importance: dict[str, float]


class RegimeRequest(BaseModel):
    """POST /api/v1/backtest/regimes request body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbols: list[str]
    start: datetime
    end: datetime
    method: Literal["hmm", "volatility_quantile"] = "hmm"
    n_states: int = Field(default=3, ge=2, le=4)
    window_days: int = Field(default=252, ge=63, le=1260)

    @field_validator("start", "end")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return v.astimezone(UTC)


class ReportRequest(BaseModel):
    """POST /api/v1/backtest/{run_id}/report request body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    formats: list[Literal["html", "pdf", "json"]] = Field(default_factory=lambda: ["html"])
    template: str = "backtest_report.html"
    include_equity_curve: bool = True
    include_drawdown: bool = True
    include_trade_analysis: bool = True
    include_regime_analysis: bool = False
    include_parameter_sensitivity: bool = True


class ReportResponse(BaseModel):
    """Report response with download URLs."""

    model_config = ConfigDict(frozen=True)

    report_id: str
    formats: list[dict[str, str]] = Field(default_factory=list)
    size_bytes: int = 0
    created_at: str = ""


class CompareRequest(BaseModel):
    """POST /api/v1/backtest/compare request body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_ids: list[str] = Field(min_length=2, max_length=50)
    labels: list[str] | None = Field(default=None, max_length=50)
    include_significance: bool = True
    bootstrap_samples: int = Field(default=1000, ge=100, le=10_000)


# ── Data/Indicator Schemas ──


class IndicatorQueryParams(BaseModel):
    """Query params for GET /api/v1/indicators/{symbol}."""

    model_config = ConfigDict(frozen=True)

    timeframe: str = "1D"
    indicators: str | None = None  # Comma-separated: "rsi,macd,ema"
    limit: int = 200


class OHLCVQueryParams(BaseModel):
    """Query params for GET /api/v1/data/{symbol}."""

    model_config = ConfigDict(frozen=True)

    timeframe: str = "1D"
    start: datetime | None = None
    end: datetime | None = None
    limit: int = 500


# ── Risk Schemas ──


class RiskVarRequest(BaseModel):
    """Query params for GET /api/v1/risk/var."""

    model_config = ConfigDict(frozen=True)

    symbols: list[str] = Field(min_length=1)
    confidence: float = 0.95
    method: Literal["historical", "parametric", "monte_carlo"] = "historical"
    horizon: int = 1


class RiskBetaRequest(BaseModel):
    """Query params for GET /api/v1/risk/beta."""

    model_config = ConfigDict(frozen=True)

    symbols: list[str] = Field(min_length=1)
    benchmark: str | None = None
    window: int = 60


class RiskCorrelationRequest(BaseModel):
    """Query params for GET /api/v1/risk/correlation."""

    model_config = ConfigDict(frozen=True)

    symbols: list[str] = Field(min_length=2)
    window: int = 30
    group_by: str | None = None


class RiskKellyRequest(BaseModel):
    """POST /api/v1/risk/kelly request body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    backtest_run_id: str
    max_dd_target: float = 0.25


class RiskPositionSizeRequest(BaseModel):
    """POST /api/v1/risk/position-size request body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbols: list[str]
    method: Literal["atr", "kelly", "fixed"] = "atr"
    cash: float = 100_000.0
    params: dict[str, Any] = Field(default_factory=dict)


class RiskSummaryRequest(BaseModel):
    """Query params for GET /api/v1/risk/summary."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: str = "default"
    symbols: list[str] | None = None


# ── Health Schemas ──


class HealthResponse(BaseModel):
    """GET /health liveness response."""

    model_config = ConfigDict(frozen=True)

    status: str
    service: str
    version: str
    timestamp: str


class HealthCheckDetail(BaseModel):
    """Individual health check result."""

    model_config = ConfigDict(frozen=True)

    database: bool = False


class ReadinessResponse(HealthResponse):
    """GET /health/ready readiness response with checks."""

    checks: HealthCheckDetail


# ── WebSocket Schemas ──


class WSSubscriptionRequest(BaseModel):
    """WebSocket subscription/unsubscription message."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["subscribe", "unsubscribe"]
    channels: list[str]


class WSSubscriptionChannel(str, enum.Enum):  # noqa: UP042 — Python 3.11+ StrEnum available
    """Enum of available WebSocket channel types."""

    PRICE = "price"
    INDICATOR = "indicator"
    SIGNAL = "signal"
    SCREENER = "screener"
    RISK = "risk"
    BACKTEST = "backtest"
    ALERT = "alert"
    REPLAY = "replay"


# StreamChannel literal type for channel string patterns
StreamChannel = Literal[
    "price",
    "indicator",
    "signal",
    "screener",
    "risk",
    "backtest",
    "alert",
    "replay",
]


# ── Phase 8: Screen Configuration Schemas ──


class CreateScreenRequest(BaseModel):
    """POST /api/v1/screens request body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: str = ""
    filter_json: str
    asset_classes: list[str] | None = None
    timeframes: list[str] | None = None
    tags: list[str] | None = None
    is_public: bool = False


class UpdateScreenRequest(BaseModel):
    """PUT /api/v1/screens/{id} request body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str | None = None
    description: str | None = None
    filter_json: str | None = None
    asset_classes: list[str] | None = None
    timeframes: list[str] | None = None
    tags: list[str] | None = None
    is_public: bool | None = None


class ScreenListItem(BaseModel):
    """Summary item for screen list response."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str = ""
    version: int
    is_public: bool = False
    created_at: str = ""
    updated_at: str = ""
    tags: list[str] = Field(default_factory=list)


class ScreenDetail(BaseModel):
    """Full screen detail response."""

    model_config = ConfigDict(frozen=True)

    id: str
    user_id: str = "default"
    name: str
    description: str = ""
    filter_json: str
    asset_classes: list[str] = Field(default_factory=list)
    timeframes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    version: int
    is_public: bool = False
    created_at: str = ""
    updated_at: str = ""


class ScreenVersionSummary(BaseModel):
    """Summary of a screen version."""

    model_config = ConfigDict(frozen=True)

    version: int
    name: str
    created_at: str = ""


# ── Phase 8: Alert Schemas ──


class CreateAlertRequest(BaseModel):
    """POST /api/v1/alerts request body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: str = ""
    alert_type: str  # price_threshold | indicator_cross | signal_trigger | volume_spike | trend_break | compound
    condition_json: str
    symbols: list[str] | None = None
    timeframes: list[str] | None = None
    is_active: bool = True
    cooldown_seconds: int = 300


class UpdateAlertRequest(BaseModel):
    """PUT /api/v1/alerts/{id} request body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str | None = None
    description: str | None = None
    condition_json: str | None = None
    symbols: list[str] | None = None
    timeframes: list[str] | None = None
    is_active: bool | None = None
    cooldown_seconds: int | None = None


class AlertDetail(BaseModel):
    """Full alert detail response."""

    model_config = ConfigDict(frozen=True)

    id: str
    user_id: str = "default"
    name: str
    description: str = ""
    alert_type: str
    condition_json: str
    symbols: list[str] = Field(default_factory=list)
    timeframes: list[str] = Field(default_factory=list)
    is_active: bool = True
    cooldown_seconds: int = 300
    last_triggered_at: str | None = None
    trigger_count: int = 0
    created_at: str = ""
    updated_at: str = ""


class AlertHistoryDetail(BaseModel):
    """Single alert history entry response."""

    model_config = ConfigDict(frozen=True)

    id: str
    alert_id: str
    symbol: str | None = None
    triggered_at: str
    condition_matched: str | None = None
    value_at_trigger: float | None = None
    threshold: float | None = None
    dismissed: bool = False


# ── Phase 8: Replay Schemas ──


class ReplayRequest(BaseModel):
    """POST /api/v1/screens/replay request body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    screen_config_id: str
    version: int = 1
    start_date: str | None = None
    end_date: str | None = None


class ReplayResultResponse(BaseModel):
    """Replay result response."""

    model_config = ConfigDict(frozen=True)

    id: str
    screen_config_id: str
    version: int
    start_date: str
    end_date: str
    total_days: int
    avg_match_count: float | None = None
    max_match_count: int | None = None
    min_match_count: int | None = None
    total_signals: int | None = None
    win_rate: float | None = None
    avg_return: float | None = None
    total_return: float | None = None
    sharpe: float | None = None
    max_drawdown: float | None = None
    equity_curve: list[dict[str, Any]] = Field(default_factory=list)
    match_series: list[dict[str, Any]] = Field(default_factory=list)


class ReplayStartResponse(BaseModel):
    """Response when replay is started."""

    model_config = ConfigDict(frozen=True)

    result_id: str
    status: str = "running"


# ── Phase 8: Sharing Schemas ──


class ShareTokenRequest(BaseModel):
    """POST /api/v1/screens/{id}/share request body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    expiry_days: int | None = None


class ShareTokenResponse(BaseModel):
    """Share token response."""

    model_config = ConfigDict(frozen=True)

    token: str
    url: str
    expires_at: str
