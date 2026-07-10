# API Reference — conflu.ai

**Last Updated:** 2026-07-09

## Base URL
`/api/v1`

---

## Screener API (`/api/v1/screen`)

### POST `/screen`
Run a TV Screener-based screen against 12,000+ symbols.

**Request Body:**
```json
{
  "config": "trend-follower" | { "name": "...", "description": "...", "asset_classes": [...], "timeframes": [...], "filters": [...] },
  "symbols": ["AAPL", "MSFT"],
  "timeframes": ["1D", "4h"],
  "export_format": "json" | "csv"
}
```

**Response:** `ApiResponse<ScreenSymbolResult[]>`
```json
{
  "data": [
    {
      "symbol": "AAPL",
      "score": 85.5,
      "matched_filters": ["price_above_ema", "adx_trending", "macd_bullish"],
      "indicator_values": { "ema_200": 145.2, "rsi": 58.3, "macd_line": 2.1 },
      "elite": {
        "rs_rating": 85,
        "inst_quality": 78,
        "signal_conviction": "high",
        "wyckoff_phase": "accumulation",
        "factor_conflicts": []
      }
    }
  ],
  "meta": { "timestamp": "2026-07-03T12:00:00Z", "duration_ms": 1120.5 }
}
```

**Elite enrichment fields:**
| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `rs_rating` | int | 1-99 | Multi-factor relative strength percentile vs screen cohort |
| `inst_quality` | int | 0-100 | Institutional quality score (market cap, volume, analyst, dividend) |
| `signal_conviction` | string | high/medium/low | Combined RS + quality + factor conflict assessment |
| `wyckoff_phase` | string | accumulation/markup/distribution/markdown | Price-volume heuristic Wyckoff phase proxy |
| `factor_conflicts` | string[] | — | Detected divergences between trend/momentum/volume factors |

**Filter Structure:**
- `config`: Predefined template name (e.g., `trend-follower`, `breakout`, `mean-reversion`, `oversold-bounce`, `volume-surge`, `breakdown`, `short-squeeze`, `distribution`) OR custom config object
- `symbols`: Optional subset of symbols to screen
- `timeframes`: Override timeframes from config (supports multi-TF weighted stacking)
- `export_format`: Optional `json` or `csv` for file download

---

## Data API (`/api/v1/data`)

### GET `/symbols`
List available symbols (from DuckDB).
- **Query:** `asset_class` (optional), `active_only` (default: true)
- **Response:** `SymbolInfo[]`

### GET `/{symbol}`
Get OHLCV data for a symbol.
- **Query:** `timeframe` (default: 1D), `start`, `end`, `limit` (default: 500)
- **Response:** OHLCV candles

### GET `/indicators/{symbol}`
Get indicator values.
- **Query:** `timeframe` (default: 1D), `indicators` (comma-separated), `limit` (default: 200)
- **Response:** Indicator time series

---

## Backtest API (`/api/v1/backtest`)
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/` | Run a new backtest |
| GET | `/{run_id}` | Get backtest run status & metrics |
| POST | `/optimize-v2` | Run parameter optimization (grid/random/bayesian) |
| POST | `/{run_id}/regimes` | Detect market regimes for a completed run |
| POST | `/{run_id}/report` | Generate backtest report (HTML/PDF/JSON) |
| POST | `/compare` | Compare multiple backtest runs |
| GET | `/{run_id}/trades` | Get trades for a backtest run |
| GET | `/{run_id}/equity` | Get equity curve for a backtest run |
| GET | `/{run_id}/timeline` | Get regime timeline for a backtest run |
| GET | `/{run_id}/optimization` | Get optimization results for a run |

## Risk API (`/api/v1/risk`)
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/var` | Value at Risk (historical/parametric/MC) |
| GET | `/beta` | Beta vs benchmark |
| GET | `/correlation` | Correlation matrix |
| POST | `/kelly` | Kelly fraction from backtest |
| POST | `/position-size` | Position sizing |
| GET | `/summary` | Portfolio risk summary |

## Sector Rotation API (`/api/v1/sector-rotation`)
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | All sector performance with 1D/1W returns, RS Z-scores, momentum, flow signals, rotation phase, market regime |
| GET | `/history` | Historical daily sector rankings for charting |
| GET | `/{symbol}` | Deep-dive: price history (3mo), relative strength, volume analysis for a single sector ETF |

**Supported sectors:** XLF (Financials), XLK (Technology), XLV (Health Care), XLI (Industrials), XLB (Materials), XLE (Energy), XLU (Utilities), XLRE (Real Estate), XLY (Consumer Cyclical), XLP (Consumer Staples), XLC (Communication Services)

**Response:** `ApiResponse<SectorRotationResponse>`
```json
{
  "data": {
    "sectors": [
      {
        "symbol": "XLK",
        "name": "Technology",
        "price": 218.45,
        "change_1d": 1.25,
        "change_1w": 3.42,
        "relative_strength_1d": 0.85,
        "relative_strength_1w": 1.12,
        "momentum_score": 72.3,
        "trend": "bullish",
        "flow_signal": "inflow",
        "flow_strength": 65.5
      }
    ],
    "leaders": ["XLK", "XLC", "XLY"],
    "laggards": ["XLU", "XLP", "XLRE"],
    "rotation_phase": "growth_lead",
    "market_regime": "broad_market_strength"
  }
}
```

## Ticker Analysis (`/api/v1/ticker/{symbol}/analyze`)

### POST `/ticker/{symbol}/analyze`
Run the full elite-trader-grade ticker analysis pipeline — technical, fundamental, earnings, sentiment, and risk — and return a synthesized actionable verdict.

**Request Body:**
```json
{
  "symbol": "QGEN",
  "timeframe": "1D",
  "tv_data": {
    "close": 41.34,
    "RSI": 65.36,
    "ADX": 26.46,
    "ATR": 1.37,
    "change": 8.79,
    "relative_volume_10d_calc": 3.82,
    "volume": 10619030,
    "SMA20": 39.50,
    "SMA50": 38.20,
    "SMA200": 36.80,
    "VWAP": 40.50,
    "sector": "Health Technology"
  }
}
```

**Response 200:** `ApiResponse<TickerAnalysisResponse>`
```json
{
  "data": {
    "symbol": "QGEN",
    "price": 41.92,
    "change_pct": 8.79,
    "sector": "Health Technology",
    "technical": { "score": 0.79, "ma_alignment": "bullish", ... },
    "fundamental": { "score": 0.04, ... },
    "earnings": { "score": -0.07, ... },
    "sentiment": { "score": 0.20, ... },
    "risk": { "score": 0.07, ... },
    "verdict": {
      "action": "WATCH",
      "conviction": 3,
      "entry_zone_low": 41.01,
      "entry_zone_high": 42.27,
      "stop_loss": 39.08,
      "targets": [47.06, 51.84],
      "risk_reward": 1.5,
      "position_size_pct": 0,
      "key_red_flags": [],
      "buy_triggers": ["Trend is up — buy on pullbacks to rising MA support."],
      "sell_triggers": ["Monitor earnings next quarter."],
      "thesis": "Neutral outlook (score 25%). Bull case: Bullish MA stack..."
    },
    "execution_ms": 377
  },
  "meta": { "timestamp": "2026-07-09T19:35:08.688Z" }
}
```

**Modules:**
| Module | Input Source | Output |
|--------|-------------|--------|
| Technical | `tv_data` (SMA, RSI, ADX, ATR, volume) | MA alignment, RSI regime, ADX strength, ATR volatility, BB position, MACD |
| Fundamental | yfinance info dict | P/E, EPS, margins, D/E, revenue growth, FCF yield, div yield |
| Earnings | yfinance earnings data | Surprise %, beat rate, EPS trend, next earnings date |
| Sentiment | yfinance info (analyst, ownership, short interest) | Consensus, PT upside, insider status, short interest |
| Risk | ATR + beta (yfinance) | Volatility regime, stop loss, position sizing |
| Synthesis | All 5 module scores + regime weights | Action + conviction + entry/stop/targets + triggers + thesis |

**Yfinance Data:** 5-minute in-memory TTL cache. Fresh data fetched on cache miss.

---

## Market Regime API (`/api/v1/market`)
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/regime` | Composite market regime snapshot: VIX analysis, risk appetite SPY/TLT spread, sector breadth, safe haven demand (GLD), yield curve signal (TLT/SHY). Returns 0-100 score with 5 sub-indicators. |

**Response:** `ApiResponse<MarketRegimeResponse>`
```json
{
  "data": {
    "composite_score": 52.1,
    "regime_label": "Neutral",
    "regime_color": "#facc15",
    "vix": { "name": "VIX", "value": 16.46, "score": 60.0, "weight": 0.3, "status": "normal" },
    "risk_appetite": { "name": "Risk Appetite", "value": 0.5, "score": 27.5, "weight": 0.25, "status": "risk_off" },
    "sector_breadth": { "name": "Sector Breadth", "value": 50.0, "score": 45.0, "weight": 0.2, "status": "mixed" },
    "safe_haven": { "name": "Safe Haven", "value": -4.13, "score": 85.0, "weight": 0.15, "status": "risk_on" },
    "yield_curve": { "name": "Yield Curve", "value": 0.37, "score": 55.0, "weight": 0.1, "status": "normal" }
  }
}
```

**Regime Labels (by score):**
| Score Range | Label | Color |
|-------------|-------|-------|
| 80-100 | Exuberance | `#22c55e` |
| 65-79 | Risk-On | `#4ade80` |
| 50-64 | Neutral | `#facc15` |
| 35-49 | Cautious | `#fb923c` |
| 20-34 | Risk-Off | `#f87171` |
| 0-19 | Crisis | `#dc2626` |

---

## Health (`/health`)
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Liveness probe |
| GET | `/ready` | Readiness probe (DB, cache checks) |
| GET | `/ingestion` | Ingestion pipeline health |

---

## Websocket Events Summary
| Channel | Events |
|---------|--------|
| `price:{symbol}` | `price_update` |
| `signal:{symbol}` | `signal_trigger` |
| `backtest:{run_id}` | `backtest.progress`, `backtest.complete` |
| `risk:{portfolio_id}` | `risk_update` |

---

## Error Response Format
All errors return:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": { "field": "config", "issue": "required" },
    "request_id": "abc-123"
  }
}
```
