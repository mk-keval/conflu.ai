# Backtesting Guide

## Running a Backtest

```bash
curl -X POST http://localhost:8000/api/v1/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "SPY",
    "startDate": "2020-01-01",
    "endDate": "2024-01-01",
    "initialCapital": 100000,
    "strategy": {
      "type": "ema_crossover",
      "fastPeriod": 20,
      "slowPeriod": 50
    }
  }'
```

## Parameter Optimization

```bash
curl -X POST http://localhost:8000/api/v1/backtest/optimize-v2 \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "SPY",
    "strategyParams": {"type": "ema_crossover"},
    "searchSpace": {
      "method": "bayesian",
      "parameters": {
        "fastPeriod": {"min": 5, "max": 50, "type": "int"},
        "slowPeriod": {"min": 50, "max": 200, "type": "int"}
      },
      "objectives": ["sharpe"],
      "maxTrials": 100
    }
  }'
```

## Comparing Strategies

Compare multiple backtest runs side-by-side with statistical significance testing.
