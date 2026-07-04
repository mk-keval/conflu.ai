# Screener Guide

## Overview

The conflu.ai screener evaluates technical filters across multiple timeframes (top-down: 1D → 4h → 1h) against all active symbols via the TradingView Screener API. Results are scored and ranked by the confluence scorer.

## Predefined Templates

| Template | Description | Timeframes | Key Filters |
|----------|-------------|------------|-------------|
| `trend-follower` | Uptrending with momentum & volume | 1D, 4h | Price > EMA200, ADX > 25, MACD bullish, RVOL > 1.2 |
| `trend-follower-mtf` | Multi-timeframe trend (NEW) | 1D, 1W | EMA50 > EMA200 (D), RSI > 60 (D), RSI > 55 (W) |
| `breakout` | Price breaking out with volume | 1D, 4h | Price > EMA50, RVOL > 1.5, MACD bullish |
| `mean-reversion` | Oversold near BB lower + volume | 1D, 1h | RSI < 30, BB touch, RVOL > 1.5 |
| `oversold-bounce` | Deeply oversold + reversal | 1D, 4h | RSI < 25, BB touch, Bullish engulfing |
| `volume-surge` | High volume + volatility | 1D, 1h | RVOL > 2.0, ATR > 75th pct, MACD bullish |

## Running a Screen

### Using the API

```bash
# Run predefined template
curl -X POST http://localhost:8000/api/v1/screen \
  -H "Content-Type: application/json" \
  -d '{"config": "trend-follower"}'

# Run custom multi-timeframe screen
curl -X POST http://localhost:8000/api/v1/screen \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "name": "Custom MTF",
      "description": "EMA50 > EMA200 daily, RSI > 60 daily, RSI > 55 weekly",
      "asset_classes": ["equities", "crypto"],
      "timeframes": ["1D", "1W"],
      "filters": [
        {"category": "trend", "indicator": "ema_compare", "params": {"fast_period": 50, "slow_period": 200, "operator": "gt"}, "timeframe": "1D"},
        {"category": "momentum", "indicator": "rsi_compare", "params": {"threshold": 60, "operator": "gt"}, "timeframe": "1D"},
        {"category": "momentum", "indicator": "rsi_compare", "params": {"threshold": 55, "operator": "gt"}, "timeframe": "1D", "compare_timeframe": "1W"}
      ]
    }
  }'

# Export as CSV
curl -X POST http://localhost:8000/api/v1/screen \
  -H "Content-Type: application/json" \
  -d '{"config": "trend-follower", "export_format": "csv"}' \
  -o results.csv
```

### Filter Reference

| Filter | Category | Description | Params |
|--------|----------|-------------|--------|
| `price_above_ema` | trend | Close > EMA(period) | `period` |
| `price_below_ema` | trend | Close < EMA(period) | `period` |
| `ema_cross` | trend | Fast EMA > Slow EMA | `fast`, `slow` |
| `ema_compare` | trend | Compare two EMAs (NEW) | `fast_period`, `slow_period`, `operator` |
| `price_vs_ema` | trend | Price vs EMA (NEW) | `ema_period`, `operator` |
| `adx_trending` | trend | ADX > threshold | `threshold` |
| `rsi_oversold` | momentum | RSI < threshold | `threshold` |
| `rsi_overbought` | momentum | RSI > threshold | `threshold` |
| `rsi_range` | momentum | RSI between low/high | `low`, `high` |
| `rsi_compare` | momentum | RSI vs threshold (NEW) | `threshold`, `operator` |
| `macd_bullish` | momentum | MACD > Signal | — |
| `macd_bearish` | momentum | MACD < Signal | — |
| `indicator_compare` | trend | Generic indicator compare (NEW) | `indicator_a`, `indicator_b`, `operator` |
| `rvol_high` | volume | RVOL > threshold | `threshold` |
| `bb_touch` | volatility | Price touches BB | — |
| `atr_percentile_high` | volatility | ATR > percentile | `percentile` |
| `candle_engulfing` | pattern | Engulfing pattern | `direction` |

### Multi-Timeframe Filters (NEW)

Filters with `compare_timeframe` merge data from another timeframe:
- **EMA50 > EMA200 (Daily)** — `ema_compare` with `timeframe: "1D"`
- **RSI Daily > 60** — `rsi_compare` with `timeframe: "1D"`
- **RSI Weekly > 55** — `rsi_compare` with `timeframe: "1D", compare_timeframe: "1W"`

The engine merges comparison timeframe data (suffixed with `_1W`, `_4h`, etc.) before evaluating the filter.

## Real-Time Updates

Connect via WebSocket:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/stream');
ws.onopen = () => ws.send(JSON.stringify({
  type: 'subscribe',
  channels: ['screener:trend-follower']
}));
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'screen_update') {
    console.log('New results:', msg.data.symbols);
  }
});
```

## Data Requirements

**The screener requires ingested data.** Run ingestion first:

```bash
# One-time setup (creates DB tables)
python -m backend.app.infrastructure.ingest.cli --setup

# Ingest all asset classes, all timeframes
python -m backend.app.infrastructure.ingest.cli

# Ingest specific asset class/timeframe
python -m backend.app.infrastructure.ingest.cli --asset-class equities --timeframe 1D

# Update indicator cache after ingestion
python -c "
import asyncio
from backend.app.infrastructure.screener.cache import IndicatorCache
asyncio.run(IndicatorCache().update_cache())
"
```

**Automation Note:** Currently ingestion runs on-demand via CLI. Automated scheduling (APScheduler/Celery Beat) is planned but not yet implemented. See [Architecture](ARCHITECTURE.md#data-ingestion) for design.

## Saving & Sharing Screens

- **Save** — Persist custom filter config to DuckDB
- **Load** — Restore saved screen with one click
- **Share** — Generate expiring shareable link
- **Replay** — Backtest screen against historical data
- **Alerts** — Trigger notifications when conditions match

## Filter Composition

- Filters within a timeframe are **AND-combined**
- Timeframes are evaluated **top-down** (1D → 4h → 1h), narrowing candidates
- Use `negate: true` for NOT logic
- Use `operator: "lt"` / `"gt"` / `"eq"` for comparisons
