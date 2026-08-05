# D-26: Trading Workflow Redesign — Dashboard, WorkflowBar & Sector Focus

**Status:** Accepted
**Date:** 2026-07-23

## Context

The app launched directly into the screener with no onboarding or market context. Users had no sense of workflow progression (Market → Screen → Analyze → Portfolio) and no quick way to see what the market was doing before diving into screens.

## Decision

Implement a top-down institutional trading workflow with four components:

### 1. Dashboard Landing Page (`/dashboard`)
- Replaces `/screener` as the default landing (`/` redirects to `/dashboard`)
- Shows regime score, VIX level, sector leaders/laggards, strategy hint
- Upcoming economic events (FOMC, CPI, PCE) with countdown timers from `GET /api/v1/market/events`
- Auto-generated market summary from `GET /api/v1/market/narrative`
- Quick-action buttons guiding users into the workflow: Screen → Analyze → Portfolio

### 2. WorkflowBar Step Indicator
- Persistent horizontal bar showing 4 steps: Market → Screen → Analyze → Portfolio
- Current step highlighted in accent, completed steps in green with checkmark
- Clickable navigation for completed/current steps; future steps disabled
- Only appears on workflow-relevant pages (dashboard, screener, ticker, portfolio)

### 3. Sector Focus Banner (Screener)
- Fetches sector rotation data, sorts by 1d change, shows top 4 sectors
- Displays each sector with daily change %, clickable to filter screener results
- Shows current rotation phase label
- Replaces generic "✅" badge with "Best for today" text on recommended templates

### 4. Backend Market Endpoints
- `GET /api/v1/market/events` — Upcoming FOMC, CPI, PCE with countdown
- `GET /api/v1/market/narrative` — Auto-generated market summary (reuses existing regime/sector data)

## Consequences

- **Positive:** Clear institutional workflow — users start with market context, not raw screens
- **Positive:** Sector focus banner reduces noise — click to filter, not scroll
- **Positive:** All existing pages preserved untouched; additive change only
- **Trade-off:** Dashboard adds ~300 lines of frontend, increases initial bundle
- **Risk:** Market events endpoint requires manual maintenance of event calendar