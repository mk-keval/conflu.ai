# Screener Guide

## Running a Screen

Use the screener to find assets matching technical criteria across multiple timeframes.

### Using the API

```bash
curl -X POST http://localhost:8000/api/v1/screen \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["SPY", "QQQ", "AAPL"],
    "timeframes": ["1D", "4h"],
    "filters": [
      {"type": "trend", "indicator": "ema_20", "operator": "gt", "value": "ema_50"},
      {"type": "momentum", "indicator": "rsi", "operator": "gt", "value": 50}
    ]
  }'
```

### Filter Types

| Type | Description | Example |
|------|-------------|---------|
| trend | Trend indicators | EMA crossover, SMA slope |
| momentum | Momentum oscillators | RSI > 70, MACD bullish |
| volume | Volume analysis | Volume > avg(20) |
| volatility | Volatility filters | ATR > 2% |
| pattern | Chart patterns | Engulfing, Doji |

## Saving Screens

Saved screens are persisted in DuckDB and can be loaded, shared, and replayed against historical data.

## Alerts

Create alerts that trigger when screen conditions are met, with WebSocket push notifications.
