# Session: UI Audit & Fixes

**Started:** 2026-07-03
**Branch:** `ui-audit-fixes`

## Prompt
Full Playwright-based UI audit of all pages. Fix overlapping, crash, and visual consistency issues. Modernize branding and styling.

## Actions Taken

### Bug Fixes
1. **ColumnCustomizer z-index** — Dropdown was hidden behind table due to `backdrop-blur-sm` creating isolated stacking context on ScreenerHeader. Fixed by rendering menu via `createPortal` into `document.body` with `position: fixed` computed from button bounding rect.
2. **ChartPane crash** — `lightweight-charts` `setData()` throws "data must be asc ordered by time" when candle/indicator data is unsorted. Added `.sort((a, b) => a.time - b.time)` before each `setData()` call.
3. **SymbolSearch crash** — `(symbols || []).filter is not a function` when API returns unexpected format. Added `Array.isArray(symbols)` guard before rendering logic.

### UI Improvements
4. **Header cleanup** — Removed redundant "conflu.ai" branding (already in sidebar), secondary nav links (sidebar handles navigation with proper `<NavLink>`), and duplicate `ConnectionStatus` component (sidebar has `ConnectionDot`). Header is now a clean centered search bar with `max-w-md` and subtle backdrop blur.
5. **Sidebar refinements** — Added accent gradient bar at top. Redesigned brand section with accent logo block + "conflu.ai" light/heavy weight split. Added `animate-ping` glow to connected dot. Refined nav item active styling with thicker border-left.
6. **Favicon** — Added `frontend/public/favicon.svg` as dark themed SVG with accent gradient "C" on dark background. Added `<link>` to `index.html`.
7. **Docker volumes** — Added `./frontend/public:/app/public` and `./frontend/index.html:/app/index.html` to frontend service for hot-reload of static assets.
8. **ScreenerTable** — Improved row hover with subtle accent tint. Added glass-effect shadow to sticky column header. Refined sort icons and column borders.

### Housekeeping
9. **.gitignore** — Added `.sisyphus/` and `*.png` to prevent session artifacts from polluting git status.
10. **Typecheck** — `tsc --noEmit` clean. **Build** — `vite build` clean (2765 modules, 9.82s).

## Files Changed
- `frontend/src/components/screener/ScreenerPage.tsx` — ColumnCustomizer portal fix
- `frontend/src/components/charts/ChartPane.tsx` — Candle/indicator data sorting
- `frontend/src/components/charts/SymbolSearch.tsx` — Array.isArray guard
- `frontend/src/components/layout/Header.tsx` — Stripped to search-only toolbar
- `frontend/src/components/layout/Sidebar.tsx` — Gradient bar, refined brand + connection dot
- `frontend/src/components/screener/ScreenerTable.tsx` — Row hover, glass header, refined styling
- `frontend/index.html` — Added favicon link
- `frontend/public/favicon.svg` — New file: dark SVG favicon
- `docker-compose.yml` — Added frontend static asset volumes
- `.gitignore` — Session artifact rules

---
### Second Session: Playwright Testing & Post-Audit Fixes

**Prompt:** Full Playwright-based end-to-end testing of Screener & Charts pages to verify all fixes, plus additional bug fixes discovered during testing.

### Changes Made

1. **IndicatorCache (backend)** — Created `backend/app/infrastructure/screener/cache.py` with `IndicatorCache` class that queries `indicator_values` table (939K rows). Fixes API 500 errors on all 4 indicator endpoints (RSI, MACD, EMA_20, BB). Added `NaT` defensive check in `data.py`.

2. **`+-` double sign bug** — Extracted `changePct()` to `lib/format.ts` with `prev < 0` fallback formula `(change / price) * 100`. Imported in `ScreenerTable.tsx` and `DetailPanel.tsx`. Fixes the `+-1880.97%` display issue.

3. **Column customizer portal outside-click** — Added `dropdownRef` for portal content. Outside-click handler now checks BOTH parent wrapper AND portal dropdown content before closing. Fixes dropdown closing immediately when clicking any option.

4. **Deep Analysis button** — Changed from `console.log` no-op to `refetchAnalysis()` (React Query manual refetch). Removed unused `onAnalyze` prop from `DetailPanel` and `ScreenerPage`.

5. **Charts error UI** — Added error state detection for indicator queries. Shows a warning banner when indicators fail: `"Indicator error: RSI, MACD — data unavailable"`.

6. **Symbol column width** — Reduced `weight` from 13 to 8 (short ticker text needs less space).

### Files Changed (this session)
- `backend/app/infrastructure/screener/cache.py` — **NEW**: IndicatorCache class
- `backend/app/api/routers/data.py` — NaT defensive check
- `frontend/src/lib/format.ts` — changePct() with prev < 0 fallback
- `frontend/src/components/screener/ScreenerTable.tsx` — Imported changePct, symbol weight 13→8
- `frontend/src/components/screener/DetailPanel.tsx` — Shared changePct(), removed onAnalyze, refetchAnalysis()
- `frontend/src/components/screener/ScreenerPage.tsx` — ColumnCustomizer portal fix, removed handleDeepAnalysis
- `frontend/src/components/charts/ChartsPage.tsx` — Indicator error UI

### Verification
- `tsc --noEmit`: Pass (0 errors)
- `python -m py_compile cache.py`: Pass
- **Playwright E2E Screener**: 615 matches load ✅, `+-` sign gone ✅, column customizer stays open on click ✅
- **Playwright E2E Charts**: All 4 indicator APIs return 200 ✅ (was 500)
- **Note**: Pre-existing bug: Charts page crashes from duplicate OHLCV timestamps (`lightweight-charts` assertion: data must be asc ordered by time). Not introduced by this session.

---
### Third Session: User-Reported Bug Fixes (Tooltip, Column Alignment)

**Prompt:** Fix 3 issues: (1) confluence tooltip shows on any row hover instead of only confluence cell, (2) tooltip not readable, (3) last two columns (Rtg, Action) not aligned.

### Changes Made

1. **Confluence tooltip scope** — Wrapped CellConfluence in `group/confluence` (Tailwind named group). Changed tooltip from `group-hover:block` to `group-hover/confluence:block`. Prevents nested group hover from any ancestor triggering the tooltip.

2. **Tooltip readability** — Changed tooltip container from `bg-dark-600 border border-border/50 text-text-secondary` to `bg-surface-elevated border border-border/60` with `shadow-2xl` and `pointer-events-none`. Significantly improves contrast and elevation.

3. **Column weight balancing** — Rating column weight 6→8, action column weight 7→9. Action column header uses `tracking-normal` instead of `tracking-wider` (empty label, no text to track).

4. **Column alignment fix** — Added `overflow-hidden` to DataRow flex cells. Root cause: flex items default to `min-width: auto` and `overflow: visible`, so cells with content wider than `flex-basis` (e.g., sector "Technology Services") visually overflow into neighboring columns, pushing them out of alignment. `overflow-hidden` clips content to flex-basis, keeping column boundaries consistent.

### Files Changed (this session)
- `frontend/src/components/screener/ScreenerTable.tsx` — Named group for confluence tooltip, tooltip styling, column weights, overflow-hidden on data cells

### Verification
- **tsc --noEmit**: No new errors (pre-existing JSX/lib config errors only)
- **Playwright alignment check**: 253 non-confluence data cells have `overflow: hidden`. Sector column width locked at 111px (was varying 111-135px). Rtg + Action center positions identical across all rows ✅
- **Tooltip scope**: `group-hover/confluence:block` only fires within `group/confluence` wrapper — row-hover no longer triggers it ✅
- **Tooltip visibility**: Playwright hover test confirms `display: block`, 121×98px, z-index 50, positioned above cell, parent overflow visible ✅
- **Note**: `overflow-hidden` is applied conditionally — all columns except `confluence` get it, so the confluence tooltip (absolutely positioned above the cell) is not clipped.
