# TV Screener Specialist — Skill

**Description:** Master of `tradingview-screener` Python package. Knows every column, filter syntax, timeframe quirk, index format, rate limit, and error mode. Translates YAML screen configs into optimal TV Queries and extracts maximum signal for confluence scoring.

**Domain:** TradingView Screener discovery for equities screening pipeline.

**Triggers:**
- "screen the market using TV"
- "how do I use tradingview-screener for X"
- "what TV columns are available"
- "how to filter by MACD/RSI/EMA in TV"
- "multi-timeframe screening with TV"
- "TV Screener rate limits"
- "tradingview-screener ATR entry/SL/targets"

---

## Core Capabilities

### 1. Column Registry (50+ columns)

| Category | Columns |
|----------|---------|
| **Price** | `close`, `open`, `high`, `low`, `change` |
| **Volume** | `volume`, `relative_volume_10d_calc`, `volume_change`, `turnover`, `OBV` |
| **Momentum** | `RSI`, `RSI7`, `RSI14`, `RSI21`, `STOCH.K`, `STOCH.D`, `CCI`, `CCI20` |
| **Trend** | `MACD.macd`, `MACD.signal`, `MACD.hist`, `EMA9`, `EMA20`, `EMA21`, `EMA50`, `EMA100`, `EMA200`, `SMA20`, `SMA50`, `SMA100`, `SMA200`, `VWAP`, `supertrend`, `supertrend.up`, `supertrend.down`, `ichimoku.*` |
| **Volatility** | `ATR`, `ATR14`, `BB.upper`, `BB.middle`, `BB.lower`, `BB.width` |
| **Strength** | `ADX`, `ADX14` |
| **Fundamentals** | `market_cap_basic`, `price_earnings_ttm`, `earnings_per_share_diluted_ttm`, `dividends_yield_current` |
| **Classification** | `sector`, `industry`, `market`, `country`, `type`, `typespecs` |
| **Sentiment** | `AnalystRating` (StrongBuy, Buy, Hold, Sell, StrongSell), `AnalystRating.tr` |
| **Meta** | `ticker` (format: "NASDAQ:AAPL"), `name` |

### 2. Timeframe Matrix

```python
TIMEFRAMES = {
    "1m":  {"indicators": "limited", "volume": True,  "endpoint": "1m"},
    "5m":  {"indicators": "limited", "volume": True,  "endpoint": "5m"},
    "15m": {"indicators": "most",    "volume": True,  "endpoint": "15m"},
    "30m": {"indicators": "most",    "volume": True,  "endpoint": "30m"},
    "1h":  {"indicators": "all",     "volume": True,  "endpoint": "1h"},
    "2h":  {"indicators": "all",     "volume": True,  "endpoint": "2h"},
    "4h":  {"indicators": "all",     "volume": True,  "endpoint": "4h"},
    "1D":  {"indicators": "all",     "volume": True,  "endpoint": "1D"},
    "1W":  {"indicators": "all",     "volume": False, "endpoint": "1W"},
    "1M":  {"indicators": "all",     "volume": False, "endpoint": "1M"},
}
```

Set via: `q.set_property("interval", "1D")`

### 3. Index Formats

| Index | Format | Status |
|-------|--------|--------|
| S&P 500 | `"SYML:SP;SPX"` | ✅ 498 components |
| Nasdaq 100 | `"SYML:NDX;NDX"` | ❌ Returns 0 (free API) |
| Russell 2000 | `"SYML:SP;RUT"` | ❌ Returns 0 (free API) |

### 4. Filter Map (YAML → TV Query)

```python
FILTER_MAP = {
    "price_above_ema":      lambda p: col("close") > col(f"EMA{p['period']}"),
    "price_below_ema":      lambda p: col("close") < col(f"EMA{p['period']}"),
    "rsi_oversold":         lambda p: col("RSI") < p.get("threshold", 30),
    "rsi_overbought":       lambda p: col("RSI") > p.get("threshold", 70),
    "macd_bullish":         lambda:  col("MACD.macd") > col("MACD.signal"),
    "macd_bearish":         lambda:  col("MACD.macd") < col("MACD.signal"),
    "macd_hist_rising":     lambda:  col("MACD.hist") > col("MACD.hist").shift(1),
    "rvol_high":            lambda p: col("relative_volume_10d_calc") > p.get("threshold", 1.5),
    "adx_trending":         lambda p: col("ADX") > p.get("threshold", 25),
    "ema_cross":            lambda p: col(f"EMA{p['fast']}") > col(f"EMA{p['slow']}"),
    "bb_squeeze":           lambda:  (col("BB.upper") - col("BB.lower")) / col("BB.middle") < 0.1,
    "price_above_vwap":     lambda:  col("close") > col("VWAP"),
    "sector_is":            lambda p: col("sector").isin(p["sectors"]),
    "market_cap_gt":        lambda p: col("market_cap_basic") > p["value"],
    "analyst_strongbuy":    lambda:  col("AnalystRating") == "StrongBuy",
    "dividend_yield_gt":    lambda p: col("dividends_yield_current") > p.get("threshold", 0.03),
}
```

### 5. Complex Logic via `where2()`

```python
from tradingview_screener import And, Or

q.where2(And(
    col("close") > col("EMA200"),
    col("RSI") > 50,
    Or(
        col("MACD.macd") > col("MACD.signal"),
        col("close") > col("VWAP"),
    )
))
```

### 6. Multi-Timeframe Per-Field (v3.2+)

```python
# Get RSI from daily + weekly in one query
col("RSI|1D")
col("RSI|1W")
col("close|4h")
col("MACD.macd|1h")
```

Pipe syntax: `col("FIELD|INTERVAL")` — INTERVAL uses TV prefix convention.

### 7. Rate Limits & Errors

| Constraint | Value |
|------------|-------|
| Free tier | ~30 req/min |
| Data delay | ~15 min (free tier) |
| Batch size | 100 symbols max |
| 400 error | Unknown presets/columns |
| 429 error | Rate limit exceeded |

### 8. TV Screener API Endpoint

```
POST https://scanner.tradingview.com/{market}/scan
```

Available markets: `america`, `crypto`, `forex`, `futures`, `cfd`, `coin`, `euronext`, `bonds`, `options`

---

## Usage Protocol

When invoked for a screening task, this agent:

1. **Receives** a `ScreenConfig` (YAML) or raw filter requirements
2. **Compiles** an optimal TV Query using `Query().select().where().order_by()`
3. **Executes** via `get_scanner_data()` with proper error handling and rate limiting
4. **Returns** normalized `TVDiscoveryResult` with tickers, TV columns, and raw DataFrame
5. **Explains** any filter that couldn't be pushed to TV (falls back to local)

---

## Limitations

| Limitation | Workaround |
|------------|------------|
| No historical data (only current snapshot) | Use DuckDB for historical OHLCV |
| Single timeframe per query | Multi-TF = multiple queries + client-side intersect |
| No cross-timeframe filters in single query | Run per-TF, intersect client-side |
| 100 symbols/batch | Auto-chunk + async gather |
| Free tier = 15-min delayed data | Acceptable for discovery |
| No custom indicator formulas | Push standard indicators; compute custom locally |

---

## Confluence Scoring (from TV data only)

5-factor scoring using ONLY TV columns (no OHLCV required):

| Factor | Weight | Sources |
|--------|--------|---------|
| **Trend** | 30 pts | EMA200, EMA50, EMA20 alignment |
| **Momentum** | 25 pts | MACD, RSI |
| **Volume** | 20 pts | relative_volume_10d_calc, VWAP |
| **Quality** | 15 pts | ADX, BB squeeze |
| **Fundamental** | 10 pts | AnalystRating, market_cap_basic, EPS |

**Entry/SL/Targets:** ATR-based (2x ATR stop, 2:1 / 3:1 R:R targets)

---

## Implementation Files

| File | Purpose |
|------|---------|
| `backend/app/infrastructure/screener/tv_specialist.py` | Core specialist: column registry, filter map, query builder |
| `backend/app/infrastructure/screener/tv_engine.py` | Async orchestration: discovery + scoring + deep analysis |
| `backend/app/infrastructure/screener/confluence_scorer.py` | Scores TV rows using ONLY TV data |
| `backend/app/infrastructure/screener/tv_models.py` | Pydantic models for TV results and scored tickers |
| `backend/app/api/routers/tv_screener.py` | FastAPI endpoints for TV screening |
| `backend/app/infrastructure/analysis/deep_analysis.py` | On-demand OHLCV + backtest + risk for matched tickers |
| `backend/app/infrastructure/screener/configs.py` | ScreenConfig YAML model |
| `config/screens/*.yaml` | 5 screen templates (breakout, mean-reversion, etc.) |

---

## Handoff

This agent outputs `TVDiscoveryResult` which feeds:
1. **ConfluenceScorer** → scores tickers using TV columns only
2. **DeepAnalysisOrchestrator** → fetches OHLCV for top-N, runs backtest/risk
3. **AlertEngine** → (future) schedules re-scan on discovered tickers
