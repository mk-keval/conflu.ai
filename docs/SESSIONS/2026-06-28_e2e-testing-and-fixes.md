# Session Log: 2026-06-28 — E2E Testing & Bug Fixes

## Started
2026-06-28 11:00 EDT

## User Prompt
Collapsed from multiple messages: Test all UI pages and all screeners end-to-end with Playwright. Fix broken template loading. Ensure all 7 screen templates work.

## Git State
- **Branch:** main (feat/sync-accumulated-changes merged)
- **Status:** Commits pushed, working tree clean before session

## Test Health Snapshot (Before)
- Screener page loads with Breakout (1,899 matches), but other 6 templates return 404
- WebSocket: `ws://api:8000/ws` fails (Docker hostname not resolvable from browser)
- Charts page: lightweight-charts assertion crash (unsorted data)

## Issues Found & Fixed

### 1. Template Name-to-Filename Mismatch (CRITICAL)
- **Root cause:** `load_screen_template(name)` constructs filename `f"{name}.yaml"` but YAML files use hyphenated filenames (e.g. `trend-follower.yaml`) while the YAML `name` field uses display names with spaces (e.g. `"Trend Follower"`)
- **Files affected:** `backend/app/api/routers/tv_screener.py`, `backend/app/infrastructure/screener/configs.py`
- **Fix added:** In `_resolve_config()`, when `load_screen_template(config)` raises `FileNotFoundError`, fall back to globbing all `*.yaml` files in the screens directory and matching by `cfg.name` field
- **Result:** All 7 templates now load correctly

### 2. WebSocket Docker Hostname (MEDIUM)
- **Root cause:** `docker-compose.override.yml` set `VITE_WS_URL=ws://api:8000/ws`, which uses the Docker internal hostname `api` that browsers cannot resolve
- **Fix:** Removed the `VITE_WS_URL` env var from the override file
- **Result:** WebSocket now connects to `ws://localhost:5173/ws/stream` via Vite proxy (the correct dev default)

### 3. SortIcon `key` Prop Warning (LOW)
- **Root cause:** `ScreenerTable.tsx` used React reserved `key` as a component prop name
- **Fix:** Renamed prop `key` → `colKey`
- **Result:** Console warning eliminated

## E2E Test Results (Playwright)

### ✅ Screener Page
- **Initial load:** 0 errors, 3 warnings (React Router future flags - benign)
- **Template dropdown:** All 7 templates listed; switching triggers correct API call
- **Template loading (all 7):**
  - Breakout: ✅
  - Mean Reversion: ✅ (108 matches, 263ms)
  - Momentum Breakout: ✅
  - Oversold Bounce: ✅
  - Trend Follower Mtf: ✅
  - Trend Follower: ✅ (593 matches, 314ms)
  - Volume Surge: ✅ (1,741 matches, 394ms)
- **Run Screen button:** ✅ Triggers fresh API call
- **Sorting (column headers):** SortIcon renders correctly per column
- **Pagination:** ✅ Page 2 shows "Showing 26 to 50 of 108 results" with different symbols
- **Detail panel:** ✅ Dialog opens with symbol name (BSX), close button works
- **Export buttons (CSV/JSON):** ✅ Rendered

### ✅ Backtest Page
- **Heading:** "Run Backtest"
- **Console errors:** 0

### ✅ Risk Page
- **Heading:** "Position Sizing"
- **Console errors:** 0

### ❌ Charts Page (Known Issues)
- **API errors:** 500 Internal Server Error for `/api/v1/data/indicators/AAPL` endpoints (macd, rsi, ema_20, bb)
- **lightweight-charts assertion:** `data must be asc ordered by time` — OHLCV data returned unsorted
- **ErrorBoundary caught and displayed:** ChartPane crashes gracefully

### ✅ Sidebar Navigation
- Screener → Charts ✅ (URL reflects correctly)
- All sidebar links functional

## Architecture Decisions
- **None** — All changes were bug fixes, not architecture decisions.

## Files Modified
- `backend/app/api/routers/tv_screener.py` — Added `ScreenConfig` import and `_resolve_config` fallback for name-to-filename matching
- `docker-compose.override.yml` — Removed `VITE_WS_URL` env var
- `frontend/src/components/screener/ScreenerTable.tsx` — Renamed `key` prop to `colKey` in SortIcon

## Verification
- API curl tests confirmed: Trend Follower (593 matches), Mean Reversion (108 matches) — both return data
- Playwright E2E: All pages load, all 7 templates work, pagination/detail/navigation functional
- LSP diagnostics: clean (pre-existing `fastapi` import resolution issue in LSP only, not runtime)
- Console errors eliminated on Screener page (was 4+ errors, now 0)

---

## Second Session: UI Redesign (Table + Detail Panel)

### Changes Made

| What | Why | Files |
|------|-----|-------|
| **TVDataFields type** | Properly typed `tv_data` from `Record<string, unknown>` to `TVDataFields` interface with known fields (close, change, volume, sector, market_cap_basic, etc.) | `types/screener.ts` |
| **ScreenerTable rewrite** | Complete column overhaul: removed dead RSI/MACD/Signal columns, added Entry (+stop loss), Confluence bars (trend/momentum/volume), sector in symbol cell, proper color coding | `ScreenerTable.tsx` |
| **ChangeCell fix** | Compute percentage from `change / (close - change)` — was always showing `0.00%` because `change_percent` field doesn't exist in API | `ScreenerTable.tsx` |
| **DetailPanel fix** | Same change percentage fix + import `formatPct` utility | `DetailPanel.tsx` |
| **Store default** | Changed `selectedConfig` from `'trend-follower'` → `'Trend Follower'` to match API response names | `screen.ts` |
| **Template init** | Added fuzzy name matching for template selector (handles old hyphenated localStorage values) | `ScreenerPage.tsx` |
| **Template selector styling** | Cleaned up dropdown styles with hover/focus states, proper option display | `ScreenerPage.tsx` |

### New Column Layout

| Column | Content | Alignment |
|--------|---------|-----------|
| Symbol | Ticker + sector label | left (sticky) |
| Price | Current close price | right |
| Score | Colored badge (green/orange/red) | center |
| Change | Price change + computed % | right (colored) |
| Entry | Entry price + stop loss | right |
| Confluence | 3-segment colored bars + scores (T/M/V) | center |
| Volume | Volume + relative volume ×N | right |
| Rating | Compact colored badge (SB/B/H/S/SS) | center |
| Action | Details button | center |

### E2E Verification
- **Console errors**: 0 (only favicon 404 pre-existing)
- **Change % correct**: Confirmed `UBER +5.47 +7.73%`, `ABBV +4.20 +1.69%`, `KO +2.75 +3.44%` etc.
- **Template switch**: Mean Reversion loads correctly, data updates
- **Detail panel**: Opens with correct symbol, shows correct change
- **TypeScript**: Clean compile (`tsc --noEmit` passes)
- **Vite build**: Succeeds (only chunk size warning, pre-existing)

### Files Modified (5)
- `frontend/src/types/screener.ts`
- `frontend/src/components/screener/ScreenerTable.tsx`
- `frontend/src/components/screener/DetailPanel.tsx`
- `frontend/src/components/screener/ScreenerPage.tsx`
- `frontend/src/store/screen.ts`

## Next Steps
1. **Charts page**: Fix API indicator endpoints (500 errors) and sort OHLCV data by time (lightweight-charts assertion)
2. Consider adding React Router v7 future flags (`v7_startTransition`, `v7_relativeSplatPath`) to eliminate warnings
3. Add backend tests for template-name resolution
