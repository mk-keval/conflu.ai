# conflu.ai Documentation

Welcome to the conflu.ai documentation. conflu.ai is a professional multi-asset trading platform with vectorized screening, backtesting, and risk management.

## Quick Links

- [Getting Started](getting-started.md) — Set up your local development environment
- [API Reference](api/) — Auto-generated API documentation
- [Architecture](architecture.md) — System architecture and data flow
- [Developer Guide](dev-guide/contributing.md) — How to contribute
- [Changelog](changelog.md) — Release history
- [Validation Infrastructure](validation-infrastructure.md) — Statistical validation, walk-forward, Monte Carlo, stress testing, paper trading

## Key Features

- **Multi-Asset Screening** — Screen 5000+ symbols across equities, crypto, forex, commodities, and indices
- **Vectorized Backtesting** — Fast backtesting with vectorbt portfolio simulation
- **Risk Management** — ATR position sizing, VaR, beta hedging, Kelly optimization
- **Real-Time Streaming** — WebSocket-based price and indicator streaming
- **Sector Rotation** — Smart money flow tracking across 11 sector ETFs with 1D/1W relative strength, momentum, flow signals, and rotation phase detection
- **Market Regime Detection** — Real-time composite market regime analysis (VIX, risk appetite, sector breadth, safe haven demand, yield curve) with global header indicator
- **Elite Screener Pipeline** — 56 TV filters, 21 screen templates, adaptive regime-aware confluence scoring, post-TV signal enrichment (RS rating, institutional quality, signal conviction, Wyckoff phase, factor conflict detection)
- **Advanced Analytics** — Parameter optimization, regime detection, report generation
- **Validation Infrastructure** — Statistical validation, walk-forward OOS testing, Monte Carlo bootstrap, regime-aware validation, stress testing, paper trading simulation

## Recent Activity

| Date | Change |
|------|--------|
| 2026-07-20 | **Ticker Analysis Elite Trader Upgrade**: Market structure analysis (swing detection, HH/HL/LH/LL, support/resistance zones), pullback quality scoring (A+ to F), multi-timeframe analysis (Daily/Weekly/4H/1H), volume profile (TPO) from daily bars, dynamic risk/reward (trend/volatility/fundamental adjusted), enhanced options flow (GEX flip, max pain, dealer positioning, unusual volume, term structure), catalyst bias analysis (earnings proximity, analyst targets, insider/short interest), dynamic trade plans (scale-in/out, ATR/structure trailing, breakeven rules, time stops), catalyst bias integration in synthesis, multi-timeframe technical tab, trade plan panel in verdict |
| 2026-07-16 | **Ticker Analysis Yahoo Finance Integration**: Added `/options` (chain, Greeks, max pain, GEX, IV Rank, PCR), `/news` (sentiment feed), `/chart` (5m/15m/1h/4h/1d intraday) endpoints + 3 new frontend tabs (Options, News, Chart redirect) + UX fixes (conviction tooltip, binary outcome N/A tooltips, market regime refresh, Explain toggle) |
| 2026-07-16 | **Screener dropdown pointer-events fix**: converted TemplateDropdown to portal-based fixed positioning (same pattern as ColumnCustomizer D-22) — dropdown items at any scroll position now clickable |
| 2026-07-14 | Screener dropdown pointer-events fix: converted TemplateDropdown to portal-based fixed positioning (same pattern as ColumnCustomizer D-22) — dropdown items at any scroll position now clickable |
| 2026-07-10 | Elite screener pipeline: 56 filters, 9 new screen templates, adaptive regime scoring, EliteSignalProcessor (RS Rating, Inst Quality, Signal Conviction, Wyckoff Phase) + frontend elite columns |
| 2026-07-09 | Sector rotation smart money tracker + market regime detection system + caching fixes + timeframe-aware volume metrics |
| 2026-07-07 | UI audit fixes: table visual improvements, column customizer, portal stacking, indicator cache backend |
| 2026-07-03 | Screener improvements: scoring calibration, short screens, filter descriptions, Learn tab |
| 2026-07-02 | Screener improvements: scoring calibration, short screens, filter descriptions, Learn tab |
| 2026-06-30 | Scoring calibration round 2 + short screen configs |
