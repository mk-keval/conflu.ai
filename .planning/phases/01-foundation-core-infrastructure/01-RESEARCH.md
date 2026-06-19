# Phase 1: Foundation & Core Infrastructure — Research

**Created:** 2026-06-18
**Status:** Complete
**Context:** Greenfield project on branch `feat/conflu-ai-platform`

---

## Table of Contents

1. [Project State & Codebase Assessment](#1-project-state--codebase-assessment)
2. [Dependency Landscape & Version Guidance](#2-dependency-landscape--version-guidance)
3. [Module-by-Module Research](#3-module-by-module-research)
   - 3.1 Configuration Management (Pydantic Settings + YAML)
   - 3.2 DuckDB Connection Pool & Parquet Storage
   - 3.3 Vectorized Compute Primitives (vectorbt + pandas-ta)
   - 3.4 Domain Models (Pydantic)
   - 3.5 Structured Logging (structlog)
   - 3.6 Testing Infrastructure
   - 3.7 Type Safety Configuration
   - 3.8 Docker Compose
4. [Integration Points & Risky Areas](#4-integration-points--risky-areas)
5. [Open Questions for Planning](#5-open-questions-for-planning)

---

## 1. Project State & Codebase Assessment

### Current State
| Aspect | Status |
|--------|--------|
| Code | **Greenfield** — zero Python files, zero config files |
| Directory structure | Stubs exist: `backend/app/{core,domain,infrastructure,api}`, `backend/tests/`, `frontend/src/{components,hooks,lib}` |
| Git branch | `feat/conflu-ai-platform` |
| Config files | None |
| Architecture decisions | 17 decisions documented in CONTEXT.md (D-01 through D-17) |
| Requirements | 7 functional (FR-001–FR-007) + 4 non-functional (NFR-001–NFR-004) |

### What Actually Exists
```
C:\_Code\conflu.ai\
├── .planning/            # GSD planning artifacts (discussion, context, roadmap)
├── backend/
│   ├── app/
│   │   ├── core/          # EMPTY
│   │   ├── domain/        # EMPTY
│   │   ├── infrastructure/ # EMPTY
│   │   └── api/           # EMPTY
│   └── tests/             # EMPTY
├── frontend/
│   └── src/
│       ├── components/    # EMPTY
│       ├── hooks/         # EMPTY
│       └── lib/           # EMPTY
├── PROJECT.md
├── REQUIREMENTS.md
└── STATE.md
```

**Key insight:** Every module directory is empty. Phase 1 must create all foundation files from scratch — no refactoring, no migration.

### Downstream Dependencies
| Future Phase | Depends on Phase 1 For |
|---|---|
| Phase 2 (Data Ingestion) | DuckDB pool, Parquet schema, config, logging |
| Phase 3 (Screener) | Indicator registry, compute primitives, logging |
| Phase 4 (Backtest) | vectorbt primitives, domain models, logging |
| Phase 5 (Risk) | Domain models, compute primitives, config |
| Phase 6 (API) | Config, logging, domain models |
| Phase 7 (Frontend) | — (separate JS/TS stack) |

---

## 2. Dependency Landscape & Version Guidance

### Core Dependencies (researched from current docs)

| Library | ID | Purpose | Key API Patterns |
|---|---|---|---|
| `pydantic-settings` | `/pydantic/pydantic-settings` | Config management | `YamlConfigSettingsSource`, `SettingsConfigDict(yaml_file=...)`, `env_prefix` |
| `duckdb` | `/duckdb/duckdb-python` | OLAP database, Parquet I/O | `duckdb.connect()` context manager, `COPY TO/FROM parquet`, `to_parquet()` |
| `vectorbt` | `/websites/vectorbt_dev` | Vectorized backtesting, indicators | `IndicatorFactory`, `Data.pivot()`, `from_apply_func`, `flex_col_param_config` |
| `pandas-ta` | `/freqtrade/pandas-ta` | 130+ technical indicators | `df.ta.indicator(...)`, `df.ta(kind='rsi')`, `df.ta.strategy(...)` |
| `structlog` | `/hynek/structlog` | Structured logging | `merge_contextvars`, `JSONRenderer`, `TimeStamper(fmt="iso")`, `bind_contextvars` |
| `pydantic` | `/pydantic/pydantic` | Domain models, validation | `BaseModel`, `ConfigDict(frozen=True, extra='forbid')`, `field_validator` |
| `pytest` | — | Test runner | `pytest-asyncio`, `hypothesis`, `conftest.py` fixtures |

### Version Guidance

Based on current documentation research, the following versions and import patterns are current:

**pydantic-settings v2.x:**
- Import from `pydantic_settings` (not from `pydantic`)
- Configuration sources: `YamlConfigSettingsSource` for YAML files
- Customize source order via `settings_customise_sources` classmethod
- Supports `yaml_file`, `yaml_config_section` in `model_config`
- `pip install pydantic-settings[yaml]` for PyYAML support

**DuckDB Python:**
- Context manager: `with duckdb.connect(":memory:", read_only=False) as con:`
- `con.sql("SELECT ...")` returns relation objects
- `con.execute("INSERT ...")` for DML
- Parquet write: `con.sql("COPY (FROM table) TO 'file.parquet' (FORMAT parquet)")`
- Parquet read: `con.sql("SELECT * FROM 'file.parquet'")` or `read_parquet('file.parquet')`

**vectorbt:**
- `vbt.IndicatorFactory` with `input_names`, `param_names`, `output_names`
- `from_apply_func` for custom indicators with Numba JIT
- Flexible broadcasting via `flex_col_param_config` / `flex_elem_param_config` in `param_settings`
- `vbt.Data.pivot()` for multi-timeframe reshaping
- No explicit Python loops — all operations vectorized over columns and rows

**pandas-ta:**
- Import: `import pandas_ta as ta`
- Usage: `df.ta.rsi(close='close', length=14)` returns Series
- Or: `df.ta(kind='rsi', length=14)` — adds column to DataFrame with `append=True`
- Strategy composition: `ta.Strategy("name", [...indicators...])` then `df.ta.strategy(strategy)`
- 130+ indicators available via `df.ta.indicators()`

**structlog:**
- Newer API: configure via `structlog.configure(processors=[...])`
- Key processors: `merge_contextvars`, `stdlib.add_log_level`, `TimeStamper(fmt="iso")`, `JSONRenderer()`
- Context vars: `bind_contextvars(key=val)`, `unbind_contextvars("key")`, `bound_contextvars(key=val)`
- Caching: `cache_logger_on_first_use=True`
- Callsite params: `CallsiteParameterAdder([FILENAME, FUNC_NAME, LINENO])`

---

## 3. Module-by-Module Research

### 3.1 Configuration Management

**Decision refs:** D-01, D-02

#### Pattern from pydantic-settings docs

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import YamlConfigSettingsSource

class CoreSettings(BaseSettings):
    model_config = SettingsConfigDict(
        yaml_file='config/config.yaml',
        env_prefix='CONFLU_',
        env_file='.env',
        env_nested_delimiter='__',
    )
    # fields...
```

**Key findings:**
- `yaml_file` in `SettingsConfigDict` is the simplest approach (v2.x)
- `settings_customise_sources` for custom source priority: CLI > env > yaml_local > yaml > defaults
- Nested models work: `DatabaseSettings` as a field of `Settings`
- Environment variables override YAML when `env_prefix` is set
- PyYAML is the underlying parser — installed via `pydantic-settings[yaml]`

**Recommended approach for conflu.ai:**

Layer-specific settings classes, each in `backend/app/core/config.py`:

| Config Class | Fields | Section in YAML |
|---|---|---|
| `CoreSettings` | `duckdb_path`, `log_level`, `log_json` | `core` |
| `DataSettings` | `screener_sources`, `timeframes`, `assets` | `data` |
| `ComputeSettings` | `vectorbt_params`, `pandas_ta_indicators` | `compute` |
| `APISettings` | `host`, `port`, `cors_origins`, `rate_limit` | `api` |
| `FrontendSettings` | `ws_endpoint`, `chart_config` | `frontend` |

A top-level `AppSettings` that aggregates all layer settings and configures the YAML source:

```python
class AppSettings(BaseSettings):
    core: CoreSettings = CoreSettings()
    data: DataSettings = DataSettings()
    compute: ComputeSettings = ComputeSettings()
    api: APISettings = APISettings()
    frontend: FrontendSettings = FrontendSettings()

    @classmethod
    def settings_customise_sources(cls, ...):
        # Priority: env > config.local.yaml > config.yaml
        ...
```

**Risks:**
- YAML section-based loading requires careful nesting in `settings_customise_sources`
- Environment variable override for nested models uses `__` delimiter: `CONFLU_CORE__DUCKDB_PATH`
- Must decide: one YAML with sections vs separate YAML files per layer

### 3.2 DuckDB Connection Pool & Parquet Storage

**Decision refs:** D-03, D-04, D-05

#### Connection Management Pattern

DuckDB is embedded (in-process) — there is no traditional "connection pool" like PostgreSQL. Instead:

1. **Thread-local connections** — DuckDB supports multiple connections to the same database file. Each thread/async task gets its own connection.
2. **Context manager** — `with duckdb.connect(path) as con:` ensures cleanup.
3. **Read-only vs read-write** — `read_only=True` for queries (no locking), `read_only=False` for ingestion.

Pattern from documented DuckDB API:

```python
import duckdb
from contextlib import contextmanager
from contextvars import ContextVar

_db_conn: ContextVar[duckdb.DuckDBPyConnection | None] = ContextVar("_db_conn", default=None)

@contextmanager
def get_db(read_only: bool = False):
    """Get a DuckDB connection (thread/async-safe)."""
    db_path = settings.core.duckdb_path
    conn = duckdb.connect(db_path, read_only=read_only)
    token = _db_conn.set(conn)
    try:
        yield conn
    finally:
        conn.close()
        _db_conn.reset(token)
```

**Alternative:** Simple connection factory — no pooling needed for an embedded database. DuckDB handles concurrent readers naturally via MVCC. Write transactions serialize.

#### Parquet Partitioning Scheme

```
data/
├── equities/
│   ├── 2025/
│   │   ├── 01/
│   │   │   ├── AAPL_1D.parquet
│   │   │   ├── AAPL_1h.parquet
│   │   │   └── SPY_1D.parquet
│   │   └── 02/
│   └── 2026/
├── crypto/
│   ├── 2025/
│   │   └── 01/
│   │       ├── BTCUSDT_1D.parquet
│   │       └── ETHUSDT_1D.parquet
│   └── 2026/
└── forex/
    └── 2025/
```

**Important considerations from DuckDB docs:**
- DuckDB supports `read_parquet('data/**/*.parquet')` with glob patterns
- Partition pruning works automatically when querying with filters on directory columns
- For best performance, register the directory as a view or table pointing to the partitioned dataset
- `COPY (FROM table) TO 'data/...' (FORMAT PARQUET, PER_THREAD_OUTPUT TRUE)` for writing

#### Schema Definition (SQL DDL)

```sql
CREATE TABLE ohlcv (
    symbol VARCHAR,
    timestamp TIMESTAMPTZ,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE,
    timeframe VARCHAR,
    asset_class VARCHAR
);
CREATE INDEX idx_ohlcv_lookup ON ohlcv (symbol, timeframe, timestamp);
CREATE INDEX idx_ohlcv_partition ON ohlcv (asset_class, year, month);
```

**Risks:**
- `year` and `month` are not stored in the schema above — they must be derived from `timestamp` for partitioning. Option: store them as generated columns or compute at write time.
- DuckDB's `TIMESTAMPTZ` is nanosecond precision — Pandas `datetime64[ns]` maps correctly.
- Multiple processes writing to the same DuckDB file is NOT safe — but Phase 1 only needs single-process access.

### 3.3 Vectorized Compute Primitives

**Decision refs:** D-06, D-07, D-08

#### Indicator Registry Pattern

```python
from functools import wraps
from typing import Callable, Dict
import pandas as pd

_indicator_registry: Dict[str, Callable] = {}

def indicator(name: str, timeframe: str = "1D"):
    """Decorator to register an indicator function."""
    def decorator(func: Callable) -> Callable:
        _indicator_registry[name] = func
        @wraps(func)
        def wrapper(df: pd.DataFrame, *args, **kwargs) -> pd.DataFrame:
            result = func(df, *args, **kwargs)
            # Ensure output has: symbol, timestamp, indicator_name, value columns
            return result
        return wrapper
    return decorator
```

#### pandas-ta usage pattern (from docs):

```python
import pandas_ta as ta

# Method 1: Standalone function
rsi = ta.rsi(close=df['close'], length=14)

# Method 2: DataFrame extension (preferred)
df.ta.rsi(length=14, append=True)  # adds 'RSI_14' column

# Method 3: Generic kind call
df.ta(kind='rsi', length=14, append=True)

# All indicators at once:
df.ta.strategy(ta.CommonStrategy)
```

#### vectorbt IndicatorsFactory pattern (from docs):

```python
import vectorbt as vbt
from numba import njit
import numpy as np

@njit
def custom_indicator_nb(close, window):
    """Custom vectorized indicator with Numba JIT."""
    output = np.full(close.shape, np.nan)
    for col in range(close.shape[1]):
        for i in range(window, close.shape[0]):
            output[i, col] = np.mean(close[i-window:i, col])
    return output

CustomIndicator = vbt.IndicatorFactory(
    input_names=['close'],
    param_names=['window'],
    output_names=['output'],
).from_apply_func(
    custom_indicator_nb,
    param_settings=dict(
        window=vbt.indicators.configs.flex_col_param_config
    )
)
```

#### Multi-Timeframe Broadcasting

vectorbt's `Data.pivot()` reshapes data for broadcasting:

```python
# Given DataFrames for daily and 4h:
daily = vbt.Data.from_df(daily_df)
hour4 = vbt.Data.from_df(hour4_df)

# Compute daily indicators and broadcast to 4h:
daily_indicators = CustomIndicator.run(daily.get('Close'), window=14)
broadcasted = daily_indicators.output.vbt.broadcast_to(hour4.get('Close'))
```

**Risks & Considerations:**

1. **Numba complexity** — `@njit` functions cannot use pandas or most Python objects. vectorbt's `from_apply_func` handles the JIT compilation, but the `apply_func_nb` must be pure NumPy.
2. **pandas-ta outputs Series/DataFrame** — the `@indicator` registry needs to standardize column names and structure.
3. **Zero-loop guarantee** — D-06 explicitly bans Python loops over DataFrame rows. All pandas-ta and vectorbt operations are inherently vectorized, so this is enforced naturally.
4. **Memory pressure** — broadcasting to multiple timeframes multiplies data. Use `flex_2d` mode to avoid materializing full arrays.

### 3.4 Domain Models

**Decision refs:** D-09, D-10

Pydantic v2 frozen models with UTC timestamps:

```python
from datetime import datetime, timezone
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, field_validator

class OHLCV(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')

    symbol: str
    timestamp: datetime  # must be UTC-aware
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str
    asset_class: str

    @field_validator('timestamp')
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError('timestamp must be timezone-aware')
        return v.astimezone(timezone.utc)
```

**Models to create:**

| Model | Fields | Purpose |
|---|---|---|
| `OHLCV` | symbol, timestamp, O, H, L, C, V, timeframe, asset_class | Raw price data |
| `Signal` | symbol, timestamp, direction, strength, source | Buy/sell/hold signal |
| `Position` | symbol, entry_time, exit_time, entry_price, exit_price, size, pnl | Tracked trade |
| `Trade` | symbol, entry/exit timestamps/prices, size, fees, pnl, mae, mfe | Full trade record |
| `Metrics` | sharpe, sortino, calmar, max_dd, win_rate, expectancy, profit_factor, sqn, ulcer | Performance metrics |
| `ScreenResult` | symbol, score, signals, indicators, timestamp | Screener output row |
| `BacktestConfig` | symbols, start/end, initial_cash, fees, slippage, position_sizing, strategy_params | Backtest parameters |
| `RiskParams` | risk_per_trade, max_position_size, atr_period, beta_benchmark, kelly_fraction | Risk configuration |

### 3.5 Structured Logging

**Decision refs:** D-11

Based on current structlog documentation:

```python
import structlog
import logging

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.CallsiteParameterAdder([
            structlog.processors.CallsiteParameter.FILENAME,
            structlog.processors.CallsiteParameter.FUNC_NAME,
            structlog.processors.CallsiteParameter.LINENO,
        ]),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# Configure stdlib logging to use structlog
logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)

# Usage
log = structlog.get_logger("conflu")
bind_contextvars(correlation_id=request_id, phase="ingestion")
log.info("data_fetched", symbol="BTCUSDT", rows=5000, duration_ms=123)
```

**Correlation ID propagation via contextvars:**

```python
from contextvars import ContextVar
from uuid import uuid4

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

def set_correlation_id(cid: str | None = None) -> str:
    cid = cid or str(uuid4())
    correlation_id.set(cid)
    bind_contextvars(correlation_id=cid)
    return cid
```

**Log level mapping:**
| Level | Context | Examples |
|---|---|---|
| `DEBUG` | Compute | Indicator calculations, DataFrame shapes |
| `INFO` | API | Request start/end, data pipeline stage |
| `WARNING` | Rate limits | API throttling, resampling fallback |
| `ERROR` | Failures | Screener fetch failed, query timeout |

### 3.6 Testing Infrastructure

**Decision refs:** D-12, D-13

#### Fixture Strategy

```python
# tests/conftest.py
import pytest
import pandas as pd
import duckdb
import numpy as np
from datetime import datetime, timezone, timedelta

@pytest.fixture
def synthetic_ohlcv() -> pd.DataFrame:
    """Generate synthetic OHLCV data with known patterns for property testing."""
    dates = pd.date_range("2024-01-01", "2024-12-31", freq="1h", tz="UTC")
    n = len(dates)
    data = {
        "symbol": ["TEST"] * n,
        "timestamp": dates,
        "open": 100 + np.cumsum(np.random.randn(n) * 0.5),
        "high": np.nan,  # filled below
        "low": np.nan,
        "close": np.nan,
        "volume": np.random.randint(1000, 10000, n),
        "timeframe": "1h",
        "asset_class": "crypto",
    }
    df = pd.DataFrame(data)
    df["high"] = df[["open", "close"]].max(axis=1) + abs(np.random.randn(n) * 0.2)
    df["low"] = df[["open", "close"]].min(axis=1) - abs(np.random.randn(n) * 0.2)
    df["close"] = df["open"] + np.random.randn(n) * 0.5
    return df

@pytest.fixture
def in_memory_db():
    """Create an in-memory DuckDB for testing."""
    with duckdb.connect(":memory:") as con:
        con.execute("""
            CREATE TABLE ohlcv (
                symbol VARCHAR, timestamp TIMESTAMPTZ, open DOUBLE,
                high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE,
                timeframe VARCHAR, asset_class VARCHAR
            )
        """)
        yield con
```

#### Property Tests with Hypothesis

```python
from hypothesis import given, strategies as st
from hypothesis.extra.pandas import data_frames, column, indexes, range_indexes

@given(
    data_frames([
        column("close", dtype=float, elements=st.floats(min_value=1, max_value=1000)),
    ], index=range_indexes(min_size=50, max_size=500))
)
def test_rsi_bounded(df):
    """RSI must always be 0-100."""
    import pandas_ta as ta
    rsi = ta.rsi(close=df["close"], length=14)
    assert rsi.dropna().between(0, 100).all()
```

#### Test Categories for Phase 1

| Test File | What It Tests | Type |
|---|---|---|
| `test_config.py` | YAML loading, env override, validation errors | Unit |
| `test_database.py` | Connection context manager, CRUD, partition write/read | Integration |
| `test_indicators.py` | Registry registration, pandas-ta wrappers, output shape | Unit + property |
| `test_models.py` | Frozen immutability, UTC validation, serialization | Unit + property |
| `test_logging.py` | Correlation ID propagation, JSON output shape | Unit |

### 3.7 Type Safety Configuration

**Decision refs:** D-14

```toml
# pyproject.toml
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
```

**Important:** `vectorbt` and `pandas-ta` don't have complete type stubs. Must add ignore overrides for these.

### 3.8 Docker Compose

**Decision refs:** D-15

Services and their roles:

| Service | Image | Purpose |
|---|---|---|
| `api` | `conflu-api` (Python 3.11-slim) | FastAPI app (Phase 6, but containerize now) |
| `worker` | same image | Celery worker for async tasks |
| `redis` | `redis:7-alpine` | Cache + message broker |
| `postgres` | `postgres:16-alpine` | Optional — for future auth (can be commented out) |

**Dockerfile strategy:**
- Multi-stage: `python:3.11-slim` as base
- Builder stage: install system deps + pip install
- Runtime stage: copy only installed packages and app code
- Non-root user for security

**Key decisions:**
- Phase 1 containers don't need API code yet — but the Dockerfile and docker-compose should be complete so devs can start the stack
- DuckDB data volume mapped from host for persistence
- structlog logs to stdout (Docker-friendly)
- Healthcheck for Redis/DuckDB availability

---

## 4. Integration Points & Risky Areas

### High Risk

| Area | Risk | Mitigation |
|---|---|---|
| **DuckDB concurrent access** | DuckDB supports multiple readers but serializes writers. Phase 1 single-process, but Phase 2+ may have concurrent ingestion + query. | Use read-only connections for queries, separate connection for writes. Document this limitation. |
| **Numba + vectorbt** | Numba JIT functions (`@njit`) cannot use pandas. The `apply_func_nb` must be pure NumPy. | Keep custom indicators simple in Phase 1. Use pandas-ta for complex indicators. |
| **pandas-ta + Polars compatibility** | D-17 leaves choice open. pandas-ta only works with pandas DataFrames, not Polars. | Default to pandas for compute layer. If Polars is used for I/O, convert to pandas for indicator computation. |

### Medium Risk

| Area | Risk | Mitigation |
|---|---|---|
| **Pydantic Settings YAML loading** | The `yaml_file` and `settings_customise_sources` APIs changed between v1 and v2. | Pin `pydantic-settings>=2.0`. Test config loading in CI. |
| **structlog CallsiteParameterAdder** | Added in structlog v24.x. Older versions lack it. | Pin `structlog>=24.1`. |
| **Hypothesis with large DataFrames** | Property tests can generate enormous inputs. | Use `max_examples=50` for DF tests, set `max_size` limits on strategies. |

### Low Risk

| Area | Risk | Mitigation |
|---|---|---|
| **UTC enforcement** | Data sources may provide naive timestamps. | `@field_validator` catches it at boundary. |
| **Parquet schema evolution** | Adding columns later requires migration. | Use `union_by_name=True` in `read_parquet`. |

---

## 5. Open Questions for Planning

These need resolution before writing PLAN.md:

### Q1: Single YAML vs Per-Layer YAML Files?
D-02 says "separate configs per layer" — does this mean one file with sections (`config.yaml` with `core:`, `data:`, etc.) or separate files (`core.yaml`, `data.yaml`, etc.)?
- **Recommendation:** Single `config.yaml` with top-level sections. Simpler for devs, one env override prefix.

### Q2: Pandas vs Polars as Internal DataFrame?
D-17 leaves this to discretion. pandas-ta requires pandas. vectorbt works with both. For Phase 1, **use pandas as the primary compute DataFrame** since both major libraries depend on it. If we adopt Polars for I/O, convert on compute boundaries.

### Q3: Test Coverage Threshold?
NFR-002 says "95%+ test coverage on compute layer." What threshold for Phase 1 specifically?
- **Recommendation:** 80% for Phase 1 (foundation code is boilerplate-heavy), ramp to 95% in Phase 3 (compute layer).

### Q4: Async Config for DuckDB?
DuckDB's Python API is synchronous. For async FastAPI, should connections be run in a thread pool (`run_in_executor`)?
- **Recommendation:** Yes. Wrap `get_db()` with async wrapper using `asyncio.to_thread()` or `anyio.to_thread.run_sync()`.

### Q5: Pre-commit Hooks?
Should we configure `pre-commit` with `ruff`, `mypy`, and `black` in Phase 1?
- **Recommendation:** Yes. Catches issues before CI. Low cost, high value.

### Q6: DuckDB Data Directory Location?
Where should partitioned Parquet files live?
- **Recommendation:** `data/` at project root (gitignored), configurable via `core.duckdb_data_dir`.

---

## Summary of Technology Choices

| Concern | Choice | Rationale |
|---|---|---|
| Config framework | pydantic-settings | Type-safe, YAML + env, industry standard |
| Database | DuckDB (embedded) | No external DB needed, columnar, Parquet-native |
| Compute | vectorbt + pandas-ta | Battle-tested, zero loops, vectorized |
| Domain models | Pydantic v2 frozen | Immutability, serialization, validation |
| Logging | structlog + JSON | Structured, correlation IDs, production-ready |
| Testing | pytest + asyncio + hypothesis | Property-based, async support, standard |
| Type checking | mypy --strict | Maximum safety, project constraint |
| Containerization | Docker multi-stage | Dev/prod parity, small images |
| Internal DataFrames | pandas | pandas-ta/vectorbt require it |
| DataFrame I/O | Polars (optional) | Performance for Parquet I/O only |

---

*This research feeds into `01-PLAN.md`. All documentation references verified against current (June 2026) library APIs.*
