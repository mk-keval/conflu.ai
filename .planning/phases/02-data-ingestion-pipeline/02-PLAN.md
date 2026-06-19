# Phase 2: Data Ingestion Pipeline — Plan

**Phase:** 2 — Data Ingestion Pipeline
**Status:** Planned
**Date:** 2026-06-18
**Branch:** `feat/conflu-ai-platform`

---

## must_haves (Goal-Backward Verification)

Every plan task, when completed, must collectively satisfy these must_haves. Verify after execution:

| # | Must Have | Verifiable With |
|---|-----------|----------------|
| MH-1 | `tradingview-screener >=3.2,<4` in pyproject.toml dependencies | `grep "tradingview-screener" pyproject.toml` |
| MH-2 | `httpx >=0.27,<1` in pyproject.toml dependencies | `grep "httpx" pyproject.toml` |
| MH-3 | `DataSettings` has `exchange_prefixes`, `asset_class_markets`, `asset_class_timezones`, `symbol_exchange_overrides`, `tv_session_id` fields | `grep "exchange_prefixes" backend/app/core/config.py` and check 5 fields |
| MH-4 | `IngestionSettings` class exists with retry/backoff/circuit-breaker params | `grep "class IngestionSettings" backend/app/core/config.py` |
| MH-5 | `backend/app/infrastructure/ingest/` package exists with files: `__init__.py`, `cli.py`, `scanner.py`, `fetcher.py`, `writer.py`, `symbol_map.py`, `quality.py`, `metrics.py`, `models.py` | `Get-ChildItem -Path backend/app/infrastructure/ingest/ -Name` lists all 9 files |
| MH-6 | `scan_symbols()` thread-pool wrapper in scanner.py with retry logic | `grep "async def scan_symbols" backend/app/infrastructure/ingest/scanner.py` |
| MH-7 | `IngestionFetcher` class in fetcher.py with semaphore concurrency (default 50) and batch size 100 | `grep "class IngestionFetcher" backend/app/infrastructure/ingest/fetcher.py` and `grep "Semaphore\|BATCH_SIZE"` |
| MH-8 | `write_incremental()` in writer.py uses staging-table dedup pattern and DuckDB COPY | `grep "def write_incremental" backend/app/infrastructure/ingest/writer.py` |
| MH-9 | `validate_ohlcv()` in quality.py validates: OHLC consistency, volume >= 0, price > 0, no NaN | `grep "def validate_ohlcv" backend/app/infrastructure/ingest/quality.py` |
| MH-10 | `TickerResolver` class in symbol_map.py maps internal symbol -> TV ticker with exchange prefix | `grep "class TickerResolver" backend/app/infrastructure/ingest/symbol_map.py` |
| MH-11 | `run_ingestion()` orchestrator in `__init__.py` coordinates scanner, fetcher, writer, quality | `grep "async def run_ingestion" backend/app/infrastructure/ingest/__init__.py` |
| MH-12 | CLI entry point at `python -m backend.app.infrastructure.ingest` with `--asset-class`, `--timeframe`, `--dry-run`, `--max-concurrent`, `--health` flags | `grep "add_argument.*asset-class" backend/app/infrastructure/ingest/cli.py` |
| MH-13 | `IngestionReport` Pydantic model with fields: `correlation_id`, `started_at`, `duration_ms`, `symbols_processed`, `candles_written`, `symbols_failed`, `error_rate` | `grep "class IngestionReport" backend/app/infrastructure/ingest/models.py` |
| MH-14 | `symbol_metadata` table DDL exists with columns: `symbol`, `asset_class`, `exchange`, `tv_ticker`, `timezone`, `active`, `added_at`, `last_seen_at` | `grep "symbol_metadata" backend/app/core/database.py` |
| MH-15 | `ingestion_health` table DDL exists for health tracking | `grep "ingestion_health" backend/app/core/database.py` |
| MH-16 | All module files have `from __future__ import annotations` as first import | Each file starts with annotations import |
| MH-17 | All new modules pass `mypy --strict` | `cd backend && mypy --strict app/` exits 0 |
| MH-18 | Tests exist for scanner, symbol_map, quality, fetcher, writer, metrics, CLI | `Get-ChildItem -Path backend/tests/ -Name` shows test files for each module |
| MH-19 | config.yaml has `commodities` and `indices` asset classes with default symbols | `grep "commodities\|indices" config.yaml` |
| MH-20 | `exchange_prefixes` config.yaml block exists under `data:` | `grep "exchange_prefixes" config.yaml` |

---

## Wave 1: Configuration & Dependencies

**No dependencies.** All three tasks run in parallel.

---

### Task 1.1: Add tradingview-screener & httpx Dependencies

**Wave:** 1
**Depends on:** None
**Files modified:** `pyproject.toml`
**Autonomous:** true

<read_first>
- `pyproject.toml` — current dependencies list, existing mypy overrides, tool sections
- `.planning/phases/02-data-ingestion-pipeline/02-RESEARCH.md` — section 10 for exact dependency versions and mypy overrides
- `.planning/phases/02-data-ingestion-pipeline/02-CONTEXT.md` — decision D-19 (httpx deferred, but dep added), D-01 (tradingview-screener)
</read_first>

<action>
Edit `pyproject.toml` at project root with three changes:

**1. Add dependencies** to `[project] dependencies` list (insert after `"pyyaml>=6.0",`):
```toml
    "tradingview-screener>=3.2,<4",
    "httpx>=0.27,<1",
```

**2. Add dev dependency** `pytest-httpx>=0.30` to `[project.optional-dependencies] dev` list (insert after `"pre-commit>=3.6",`):
```toml
    "pytest-httpx>=0.30",
```

**3. Add mypy override** after the existing `module = "duckdb.*"` block:
```toml
[[tool.mypy.overrides]]
module = "tradingview_screener.*"
ignore_missing_imports = true
```
</action>

<acceptance_criteria>
1. `grep "\"tradingview-screener" pyproject.toml` shows `"tradingview-screener>=3.2,<4",`
2. `grep "\"httpx" pyproject.toml` shows `"httpx>=0.27,<1",`
3. `grep "pytest-httpx" pyproject.toml` shows `"pytest-httpx>=0.30",`
4. `grep -A2 "tradingview_screener" pyproject.toml` shows `module = "tradingview_screener.*"` and `ignore_missing_imports = true`
5. `cd backend && pip install -e ".[dev]"` exits 0 (dependencies resolvable)
</acceptance_criteria>

---

### Task 1.2: Extend DataSettings & Add IngestionSettings

**Wave:** 1
**Depends on:** None
**Files modified:** `backend/app/core/config.py`
**Autonomous:** true

<read_first>
- `backend/app/core/config.py` — current `DataSettings` class structure, `AppSettings` nesting
- `.planning/phases/02-data-ingestion-pipeline/02-RESEARCH.md` — sections 5.2 (exchange prefixes), 7 (retry/backoff), Q6 (timezones), Q7 (TV session), Q3 (symbol exchange overrides)
- `.planning/phases/02-data-ingestion-pipeline/02-CONTEXT.md` — decisions D-02, D-03, D-04, D-05, D-06, D-10, D-20
</read_first>

<action>
Edit `backend/app/core/config.py` to:

**1. Add 6 new fields to `DataSettings`:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `exchange_prefixes` | `dict[str, str]` | `{"equities": "NASDAQ:", "crypto": "BINANCE:", "forex": "FX:", "commodities": "COMEX:", "indices": "SP:"}` | Default exchange prefix per asset class for TV ticker |
| `asset_class_markets` | `dict[str, str]` | `{"equities": "america", "crypto": "crypto", "forex": "forex", "commodities": "futures", "indices": "america"}` | TV market name per asset class |
| `asset_class_timezones` | `dict[str, str]` | `{"equities": "America/New_York", "crypto": "UTC", "forex": "UTC", "commodities": "America/New_York", "indices": "America/New_York"}` | Default timezone per asset class |
| `symbol_exchange_overrides` | `dict[str, str]` | `{"SPY": "AMEX:"}` | Per-symbol exchange prefix overrides |
| `tv_session_id` | `str` | `""` | TradingView session cookie for reduced data delay (optional) |
| `batch_size` | `int` | `100` | Symbols per API call (TV limit), ge=1, le=500 |

**2. Add a new `IngestionSettings` class** (insert before `ComputeSettings`):

```python
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
```

**3. Add `IngestionSettings` to `AppSettings`** (insert after `data: DataSettings = DataSettings()`):
```python
    ingestion: IngestionSettings = IngestionSettings()
```

**4. Update `DataSettings.assets` default** to include `commodities` and `indices`:
```python
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
```

**5. Update `DataSettings.screener_sources` default** to include all 5 asset classes:
```python
    screener_sources: list[str] = Field(
        default=["america", "crypto", "forex", "futures"],
        description="Active screener data sources",
    )
```
</action>

<acceptance_criteria>
1. `grep "exchange_prefixes" backend/app/core/config.py` shows field definition with 5 asset classes
2. `grep "asset_class_markets" backend/app/core/config.py` shows field definition
3. `grep "asset_class_timezones" backend/app/core/config.py` shows field definition
4. `grep "symbol_exchange_overrides" backend/app/core/config.py` shows field with `SPY: "AMEX:"` override
5. `grep "tv_session_id" backend/app/core/config.py` shows field with `default=""`
6. `grep "batch_size" backend/app/core/config.py` shows field with `default=100`
7. `grep "class IngestionSettings" backend/app/core/config.py` exists
8. `IngestionSettings` has all 10 fields: `retry_max_attempts`, `retry_base_delay_s`, `retry_max_delay_s`, `retry_backoff_factor`, `retry_jitter`, `circuit_breaker_threshold`, `circuit_breaker_cooldown_s`, `daily_schedule_utc`, `intraday_interval_s`
9. `grep "ingestion: IngestionSettings" backend/app/core/config.py` exists in `AppSettings`
10. `grep "commodities" backend/app/core/config.py` shows default asset list includes `GC1!`, `CL1!`, `SI1!`, `HG1!`
11. `grep "indices" backend/app/core/config.py` shows default asset list includes `SPX`, `NDX`, `DJI`
12. `cd backend && python -c "from backend.app.core.config import settings; print(settings.ingestion.retry_max_attempts)"` prints `3`
</acceptance_criteria>

---

### Task 1.3: Update config.yaml with New Settings

**Wave:** 1
**Depends on:** None
**Files modified:** `config.yaml`
**Autonomous:** true

<read_first>
- `config.yaml` — current structure, existing `data:` section
- `backend/app/core/config.py` — verify new field names and structures from Task 1.2 (ensure config.yaml keys match exactly)
</read_first>

<action>
Edit `config.yaml` to update the `data:` section and add new sections:

**1. Replace the entire `data:` block** with this extended version (adds commodities, indices, exchange config, TV session):

```yaml
data:
  screener_sources:
    - america
    - crypto
    - forex
    - futures
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
    commodities:
      - GC1!
      - CL1!
      - SI1!
      - HG1!
    indices:
      - SPX
      - NDX
      - DJI
  max_concurrent: 50
  batch_size: 100
  exchange_prefixes:
    equities: "NASDAQ:"
    crypto: "BINANCE:"
    forex: "FX:"
    commodities: "COMEX:"
    indices: "SP:"
  asset_class_markets:
    equities: "america"
    crypto: "crypto"
    forex: "forex"
    commodities: "futures"
    indices: "america"
  asset_class_timezones:
    equities: "America/New_York"
    crypto: "UTC"
    forex: "UTC"
    commodities: "America/New_York"
    indices: "America/New_York"
  symbol_exchange_overrides:
    SPY: "AMEX:"
  tv_session_id: ""
```

**2. Add an `ingestion:` section** after the `data:` section (before `compute:`):

```yaml
ingestion:
  retry_max_attempts: 3
  retry_base_delay_s: 1.0
  retry_max_delay_s: 30.0
  retry_backoff_factor: 2.0
  retry_jitter: 0.1
  circuit_breaker_threshold: 5
  circuit_breaker_cooldown_s: 30.0
  daily_schedule_utc: "00:00"
  intraday_interval_s: 300
```
</action>

<acceptance_criteria>
1. `grep "commodities:" config.yaml` shows `commodities:` under `assets:` with `GC1!`, `CL1!`, `SI1!`, `HG1!`
2. `grep "indices:" config.yaml` shows `indices:` under `assets:` with `SPX`, `NDX`, `DJI`
3. `grep "exchange_prefixes:" config.yaml` exists under `data:` with all 5 asset classes
4. `grep "asset_class_markets:" config.yaml` exists with all 5 mappings
5. `grep "asset_class_timezones:" config.yaml` exists with all 5 timezone mappings
6. `grep "symbol_exchange_overrides:" config.yaml` exists with `SPY: "AMEX:"`
7. `grep "tv_session_id:" config.yaml` exists with `""`
8. `grep "ingestion:" config.yaml` exists
9. `grep "retry_max_attempts:" config.yaml` shows `3`
10. `grep "circuit_breaker_threshold:" config.yaml` shows `5`
11. `grep "batch_size:" config.yaml` shows `100`
12. `cd backend && python -c "from backend.app.core.config import settings; print(settings.data.exchange_prefixes['equities'])"` prints `NASDAQ:`
</acceptance_criteria>

---

## Wave 2: Core Ingestion Modules

**Depends on:** Wave 1 (config with exchange_prefixes, markets, timezones exists)

Tasks in Wave 2 can run in parallel after Wave 1 completes.

---

### Task 2.1: Ingestion Package Scaffold & scanner.py

**Wave:** 2
**Depends on:** Task 1.1 (tradingview-screener dependency), Task 1.2 (config with retry params)
**Files modified:**
- `backend/app/infrastructure/ingest/__init__.py` (new — empty, exports populated in Task 4.1)
- `backend/app/infrastructure/ingest/scanner.py` (new)
**Autonomous:** true

<read_first>
- `backend/app/infrastructure/` — verify directory exists with `__init__.py`
- `.planning/phases/02-data-ingestion-pipeline/02-RESEARCH.md` — sections 3.1 (Query API), 3.5 (sync constraint), 4.1 (thread-pool wrapper), 7 (retry, circuit breaker)
- `.planning/phases/02-data-ingestion-pipeline/02-CONTEXT.md` — D-01, D-04, D-05, D-06, D-14, D-15, D-20
- `backend/app/core/config.py` — verify `IngestionSettings` fields for retry params
- `backend/app/core/logging.py` — verify `get_logger()` pattern
</read_first>

<action>
**1. Create directory** `backend/app/infrastructure/ingest/` with an empty `__init__.py`:
```python
# backend/app/infrastructure/ingest/__init__.py
"""Data ingestion pipeline — TradingView scanner, fetcher, writer, quality."""
```

**2. Create `backend/app/infrastructure/ingest/scanner.py`** with:

- `from __future__ import annotations` as first import
- Imports: `asyncio`, `random`, `time`, `collections.abc.Sequence`, `pandas as pd`, `tradingview_screener.Query`, `backend.app.core.config.settings`, `backend.app.core.logging.get_logger`
- Module-level logger: `log = get_logger("conflu.ingest.scanner")`
- `_CIRCUIT_BREAKER_STATE` module variable: `dict` tracking state per market (keys: `"state"` = `"CLOSED"`/`"OPEN"`/`"HALF_OPEN"`, `"failures"` = 0, `"last_failure"` = 0.0)
- `async def scan_symbols(tickers: Sequence[str], columns: Sequence[str], market: str = "america") -> pd.DataFrame`:
  - Check circuit breaker state first (if OPEN and cooldown not elapsed, raise `RuntimeError("Circuit breaker OPEN")`)
  - If `not tickers`, return `pd.DataFrame()`
  - Build `Query()`, call `.select(*columns)`, `.set_tickers(*tickers)`, `.limit(len(tickers))`
  - Wrap `q.get_scanner_data()` in `loop.run_in_executor(None, ...)`
  - On success: reset circuit breaker failures to 0, log with `log.info("scan_completed", market=market, requested=len(tickers), received=len(df))`, return `df`
  - On exception: increment circuit breaker failures, log with `log.exception("scan_failed", market=market, ticker_count=len(tickers))`, re-raise
- `async def scan_with_retry(tickers: Sequence[str], columns: Sequence[str], market: str = "america") -> pd.DataFrame`:
  - Implement retry loop with exponential backoff from config (`settings.ingestion.retry_max_attempts`, `retry_base_delay_s`, `retry_max_delay_s`, `retry_backoff_factor`, `retry_jitter`)
  - Retry on any exception up to `retry_max_attempts` times
  - Add jitter: `delay * (1 + random.uniform(-jitter, jitter))`
  - Log each retry attempt with attempt number and delay
  - After exhausting retries, log `log.error("scan_failed_after_retries", market=market, tickers=len(tickers), attempts=retry_max_attempts)` and re-raise
- `def circuit_breaker_state(market: str) -> dict` — return copy of breaker state for a market
- `def reset_circuit_breaker(market: str) -> None` — reset breaker state for a market

Use the exact retry parameters from `settings.ingestion` dynamically (not hardcoded).
</action>

<acceptance_criteria>
1. `backend/app/infrastructure/ingest/__init__.py` exists and is a valid Python file
2. `backend/app/infrastructure/ingest/scanner.py` exists
3. `grep "async def scan_symbols" backend/app/infrastructure/ingest/scanner.py` exists
4. `grep "async def scan_with_retry" backend/app/infrastructure/ingest/scanner.py` exists
5. `grep "run_in_executor" backend/app/infrastructure/ingest/scanner.py` exists (thread-pool wrapper)
6. `grep "tradingview_screener" backend/app/infrastructure/ingest/scanner.py` shows `from tradingview_screener import Query`
7. `grep "exponential\|backoff\|retry_max_attempts" backend/app/infrastructure/ingest/scanner.py` shows retry logic using config settings
8. `grep "circuit_breaker" backend/app/infrastructure/ingest/scanner.py` shows circuit breaker pattern
9. `grep "log.exception\|log.error\|log.info" backend/app/infrastructure/ingest/scanner.py` shows structured logging
10. `cd backend && python -c "from backend.app.infrastructure.ingest.scanner import scan_symbols, scan_with_retry; print('OK')"` prints `OK`
</acceptance_criteria>

---

### Task 2.2: Symbol Mapping — TickerResolver

**Wave:** 2
**Depends on:** Task 1.2 (exchange_prefixes, symbol_exchange_overrides in config)
**Files modified:** `backend/app/infrastructure/ingest/symbol_map.py` (new)
**Autonomous:** true

<read_first>
- `.planning/phases/02-data-ingestion-pipeline/02-RESEARCH.md` — section 5 (Multi-Asset Class Mapping), tables in 5.1 and 5.2 for ticker format per asset class
- `.planning/phases/02-data-ingestion-pipeline/02-CONTEXT.md` — D-10, D-11
- `backend/app/core/config.py` — verify `DataSettings.exchange_prefixes`, `DataSettings.asset_class_markets`, `DataSettings.symbol_exchange_overrides`, `DataSettings.assets` structure
- `backend/app/core/database.py` — verify `normalize_symbol()` pattern
</read_first>

<action>
Create `backend/app/infrastructure/ingest/symbol_map.py` with:

```python
"""Symbol resolution: internal ↔ TradingView ticker mapping."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

log = get_logger("conflu.ingest.symbol_map")


@dataclass
class AssetClassConfig:
    """Resolved configuration for one asset class."""
    name: str
    market: str
    default_exchange: str
    timezone: str
    symbols: list[str]


class TickerResolver:
    """Resolve internal symbols to TradingView tickers.

    Uses exchange_prefixes from config, with per-symbol overrides.
    """

    def __init__(self) -> None:
        self._build_asset_classes()

    def _build_asset_classes(self) -> None:
        """Build asset class configs from DataSettings."""
        ds = settings.data
        self._asset_classes: dict[str, AssetClassConfig] = {}

        for asset_class, symbols in ds.assets.items():
            market = ds.asset_class_markets.get(asset_class, "america")
            default_exchange = ds.exchange_prefixes.get(asset_class, "")
            timezone = ds.asset_class_timezones.get(asset_class, "UTC")
            self._asset_classes[asset_class] = AssetClassConfig(
                name=asset_class,
                market=market,
                default_exchange=default_exchange,
                timezone=timezone,
                symbols=list(symbols),
            )

    def get_exchange(self, symbol: str, asset_class: str) -> str:
        """Get exchange prefix for a symbol, checking overrides first."""
        overrides = settings.data.symbol_exchange_overrides
        if symbol in overrides:
            return overrides[symbol]
        cfg = self._asset_classes.get(asset_class)
        if cfg is None:
            log.warning("unknown_asset_class", asset_class=asset_class, symbol=symbol)
            return ""
        return cfg.default_exchange

    def to_tv_ticker(self, symbol: str, asset_class: str) -> str:
        """Convert internal symbol to TradingView ticker format.

        Returns: '{EXCHANGE}:{SYMBOL}' (e.g., 'NASDAQ:AAPL', 'BINANCE:BTCUSDT').
        """
        exchange = self.get_exchange(symbol, asset_class)
        return f"{exchange}{symbol}"

    def from_tv_ticker(self, tv_ticker: str) -> tuple[str, str]:
        """Parse a TV ticker into (exchange, symbol).

        Example: 'NASDAQ:AAPL' -> ('NASDAQ', 'AAPL')
        """
        if ":" in tv_ticker:
            parts = tv_ticker.split(":", 1)
            return (parts[0], parts[1])
        return ("", tv_ticker)

    def get_asset_classes(self) -> dict[str, AssetClassConfig]:
        """Return all configured asset classes."""
        return dict(self._asset_classes)

    def get_market_for_asset_class(self, asset_class: str) -> str:
        """Get the TradingView market name for an asset class."""
        cfg = self._asset_classes.get(asset_class)
        return cfg.market if cfg else "america"

    def get_timezone(self, asset_class: str) -> str:
        """Get the default timezone for an asset class."""
        cfg = self._asset_classes.get(asset_class)
        return cfg.timezone if cfg else "UTC"
```

**Also** add a `def refresh()` method that rebuilds asset classes from current config (useful if config changes at runtime).
</action>

<acceptance_criteria>
1. `backend/app/infrastructure/ingest/symbol_map.py` exists
2. `grep "class TickerResolver" backend/app/infrastructure/ingest/symbol_map.py` exists
3. `grep "class AssetClassConfig" backend/app/infrastructure/ingest/symbol_map.py` exists (dataclass)
4. `grep "def to_tv_ticker" backend/app/infrastructure/ingest/symbol_map.py` exists and returns `{exchange}{symbol}`
5. `grep "def from_tv_ticker" backend/app/infrastructure/ingest/symbol_map.py` exists
6. `grep "def get_exchange" backend/app/infrastructure/ingest/symbol_map.py` exists and checks `symbol_exchange_overrides` first
7. `grep "def get_market_for_asset_class" backend/app/infrastructure/ingest/symbol_map.py` exists
8. `grep "def get_timezone" backend/app/infrastructure/ingest/symbol_map.py` exists
9. `grep "def get_asset_classes" backend/app/infrastructure/ingest/symbol_map.py` exists
10. `cd backend && python -c "from backend.app.infrastructure.ingest.symbol_map import TickerResolver; r = TickerResolver(); print(r.to_tv_ticker('AAPL', 'equities'))"` prints `NASDAQ:AAPL`
11. `cd backend && python -c "from backend.app.infrastructure.ingest.symbol_map import TickerResolver; r = TickerResolver(); print(r.to_tv_ticker('SPY', 'equities'))"` prints `AMEX:SPY` (override)
</acceptance_criteria>

---

### Task 2.3: Data Quality Validation

**Wave:** 2
**Depends on:** None
**Files modified:** `backend/app/infrastructure/ingest/quality.py` (new)
**Autonomous:** true

<read_first>
- `.planning/phases/02-data-ingestion-pipeline/02-RESEARCH.md` — section 6.2 (Data Quality Validation Rules) for exact validation rules and code pattern
- `.planning/phases/02-data-ingestion-pipeline/02-CONTEXT.md` — D-09 for validation rules
- `backend/app/domain/models.py` — verify OHLCV model fields (symbol, timestamp, open, high, low, close, volume, timeframe, asset_class)
</read_first>

<action>
Create `backend/app/infrastructure/ingest/quality.py` with the following validation functions, each returning `(clean_df: pd.DataFrame, report: QualityReport)`:

```python
"""OHLCV data quality validation."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from backend.app.core.logging import get_logger

log = get_logger("conflu.ingest.quality")


@dataclass
class QualityReport:
    """Result of a quality validation pass."""
    total_rows: int = 0
    rows_discarded: int = 0
    duplicate_timestamps: int = 0
    ohlc_inconsistencies: int = 0
    negative_volume: int = 0
    zero_negative_prices: int = 0
    nan_values: int = 0
    passed: bool = True


def validate_ohlcv(df: pd.DataFrame) -> tuple[pd.DataFrame, QualityReport]:
    """Validate OHLCV data quality. Returns (cleaned_df, report).

    Validation rules (D-09):
    1. No NaN values in any column
    2. No duplicate (symbol, timestamp, timeframe) combos — keep first occurrence
    3. OHLC consistency: high >= max(open, close), low <= min(open, close)
    4. Volume >= 0
    5. All prices (open, high, low, close) > 0
    6. 'ticker' column (if present) is used for symbol extraction
    """
    report = QualityReport()
    if df.empty:
        return df, report

    n_before = len(df)
    report.total_rows = n_before

    # 1. Remove NaN rows
    nan_mask = df[["open", "high", "low", "close", "volume"]].isna().any(axis=1)
    df = df[~nan_mask].copy()
    report.nan_values = int(nan_mask.sum())

    # 2. Handle ticker -> symbol conversion if ticker column exists
    if "ticker" in df.columns and "symbol" not in df.columns:
        df["symbol"] = df["ticker"].apply(lambda t: t.split(":")[-1] if ":" in str(t) else str(t))

    # 3. Remove duplicate (symbol, timestamp, timeframe) — keep first
    if "symbol" in df.columns and "timestamp" in df.columns:
        if "timeframe" not in df.columns:
            df["timeframe"] = "1D"  # default if not present
        before_dedup = len(df)
        df = df.drop_duplicates(subset=["symbol", "timestamp", "timeframe"], keep="first")
        report.duplicate_timestamps = before_dedup - len(df)

    # 4. OHLC consistency: high >= max(open, close)
    ohlc_mask = (
        (df["high"] >= df[["open", "close"]].max(axis=1))
        & (df["low"] <= df[["open", "close"]].min(axis=1))
    )
    # 5. Volume >= 0
    vol_mask = df["volume"] >= 0
    # 6. Prices > 0
    price_mask = (df[["open", "high", "low", "close"]] > 0).all(axis=1)

    combined_mask = ohlc_mask & vol_mask & price_mask
    report.ohlc_inconsistencies = int((~ohlc_mask).sum())
    report.negative_volume = int((~vol_mask).sum())
    report.zero_negative_prices = int((~price_mask).sum())

    rows_discarded = int((~combined_mask).sum())
    report.rows_discarded = rows_discarded

    if rows_discarded > 0:
        report.passed = False
        log.warning(
            "quality_check_failed",
            total_rows=n_before,
            discarded=rows_discarded,
            nan_values=report.nan_values,
            duplicates=report.duplicate_timestamps,
            ohlc_inconsistencies=report.ohlc_inconsistencies,
            negative_volume=report.negative_volume,
            bad_prices=report.zero_negative_prices,
        )

    return df[combined_mask].copy(), report
```

Also add:
- `def validate_ohlcv_strict(df: pd.DataFrame) -> pd.DataFrame` — raises `ValueError` on any validation failure (for use in tests / dry-run mode)
- `def merge_quality_reports(reports: list[QualityReport]) -> QualityReport` — aggregates multiple quality reports into one
</action>

<acceptance_criteria>
1. `backend/app/infrastructure/ingest/quality.py` exists
2. `grep "def validate_ohlcv" backend/app/infrastructure/ingest/quality.py` exists
3. `grep "class QualityReport" backend/app/infrastructure/ingest/quality.py` exists (dataclass)
4. Validation checks: high >= max(open, close) — grep for `"high"` and `"max"`
5. Validation checks: low <= min(open, close) — grep for `"low"` and `"min"`
6. Validation checks: volume >= 0 — grep for `volume` and `>= 0`
7. Validation checks: prices > 0 — grep for `> 0`
8. NaN removal — grep for `isna()`
9. Duplicate removal — grep for `drop_duplicates`
10. `cd backend && python -c "from backend.app.infrastructure.ingest.quality import validate_ohlcv, QualityReport; print('OK')"` prints `OK`
</acceptance_criteria>

---

### Task 2.4: Ingestion Models

**Wave:** 2
**Depends on:** None
**Files modified:** `backend/app/infrastructure/ingest/models.py` (new)
**Autonomous:** true

<read_first>
- `backend/app/domain/models.py` — verify existing Pydantic model patterns (ConfigDict frozen+extra forbid, field_validator for UTC timestamps)
- `.planning/phases/02-data-ingestion-pipeline/02-RESEARCH.md` — section 8.2 for module structure, section 7 for health check response shape
- `.planning/phases/02-data-ingestion-pipeline/02-CONTEXT.md` — D-14 (metrics), D-17 (health endpoint)
</read_first>

<action>
Create `backend/app/infrastructure/ingest/models.py` with:

```python
"""Pydantic models for ingestion pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScanResult(BaseModel):
    """Result of a single TradingView scan operation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    market: str
    tickers_requested: int
    tickers_received: int
    duration_ms: float
    success: bool
    error: str | None = None


class IngestionReport(BaseModel):
    """Summary report for a full ingestion run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    correlation_id: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: float | None = None
    asset_classes_processed: list[str] = Field(default_factory=list)
    timeframes_processed: list[str] = Field(default_factory=list)
    symbols_processed: int = 0
    candles_written: int = 0
    symbols_failed: int = 0
    bytes_written: int = 0
    scans_succeeded: int = 0
    scans_failed: int = 0
    rows_discarded: int = 0
    error_rate: float = 0.0
    scan_results: list[ScanResult] = Field(default_factory=list)

    @field_validator("started_at", "completed_at")
    @classmethod
    def ensure_utc(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


class IngestionHealth(BaseModel):
    """Health status for the ingestion pipeline."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    last_successful_run: datetime | None = None
    last_run_duration_ms: float | None = None
    symbols_processed: int = 0
    candles_written: int = 0
    error_rate: float = 0.0
    circuit_breaker_state: str = "CLOSED"
    is_running: bool = False
```
</action>

<acceptance_criteria>
1. `backend/app/infrastructure/ingest/models.py` exists
2. `grep "class ScanResult" backend/app/infrastructure/ingest/models.py` exists with `ConfigDict(frozen=True, extra='forbid')`
3. `grep "class IngestionReport" backend/app/infrastructure/ingest/models.py` exists with all required fields
4. `grep "class IngestionHealth" backend/app/infrastructure/ingest/models.py` exists
5. `IngestionReport` has fields: `correlation_id`, `started_at`, `completed_at`, `duration_ms`, `asset_classes_processed`, `timeframes_processed`, `symbols_processed`, `candles_written`, `symbols_failed`, `bytes_written`, `scans_succeeded`, `scans_failed`, `rows_discarded`, `error_rate`, `scan_results`
6. `IngestionHealth` has fields: `last_successful_run`, `last_run_duration_ms`, `symbols_processed`, `candles_written`, `error_rate`, `circuit_breaker_state`, `is_running`
7. `cd backend && python -c "from backend.app.infrastructure.ingest.models import IngestionReport; print('OK')"` prints `OK`
</acceptance_criteria>

---

## Wave 3: Pipeline Orchestration

**Depends on:** Wave 2 (TickerResolver, scanner, quality, models exist)

---

### Task 3.1: Async Chunked Fetcher

**Wave:** 3
**Depends on:** Task 2.1 (scanner.py), Task 2.2 (symbol_map.py), Task 2.4 (models.py)
**Files modified:** `backend/app/infrastructure/ingest/fetcher.py` (new)
**Autonomous:** true

<read_first>
- `.planning/phases/02-data-ingestion-pipeline/02-RESEARCH.md` — section 4 (Async Chunked Fetching Architecture) for semaphore usage, chunking strategy, and fetch_asset_class code
- `.planning/phases/02-data-ingestion-pipeline/02-CONTEXT.md` — D-04 (semaphore), D-05 (batch size), D-14 (logging), D-15 (partial failure)
- `backend/app/infrastructure/ingest/scanner.py` — verify `scan_with_retry` signature
- `backend/app/infrastructure/ingest/symbol_map.py` — verify `TickerResolver` API
- `backend/app/infrastructure/ingest/models.py` — verify `ScanResult` model
- `backend/app/core/config.py` — verify `DataSettings.batch_size`, `DataSettings.max_concurrent`
</read_first>

<action>
Create `backend/app/infrastructure/ingest/fetcher.py` with:

```python
"""Async chunked fetcher with semaphore concurrency control."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

import pandas as pd

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.infrastructure.ingest.models import ScanResult
from backend.app.infrastructure.ingest.scanner import scan_with_retry

log = get_logger("conflu.ingest.fetcher")


class IngestionFetcher:
    """Async fetcher that chunks symbols and manages concurrency.

    Uses TradingView's batch endpoint (100 symbols/call) with semaphore
    limiting to max_concurrent simultaneous operations.
    """

    def __init__(self, max_concurrent: int | None = None) -> None:
        self._max_concurrent = max_concurrent or settings.data.max_concurrent
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._batch_size = settings.data.batch_size

    async def fetch_asset_class(
        self,
        asset_class: str,
        market: str,
        tickers: list[str],
        columns: list[str],
    ) -> tuple[pd.DataFrame, list[ScanResult]]:
        """Fetch OHLCV data for all tickers in an asset class.

        Returns:
            Tuple of (combined DataFrame, list of per-chunk ScanResults).
        """
        all_chunks: list[pd.DataFrame] = []
        all_results: list[ScanResult] = []

        async for chunk_df, scan_result in self._chunked_fetch(tickers, columns, market):
            all_results.append(scan_result)
            if not chunk_df.empty:
                chunk_df = chunk_df.copy()
                chunk_df["asset_class"] = asset_class
                all_chunks.append(chunk_df)

        if not all_chunks:
            return pd.DataFrame(), all_results
        return pd.concat(all_chunks, ignore_index=True), all_results

    async def _chunked_fetch(
        self,
        tickers: list[str],
        columns: list[str],
        market: str,
    ) -> AsyncIterator[tuple[pd.DataFrame, ScanResult]]:
        """Yield (DataFrame, ScanResult) for each chunk as they complete."""
        chunks = [
            tickers[i : i + self._batch_size]
            for i in range(0, len(tickers), self._batch_size)
        ]

        async def fetch_chunk(chunk_tickers: list[str]) -> tuple[pd.DataFrame, ScanResult]:
            start = time.monotonic()
            async with self._semaphore:
                try:
                    df = await scan_with_retry(chunk_tickers, columns, market)
                    duration = (time.monotonic() - start) * 1000
                    result = ScanResult(
                        market=market,
                        tickers_requested=len(chunk_tickers),
                        tickers_received=len(df),
                        duration_ms=round(duration, 2),
                        success=True,
                    )
                    return df, result
                except Exception as e:
                    duration = (time.monotonic() - start) * 1000
                    result = ScanResult(
                        market=market,
                        tickers_requested=len(chunk_tickers),
                        tickers_received=0,
                        duration_ms=round(duration, 2),
                        success=False,
                        error=str(e),
                    )
                    log.exception(
                        "chunk_fetch_failed",
                        market=market,
                        chunk_size=len(chunk_tickers),
                    )
                    # D-15: partial failures don't stop pipeline
                    return pd.DataFrame(), result

        tasks = [fetch_chunk(chunk) for chunk in chunks]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            yield result
```

Key behaviors:
- Uses `settings.data.batch_size` (default 100) for chunking
- Uses `settings.data.max_concurrent` (default 50) for semaphore limit (or `max_concurrent` constructor param override)
- Each chunk: 1 semaphore slot → 1 `scan_with_retry` call
- Partial failures: return empty DataFrame + ScanResult with success=False, never raise
- Attaches `asset_class` column to each chunk DataFrame
- Returns tuple of (combined_df, scan_results_list) from `fetch_asset_class()`
</action>

<acceptance_criteria>
1. `backend/app/infrastructure/ingest/fetcher.py` exists
2. `grep "class IngestionFetcher" backend/app/infrastructure/ingest/fetcher.py` exists
3. `grep "Semaphore" backend/app/infrastructure/ingest/fetcher.py` shows semaphore with `max_concurrent`
4. `grep "batch_size" backend/app/infrastructure/ingest/fetcher.py` shows chunking at 100
5. `grep "async def fetch_asset_class" backend/app/infrastructure/ingest/fetcher.py` exists
6. `grep "as_completed" backend/app/infrastructure/ingest/fetcher.py` shows concurrent task scheduling
7. `grep "asset_class" backend/app/infrastructure/ingest/fetcher.py` shows column attachment to chunks
8. `grep "def _chunked_fetch" backend/app/infrastructure/ingest/fetcher.py` exists
9. Partial failure handling — grep for `"chunk_fetch_failed"` log or `except Exception`
10. `cd backend && python -c "from backend.app.infrastructure.ingest.fetcher import IngestionFetcher; print('OK')"` prints `OK`
</acceptance_criteria>

---

### Task 3.2: Incremental Parquet Writer

**Wave:** 3
**Depends on:** Task 2.3 (quality.py), Task 2.4 (models.py)
**Files modified:** `backend/app/infrastructure/ingest/writer.py` (new)
**Autonomous:** true

<read_first>
- `.planning/phases/02-data-ingestion-pipeline/02-RESEARCH.md` — section 6 (Incremental Parquet Update Strategy) for append-only workflow, dedup via staging table, multi-file idempotency pattern
- `.planning/phases/02-data-ingestion-pipeline/02-CONTEXT.md` — D-07 (append-only), D-08 (DuckDB COPY), D-09 (validation before write), D-16 (idempotency)
- `backend/app/core/database.py` — verify `get_db()`, `partition_path()`, `normalize_symbol()`, `OHLCV_DDL`
- `backend/app/infrastructure/ingest/quality.py` — verify `validate_ohlcv()` return type
- `backend/app/infrastructure/ingest/models.py` — verify `IngestionReport` fields for writer
</read_first>

<action>
Create `backend/app/infrastructure/ingest/writer.py` with:

```python
"""Incremental Parquet writer with dedup and idempotency."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from backend.app.core.database import get_db, partition_path
from backend.app.core.logging import get_logger
from backend.app.infrastructure.ingest.quality import QualityReport, validate_ohlcv

log = get_logger("conflu.ingest.writer")


def write_incremental(
    df: pd.DataFrame,
    asset_class: str,
    timeframe: str,
) -> tuple[int, int, QualityReport]:
    """Append new candles to Parquet partitions, returning (new_rows, bytes_written, quality_report).

    Steps:
    1. Validate OHLCV data quality
    2. Ensure symbol column exists (extract from ticker if needed)
    3. Group by symbol, year, month
    4. For each group: check existing max timestamp, append only new rows
    5. Write to Parquet via DuckDB COPY with deterministic ordering
    6. Track bytes written from file sizes

    Idempotent: re-running with same data produces identical results.
    """
    if df.empty:
        return 0, 0, QualityReport()

    # 1. Validate
    clean_df, quality_report = validate_ohlcv(df)
    if clean_df.empty:
        log.warning(
            "write_no_valid_rows",
            asset_class=asset_class,
            timeframe=timeframe,
            total_rows=len(df),
        )
        return 0, 0, quality_report

    # 2. Ensure symbol, timestamp, timeframe columns
    if "symbol" not in clean_df.columns and "ticker" in clean_df.columns:
        clean_df["symbol"] = clean_df["ticker"].apply(
            lambda t: str(t).split(":")[-1] if ":" in str(t) else str(t)
        )

    if "timeframe" not in clean_df.columns:
        clean_df["timeframe"] = timeframe

    # 3. Parse timestamps and add partition columns
    ts_col = clean_df["timestamp"]
    if not pd.api.types.is_datetime64_any_dtype(ts_col):
        ts_col = pd.to_datetime(ts_col, utc=True)
    clean_df["year"] = ts_col.dt.year.astype(int)
    clean_df["month"] = ts_col.dt.month.astype(int)

    # 4. Group by (symbol, year, month) for partition writes
    total_new = 0
    total_bytes = 0

    with get_db() as con:
        for (symbol, year, month), group_df in clean_df.groupby(
            ["symbol", "year", "month"], sort=False
        ):
            symbol_norm = str(symbol)
            group_df = group_df.copy()

            # 5. Check existing max timestamp for this (symbol, timeframe)
            existing_max = con.sql(
                "SELECT MAX(timestamp) FROM ohlcv WHERE symbol = ? AND timeframe = ?",
                params=[symbol_norm, timeframe],
            ).fetchone()[0]

            if existing_max is not None:
                # Filter to only rows with timestamp > existing max
                group_df = group_df[group_df["timestamp"] > existing_max]

            if group_df.empty:
                continue

            # 6. Determine partition file path
            year_int = int(year)
            month_int = int(month)
            parquet_path = partition_path(
                asset_class=asset_class,
                year=year_int,
                month=month_int,
                symbol=symbol_norm,
                timeframe=timeframe,
            )
            parquet_path.parent.mkdir(parents=True, exist_ok=True)

            # 7. Write to Parquet via DuckDB COPY
            con.execute("CREATE TEMP TABLE IF NOT EXISTS _write_staging AS SELECT * FROM ohlcv WHERE 1=0")
            con.execute("DELETE FROM _write_staging")

            # Insert the new rows into staging
            con.execute(
                "INSERT INTO _write_staging SELECT * FROM group_df",
            )

            # Append to main table
            con.execute(
                "INSERT INTO ohlcv SELECT * FROM _write_staging",
            )

            # Write partition file with deterministic ordering
            con.execute(
                f"""
                COPY (
                    SELECT * FROM _write_staging
                    ORDER BY symbol, timestamp
                ) TO '{parquet_path}' (FORMAT PARQUET)
                """
            )

            con.execute("DROP TABLE IF EXISTS _write_staging")

            new_count = len(group_df)
            total_new += new_count
            total_bytes += parquet_path.stat().st_size if parquet_path.exists() else 0

            log.info(
                "partition_written",
                symbol=symbol_norm,
                asset_class=asset_class,
                timeframe=timeframe,
                year=year_int,
                month=month_int,
                new_rows=new_count,
                path=str(parquet_path),
            )

    return total_new, total_bytes, quality_report
```

Also add:
- `def write_incremental_multi(df: pd.DataFrame, asset_class: str) -> dict[str, tuple[int, int, QualityReport]]` — iterates over unique timeframes in the DataFrame and calls `write_incremental()` per timeframe (since scan returns all timeframes in one DataFrame)
- `def update_symbol_metadata(con: duckdb.DuckDBPyConnection, symbols: list[dict]) -> None` — upserts into `symbol_metadata` table
</action>

<acceptance_criteria>
1. `backend/app/infrastructure/ingest/writer.py` exists
2. `grep "def write_incremental" backend/app/infrastructure/ingest/writer.py` exists
3. `grep "CREATE TEMP TABLE\|COPY.*TO\|INSERT INTO ohlcv" backend/app/infrastructure/ingest/writer.py` shows DuckDB write operations
4. `grep "def write_incremental_multi" backend/app/infrastructure/ingest/writer.py` exists
5. `grep "def update_symbol_metadata" backend/app/infrastructure/ingest/writer.py` exists
6. `grep "partition_path" backend/app/infrastructure/ingest/writer.py` shows path computation per symbol
7. `grep "validate_ohlcv" backend/app/infrastructure/ingest/writer.py` shows quality check before write
8. `grep "MAX(timestamp)" backend/app/infrastructure/ingest/writer.py` shows existing-data check for incremental
9. `cd backend && python -c "from backend.app.infrastructure.ingest.writer import write_incremental; print('OK')"` prints `OK`
</acceptance_criteria>

---

### Task 3.3: Ingestion Metrics & Reporting

**Wave:** 3
**Depends on:** Task 2.4 (models.py — IngestionReport)
**Files modified:** `backend/app/infrastructure/ingest/metrics.py` (new)
**Autonomous:** true

<read_first>
- `.planning/phases/02-data-ingestion-pipeline/02-RESEARCH.md` — section 8.2 module diagram, Section 7 for health data structure
- `.planning/phases/02-data-ingestion-pipeline/02-CONTEXT.md` — D-14 (metrics), D-17 (health check)
- `backend/app/infrastructure/ingest/models.py` — verify `IngestionReport`, `IngestionHealth` models
</read_first>

<action>
Create `backend/app/infrastructure/ingest/metrics.py` with:

```python
"""Ingestion metrics tracking and reporting."""

from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

import duckdb

from backend.app.core.logging import get_logger, set_correlation_id
from backend.app.infrastructure.ingest.models import IngestionHealth, IngestionReport, ScanResult

log = get_logger("conflu.ingest.metrics")


class IngestionMetrics:
    """Tracks counters, timing, and generates IngestionReport.

    Usage:
        metrics = IngestionMetrics()
        with metrics.track_time():
            ... do work ...
        report = metrics.report()
    """

    def __init__(self) -> None:
        self.correlation_id: str = set_correlation_id()
        self.started_at: datetime = datetime.now(timezone.utc)
        self.asset_classes_processed: list[str] = []
        self.timeframes_processed: list[str] = []
        self.symbols_processed: int = 0
        self.candles_written: int = 0
        self.symbols_failed: int = 0
        self.bytes_written: int = 0
        self.scans_succeeded: int = 0
        self.scans_failed: int = 0
        self.rows_discarded: int = 0
        self.scan_results: list[ScanResult] = []
        self._duration_ms: float | None = None

    @contextmanager
    def track_time(self) -> ...:
        """Context manager that records elapsed time."""
        start = time.monotonic()
        try:
            yield
        finally:
            self._duration_ms = (time.monotonic() - start) * 1000

    def record_scan(self, result: ScanResult) -> None:
        """Record a single scan result."""
        self.scan_results.append(result)
        if result.success:
            self.scans_succeeded += 1
            self.symbols_processed += result.tickers_received
        else:
            self.scans_failed += 1
            self.symbols_failed += result.tickers_requested

    def record_write(self, new_rows: int, bytes_written: int, discarded: int) -> None:
        """Record write statistics."""
        self.candles_written += new_rows
        self.bytes_written += bytes_written
        self.rows_discarded += discarded

    def record_asset_class(self, asset_class: str) -> None:
        """Record that an asset class was processed."""
        if asset_class not in self.asset_classes_processed:
            self.asset_classes_processed.append(asset_class)

    def record_timeframe(self, timeframe: str) -> None:
        """Record that a timeframe was processed."""
        if timeframe not in self.timeframes_processed:
            self.timeframes_processed.append(timeframe)

    def report(self) -> IngestionReport:
        """Generate the final IngestionReport."""
        total_ops = self.scans_succeeded + self.scans_failed
        error_rate = round(self.scans_failed / total_ops, 4) if total_ops > 0 else 0.0

        return IngestionReport(
            correlation_id=self.correlation_id,
            started_at=self.started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=self._duration_ms,
            asset_classes_processed=self.asset_classes_processed,
            timeframes_processed=self.timeframes_processed,
            symbols_processed=self.symbols_processed,
            candles_written=self.candles_written,
            symbols_failed=self.symbols_failed,
            bytes_written=self.bytes_written,
            scans_succeeded=self.scans_succeeded,
            scans_failed=self.scans_failed,
            rows_discarded=self.rows_discarded,
            error_rate=error_rate,
            scan_results=self.scan_results,
        )

    def log_summary(self) -> None:
        """Emit a structured log line with the ingestion summary."""
        report = self.report()
        log.info(
            "ingestion_complete",
            correlation_id=report.correlation_id,
            duration_ms=report.duration_ms,
            symbols_processed=report.symbols_processed,
            candles_written=report.candles_written,
            symbols_failed=report.symbols_failed,
            bytes_written=report.bytes_written,
            error_rate=report.error_rate,
            asset_classes=report.asset_classes_processed,
            timeframes=report.timeframes_processed,
        )


def load_latest_health(con: duckdb.DuckDBPyConnection) -> IngestionHealth | None:
    """Load most recent ingestion health from DuckDB."""
    row = con.sql(
        "SELECT * FROM ingestion_health ORDER BY last_successful_run DESC LIMIT 1"
    ).fetchdf()
    if row.empty:
        return None
    return IngestionHealth(**row.iloc[0].to_dict())


def save_health(con: duckdb.DuckDBPyConnection, report: IngestionReport) -> None:
    """Save ingestion health report to DuckDB."""
    health = IngestionHealth(
        last_successful_run=report.completed_at or datetime.now(timezone.utc),
        last_run_duration_ms=report.duration_ms,
        symbols_processed=report.symbols_processed,
        candles_written=report.candles_written,
        error_rate=report.error_rate,
        circuit_breaker_state="CLOSED",
        is_running=False,
    )
    con.execute(
        """
        INSERT INTO ingestion_health (
            last_successful_run, last_run_duration_ms, symbols_processed,
            candles_written, error_rate, circuit_breaker_state, is_running
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            health.last_successful_run,
            health.last_run_duration_ms,
            health.symbols_processed,
            health.candles_written,
            health.error_rate,
            health.circuit_breaker_state,
            health.is_running,
        ],
    )
```

Key design:
- `IngestionMetrics` is the central accumulator, passed through the pipeline
- `track_time()` context manager wraps the entire ingestion run
- `log_summary()` emits a single structured JSON log line at the end
- `save_health()` persists to DuckDB `ingestion_health` table (created in Task 4.3)
- `load_latest_health()` is used by the health endpoint
</action>

<acceptance_criteria>
1. `backend/app/infrastructure/ingest/metrics.py` exists
2. `grep "class IngestionMetrics" backend/app/infrastructure/ingest/metrics.py` exists
3. `grep "def report" backend/app/infrastructure/ingest/metrics.py` returns `IngestionReport`
4. `grep "def log_summary" backend/app/infrastructure/ingest/metrics.py` emits structured log
5. `grep "def load_latest_health" backend/app/infrastructure/ingest/metrics.py` exists
6. `grep "def save_health" backend/app/infrastructure/ingest/metrics.py` exists
7. `grep "def record_scan\|record_write\|record_asset_class\|record_timeframe" backend/app/infrastructure/ingest/metrics.py` — at least 3 record methods exist
8. `cd backend && python -c "from backend.app.infrastructure.ingest.metrics import IngestionMetrics; print('OK')"` prints `OK`
</acceptance_criteria>

---

## Wave 4: Entry Points & Database Integration

**Depends on:** Wave 3 (fetcher, writer, metrics exist)

---

### Task 4.1: run_ingestion Orchestrator

**Wave:** 4
**Depends on:** Task 3.1 (fetcher.py), Task 3.2 (writer.py), Task 3.3 (metrics.py), Task 2.2 (symbol_map.py), Task 2.4 (models.py)
**Files modified:** `backend/app/infrastructure/ingest/__init__.py` (replace empty with full orchestrator)
**Autonomous:** true

<read_first>
- `backend/app/infrastructure/ingest/__init__.py` — verify empty state (created in Task 2.1)
- `backend/app/infrastructure/ingest/fetcher.py` — verify `IngestionFetcher.fetch_asset_class()` signature
- `backend/app/infrastructure/ingest/writer.py` — verify `write_incremental_multi()` signature
- `backend/app/infrastructure/ingest/metrics.py` — verify `IngestionMetrics` API
- `backend/app/infrastructure/ingest/symbol_map.py` — verify `TickerResolver` API
- `.planning/phases/02-data-ingestion-pipeline/02-RESEARCH.md` — section 8.3 (Data Flow) for orchestration sequence
- `.planning/phases/02-data-ingestion-pipeline/02-CONTEXT.md` — D-12 (scheduling), D-14 (logging), D-15 (partial failures)
</read_first>

<action>
Replace `backend/app/infrastructure/ingest/__init__.py` with the full orchestrator:

```python
"""Data ingestion pipeline — TradingView scanner, fetcher, writer, quality.

Usage:
    from backend.app.infrastructure.ingest import run_ingestion
    report = await run_ingestion()
"""

from __future__ import annotations

from backend.app.core.logging import get_logger
from backend.app.infrastructure.ingest.fetcher import IngestionFetcher
from backend.app.infrastructure.ingest.metrics import IngestionMetrics
from backend.app.infrastructure.ingest.models import IngestionReport
from backend.app.infrastructure.ingest.symbol_map import TickerResolver
from backend.app.infrastructure.ingest.writer import write_incremental_multi

log = get_logger("conflu.ingest")


async def run_ingestion(
    asset_classes: list[str] | None = None,
    timeframes: list[str] | None = None,
    dry_run: bool = False,
    max_concurrent: int | None = None,
) -> IngestionReport:
    """Run the full ingestion pipeline.

    Args:
        asset_classes: Subset of asset classes to process (None = all configured).
        timeframes: Subset of timeframes to process (None = all configured).
        dry_run: If True, validate only — don't write to Parquet.
        max_concurrent: Override max concurrent requests (default from config).

    Returns:
        IngestionReport with summary of the run.

    Flow:
    1. Resolve all symbols -> TV tickers via TickerResolver
    2. For each (asset_class, timeframe):
       a. Determine which columns to request from scanner
       b. Chunk tickers into batches of 100
       c. Fire semaphore-constrained concurrent scans
       d. Validate OHLCV data quality
       e. Deduplicate against existing data
       f. Write new rows to Parquet + DuckDB (unless dry_run)
    3. Update symbol_metadata table
    4. Save health report to DuckDB
    5. Emit metrics summary
    """
    from backend.app.core.config import settings
    from backend.app.core.database import get_db

    metrics = IngestionMetrics()
    resolver = TickerResolver()
    fetcher = IngestionFetcher(max_concurrent=max_concurrent)

    # Determine which asset classes and timeframes to process
    acs = asset_classes or list(settings.data.assets.keys())
    tfs = timeframes or list(settings.data.timeframes)

    # Build column sets per timeframe
    # 1D = bare fields, intraday = pipe suffix (e.g., close|5, open|60)
    timeframe_columns: dict[str, list[str]] = {}
    for tf in tfs:
        if tf == "1D":
            timeframe_columns[tf] = ["open", "high", "low", "close", "volume"]
        else:
            suffix = _timeframe_to_tv_suffix(tf)
            timeframe_columns[tf] = [
                f"open{suffix}", f"high{suffix}", f"low{suffix}",
                f"close{suffix}", f"volume{suffix}",
            ]

    with metrics.track_time():
        for asset_class in acs:
            cfg = resolver.get_asset_classes().get(asset_class)
            if cfg is None:
                log.warning("unknown_asset_class", asset_class=asset_class)
                continue

            market = cfg.market
            tickers = [resolver.to_tv_ticker(s, asset_class) for s in cfg.symbols]
            metrics.record_asset_class(asset_class)

            for tf in tfs:
                metrics.record_timeframe(tf)
                columns = ["ticker"] + timeframe_columns.get(tf, ["close"])

                log.info(
                    "fetching_asset_class_timeframe",
                    asset_class=asset_class,
                    timeframe=tf,
                    market=market,
                    symbol_count=len(tickers),
                )

                # Fetch
                chunk_df, scan_results = await fetcher.fetch_asset_class(
                    asset_class=asset_class,
                    market=market,
                    tickers=tickers,
                    columns=columns,
                )

                for sr in scan_results:
                    metrics.record_scan(sr)

                if chunk_df.empty:
                    log.info("no_data_fetched", asset_class=asset_class, timeframe=tf)
                    continue

                # Assign timeframe to the data
                chunk_df["timeframe"] = tf

                # Write (unless dry run)
                if not dry_run:
                    results = write_incremental_multi(chunk_df, asset_class)
                    timeframe_key = f"{asset_class}/{tf}"
                    if timeframe_key in results:
                        new_rows, bytes_written, quality = results[timeframe_key]
                        metrics.record_write(new_rows, bytes_written, quality.rows_discarded)
                else:
                    log.info(
                        "dry_run_validation",
                        asset_class=asset_class,
                        timeframe=tf,
                        rows_fetched=len(chunk_df),
                    )

        # Update symbol_metadata after processing
        if not dry_run:
            try:
                with get_db() as con:
                    _update_symbol_metadata(con, resolver, acs)
                    from backend.app.infrastructure.ingest.metrics import save_health
                    save_health(con, metrics.report())
            except Exception:
                log.exception("metadata_update_failed")

    metrics.log_summary()
    return metrics.report()


def _timeframe_to_tv_suffix(tf: str) -> str:
    """Convert internal timeframe to TV pipe suffix.

    Examples:
        '5m' -> '|5'
        '15m' -> '|15'
        '1h' -> '|60'
        '4h' -> '|240'
        '1D' -> ''  (bare field)
    """
    if tf == "1D":
        return ""
    if tf.endswith("h"):
        mins = int(tf[:-1]) * 60
        return f"|{mins}"
    if tf.endswith("m"):
        mins = int(tf[:-1])
        return f"|{mins}"
    return ""


def _update_symbol_metadata(con, resolver: TickerResolver, asset_classes: list[str]) -> None:
    """Upsert symbols into symbol_metadata table."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    for ac in asset_classes:
        cfg = resolver.get_asset_classes().get(ac)
        if cfg is None:
            continue
        for symbol in cfg.symbols:
            exchange = resolver.get_exchange(symbol, ac)
            tv_ticker = resolver.to_tv_ticker(symbol, ac)
            con.execute(
                """
                INSERT INTO symbol_metadata (symbol, asset_class, exchange, tv_ticker, timezone, active, last_seen_at)
                VALUES (?, ?, ?, ?, ?, true, ?)
                ON CONFLICT (symbol) DO UPDATE SET
                    last_seen_at = EXCLUDED.last_seen_at,
                    active = true
                """,
                [symbol, ac, exchange.rstrip(":"), tv_ticker, cfg.timezone, now],
            )


__all__ = ["run_ingestion", "IngestionReport"]
```
</action>

<acceptance_criteria>
1. `grep "async def run_ingestion" backend/app/infrastructure/ingest/__init__.py` exists
2. `grep "asset_classes.*None, timeframes.*None, dry_run.*False"` shows correct default params
3. `grep "fetcher.fetch_asset_class" backend/app/infrastructure/ingest/__init__.py` shows fetcher call
4. `grep "write_incremental_multi" backend/app/infrastructure/ingest/__init__.py` shows writer call
5. `grep "dry_run" backend/app/infrastructure/ingest/__init__.py` shows dry-run skip logic
6. `grep "def _timeframe_to_tv_suffix" backend/app/infrastructure/ingest/__init__.py` exists with TV pipe suffix logic
7. `grep "def _update_symbol_metadata" backend/app/infrastructure/ingest/__init__.py` exists
8. `grep "save_health" backend/app/infrastructure/ingest/__init__.py` shows health report saving
9. `grep "log_summary" backend/app/infrastructure/ingest/__init__.py` shows metrics summary
10. `cd backend && python -c "from backend.app.infrastructure.ingest import run_ingestion; print('OK')"` prints `OK`
</acceptance_criteria>

---

### Task 4.2: CLI Entry Point

**Wave:** 4
**Depends on:** Task 4.1 (run_ingestion orchestrator)
**Files modified:** `backend/app/infrastructure/ingest/cli.py` (new)
**Autonomous:** true

<read_first>
- `backend/app/infrastructure/ingest/__init__.py` — verify `run_ingestion()` signature
- `.planning/phases/02-data-ingestion-pipeline/02-RESEARCH.md` — section Q4 (CLI arguments)
- `.planning/phases/02-data-ingestion-pipeline/02-CONTEXT.md` — D-13 (standalone CLI)
- `backend/app/core/config.py` — verify `DataSettings.assets.keys()` for `--asset-class` choices
- `backend/app/core/database.py` — verify `initialize_database()` exists for setup command
</read_first>

<action>
Create `backend/app/infrastructure/ingest/cli.py` with:

```python
"""CLI entry point for ingestion pipeline.

Usage:
    python -m backend.app.infrastructure.ingest
    python -m backend.app.infrastructure.ingest --asset-class equities --timeframe 1D
    python -m backend.app.infrastructure.ingest --dry-run
    python -m backend.app.infrastructure.ingest --health
    python -m backend.app.infrastructure.ingest --setup  # Initialize DB tables
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from backend.app.core.config import settings
from backend.app.core.database import get_db, initialize_database
from backend.app.core.logging import configure_logging, get_logger
from backend.app.infrastructure.ingest.metrics import load_latest_health

log = get_logger("conflu.ingest.cli")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m backend.app.infrastructure.ingest",
        description="conflu.ai data ingestion pipeline — TradingView scanner to Parquet",
    )

    parser.add_argument(
        "--asset-class",
        action="append",
        choices=list(settings.data.assets.keys()),
        dest="asset_classes",
        help="Asset class(es) to process (default: all). Can be specified multiple times.",
    )
    parser.add_argument(
        "--timeframe",
        action="append",
        choices=settings.data.timeframes,
        dest="timeframes",
        help="Timeframe(s) to fetch (default: all). Can be specified multiple times.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Validate configuration and connectivity without writing data.",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=None,
        help=f"Max concurrent scan operations (default: {settings.data.max_concurrent}).",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        default=False,
        help="Show last ingestion health status and exit.",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        default=False,
        help="Initialize DuckDB tables (symbol_metadata, ingestion_health) and exit.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns exit code."""
    configure_logging(
        log_level=settings.core.log_level,
        log_json=settings.core.log_json,
    )

    parser = build_parser()
    args = parser.parse_args(argv)

    # Handle --setup
    if args.setup:
        initialize_database()
        _ensure_ingestion_tables()
        log.info("setup_complete", tables=["ohlcv", "symbol_metadata", "ingestion_health"])
        return 0

    # Handle --health
    if args.health:
        try:
            with get_db() as con:
                health = load_latest_health(con)
            if health:
                print(health.model_dump_json(indent=2))
            else:
                print('{"status": "no_data", "message": "No ingestion runs recorded yet."}')
        except Exception as e:
            print(f'{{"status": "error", "message": "{e}"}}')
        return 0

    # Run ingestion
    try:
        from backend.app.infrastructure.ingest import run_ingestion

        report = asyncio.run(
            run_ingestion(
                asset_classes=args.asset_classes,
                timeframes=args.timeframes,
                dry_run=args.dry_run,
                max_concurrent=args.max_concurrent,
            )
        )
        print(report.model_dump_json(indent=2))
        return 0 if report.error_rate < 1.0 else 1
    except Exception:
        log.exception("ingestion_fatal")
        return 1


def _ensure_ingestion_tables() -> None:
    """Create symbol_metadata and ingestion_health tables if not exist."""
    from backend.app.core.database import get_db

    with get_db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS symbol_metadata (
                symbol VARCHAR PRIMARY KEY,
                asset_class VARCHAR NOT NULL,
                exchange VARCHAR,
                tv_ticker VARCHAR,
                timezone VARCHAR DEFAULT 'UTC',
                active BOOLEAN DEFAULT true,
                added_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_health (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                last_successful_run TIMESTAMPTZ,
                last_run_duration_ms DOUBLE,
                symbols_processed INTEGER DEFAULT 0,
                candles_written INTEGER DEFAULT 0,
                error_rate DOUBLE DEFAULT 0.0,
                circuit_breaker_state VARCHAR DEFAULT 'CLOSED',
                is_running BOOLEAN DEFAULT false,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        log.info("ingestion_tables_ensured")


if __name__ == "__main__":
    sys.exit(main())
```

**Also update `backend/app/infrastructure/ingest/__init__.py`** to export `main`:
```python
from backend.app.infrastructure.ingest.cli import main
```
</action>

<acceptance_criteria>
1. `backend/app/infrastructure/ingest/cli.py` exists
2. `grep "add_argument.*asset-class" backend/app/infrastructure/ingest/cli.py` shows `--asset-class` with choices from config
3. `grep "add_argument.*timeframe" backend/app/infrastructure/ingest/cli.py` shows `--timeframe` with choices
4. `grep "add_argument.*dry-run" backend/app/infrastructure/ingest/cli.py` shows `--dry-run` flag
5. `grep "add_argument.*max-concurrent" backend/app/infrastructure/ingest/cli.py` shows `--max-concurrent`
6. `grep "add_argument.*health" backend/app/infrastructure/ingest/cli.py` shows `--health` flag
7. `grep "add_argument.*setup" backend/app/infrastructure/ingest/cli.py` shows `--setup` flag
8. `grep "def main" backend/app/infrastructure/ingest/cli.py` returns `int` exit code
9. `grep "run_ingestion" backend/app/infrastructure/ingest/cli.py` shows async run
10. `grep "initialize_database" backend/app/infrastructure/ingest/cli.py` shows `--setup` calls it
11. `grep "symbol_metadata\|ingestion_health" backend/app/infrastructure/ingest/cli.py` shows table creation DDL
12. `cd backend && python -c "from backend.app.infrastructure.ingest.cli import main; print('OK')"` prints `OK`
</acceptance_criteria>

---

### Task 4.3: Database Schema Update

**Wave:** 4
**Depends on:** None (independent DB layer update)
**Files modified:** `backend/app/core/database.py`
**Autonomous:** true

<read_first>
- `backend/app/core/database.py` — current `OHLCV_DDL`, `initialize_database()`, `get_db()` pattern
- `.planning/phases/02-data-ingestion-pipeline/02-RESEARCH.md` — sections 5.3 (symbol_metadata DDL) and 7 (ingestion_health DDL)
- `.planning/phases/02-data-ingestion-pipeline/02-CONTEXT.md` — D-11 (symbol metadata table)
</read_first>

<action>
Edit `backend/app/core/database.py` to:

**1. Add `SYMBOL_METADATA_DDL` constant** after `OHLCV_DDL`:
```python
# Symbol metadata for multi-asset class tracking
SYMBOL_METADATA_DDL = """
CREATE TABLE IF NOT EXISTS symbol_metadata (
    symbol VARCHAR PRIMARY KEY,
    asset_class VARCHAR NOT NULL,
    exchange VARCHAR,
    tv_ticker VARCHAR,
    timezone VARCHAR DEFAULT 'UTC',
    active BOOLEAN DEFAULT true,
    added_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
"""
```

**2. Add `INGESTION_HEALTH_DDL` constant** after `SYMBOL_METADATA_DDL`:
```python
# Ingestion health tracking for the /health/ingestion endpoint
INGESTION_HEALTH_DDL = """
CREATE TABLE IF NOT EXISTS ingestion_health (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    last_successful_run TIMESTAMPTZ,
    last_run_duration_ms DOUBLE,
    symbols_processed INTEGER DEFAULT 0,
    candles_written INTEGER DEFAULT 0,
    error_rate DOUBLE DEFAULT 0.0,
    circuit_breaker_state VARCHAR DEFAULT 'CLOSED',
    is_running BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
"""
```

**3. Update `initialize_database()`** to also execute the new DDLs:
```python
def initialize_database() -> None:
    """Initialize the DuckDB database: create tables and indexes."""
    with get_db() as con:
        con.execute(OHLCV_DDL)
        con.execute(SYMBOL_METADATA_DDL)
        con.execute(INGESTION_HEALTH_DDL)
```
</action>

<acceptance_criteria>
1. `grep "SYMBOL_METADATA_DDL" backend/app/core/database.py` exists
2. `grep "symbol_metadata" backend/app/core/database.py` shows DDL with columns `symbol`, `asset_class`, `exchange`, `tv_ticker`, `timezone`, `active`, `added_at`, `last_seen_at`
3. `grep "INGESTION_HEALTH_DDL" backend/app/core/database.py` exists
4. `grep "ingestion_health" backend/app/core/database.py` shows DDL with health columns
5. `grep "SYMBOL_METADATA_DDL" -A 1 "initialize_database"` or similar shows new DDLs executed in `initialize_database()`
6. `cd backend && python -c "from backend.app.core.database import initialize_database, SYMBOL_METADATA_DDL, INGESTION_HEALTH_DDL; print('OK')"` prints `OK`
</acceptance_criteria>

---

## Wave 5: Testing

**Depends on:** Wave 2 (core modules exist), Wave 3 (pipeline modules exist)

---

### Task 5.1: Unit Tests — scanner, symbol_map, quality, models

**Wave:** 5
**Depends on:** Task 2.1 (scanner.py), Task 2.2 (symbol_map.py), Task 2.3 (quality.py), Task 2.4 (models.py)
**Files modified:**
- `backend/tests/__init__.py` (no change needed)
- `backend/tests/test_ingest_scanner.py` (new)
- `backend/tests/test_ingest_symbol_map.py` (new)
- `backend/tests/test_ingest_quality.py` (new)
- `backend/tests/test_ingest_models.py` (new)
**Autonomous:** true

<read_first>
- `backend/tests/conftest.py` — verify existing fixtures: `synthetic_ohlcv`, `in_memory_db`, `sample_ohlcv_row`
- `backend/app/infrastructure/ingest/scanner.py` — verify `scan_symbols`, `scan_with_retry`, `circuit_breaker_state` signatures
- `backend/app/infrastructure/ingest/symbol_map.py` — verify `TickerResolver` API
- `backend/app/infrastructure/ingest/quality.py` — verify `validate_ohlcv()` return type
- `backend/app/infrastructure/ingest/models.py` — verify Pydantic model fields
- `.planning/phases/02-data-ingestion-pipeline/02-RESEARCH.md` — section Q5 (Testing Strategy)
</read_first>

<action>
Create four test files:

**a) `backend/tests/test_ingest_scanner.py`** — Tests for scanner module:
- `test_circuit_breaker_initial_state` — circuit starts CLOSED with 0 failures
- `test_circuit_breaker_reset` — `reset_circuit_breaker()` resets state
- `test_scan_with_retry_empty_tickers` — returns empty DataFrame when tickers=[]
- `test_scan_with_retry_fails_after_retries` — mock `get_scanner_data` to always raise, verify retry logic runs `retry_max_attempts` times
- Mock `tradingview_screener.Query` using `unittest.mock.patch` for all tests that would call TV API
- Use `pytest.mark.asyncio` for async test functions

**b) `backend/tests/test_ingest_symbol_map.py`** — Tests for symbol mapping:
- `test_to_tv_ticker_default` — `TickerResolver().to_tv_ticker('AAPL', 'equities')` returns `'NASDAQ:AAPL'`
- `test_to_tv_ticker_override` — `to_tv_ticker('SPY', 'equities')` returns `'AMEX:SPY'` (override)
- `test_to_tv_ticker_crypto` — `to_tv_ticker('BTCUSDT', 'crypto')` returns `'BINANCE:BTCUSDT'`
- `test_to_tv_ticker_forex` — `to_tv_ticker('EURUSD', 'forex')` returns `'FX:EURUSD'`
- `test_from_tv_ticker` — `from_tv_ticker('NASDAQ:AAPL')` returns `('NASDAQ', 'AAPL')`
- `test_from_tv_ticker_no_exchange` — `from_tv_ticker('AAPL')` returns `('', 'AAPL')`
- `test_get_market_for_asset_class` — returns correct market per asset class
- `test_get_asset_classes` — returns dict with all configured asset classes
- `test_refresh` — `refresh()` rebuilds from current config

**c) `backend/tests/test_ingest_quality.py`** — Tests for quality validation:
- `test_valid_data_passes` — valid OHLCV DataFrame passes all checks
- `test_high_low_violation` — rows where high < low are discarded
- `test_ohlc_consistency` — rows where high < max(open,close) are discarded
- `test_negative_volume` — rows with volume < 0 are discarded
- `test_zero_price` — rows with open=0 are discarded
- `test_nan_values` — rows with NaN in any OHLCV column are removed
- `test_duplicate_timestamps` — duplicate (symbol, timestamp, timeframe) are deduplicated
- `test_empty_dataframe` — returns empty DataFrame with clean report
- `test_ticker_to_symbol` — ticker column is converted to symbol when symbol missing
- `test_quality_report_counts` — verify report counts match expected discard numbers
- Use `synthetic_ohlcv` fixture from conftest, modify copies for invalid data

**d) `backend/tests/test_ingest_models.py`** — Tests for Pydantic models:
- `test_ingestion_report_defaults` — default values are correct
- `test_ingestion_report_with_scan_results` — can include ScanResult list
- `test_scan_result_fields` — all fields present with correct types
- `test_ingestion_health` — all health fields present
- `test_report_utc_validation` — naive datetime gets UTC assigned (not rejected, per validator design)
- `test_report_frozen` — trying to modify field raises TypeError
</action>

<acceptance_criteria>
1. `backend/tests/test_ingest_scanner.py` exists with at least 4 test functions
2. `backend/tests/test_ingest_symbol_map.py` exists with at least 8 test functions including SPY override
3. `backend/tests/test_ingest_quality.py` exists with at least 8 test functions covering all validation rules
4. `backend/tests/test_ingest_models.py` exists with at least 5 test functions
5. `cd backend && python -m pytest tests/test_ingest_models.py -v --no-header 2>&1 | tail -20` shows all tests pass
6. `cd backend && python -m pytest tests/test_ingest_quality.py -v --no-header 2>&1 | tail -20` shows all tests pass
7. `cd backend && python -m pytest tests/test_ingest_symbol_map.py -v --no-header 2>&1 | tail -20` shows all tests pass
8. Each test file has `from __future__ import annotations` as first import
9. Mock-based scanner tests don't call real TV API (no network in unit tests)
</acceptance_criteria>

---

### Task 5.2: Pipeline Tests — fetcher, writer, metrics, CLI

**Wave:** 5
**Depends on:** Task 3.1 (fetcher.py), Task 3.2 (writer.py), Task 3.3 (metrics.py), Task 4.2 (cli.py)
**Files modified:**
- `backend/tests/test_ingest_fetcher.py` (new)
- `backend/tests/test_ingest_writer.py` (new)
- `backend/tests/test_ingest_metrics.py` (new)
- `backend/tests/test_ingest_cli.py` (new)
- `backend/tests/conftest.py` (add new fixtures as needed)
**Autonomous:** true

<read_first>
- `backend/app/infrastructure/ingest/fetcher.py` — verify `IngestionFetcher` API
- `backend/app/infrastructure/ingest/writer.py` — verify `write_incremental`, `write_incremental_multi` signatures
- `backend/app/infrastructure/ingest/metrics.py` — verify `IngestionMetrics` API
- `backend/app/infrastructure/ingest/cli.py` — verify CLI arg names
- `backend/tests/conftest.py` — verify existing fixtures to reuse
- `.planning/phases/02-data-ingestion-pipeline/02-RESEARCH.md` — section Q5 for testing strategy
</read_first>

<action>
Create four test files:

**a) `backend/tests/test_ingest_fetcher.py`** — Tests for fetcher:
- `test_fetcher_initialization` — defaults use config values
- `test_fetcher_custom_concurrency` — constructor override works
- `test_fetcher_empty_tickers` — returns empty DataFrame for empty list
- `test_fetcher_chunking` — verifies chunking splits tickers correctly (mock `scan_with_retry`)
- `test_fetcher_semaphore_limit` — verify semaphore enforces max_concurrent (use `asyncio.Semaphore` introspection)
- `test_fetcher_partial_failure` — one chunk fails, others succeed, no exception raised (D-15)
- Use `pytest.mark.asyncio` and mock `scan_with_retry` with `unittest.mock.patch`

**b) `backend/tests/test_ingest_writer.py`** — Tests for writer:
- `test_write_incremental_empty` — returns (0, 0, report) for empty DataFrame
- `test_write_incremental_new_data` — writes new rows to DuckDB (use `in_memory_db` fixture, patch `get_db`)
- `test_write_incremental_dedup` — duplicate rows are skipped (idempotency)
- `test_write_incremental_existing_timestamp` — rows with existing timestamps are skipped
- `test_write_incremental_partition_path` — verifies correct partition path generation
- `test_write_incremental_multi` — processes multiple timeframes
- `test_update_symbol_metadata` — upserts symbol metadata correctly
- Use `in_memory_db` fixture and patch `get_db` or inject connection directly
- Use `tmp_path` fixture from pytest for Parquet file output

**c) `backend/tests/test_ingest_metrics.py`** — Tests for metrics:
- `test_metrics_initialization` — correlation_id is set, started_at is UTC
- `test_metrics_track_time` — duration_ms is populated after context manager
- `test_metrics_record_scan_success` — increments scans_succeeded and symbols_processed
- `test_metrics_record_scan_failure` — increments scans_failed and symbols_failed
- `test_metrics_record_write` — increments candles_written, bytes_written, rows_discarded
- `test_metrics_report` — returns IngestionReport with correct aggregated values
- `test_metrics_log_summary` — emits structured log (capture with `log_capture` or similar)
- `test_save_health_and_load` — save then load returns equal health data (use `in_memory_db`)
- `test_asset_class_timeframe_tracking` — record_asset_class/record_timeframe dedupes

**d) `backend/tests/test_ingest_cli.py`** — Tests for CLI:
- `test_parser_asset_class` — `--asset-class equities` sets `asset_classes=['equities']`
- `test_parser_multiple_asset_classes` — `--asset-class equities --asset-class crypto` sets both
- `test_parser_timeframe` — `--timeframe 1D` sets `timeframes`
- `test_parser_dry_run` — `--dry-run` sets `dry_run=True`
- `test_parser_health` — `--health` sets `health=True`
- `test_parser_setup` — `--setup` sets `setup=True`
- `test_parser_defaults` — no args gives None for optional params
- `test_main_setup` — `main(['--setup'])` returns 0 and calls initialize_database (mock)
- `test_main_health` — `main(['--health'])` returns 0 (mock DB)
- `test_main_run` — `main([])` returns 0 (mock run_ingestion)
</action>

<acceptance_criteria>
1. `backend/tests/test_ingest_fetcher.py` exists with at least 5 test functions
2. `backend/tests/test_ingest_writer.py` exists with at least 6 test functions
3. `backend/tests/test_ingest_metrics.py` exists with at least 8 test functions
4. `backend/tests/test_ingest_cli.py` exists with at least 8 test functions
5. `cd backend && python -m pytest tests/test_ingest_metrics.py tests/test_ingest_cli.py -v --no-header 2>&1 | tail -30` shows all tests pass
6. All test files have `from __future__ import annotations`
7. Tests use existing fixtures (`in_memory_db`, `synthetic_ohlcv`, `sample_ohlcv_row`) from conftest where applicable
8. CLI tests use `argparse` parser directly to avoid subprocess overhead
</acceptance_criteria>

---

## Verification

After all tasks complete, run:

```bash
# 1. Type check
cd backend && mypy --strict app/ tests/

# 2. Test suite
cd backend && python -m pytest tests/ -v --tb=short

# 3. Verify CLI runs
cd backend && python -m backend.app.infrastructure.ingest --help

# 4. Verify setup creates tables
cd backend && python -m backend.app.infrastructure.ingest --setup

# 5. Verify health check works (even with no data)
cd backend && python -m backend.app.infrastructure.ingest --health
```

**Exit criteria:**
- `mypy --strict` exits 0
- `pytest tests/` exits 0 with all tests passing
- `--help` prints usage
- `--setup` exits 0
- `--health` prints valid JSON
