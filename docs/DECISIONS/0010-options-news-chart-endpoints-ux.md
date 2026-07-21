# ADR-0010: Options Chain, News Feed, Chart Data Endpoints + UX Improvements

**Status:** Accepted  
**Date:** 2026-07-16  

## Context

The Ticker Analysis page (`/ticker/:symbol`) provided a multi-module verdict (Technical, Fundamental, Earnings, Sentiment, Risk) with actionable entry/stop/targets. However, traders needed:

1. **Options signals** — IV Rank, GEX, Max Pain, PCR to inform premium selling/buying decisions
2. **News catalysts** — Real-time headlines with sentiment to identify earnings beats, upgrades, trials
3. **Intraday charts** — 5m/15m/1h/4h/1D OHLCV for precise entry/exit timing
4. **Better UX** — Conviction tooltip, binary outcome N/A handling, market regime refresh

Previously, users had to leave the platform for options data (Thinkorswim, CBOE), news (Benzinga, Seeking Alpha), and charts (TradingView).

## Decision

Add three Yahoo Finance endpoints to `/api/v1/ticker/{symbol}/` and integrate into TickerAnalysisPage:

### 1. Options Chain (`GET /api/v1/ticker/{symbol}/options`)
- Calls/puts with strike, bid, ask, IV, volume, OI, Greeks (when available)
- Computed: IV Rank (placeholder), Max Pain, Gamma Exposure (GEX), Put/Call Ratio
- Expiry selector with all available expiries
- 5-min TTL cache

### 2. News Feed (`GET /api/v1/ticker/{symbol}/news`)
- Headlines, publisher, timestamp, link
- Simple keyword sentiment: positive/negative/neutral
- 5-min TTL cache

### 3. Intraday Chart Data (`GET /api/v1/ticker/{symbol}/chart`)
- OHLCV for 5m, 15m, 1h, 4h, 1D intervals
- Auto-range limiting (Yahoo limits: 5m/15m → 7d, 1h → 60d, 4h → 730d)
- Output format for Lightweight Charts (time, open, high, low, close, volume)
- 5-min TTL cache

### Frontend Integration
- **Options Tab** — Overview cards + sortable calls/puts tables (by OI) + expiry pills
- **News Tab** — Sentiment-coded headlines (green/red/gray) with external links
- **View Chart Button** — Redirects to `/charts?symbol={SYMBOL}&timeframe=1D`
- **Conviction Ring Tooltip** — "1-10 scale: ≥7 High, 4-6 Moderate, ≤3 Low"
- **Binary Outcome N/A** — ATAI shows "N/A" with tooltips: "Binary outcome stock — no technical entry zones. Position on catalyst confirmation."
- **Market Regime Refresh** — Manual refresh button (🔄) with loading spinner + "Updated X:XX PM" timestamp

### Technical Fixes
- NaN handling in options processing (`pd.notna()` for volume, OI, bid, ask, IV, Greeks)
- Try/catch around `option_chain()` with graceful error response
- JSX escaping for `<`/`>` in explanation text (string variable)
- Added missing imports: `Search`, `Loader2`, `ExternalLink`, `BarChart2`, `MagnifyingGlass`

## Consequences

### Benefits
- **All-in-one decision support** — Options flow, news catalysts, intraday charts in one tab
- **Free data source** — Yahoo Finance (no paid API keys needed)
- **Progressive disclosure** — Explain toggle + metric tooltips for learning traders
- **Binary-outcome aware** — Honest N/A with education, not fake levels
- **Regime awareness** — Manual refresh prevents stale 6-hour cached regime

### Trade-offs
- **Yahoo rate limits** — 5-min cache prevents abuse; heavy users may hit limits
- **No Greeks for all strikes** — Yahoo omits delta/gamma/theta/vega for many contracts
- **IV Rank placeholder** — True IV Rank needs historical IV data (future: store daily IV snapshots)
- **News quality** — Yahoo headlines often empty for small caps; sentiment is keyword-only

### Mitigations
- 5-min TTL cache on all endpoints
- Graceful error handling (shows "No data" cards, not crashes)
- "View Chart" redirects to existing charts page (no duplicate chart logic)

## Implementation

### Backend (`backend/app/api/routers/ticker_analysis.py`)
```python
# Added endpoints:
GET /api/v1/ticker/{symbol}/options?expiry=YYYY-MM-DD
GET /api/v1/ticker/{symbol}/news?limit=20
GET /api/v1/ticker/{symbol}/chart?interval=5m&range=5d
```

### Frontend
- `frontend/src/api/tickerAnalysis.ts` — Added `fetchOptionsChain`, `fetchNews`, `fetchChartData` + types
- `frontend/src/types/tickerAnalysis.ts` — Added `OptionsChainResponse`, `NewsResponse`, `ChartDataResponse`
- `frontend/src/components/ticker-analysis/TickerAnalysisPage.tsx` — Options/News tabs, View Chart button, Explain toggle, Conviction tooltip, binary outcome N/A

### Regime Badge (`frontend/src/components/layout/RegimeBar.tsx`)
- Added refresh button with spinner + timestamp display
- Added `data_fetched_at` to `MarketRegimeResponse` type

### Market Regime Backend (`backend/app/api/routers/regime.py`)
- Added `data_fetched_at` field (actual macro data fetch timestamp)
- Returns `data_fetched_at` alongside `timestamp` (request time)

## Verification

### Tested Tickers
| Ticker | Type | Options | News | Chart |
|--------|------|---------|------|-------|
| ATAI | Clinical biotech (binary) | ✅ (7 expiries) | ✅ (empty titles) | ✅ |
| HOMB | Financial services | ✅ (4 expiries) | ✅ (empty titles) | ✅ |

### End-to-End Flows
1. ATAI → Verdict shows "N/A" for Entry/Stop/Targets → Tooltips explain binary outcome
2. HOMB → Full Options tab with calls/puts tables, Max Pain $22.50, GEX 0
3. View Chart → Redirects to `/charts?symbol=HOMB&timeframe=1D`
4. Explain On/Off → Toggles metric tooltips, verdict walkthrough, glossary
5. Market Regime badge → Click 🔄 → Spinner → Fresh data + timestamp
6. All tabs navigable: Verdict → Technical → Fundamental → Earnings → Sentiment → Risk → Options → News

### Console Errors
- **0 errors** on all pages tested (ATAI, HOMB, charts page)

## Rollback Plan
If issues arise:
1. Disable endpoints in `ticker_analysis.py` router
2. Remove Options/News tabs from `TickerAnalysisPage.tsx`
3. Revert `RegimeBar.tsx` to previous version

## Success Metrics
- All 3 endpoints return 200 with valid JSON
- Options tab renders without NaN crashes (HOMB fixed)
- View Chart redirects correctly
- No console errors on ATAI/HOMB ticker pages
- Market regime refresh updates timestamp