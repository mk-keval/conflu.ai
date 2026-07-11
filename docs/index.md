# conflu.ai Documentation

Welcome to the conflu.ai documentation. conflu.ai is a professional multi-asset trading platform with vectorized screening, backtesting, and risk management.

## Quick Links

- [Getting Started](getting-started.md) — Set up your local development environment
- [API Reference](api/) — Auto-generated API documentation
- [Architecture](architecture.md) — System architecture and data flow
- [Developer Guide](dev-guide/contributing.md) — How to contribute
- [Changelog](changelog.md) — Release history

## Key Features

- **Multi-Asset Screening** — Screen 5000+ symbols across equities, crypto, forex, commodities, and indices
- **Vectorized Backtesting** — Fast backtesting with vectorbt portfolio simulation
- **Risk Management** — ATR position sizing, VaR, beta hedging, Kelly optimization
- **Real-Time Streaming** — WebSocket-based price and indicator streaming
- **Sector Rotation** — Smart money flow tracking across 11 sector ETFs with 1D/1W relative strength, momentum, flow signals, and rotation phase detection
- **Market Regime Detection** — Real-time composite market regime analysis (VIX, risk appetite, sector breadth, safe haven demand, yield curve) with global header indicator
- **Elite Screener Pipeline** — 56 TV filters, 21 screen templates, adaptive regime-aware confluence scoring, post-TV signal enrichment (RS rating, institutional quality, signal conviction, Wyckoff phase, factor conflict detection)
- **Advanced Analytics** — Parameter optimization, regime detection, report generation

## Recent Activity

| Date | Change |
|------|--------|
| 2026-07-10 | Fund instrument detection framework: REIT, BDC, MLP, preferred, mining royalty, deSPAC, biotech milestone, crypto miner, expert market, >$100M pre-profit + 11 synthetic tests + squeeze override guard + risk caps — 404/404 tests pass |
| 2026-07-09 | Elite screener pipeline: 56 filters, 9 new screen templates, adaptive regime scoring, EliteSignalProcessor (RS Rating, Inst Quality, Signal Conviction, Wyckoff Phase) + frontend elite columns |
| 2026-07-09 | **Ticker Analysis Engine**: `POST /api/v1/ticker/{symbol}/analyze` — 5-module analysis (technical, fundamental, earnings, sentiment, risk) with regime-weighted synthesis → verdict (BUY/SELL/HOLD/WATCH) + entry/stop/targets/triggers/thesis + frontend page at `/ticker/:symbol` |
| 2026-07-07 | Sector rotation smart money tracker + market regime detection system + caching fixes + timeframe-aware volume metrics |
| 2026-07-03 | UI audit fixes: table visual improvements, column customizer, portal stacking, indicator cache backend |
| 2026-07-02 | Screener improvements: scoring calibration, short screens, filter descriptions, Learn tab |
| 2026-06-30 | Scoring calibration round 2 + short screen configs |
