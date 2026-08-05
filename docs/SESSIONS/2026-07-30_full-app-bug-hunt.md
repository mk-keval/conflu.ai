# Session: Full-App Bug Hunt — Guided Mode & Education Fixes

**Date**: 2026-07-30
**Branch**: fix/elite-trader-gaps

## Context
User asked for a full-app analysis with focus on: (1) bugs like the RotationFlows timeframe issue, (2) whether education content is enough for non-market people, (3) missing /pro navigation. Full Playwright walkthrough of all pages performed.

## Bugs Found & Fixed

### 🔴 HIGH: Morning Brief regime detection broken — always "strong_trend"
**Files**: `backend/app/api/routers/regime.py`, `frontend/src/components/professional/MorningBriefPage.tsx`

- `get_market_regime_sync()` used `loop.run_until_complete()` on a **running** async loop → `RuntimeError` → swallowed → fell back to `_DEFAULT_REGIME = "strong_trend"`
- Result: Morning Brief always showed "STRONG TREND" while header showed "49 Cautious" — direct contradiction, and regime-based screen selection always picked trend screens
- **Fix**: Extracted pure-sync `compute_market_regime_sync()` — both the async route and sync wrapper now call the same sync core. No event-loop gymnastics.
- Added raw regime labels (Exuberance/Risk-On/Neutral/Cautious/Risk-Off/Crisis) to frontend `REGIME_COLORS`
- **Verified**: Morning Brief now returns `Cautious` / "Elevated uncertainty. Tighten stops..."

### 🔴 HIGH: Market internals education tooltips explained the WRONG metric
**Files**: `frontend/src/components/professional/MarketInternalsStrip.tsx`, `MorningBriefPage.tsx`, `EducationTooltip.tsx`

- VIX used `educationKey="rsi"`, A/D used `volume_ratio`, $USD used `beta`, S&P/Nasdaq used `market_cap` — all wrong
- Morning Brief regime badge used `rsi`, Sector Rotation header used `market_cap`
- **Fix**: Added proper static explanations for `vix`, `advance_decline_ratio`, `dollar_index`, `sp500_futures`, `nasdaq_futures`, `market_regime`, `sector_rotation`, `change_1w`. Re-wired all keys.

### 🟠 MEDIUM: "S&P Fut 741.7" / "NAS Fut 683.5" were SPY/QQQ ETF prices, not indices
**Files**: `backend/app/infrastructure/professional/morning_brief.py`, `MarketInternalsStrip.tsx`

- Backend fetched `SPY` (~$743) and `QQQ` (~$683) but labeled them "S&P Fut"/"NAS Fut"
- **Fix**: Now fetches `^GSPC` and `^IXIC` — shows real index levels (7437.63 / 25122.18). Labels renamed to "S&P 500"/"Nasdaq"

### 🟠 MEDIUM: No navigation to /pro (Morning Brief)
**Files**: `frontend/src/components/layout/Sidebar.tsx`, `WorkflowBar.tsx`

- Sidebar had no link to /pro — once you left, no way back except URL
- **Fix**: Added "Guided Mode" section with Morning Brief (/pro) + Watchlist (/pro/watchlist) links when pro mode enabled

### 🟠 MEDIUM: Swing Desk leaders/laggards mixed momentum with 1D change
**Files**: `frontend/src/components/workflow/WorkflowPage.tsx`

- Used API `leaders`/`laggards` (momentum-based, 1W-heavy) but displayed `change_1d` → "Leading: Health Care -1.6%" was confusing
- **Fix**: Sort by `change_1d` client-side so the metric shown matches the label

### 🟡 LOW: WorkflowBar not shown on /pro or /workflow
**Files**: `frontend/src/components/layout/WorkflowBar.tsx`

- STEPS hardcoded to `/dashboard`; /pro and /workflow showed no step bar
- **Fix**: Market step now points to `/pro` in Guided mode, `/dashboard` otherwise; `/pro/ticker/:symbol` maps to Analyze step

### 🔴 HIGH (pre-existing): Production build completely broken
**Files**: 7 files — `api/market.ts`, `DashboardPage.tsx`, `PortfolioPage.tsx`, `ScreenerPage.tsx`, `TickerAnalysisPage.tsx`, `WorkflowPage.tsx`, `api/workflow.ts`

- 34 TS errors: unused imports + real type mismatch (`SymbolAllocation.beta` missing in frontend type but present in backend)
- `docker compose build frontend` failed — no production image could be built
- **Fix**: Removed all unused imports, added `beta` to `SymbolAllocation` interface, removed dead code (SectorPill, step state)
- **Verified**: `tsc --noEmit` exit 0, Docker image builds

## Education Content Assessment
- **Sector Rotation** Learn tab: rewritten earlier today (plain English, actionable)
- **Screener** Learn tab: good — template-specific, plain English, usage guidance
- **Ticker Analysis** education.ts: excellent — metric lessons with plain-English analogies
- **Pro mode** EducationTooltips: fixed all wrong keys; static fallbacks now cover internals/regime
- **Dashboard**: readable, non-jargon
- Gap: WorkflowBar "Analyze" step on /pro/ticker/:symbol could confuse — mitigated by mapping to Analyze step
