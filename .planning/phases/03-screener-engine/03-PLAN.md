# Phase 3: Screener Engine — Plan

**Phase:** 3 — Screener Engine
**Status:** Planned
**Date:** 2026-06-19
**Branch:** `feat/conflu-ai-platform`

---

## must_haves (Goal-Backward Verification)

Every plan task, when completed, must collectively satisfy these must_haves. Verify after execution:

| # | Must Have | Verifiable With |
|---|-----------|----------------|
| MH-1 | `fastapi>=0.110,<1` and `uvicorn[standard]>=0.29,<1` in pyproject.toml dependencies | `grep "fastapi" pyproject.toml && grep "uvicorn" pyproject.toml` |
| MH-2 | `ScreenSettings` class in config.py with fields: `screens_dir`, `screener_ws_path`, `stream_interval_s`, `max_history`, `top_down_narrowing`, `parallel_asset_classes` | `grep "class ScreenSettings" backend/app/core/config.py` |
| MH-3 | `ComputeSettings` has new field: `cached_indicators` (list of indicator names to cache) | `grep "cached_indicators" backend/app/core/config.py` |
| MH-4 | `indicator_values` table DDL in database.py with columns: `symbol`, `timestamp`, `indicator_name`, `value`, `timeframe`, `params`, `computed_at` | `grep "indicator_values" backend/app/core/database.py` |
| MH-5 | `backend/app/infrastructure/screener/` package exists with files: `__init__.py`, `filters.py`, `engine.py`, `cache.py`, `broadcasting.py`, `configs.py`, `scoring.py`, `streaming.py`, `export.py`, `models.py` | `Get-ChildItem -Path backend/app/infrastructure/screener/ -Name` lists all 10 files |
| MH-6 | `backend/app/infrastructure/indicators_extended.py` exists with ADX, OBV, BB, VWAP, Stoch indicators | `grep "adx\|obv\|bb\|vwap\|stoch" backend/app/infrastructure/indicators_extended.py` |
| MH-7 | `@filter` decorator registry in filters.py with 5 categories and built-in filters for each | `grep "@filter" backend/app/infrastructure/screener/filters.py` shows trend, momentum, volume, volatility, pattern filters |
| MH-8 | `IndicatorCache` class in cache.py with `update_cache()`, `get_latest()`, `get_series()`, `rebuild()` methods | `grep "class IndicatorCache" backend/app/infrastructure/screener/cache.py` and 4 method defs |
| MH-9 | `ScreenEngine` class in engine.py with `screen()`, `screen_to_csv()`, `screen_to_json()` methods | `grep "class ScreenEngine" backend/app/infrastructure/screener/engine.py` |
| MH-10 | `broadcast_timeframe()` in broadcasting.py uses `reindex(method='ffill')` | `grep "def broadcast_timeframe" backend/app/infrastructure/screener/broadcasting.py` and `grep "ffill"` |
| MH-11 | `ConnectionManager` class in streaming.py with `broadcast()`, `register()`, `disconnect()`, `resync()` methods | `grep "class ConnectionManager" backend/app/infrastructure/screener/streaming.py` |
| MH-12 | `config/screens/` directory with at least 4 YAML screen templates (trend-follower, mean-reversion, breakout, volume-surge) | `Get-ChildItem -Path config/screens/ -Name` shows 4+ `.yaml` files |
| MH-13 | `export_csv()` and `export_json()` in export.py | `grep "def export_csv\|def export_json" backend/app/infrastructure/screener/export.py` |
| MH-14 | `ScreenConfig` Pydantic model validates filter names against registry | `grep "validate_filter_names" backend/app/infrastructure/screener/configs.py` |
| MH-15 | All module files have `from __future__ import annotations` as first import | Each file starts with annotations import |
| MH-16 | All new modules pass `mypy --strict` | `cd backend && mypy --strict app/` exits 0 |
| MH-17 | Tests exist for filters, engine, cache, broadcasting, scoring, streaming, configs, export | `Get-ChildItem -Path backend/tests/ -Name` shows test files for each screener module |
| MH-18 | Phase 2's `run_ingestion()` calls `IndicatorCache.update_cache()` after writing data | `grep "cache.update_cache\|IndicatorCache" backend/app/infrastructure/ingest/__init__.py` |

---

## Wave 1: Dependencies, Config & Database Schema

**No dependencies.** All three tasks run in parallel.

---

### Task 1.1: Add FastAPI, Uvicorn & Websockets Dependencies

**Wave:** 1
**Depends on:** None
**Files modified:** `pyproject.toml`
**Autonomous:** true

<read_first>
- `pyproject.toml` — current dependencies list, existing mypy overrides, tool sections
- `.planning/phases/03-screener-engine/03-RESEARCH.md` — section 11 (New Dependencies) for exact version specs
- `.planning/phases/03-screener-engine/03-CONTEXT.md` — D-14 (WebSocket via FastAPI)
</read_first>

<action>
Edit `pyproject.toml` at project root with three changes:

**1. Add dependencies** to `[project] dependencies` list (insert after `"httpx>=0.27,<1",`):
```toml
    "fastapi>=0.110,<1",
    "uvicorn[standard]>=0.29,<1",
```

**2. Add `"websockets>=12.0"` to the `[project.optional-dependencies] test` list (insert after `"hypothesis>=6.0",`):
```toml
    "websockets>=12.0",
```

**3. Add mypy override** after the existing `module = "tradingview_screener.*"` block:
```toml
[[tool.mypy.overrides]]
module = "fastapi.*"
ignore_missing_imports = false

[[tool.mypy.overrides]]
module = "uvicorn.*"
ignore_missing_imports = false

[[tool.mypy.overrides]]
module = "websockets.*"
ignore_missing_imports = true
```
</action>

<acceptance_criteria>
1. `grep "\"fastapi" pyproject.toml` shows `"fastapi>=0.110,<1",`
2. `grep "\"uvicorn" pyproject.toml` shows `"uvicorn[standard]>=0.29,<1",`
3. `grep "websockets" pyproject.toml` shows test dep `"websockets>=12.0",`
4. `grep -A1 "fastapi\." pyproject.toml` shows `module = "fastapi.*"` and `ignore_missing_imports = false`
5. `grep -A1 "uvicorn\." pyproject.toml` shows `module = "uvicorn.*"` and `ignore_missing_imports = false`
6. `cd backend && pip install -e ".[dev,test]"` exits 0
</acceptance_criteria>

---

### Task 1.2: Add ScreenSettings, Extend ComputeSettings & Add DDL

**Wave:** 1
**Depends on:** None
**Files modified:**
- `backend/app/core/config.py` — add `ScreenSettings` class + extend `ComputeSettings`
- `backend/app/core/database.py` — add `indicator_values` / `indicator_snapshot` DDL
**Autonomous:** true

<read_first>
- `backend/app/core/config.py` — current `ComputeSettings` class structure, `AppSettings` nesting, field patterns
- `backend/app/core/database.py` — current DDL strings, `initialize_database()` function, DDL pattern
- `.planning/phases/03-screener-engine/03-RESEARCH.md` — sections 2 (DDL design), 4.1 (indicator_values table), options for wide snapshot
- `.planning/phases/03-screener-engine/03-CONTEXT.md` — D-05, D-06, D-19, D-20
</read_first>

<action>
**Part A: Edit `backend/app/core/config.py`**

**1. Add a new `ScreenSettings` class** (insert before `APISettings`):

```python
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
```

**2. Add 3 new fields to `ComputeSettings`** (insert after existing fields):

```python
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
```

**3. Add `ScreenSettings` to `AppSettings`** (insert after `compute: ComputeSettings = ComputeSettings()`):

```python
    screen: ScreenSettings = ScreenSettings()
```

**Part B: Edit `backend/app/core/database.py`**

**1. Add `INDICATOR_VALUES_DDL`** (insert after `INGESTION_HEALTH_DDL`):

```python
# Indicator cache table (tall format — one row per indicator value per timestamp per symbol)
INDICATOR_VALUES_DDL = """
CREATE TABLE IF NOT EXISTS indicator_values (
    symbol VARCHAR,
    timestamp TIMESTAMPTZ,
    indicator_name VARCHAR,
    value DOUBLE,
    timeframe VARCHAR,
    params VARCHAR,
    computed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_iv_lookup ON indicator_values (symbol, indicator_name, timeframe, timestamp);
CREATE INDEX IF NOT EXISTS idx_iv_scan ON indicator_values (indicator_name, timeframe, timestamp DESC);
"""

# Optional wide snapshot for screening performance (created on demand)
INDICATOR_SNAPSHOT_DDL = """
CREATE TABLE IF NOT EXISTS indicator_snapshot (
    symbol VARCHAR,
    timestamp TIMESTAMPTZ,
    timeframe VARCHAR DEFAULT '1D',
    rsi_14 DOUBLE,
    macd_line DOUBLE,
    macd_signal DOUBLE,
    macd_hist DOUBLE,
    ema_20 DOUBLE,
    ema_50 DOUBLE,
    ema_200 DOUBLE,
    sma_50 DOUBLE,
    sma_200 DOUBLE,
    atr_14 DOUBLE,
    obv DOUBLE,
    vwap DOUBLE,
    bb_lower_20 DOUBLE,
    bb_middle_20 DOUBLE,
    bb_upper_20 DOUBLE,
    stoch_k_14 DOUBLE,
    stoch_d_14 DOUBLE,
    adx_14 DOUBLE,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_is_scan ON indicator_snapshot (timeframe, symbol);
"""
```

**2. Update `initialize_database()`** — add the two new DDL statements after the existing `con.execute(INGESTION_HEALTH_DDL)`:

```python
        con.execute(INDICATOR_VALUES_DDL)
        con.execute(INDICATOR_SNAPSHOT_DDL)
```
</action>

<acceptance_criteria>
1. `grep "class ScreenSettings" backend/app/core/config.py` exists
2. `ScreenSettings` has 6 fields: `screens_dir`, `screener_ws_path`, `stream_interval_s`, `max_history`, `top_down_narrowing`, `parallel_asset_classes`
3. `grep "cached_indicators" backend/app/core/config.py` shows default list with all 10 indicators
4. `grep "indicator_cache_enabled" backend/app/core/config.py` exists
5. `grep "screen_default_timeframes" backend/app/core/config.py` shows `["1D", "4h", "1h"]`
6. `grep "screen: ScreenSettings" backend/app/core/config.py` exists in `AppSettings`
7. `grep "INDICATOR_VALUES_DDL" backend/app/core/database.py` exists with columns: `symbol`, `timestamp`, `indicator_name`, `value`, `timeframe`, `params`, `computed_at`
8. `grep "INDICATOR_SNAPSHOT_DDL" backend/app/core/database.py` exists with all 11 indicator columns
9. `grep "INDICATOR_VALUES_DDL" backend/app/core/database.py | head -1 | grep "con.execute"` — verify `initialize_database()` executes both DDLs
10. `cd backend && python -c "from backend.app.core.config import settings; print(settings.screen.screens_dir)"` prints `config/screens`
11. `cd backend && python -c "from backend.app.core.config import settings; print(settings.compute.cached_indicators)"` prints list with 10 indicators
</acceptance_criteria>

---

### Task 1.3: Update config.yaml with Screen Settings

**Wave:** 1
**Depends on:** None
**Files modified:** `config.yaml`
**Autonomous:** true

<read_first>
- `config.yaml` — current structure, existing `compute:` and `api:` sections
- `backend/app/core/config.py` — verify new field names from Task 1.2
</read_first>

<action>
Edit `config.yaml` with two changes:

**1. Update the `compute:` section** to add `cached_indicators`, `indicator_cache_enabled`, and `screen_default_timeframes`:

```yaml
compute:
  default_indicator_timeframe: 1D
  cache_indicators: true
  broadcast_indicators:
    - rsi
    - macd
    - ema
    - sma
    - atr
  cached_indicators:
    - rsi
    - macd
    - ema
    - sma
    - atr
    - adx
    - obv
    - bb
    - vwap
    - stoch
  indicator_cache_enabled: true
  screen_default_timeframes:
    - 1D
    - 4h
    - 1h
```

**2. Add a `screen:` section** after the `compute:` section (before `api:`):

```yaml
screen:
  screens_dir: config/screens
  screener_ws_path: /api/v1/ws/screener/{screen_id}
  stream_interval_s: 5.0
  max_history: 100
  top_down_narrowing: true
  parallel_asset_classes: 5
```
</action>

<acceptance_criteria>
1. `grep "cached_indicators:" config.yaml` exists under `compute:` with 10 indicator names
2. `grep "indicator_cache_enabled:" config.yaml` shows `true`
3. `grep "screen_default_timeframes:" config.yaml` shows `- 1D`, `- 4h`, `- 1h`
4. `grep "screen:" config.yaml` exists
5. `grep "screens_dir:" config.yaml` shows `config/screens`
6. `grep "stream_interval_s:" config.yaml` shows `5.0`
7. `grep "max_history:" config.yaml` shows `100`
8. `grep "parallel_asset_classes:" config.yaml` shows `5`
9. `cd backend && python -c "from backend.app.core.config import settings; print(settings.screen.stream_interval_s)"` prints `5.0`
</acceptance_criteria>

---

## Wave 2: Core Screener Modules

**Depends on:** Wave 1 (config with ScreenSettings, cached_indicators)

Tasks 2.1, 2.2, 2.3, 2.4 can run in parallel after Wave 1 completes.

---

### Task 2.1: Extended Indicators — ADX, OBV, BB, VWAP, Stoch

**Wave:** 2
**Depends on:** None (uses `@indicator` registry from Phase 1)
**Files modified:** `backend/app/infrastructure/indicators_extended.py` (new)
**Autonomous:** true

<read_first>
- `backend/app/infrastructure/indicators.py` — existing `@indicator` decorator pattern, `compute_all()`, `list_indicators()` — must replicate exact decorator usage and return format
- `.planning/phases/03-screener-engine/03-RESEARCH.md` — section 4.4 (cached indicators), section 10 (integration with Phase 1)
- `.planning/phases/03-screener-engine/03-CONTEXT.md` — D-06 (core cached indicators list)
</read_first>

<action>
Create `backend/app/infrastructure/indicators_extended.py` with 5 new `@indicator`-registered functions. Each returns a DataFrame with columns: `symbol`, `timestamp`, `indicator_name`, `value`.

**1. Compute OBV (On-Balance Volume)** — no parameters:
```python
"""Extended indicator computations: ADX, OBV, BB, VWAP, Stochastics.

Registered via @indicator decorator into the same _INDICATOR_REGISTRY.
"""

from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from backend.app.infrastructure.indicators import indicator


@indicator(name="obv", timeframe="1D")
def compute_obv(df: pd.DataFrame) -> pd.DataFrame:
    """Compute On-Balance Volume.

    OBV = cumulative(volume * sign(close - previous_close))

    Args:
        df: DataFrame with 'close' and 'volume' columns.

    Returns:
        DataFrame with symbol, timestamp, indicator_name, value columns.
    """
    result = df[["symbol", "timestamp"]].copy()
    values = ta.obv(close=df["close"], volume=df["volume"])
    result["indicator_name"] = "obv"
    result["value"] = values
    return result
```

**2. Compute Bollinger Bands** — length=20, std=2 — returns 3 rows per timestamp (`bb_lower`, `bb_middle`, `bb_upper`):
```python
@indicator(name="bb", timeframe="1D")
def compute_bb(
    df: pd.DataFrame,
    length: int = 20,
    std: int = 2,
) -> pd.DataFrame:
    """Compute Bollinger Bands (upper, middle, lower).

    Returns three rows per timestamp: 'bb_lower', 'bb_middle', 'bb_upper'.

    Args:
        df: DataFrame with 'close' column.
        length: BB period (default 20).
        std: Standard deviations (default 2).

    Returns:
        DataFrame with symbol, timestamp, indicator_name, value columns.
    """
    bb_result = ta.bbands(close=df["close"], length=length, std=std)
    if bb_result is None or bb_result.empty:
        return pd.DataFrame(columns=["symbol", "timestamp", "indicator_name", "value"])

    base = df[["symbol", "timestamp"]]
    rows = []
    col_map = {
        f"BBL_{length}_{std}": "bb_lower",
        f"BBM_{length}_{std}": "bb_middle",
        f"BBU_{length}_{std}": "bb_upper",
    }
    for old_name, new_name in col_map.items():
        if old_name in bb_result.columns:
            part = base.copy()
            part["indicator_name"] = new_name
            part["value"] = bb_result[old_name].values
            rows.append(part)

    return pd.concat(rows, ignore_index=True)
```

**3. Compute VWAP** — no pandas-ta equivalent, implement directly:
```python
@indicator(name="vwap", timeframe="1D")
def compute_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """Compute Volume-Weighted Average Price.

    VWAP = cumulative(price * volume) / cumulative(volume)
    Using typical price: (high + low + close) / 3

    Args:
        df: DataFrame with 'high', 'low', 'close', 'volume' columns.

    Returns:
        DataFrame with symbol, timestamp, indicator_name, value columns.
    """
    result = df[["symbol", "timestamp"]].copy()
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cum_pv = (typical_price * df["volume"]).cumsum()
    cum_vol = df["volume"].cumsum()
    values = cum_pv / cum_vol
    result["indicator_name"] = "vwap"
    result["value"] = values
    return result
```

**4. Compute ADX** — length=14:
```python
@indicator(name="adx", timeframe="1D")
def compute_adx(
    df: pd.DataFrame,
    length: int = 14,
) -> pd.DataFrame:
    """Compute Average Directional Index.

    Args:
        df: DataFrame with 'high', 'low', 'close' columns.
        length: ADX period (default 14).

    Returns:
        DataFrame with symbol, timestamp, indicator_name, value columns.
    """
    adx_result = ta.adx(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        length=length,
    )
    if adx_result is None or adx_result.empty:
        return pd.DataFrame(columns=["symbol", "timestamp", "indicator_name", "value"])

    result = df[["symbol", "timestamp"]].copy()
    col = f"ADX_{length}"
    if col in adx_result.columns:
        result["indicator_name"] = "adx"
        result["value"] = adx_result[col].values
    else:
        result["indicator_name"] = "adx"
        result["value"] = float("nan")

    return result
```

**5. Compute Stochastic Oscillator** — k=14, d=3, smooth=3:
```python
@indicator(name="stoch", timeframe="1D")
def compute_stoch(
    df: pd.DataFrame,
    k: int = 14,
    d: int = 3,
    smooth: int = 3,
) -> pd.DataFrame:
    """Compute Stochastic Oscillator (%K and %D lines).

    Returns two rows per timestamp: 'stoch_k', 'stoch_d'.

    Args:
        df: DataFrame with 'high', 'low', 'close' columns.
        k: %K period (default 14).
        d: %D smoothing period (default 3).
        smooth: Smoothing factor (default 3).

    Returns:
        DataFrame with symbol, timestamp, indicator_name, value columns.
    """
    stoch_result = ta.stoch(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        k=k,
        d=d,
        smooth_k=smooth,
    )
    if stoch_result is None or stoch_result.empty:
        return pd.DataFrame(columns=["symbol", "timestamp", "indicator_name", "value"])

    base = df[["symbol", "timestamp"]]
    rows = []
    for col in stoch_result.columns:
        name = col.lower().replace("stoch", "stoch_")
        part = base.copy()
        part["indicator_name"] = name
        part["value"] = stoch_result[col].values
        rows.append(part)

    return pd.concat(rows, ignore_index=True)
```

All functions follow the exact same pattern as Phase 1's indicators.py — the `@indicator` decorator fires on import and registers into `_INDICATOR_REGISTRY` automatically.
</action>

<acceptance_criteria>
1. `backend/app/infrastructure/indicators_extended.py` exists
2. `grep "@indicator" backend/app/infrastructure/indicators_extended.py` shows 5 decorators for obv, bb, vwap, adx, stoch
3. `grep "def compute_obv" backend/app/infrastructure/indicators_extended.py` exists
4. `grep "def compute_bb" backend/app/infrastructure/indicators_extended.py` exists
5. `grep "def compute_vwap" backend/app/infrastructure/indicators_extended.py` exists
6. `grep "def compute_adx" backend/app/infrastructure/indicators_extended.py` exists
7. `grep "def compute_stoch" backend/app/infrastructure/indicators_extended.py` exists
8. `grep "from __future__ import annotations" backend/app/infrastructure/indicators_extended.py` is first import
9. `cd backend && python -c "from backend.app.infrastructure.indicators import list_indicators; reg = list_indicators(); assert 'obv' in reg and 'adx' in reg and 'bb' in reg and 'vwap' in reg and 'stoch' in reg; print('OK')"` prints `OK` (verifies registration into shared registry)
10. `cd backend && mypy --strict backend/app/infrastructure/indicators_extended.py` exits 0
</acceptance_criteria>

---

### Task 2.2: Filter Registry & Built-in Filters

**Wave:** 2
**Depends on:** None (pure functions, no other modules needed)
**Files modified:** `backend/app/infrastructure/screener/filters.py` (new)
**Autonomous:** true

<read_first>
- `backend/app/infrastructure/indicators.py` — existing `@indicator` registry pattern to replicate for `@filter`
- `.planning/phases/03-screener-engine/03-RESEARCH.md` — section 3 (Filter Pipeline Architecture) for complete decorator code, filter signatures, built-in filter tables, pattern filter code
- `.planning/phases/03-screener-engine/03-CONTEXT.md` — D-01, D-02, D-03, D-17
</read_first>

<action>
Create `backend/app/infrastructure/screener/filters.py` with the filter registry, `@filter` decorator, and all built-in filter functions across 5 categories. Follow the exact code patterns from RESEARCH.md sections 3.1–3.4.

**Module structure:**
1. `_FILTER_REGISTRY: dict[str, FilterDef]` — registry dict
2. `FilterDef` dataclass with: `name`, `category`, `description`, `func`, `params`, `timeframes_supported`
3. `FilterParam` dataclass with: `name`, `type`, `default`, `description`
4. `@filter(name, category, ...)` decorator — registers function, wraps for validation (returns bool Series check)
5. Built-in filters for all 5 categories (see RESEARCH.md section 3.3 tables)

**Built-in filters to implement:**

| Category | Filter Name | Signature | Logic |
|----------|-------------|-----------|-------|
| trend | `price_above_ema` | `(df, period=200)` | `close > ema_{period}` |
| trend | `price_below_ema` | `(df, period=200)` | `close < ema_{period}` |
| trend | `adx_trending` | `(df, threshold=25)` | `adx > threshold` |
| trend | `adx_non_trending` | `(df, threshold=20)` | `adx < threshold` |
| trend | `ema_cross` | `(df, fast=50, slow=200)` | `ema_{fast} > ema_{slow}` (bullish) |
| momentum | `rsi_oversold` | `(df, threshold=30)` | `rsi < threshold` |
| momentum | `rsi_overbought` | `(df, threshold=70)` | `rsi > threshold` |
| momentum | `rsi_range` | `(df, low=30, high=70)` | `low < rsi < high` |
| momentum | `macd_bullish` | `(df,)` | `macd > macd_signal` |
| momentum | `macd_bearish` | `(df,)` | `macd < macd_signal` |
| momentum | `macd_histogram_rising` | `(df,)` | `macd_hist > previous macd_hist` |
| volume | `rvol_high` | `(df, threshold=1.5)` | `volume / avg_volume(20) > threshold` |
| volume | `rvol_low` | `(df, threshold=0.5)` | `volume / avg_volume(20) < threshold` |
| volume | `obv_slope_positive` | `(df, lookback=5)` | `OBV slope > 0 over lookback` |
| volatility | `atr_percentile_high` | `(df, percentile=75)` | `ATR > rolling_percentile(ATR, percentile)` |
| volatility | `atr_percentile_low` | `(df, percentile=25)` | `ATR < rolling_percentile(ATR, percentile)` |
| volatility | `bb_inside` | `(df,)` | Price inside bollinger bands |
| volatility | `bb_touch` | `(df,)` | Price touches/breaks outer band |
| pattern | `candle_engulfing` | `(df, direction='bullish')` | Bullish/bearish engulfing pattern |
| pattern | `candle_hammer` | `(df,)` | Hammer pattern (long lower wick) |
| pattern | `candle_doji` | `(df,)` | Doji pattern (open ≈ close) |

**Critical:** Pattern filters receive raw OHLCV data (not `indicator_values`), while all other filters receive indicator values DataFrames. The filter function signature uses `df` as a generic DataFrame — the `ScreenEngine` provides the correct data type based on filter category.

**Also export:**
- `def list_filters() -> dict[str, FilterDef]` — returns copy of registry
- `def list_filters_by_category(category: str) -> dict[str, FilterDef]` — filtered by category

Follow the exact `@filter` decorator code from RESEARCH.md section 3.2 (including `_FILTER_REGISTRY`, `FilterDef`, `FilterParam` dataclasses, and the decorator function with bool validation).
</action>

<acceptance_criteria>
1. `backend/app/infrastructure/screener/filters.py` exists
2. `grep "_FILTER_REGISTRY" backend/app/infrastructure/screener/filters.py` exists
3. `grep "class FilterDef" backend/app/infrastructure/screener/filters.py` exists (dataclass)
4. `grep "class FilterParam" backend/app/infrastructure/screener/filters.py` exists (dataclass)
5. `grep "def filter" backend/app/infrastructure/screener/filters.py` shows the decorator function
6. `grep "@filter" backend/app/infrastructure/screener/filters.py` shows 21 filters registered
7. `grep "rsi_oversold\|rsi_overbought\|rsi_range\|macd_bullish\|macd_bearish\|macd_histogram_rising"` shows all momentum filters
8. `grep "price_above_ema\|price_below_ema\|adx_trending\|adx_non_trending\|ema_cross"` shows all trend filters
9. `grep "rvol_high\|rvol_low\|obv_slope_positive"` shows volume filters
10. `grep "atr_percentile_high\|atr_percentile_low\|bb_inside\|bb_touch"` shows volatility filters
11. `grep "candle_engulfing\|candle_hammer\|candle_doji"` shows pattern filters
12. `grep "def list_filters" backend/app/infrastructure/screener/filters.py` exists
13. `grep "from __future__ import annotations" backend/app/infrastructure/screener/filters.py` is first import
14. `cd backend && python -c "from backend.app.infrastructure.screener.filters import list_filters, list_filters_by_category; print(len(list_filters()))"` prints a number >= 21
15. `cd backend && mypy --strict backend/app/infrastructure/screener/filters.py` exits 0
</acceptance_criteria>

---

### Task 2.3: Screen Config Models & YAML Loader

**Wave:** 2
**Depends on:** None (Pydantic models, no other screener modules needed)
**Files modified:**
- `backend/app/infrastructure/screener/configs.py` (new) — ScreenConfig, FilterRule, YAML loader, built-in templates
- `backend/app/infrastructure/screener/models.py` (new) — Screener-specific Pydantic models
**Autonomous:** true

<read_first>
- `backend/app/domain/models.py` — existing `ScreenResult` model (must be extended with matched_filters, indicator_values)
- `.planning/phases/03-screener-engine/03-RESEARCH.md` — sections 6.1 (YAML schema), 6.2 (templates), 6.3 (ScreenConfig validation), 8 (ScreenResult serialization)
- `.planning/phases/03-screener-engine/03-CONTEXT.md` — D-11, D-12, D-13
- `backend/app/core/config.py` — verify `ScreenSettings.screens_dir` path
- `backend/app/infrastructure/screener/filters.py` — requires `list_filters()` for validation (import in field_validator)
</read_first>

<action>
**Part A: Create `backend/app/infrastructure/screener/models.py`** with screener-specific Pydantic models:

```python
"""Screener-specific Pydantic models for filter results and screen runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FilterRunResult(BaseModel):
    """Result of evaluating a single filter expression."""
    model_config = ConfigDict(frozen=True)

    filter_name: str
    category: str
    params: dict[str, Any] = Field(default_factory=dict)
    timeframe: str = "1D"
    matched: int = 0
    total: int = 0
    pass_rate: float = 0.0


class ScreenRunResult(BaseModel):
    """Complete result of a single screen evaluation."""
    model_config = ConfigDict(frozen=True)

    screen_name: str
    timestamp: datetime
    duration_ms: float
    total_symbols: int
    symbols_matched: int
    filter_results: list[FilterRunResult] = Field(default_factory=list)
    symbols: list[dict[str, Any]] = Field(default_factory=list)


class ScreenStreamMessage(BaseModel):
    """WebSocket message sent during screener streaming."""
    model_config = ConfigDict(frozen=True)

    type: Literal["screen_update", "delta_update", "error", "pong"] = "screen_update"
    screen_id: str
    sequence: int = 0
    timestamp: datetime
    interval_ms: float = 5000.0
    results: list[dict[str, Any]] = Field(default_factory=list)
    total_matched: int = 0
    total_symbols: int = 0
    added: list[dict[str, Any]] | None = None
    removed: list[str] | None = None
    updated: list[dict[str, Any]] | None = None
```

**Part B: Create `backend/app/infrastructure/screener/configs.py`** with ScreenConfig model and YAML loader:

```python
"""Screen configuration models and YAML load/save utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

log = get_logger("conflu.screener.configs")


class FilterRule(BaseModel):
    """A single filter rule in a screen configuration."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    category: str
    indicator: str
    params: dict[str, Any] = Field(default_factory=dict)
    operator: Literal["gt", "lt", "eq", "crosses_above", "crosses_below"] = "gt"
    timeframe: str = "1D"
    negate: bool = False


class ScreenConfig(BaseModel):
    """A complete screen configuration loaded from YAML."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    description: str = ""
    asset_classes: list[str] = Field(default_factory=lambda: ["equities", "crypto"])
    timeframes: list[str] = Field(default_factory=lambda: ["1D", "4h"])
    filters: list[FilterRule] = Field(default_factory=list)

    @field_validator("filters")
    @classmethod
    def validate_filter_names(cls, filters: list[FilterRule]) -> list[FilterRule]:
        """Ensure all referenced filter names are registered."""
        # Lazy import to avoid circular dependency
        from backend.app.infrastructure.screener.filters import list_filters

        registered = list_filters()
        for flt in filters:
            if flt.indicator not in registered:
                msg = (
                    f"Unknown filter '{flt.indicator}'. "
                    f"Available: {list(registered.keys())}"
                )
                raise ValueError(msg)
        return filters


def load_screen_template(name: str) -> ScreenConfig:
    """Load a screen configuration from YAML.

    Args:
        name: Screen name (filename without .yaml extension).

    Returns:
        ScreenConfig instance.

    Raises:
        FileNotFoundError: If template file doesn't exist.
        ValueError: If YAML validation fails.
    """
    screens_dir = Path(settings.screen.screens_dir)
    path = screens_dir / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Screen template '{name}' not found at {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return ScreenConfig(**data)


def list_screen_templates() -> list[dict[str, str]]:
    """List available screen configuration names with descriptions.

    Returns:
        List of dicts with 'name' and 'description' keys.
    """
    screens_dir = Path(settings.screen.screens_dir)
    templates: list[dict[str, str]] = []
    for p in sorted(screens_dir.glob("*.yaml")):
        try:
            cfg = load_screen_template(p.stem)
            templates.append({"name": cfg.name, "description": cfg.description})
        except Exception:
            log.warning("failed_to_load_template", template=str(p))
            templates.append({"name": p.stem, "description": ""})
    return templates


def save_screen_config(config: ScreenConfig, path: str | Path | None = None) -> Path:
    """Save a screen configuration to YAML.

    Args:
        config: ScreenConfig instance.
        path: Optional output path. Defaults to config/screens/{name}.yaml.

    Returns:
        Path to the saved file.
    """
    if path is None:
        screens_dir = Path(settings.screen.screens_dir)
        screens_dir.mkdir(parents=True, exist_ok=True)
        path = screens_dir / f"{config.name}.yaml"

    data = config.model_dump(mode="python")
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    log.info("screen_config_saved", name=config.name, path=str(path))
    return Path(path)
```

**Part C: Also extend the existing `ScreenResult` model** in `backend/app/domain/models.py` with new fields:
- Add `matched_filters: list[str] = Field(default_factory=list)` — names of filters that matched
- Add `indicator_values: dict[str, float] = Field(default_factory=dict)` — current indicator values for the symbol
</action>

<acceptance_criteria>
1. `backend/app/infrastructure/screener/models.py` exists with `FilterRunResult`, `ScreenRunResult`, `ScreenStreamMessage`
2. `grep "class FilterRunResult" backend/app/infrastructure/screener/models.py` has `filter_name`, `category`, `params`, `matched`, `total`, `pass_rate`
3. `grep "class ScreenRunResult" backend/app/infrastructure/screener/models.py` has `screen_name`, `timestamp`, `duration_ms`, `total_symbols`, `symbols_matched`, `filter_results`
4. `grep "class ScreenStreamMessage" backend/app/infrastructure/screener/models.py` has `type`, `sequence`, `added`, `removed`, `updated`
5. `backend/app/infrastructure/screener/configs.py` exists
6. `grep "class FilterRule" backend/app/infrastructure/screener/configs.py` has `category`, `indicator`, `params`, `operator`, `timeframe`, `negate`
7. `grep "class ScreenConfig" backend/app/infrastructure/screener/configs.py` has `validate_filter_names` field_validator
8. `grep "def load_screen_template" backend/app/infrastructure/screener/configs.py` exists
9. `grep "def list_screen_templates" backend/app/infrastructure/screener/configs.py` exists
10. `grep "def save_screen_config" backend/app/infrastructure/screener/configs.py` exists
11. `grep "matched_filters" backend/app/domain/models.py` shows the new field on ScreenResult
12. `grep "indicator_values" backend/app/domain/models.py` shows the new field on ScreenResult
13. `grep "from __future__ import annotations"` is first import in both files
14. `cd backend && python -c "from backend.app.infrastructure.screener.configs import ScreenConfig; print('OK')"` prints `OK`
15. `cd backend && python -c "from backend.app.infrastructure.screener.models import ScreenRunResult; print('OK')"` prints `OK`
</acceptance_criteria>

---

### Task 2.4: Indicator Cache — DuckDB Cache Manager

**Wave:** 2
**Depends on:** Task 1.2 (indicator_values DDL exists), Task 2.1 (extended indicators)
**Files modified:** `backend/app/infrastructure/screener/cache.py` (new)
**Autonomous:** true

<read_first>
- `backend/app/core/database.py` — verify `get_db()`, `get_db_async()`, `INDICATOR_VALUES_DDL` columns
- `backend/app/infrastructure/indicators.py` — verify `compute_all()`, `list_indicators()` signatures
- `backend/app/infrastructure/indicators_extended.py` — verify extended indicator signatures
- `.planning/phases/03-screener-engine/03-RESEARCH.md` — sections 2 (DDL), 4.2 (Cache Refresh Workflow code), 4.3 (Incremental vs Full)
- `.planning/phases/03-screener-engine/03-CONTEXT.md` — D-05, D-06, D-20
- `backend/app/core/config.py` — verify `ComputeSettings.cached_indicators`, `indicator_cache_enabled`
- `backend/app/core/logging.py` — verify `get_logger()` pattern
</read_first>

<action>
Create `backend/app/infrastructure/screener/cache.py` with:

```python
"""DuckDB indicator cache — pre-compute and store indicator values."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import duckdb
import pandas as pd

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.logging import get_logger
from backend.app.infrastructure.indicators import compute_all, list_indicators

log = get_logger("conflu.screener.cache")


class IndicatorCache:
    """Pre-compute and store indicator values in DuckDB.

    Uses the indicator_values table for tall-format storage.
    Supports incremental updates (compute only new bars) and
    full rebuilds (on parameter changes).
    """

    def __init__(self) -> None:
        self._log = get_logger("conflu.screener.cache")
        self._cached_indicators: list[str] = list(settings.compute.cached_indicators)
        self._enabled: bool = settings.compute.indicator_cache_enabled

    async def update_cache(
        self,
        timeframes: list[str] | None = None,
        indicator_names: list[str] | None = None,
    ) -> int:
        """Refresh indicator cache incrementally after ingestion.

        For each (timeframe, indicator), computes indicator values for OHLCV
        bars that are newer than the latest cached value. Only processes
        the intersection of cached_indicators and registered indicators.

        Args:
            timeframes: Timeframes to update (default: all configured).
            indicator_names: Indicators to compute (default: all cached).

        Returns:
            Number of new indicator value rows written.
        """
        if not self._enabled:
            return 0

        import asyncio

        tfs = timeframes or list(settings.data.timeframes)
        names = indicator_names or self._cached_indicators
        total_new = 0

        for tf in tfs:
            # Load OHLCV data for this timeframe
            ohlcv_data = await self._load_ohlcv_for_timeframe(tf)
            if ohlcv_data is None or ohlcv_data.empty:
                continue

            # Compute and store each indicator
            for ind_name in names:
                if ind_name not in list_indicators():
                    self._log.warning("indicator_not_registered", indicator=ind_name)
                    continue

                try:
                    new_rows = await self._compute_and_store(
                        indicator_name=ind_name,
                        ohlcv=ohlcv_data,
                        timeframe=tf,
                    )
                    total_new += new_rows
                except Exception:
                    self._log.exception(
                        "indicator_cache_failed",
                        indicator=ind_name,
                        timeframe=tf,
                    )

        self._log.info("cache_update_complete", new_values=total_new)
        return total_new

    async def _load_ohlcv_for_timeframe(
        self, timeframe: str
    ) -> pd.DataFrame | None:
        """Load latest OHLCV data for a timeframe from DuckDB.

        Gets the latest 500 bars per symbol (configurable in future).
        """
        import asyncio

        loop = asyncio.get_running_loop()

        def _query() -> pd.DataFrame:
            with get_db(read_only=True) as con:
                return con.sql(
                    """
                    SELECT symbol, timestamp, open, high, low, close, volume
                    FROM ohlcv
                    WHERE timeframe = ?
                    ORDER BY symbol, timestamp DESC
                    LIMIT 500
                    """,
                    params=[timeframe],
                ).fetchdf()

        return await loop.run_in_executor(None, _query)

    async def _compute_and_store(
        self,
        indicator_name: str,
        ohlcv: pd.DataFrame,
        timeframe: str,
    ) -> int:
        """Compute an indicator and store results incrementally.

        Steps:
        1. Check MAX(timestamp) per symbol in existing cache
        2. Filter OHLCV to rows newer than cached max
        3. Compute indicator on delta
        4. Insert new rows into indicator_values

        Returns number of rows written.
        """
        import asyncio

        loop = asyncio.get_running_loop()

        def _compute_and_insert() -> int:
            with get_db() as con:
                # 1. Get max cached timestamp per symbol
                cached_max = con.sql(
                    """
                    SELECT symbol, MAX(timestamp) as max_ts
                    FROM indicator_values
                    WHERE indicator_name = ? AND timeframe = ?
                    GROUP BY symbol
                    """,
                    params=[indicator_name, timeframe],
                ).fetchdf()

                # 2. Filter to new data only
                if not cached_max.empty:
                    merged = ohlcv.merge(
                        cached_max.rename(columns={"max_ts": "cached_until"}),
                        on="symbol",
                        how="left",
                    )
                    new_data = merged[
                        merged["cached_until"].isna()
                        | (merged["timestamp"] > merged["cached_until"])
                    ].drop(columns=["cached_until"])
                else:
                    new_data = ohlcv

                if new_data.empty:
                    return 0

                # 3. Compute indicator
                results = compute_all(new_data, indicators=[indicator_name])

                if indicator_name not in results:
                    return 0

                result_df = results[indicator_name]

                # 4. Add timeframe and params columns
                # Fetch the indicator function's params from registry metadata
                params_json = json.dumps({})

                result_df["timeframe"] = timeframe
                result_df["params"] = params_json

                # 5. Insert into indicator_values
                con.sql(
                    """
                    INSERT INTO indicator_values
                    SELECT symbol, timestamp, indicator_name, value, timeframe, params, CURRENT_TIMESTAMP
                    FROM result_df
                    """
                )

                return len(result_df)

        return await loop.run_in_executor(None, _compute_and_insert)

    async def get_latest(
        self,
        indicator_name: str,
        timeframe: str = "1D",
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        """Get latest indicator values for all (or specified) symbols.

        Returns DataFrame with columns: symbol, timestamp, value.
        One row per symbol (latest timestamp before or at current time).
        """
        import asyncio

        loop = asyncio.get_running_loop()

        def _query() -> pd.DataFrame:
            with get_db(read_only=True) as con:
                query = """
                    SELECT symbol, timestamp, value
                    FROM indicator_values
                    WHERE indicator_name = ?
                      AND timeframe = ?
                      AND timestamp <= CURRENT_TIMESTAMP
                """
                params: list[Any] = [indicator_name, timeframe]

                if symbols:
                    placeholders = ",".join("?" * len(symbols))
                    query += f" AND symbol IN ({placeholders})"
                    params.extend(symbols)

                # Get latest per symbol
                query = f"""
                    SELECT symbol, timestamp, value
                    FROM ({query}) sub
                    QUALIFY ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY timestamp DESC) = 1
                """
                return con.sql(query, params=params).fetchdf()

        return await loop.run_in_executor(None, _query)

    async def get_series(
        self,
        indicator_name: str,
        timeframe: str = "1D",
        symbol: str | None = None,
        limit: int = 500,
    ) -> pd.DataFrame:
        """Get time series for an indicator.

        Returns DataFrame with columns: symbol, timestamp, value.
        """
        import asyncio

        loop = asyncio.get_running_loop()

        def _query() -> pd.DataFrame:
            with get_db(read_only=True) as con:
                if symbol:
                    return con.sql(
                        """
                        SELECT symbol, timestamp, value
                        FROM indicator_values
                        WHERE indicator_name = ?
                          AND timeframe = ?
                          AND symbol = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                        """,
                        params=[indicator_name, timeframe, symbol, limit],
                    ).fetchdf()
                else:
                    return con.sql(
                        """
                        SELECT symbol, timestamp, value
                        FROM indicator_values
                        WHERE indicator_name = ?
                          AND timeframe = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                        """,
                        params=[indicator_name, timeframe, limit],
                    ).fetchdf()

        return await loop.run_in_executor(None, _query)

    async def rebuild(
        self,
        indicator_name: str | None = None,
        timeframe: str | None = None,
    ) -> int:
        """Full recompute: delete existing cache and recompute from scratch.

        Args:
            indicator_name: Specific indicator to rebuild (None = all cached).
            timeframe: Specific timeframe to rebuild (None = all configured).

        Returns:
            Total number of rows written.
        """
        import asyncio

        loop = asyncio.get_running_loop()
        names = [indicator_name] if indicator_name else self._cached_indicators
        tfs = [timeframe] if timeframe else list(settings.data.timeframes)

        def _delete_and_recompute() -> int:
            with get_db() as con:
                for ind in names:
                    for tf in tfs:
                        con.sql(
                            "DELETE FROM indicator_values WHERE indicator_name = ? AND timeframe = ?",
                            params=[ind, tf],
                        )
            return 0  # Will be recomputed in update_cache call

        await loop.run_in_executor(None, _delete_and_recompute)
        # Recompute all
        return await self.update_cache(timeframes=tfs, indicator_names=names)
```

**Also add** a `def cache_status()` method that returns a dict with:
- `enabled`: bool
- `cached_indicators`: list[str]
- `total_rows`: int (query COUNT(*) from indicator_values)
- `last_update`: datetime or None

Make sure all methods are async and use `run_in_executor` to avoid blocking the event loop (same pattern as `get_db_async`).
</action>

<acceptance_criteria>
1. `backend/app/infrastructure/screener/cache.py` exists
2. `grep "class IndicatorCache" backend/app/infrastructure/screener/cache.py` exists
3. `grep "async def update_cache" backend/app/infrastructure/screener/cache.py` exists with incremental logic
4. `grep "async def get_latest" backend/app/infrastructure/screener/cache.py` exists with `QUALIFY ROW_NUMBER() OVER` for latest per symbol
5. `grep "async def get_series" backend/app/infrastructure/screener/cache.py` exists with limit/order
6. `grep "async def rebuild" backend/app/infrastructure/screener/cache.py` exists with DELETE + recompute
7. `grep "async def cache_status" backend/app/infrastructure/screener/cache.py` exists
8. `grep "run_in_executor" backend/app/infrastructure/screener/cache.py` shows thread-pool usage
9. `grep "compute_all" backend/app/infrastructure/screener/cache.py` shows usage of Phase 1 indicator registry
10. `grep "from __future__ import annotations" backend/app/infrastructure/screener/cache.py` is first import
11. `cd backend && python -c "from backend.app.infrastructure.screener.cache import IndicatorCache; print('OK')"` prints `OK`
12. `cd backend && mypy --strict backend/app/infrastructure/screener/cache.py` exits 0
</acceptance_criteria>

---

## Wave 3: Screening Engine & Broadcasting

**Depends on:** Wave 2 (filters, cache, configs exist)

Tasks 3.1 and 3.2 can run in parallel. Task 3.3 depends on both.

---

### Task 3.1: Multi-Timeframe Broadcasting Module

**Wave:** 3
**Depends on:** None (pure pandas utilities, no screener module deps)
**Files modified:** `backend/app/infrastructure/screener/broadcasting.py` (new)
**Autonomous:** true

<read_first>
- `.planning/phases/03-screener-engine/03-RESEARCH.md` — sections 5.1 (pandas reindex/ffill vs vectorbt), 5.2 (timeframe hierarchy), 5.3 (cross-timeframe filter rules with exact code)
- `.planning/phases/03-screener-engine/03-CONTEXT.md` — D-08, D-09, D-10
- `backend/app/core/config.py` — verify `ComputeSettings.screen_default_timeframes`
</read_first>

<action>
Create `backend/app/infrastructure/screener/broadcasting.py` with:

```python
"""Multi-timeframe broadcasting utilities for indicator alignment.

Uses pandas reindex with forward-fill (not vectorbt broadcast) for
timeframe alignment — simpler, correct semantics, well-understood.
"""

from __future__ import annotations

import pandas as pd

_TIME_FRAME_RANK: dict[str, int] = {
    "1m": 0,
    "5m": 1,
    "15m": 2,
    "30m": 3,
    "1h": 4,
    "2h": 5,
    "4h": 6,
    "12h": 7,
    "1D": 8,
    "1W": 9,
}


def timeframe_rank(tf: str) -> int:
    """Return numeric rank for a timeframe (higher = longer period).

    Args:
        tf: Timeframe string (e.g., '1D', '4h', '15m').

    Returns:
        Integer rank: 1m=0, 5m=1, ..., 1D=8, 1W=9.
    """
    return _TIME_FRAME_RANK.get(tf, 5)


def sort_timeframes(timeframes: list[str], descending: bool = True) -> list[str]:
    """Sort timeframes by duration.

    Args:
        timeframes: List of timeframe strings.
        descending: If True, sort highest-to-lowest (1D, 4h, 1h).

    Returns:
        Sorted timeframe list.
    """
    return sorted(timeframes, key=timeframe_rank, reverse=descending)


def broadcast_timeframe(
    higher_tf_df: pd.DataFrame,
    lower_tf_timestamps: pd.DatetimeIndex,
    value_column: str = "value",
) -> pd.DataFrame:
    """Broadcast higher-timeframe indicator to lower-timeframe timestamps.

    Uses forward-fill: the value from the higher timeframe applies
    to all lower-timeframe bars until the next higher-timeframe update.

    Args:
        higher_tf_df: DataFrame with 'timestamp' column and value_column.
            Must have a DatetimeIndex or 'timestamp' column.
        lower_tf_timestamps: DatetimeIndex of the target timeframe.
        value_column: Name of the value column to broadcast.

    Returns:
        DataFrame indexed by lower_tf_timestamps with broadcast values.

    Example:
        daily_rsi has daily timestamps.
        hourly_timestamps = pd.date_range(...) for 4h bars.
        broadcast_timeframe(daily_rsi, hourly_timestamps)
        → forward-fills daily RSI values into each 4h bar.
    """
    # Ensure we have a proper DatetimeIndex
    if "timestamp" in higher_tf_df.columns:
        higher_tf_df = higher_tf_df.set_index("timestamp")

    if not isinstance(higher_tf_df.index, pd.DatetimeIndex):
        msg = "higher_tf_df must have a DatetimeIndex or 'timestamp' column"
        raise ValueError(msg)

    # Reindex to lower timeframe with forward-fill
    broadcast = (
        higher_tf_df[[value_column]]
        .reindex(lower_tf_timestamps, method="ffill")
        .reindex(lower_tf_timestamps)  # ensure exact alignment
    )

    broadcast.index.name = "timestamp"
    return broadcast


def align_timeframes(
    dataframes: dict[str, pd.DataFrame],
    target_timeframe: str,
) -> dict[str, pd.DataFrame]:
    """Align multiple timeframe indicator DataFrames to a target timeframe.

    Higher timeframes are forward-filled down, same timeframe is kept,
    lower timeframes are not upsampled (would create false data).

    Args:
        dataframes: Dict mapping timeframe -> DataFrame with timestamp index.
        target_timeframe: The timeframe to align to.
        value_column: Name of the value column to broadcast.

    Returns:
        Dict of {timeframe: aligned_df} — only timeframes >= target.
    """
    # This is a stub for now — full multi-TF alignment will be in ScreenEngine
    pass
```
</action>

<acceptance_criteria>
1. `backend/app/infrastructure/screener/broadcasting.py` exists
2. `grep "def broadcast_timeframe" backend/app/infrastructure/screener/broadcasting.py` exists
3. `grep "reindex.*ffill\|method='ffill'\|method=\"ffill\"" backend/app/infrastructure/screener/broadcasting.py` shows forward-fill broadcasting
4. `grep "def timeframe_rank" backend/app/infrastructure/screener/broadcasting.py` exists
5. `grep "def sort_timeframes" backend/app/infrastructure/screener/broadcasting.py` exists
6. `grep "def align_timeframes" backend/app/infrastructure/screener/broadcasting.py` exists
7. `_TIME_FRAME_RANK` dict has at least 8 timeframe mappings
8. `grep "from __future__ import annotations" backend/app/infrastructure/screener/broadcasting.py` is first import
9. `cd backend && python -c "from backend.app.infrastructure.screener.broadcasting import broadcast_timeframe, timeframe_rank, sort_timeframes; print('OK')"` prints `OK`
10. `cd backend && mypy --strict backend/app/infrastructure/screener/broadcasting.py` exits 0
</acceptance_criteria>

---

### Task 3.2: Scoring Engine

**Wave:** 3
**Depends on:** None (pure pandas/numpy, no screener module deps)
**Files modified:** `backend/app/infrastructure/screener/scoring.py` (new)
**Autonomous:** true

<read_first>
- `.planning/phases/03-screener-engine/03-RESEARCH.md` — section 3.5 (Scoring System) for compute_score code, per-filter tracking, Approach A vs B
- `.planning/phases/03-screener-engine/03-CONTEXT.md` — D-13 (score in results)
</read_first>

<action>
Create `backend/app/infrastructure/screener/scoring.py`:

```python
"""Score computation from matched filters and indicator values."""

from __future__ import annotations

import pandas as pd


def compute_score(
    mask: pd.Series,
    total_filters: int,
    per_filter_masks: dict[str, pd.Series] | None = None,
) -> pd.Series:
    """Compute fractional score for each symbol.

    Phase 3 uses Approach A: fraction-based scoring.
    score = (matched_filters / total_filters) × 100

    With multiple AND-combined filters, the score is binary:
    100.0 if all filters pass, 0.0 otherwise.

    When per_filter_masks is provided (for future OR-group support),
    computes a nuanced score: (sum of passed filters / total_filters) × 100.

    Args:
        mask: Boolean Series where True means the symbol passed all filters.
        total_filters: Total number of filter expressions.
        per_filter_masks: Optional dict of {filter_name: boolean_mask}
            for per-filter granularity.

    Returns:
        Series with float scores 0.0–100.0.
    """
    if per_filter_masks and total_filters > 1:
        # Nuanced scoring: count how many filters each symbol passed
        passed_count = sum(
            per_filter_masks[name].astype(int)
            for name in per_filter_masks
            if name in per_filter_masks
        )
        return (passed_count / total_filters * 100.0).clip(0, 100)

    # Binary: all or nothing (AND-combined)
    return mask.astype(float) * 100.0


def compute_pass_rates(
    per_filter_masks: dict[str, pd.Series],
) -> dict[str, float]:
    """Compute pass rate for each filter.

    Returns dict mapping filter_name -> pass_rate (0.0–1.0).
    pass_rate = number of True / total symbols.

    Args:
        per_filter_masks: Dict of {filter_name: boolean_mask}.

    Returns:
        Dict of {filter_name: pass_rate}.
    """
    rates: dict[str, float] = {}
    for name, mask in per_filter_masks.items():
        total = len(mask)
        passed = int(mask.sum()) if total > 0 else 0
        rates[name] = round(passed / total, 4) if total > 0 else 0.0
    return rates


def rank_results(
    scores: pd.Series,
    ascending: bool = False,
) -> pd.Series:
    """Rank symbols by score.

    Args:
        scores: Series of scores indexed by symbol.
        ascending: If True, lowest scores first (default: highest first).

    Returns:
        Series with rank (1 = best). NaN scores are ranked last.
    """
    return scores.rank(method="min", ascending=ascending, na_option="bottom").astype(int)
```
</action>

<acceptance_criteria>
1. `backend/app/infrastructure/screener/scoring.py` exists
2. `grep "def compute_score" backend/app/infrastructure/screener/scoring.py` exists
3. `grep "def compute_pass_rates" backend/app/infrastructure/screener/scoring.py` exists
4. `grep "def rank_results" backend/app/infrastructure/screener/scoring.py` exists
5. `grep "from __future__ import annotations" backend/app/infrastructure/screener/scoring.py` is first import
6. `cd backend && python -c "from backend.app.infrastructure.screener.scoring import compute_score, compute_pass_rates, rank_results; print('OK')"` prints `OK`
7. `cd backend && mypy --strict backend/app/infrastructure/screener/scoring.py` exits 0
</acceptance_criteria>

---

### Task 3.3: ScreenEngine Orchestrator

**Wave:** 3
**Depends on:** Task 2.1 (indicators_extended), Task 2.2 (filters.py), Task 2.3 (configs.py, models.py), Task 2.4 (cache.py), Task 3.1 (broadcasting.py), Task 3.2 (scoring.py)
**Files modified:** `backend/app/infrastructure/screener/engine.py` (new)
**Autonomous:** true

<read_first>
- `backend/app/infrastructure/screener/filters.py` — verify `list_filters()`, `_FILTER_REGISTRY`, filter function signatures
- `backend/app/infrastructure/screener/cache.py` — verify `IndicatorCache.get_latest()` signature
- `backend/app/infrastructure/screener/configs.py` — verify `ScreenConfig`, `FilterRule` models, `load_screen_template()`
- `backend/app/infrastructure/screener/scoring.py` — verify `compute_score()`, `compute_pass_rates()`
- `backend/app/infrastructure/screener/broadcasting.py` — verify `broadcast_timeframe()`, `sort_timeframes()`
- `.planning/phases/03-screener-engine/03-RESEARCH.md` — sections 5.2 (screen method code), 9.2 (class diagram), 9.3 (data flow)
- `.planning/phases/03-screener-engine/03-CONTEXT.md` — D-17 (vectorized), D-18 (parallel), D-19 (performance targets)
- `backend/app/core/logging.py` — verify `set_correlation_id()`, `get_logger()`
- `backend/app/domain/models.py` — verify `ScreenResult` model
</read_first>

<action>
Create `backend/app/infrastructure/screener/engine.py` with:

```python
"""ScreenEngine — orchestrator for the screener filter pipeline.

Flow:
1. Load ScreenConfig from YAML
2. Resolve filter dependencies → indicator names needed
3. For each timeframe (top-down):
   a. Cache.get_latest() → latest indicator values
   b. Broadcast higher-TF indicators to this TF (ffill)
   c. Apply each filter → boolean masks
   d. AND-combine masks within timeframe
   e. AND-combine with parent mask (narrowing candidates)
4. Compute scores
5. Build results DataFrame
6. Output: DataFrame / CSV / JSON / WebSocket
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from backend.app.core.config import settings
from backend.app.core.logging import get_logger, set_correlation_id
from backend.app.domain.models import ScreenResult
from backend.app.infrastructure.screener.broadcasting import sort_timeframes
from backend.app.infrastructure.screener.cache import IndicatorCache
from backend.app.infrastructure.screener.configs import ScreenConfig, load_screen_template
from backend.app.infrastructure.screener.filters import _FILTER_REGISTRY, list_filters
from backend.app.infrastructure.screener.models import FilterRunResult, ScreenRunResult
from backend.app.infrastructure.screener.scoring import compute_pass_rates, compute_score

log = get_logger("conflu.screener.engine")


class ScreenEngine:
    """Orchestrator for screen evaluation.

    Loads config, resolves indicators, applies filters, scores results.
    Supports multi-timeframe top-down narrowing and parallel asset classes.
    """

    def __init__(self) -> None:
        self._cache = IndicatorCache()
        self._log = get_logger("conflu.screener.engine")
        self._correlation_id: str | None = None

    async def screen(
        self,
        config: ScreenConfig | str,
        symbols: list[str] | None = None,
        timeframes: list[str] | None = None,
    ) -> ScreenRunResult:
        """Run a screen configuration against all symbols.

        Args:
            config: ScreenConfig instance or name of screen template.
            symbols: Optional subset of symbols to screen (None = all).
            timeframes: Override timeframes (None = from config).

        Returns:
            ScreenRunResult with matched symbols and filter statistics.
        """
        self._correlation_id = set_correlation_id()
        start = time.monotonic()

        # 1. Resolve config
        if isinstance(config, str):
            cfg = load_screen_template(config)
        else:
            cfg = config

        tfs = sort_timeframes(timeframes or cfg.timeframes, descending=True)
        filters_by_tf = self._group_filters_by_timeframe(cfg.filters, tfs)

        # 2. Track per-filter results
        per_filter_masks: dict[str, pd.Series] = {}
        candidates_mask: pd.Series | None = None
        all_indicator_data: dict[str, Any] = {}

        # 3. Evaluate top-down
        for tf in tfs:
            tf_filters = filters_by_tf.get(tf, [])
            if not tf_filters:
                continue

            # Get indicator data for this timeframe
            indicator_data = await self._load_indicator_data(tf, symbols)

            if indicator_data is None or indicator_data.empty:
                self._log.warning("no_indicator_data", timeframe=tf)
                continue

            # Store for later use
            all_indicator_data[tf] = indicator_data

            # Apply each filter
            for flt in tf_filters:
                filter_def = _FILTER_REGISTRY.get(flt.indicator)
                if filter_def is None:
                    self._log.warning("filter_not_found", filter_name=flt.indicator)
                    continue

                try:
                    mask = filter_def.func(indicator_data, **flt.params)

                    # Apply negation if specified
                    if flt.negate:
                        mask = ~mask

                    # Fill NaN with False (no match)
                    mask = mask.fillna(False)

                    per_filter_masks[flt.indicator] = mask

                    # AND-combine into timeframe mask
                    if candidates_mask is None:
                        candidates_mask = mask
                    else:
                        candidates_mask = candidates_mask & mask

                except Exception:
                    self._log.exception(
                        "filter_evaluation_failed",
                        filter_name=flt.indicator,
                        timeframe=tf,
                    )

            # Early exit: no candidates left
            if candidates_mask is not None and not candidates_mask.any():
                self._log.info("no_candidates", timeframe=tf)
                break

        # 4. Compute scores
        total_filters = len(cfg.filters)
        if candidates_mask is None:
            scores = pd.Series(dtype=float)
        else:
            scores = compute_score(
                mask=candidates_mask,
                total_filters=total_filters,
                per_filter_masks=per_filter_masks,
            )

        # 5. Build results
        matched_symbols = (
            list(scores[scores > 0].index) if not scores.empty else []
        )
        pass_rates = compute_pass_rates(per_filter_masks) if per_filter_masks else {}

        # Build matched symbols detail
        symbol_details: list[dict[str, Any]] = []
        for sym in matched_symbols:
            symbol_details.append({
                "symbol": sym,
                "score": float(scores[sym]),
                "matched_filters": [
                    name for name, mask in per_filter_masks.items()
                    if sym in mask.index and mask.get(sym, False)
                ],
            })

        # Build filter run results
        filter_results = []
        for name, mask in per_filter_masks.items():
            filter_results.append(
                FilterRunResult(
                    filter_name=name,
                    category=_FILTER_REGISTRY.get(name, None) or "",
                    matched=int(mask.sum()) if not mask.empty else 0,
                    total=len(mask) if not mask.empty else 0,
                    pass_rate=pass_rates.get(name, 0.0),
                )
            )

        duration_ms = (time.monotonic() - start) * 1000

        return ScreenRunResult(
            screen_name=cfg.name,
            timestamp=datetime.now(timezone.utc),
            duration_ms=round(duration_ms, 2),
            total_symbols=len(scores) if not scores.empty else 0,
            symbols_matched=len(matched_symbols),
            filter_results=filter_results,
            symbols=symbol_details,
        )

    async def _load_indicator_data(
        self,
        timeframe: str,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame | None:
        """Load indicator data for a timeframe from cache.

        Aggregates all cached indicators into a single wide DataFrame.
        If cache is empty, computes on-the-fly.
        """
        # Get all registered indicators
        all_indicators = list_filters()
        indicator_names = list(all_indicators.keys())

        # For each indicator, get latest values
        data_frames: list[pd.DataFrame] = []
        for ind_name in indicator_names:
            try:
                df = await self._cache.get_latest(
                    indicator_name=ind_name,
                    timeframe=timeframe,
                    symbols=symbols,
                )
                if df is not None and not df.empty:
                    # Pivot to wide format: symbol -> indicator value
                    df = df.rename(columns={"value": ind_name})
                    data_frames.append(df[["symbol", ind_name]])
            except Exception:
                self._log.debug(
                    "indicator_data_unavailable",
                    indicator=ind_name,
                    timeframe=timeframe,
                )

        if not data_frames:
            return None

        # Merge all indicator values on symbol
        result = data_frames[0]
        for df in data_frames[1:]:
            result = result.merge(df, on="symbol", how="outer")

        return result

    def _group_filters_by_timeframe(
        self,
        filters: list[Any],
        timeframes: list[str],
    ) -> dict[str, list[Any]]:
        """Group filter rules by their target timeframe."""
        grouped: dict[str, list[Any]] = {tf: [] for tf in timeframes}
        for flt in filters:
            tf = flt.timeframe if hasattr(flt, "timeframe") else "1D"
            if tf in grouped:
                grouped[tf].append(flt)
            else:
                # Put in the nearest higher timeframe
                grouped[timeframes[0]].append(flt)
        return grouped

    async def screen_to_csv(
        self,
        config: ScreenConfig | str,
        path: str | Path,
        symbols: list[str] | None = None,
    ) -> ScreenRunResult:
        """Run screen and export results to CSV."""
        from backend.app.infrastructure.screener.export import export_csv

        result = await self.screen(config, symbols=symbols)
        if result.symbols:
            df = pd.DataFrame(result.symbols)
            export_csv(df, path)
        return result

    async def screen_to_json(
        self,
        config: ScreenConfig | str,
        path: str | Path,
        symbols: list[str] | None = None,
    ) -> ScreenRunResult:
        """Run screen and export results to JSON."""
        from backend.app.infrastructure.screener.export import export_json

        result = await self.screen(config, symbols=symbols)
        if result.symbols:
            df = pd.DataFrame(result.symbols)
            export_json(df, path)
        return result
```

Key behaviors:
- Top-down timeframe evaluation (1D → 4h → 1h) narrowing candidates at each step
- NaN values in mask → False (no match)
- Early exit when no candidates remain
- Per-filter mask tracking for scoring and reporting
- Async throughout using IndicatorCache (which uses thread-pool for DuckDB)
</action>

<acceptance_criteria>
1. `backend/app/infrastructure/screener/engine.py` exists
2. `grep "class ScreenEngine" backend/app/infrastructure/screener/engine.py` exists
3. `grep "async def screen" backend/app/infrastructure/screener/engine.py` exists with top-down narrowing logic
4. `grep "async def screen_to_csv" backend/app/infrastructure/screener/engine.py` exists
5. `grep "async def screen_to_json" backend/app/infrastructure/screener/engine.py` exists
6. `grep "_FILTER_REGISTRY" backend/app/infrastructure/screener/engine.py` shows filter resolution from registry
7. `grep "IndicatorCache" backend/app/infrastructure/screener/engine.py` shows cache integration
8. `grep "candidates_mask" backend/app/infrastructure/screener/engine.py` shows top-down narrowing
9. `grep "per_filter_masks" backend/app/infrastructure/screener/engine.py` shows per-filter tracking
10. `grep "ScreenRunResult" backend/app/infrastructure/screener/engine.py` shows correct return type
11. `cd backend && python -c "from backend.app.infrastructure.screener.engine import ScreenEngine; print('OK')"` prints `OK`
12. `cd backend && mypy --strict backend/app/infrastructure/screener/engine.py` exits 0
</acceptance_criteria>

---

## Wave 4: Streaming, Export & Templates

**Depends on:** Wave 3 (engine, broadcasting, scoring exist)

Tasks 4.1 and 4.2 can run in parallel.

---

### Task 4.1: ConnectionManager & WebSocket Streaming

**Wave:** 4
**Depends on:** Task 3.3 (ScreenEngine)
**Files modified:** `backend/app/infrastructure/screener/streaming.py` (new)
**Autonomous:** true

<read_first>
- `.planning/phases/03-screener-engine/03-RESEARCH.md` — section 7 (Real-Time WebSocket Streaming) for ConnectionManager code, message format, reconnection strategy, sequence numbers
- `.planning/phases/03-screener-engine/03-CONTEXT.md` — D-14, D-15, D-16, D-22
- `backend/app/core/config.py` — verify `ScreenSettings.stream_interval_s`, `max_history`
- `backend/app/infrastructure/screener/engine.py` — verify `ScreenEngine.screen()` signature
- `backend/app/infrastructure/screener/configs.py` — verify `load_screen_template()`
</read_first>

<action>
Create `backend/app/infrastructure/screener/streaming.py` with:

```python
"""WebSocket connection manager for real-time screener streaming.

Provides ConnectionManager class with:
- Connection registration/disconnection per screen
- Sequence-numbered message broadcasting
- Delta updates (changed symbols only)
- Reconnection with history replay
- Heartbeat and configurable intervals
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.infrastructure.screener.configs import load_screen_template
from backend.app.infrastructure.screener.engine import ScreenEngine
from backend.app.infrastructure.screener.models import ScreenStreamMessage

log = get_logger("conflu.screener.streaming")


class ConnectionManager:
    """Manages WebSocket connections with sequence tracking.

    Each screen has its own set of connections, sequence counter,
    and message history for reconnection support.
    """

    def __init__(self) -> None:
        self._connections: dict[str, set[Any]] = defaultdict(set)
        self._sequences: dict[str, int] = defaultdict(int)
        self._history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._max_history: int = settings.screen.max_history
        self._stream_interval: float = settings.screen.stream_interval_s
        self._engine = ScreenEngine()
        self._log = get_logger("conflu.screener.streaming")

    async def register(self, screen_id: str, websocket: Any) -> None:
        """Register a WebSocket connection for a screen.

        Args:
            screen_id: Screen identifier (template name).
            websocket: FastAPI WebSocket connection instance.
        """
        self._connections[screen_id].add(websocket)
        self._log.info("client_connected", screen_id=screen_id)

        # Send full snapshot on initial connection
        try:
            result = await self._engine.screen(screen_id)
            snapshot = {
                "type": "screen_update",
                "screen_id": screen_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "results": result.symbols,
                "total_matched": result.symbols_matched,
                "total_symbols": result.total_symbols,
            }
            await self._send_with_sequence(screen_id, snapshot, websocket)
        except Exception:
            self._log.exception("initial_screen_failed", screen_id=screen_id)
            await websocket.send_json({
                "type": "error",
                "screen_id": screen_id,
                "message": "Failed to load initial screen data",
            })

    async def disconnect(self, screen_id: str, websocket: Any) -> None:
        """Remove a WebSocket connection.

        Args:
            screen_id: Screen identifier.
            websocket: WebSocket connection to remove.
        """
        self._connections[screen_id].discard(websocket)
        self._log.info("client_disconnected", screen_id=screen_id)

    async def broadcast(self, screen_id: str, message: dict[str, Any]) -> None:
        """Send a message to all clients on a screen, with sequencing.

        Args:
            screen_id: Screen identifier.
            message: Message dict to broadcast.
        """
        # Add sequence number
        self._sequences[screen_id] += 1
        message["sequence"] = self._sequences[screen_id]

        # Store in history for reconnection
        self._history[screen_id].append(dict(message))
        if len(self._history[screen_id]) > self._max_history:
            self._history[screen_id].pop(0)

        # Send to all connected clients
        disconnected: list[Any] = []
        for ws in list(self._connections.get(screen_id, set())):
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self._connections[screen_id].discard(ws)

    async def _send_with_sequence(
        self,
        screen_id: str,
        message: dict[str, Any],
        websocket: Any,
    ) -> None:
        """Send a message to a single client with sequence number."""
        self._sequences[screen_id] += 1
        message["sequence"] = self._sequences[screen_id]
        try:
            await websocket.send_json(message)
        except Exception:
            self._log.warning("send_failed", screen_id=screen_id)

    async def resync(self, screen_id: str, websocket: Any, last_sequence: int) -> None:
        """Replay missed messages for a reconnecting client.

        Args:
            screen_id: Screen identifier.
            websocket: Reconnecting WebSocket connection.
            last_sequence: Last sequence number the client received.
        """
        history = self._history.get(screen_id, [])

        if len(history) >= self._max_history or last_sequence < (
            self._sequences[screen_id] - len(history)
        ):
            # Too many missed — send full snapshot instead
            self._log.info(
                "resync_full_snapshot",
                screen_id=screen_id,
                last_sequence=last_sequence,
            )
            await self.register(screen_id, websocket)
            return

        # Replay missed messages
        missed = [
            msg for msg in history
            if msg.get("sequence", 0) > last_sequence
        ]
        for msg in missed:
            try:
                await websocket.send_json(msg)
            except Exception:
                self._log.warning("resync_send_failed", screen_id=screen_id)
                break

        self._log.info(
            "resync_complete",
            screen_id=screen_id,
            replayed=len(missed),
        )

    async def stream_loop(self, screen_id: str) -> None:
        """Background task that periodically evaluates a screen and broadcasts.

        This is designed to be launched as an asyncio task. It runs the
        screen at the configured interval and pushes delta updates.

        Args:
            screen_id: Screen template name to stream.
        """
        self._log.info("stream_started", screen_id=screen_id)

        while True:
            try:
                # Check if any clients remain
                if not self._connections.get(screen_id):
                    await asyncio.sleep(self._stream_interval)
                    continue

                # Run screen evaluation
                result = await self._engine.screen(screen_id)

                # Build delta update
                message = {
                    "type": "screen_update",
                    "screen_id": screen_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "interval_ms": self._stream_interval * 1000,
                    "results": result.symbols,
                    "total_matched": result.symbols_matched,
                    "total_symbols": result.total_symbols,
                }

                await self.broadcast(screen_id, message)

            except asyncio.CancelledError:
                self._log.info("stream_cancelled", screen_id=screen_id)
                break
            except Exception:
                self._log.exception("stream_error", screen_id=screen_id)

            await asyncio.sleep(self._stream_interval)

    def get_connections_count(self, screen_id: str) -> int:
        """Get number of connected clients for a screen."""
        return len(self._connections.get(screen_id, set()))

    async def handle_client_message(
        self,
        screen_id: str,
        websocket: Any,
        data: dict[str, Any],
    ) -> None:
        """Handle an incoming client control message.

        Supported messages:
        - {"type": "ping"} → responds with pong
        - {"type": "resync", "last_sequence": N} → replay missed messages
        - {"type": "change_interval", "interval_ms": N} → update stream rate

        Args:
            screen_id: Screen identifier.
            websocket: Client WebSocket connection.
            data: Parsed JSON message from client.
        """
        msg_type = data.get("type", "")

        if msg_type == "ping":
            await websocket.send_json({
                "type": "pong",
                "screen_id": screen_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        elif msg_type == "resync":
            last_seq = data.get("last_sequence", 0)
            await self.resync(screen_id, websocket, last_seq)

        elif msg_type == "change_interval":
            new_interval = data.get("interval_ms", self._stream_interval * 1000)
            self._stream_interval = max(1.0, new_interval / 1000)
            self._log.info(
                "stream_interval_changed",
                screen_id=screen_id,
                interval_s=self._stream_interval,
            )

        else:
            self._log.warning(
                "unknown_client_message",
                screen_id=screen_id,
                message_type=msg_type,
            )
```

Key design decisions (from RESEARCH.md Q3 and Q4):
- Phase 3 provides `ConnectionManager` class + streaming runtime
- Actual FastAPI WebSocket route is minimal (wired in Phase 6 with auth and rate limiting)
- Streams use delta updates (full snapshot on connect, then delta)
- Reconnection with sequence numbers and history replay
</action>

<acceptance_criteria>
1. `backend/app/infrastructure/screener/streaming.py` exists
2. `grep "class ConnectionManager" backend/app/infrastructure/screener/streaming.py` exists
3. `grep "async def register" backend/app/infrastructure/screener/streaming.py` exists
4. `grep "async def disconnect" backend/app/infrastructure/screener/streaming.py` exists
5. `grep "async def broadcast" backend/app/infrastructure/screener/streaming.py` exists with sequence numbering
6. `grep "async def resync" backend/app/infrastructure/screener/streaming.py` exists with history replay
7. `grep "async def stream_loop" backend/app/infrastructure/screener/streaming.py` exists
8. `grep "async def handle_client_message" backend/app/infrastructure/screener/streaming.py` exists with ping/pong and resync
9. `grep "type.*screen_update\|type.*delta_update\|type.*pong"` shows all message types
10. `grep "from __future__ import annotations" backend/app/infrastructure/screener/streaming.py` is first import
11. `cd backend && python -c "from backend.app.infrastructure.screener.streaming import ConnectionManager; print('OK')"` prints `OK`
12. `cd backend && mypy --strict backend/app/infrastructure/screener/streaming.py` exits 0
</acceptance_criteria>

---

### Task 4.2: Export Utilities (CSV/JSON)

**Wave:** 4
**Depends on:** None (pure pandas utilities)
**Files modified:** `backend/app/infrastructure/screener/export.py` (new)
**Autonomous:** true

<read_first>
- `.planning/phases/03-screener-engine/03-RESEARCH.md` — section 8 (Export Formats) for exact pandas to_csv/to_json code
- `.planning/phases/03-screener-engine/03-CONTEXT.md` — D-13 (export formats)
</read_first>

<action>
Create `backend/app/infrastructure/screener/export.py`:

```python
"""Screen results export to CSV and JSON formats."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd

from backend.app.core.logging import get_logger

log = get_logger("conflu.screener.export")


def export_csv(results: pd.DataFrame, path: str | Path) -> None:
    """Export screen results to CSV.

    Columns: symbol, score, matched_filters, indicator_values, timestamp.
    matched_filters stored as pipe-separated string.

    Args:
        results: DataFrame with screen results.
        path: Output file path.
    """
    df = results.copy()

    # Flatten list columns for CSV
    if "matched_filters" in df.columns:
        df["matched_filters"] = df["matched_filters"].apply(
            lambda x: "|".join(x) if isinstance(x, list) else str(x)
        )

    # Flatten indicator_values dict
    if "indicator_values" in df.columns and "indicators" not in df.columns:
        df["indicators"] = df["indicator_values"].apply(
            lambda x: str(x) if isinstance(x, dict) else ""
        )
    elif "indicators" in df.columns:
        df["indicators"] = df["indicators"].apply(
            lambda x: str(x) if isinstance(x, dict) else ""
        )

    df.to_csv(path, index=False)
    log.info("csv_exported", path=str(path), rows=len(df))


def export_json(
    results: pd.DataFrame,
    path: str | Path,
    orient: Literal["records", "split", "index"] = "records",
) -> None:
    """Export screen results to JSON.

    Args:
        results: DataFrame with screen results.
        path: Output file path.
        orient: JSON orientation:
            - 'records' → list of objects (default)
            - 'split' → {columns, index, data}
            - 'index' → {index: {column: value}}
    """
    results.to_json(path, orient=orient, date_format="iso")
    log.info("json_exported", path=str(path), orient=orient, rows=len(results))
```
</action>

<acceptance_criteria>
1. `backend/app/infrastructure/screener/export.py` exists
2. `grep "def export_csv" backend/app/infrastructure/screener/export.py` exists
3. `grep "def export_json" backend/app/infrastructure/screener/export.py` exists
4. `grep "matched_filters.*|.join" backend/app/infrastructure/screener/export.py` shows list flattening for CSV
5. `grep "to_csv" backend/app/infrastructure/screener/export.py` shows pandas CSV export
6. `grep "to_json" backend/app/infrastructure/screener/export.py` shows pandas JSON export
7. `grep "from __future__ import annotations" backend/app/infrastructure/screener/export.py` is first import
8. `cd backend && python -c "from backend.app.infrastructure.screener.export import export_csv, export_json; print('OK')"` prints `OK`
9. `cd backend && mypy --strict backend/app/infrastructure/screener/export.py` exits 0
</acceptance_criteria>

---

### Task 4.3: Screener Package Init, Post-Ingestion Hook & Screen Templates

**Wave:** 4
**Depends on:** Tasks 4.1, 4.2 (streaming.py, export.py exist)
**Files modified:**
- `backend/app/infrastructure/screener/__init__.py` (new) — package exports
- `backend/app/infrastructure/ingest/__init__.py` — add post-ingestion cache hook
- `config/screens/` — create directory with 5 YAML template files
**Autonomous:** true

<read_first>
- `.planning/phases/03-screener-engine/03-RESEARCH.md` — sections 6.1 (YAML schema), 6.2 (templates table), 9.1 (module layout), Q8 (post-ingestion hook)
- `.planning/phases/03-screener-engine/03-CONTEXT.md` — D-11, D-12
- `backend/app/infrastructure/ingest/__init__.py` — existing `run_ingestion()` function structure, import pattern
</read_first>

<action>
**Part A: Create `backend/app/infrastructure/screener/__init__.py`:**

```python
"""Screener engine — multi-timeframe vectorized screening, filter pipeline, indicator cache, WebSocket streaming.

Usage:
    from backend.app.infrastructure.screener import ScreenEngine, list_filters
    engine = ScreenEngine()
    result = await engine.screen("trend-follower")
"""

from __future__ import annotations

from backend.app.infrastructure.screener.cache import IndicatorCache
from backend.app.infrastructure.screener.configs import list_screen_templates, load_screen_template
from backend.app.infrastructure.screener.engine import ScreenEngine
from backend.app.infrastructure.screener.filters import list_filters, list_filters_by_category
from backend.app.infrastructure.screener.streaming import ConnectionManager

__all__ = [
    "ScreenEngine",
    "IndicatorCache",
    "ConnectionManager",
    "list_filters",
    "list_filters_by_category",
    "list_screen_templates",
    "load_screen_template",
]
```

**Part B: Add post-ingestion cache update to `backend/app/infrastructure/ingest/__init__.py`:**

Insert after the `_update_symbol_metadata` call (after line ~147, before `metrics.log_summary()`):

```python
        # Update indicator cache after successful ingestion
        if not dry_run:
            try:
                from backend.app.infrastructure.screener.cache import IndicatorCache
                cache = IndicatorCache()
                cache_updated = await cache.update_cache(
                    timeframes=tfs,
                    indicator_names=None,  # all cached indicators
                )
                if cache_updated > 0:
                    log.info("indicator_cache_updated", new_values=cache_updated)
            except Exception:
                log.exception("indicator_cache_update_failed")
```

Also add the import of `IngestionReport` at the module level (it's already imported — verify it exists).

**Part C: Create `config/screens/` directory with 5 YAML templates:**

Template 1: `config/screens/trend-follower.yaml`
```yaml
name: "Trend Follower"
description: "Uptrending assets with momentum and volume confirmation"
asset_classes:
  - equities
  - crypto
timeframes:
  - 1D
  - 4h
filters:
  - category: trend
    indicator: price_above_ema
    params:
      period: 200
    operator: gt
    timeframe: "1D"
  - category: trend
    indicator: adx_trending
    params:
      threshold: 25
    timeframe: "1D"
  - category: momentum
    indicator: macd_bullish
    timeframe: "4h"
  - category: volume
    indicator: rvol_high
    params:
      threshold: 1.2
    timeframe: "4h"
```

Template 2: `config/screens/mean-reversion.yaml`
```yaml
name: "Mean Reversion"
description: "Oversold assets near Bollinger Band lower with volume spike"
asset_classes:
  - equities
  - crypto
  - forex
timeframes:
  - 1D
  - 1h
filters:
  - category: momentum
    indicator: rsi_oversold
    params:
      threshold: 30
    timeframe: "1D"
  - category: volatility
    indicator: bb_touch
    timeframe: "1D"
  - category: volume
    indicator: rvol_high
    params:
      threshold: 1.5
    timeframe: "1h"
```

Template 3: `config/screens/breakout.yaml`
```yaml
name: "Breakout"
description: "Price breaking out with volume and momentum confirmation"
asset_classes:
  - equities
  - crypto
timeframes:
  - 1D
  - 4h
filters:
  - category: trend
    indicator: price_above_ema
    params:
      period: 50
    operator: gt
    timeframe: "1D"
  - category: volume
    indicator: rvol_high
    params:
      threshold: 1.5
    timeframe: "1D"
  - category: momentum
    indicator: macd_bullish
    timeframe: "4h"
```

Template 4: `config/screens/volume-surge.yaml`
```yaml
name: "Volume Surge"
description: "High relative volume with above-average price movement"
asset_classes:
  - equities
  - crypto
  - forex
timeframes:
  - 1D
  - 1h
filters:
  - category: volume
    indicator: rvol_high
    params:
      threshold: 2.0
    timeframe: "1D"
  - category: volatility
    indicator: atr_percentile_high
    params:
      percentile: 75
    timeframe: "1D"
  - category: momentum
    indicator: macd_bullish
    timeframe: "1h"
```

Template 5: `config/screens/oversold-bounce.yaml`
```yaml
name: "Oversold Bounce"
description: "Deeply oversold with bullish reversal pattern"
asset_classes:
  - equities
  - crypto
timeframes:
  - 1D
  - 4h
filters:
  - category: momentum
    indicator: rsi_oversold
    params:
      threshold: 25
    timeframe: "1D"
  - category: volatility
    indicator: bb_touch
    timeframe: "1D"
  - category: pattern
    indicator: candle_engulfing
    params:
      direction: bullish
    timeframe: "1D"
```
</action>

<acceptance_criteria>
1. `backend/app/infrastructure/screener/__init__.py` exists with exports for ScreenEngine, IndicatorCache, ConnectionManager, list_filters
2. `grep "IndicatorCache\|cache.update_cache" backend/app/infrastructure/ingest/__init__.py` shows post-ingestion hook
3. `grep "async def" backend/app/infrastructure/ingest/__init__.py` after the hook insertion still has valid Python
4. Directory `config/screens/` exists
5. `config/screens/trend-follower.yaml` exists with 4 filters (price_above_ema, adx_trending, macd_bullish, rvol_high)
6. `config/screens/mean-reversion.yaml` exists with 3 filters (rsi_oversold, bb_touch, rvol_high)
7. `config/screens/breakout.yaml` exists with 3 filters (price_above_ema, rvol_high, macd_bullish)
8. `config/screens/volume-surge.yaml` exists with 3 filters (rvol_high, atr_percentile_high, macd_bullish)
9. `config/screens/oversold-bounce.yaml` exists with 3 filters (rsi_oversold, bb_touch, candle_engulfing)
10. Each YAML file has valid `name`, `description`, `asset_classes`, `timeframes`, `filters` keys
11. `cd backend && python -c "from backend.app.infrastructure.screener import ScreenEngine, IndicatorCache, ConnectionManager, list_filters, list_screen_templates; print('OK')"` prints `OK`
</acceptance_criteria>

---

## Wave 5: Tests

**Depends on:** Waves 2-4 (all screener modules exist)

---

### Task 5.1: Tests for Filters, Configs, Broadcasting, Scoring

**Wave:** 5
**Depends on:** Task 2.2 (filters.py), Task 2.3 (configs.py, models.py), Task 3.1 (broadcasting.py), Task 3.2 (scoring.py), Task 4.3 (screen templates)
**Files modified:**
- `backend/tests/test_screener_filters.py` (new)
- `backend/tests/test_screener_configs.py` (new)
- `backend/tests/test_screener_broadcasting.py` (new)
- `backend/tests/test_screener_scoring.py` (new)
**Autonomous:** true

<read_first>
- `backend/tests/conftest.py` — verify `synthetic_ohlcv` fixture, `in_memory_db` fixture patterns
- `backend/tests/test_indicators.py` — verify test class naming convention, pytest patterns
- `.planning/phases/03-screener-engine/03-RESEARCH.md` — section 13 Q6 (Testing Strategy) for test file list
</read_first>

<action>
Create 4 test files following the existing test patterns:

**1. `backend/tests/test_screener_filters.py`** — test each filter category:

```python
"""Tests for screener filter registry and built-in filters."""
```
- `TestFilterRegistry` — test `list_filters()` returns all categories, test `list_filters_by_category()`
- `TestTrendFilters` — synthetic data tests for `price_above_ema`, `price_below_ema`, `adx_trending`, `adx_non_trending`, `ema_cross`
- `TestMomentumFilters` — tests for `rsi_oversold/overbought/range`, `macd_bullish/bearish`, `macd_histogram_rising`
- `TestVolumeFilters` — tests for `rvol_high/low`, `obv_slope_positive`
- `TestVolatilityFilters` — tests for `atr_percentile_high/low`, `bb_inside`, `bb_touch`
- `TestPatternFilters` — tests for `candle_engulfing`, `candle_hammer`, `candle_doji` using synthetic OHLCV
- `TestFilterComposition` — test AND/OR combination of multiple filters returns correct boolean masks

**2. `backend/tests/test_screener_configs.py`** — test ScreenConfig validation:

```python
"""Tests for screen configuration loading and validation."""
```
- `TestScreenConfig` — test valid config loads, test invalid filter name raises ValueError, test missing file raises FileNotFoundError
- `TestFilterRule` — test default values, test operator validation
- `TestScreenTemplates` — test all 5 YAML templates load successfully via `load_screen_template()`, test `list_screen_templates()` returns 5 entries
- `TestScreenRunResult` — test model serialization
- `TestScreenStreamMessage` — test all message types

**3. `backend/tests/test_screener_broadcasting.py`** — test timeframe utilities:

```python
"""Tests for multi-timeframe broadcasting utilities."""
```
- `TestTimeframeRank` — test sort order: `sort_timeframes(["1h", "1D", "4h"])` returns `["1D", "4h", "1h"]`
- `TestBroadcastTimeframe` — test `broadcast_timeframe()` correctly forward-fills values, test error on non-DatetimeIndex input
- `TestAlignment` — test that forward-filled values correctly propagate

**4. `backend/tests/test_screener_scoring.py`** — test score computation:

```python
"""Tests for scoring engine."""
```
- `TestComputeScore` — test binary (and-combined) returns 100/0, test nuanced scoring with per_filter_masks
- `TestComputePassRates` — test all-pass, some-pass, all-fail
- `TestRankResults` — test descending sort order
</action>

<acceptance_criteria>
1. `backend/tests/test_screener_filters.py` exists with test classes for all 5 categories
2. `backend/tests/test_screener_configs.py` exists with template loading tests
3. `backend/tests/test_screener_broadcasting.py` exists with timeframe sort and broadcast tests
4. `backend/tests/test_screener_scoring.py` exists with score and pass rate tests
5. `grep "TestFilterRegistry\|TestTrendFilters\|TestMomentumFilters\|TestPatternFilters"` — all categories tested
6. `grep "list_screen_templates\|load_screen_template" backend/tests/test_screener_configs.py` shows template tests
7. `grep "sort_timeframes\|broadcast_timeframe" backend/tests/test_screener_broadcasting.py` shows broadcast tests
8. `grep "compute_score\|compute_pass_rates\|rank_results" backend/tests/test_screener_scoring.py` shows scoring tests
9. `cd backend && python -m pytest tests/test_screener_filters.py tests/test_screener_configs.py tests/test_screener_broadcasting.py tests/test_screener_scoring.py -v` exits 0 with tests collected
</acceptance_criteria>

---

### Task 5.2: Tests for Engine, Cache, Export

**Wave:** 5
**Depends on:** Task 3.3 (engine.py), Task 2.4 (cache.py), Task 4.2 (export.py)
**Files modified:**
- `backend/tests/test_screener_engine.py` (new)
- `backend/tests/test_screener_cache.py` (new)
- `backend/tests/test_screener_export.py` (new)
**Autonomous:** true

<read_first>
- `backend/tests/conftest.py` — verify `in_memory_db` fixture, `synthetic_ohlcv` fixture
- `backend/app/infrastructure/screener/engine.py` — verify `ScreenEngine` API
- `backend/app/infrastructure/screener/cache.py` — verify `IndicatorCache` method signatures
- `backend/app/infrastructure/screener/export.py` — verify `export_csv()`, `export_json()` signatures
</read_first>

<action>
Create 3 test files:

**1. `backend/tests/test_screener_engine.py`**:

```python
"""Tests for ScreenEngine orchestrator."""
```
- `TestScreenEngine`:
  - Test with valid template name returns `ScreenRunResult`
  - Test with `ScreenConfig` object returns correct `screen_name`
  - Test symbols_matched is 0 when no symbols pass (empty filter set should be handled)
  - Test that engine handles unknown filter names gracefully
- Integration test: Load a test template, run screen, verify result shape with `synthetic_ohlcv` fixture

**2. `backend/tests/test_screener_cache.py`**:

```python
"""Tests for IndicatorCache with in-memory DuckDB."""
```
- `TestIndicatorCacheInit` — test class initializes with config
- `TestGetLatest` — test returns DataFrame with correct columns
- `TestGetSeries` — test with tmp_path for series query
- `TestCacheStatus` — test returns dict with expected keys
- Use `in_memory_db` fixture for database-dependent tests

**3. `backend/tests/test_screener_export.py`**:

```python
"""Tests for CSV/JSON export utilities."""
```
- `TestExportCsv` — test writes CSV file, test content includes header and data rows
- `TestExportJson` — test writes JSON file, test content is valid JSON
- `TestExportFormats` — test with empty DataFrame, test with matched_filters list column
</action>

<acceptance_criteria>
1. `backend/tests/test_screener_engine.py` exists with engine tests
2. `backend/tests/test_screener_cache.py` exists with cache tests
3. `backend/tests/test_screener_export.py` exists with export tests
4. `grep "ScreenEngine\|ScreenRunResult" backend/tests/test_screener_engine.py` shows engine tests
5. `grep "IndicatorCache\|in_memory_db" backend/tests/test_screener_cache.py` shows cache tests
6. `grep "export_csv\|export_json" backend/tests/test_screener_export.py` shows export tests
7. `cd backend && python -m pytest tests/test_screener_engine.py tests/test_screener_cache.py tests/test_screener_export.py -v` exits 0 with tests collected
</acceptance_criteria>

---

### Task 5.3: Tests for Streaming

**Wave:** 5
**Depends on:** Task 4.1 (streaming.py)
**Files modified:** `backend/tests/test_screener_streaming.py` (new)
**Autonomous:** true

<read_first>
- `backend/app/infrastructure/screener/streaming.py` — verify `ConnectionManager` method signatures
- `backend/tests/conftest.py` — verify fixture patterns
</read_first>

<action>
Create `backend/tests/test_screener_streaming.py`:

```python
"""Tests for WebSocket ConnectionManager."""
```
- `TestConnectionManager`:
  - Test register/disconnect connection tracking
  - Test broadcast adds sequence numbers
  - Test resync replays missed messages
  - Test handle_client_message handles ping/pong
  - Test broadcast with no connections doesn't raise
  - Test get_connections_count

Note: These tests use a mock WebSocket (simple class with `send_json` method) rather than requiring a live server. See test pattern:

```python
class MockWebSocket:
    """Minimal mock for testing WebSocket connections."""
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_json(self, data: dict) -> None:
        self.messages.append(data)
```
</action>

<acceptance_criteria>
1. `backend/tests/test_screener_streaming.py` exists
2. `grep "class TestConnectionManager" backend/tests/test_screener_streaming.py` exists
3. `grep "register\|disconnect\|broadcast\|resync\|handle_client_message"` — tests for all major methods
4. `grep "MockWebSocket" backend/tests/test_screener_streaming.py` shows mock pattern
5. `cd backend && python -m pytest tests/test_screener_streaming.py -v` exits 0 with tests collected
</acceptance_criteria>

---

## Verification Plan

After all waves execute, verify:

1. **Module imports**: `cd backend && python -c "from backend.app.infrastructure.screener import ScreenEngine, IndicatorCache, ConnectionManager, list_filters, list_screen_templates"` — all imports work
2. **Type checking**: `cd backend && mypy --strict app/` — exits 0
3. **Tests**: `cd backend && python -m pytest tests/ -v --tb=short` — all tests pass
4. **YAML templates**: All 5 screen templates load via `load_screen_template()` without validation errors
5. **Post-ingestion hook**: Verify `run_ingestion()` imports and calls `IndicatorCache.update_cache()` indirectly

---

*Phase 3 — Screener Engine*
*Planned: 2026-06-19*
*Waves: 5 | Tasks: 15 | Must Haves: 18*
