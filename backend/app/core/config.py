"""Application configuration using pydantic-settings with YAML support."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
from pydantic_settings.sources import YamlConfigSettingsSource


class CoreSettings(BaseSettings):
    """Core infrastructure settings."""

    model_config = SettingsConfigDict(env_prefix="CONFLU_CORE_")

    duckdb_path: str = Field(
        default="data/conflu.duckdb",
        description="Path to DuckDB database file",
    )
    duckdb_data_dir: str = Field(
        default="data",
        description="Root directory for partitioned Parquet data",
    )
    log_level: str = Field(default="INFO", description="Log level (DEBUG, INFO, WARNING, ERROR)")
    log_json: bool = Field(default=True, description="Output logs as JSON")


class DataSettings(BaseSettings):
    """Data ingestion settings."""

    model_config = SettingsConfigDict(env_prefix="CONFLU_DATA_")

    screener_sources: list[str] = Field(
        default=["america", "crypto", "forex", "futures"],
        description="Active screener data sources",
    )
    timeframes: list[str] = Field(
        default=["1m", "5m", "15m", "1h", "4h", "1D"],
        description="Supported timeframes",
    )
    assets: dict[str, list[str]] = Field(
        default={
            "equities": ["SPY", "QQQ", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM"],
            "crypto": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"],
            "forex": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"],
            "commodities": ["GC1!", "CL1!", "SI1!", "HG1!"],
            "indices": ["SPX", "NDX", "DJI"],
        },
        description="Default symbol lists per asset class",
    )
    max_concurrent: int = Field(
        default=50,
        description="Max concurrent fetch operations (semaphore limit)",
        ge=1,
        le=200,
    )
    exchange_prefixes: dict[str, str] = Field(
        default={
            "equities": "NASDAQ:",
            "crypto": "BINANCE:",
            "forex": "FX:",
            "commodities": "COMEX:",
            "indices": "SP:",
        },
        description="Default exchange prefix per asset class for TV ticker",
    )
    asset_class_markets: dict[str, str] = Field(
        default={
            "equities": "america",
            "crypto": "crypto",
            "forex": "forex",
            "commodities": "futures",
            "indices": "america",
        },
        description="TV market name per asset class",
    )
    asset_class_timezones: dict[str, str] = Field(
        default={
            "equities": "America/New_York",
            "crypto": "UTC",
            "forex": "UTC",
            "commodities": "America/New_York",
            "indices": "America/New_York",
        },
        description="Default timezone per asset class",
    )
    symbol_exchange_overrides: dict[str, str] = Field(
        default={"SPY": "AMEX:"},
        description="Per-symbol exchange prefix overrides",
    )
    tv_session_id: str = Field(
        default="",
        description="TradingView session cookie for reduced data delay (optional)",
    )
    batch_size: int = Field(
        default=100,
        description="Symbols per API call (TV limit)",
        ge=1,
        le=500,
    )


class IngestionSettings(BaseSettings):
    """Ingestion pipeline resilience and scheduling settings."""

    model_config = SettingsConfigDict(env_prefix="CONFLU_INGESTION_")

    retry_max_attempts: int = Field(
        default=3,
        description="Maximum retry attempts per scan request",
        ge=0,
        le=10,
    )
    retry_base_delay_s: float = Field(
        default=1.0,
        description="Base delay in seconds for exponential backoff",
        ge=0.1,
        le=60.0,
    )
    retry_max_delay_s: float = Field(
        default=30.0,
        description="Maximum delay in seconds between retries",
        ge=1.0,
        le=300.0,
    )
    retry_backoff_factor: float = Field(
        default=2.0,
        description="Exponential backoff multiplier",
        ge=1.0,
        le=10.0,
    )
    retry_jitter: float = Field(
        default=0.1,
        description="Jitter fraction applied to delay (0.1 = 10%)",
        ge=0.0,
        le=0.5,
    )
    circuit_breaker_threshold: int = Field(
        default=5,
        description="Consecutive failures before circuit opens",
        ge=1,
        le=50,
    )
    circuit_breaker_cooldown_s: float = Field(
        default=30.0,
        description="Cooldown seconds before half-open retry",
        ge=1.0,
        le=600.0,
    )
    daily_schedule_utc: str = Field(
        default="00:00",
        description="UTC time for daily 1D refresh (HH:MM format)",
    )
    intraday_interval_s: int = Field(
        default=300,
        description="Seconds between intraday polling cycles (default 300 = 5m)",
        ge=60,
        le=3600,
    )


class ComputeSettings(BaseSettings):
    """Compute engine settings."""

    model_config = SettingsConfigDict(env_prefix="CONFLU_COMPUTE_")

    default_indicator_timeframe: str = Field(
        default="1D",
        description="Default timeframe for indicator computation",
    )
    cache_indicators: bool = Field(
        default=True,
        description="Cache computed indicators in DuckDB materialized views",
    )
    broadcast_indicators: list[str] = Field(
        default=["rsi", "macd", "ema", "sma", "atr"],
        description="Indicators to broadcast to lower timeframes",
    )
    cached_indicators: list[str] = Field(
        default=["rsi", "macd", "ema", "sma", "atr", "adx", "obv", "bb", "vwap", "stoch"],
        description="Indicator names to pre-compute and cache in indicator_values table",
    )
    indicator_cache_enabled: bool = Field(
        default=True,
        description="Enable DuckDB indicator cache (indicator_values table)",
    )
    screen_default_timeframes: list[str] = Field(
        default=["1D", "4h", "1h"],
        description="Default timeframes for screening, evaluated top-down",
    )


class ScreenSettings(BaseSettings):
    """Screener engine settings."""

    model_config = SettingsConfigDict(env_prefix="CONFLU_SCREEN_")

    screens_dir: str = Field(
        default="config/screens",
        description="Directory containing screen YAML configuration files",
    )
    screener_ws_path: str = Field(
        default="/api/v1/ws/screener/{screen_id}",
        description="WebSocket endpoint path template for screener streaming",
    )
    stream_interval_s: float = Field(
        default=5.0,
        description="Seconds between WebSocket stream updates",
        ge=1.0,
        le=60.0,
    )
    max_history: int = Field(
        default=100,
        description="Max WebSocket history messages to retain for reconnection",
        ge=10,
        le=1000,
    )
    top_down_narrowing: bool = Field(
        default=True,
        description="Evaluate timeframes top-down (1D->4h->1h), narrowing candidates at each step",
    )
    parallel_asset_classes: int = Field(
        default=5,
        description="Max asset classes to screen in parallel",
        ge=1,
        le=20,
    )


class OptimizationSettings(BaseSettings):
    """Parameter optimization settings."""

    model_config = SettingsConfigDict(env_prefix="CONFLU_OPTIMIZATION_")

    enabled: bool = Field(default=False, description="Enable parameter optimization")
    default_method: Literal["grid", "random", "bayesian"] = Field(default="bayesian", description="Default method")
    max_trials: int = Field(default=100, ge=10, le=100_000, description="Max trials")
    timeout_s: int = Field(default=300, ge=30, le=86_400, description="Timeout in seconds")
    n_jobs: int = Field(default=4, ge=1, le=32, description="Parallel jobs")
    early_stopping: bool = Field(default=True, description="Median pruning for Optuna")
    min_improvement: float = Field(default=0.01, ge=0.0, le=1.0, description="Min improvement to continue")
    multi_objective: bool = Field(default=False, description="Multi-objective Pareto")
    objective_metrics: list[str] = Field(default=["sharpe","sortino","calmar","max_dd","win_rate"])
    default_objective: str = Field(default="sharpe", description="Default objective metric")
    optuna_storage: Literal["sqlite", "duckdb"] = Field(default="sqlite")
    optuna_storage_path: str = Field(default="data/optuna_studies.db")


class RegimeSettings(BaseSettings):
    """Market regime detection settings."""

    model_config = SettingsConfigDict(env_prefix="CONFLU_REGIME_")

    enabled: bool = Field(default=False)
    default_method: Literal["hmm", "volatility_quantile", "garch"] = Field(default="hmm")
    hmm_n_states: int = Field(default=3, ge=2, le=4)
    hmm_window_days: int = Field(default=252, ge=63, le=1260)
    hmm_n_iter: int = Field(default=100, ge=10, le=1000)
    vol_quantile_buckets: int = Field(default=4, ge=2, le=5)
    vol_window_days: int = Field(default=21, ge=5, le=252)
    regime_features: list[str] = Field(default=["returns", "volatility"])


class ReportSettings(BaseSettings):
    """Report generation settings."""

    model_config = SettingsConfigDict(env_prefix="CONFLU_REPORT_")

    enabled: bool = Field(default=False)
    default_formats: list[Literal["html", "pdf", "json"]] = Field(default=["html", "json"])
    templates_dir: str = Field(default="config/report_templates")
    default_template: str = Field(default="backtest_report.html")
    include_equity_curve: bool = Field(default=True)
    include_drawdown: bool = Field(default=True)
    include_trade_analysis: bool = Field(default=True)
    include_regime_analysis: bool = Field(default=False)
    include_parameter_sensitivity: bool = Field(default=True)
    max_chart_points: int = Field(default=5000, ge=100, le=50000)


class ComparisonSettings(BaseSettings):
    """Strategy comparison settings."""

    model_config = SettingsConfigDict(env_prefix="CONFLU_COMPARISON_")

    enabled: bool = Field(default=False)
    max_strategies: int = Field(default=10, ge=2, le=50)
    significance_level: float = Field(default=0.05, ge=0.001, le=0.1)
    bootstrap_samples: int = Field(default=1000, ge=100, le=10000)


class BacktestSettings(BaseSettings):
    """Backtest engine settings."""

    model_config = SettingsConfigDict(env_prefix="CONFLU_BACKTEST_")

    default_timeframe: str = Field(
        default="1D",
        description="Default timeframe for backtest runs",
    )
    default_position_sizing: Literal["fixed", "atr", "kelly"] = Field(
        default="fixed",
        description="Default position sizing method",
    )
    default_fees_bps: float = Field(
        default=10.0,
        description="Default fee in basis points per trade side",
        ge=0.0,
    )
    default_slippage_bps: float = Field(
        default=5.0,
        description="Default slippage in basis points per trade side",
        ge=0.0,
    )
    default_initial_cash: float = Field(
        default=100_000.0,
        description="Default initial capital",
        gt=0,
    )
    default_min_train_bars: int = Field(
        default=252,
        description="Minimum training bars for walk-forward optimization",
        ge=50,
    )
    default_train_pct: float = Field(
        default=0.7,
        description="Default training percentage for walk-forward split",
        ge=0.5,
        le=0.9,
    )
    cache_results: bool = Field(
        default=True,
        description="Cache backtest results in DuckDB for repeat runs",
    )
    max_symbols_per_run: int = Field(
        default=50,
        description="Maximum symbols to backtest in a single run",
        ge=1,
        le=1000,
    )
    parallel_symbols: int = Field(
        default=4,
        description="Number of symbols to process in parallel",
        ge=1,
        le=16,
    )

    optimization: OptimizationSettings = Field(default_factory=OptimizationSettings)
    regime_detection: RegimeSettings = Field(default_factory=RegimeSettings)
    reporting: ReportSettings = Field(default_factory=ReportSettings)
    comparison: ComparisonSettings = Field(default_factory=ComparisonSettings)


class APISettings(BaseSettings):
    """API server settings."""

    model_config = SettingsConfigDict(env_prefix="CONFLU_API_")

    host: str = Field(default="0.0.0.0", description="API server bind address")
    port: int = Field(default=8000, description="API server port", ge=1024, le=65535)
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins",
    )
    rate_limit: int = Field(
        default=100,
        description="Max requests per minute per client",
        ge=1,
    )

    # Rate limits per endpoint group (D-14)
    rate_limit_screener: int = Field(default=30, ge=1, le=1000, description="Screener endpoint requests/min")
    rate_limit_backtest: int = Field(default=10, ge=1, le=100, description="Backtest endpoint requests/min")
    rate_limit_data: int = Field(default=200, ge=1, le=5000, description="Data endpoint requests/min")
    rate_limit_ws: int = Field(default=10, ge=1, le=100, description="WebSocket messages/second/client")

    # Authentication (D-10, D-11)
    api_keys: list[str] = Field(default_factory=list, description="Valid API keys. Empty = auth disabled (dev mode).")
    jwt_secret: str = Field(default="", description="JWT signing secret (deferred)")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expire_minutes: int = Field(default=60, description="JWT token expiry in minutes")

    # CORS
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = Field(default=["*"])
    cors_allow_headers: list[str] = Field(default=["*"])

    # OpenTelemetry (D-17)
    otel_service_name: str = "conflu-api"
    otel_exporter_otlp_endpoint: str = Field(default="", description="OTLP gRPC endpoint (empty = console exporter)")

    # Prometheus (D-16)
    prometheus_enabled: bool = True

    # Security
    log_request_body: bool = False

    # Health checks
    health_db_timeout_s: float = Field(default=5.0, ge=1.0)

    # WebSocket (D-05, D-06)
    ws_max_connections: int = Field(default=1000, ge=1, le=10000)
    ws_ping_interval_s: float = Field(default=30.0, ge=5.0)
    ws_pong_timeout_s: float = Field(default=10.0, ge=1.0)


class FrontendSettings(BaseSettings):
    """Frontend configuration."""

    model_config = SettingsConfigDict(env_prefix="CONFLU_FRONTEND_")

    ws_endpoint: str = Field(
        default="ws://localhost:8000/ws",
        description="WebSocket endpoint for real-time data",
    )
    chart_config: dict[str, object] = Field(
        default={
            "default_timeframe": "1D",
            "indicators": ["RSI", "MACD", "EMA_20", "EMA_50", "BB"],
        },
        description="Default chart configuration",
    )


class RiskSettings(BaseSettings):
    """Risk management engine settings."""

    model_config = SettingsConfigDict(env_prefix="CONFLU_RISK_")

    default_risk_per_trade: float = Field(default=0.01, ge=0.001, le=0.1, description="Default risk per trade as fraction of equity (1%)")
    default_atr_multiplier: float = Field(default=2.0, ge=1.0, le=5.0, description="Default ATR multiplier")
    beta_window_days: int = Field(default=60, ge=20, le=252, description="Rolling window for beta in days")
    beta_benchmark_map: dict[str, str] = Field(default={"equities": "SPY", "crypto": "BTCUSDT", "forex": "EURUSD", "commodities": "GC1!", "indices": "SPX"}, description="Benchmark per asset class")
    correlation_window_days: int = Field(default=30, ge=10, le=252, description="Rolling window for correlation in days")
    var_confidence_levels: list[float] = Field(default=[0.95, 0.99], description="Confidence levels for VaR")
    var_horizon_days: list[int] = Field(default=[1, 10], description="Time horizons for VaR in days")
    var_methods: list[str] = Field(default=["historical", "parametric", "monte_carlo"], description="Active VaR methods")
    var_monte_carlo_paths: int = Field(default=10000, ge=1000, le=100000, description="Paths for MC VaR")
    default_kelly_fraction: float = Field(default=0.5, ge=0.0, le=1.0, description="Default Kelly fraction (0.5 = half-Kelly)")
    max_dd_target: float = Field(default=0.25, ge=0.1, le=0.5, description="Max acceptable drawdown")
    risk_ws_path: str = Field(default="/api/v1/ws/risk/{portfolio_id}", description="WebSocket endpoint template")
    report_max_symbols: int = Field(default=50, description="Max symbols in risk report")
    cache_risk_results: bool = Field(default=True, description="Cache risk results in DuckDB")
    max_correlation_symbols: int = Field(default=100, description="Max symbols in correlation matrix (0=unlimited)")


class AlertSettings(BaseSettings):
    """Alert engine settings."""

    model_config = SettingsConfigDict(env_prefix="CONFLU_ALERT_")

    evaluation_interval_s: int = Field(
        default=60,
        description="Seconds between alert evaluation cycles",
        ge=5,
        le=600,
    )
    max_alerts_per_user: int = Field(
        default=100,
        description="Maximum active alerts per user",
        ge=1,
        le=500,
    )
    max_triggers_per_day: int = Field(
        default=100,
        description="Max alert triggers per user per day before auto-disable",
        ge=1,
        le=1000,
    )
    default_cooldown_s: int = Field(
        default=300,
        description="Default cooldown in seconds between alert triggers (5 min)",
        ge=30,
        le=86400,
    )


class ShareSettings(BaseSettings):
    """Screen sharing settings."""

    model_config = SettingsConfigDict(env_prefix="CONFLU_SHARE_")

    default_expiry_days: int = Field(
        default=7,
        description="Default share URL expiry in days",
        ge=1,
        le=365,
    )
    max_expiry_days: int = Field(
        default=365,
        description="Maximum share URL expiry in days",
        ge=1,
        le=3650,
    )
    secret_key: str = Field(
        default="conflu-share-secret-dev",
        description="Secret key for HMAC share token signing",
    )


class ReplaySettings(BaseSettings):
    """Screen replay settings."""

    model_config = SettingsConfigDict(env_prefix="CONFLU_REPLAY_")

    max_years: int = Field(
        default=2,
        description="Maximum years of historical replay data",
        ge=1,
        le=10,
    )
    default_years: int = Field(
        default=2,
        description="Default years for replay",
        ge=1,
        le=10,
    )
    max_symbols: int = Field(
        default=100,
        description="Maximum symbols per replay evaluation",
        ge=1,
        le=5000,
    )


class AppSettings(BaseSettings):
    """Top-level settings aggregating all layer configs.

    Config source priority (highest to lowest):
    1. Environment variables (CONFLU_* prefix)
    2. config.local.yaml (gitignored, for secrets/overrides)
    3. config.yaml (version-controlled, shared defaults)
    4. Field defaults in settings classes
    """

    model_config = SettingsConfigDict(
        yaml_file=["config.yaml", "config.local.yaml"],
        env_prefix="CONFLU_",
        env_nested_delimiter="__",
        extra="forbid",
    )

    core: CoreSettings = CoreSettings()
    data: DataSettings = DataSettings()
    ingestion: IngestionSettings = IngestionSettings()
    compute: ComputeSettings = ComputeSettings()
    screen: ScreenSettings = ScreenSettings()
    backtest: BacktestSettings = BacktestSettings()
    api: APISettings = APISettings()
    frontend: FrontendSettings = FrontendSettings()
    risk: RiskSettings = RiskSettings()
    alert: AlertSettings = AlertSettings()
    share: ShareSettings = ShareSettings()
    replay: ReplaySettings = ReplaySettings()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize source priority: env > config.local.yaml > config.yaml > defaults."""
        yaml_sources: list[YamlConfigSettingsSource] = []
        for yaml_file in ["config.local.yaml", "config.yaml"]:
            yaml_path = Path(yaml_file)
            if yaml_path.exists():
                yaml_sources.append(
                    YamlConfigSettingsSource(settings_cls, yaml_file=str(yaml_path))
                )

        return (env_settings, *yaml_sources, init_settings)


# Singleton settings instance
settings = AppSettings()
