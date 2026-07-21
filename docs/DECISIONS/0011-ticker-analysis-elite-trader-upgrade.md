# ADR-0011: Ticker Analysis Elite Trader Upgrade

**Status:** Accepted (Uncommitted)
**Date:** 2026-07-20

## Context

The ticker analysis engine provided a multi-module verdict (Technical, Fundamental, Earnings, Sentiment, Risk) with basic entry/stop/targets. Elite traders needed:

1. **Market structure analysis** — Swing detection, HH/HL/LH/LL patterns, key S/R zones
2. **Pullback quality scoring** — A+ to F rating with depth, volume dry-up, structure hold factors
3. **Multi-timeframe analysis** — Daily/Weekly/4H/1H structure context
4. **Volume profile (TPO)** — Institutional order flow approximation from daily bars
5. **Enhanced options flow** — GEX flip, max pain magnet, dealer positioning, unusual volume, term structure
6. **Catalyst bias overlay** — Earnings proximity, analyst targets, insider/short interest
7. **Dynamic trade plans** — Scale-in/out, ATR/structure trailing, breakeven rules, time stops, risk caps

## Decision

### Technical Module Enhancements

| Feature | Implementation |
|---------|---------------|
| Swing detection | 5-bar fractal pattern across highs/lows |
| Structure classification | HH/HL (uptrend), LH/LL (downtrend), ranging |
| Key levels | DBSCAN clustering of swing points into S/R zones |
| Pullback quality | Multi-factor scoring: depth (0-30pts), volume dry-up (0-30pts), time (0-20pts), RSI reset (0-10pts), structure hold (0-10pts) → A+/A/B/C/D/F |
| TPO volume profile | Daily bar pseudo-TPO: POC, VAH/VAL (70% value area), HVN/LVN |
| Multi-timeframe | Per-TF analysis with structure aggregation |

### Synthesis Engine Enhancements

| Feature | Implementation |
|---------|---------------|
| Catalyst bias | Earnings proximity/drift + analyst targets + insider/short interest → -10 to +10 bias score |
| Dynamic R:R | Base 1:2 → trend quality mulitplier (0.8-1.5) + volatility multiplier (0.7-1.3) + fundamental multiplier (0.8-1.2) |
| Trade plan | Scale-in (3 tranches at entry/retrace/extended), Scale-out (1R/0.7R/full target), Trail (ATR chandelier + structure), Breakeven at 1R, Time stops (counter-trend 20d, dev-stage 60d) |
| Risk caps | Position (<5%), Daily loss (<2%), Correlation check |

### API Router Enhancement

Enhanced options flow endpoint (`GET /ticker/{symbol}/options-flow`) computes:
- GEX by strike (gamma × OI × 100 × spot × 0.01)
- GEX total, flip level (strike > spot where cumulative GEX > 0)
- Max pain (OI-weighted pain minimization across all strikes)
- Unusual volume detection (volume > 2× OI & OI > 100)
- Term structure (IV across 6 nearest expiries)
- Dealer gamma positioning (long/short gamma determination)

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `backend/app/domain/ticker_analysis/technical.py` | +685/-80 | Market structure, pullback quality, TPO, multi-timeframe |
| `backend/app/domain/ticker_analysis/synthesis.py` | +211/-40 | Catalyst bias, dynamic R:R, trade plans |
| `backend/app/domain/ticker_analysis/orchestrator.py` | +156/-20 | Multi-timeframe orchestration, macro overlay |
| `backend/app/domain/ticker_analysis/models.py` | +44/-5 | New model fields |
| `backend/app/domain/ticker_analysis/__init__.py` | +40/-2 | Module exports |
| `backend/app/api/routers/ticker_analysis.py` | +276/-30 | Enhanced options flow endpoint |
| `frontend/src/components/ticker-analysis/TickerAnalysisPage.tsx` | +329/-90 | Multi-timeframe tab, trade plan panel |
| `frontend/src/types/tickerAnalysis.ts` | +69/-10 | New TypeScript types |
| `docs/ARCHITECTURE.md` | +98/-8 | Data flow diagrams |
| `docs/index.md` | +11/-0 | Recent activity |

**Total:** 14 files, ~1100 lines net added

## Risk Assessment

- **Core domain logic changed** (HIGH) — `technical.py`, `synthesis.py` are core business logic
- **API contract extended** (MEDIUM) — New response fields, no breaking changes
- **Tests** (LOW) — 407/407 passed
- **E2E** (LOW) — All 6 routes verified with Playwright, 0 console errors
- **LSP diagnostics** (LOW) — 0 errors, 3 warnings (pre-existing deprecations)

## Verification

| Check | Result |
|-------|--------|
| LSP diagnostics | ✅ 0 errors |
| Docker build (api) | ✅ Pass |
| Docker build (frontend) | ✅ Pass |
| Docker compose | ✅ All 3 services healthy |
| Backend tests | ✅ 407/407 passed |
| Playwright E2E | ✅ 6 routes, 0 console errors |

## Breaking Changes

**No breaking changes.** All additions are backward-compatible:
- New response fields are optional (null if not populated)
- Existing API contracts unchanged
- Frontend handles missing fields gracefully

**Decision ID:** ADR-0011
