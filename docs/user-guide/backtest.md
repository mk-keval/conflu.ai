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

## Reading Your Results

Every metric on the Backtest page has an inline tooltip (click the ⓘ icon) — the same
explanations live in-app under **Learn → Backtest Metrics**. The essentials:

| Metric | How to read it |
|---|---|
| Total Return | % gain over the tested period. Decompose into gross profit/loss before trusting it. |
| Profit Factor | Gross wins ÷ gross losses. <1 losing · 1.3–1.5 caution · 1.5–2 good · >2 suspect overfitting on small samples. |
| Sharpe Ratio | Return per unit of total risk. <0.5 weak · 1.0–2.0 good · >2 exceptional but verify. Penalizes upside volatility too — see Sortino. |
| Sortino Ratio | Like Sharpe but only penalizes *downside* volatility. Prefer it for directional swing strategies. |
| Calmar Ratio | Annualized return ÷ max drawdown — how much return each unit of worst pain bought. |
| Max Drawdown | Largest peak-to-trough decline. <15% robust, >25% psychologically brutal. **Worst so far ≠ worst possible.** |
| Win Rate | Meaningless alone — always read with average win/loss (R:R). 80% wins with 0.2:1 R:R still loses money. |
| Expectancy | (Win rate × avg win) − (loss rate × avg loss). Positive = edge. THE number that matters most. |
| SQN | System Quality Number — combines expectancy, dispersion, and trade count into one grade. |
| Ulcer Index | Depth × duration of declines — captures pain that max-drawdown misses. |

### Sample-size rule

Under ~100 trades, every statistic above is noise. A great backtest on 20 trades proves
nothing; prefer 200+ trades across trending AND ranging periods before trusting results.

### Overfitting warning signs

- Profit factor >2.5 on fewer than 100 trades
- Metrics that improve with *every* parameter tweak
- Results collapse when transaction costs rise slightly
- Performance only works in one narrow date range

Reserve a holdout period you never optimize against; validate once at the end.

These thresholds are also enforced visually in-app: metric cards color-code
against them, and each card's tooltip explains its own bands.
