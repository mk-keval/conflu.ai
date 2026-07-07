# API Reference — conflu.ai

**Last Updated:** 2026-07-07

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
      "indicator_values": { "ema_200": 145.2, "rsi": 58.3, "macd_line": 2.1 }
    }
  ],
  "meta": { "timestamp": "2026-07-03T12:00:00Z", "duration_ms": 1120.5 }
}
```

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
