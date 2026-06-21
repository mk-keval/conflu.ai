# Risk Management Guide

## Position Sizing

ATR-based position sizing formula:

```
Position Size = (Risk% × Account Equity) / (ATR × ATR Multiplier)
```

## Value at Risk (VaR)

Three methods available:
- **Historical**: Based on historical return distribution
- **Parametric**: Assumes normal distribution
- **Monte Carlo**: Simulated paths with random walks

## Beta Hedging

Rolling 60-day beta vs benchmark:
- Equities: SPY
- Crypto: BTCUSDT
- Forex: EURUSD

## Kelly Criterion

Optimal position sizing from backtest statistics. Half-Kelly (50% fraction) is the default conservative approach.
