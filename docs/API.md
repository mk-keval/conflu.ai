# API Reference — conflu.ai

**Last Updated:** 2026-07-20

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

### GET `/ticker/{symbol}/options`
Fetch options chain data from Yahoo Finance.

**Query:**
- `expiry` (optional): Expiry date `YYYY-MM-DD`. Defaults to nearest Friday.

**Response 200:** `ApiResponse<OptionsChainResponse>`
```json
{
  "data": {
    "symbol": "AAPL",
    "expiry": "2026-08-21",
    "calls": [{"strike": 170.0, "lastPrice": 12.50, "bid": 12.40, "ask": 12.60, "impliedVolatility": 0.35, "volume": 12000, "openInterest": 45000, "delta": 0.65, "gamma": 0.02, "theta": -0.08, "vega": 0.15}],
    "puts": [...],
    "totalCallOI": 450000,
    "totalPutOI": 380000,
    "availableExpiries": ["2026-08-21", "2026-08-28", "2026-09-18", "2026-10-16", "2026-12-18", "2027-01-15"]
  }
}
```

Cache: 5-minute in-memory TTL. NaN handling for volume, OI, bid, ask, IV, Greeks. Try/catch around option_chain() with graceful error.

### GET `/ticker/{symbol}/options-flow`
Enhanced options flow analysis with dealer positioning and advanced flow metrics.

**Query:**
- `expiry` (optional): Expiry date `YYYY-MM-DD`. Defaults to nearest Friday.

**Response 200:** `ApiResponse<OptionsFlowResponse>`
```json
{
  "data": {
    "symbol": "AAPL",
    "spot": 185.50,
    "ivRank": 50,
    "ivMean": 0.32,
    "maxPain": 182.50,
    "gexTotal": 1250000.50,
    "gexFlip": 190.00,
    "gexByStrike": {"180.0": 45000.2, "185.0": 32000.1},
    "putCallRatio": 0.84,
    "unusualActivity": {
      "calls": [{"strike": 190.0, "volume": 5000, "oi": 500, "iv": 0.45}],
      "puts": [{"strike": 175.0, "volume": 8000, "oi": 600, "iv": 0.52}]
    },
    "keyLevels": {"maxPain": 182.5, "gexFlip": 190.0, "highOICalls": [...], "highOIPuts": [...]},
    "termStructure": {"2026-08-21": 0.32, "2026-08-28": 0.34, "2026-09-18": 0.35},
    "totalCallOI": 450000,
    "totalPutOI": 380000,
    "availableExpiries": [...]
  }
}
```

Metrics: GEX by strike, flip level, max pain magnet, dealer gamma positioning, unusual volume (volume > 2× OI & OI > 100), high OI strikes, term structure across 6 expiries.

### GET `/ticker/{symbol}/news`
Fetch news/catalyst feed from Yahoo Finance.

**Query:**
- `limit` (optional, default: 10): Number of headlines to return.

**Response 200:** `ApiResponse<NewsResponse>`
```json
{
  "data": [
    {
      "title": "Apple Reports Strong Q3 Earnings",
      "publisher": "Yahoo Finance",
      "link": "https://finance.yahoo.com/...",
      "timestamp": 1721491200,
      "sentiment": "positive",
      "summary": "Apple exceeded analyst expectations..."
    }
  ]
}
```

Sentiment scoring: keyword-based positive/negative/neutral classification. Cache: 5-minute in-memory TTL.

### GET `/ticker/{symbol}/chart`
Fetch intraday chart OHLCV data from Yahoo Finance.

**Query:**
- `interval` (optional, default: `15m`, values: `5m`, `15m`, `1h`, `4h`, `1d`): Chart bar interval.
- `range` (optional, default: `7d`, values per interval: `5m`/`15m`→`7d`, `1h`→`60d`, `4h`→`730d`, `1d`→`1mo`): Data range.

**Response 200:** `ApiResponse<ChartDataResponse>`
```json
{
  "data": [
    {"time": 1721448000, "open": 184.20, "high": 185.80, "low": 184.00, "close": 185.50, "volume": 25000000}
  ]
}
```

Output format is TradingView Lightweight Charts compatible. Auto-range limiting enforces Yahoo's interval constraints.

**Response:** `ApiResponse<ChartResponse>` (symbol, interval, prices array)

---

## Portfolio Analysis API (`/api/v1/portfolio`)
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/analyze` | Analyze a list of symbols — returns per-symbol summaries, correlation matrix, sector allocation, combined beta, portfolio volatility, equal-risk position sizing |

**Request body:**
```json
{
  "symbols": ["AAPL", "MSFT", "GOOGL", "NVDA"]
}
```
**Response:** `ApiResponse<PortfolioResponse>` with `symbol_count`, `analyses[]` (sector, price, conviction, action), `sector_allocation`, `combined_beta`, `portfolio_volatility`, `equal_risk_pct`, `correlation_matrix[]`, `high_correlation_pairs[]`

---

## Market Regime API (`/api/v1/market`)
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/regime` | Composite market regime snapshot: VIX analysis, risk appetite SPY/TLT spread, sector breadth, safe haven demand (GLD), yield curve signal (TLT/SHY). Returns 0-100 score with 5 sub-indicators. |
| GET | `/events` | Upcoming economic events (FOMC, CPI, PCE) with countdown timers |
| GET | `/narrative` | Auto-generated market summary text |

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

---

## Professional Mode API (`/api/v1/professional`)

Guided workflow endpoints for working professionals. All endpoints optional auth (will require auth in Phase 6+).

---

### GET `/morning-brief`
Get the complete morning brief (regime, market internals, sector rotation, top 9 tickers from 3 regime-matched screens).

**Query Parameters:** None (auto-detects regime, uses cached screen selection)

**Response:** `ApiResponse<MorningBriefResponse>`

```json
{
  "data": {
    "date": "2026-07-26",
    "regime": "strong_trend",
    "regimeDescription": "Strong uptrend — favor trend following and breakout strategies",
    "marketInternals": {
      "vix": 14.2,
      "advanceDeclineRatio": 2.1,
      "dollarIndex": 104.3,
      "sp500Futures": 5620.5,
      "nasdaqFutures": 19850.0
    },
    "sectorRotation": {
      "leadingSectors": ["XLK", "XLC", "XLY"],
      "laggingSectors": ["XLU", "XLP", "XLRE"],
      "regimeAlignment": "risk_on"
    },
    "sectors": [
      {"symbol": "XLK", "name": "Technology", "changePct": 1.8, "rsRank": 92},
      {"symbol": "XLF", "name": "Financials", "changePct": 0.5, "rsRank": 65}
    ],
    "screenSections": [
      {
        "screenName": "trend-follower",
        "screenLabel": "Trend Follower",
        "regimeMatchScore": 0.92,
        "tickers": [
          {
            "symbol": "AAPL",
            "screenName": "trend-follower",
            "screenScore": 87.3,
            "confluenceScore": 85,
            "entry": 228.50,
            "stopLoss": 222.10,
            "targets": [241.00, 253.50],
            "verdict": "STRONG_BUY",
            "conviction": 8,
            "livePrice": 229.10,
            "premarketChangePct": 0.45,
            "educationHints": {
              "pe_ratio": "You're paying $28 for $1 of earnings...",
              "rsi": "Momentum at 62. Neutral."
            }
          }
        ]
      }
    ],
    "generatedAt": "2026-07-26T10:00:00Z"
  },
  "meta": {"timestamp": "2026-07-26T10:00:00Z", "requestId": "..."}
}
```

---

### GET `/verdict/{symbol}`
Get a simplified, actionable verdict for a single ticker.

**Path Parameters:**
- `symbol` (string, required) — Ticker symbol (e.g., `AAPL`)

**Response:** `ApiResponse<SimplifiedVerdictResponse>`

```json
{
  "data": {
    "symbol": "AAPL",
    "action": "STRONG_BUY",
    "conviction": 8,
    "verdictSummary": "Strong uptrend with institutional accumulation. Buy pullbacks to rising 20-day EMA.",
    "keyMetrics": {
      "pe_ratio": 28.5,
      "rsi": 62,
      "atr_pct": 1.8,
      "beta": 1.2,
      "market_cap": 3.5e12,
      "volume_ratio": 1.3
    },
    "entryZone": "227.50 - 229.00",
    "stopLoss": 222.10,
    "targets": [241.00, 253.50],
    "positionSize": {
      "shares": 16,
      "amount": 5000,
      "riskPct": 1.5,
      "cappedBy": "position"
    },
    "education": [
      {"metric": "pe_ratio", "explanation": "You're paying $28.50 for $1 of earnings..."},
      {"metric": "rsi", "explanation": "Momentum at 62. Neutral — not overbought."}
    ]
  },
  "meta": {"timestamp": "...", "requestId": "..."}
}
```

**Notes:**
- `positionSize` present only if account size configured in settings
- `cappedBy`: `"position"` (5% cap), `"sector"` (15% cap), or `"kelly"` (uncapped)

---

### POST `/watchlist/analyze`
Batch analyze multiple symbols for watchlist building.

**Request Body:**
```json
{ "symbols": ["AAPL", "MSFT", "NVDA"] }
```

**Response:** `ApiResponse<WatchlistAnalyzeResponse>`
```json
{
  "data": {
    "items": [
      {"symbol": "AAPL", "verdict": "STRONG_BUY", "conviction": 8, "positionSize": {"shares": 16, "amount": 5000, "riskPct": 1.5}},
      {"symbol": "MSFT", "verdict": "BUY", "conviction": 6, "positionSize": {"shares": 12, "amount": 4500, "riskPct": 1.5}}
    ]
  }
}
```

---

### GET `/education/{metric}`
Get plain-English explanation for a metric.

**Path Parameters:**
- `metric` (string) — Metric key (e.g., `pe_ratio`, `rsi`, `atr_pct`, `beta`)

**Query Parameters:**
- `symbol` (optional) — For symbol-specific LLM enhancement

**Response:** `ApiResponse<EducationResponse>`
```json
{
  "data": {
    "metric": "pe_ratio",
    "symbol": "AAPL",
    "plainEnglish": "You're paying $28.50 for $1 of earnings. Market average is ~20x. This means AAPL is priced for above-average growth.",
    "valueContext": "At 28.5x, you're paying a premium. Check if earnings growth justifies it.",
    "actionable": "If growth slows, multiple compression risk is high.",
    "source": "template",
    "cached": false
  }
}
```

**Source values:** `"template"` (static), `"llm"` (enhanced), `"combined"` (both)

---

### GET `/position-size`
Calculate position size from trade parameters.

**Query Parameters:**
| Param | Type | Required | Default |
|-------|------|----------|---------|
| `symbol` | string | Yes | — |
| `account_equity` | number | Yes | — |
| `entry` | number | Yes | — |
| `stop_loss` | number | Yes | — |
| `conviction` | string | Yes | — (high/medium/low) |
| `max_position_pct` | number | No | 0.05 |
| `max_sector_pct` | number | No | 0.15 |
| `risk_per_trade_pct` | number | No | 0.015 |

**Response:** `ApiResponse<PositionSizeResponse>`
```json
{
  "data": {
    "positionSize": 5000,
    "shares": 16,
    "riskAmount": 112,
    "riskPct": 1.5,
    "convictionMultiplier": 0.67,
    "cappedBy": "position"
  }
}
```

---

### GET `/alerts/preferences`
Get user alert preferences.

**Response:** `ApiResponse<AlertPreferences>`

---

### PUT `/alerts/preferences`
Update alert preferences.

**Request Body:** `AlertPreferences` (all boolean fields)

---

### GET `/alerts`
Get recent in-app alerts.

**Query Parameters:**
- `limit` (default: 50)
- `unread_only` (default: false)

**Response:** `ApiResponse<Alert[]>` where `Alert = { id, type, symbol, title, message, timestamp, read }`

---

### Alert Types
| Type | Trigger | Channels |
|------|---------|----------|
| `morning_brief` | Daily 6 AM generation | Email + In-app |
| `stop_hit` | Position stop loss breached | Email + Push + Browser |
| `target_hit` | Position target (1R/2R) reached | In-app |
| `earnings` | Earnings tomorrow for watchlist symbol | Email |
| `regime_change` | Market regime transition detected | Email + In-app |
| `weekly_review` | Sunday 7 PM summary | Email (opt-in) |

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

---

## Workflow API (`/api/v1/workflow`)

Paper-trade journal and gate enforcement endpoints. Single source of truth: CSV journal in `docs/paper_trades/`.

### GET `/journal`
Read all journal rows (open + closed).

**Query Parameters:**
- `limit` (optional, max 10000) — Max rows to return

**Response:** `ApiResponse<JournalResponse>`
```json
{
  "data": {
    "rows": [...],
    "count": 127
  },
  "meta": {...}
}
```

### GET `/journal/open`
Read open positions (rows with no `date_closed`).

**Response:** `ApiResponse<OpenPositionsResponse>`
```json
{
  "data": {
    "positions": [...],
    "count": 5,
    "total_size_pct": 12.5,
    "sector_exposure": {"Technology": 8.0, "Financials": 4.5}
  }
}
```

### GET `/journal/closed`
Read closed trades (measurable sample for expectancy).

**Response:** `ApiResponse<ClosedTradesResponse>`
```json
{
  "data": {
    "trades": [...],
    "count": 42,
    "win_rate": 0.64,
    "expectancy_r": 0.47,
    "profit_factor": 2.1
  }
}
```

### GET `/journal/capital`
Available capital for new positions.

**Query Parameters:**
- `account_value` (optional, gt=0) — Explicit account value

**Response:** `ApiResponse<AvailableCapitalResponse>`

### POST `/paper-trades/enforce`
**Touchpoint A** — Run gate enforcement and write paper trades.

Fetches morning brief, evaluates candidates through 7-step gate, writes accepted trades to today's CSV.

**Request Body:**
```json
{
  "min_conviction": 5,
  "only": "AAPL,MSFT"  // optional comma-separated symbols
}
```

**Response:** `ApiResponse<EnforceResponse>`
```json
{
  "data": {
    "accepted": [
      {"symbol": "AAPL", "gate_verdict": "PASS", "entry_price": 228.5, "stop_loss": 222.1, "position_size_pct": 2.1, "target_1": 241.0, "target_2": 253.5}
    ],
    "rejected": [
      {"symbol": "TSLA", "gate_verdict": "FAIL", "rejected": true, "failed_step": "Risk/Reward", "reason": "R/R floor not met: 1.8 < 2.5"}
    ],
    "message": "2 accepted, 1 rejected — written to 2026-09-28.csv"
  }
}
```

### POST `/paper-trades/sync-exits`
**Touchpoint B** — Sync exits from OHLCV (infer + apply).

Fetches daily OHLCV for open journal rows, infers exit (stop/target/time), writes exit data when `apply=true`.

**Request Body:**
```json
{ "apply": false }
```

**Response:** `ApiResponse<SyncExitsResponse>`
```json
{
  "data": {
    "updated": 3,
    "skipped": 1,
    "items": [
      {
        "symbol": "AAPL",
        "exit_date": "2026-09-27",
        "exit_price": 241.0,
        "exit_reason": "target_1",
        "realized_r": 1.9,
        "pnl_usd": 950.0,
        "mfe_r": 2.1,
        "mae_r": -0.3,
        "plan_adherence": 1.0,
        "applied": false
      }
    ],
    "message": "3 exit(s) would be applied (1 skipped) — re-run with apply=true to persist"
  }
}
```

### GET `/expectancy`
Expectancy metrics per template/regime combination.

**Query Parameters:**
- `min_trades` (default: 30, ge=1) — Minimum trades for elite status

**Response:** `ApiResponse<ExpectancyResponse>`
```json
{
  "data": {
    "items": [
      {
        "template": "trend-follower",
        "regime": "strong_trend",
        "n_trades": 42,
        "win_rate": 0.62,
        "expectancy_r": 0.47,
        "profit_factor": 2.1,
        "avg_r": 0.47,
        "avg_win_r": 1.2,
        "avg_loss_r": -0.8,
        "max_win_r": 3.5,
        "max_loss_r": -1.0,
        "total_r": 19.7,
        "is_elite": true,
        "elite_min_trades": 30
      }
    ],
    "elite_count": 3,
    "total_combinations": 12
  }
}
```

### GET `/expectancy/elite`
Only elite template/regime combinations (n≥min_trades, expectancy>0).

**Response:** `ApiResponse<ExpectancyResponse>` (same shape, only elite items)

### POST `/expectancy/rolling`
Rolling expectancy for a specific filter (symbol/template/regime).

**Request Body:**
```json
{
  "symbol": "AAPL",
  "template": "trend-follower",
  "regime": "strong_trend",
  "window": 30
}
```

**Response:** `ApiResponse<RollingExpectancyResponse | null>`
```json
{
  "data": {
    "symbol": "AAPL",
    "template": "trend-follower",
    "regime": "strong_trend",
    "window": 15,
    "win_rate": 0.67,
    "expectancy_r": 0.52,
    "profit_factor": 2.4,
    "total_r": 7.8
  }
}
```

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
