"""Application configuration using pydantic-settings with YAML support."""

from __future__ import annotations

from pathlib import Path
from typing import Any

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


class APISettings(BaseSettings):
    """API server settings."""

    model_config = SettingsConfigDict(env_prefix="CONFLU_API_")

    host: str = Field(default="0.0.0.0", description="API server bind address")
    port: int = Field(default=8000, description="API server port", ge=1024, le=65535)
    cors_origins: list[str] = Field(
        default=["http://localhost:5173"],
        description="Allowed CORS origins",
    )
    rate_limit: int = Field(
        default=100,
        description="Max requests per minute per client",
        ge=1,
    )


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
    api: APISettings = APISettings()
    frontend: FrontendSettings = FrontendSettings()

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
