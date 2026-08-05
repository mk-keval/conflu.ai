# conflu.ai Documentation

Welcome to the conflu.ai documentation. conflu.ai is a professional multi-asset trading platform with vectorized screening, backtesting, and risk management.

## Quick Links

- [Getting Started](getting-started.md) â€” Set up your local development environment
- [API Reference](api/) â€” Auto-generated API documentation
- [Architecture](architecture.md) â€” System architecture and data flow
- [Developer Guide](dev-guide/contributing.md) â€” How to contribute
- [Changelog](changelog.md) â€” Release history
- [Professional Mode User Guide](professional-mode.md) — Guided workflow for working professionals
- [Validation Infrastructure](validation-infrastructure.md) â€” Statistical validation, walk-forward, Monte Carlo, stress testing, paper trading

## Key Features

- **Multi-Asset Screening** â€” Screen 5000+ symbols across equities, crypto, forex, commodities, and indices
- **Vectorized Backtesting** â€” Fast backtesting with vectorbt portfolio simulation
- **Risk Management** â€” ATR position sizing, VaR, beta hedging, Kelly optimization
- **Real-Time Streaming** â€” WebSocket-based price and indicator streaming
- **Sector Rotation** â€” Smart money flow tracking across 11 sector ETFs with 1D/1W relative strength, momentum, flow signals, and rotation phase detection
- **Market Regime Detection** â€” Real-time composite market regime analysis (VIX, risk appetite, sector breadth, safe haven demand, yield curve) with global header indicator
- **Elite Screener Pipeline** â€” 56 TV filters, 21 screen templates, adaptive regime-aware confluence scoring, post-TV signal enrichment (RS rating, institutional quality, signal conviction, Wyckoff phase, factor conflict detection)
- **Advanced Analytics** â€” Parameter optimization, regime detection, report generation
- **Validation Infrastructure** â€” Statistical validation, walk-forward OOS testing, Monte Carlo bootstrap, regime-aware validation, stress testing, paper trading simulation

## Recent Activity

| Date | Change |
|------|--------|
| 2026-08-04 | **Docker UI Fix + TickerTape Removal**: UI would not load — root cause was TickerTape header component (duplicate declarations broke esbuild; its `/data/prices` endpoint shadowed by `/data/{symbol}` catch-all; response_model mismatch → 500s; missing price → React crash). Decided to **remove the TickerTape entirely** (D-30) — it polled 24 individual Yahoo calls every 5s for a decorative strip. Also deleted orphaned batch-prices endpoint and guarded a missing Phase-6 `alert_engine` import in `ws/manager.py` that crashed shutdown/reload. Verified: dashboard + /pro render with 0 console errors, WebSocket Connected, regime/VIX/sectors/events load, OHLCV endpoint confirmed |
| 2026-07-31 | **TV Screener Verification & Doc Correction**: Live-verified `tradingview-screener` v3.2.0 capabilities (snapshot-only, no history; 15-min delay unauth / streaming w/ cookies; per-column `\|INTERVAL` multi-TF; no documented rate limit; retry is app-side). Corrected `.claude/skills/tvscreener-specialist/SKILL.md` (removed `OBV`/`supertrend*` which return `None`, valid interval codes + label mapping, accurate rate-limit table) and ADR-004 (retry not built-in, no historical data) |
| 2026-07-31 | **Glass Terminal — Typography, Brand & DX**: Body font IBM Plex Sans → **Manrope**, all page titles → Newsreader semibold + tight tracking; new **"Converging Flow" brand mark** (SVG glyph: signal streams converging into an upward verdict arrow, teal gradient) replacing the text "C" box + stale purple favicon; fixed Tailwind v3 `@layer` tree-shaking (glass/page-title/tape-item utilities now always emitted); Vite `usePolling` for Docker bind-mount HMR (no more restart-per-edit); Dashboard container widened `max-w-5xl` → `max-w-6xl` (killed ~80px dead space) |
| 2026-07-31 | **Glass Terminal — Design Token Foundation**: Transformed design tokens from generic dark-slate/green to "glass terminal" — deep ink `#05070D` background, frosted-glass surfaces (`white/[0.03]` + `backdrop-blur-xl`), teal/cyan brand accent (`#2DD4BF`, never green — green/red reserved for gain/loss), Newsreader editorial serif for display headlines, `surface-tertiary` token added (was referenced but undefined), `glow-teal` shadow, `tape-scroll` keyframes + `animate-tape-scroll`. Values-only change across `tailwind.config.ts`, `src/index.css`, `index.html` — no token/class names renamed, all existing components keep working |
| 2026-07-31 | **Glass Terminal Responsive Shell**: App shell redesigned as frosted-glass panels over deep ink with subtle teal/indigo ambient glows, teal active states, new mobile bottom-nav (MobileNav) with slide-up "More" drawer, TickerTape under the header, first responsive pass (sidebar now desktop-only, header condenses on mobile) |
| 2026-07-30 | **Full-App Bug Hunt**: Fixed 7 bugs across frontend+backend — (1) Morning Brief regime always said "STRONG TREND" (event-loop bug, now sync), (2) market internals education tooltips explained wrong metrics, (3) "S&P Fut"/"NAS Fut" showed ETF prices not index levels, (4) missing /pro Morning Brief nav, (5) Swing Desk leaders mixed momentum with 1D change, (6) WorkflowBar missing on /pro & /workflow, (7) pre-existing production build break (34 TS errors) — Docker image now builds |
| 2026-07-30 | **Sector Rotation UI Fixes**: RotationFlows tab now responds to 1D/1W toggle (was frozen on composite score), phase banner shows timeframe basis + actionable guidance, EducationPanel rewritten with plain-English explanations covering RS, volume, flow signals, 1D vs 1W usage, rotation phase strategy, and common mistakes |
| 2026-07-26 | **Professional Mode (Phase 8)**: 5 backend services (MorningBrief, RegimeSelector, PositionSizer, Education, Alert), 8 API endpoints, 4 frontend pages (/pro/*), 12 UI components, 30+ education metrics, email + in-app alerts, APScheduler integration, graduation path |
| 2026-07-24 | **Portfolio Page & WorkflowBar**: New Portfolio page with store management, WorkflowBar step indicator for guided workflow, Dashboard landing page with market context and top-down navigation, sector focus banner with "Best for today" regime badges |
| 2026-07-20 | **Ticker Analysis Elite Trader Upgrade**: Market structure analysis (swing detection, HH/HL/LH/LL, support/resistance zones), pullback quality scoring (A+ to F), multi-timeframe analysis (Daily/Weekly/4H/1H), volume profile (TPO) from daily bars, dynamic risk/reward (trend/volatility/fundamental adjusted), enhanced options flow (GEX flip, max pain, dealer positioning, unusual volume, term structure), catalyst bias analysis (earnings proximity, analyst targets, insider/short interest), dynamic trade plans (scale-in/out, ATR/structure trailing, breakeven rules, time stops), catalyst bias integration in synthesis, multi-timeframe technical tab, trade plan panel in verdict |
| 2026-07-16 | **Ticker Analysis Yahoo Finance Integration**: Added `/options` (chain, Greeks, max pain, GEX, IV Rank, PCR), `/news` (sentiment feed), `/chart` (5m/15m/1h/4h/1d intraday) endpoints + 3 new frontend tabs (Options, News, Chart redirect) + UX fixes (conviction tooltip, binary outcome N/A tooltips, market regime refresh, Explain toggle) |
| 2026-07-16 | **Screener dropdown pointer-events fix**: converted TemplateDropdown to portal-based fixed positioning (same pattern as ColumnCustomizer D-22) â€” dropdown items at any scroll position now clickable |
| 2026-07-14 | Screener dropdown pointer-events fix: converted TemplateDropdown to portal-based fixed positioning (same pattern as ColumnCustomizer D-22) â€” dropdown items at any scroll position now clickable |
| 2026-07-10 | Elite screener pipeline: 56 filters, 9 new screen templates, adaptive regime scoring, EliteSignalProcessor (RS Rating, Inst Quality, Signal Conviction, Wyckoff Phase) + frontend elite columns |
| 2026-07-09 | Sector rotation smart money tracker + market regime detection system + caching fixes + timeframe-aware volume metrics |
| 2026-07-07 | UI audit fixes: table visual improvements, column customizer, portal stacking, indicator cache backend |
| 2026-07-03 | Screener improvements: scoring calibration, short screens, filter descriptions, Learn tab |
| 2026-07-02 | Screener improvements: scoring calibration, short screens, filter descriptions, Learn tab |
| 2026-06-30 | Scoring calibration round 2 + short screen configs |

