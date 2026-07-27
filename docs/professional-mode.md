# Professional Mode User Guide

## What is Professional Mode?

Professional Mode is a workflow layer for working professionals (9-5 job, zero market knowledge) that translates institutional-grade analysis into actionable daily trades. Think of it as a **co-pilot** — it tells you what to trade, why, how much, and when to exit — without requiring you to understand the underlying technical analysis.

## Getting Started

1. **Enable Professional Mode**: Click the toggle in the header (Guided ↔ Explorer) or go to `/pro/settings`
2. **Set your account size**: Enter your total portfolio value in Settings — this enables automatic position sizing
3. **Choose risk tolerance**: Conservative (1% risk/trade), Moderate (1.5%), or Aggressive (2%)
4. **Read your Morning Brief**: Visit `/pro` each morning after 6 AM ET for your daily snapshot
5. **Review top picks**: Each ticker shows a verdict, entry/stop/target, and position size
6. **Analyze a ticker**: Click "Analyze" to see the full simplified verdict with education tooltips
7. **Build your watchlist**: Add tickers to track, batch-analyze them, and set alerts

## Key Features

### Morning Brief (`/pro`)
Your daily 5-minute market briefing:
- **Regime badge**: Current market personality (Strong Trend, Ranging, High Volatility)
- **Market internals**: VIX (fear gauge), Advance/Decline ratio, Dollar Index, S&P 500 and Nasdaq futures
- **Sector rotation heatmap**: Which sectors are leading/lagging (click any sector for details)
- **Top 9 picks**: 3 regime-matched screens × 3 best tickers each, with live pre-market prices
- **Education tooltips**: Hover `?` on any metric for plain-English explanation

### One-Click Verdict (`/pro/ticker/{symbol}`)
Simplified ticker analysis:
- **Verdict**: STRONG BUY / BUY / WATCH / AVOID
- **Conviction score**: 1-10 confidence measure
- **Key metrics**: Score breakdown with expandable sections (hover `?` for explanations)
- **Position size**: Automatic calculation based on your account size and risk tolerance
- **Entry zone**: Suggested price range to enter
- **Stop loss**: Emergency exit price
- **Targets**: Profit-taking price levels (1R, 2R)

### Watchlist Builder (`/pro/watchlist`)
Build and manage your watchlist:
- **Search**: Find tickers by symbol
- **Batch analyze**: Get verdicts for all watchlist tickers at once
- **Position preview**: See position sizes without leaving the page
- **One-click add to portfolio**: Paper trade to the Portfolio page

### Settings (`/pro/settings`)
Configure your Professional Mode experience:
- **Account size**: Your total portfolio value (used for position sizing)
- **Risk tolerance**: Conservative / Moderate / Aggressive
- **Alert preferences**: Toggle email and in-app notifications per alert type
- **Feature progress**: See which features are unlocked and when more unlock

### Education Tools
Learn as you trade:
- **EducationTooltip**: Hover `?` on any metric for instant plain-English explanation
- **ConceptExplainer**: Inline cards explain broader concepts (sector rotation, risk-on/off, conviction scores)
- **ConceptExplorer**: Full reference browser with search — browse all metrics by category, explore modules, look up glossary terms

### Graduation Path
Features unlock gradually over 90 days to prevent overwhelm:

| Day | Features Unlocked |
|-----|-------------------|
| 1 | Morning Brief, One-Click Verdict, Watchlist Builder |
| 14 | Screen Selector (see all 21 screens) |
| 30 | Deep Analysis (all 8 tabs) |
| 60 | Backtest Engine, Portfolio Analytics |
| 90 | Charts (full) |

## FAQ

### How do I learn what P/E means?
Hover the `?` icon next to any metric — a tooltip explains it in plain English. Click "Explain more" for AI-enhanced context. Or open the Concept Explorer from the education panel to browse all metrics.

### What happens if I don't check the brief?
The brief is available all day at `/pro`. Stop/target alerts fire in real-time via in-app notifications. The morning brief email arrives at 6 AM ET regardless.

### Can I go back to Explorer mode?
Yes — toggle "Professional Mode" OFF in the header or `/pro/settings`. All existing features (Screener, Ticker Analysis, Portfolio, Charts) remain unchanged.

### How is position size calculated?
Using the Kelly Criterion formula from CONTEXT.md:
```
risk_dollars = account × risk_per_trade_pct × conviction_multiplier
shares = risk_dollars / |entry - stop_loss|
```
Capped at 5% of account per position and 15% per sector.

### Can I use this for crypto / forex?
Yes — Professional Mode works cross-asset. The regime selector, screens, and position sizer support equities, crypto, forex, and commodities.

### Does Professional Mode cost extra?
No — it's part of the existing app. LLM-enhanced education explanations may incur API costs if enabled (disabled by default in dev).

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Morning Brief shows "No data" | The brief generates at 6 AM ET. If before 6 AM, check back later. |
| Position size is $0 | Set your account size in Settings. Minimum position is $500. |
| Feature is locked | See Graduation Path above. Features unlock on schedule based on your start date. |
| Education tooltip says "No explanation" | The metric may not have a template yet. Use the Concept Explorer to browse available metrics. |
| Schedule jobs not running | Ensure `professional.morning_brief_enabled=True` in config and APScheduler is installed. |

## What's Next (Future Phases)
- **Paper trading integration** (v1.1) — execute trades from the verdict page
- **Behavioral coach** (v1.2) — journaling, bias detection, trade review
- **Mobile app / PWA** (v2.0) — morning brief on the go
- **Brokerage integration** (v2.0) — real trade execution
