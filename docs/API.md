# API Reference — conflu.ai

**Last Updated:** 2026-06-23

## Base URL
`/api/v1`

---

## Screener API (`/api/v1/screen`)

### POST `/screen`
Run a technical screen against all active symbols.

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
  "meta": { "timestamp": "2026-06-23T12:00:00Z", "duration_ms": 145.2 }
}
```

**Filter Structure:**
- `config`: Predefined template name (e.g., `trend-follower`, `breakout`, `mean-reversion`, `oversold-bounce`, `volume-surge`) OR custom config object
- `symbols`: Optional subset of symbols to screen
- `timeframes`: Override timeframes from config
- `export_format`: Optional `json` or `csv` for file download

---

## Screener WebSocket (`/api/v1/ws/screener/{screen_id}`)
Real-time screen updates with configurable interval.

**Subscribe:**
```json
{ "type": "subscribe", "channels": ["screener:trend-follower"] }
```

**Events:**
- `screen_update` — Full screen result refresh
- `delta_update` — Incremental symbol changes

---

## Data API (`/api/v1/data`)

### GET `/symbols`
List available symbols.
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

## Screen Management (`/api/v1/screens`)
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/` | Create saved screen |
| GET | `/` | List saved screens |
| GET | `/{id}` | Get screen detail |
| PUT | `/{id}` | Update screen |
| DELETE | `/{id}` | Delete screen |
| POST | `/{id}/share` | Create shareable link |
| POST | `/replay` | Historical replay |

## Alerts (`/api/v1/alerts`)
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/` | Create alert |
| GET | `/` | List alerts |
| GET | `/{id}` | Get alert detail |
| PUT | `/{id}` | Update alert |
| DELETE | `/{id}` | Delete alert |
| GET | `/{id}/history` | Trigger history |

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
| `screener:{screen_id}` | `screen_update`, `delta_update` |
| `price:{symbol}` | `price_update` |
| `signal:{symbol}` | `signal_trigger` |
| `backtest:{run_id}` | `backtest.progress`, `backtest.complete` |
| `risk:{portfolio_id}` | `risk_update` |
| `alert` | `alert_triggered` |
| `replay:{result_id}` | `replay_progress` |

---

## Error Response Format (D-19)
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
