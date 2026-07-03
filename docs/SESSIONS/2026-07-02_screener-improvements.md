# Session: Screener Improvements — Scoring Smoothing, Rationale, Sector, UI Fixes

**Started:** 2026-07-02
**Branch:** `screener-improvements`

## Prompt
Comprehensive analysis of the TV Screener product from an elite trader's perspective. Fix bugs, smooth scoring thresholds, add educational features — all without external dependencies or historical data (TV Screener only).

## Actions Taken

### Bug Fixes
1. **DetailPanel dead factors** — Replaced `volatility`/`pattern` (always 0) with correct `quality`/`fundamental` keys in BREAKDOWN_FACTORS
2. **DetailPanel rating mapping** — Scorer returns A+/A/B+/B/C/D but panel checked for Strong Buy/Buy/Hold. Fixed color mapping so A+/A → green, B+/B → neutral, C/D → red

### Scoring Refinements (confluence_scorer.py)
3. **ADX 20-25 transition zone** — Changed from 4→6 pts to catch early trend formation (the "ADX dead zone") before the crowd piles in at 25+
4. **RSI 54-55 bridge** — Added intermediate 6-point bracket between 53 (5) and 55 (7) to smooth the RSI momentum cliff
5. **rel_vol 1.35 smoothing** — Changed from 4→5 pts so the 1.35→1.5 transition is 20% instead of 50%

### "Why This Score" Rationale
6. **generate_rationale() method** — Added to TVConfluenceScorer, returns per-factor human-readable explanations (e.g., "Strong trend alignment — price well above EMAs with bullish stacking")
7. **API response** — Added `rationale` field to ConfluenceScore dataclass, ScoredTickerResponse, and _build_scored_response router helper
8. **Frontend display** — DetailPanel shows "Why This Score" collapsible section with bullet-point rationale

### UI Improvements
9. **Confluence tooltips** — Hovering over `T30·M25·V20·Q15·F10` in ScreenerTable now shows a tooltip explaining each factor
10. **Sector column** — Added `Sector` column to ScreenerTable (reads from TV `sector` field), added `sector` to TV specialist column selection
11. **Template descriptions** — Added `title` tooltip on <option> elements in both ScreenerPage inline selector and ScreenSelector component, showing YAML description on hover

### New Screen Templates
12. **52-Week Breakout** (`config/screens/52week-breakout.yaml`) — Stocks near 52-week highs with EMA200 trend, MACD bullish, volume confirmation
13. **Low-Vol Setup** (`config/screens/low-vol-setup.yaml`) — Low volatility stocks with steady trend, BB squeeze, and moderate volume

### Signal Freshness Badge
14. **Backend `fetched_at`** — Added ISO timestamp to `TVScreenResponse` model, populated at response time
15. **Frontend `FreshnessBadge`** — Auto-updating component in header showing "just now" / "Xs ago" / "Xm ago" with color-coded dot (green=seconds, yellow=minutes, red=hours)

### Multi-Template Convergence Badge
16. **Convergence tracking** — ScreenerPage tracks last 5 template runs (template name + ticker set), builds a `Map<ticker, count>` showing how many different templates matched each symbol
17. **TableCell badge** — `CellSymbol` shows a `2x` / `3x` etc. badge when a ticker appears in multiple templates

### Customizable Columns (TradingView-Style)
18. **Column metadata system** — `ALL_COLUMNS_META` defines 14 columns with weights, labels, and `alwaysOn` flag. `buildColumns()` normalises widths so hidden columns' space redistributes proportionally
19. **New column types**: Mkt Cap (market_cap_basic), P/E (price_earnings_ttm), Div % (dividends_yield_current), Rel Vol (standalone relative_volume_10d_calc)
20. **ColumnCustomizer dropdown** — "Columns" button in header opens a dropdown with checkboxes for all toggleable columns
21. **localStorage persistence** — Column preferences saved across sessions under `screener:visible-columns`
22. **TV specialist** — Added `price_earnings_ttm` and `dividends_yield_current` to TV query select columns

## Files Modified (10 + 3 new)
- `backend/app/infrastructure/screener/confluence_scorer.py`
- `backend/app/infrastructure/screener/tv_models.py`
- `backend/app/infrastructure/screener/tv_specialist.py`
- `backend/app/api/routers/tv_screener.py`
- `frontend/src/components/screener/DetailPanel.tsx`
- `frontend/src/components/screener/ScreenerTable.tsx`
- `frontend/src/components/screener/ScreenerPage.tsx`
- `frontend/src/components/screener/ScreenSelector.tsx`
- `frontend/src/lib/constants.ts`
- `frontend/src/types/screener.ts`

## Files Created (2)
- `config/screens/52week-breakout.yaml`
- `config/screens/low-vol-setup.yaml`

## Verification
- TypeScript: `tsc --noEmit` → clean (no errors)
- Python: `py_compile` all changed files → OK
- Branch: `screener-improvements` (forked from `main`)

## Deferred Items
- Historical backtesting / signal trust — deferred to separate conversation
- Signal freshness badge (TV data is always live, low value)
- Multi-template convergence badge (requires cross-template state management)

## Next Steps
- Push branch for review
- Discuss backtesting/historical trust architecture
