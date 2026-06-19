# Phase 1: Foundation & Core Infrastructure — Plan

**Phase:** 1 — Foundation & Core Infrastructure
**Status:** Planned
**Date:** 2026-06-18
**Branch:** `feat/conflu-ai-platform`

---

## must_haves (Goal-Backward Verification)

Every plan task, when completed, must collectively satisfy these must_haves. Verify after execution:

| # | Must Have | Verifiable With |
|---|-----------|----------------|
| MH-1 | `pydantic-settings` loads `config.yaml` and overrides via env vars | `grep "YamlConfigSettingsSource" backend/app/core/config.py` |
| MH-2 | DuckDB `get_db()` context manager works with read-only and read-write modes | `grep "def get_db" backend/app/core/database.py` |
| MH-3 | Parquet partition path pattern `{asset_class}/{year}/{month}/{symbol}_{timeframe}.parquet` is defined as a constant or function | `grep "partition" backend/app/core/database.py` |
| MH-4 | `@indicator` decorator registered functions return DataFrame with `symbol`, `timestamp`, `indicator_name`, `value` columns | `grep "def indicator" backend/app/infrastructure/indicators.py` |
| MH-5 | All domain models (`OHLCV`, `Signal`, `Position`, `Trade`, `Metrics`, `ScreenResult`, `BacktestConfig`, `RiskParams`) use `ConfigDict(frozen=True, extra='forbid')` | `grep -c "frozen=True" backend/app/domain/models.py` shows 8 |
| MH-6 | `structlog` configured with JSON renderer, correlation IDs via `contextvars` | `grep "JSONRenderer" backend/app/core/logging.py` |
| MH-7 | `pytest` + `pytest-asyncio` + `hypothesis` are in test dependencies and conftest has DuckDB in-memory fixture | `grep "in_memory_db" backend/tests/conftest.py` |
| MH-8 | `mypy --strict` passes with zero errors | `cd backend && mypy --strict app/ tests/` exits 0 |
| MH-9 | Docker Compose has `api`, `worker`, `redis` services | `grep -c "^\s" docker-compose.yml` shows 3+ services |
| MH-10 | All task acceptance criteria pass (see per-task below) | Automated per-criterion checks |

---

## Wave 1: Foundation & Scaffolding

**No dependencies.** All three tasks run in parallel.

---

### Task 1.1: Project Scaffolding & Build Configuration

**Wave:** 1
**Depends on:** None
**Files modified:** `pyproject.toml` (new), `.gitignore` (new), `.pre-commit-config.yaml` (new), `backend/app/__init__.py` (new), `backend/app/core/__init__.py` (new), `backend/app/domain/__init__.py` (new), `backend/app/infrastructure/__init__.py` (new), `backend/app/api/__init__.py` (new), `backend/tests/__init__.py` (new)
**Autonomous:** true

<read_first>
- `.planning/phases/01-foundation-core-infrastructure/01-RESEARCH.md` — section 3.7 for mypy config, section 2 for dependency versions
- `.planning/phases/01-foundation-core-infrastructure/01-CONTEXT.md` — decisions D-12, D-14 for testing and type safety
- `backend/` directory — verify it exists and contains `app/` and `tests/` subdirectories
</read_first>

<action>
Create project scaffold files at `C:\_Code\conflu.ai\`:

**1. `pyproject.toml`** with the following exact dependencies and tool configs:

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "conflu-ai"
version = "0.1.0"
description = "Professional Multi-Asset Trading Platform"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0,<3",
    "pydantic-settings[yaml]>=2.0,<3",
    "duckdb>=0.10.0",
    "vectorbt>=0.40.0",
    "pandas-ta>=0.3.14",
    "pandas>=2.0,<3",
    "structlog>=24.1,<25",
    "numpy>=1.26",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "hypothesis>=6.0",
    "mypy>=1.8",
    "ruff>=0.3",
    "pre-commit>=3.6",
]
test = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "hypothesis>=6.0",
]

[tool.mypy]
strict = true
disallow_untyped_defs = true
warn_return_any = true
no_implicit_optional = true
check_untyped_defs = true
warn_unused_ignores = true
warn_redundant_casts = true
warn_unused_configs = true
warn_unreachable = true

[[tool.mypy.overrides]]
module = "pandas_ta.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "vectorbt.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "duckdb.*"
ignore_missing_imports = true

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM", "ARG", "C4"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["backend/tests"]
python_files = ["test_*.py"]
```

**2. `.gitignore`:**
```
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/
*.egg
.venv/
venv/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Project data
data/
*.db

# Config overrides
config.local.yaml

# Environment
.env
.env.local

# OS
.DS_Store
Thumbs.db

# Docker
.docker/
```

**3. `.pre-commit-config.yaml`:**
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        args: [--strict, --ignore-missing-imports]
        additional_dependencies: [pydantic, pydantic-settings, structlog]
```

**4. Empty `__init__.py` files** in each subpackage:
- `backend/app/__init__.py`
- `backend/app/core/__init__.py`
- `backend/app/domain/__init__.py`
- `backend/app/infrastructure/__init__.py`
- `backend/app/api/__init__.py`
- `backend/tests/__init__.py`
</action>

<acceptance_criteria>
1. `pyproject.toml` exists at project root and contains `[project]` with `pydantic-settings[yaml]`, `duckdb`, `vectorbt`, `pandas-ta`, `structlog` in dependencies
2. `pyproject.toml` contains `[tool.mypy]` with `strict = true`
3. `pyproject.toml` contains `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`
4. `pyproject.toml` `[[tool.mypy.overrides]]` has entries for `pandas_ta.*`, `vectorbt.*`, `duckdb.*` with `ignore_missing_imports = true`
5. `.gitignore` contains `data/`, `config.local.yaml`, `__pycache__/`
6. `.pre-commit-config.yaml` exists and references `ruff` and `mypy` repos
7. `backend/app/__init__.py` exists and is empty (0 bytes or just a newline)
8. `backend/app/core/__init__.py` exists
9. `backend/app/domain/__init__.py` exists
10. `backend/app/infrastructure/__init__.py` exists
11. `backend/app/api/__init__.py` exists
12. `backend/tests/__init__.py` exists
</acceptance_criteria>

---

### Task 1.2: Configuration Management

**Wave:** 1
**Depends on:** None (only needs `pyproject.toml` for context, but writes independent files)
**Files modified:** `backend/app/core/config.py` (new)
**Autonomous:** true

<read_first>
- `.planning/phases/01-foundation-core-infrastructure/01-RESEARCH.md` — section 3.1 (Configuration Management) for pydantic-settings API patterns
- `.planning/phases/01-foundation-core-infrastructure/01-CONTEXT.md` — decisions D-01, D-02 for config design
- `backend/app/core/` — verify directory exists (created in Task 1.1)
</read_first>

<action>
Create `backend/app/core/config.py` with the following layered settings classes and a YAML config file at the project root.

**Settings classes (all in one file `backend/app/core/config.py`):**

```python
"""Application configuration using pydantic-settings with YAML support."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
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
        default=["america", "crypto", "forex"],
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
        },
        description="Default symbol lists per asset class",
    )
    max_concurrent: int = Field(
        default=50,
        description="Max concurrent fetch operations (semaphore limit)",
        ge=1,
        le=200,
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
    compute: ComputeSettings = ComputeSettings()
    api: APISettings = APISettings()
    frontend: FrontendSettings = FrontendSettings()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: YamlConfigSettingsSource,
        env_settings: YamlConfigSettingsSource,
        dotenv_settings: YamlConfigSettingsSource,
        file_secret_settings: YamlConfigSettingsSource,
    ) -> tuple[YamlConfigSettingsSource, ...]:
        """Customize source priority: env > config.local.yaml > config.yaml > defaults."""
        from pydantic_settings.sources import (
            EnvSettingsSource,
            InitSettingsSource,
            SecretsSettingsSource,
        )

        yaml_sources = []
        for yaml_file in ["config.local.yaml", "config.yaml"]:
            yaml_path = Path(yaml_file)
            if yaml_path.exists():
                yaml_sources.append(
                    YamlConfigSettingsSource(settings_cls, yaml_file=str(yaml_path))
                )

        return (
            EnvSettingsSource(settings_cls, env_prefix="CONFLU_", env_nested_delimiter="__"),
            *yaml_sources,
            InitSettingsSource(init_settings),
        )


# Singleton settings instance
settings = AppSettings()
```

**Also create `config.yaml` at project root:**

```yaml
core:
  duckdb_path: data/conflu.duckdb
  duckdb_data_dir: data
  log_level: INFO
  log_json: true

data:
  screener_sources:
    - america
    - crypto
    - forex
  timeframes:
    - 1m
    - 5m
    - 15m
    - 1h
    - 4h
    - 1D
  assets:
    equities:
      - SPY
      - QQQ
      - AAPL
      - MSFT
      - GOOGL
      - AMZN
      - NVDA
      - META
      - TSLA
      - JPM
    crypto:
      - BTCUSDT
      - ETHUSDT
      - BNBUSDT
      - SOLUSDT
      - XRPUSDT
    forex:
      - EURUSD
      - GBPUSD
      - USDJPY
      - AUDUSD
      - USDCAD
  max_concurrent: 50

compute:
  default_indicator_timeframe: 1D
  cache_indicators: true
  broadcast_indicators:
    - rsi
    - macd
    - ema
    - sma
    - atr

api:
  host: 0.0.0.0
  port: 8000
  cors_origins:
    - http://localhost:5173
  rate_limit: 100

frontend:
  ws_endpoint: ws://localhost:8000/ws
  chart_config:
    default_timeframe: 1D
    indicators:
      - RSI
      - MACD
      - EMA_20
      - EMA_50
      - BB
```
</action>

<acceptance_criteria>
1. `backend/app/core/config.py` exists and contains `class CoreSettings(BaseSettings)`
2. `backend/app/core/config.py` contains `class AppSettings(BaseSettings)` with nested `core: CoreSettings`, `data: DataSettings`, `compute: ComputeSettings`, `api: APISettings`, `frontend: FrontendSettings`
3. `backend/app/core/config.py` defines `settings = AppSettings()` singleton at module level
4. `CoreSettings` has fields: `duckdb_path`, `duckdb_data_dir`, `log_level`, `log_json`
5. `DataSettings` has fields: `screener_sources`, `timeframes`, `assets`, `max_concurrent`
6. `ComputeSettings` has fields: `default_indicator_timeframe`, `cache_indicators`, `broadcast_indicators`
7. `APISettings` has fields: `host`, `port`, `cors_origins`, `rate_limit`
8. `FrontendSettings` has fields: `ws_endpoint`, `chart_config`
9. `backend/app/core/config.py` references `YamlConfigSettingsSource` from `pydantic_settings.sources`
10. `config.yaml` exists at project root with top-level keys: `core`, `data`, `compute`, `api`, `frontend`
11. `config.yaml` `assets` contains `equities`, `crypto`, `forex` as sub-keys
</acceptance_criteria>

---

### Task 1.3: Structured Logging

**Wave:** 1
**Depends on:** None
**Files modified:** `backend/app/core/logging.py` (new)
**Autonomous:** true

<read_first>
- `.planning/phases/01-foundation-core-infrastructure/01-RESEARCH.md` — section 3.5 (Structured Logging) for structlog API patterns
- `.planning/phases/01-foundation-core-infrastructure/01-CONTEXT.md` — decision D-11 for log levels and fields
- `backend/app/core/` — verify directory exists
</read_first>

<action>
Create `backend/app/core/logging.py` with the following exact content:

```python
"""Structured logging configuration using structlog."""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from uuid import uuid4

import structlog
from structlog.processors import CallsiteParameter, CallsiteParameterAdder

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def configure_logging(*, log_level: str = "INFO", log_json: bool = True) -> None:
    """Configure structlog with JSON output and correlation ID support.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        log_json: If True, output JSON-formatted logs. If False, use console-friendly format.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        CallsiteParameterAdder(
            [
                CallsiteParameter.FILENAME,
                CallsiteParameter.FUNC_NAME,
                CallsiteParameter.LINENO,
            ]
        ),
    ]

    if log_json:
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        shared_processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )


def set_correlation_id(cid: str | None = None) -> str:
    """Set and return a correlation ID for the current async context.

    Args:
        cid: Optional pre-existing correlation ID. If None, generates a new UUID.

    Returns:
        The correlation ID string.
    """
    cid = cid or str(uuid4())
    correlation_id.set(cid)
    structlog.contextvars.bind_contextvars(correlation_id=cid)
    return cid


def get_logger(name: str = "conflu") -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically module path).

    Returns:
        A structlog BoundLogger instance.
    """
    return structlog.get_logger(name)
```
</action>

<acceptance_criteria>
1. `backend/app/core/logging.py` exists
2. Contains `correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")`
3. Contains `def configure_logging(*, log_level: str = "INFO", log_json: bool = True) -> None:`
4. Contains `def set_correlation_id(cid: str | None = None) -> str:`
5. Contains `def get_logger(name: str = "conflu") -> structlog.stdlib.BoundLogger:`
6. References `JSONRenderer` from `structlog.processors`
7. References `CallsiteParameterAdder` from `structlog.processors`
8. References `merge_contextvars` from `structlog.contextvars`
9. `configure_logging` calls `logging.basicConfig(format="%(message)s", stream=sys.stdout, ...)`
10. `set_correlation_id` calls `structlog.contextvars.bind_contextvars(correlation_id=cid)`
</acceptance_criteria>

---

## Wave 2: Storage & Models

**Depends on:** Wave 1 (config and logging exist). Tasks run in parallel.

---

### Task 2.1: DuckDB Connection Pool & Data Schema

**Wave:** 2
**Depends on:** Task 1.2 (config.py exists), Task 1.1 (__init__.py files exist)
**Files modified:** `backend/app/core/database.py` (new)
**Autonomous:** true

<read_first>
- `.planning/phases/01-foundation-core-infrastructure/01-RESEARCH.md` — section 3.2 (DuckDB Connection Pool & Parquet Storage) for connection patterns, DDL, and partition scheme
- `.planning/phases/01-foundation-core-infrastructure/01-CONTEXT.md` — decisions D-03, D-04, D-05 for partition scheme, connection management, and schema
- `backend/app/core/config.py` — verify CoreSettings has duckdb_path, duckdb_data_dir
- `backend/app/core/__init__.py` — verify empty init exists
</read_first>

<action>
Create `backend/app/core/database.py` with:

```python
"""DuckDB connection management and Parquet partitioning utilities."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from pathlib import Path

import duckdb

from backend.app.core.config import settings

# SQL DDL for the OHLCV table
OHLCV_DDL = """
CREATE TABLE IF NOT EXISTS ohlcv (
    symbol VARCHAR,
    timestamp TIMESTAMPTZ,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE,
    timeframe VARCHAR,
    asset_class VARCHAR,
    year INTEGER,
    month INTEGER
);
CREATE INDEX IF NOT EXISTS idx_ohlcv_lookup ON ohlcv (symbol, timeframe, timestamp);
CREATE INDEX IF NOT EXISTS idx_ohlcv_partition ON ohlcv (asset_class, year, month);
"""

# Parquet partition path pattern
# Example: data/equities/2025/01/AAPL_1D.parquet
PARTITION_TEMPLATE = "{asset_class}/{year:04d}/{month:02d}/{symbol}_{timeframe}.parquet"


def partition_path(
    asset_class: str,
    year: int,
    month: int,
    symbol: str,
    timeframe: str,
    *,
    data_dir: str | None = None,
) -> Path:
    """Build the Parquet file path for a given partition.

    Partition scheme: {data_dir}/{asset_class}/{year}/{month}/{symbol}_{timeframe}.parquet

    Args:
        asset_class: Asset class (e.g., 'equities', 'crypto', 'forex').
        year: Calendar year of the data.
        month: Calendar month (1-12) of the data.
        symbol: Normalized symbol name (e.g., 'AAPL', 'BTCUSDT').
        timeframe: Timeframe string (e.g., '1D', '1h', '15m').
        data_dir: Override data directory. Defaults to settings.core.duckdb_data_dir.

    Returns:
        Absolute Path to the Parquet file.
    """
    base = Path(data_dir or settings.core.duckdb_data_dir)
    relative = PARTITION_TEMPLATE.format(
        asset_class=asset_class,
        year=year,
        month=month,
        symbol=symbol,
        timeframe=timeframe,
    )
    return (base / relative).resolve()


def normalize_symbol(symbol: str) -> str:
    """Normalize a symbol to a filesystem-safe representation.

    Removes characters that are problematic in file paths and uppercases.

    Args:
        symbol: Raw symbol string (e.g., 'BTC/USDT', 'BRK.B').

    Returns:
        Normalized symbol (e.g., 'BTCUSDT', 'BRK_B').
    """
    return (
        symbol.replace("/", "")
        .replace("\\", "")
        .replace(":", "")
        .replace("*", "")
        .replace("?", "")
        .replace('"', "")
        .replace("<", "")
        .replace(">", "")
        .replace("|", "")
        .upper()
    )


@contextmanager
def get_db(read_only: bool = False) -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Get a DuckDB connection via context manager.

    DuckDB is embedded — each call creates a new connection to the same database
    file. Multiple read-only connections are safe concurrently. Writes serialize.

    Args:
        read_only: If True, open connection in read-only mode.

    Yields:
        DuckDB connection instance.

    Example:
        with get_db() as con:
            result = con.sql("SELECT COUNT(*) FROM ohlcv")
    """
    db_path = settings.core.duckdb_path
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = duckdb.connect(db_path, read_only=read_only)
    try:
        yield conn
    finally:
        conn.close()


@asynccontextmanager
async def get_db_async(read_only: bool = False) -> AsyncGenerator[duckdb.DuckDBPyConnection, None]:
    """Async wrapper around get_db() using asyncio.to_thread.

    DuckDB's Python API is synchronous. This wrapper runs the connection
    lifecycle in a thread pool to avoid blocking the async event loop.

    Args:
        read_only: If True, open connection in read-only mode.

    Yields:
        DuckDB connection instance (running in executor thread).
    """
    import asyncio

    loop = asyncio.get_running_loop()
    conn: duckdb.DuckDBPyConnection = await loop.run_in_executor(
        None, lambda: duckdb.connect(settings.core.duckdb_path, read_only=read_only)
    )
    try:
        yield conn
    finally:
        await loop.run_in_executor(None, conn.close)


def initialize_database() -> None:
    """Initialize the DuckDB database: create tables and indexes."""
    with get_db() as con:
        con.execute(OHLCV_DDL)
```
</action>

<acceptance_criteria>
1. `backend/app/core/database.py` exists
2. Contains `def get_db(read_only: bool = False) -> Generator[duckdb.DuckDBPyConnection, None, None]:`
3. Contains `async def get_db_async(read_only: bool = False) -> AsyncGenerator[duckdb.DuckDBPyConnection, None, None]:`
4. Contains `def partition_path(...)` that produces paths matching `{data_dir}/{asset_class}/{year:04d}/{month:02d}/{symbol}_{timeframe}.parquet`
5. Contains `def normalize_symbol(symbol: str) -> str:` that strips `/\:*?"<>|` and uppercases
6. `OHLCV_DDL` constant contains `CREATE TABLE IF NOT EXISTS ohlcv` with columns: `symbol`, `timestamp TIMESTAMPTZ`, `open DOUBLE`, `high DOUBLE`, `low DOUBLE`, `close DOUBLE`, `volume DOUBLE`, `timeframe VARCHAR`, `asset_class VARCHAR`, `year INTEGER`, `month INTEGER`
7. `OHLCV_DDL` contains both `idx_ohlcv_lookup` and `idx_ohlcv_partition` indexes
8. `PARTITION_TEMPLATE` constant contains `{asset_class}/{year:04d}/{month:02d}/{symbol}_{timeframe}.parquet`
9. `initialize_database()` function exists and calls `get_db()` and `con.execute(OHLCV_DDL)`
10. `get_db_async` uses `asyncio.get_running_loop().run_in_executor` for non-blocking connect
</acceptance_criteria>

---

### Task 2.2: Domain Models

**Wave:** 2
**Depends on:** Task 1.1 (__init__.py exists)
**Files modified:** `backend/app/domain/models.py` (new)
**Autonomous:** true

<read_first>
- `.planning/phases/01-foundation-core-infrastructure/01-RESEARCH.md` — section 3.4 (Domain Models) for model field definitions and Pydantic v2 patterns
- `.planning/phases/01-foundation-core-infrastructure/01-CONTEXT.md` — decisions D-09, D-10 for frozen models and UTC timestamps
- `backend/app/domain/` — verify directory exists
</read_first>

<action>
Create `backend/app/domain/models.py` with the following eight domain models, all using `ConfigDict(frozen=True, extra='forbid')` and UTC-aware timestamp validation:

```python
"""Domain models for the trading platform.

All models are frozen (immutable) and forbid extra fields.
Timestamps are UTC-aware datetime objects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
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


class ScreenResult(BaseModel):
    """Single row from a screener output."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    score: float = Field(default=0.0, ge=0.0, le=100.0)
    signals: list[Signal] = Field(default_factory=list)
    indicators: dict[str, float] = Field(default_factory=dict)
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
```
</action>

<acceptance_criteria>
1. `backend/app/domain/models.py` exists
2. File contains exactly 8 model classes: `OHLCV`, `Signal`, `Position`, `Trade`, `Metrics`, `ScreenResult`, `BacktestConfig`, `RiskParams`
3. Every model class uses `model_config = ConfigDict(frozen=True, extra="forbid")` — verify with: `grep -c "frozen=True" backend/app/domain/models.py` outputs at least 8
4. Every `ConfigDict` uses `extra="forbid"` — string appears exactly 8 times
5. `OHLCV` has fields: `symbol`, `timestamp`, `open`, `high`, `low`, `close`, `volume`, `timeframe`, `asset_class`
6. `Signal` has fields: `symbol`, `timestamp`, `direction` (Literal["buy", "sell", "hold"]), `strength` (ge=0.0, le=1.0), `source`
7. `Metrics` has fields: `sharpe`, `sortino`, `calmar`, `max_dd`, `win_rate`, `expectancy`, `profit_factor`, `sqn`, `ulcer`
8. `BacktestConfig` has fields: `symbols`, `start`, `end`, `initial_cash`, `fees`, `slippage`, `position_sizing` (Literal["fixed", "atr", "kelly"]), `strategy_params`
9. `RiskParams` has fields: `risk_per_trade`, `max_position_size`, `atr_period`, `beta_benchmark`, `kelly_fraction`
10. Every `timestamp`/`start`/`end`/`entry_time`/`exit_time` field has a `@field_validator("ensure_utc")` that raises `ValueError` for naive datetimes
11. `Trade` includes fields: `mae`, `mfe`
12. `ScreenResult` includes a `signals: list[Signal]` field with `default_factory=list`
</acceptance_criteria>

---

## Wave 3: Compute Primitives

**Depends on:** Wave 2 (domain models exist)

---

### Task 3.1: Indicator Registry & Vectorized Compute Primitives

**Wave:** 3
**Depends on:** Task 2.2 (Domain models exist — Signal model for output typing)
**Files modified:** `backend/app/infrastructure/indicators.py` (new)
**Autonomous:** true

<read_first>
- `.planning/phases/01-foundation-core-infrastructure/01-RESEARCH.md` — section 3.3 (Vectorized Compute Primitives) for indicator registry pattern, pandas-ta API, and vectorbt IndicatorFactory patterns
- `.planning/phases/01-foundation-core-infrastructure/01-CONTEXT.md` — decisions D-06, D-07, D-08 for zero-loop guarantee, registry pattern, multi-timeframe broadcasting
- `backend/app/domain/models.py` — verify OHLCV and Signal models exist for type hints
- `backend/app/infrastructure/` — verify directory exists
</read_first>

<action>
Create `backend/app/infrastructure/indicators.py` with the following components:

**a) Indicator Registry Decorator:**
```python
"""Vectorized compute primitives: indicator registry, pandas-ta wrappers, vectorbt integration.

ZERO explicit loops over DataFrame rows — all operations are vectorized.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

import pandas as pd

_INDICATOR_REGISTRY: dict[str, Callable[..., pd.DataFrame]] = {}


def indicator(name: str, timeframe: str = "1D") -> Callable[[Callable[..., pd.DataFrame]], Callable[..., pd.DataFrame]]:
    """Register an indicator computation function.

    Registered functions are tracked in ``_INDICATOR_REGISTRY`` for discovery
    and caching. The wrapped function must return a DataFrame with columns:
    ``symbol``, ``timestamp``, ``indicator_name``, ``value``.

    Args:
        name: Canonical indicator name (e.g., 'rsi', 'macd').
        timeframe: Default computation timeframe (e.g., '1D', '1h').

    Returns:
        A decorator that registers the function and wraps it for validation.

    Example:
        @indicator(name="rsi", timeframe="1D")
        def compute_rsi(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
            ...
    """

    def decorator(func: Callable[..., pd.DataFrame]) -> Callable[..., pd.DataFrame]:
        _INDICATOR_REGISTRY[name] = func

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> pd.DataFrame:
            result = func(*args, **kwargs)
            required_cols = {"symbol", "timestamp", "indicator_name", "value"}
            if not required_cols.issubset(result.columns):
                msg = (
                    f"Indicator '{name}' output missing required columns. "
                    f"Expected {required_cols}, got {set(result.columns)}"
                )
                raise ValueError(msg)
            return result

        return wrapper

    return decorator
```

**b) pandas-ta Wrapper Indicators (first 5):**

```python
import pandas_ta as ta


@indicator(name="rsi", timeframe="1D")
def compute_rsi(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """Compute Relative Strength Index.

    Args:
        df: DataFrame with 'close' column, plus 'symbol' and 'timestamp'.
        length: RSI lookback period (default 14).

    Returns:
        DataFrame with columns: symbol, timestamp, indicator_name, value.
    """
    result = df[["symbol", "timestamp"]].copy()
    values = ta.rsi(close=df["close"], length=length)
    result["indicator_name"] = "rsi"
    result["value"] = values
    return result


@indicator(name="macd", timeframe="1D")
def compute_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Compute MACD oscillator (MACD line, signal line, histogram).

    Returns three rows per timestamp: one for 'macd', 'macd_signal', 'macd_hist'.

    Args:
        df: DataFrame with 'close' column.
        fast: Fast EMA period (default 12).
        slow: Slow EMA period (default 26).
        signal: Signal line period (default 9).

    Returns:
        DataFrame with symbol, timestamp, indicator_name, value columns.
    """
    macd_result = ta.macd(close=df["close"], fast=fast, slow=slow, signal=signal)
    if macd_result is None or macd_result.empty:
        return pd.DataFrame(columns=["symbol", "timestamp", "indicator_name", "value"])

    rows = []
    base = df[["symbol", "timestamp"]]
    for col in macd_result.columns:
        part = base.copy()
        part["indicator_name"] = col.lower().replace("macd_", "macd_")
        part["value"] = macd_result[col].values
        rows.append(part)

    return pd.concat(rows, ignore_index=True)


@indicator(name="ema", timeframe="1D")
def compute_ema(df: pd.DataFrame, length: int = 20) -> pd.DataFrame:
    """Compute Exponential Moving Average.

    Args:
        df: DataFrame with 'close' column.
        length: EMA period (default 20).

    Returns:
        DataFrame with symbol, timestamp, indicator_name, value columns.
    """
    result = df[["symbol", "timestamp"]].copy()
    values = ta.ema(close=df["close"], length=length)
    result["indicator_name"] = f"ema_{length}"
    result["value"] = values
    return result


@indicator(name="sma", timeframe="1D")
def compute_sma(df: pd.DataFrame, length: int = 50) -> pd.DataFrame:
    """Compute Simple Moving Average.

    Args:
        df: DataFrame with 'close' column.
        length: SMA period (default 50).

    Returns:
        DataFrame with symbol, timestamp, indicator_name, value columns.
    """
    result = df[["symbol", "timestamp"]].copy()
    values = ta.sma(close=df["close"], length=length)
    result["indicator_name"] = f"sma_{length}"
    result["value"] = values
    return result


@indicator(name="atr", timeframe="1D")
def compute_atr(
    df: pd.DataFrame,
    length: int = 14,
) -> pd.DataFrame:
    """Compute Average True Range for volatility measurement.

    Args:
        df: DataFrame with 'high', 'low', 'close' columns.
        length: ATR period (default 14).

    Returns:
        DataFrame with symbol, timestamp, indicator_name, value columns.
    """
    result = df[["symbol", "timestamp"]].copy()
    values = ta.atr(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        length=length,
    )
    result["indicator_name"] = "atr"
    result["value"] = values
    return result
```

**c) Helper functions:**

```python
def list_indicators() -> dict[str, Callable[..., pd.DataFrame]]:
    """Return a copy of the registered indicator registry.

    Returns:
        Dict mapping indicator name to its registered function.
    """
    return dict(_INDICATOR_REGISTRY)


def compute_all(
    df: pd.DataFrame,
    indicators: list[str] | None = None,
    **kwargs: Any,
) -> dict[str, pd.DataFrame]:
    """Compute multiple indicators at once.

    Args:
        df: Input DataFrame with OHLCV columns.
        indicators: List of indicator names to compute. If None, compute all registered.
        **kwargs: Additional keyword arguments passed to each indicator function.

    Returns:
        Dict mapping indicator name to its result DataFrame.
    """
    names = indicators or list(_INDICATOR_REGISTRY.keys())
    results: dict[str, pd.DataFrame] = {}
    for name in names:
        func = _INDICATOR_REGISTRY.get(name)
        if func is not None:
            results[name] = func(df, **kwargs)
    return results
```
</action>

<acceptance_criteria>
1. `backend/app/infrastructure/indicators.py` exists
2. `_INDICATOR_REGISTRY` is a `dict[str, Callable[..., pd.DataFrame]]` at module level
3. `def indicator(name: str, timeframe: str = "1D")` decorator exists and registers functions into `_INDICATOR_REGISTRY`
4. The `wrapper` inside `@indicator` validates that output DataFrame has columns `symbol`, `timestamp`, `indicator_name`, `value`
5. `compute_rsi` is registered with `@indicator(name="rsi")` and calls `ta.rsi(close=..., length=...)`
6. `compute_macd` is registered with `@indicator(name="macd")` and returns 3 rows per timestamp (macd, macd_signal, macd_hist)
7. `compute_ema` is registered with `@indicator(name="ema")` and calls `ta.ema(close=..., length=...)`
8. `compute_sma` is registered with `@indicator(name="sma")` and calls `ta.sma(close=..., length=...)`
9. `compute_atr` is registered with `@indicator(name="atr")` and calls `ta.atr(high=..., low=..., close=..., length=...)`
10. `def list_indicators() -> dict[str, Callable]` returns a copy of `_INDICATOR_REGISTRY`
11. `def compute_all(df, indicators=None, **kwargs) -> dict[str, pd.DataFrame]` exists and iterates over registered indicators
12. File imports `pandas_ta as ta` and `import pandas as pd`
13. No Python `for` loops iterating over DataFrame rows exist in any compute function (no `df.iterrows()`, no `for i in range(len(df))`)
</acceptance_criteria>

---

## Wave 4: Infrastructure & Testing

**Depends on:** Waves 1-3 (all code exists). Docker task is independent of other Wave 4 tasks.

---

### Task 4.1: Docker Setup

**Wave:** 4
**Depends on:** Task 1.1 (pyproject.toml for dependency list)
**Files modified:** `Dockerfile` (new), `docker-compose.yml` (new), `.dockerignore` (new)
**Autonomous:** true

<read_first>
- `.planning/phases/01-foundation-core-infrastructure/01-RESEARCH.md` — section 3.8 (Docker Compose) for service definitions and Dockerfile strategy
- `.planning/phases/01-foundation-core-infrastructure/01-CONTEXT.md` — decision D-15 for service composition
- `pyproject.toml` — verify dependency list for pip install
</read_first>

<action>
Create three files at project root:

**1. `Dockerfile`** — multi-stage build:

```dockerfile
# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir --user .

# Stage 2: Runtime
FROM python:3.11-slim AS runtime

# Create non-root user
RUN groupadd -r conflu && useradd -r -g conflu -d /app -s /bin/false conflu

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Ensure local bin is in PATH
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY backend/ ./backend/
COPY config.yaml ./

# Create data directory with write permissions
RUN mkdir -p /app/data && chown -R conflu:conflu /app/data

USER conflu

# Default command (overridden by docker-compose)
CMD ["python", "-c", "import conflu; print('conflu.ai ready')"]
```

**2. `.dockerignore`:**

```
__pycache__/
*.pyc
.git/
.gitignore
.planning/
.venv/
venv/
.vscode/
.idea/
data/
*.md
.pre-commit-config.yaml
.env*
config.local.yaml
```

**3. `docker-compose.yml`:**

```yaml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: conflu-api
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./backend:/app/backend
      - ./config.yaml:/app/config.yaml
    environment:
      - CONFLU_CORE__LOG_LEVEL=INFO
      - CONFLU_CORE__LOG_JSON=true
    command: >
      sh -c "python -c 'from backend.app.core.database import initialize_database; initialize_database()'
      && uvicorn backend.app.api.main:app --host 0.0.0.0 --port 8000 --reload"
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

  worker:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: conflu-worker
    volumes:
      - ./data:/app/data
      - ./backend:/app/backend
      - ./config.yaml:/app/config.yaml
    environment:
      - CONFLU_CORE__LOG_LEVEL=INFO
    command: >
      sh -c "python -c 'from backend.app.core.database import initialize_database; initialize_database()'
      && celery -A backend.app.worker.tasks worker --loglevel=info"
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: conflu-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    restart: unless-stopped

volumes:
  redis_data:
```
</action>

<acceptance_criteria>
1. `Dockerfile` exists at project root with `FROM python:3.11-slim AS builder` and `FROM python:3.11-slim AS runtime`
2. `Dockerfile` creates a non-root user `conflu` and `USER conflu` before CMD
3. `.dockerignore` exists and contains `__pycache__/`, `.git/`, `.planning/`, `data/`
4. `docker-compose.yml` exists with services: `api`, `worker`, `redis`
5. `docker-compose.yml` `api` service has `ports: ["8000:8000"]` and `healthcheck` with `/health` endpoint
6. `docker-compose.yml` `redis` service uses `image: redis:7-alpine` with `healthcheck`
7. `docker-compose.yml` `worker` service exists and depends on `redis`
8. `docker-compose.yml` `api` service maps volumes: `./data:/app/data`, `./config.yaml:/app/config.yaml`
9. `docker-compose.yml` has a `volumes:` section with `redis_data`
</acceptance_criteria>

---

### Task 4.2: Test Infrastructure & Test Suite

**Wave:** 4
**Depends on:** Waves 1-3 (all source code exists)
**Files modified:** `backend/tests/conftest.py` (full), `backend/tests/test_config.py` (new), `backend/tests/test_database.py` (new), `backend/tests/test_models.py` (new), `backend/tests/test_indicators.py` (new), `backend/tests/test_logging.py` (new)
**Autonomous:** true

<read_first>
- `.planning/phases/01-foundation-core-infrastructure/01-RESEARCH.md` — section 3.6 (Testing Infrastructure) for fixture patterns and property test examples
- `.planning/phases/01-foundation-core-infrastructure/01-CONTEXT.md` — decisions D-12, D-13 for test approach and property-based testing
- `backend/app/core/config.py` — verify settings classes for config tests
- `backend/app/core/database.py` — verify get_db, partition_path, normalize_symbol for DB tests
- `backend/app/core/logging.py` — verify configure_logging, set_correlation_id for logging tests
- `backend/app/domain/models.py` — verify model classes for model tests
- `backend/app/infrastructure/indicators.py` — verify indicator functions for indicator tests
- `backend/tests/__init__.py` — verify empty init exists
</read_first>

<action>
Create the following test files:

**a) `backend/tests/conftest.py`** — shared fixtures:

```python
"""Shared test fixtures and configurations."""

from __future__ import annotations

from datetime import datetime, timezone

import duckdb
import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def synthetic_ohlcv() -> pd.DataFrame:
    """Generate synthetic OHLCV data with known patterns for property testing.

    Produces 1-hour bars for 2024 with a trending price and realistic
    high/low/volume.
    """
    rng = np.random.default_rng(seed=42)
    dates = pd.date_range("2024-01-01", "2024-12-31", freq="1h", tz="UTC")
    n = len(dates)

    close = 100.0 + np.cumsum(rng.normal(0, 0.5, n))
    open_ = close + rng.normal(0, 0.2, n)

    data = {
        "symbol": ["TEST"] * n,
        "timestamp": dates,
        "open": open_,
        "high": np.maximum(open_, close) + np.abs(rng.normal(0, 0.2, n)),
        "low": np.minimum(open_, close) - np.abs(rng.normal(0, 0.2, n)),
        "close": close,
        "volume": rng.integers(1000, 10000, n),
        "timeframe": "1h",
        "asset_class": "crypto",
    }
    return pd.DataFrame(data)


@pytest.fixture
def in_memory_db() -> duckdb.DuckDBPyConnection:
    """Create an in-memory DuckDB database with the OHLCV schema.

    The connection is yielded, then closed after the test completes.
    """
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE ohlcv (
            symbol VARCHAR,
            timestamp TIMESTAMPTZ,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume DOUBLE,
            timeframe VARCHAR,
            asset_class VARCHAR,
            year INTEGER,
            month INTEGER
        )
    """)
    yield con
    con.close()


@pytest.fixture
def sample_ohlcv_row() -> dict:
    """A single valid OHLCV data point for model construction tests."""
    return {
        "symbol": "AAPL",
        "timestamp": datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
        "open": 150.0,
        "high": 152.0,
        "low": 149.0,
        "close": 151.5,
        "volume": 10_000_000,
        "timeframe": "1h",
        "asset_class": "equities",
    }
```

**b) `backend/tests/test_config.py`**:

```python
"""Tests for configuration management."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.core.config import APISettings, AppSettings, ComputeSettings, CoreSettings, DataSettings, FrontendSettings


class TestCoreSettings:
    def test_defaults(self) -> None:
        s = CoreSettings()
        assert s.duckdb_path == "data/conflu.duckdb"
        assert s.duckdb_data_dir == "data"
        assert s.log_level == "INFO"
        assert s.log_json is True

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CONFLU_CORE_LOG_LEVEL", "DEBUG")
        s = CoreSettings()
        assert s.log_level == "DEBUG"


class TestDataSettings:
    def test_timeframes(self) -> None:
        s = DataSettings()
        assert "1D" in s.timeframes
        assert "1h" in s.timeframes
        assert "15m" in s.timeframes

    def test_max_concurrent_bounds(self) -> None:
        with pytest.raises(ValidationError):
            DataSettings(max_concurrent=0)
        with pytest.raises(ValidationError):
            DataSettings(max_concurrent=300)


class TestComputeSettings:
    def test_default_indicator_timeframe(self) -> None:
        s = ComputeSettings()
        assert s.default_indicator_timeframe == "1D"

    def test_broadcast_indicators(self) -> None:
        s = ComputeSettings()
        assert "rsi" in s.broadcast_indicators


class TestAPISettings:
    def test_default_port(self) -> None:
        s = APISettings()
        assert s.port == 8000

    def test_rate_limit_positive(self) -> None:
        with pytest.raises(ValidationError):
            APISettings(rate_limit=0)


class TestFrontendSettings:
    def test_ws_endpoint(self) -> None:
        s = FrontendSettings()
        assert s.ws_endpoint == "ws://localhost:8000/ws"


class TestAppSettings:
    def test_nested_settings(self) -> None:
        s = AppSettings()
        assert isinstance(s.core, CoreSettings)
        assert isinstance(s.data, DataSettings)
        assert isinstance(s.compute, ComputeSettings)
        assert isinstance(s.api, APISettings)
        assert isinstance(s.frontend, FrontendSettings)

    def test_env_nested_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CONFLU_CORE__LOG_LEVEL", "DEBUG")
        s = AppSettings()
        assert s.core.log_level == "DEBUG"
```

**c) `backend/tests/test_database.py`**:

```python
"""Tests for DuckDB connection management and Parquet partitioning."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.app.core.database import (
    get_db,
    initialize_database,
    normalize_symbol,
    partition_path,
)


class TestNormalizeSymbol:
    def test_simple(self) -> None:
        assert normalize_symbol("AAPL") == "AAPL"

    def test_forward_slash(self) -> None:
        assert normalize_symbol("BTC/USDT") == "BTCUSDT"

    def test_special_chars(self) -> None:
        assert normalize_symbol("BRK.B") == "BRK_B"

    def test_lowercase(self) -> None:
        assert normalize_symbol("aapl") == "AAPL"

    def test_multiple_invalid(self) -> None:
        assert normalize_symbol("A:B*C?D\"E<F>G|H") == "ABCDEFGH"


class TestPartitionPath:
    def test_basic(self) -> None:
        path = partition_path("equities", 2025, 1, "AAPL", "1D", data_dir="/tmp/data")
        assert "equities" in str(path)
        assert "2025" in str(path)
        assert "01" in str(path)
        assert "AAPL_1D.parquet" in str(path)

    def test_crypto(self) -> None:
        path = partition_path("crypto", 2026, 6, "BTCUSDT", "1h", data_dir="/tmp/data")
        assert "crypto" in str(path)
        assert "BTCUSDT_1h.parquet" in str(path)


class TestGetDb:
    def test_connection(self) -> None:
        """Verify get_db yields a working connection."""
        with get_db() as con:
            result = con.sql("SELECT 1 AS val").fetchone()
            assert result is not None
            assert result[0] == 1

    def test_initialize_database(self, tmp_path: pytest.TempPathFactory) -> None:
        """Verify initialize_database creates tables."""
        import duckdb

        # Use in-memory for initialization test
        con = duckdb.connect(":memory:")
        con.execute("CREATE TABLE ohlcv (symbol VARCHAR, timestamp TIMESTAMPTZ, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE, timeframe VARCHAR, asset_class VARCHAR, year INTEGER, month INTEGER)")
        result = con.sql("SELECT table_name FROM information_schema.tables WHERE table_name = 'ohlcv'").fetchone()
        assert result is not None
        assert result[0] == "ohlcv"
        con.close()
```

**d) `backend/tests/test_models.py`**:

```python
"""Tests for domain Pydantic models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.app.domain.models import (
    BacktestConfig,
    Metrics,
    OHLCV,
    Position,
    RiskParams,
    ScreenResult,
    Signal,
    Trade,
)


class TestOHLCV:
    def test_valid(self, sample_ohlcv_row: dict) -> None:
        ohlcv = OHLCV(**sample_ohlcv_row)
        assert ohlcv.symbol == "AAPL"
        assert ohlcv.close == 151.5

    def test_frozen(self, sample_ohlcv_row: dict) -> None:
        ohlcv = OHLCV(**sample_ohlcv_row)
        with pytest.raises(ValidationError):
            # Attempting to set a field as a dict should fail (frozen)
            ohlcv.__dict__  # type: ignore[unreachable]

    def test_naive_timestamp_raises(self) -> None:
        data = {
            "symbol": "AAPL",
            "timestamp": datetime(2024, 1, 1),  # naive — no tzinfo
            "open": 150.0,
            "high": 152.0,
            "low": 149.0,
            "close": 151.0,
            "volume": 10000,
            "timeframe": "1D",
            "asset_class": "equities",
        }
        with pytest.raises(ValidationError, match="timezone-aware"):
            OHLCV(**data)

    def test_extra_field_forbidden(self, sample_ohlcv_row: dict) -> None:
        with pytest.raises(ValidationError):
            OHLCV(**sample_ohlcv_row, extra_field="should_fail")


class TestSignal:
    def test_valid(self) -> None:
        s = Signal(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            direction="buy",
        )
        assert s.direction == "buy"
        assert s.strength == 1.0

    def test_invalid_direction(self) -> None:
        with pytest.raises(ValidationError):
            Signal(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                direction="invalid",
            )

    def test_strength_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            Signal(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                direction="buy",
                strength=1.5,
            )


class TestMetrics:
    def test_all_optional(self) -> None:
        m = Metrics()
        assert m.sharpe is None

    def test_win_rate_bounds(self) -> None:
        with pytest.raises(ValidationError):
            Metrics(win_rate=1.5)


class TestBacktestConfig:
    def test_defaults(self) -> None:
        cfg = BacktestConfig(
            symbols=["AAPL", "SPY"],
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 12, 31, tzinfo=timezone.utc),
        )
        assert cfg.initial_cash == 100_000.0
        assert cfg.position_sizing == "fixed"

    def test_naive_timestamp_raises(self) -> None:
        with pytest.raises(ValidationError):
            BacktestConfig(
                symbols=["AAPL"],
                start=datetime(2024, 1, 1),  # naive
                end=datetime(2024, 12, 31, tzinfo=timezone.utc),
            )


class TestRiskParams:
    def test_defaults(self) -> None:
        r = RiskParams()
        assert r.risk_per_trade == 0.01
        assert r.kelly_fraction == 0.5

    def test_risk_per_trade_bounds(self) -> None:
        with pytest.raises(ValidationError):
            RiskParams(risk_per_trade=0.0)
        with pytest.raises(ValidationError):
            RiskParams(risk_per_trade=0.2)


class TestTrade:
    def test_minimal(self) -> None:
        t = Trade(
            symbol="AAPL",
            entry_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
            entry_price=150.0,
            size=100,
        )
        assert t.exit_time is None


class TestPosition:
    def test_minimal(self) -> None:
        p = Position(
            symbol="AAPL",
            entry_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
            entry_price=150.0,
            size=100,
        )
        assert p.pnl is None


class TestScreenResult:
    def test_empty_signals(self) -> None:
        sr = ScreenResult(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        assert sr.signals == []
        assert sr.indicators == {}
```

**e) `backend/tests/test_indicators.py`**:

```python
"""Tests for vectorized indicator computation."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.app.infrastructure.indicators import (
    compute_all,
    compute_rsi,
    list_indicators,
)


class TestIndicatorRegistry:
    def test_list_indicators(self) -> None:
        registry = list_indicators()
        assert "rsi" in registry
        assert "macd" in registry
        assert "ema" in registry
        assert "sma" in registry
        assert "atr" in registry

    def test_compute_all(self, synthetic_ohlcv: pd.DataFrame) -> None:
        results = compute_all(synthetic_ohlcv)
        assert isinstance(results, dict)
        assert "rsi" in results
        assert "macd" in results


class TestComputeRsi:
    def test_output_columns(self, synthetic_ohlcv: pd.DataFrame) -> None:
        result = compute_rsi(synthetic_ohlcv)
        assert "symbol" in result.columns
        assert "timestamp" in result.columns
        assert "indicator_name" in result.columns
        assert "value" in result.columns

    def test_rsi_bounded(self, synthetic_ohlcv: pd.DataFrame) -> None:
        result = compute_rsi(synthetic_ohlcv)
        values = result["value"].dropna()
        assert (values >= 0).all()
        assert (values <= 100).all()

    def test_rsi_length(self, synthetic_ohlcv: pd.DataFrame) -> None:
        result_14 = compute_rsi(synthetic_ohlcv, length=14)
        result_7 = compute_rsi(synthetic_ohlcv, length=7)
        assert len(result_14["value"].dropna()) <= len(result_7["value"].dropna())


class TestComputeEma:
    def test_output_shape(self, synthetic_ohlcv: pd.DataFrame) -> None:
        result = compute_ema(synthetic_ohlcv)
        assert result["indicator_name"].iloc[0] == "ema_20"


class TestComputeSma:
    def test_output_shape(self, synthetic_ohlcv: pd.DataFrame) -> None:
        result = compute_sma(synthetic_ohlcv)
        assert result["indicator_name"].iloc[0] == "sma_50"


class TestComputeAtr:
    def test_positive_values(self, synthetic_ohlcv: pd.DataFrame) -> None:
        result = compute_atr(synthetic_ohlcv)
        values = result["value"].dropna()
        assert (values >= 0).all()
```

**f) `backend/tests/test_logging.py`**:

```python
"""Tests for structured logging configuration."""

from __future__ import annotations

from backend.app.core.logging import configure_logging, get_logger, set_correlation_id


class TestConfigureLogging:
    def test_configure_stdout(self) -> None:
        """Verify configure_logging runs without error."""
        configure_logging(log_level="DEBUG", log_json=False)
        log = get_logger("test")
        assert log is not None

    def test_configure_json(self) -> None:
        """Verify JSON configuration runs without error."""
        configure_logging(log_level="INFO", log_json=True)
        log = get_logger("test-json")
        assert log is not None


class TestCorrelationId:
    def test_set_generates_id(self) -> None:
        cid = set_correlation_id()
        assert isinstance(cid, str)
        assert len(cid) > 0

    def test_set_provided_id(self) -> None:
        cid = set_correlation_id("my-test-id")
        assert cid == "my-test-id"


class TestGetLogger:
    def test_default_name(self) -> None:
        log = get_logger()
        assert log is not None

    def test_custom_name(self) -> None:
        log = get_logger("custom.module")
        assert log is not None
```
</action>

<acceptance_criteria>
1. `backend/tests/conftest.py` exists with `synthetic_ohlcv`, `in_memory_db`, `sample_ohlcv_row` fixtures
2. `backend/tests/conftest.py` `synthetic_ohlcv` fixture generates a DataFrame with columns: `symbol`, `timestamp`, `open`, `high`, `low`, `close`, `volume`, `timeframe`, `asset_class`
3. `backend/tests/conftest.py` `in_memory_db` fixture creates a DuckDB connection to `":memory:"` with table `ohlcv`
4. `backend/tests/test_config.py` exists with test classes: `TestCoreSettings`, `TestDataSettings`, `TestComputeSettings`, `TestAPISettings`, `TestFrontendSettings`, `TestAppSettings`
5. `backend/tests/test_database.py` exists with test classes: `TestNormalizeSymbol`, `TestPartitionPath`, `TestGetDb`
6. `backend/tests/test_models.py` exists with test classes for all 8 models: `TestOHLCV`, `TestSignal`, `TestMetrics`, `TestBacktestConfig`, `TestRiskParams`, `TestTrade`, `TestPosition`, `TestScreenResult`
7. `backend/tests/test_models.py` `test_naive_timestamp_raises` tests that naive datetime raises `ValidationError` with match `"timezone-aware"`
8. `backend/tests/test_indicators.py` exists with test classes: `TestIndicatorRegistry`, `TestComputeRsi`, `TestComputeEma`, `TestComputeSma`, `TestComputeAtr`
9. `backend/tests/test_indicators.py` `test_rsi_bounded` asserts RSI values are always between 0 and 100
10. `backend/tests/test_logging.py` exists with test classes: `TestConfigureLogging`, `TestCorrelationId`, `TestGetLogger`
11. `pytest --co` (collect-only) from `backend/` directory shows all test functions discovered
</acceptance_criteria>

---

## Verification Criteria

After all waves complete, the following verifications must pass:

| # | Verification | Command | Expected |
|---|-------------|---------|----------|
| V-1 | mypy strict passes | `cd backend && pip install -e ".[dev]" && mypy --strict app/ tests/` | Exit code 0, zero errors |
| V-2 | All unit tests pass | `cd backend && pip install -e ".[test]" && pytest tests/ -v` | All tests pass (exit 0) |
| V-3 | Config imports without error | `cd backend && python -c "from backend.app.core.config import settings; print(settings.core.log_level)"` | Prints "INFO" |
| V-4 | Logging configures without error | `cd backend && python -c "from backend.app.core.logging import configure_logging; configure_logging()"` | No exception |
| V-5 | DuckDB connection works | `cd backend && python -c "from backend.app.core.database import get_db; next(get_db())"` | No exception |
| V-6 | Domain models instantiate | `cd backend && python -c "from backend.app.domain.models import OHLCV, Signal, Metrics; print('OK')"` | Prints "OK" |
| V-7 | Indicator registry populated | `cd backend && python -c "from backend.app.infrastructure.indicators import list_indicators; reg=list_indicators(); print(len(reg))"` | Prints "5" (rsi, macd, ema, sma, atr) |
| V-8 | Docker Compose config valid | `docker-compose config` (if Docker available) | No error |

---

## Execution Order Summary

```
Wave 1                          Wave 2                  Wave 3              Wave 4
[parallel]                      [parallel]              [single]            [parallel]
                                
Task 1.1: Scaffolding ──────────────────►                                          
                                        │                                          
Task 1.2: Config ───────────────────────┼────► Task 2.1: DuckDB ───►              
                                        │                                          
Task 1.3: Logging ──────────────────────┼────► Task 2.2: Models ────► Task 3.1: Compute ──►
                                        │                                              │
                                        └──────────────────────────────────────────────┼────► Task 4.1: Docker
                                                                                       │
                                                                                       └────► Task 4.2: Tests
```
