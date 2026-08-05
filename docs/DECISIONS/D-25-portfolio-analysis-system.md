# D-25: Portfolio Analysis System

**Status:** Accepted
**Date:** 2026-07-23

## Context

The trading workflow was missing a portfolio-level view. Users could screen tickers and analyze individual symbols but had no way to track a watchlist, assess cross-ticker correlation, or get portfolio-level risk metrics (beta, volatility, position sizing).

## Decision

Build a lightweight portfolio system with three layers:

### 1. Persistent Store (Frontend)
- Zustand store with `persist` middleware (localStorage) — no backend auth needed
- Stores symbol list with timestamps
- Actions: `addSymbol`, `removeSymbol`, `hasSymbol`, `clearAll`
- "Add to Portfolio" button on Ticker Analysis page

### 2. Backend Analysis Endpoint
- `POST /api/v1/portfolio/analyze` — accepts symbol list, returns:
  - Per-symbol analysis summaries (sector, price, conviction, action)
  - Correlation matrix (`correlation_matrix`, `high_correlation_pairs`)
  - Portfolio-level metrics: `combined_beta`, `portfolio_volatility`, `equal_risk_pct`
  - Sector allocation breakdown
- Reuses existing ticker analysis engine and beta endpoint

### 3. Portfolio Page (Frontend)
- Grid of ticker cards with sector, price, beta per symbol
- "Analyze Portfolio" button triggers backend call
- Summary metrics panel: Combined Beta, Portfolio Vol, Per-Position Size, Top Sector
- High correlation warnings (red alert for r > 0.7 pairs)
- Correlation matrix table
- Quick links to full ticker analysis per symbol
- Empty state with navigation to Dashboard / Screener

## Consequences

- **Positive:** Zero-config portfolio tracking (no auth, no database)
- **Positive:** Portfolio survives page reloads and sessions (localStorage persist)
- **Trade-off:** Limited to client-side storage — no cross-device sync
- **Risk:** Large portfolios (>20 symbols) may hit API latency; frontend requires ≥2 symbols to analyze