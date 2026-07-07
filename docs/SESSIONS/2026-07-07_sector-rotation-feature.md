# Session Log: Sector Rotation Smart Money Tracker

**Started:** 2026-07-07 08:00
**Branch:** `feature/sector-rotation`
**Base:** `ui-audit-fixes`

## User Prompt
Build a sector rotation feature where users can see which sector smart money is flowing into, with 1D and 1W timeframe views, and educational content about sector rotation concepts.

## Actions Taken
1. Created new branch `feature/sector-rotation` from `ui-audit-fixes`
2. Built backend API router at `backend/app/api/routers/sector_rotation.py`:
   - `GET /api/v1/sector-rotation` — Full sector rotation snapshot with 11 sector ETFs
   - `GET /api/v1/sector-rotation/history` — Historical rankings for charting
   - `GET /api/v1/sector-rotation/{symbol}` — Deep-dive on single sector
3. Registered router in `main.py` and `__init__.py`
4. Built frontend types at `frontend/src/types/sector.ts`
5. Built API client at `frontend/src/api/sectorRotation.ts`
6. Built Zustand store at `frontend/src/store/sectorRotation.ts`
7. Created component directory `frontend/src/components/sector-rotation/` with:
   - `SectorHeatMap.tsx` — Color-coded grid of all 11 sectors with perf, RS, volume, flow
   - `SectorDetailCard.tsx` — Deep-dive panel with price chart, metrics, flow signal
   - `RotationFlows.tsx` — Rotation phase banner + top momentum sectors with flow arrows
   - `EducationPanel.tsx` — Learn section: What is sector rotation, how smart money rotates, classic cycle, key metrics, strategy tips
   - `SectorRotationPage.tsx` — Main page with tabs (Heatmap, Flows, Learn), metrics bar, timeframe toggle
8. Updated `Sidebar.tsx` with nav item, `App.tsx` with route, store/types index exports

## Files Modified
- `backend/app/api/main.py` — Registered sector_rotation router
- `backend/app/api/routers/__init__.py` — Added sector_rotation import
- `frontend/src/App.tsx` — Added `/sector-rotation` route
- `frontend/src/components/layout/Sidebar.tsx` — Added nav item
- `frontend/src/store/index.ts` — Exported sectorRotation store
- `frontend/src/types/index.ts` — Exported sector types
- `docs/API.md` — Added sector rotation API documentation

## Files Created
- `backend/app/api/routers/sector_rotation.py` — 545 lines
- `frontend/src/types/sector.ts` — 34 lines
- `frontend/src/api/sectorRotation.ts` — 22 lines
- `frontend/src/store/sectorRotation.ts` — 53 lines
- `frontend/src/components/sector-rotation/` (6 files)

## Key Design Decisions
- **11 sector SPDR ETFs** tracked (XLF, XLK, XLV, XLI, XLB, XLE, XLU, XLRE, XLY, XLP, XLC)
- **Relative strength** computed as Z-score vs all sectors (positive = outperforming)
- **Smart money flow signal** derived from price + volume ratio + RS combination (not actual order flow)
- **3 tabs**: Heatmap (visual grid), Flows (rotation phase + momentum), Learn (educational content)
- **Auto-refresh** every 60s with toggle
- **Rotation phase detection** via which sectors lead (early cycle → growth → late cycle → defensive)

## Phase 2 — Market Regime System + Frontend Integration

### Actions Taken
1. **Created market regime backend** (`backend/app/api/routers/regime.py`):
   - `GET /api/v1/market/regime` — Elite trader-grade composite regime analysis
   - Tracks 6 macro symbols: VIX, SPY, TLT, GLD, SHY, DXY
   - **5 sub-indicators weighted into a 0-100 composite score:**
     - VIX (30%): Level + trend scoring (complacent → panic)
     - Risk Appetite (25%): SPY vs TLT performance spread
     - Sector Breadth (20%): % of 11 sectors with positive 1W return
     - Safe Haven (15%): GLD vs SPY divergence (flight to safety detection)
     - Yield Curve (10%): TLT vs SHY relative performance
   - Dynamic weight adjustment: boosts Risk Appetite weight during extreme conditions
   - Returns label + hex color for UI rendering + human-readable interpretation
2. **Registered regime router** in main.py and __init__.py
3. **Built RegimeBar component** (`frontend/src/components/layout/RegimeBar.tsx`):
   - Compact pill button in the top Header showing score + label + mini bar
   - Expandable detail panel with 5 sub-indicator scores + color-coded dots
   - Dynamic interpretation text based on composite score range
   - Auto-fetches every 60s, closes on outside click
4. **Created global market store** (`frontend/src/store/market.ts`) — Zustand store for regime state
5. **Integrated into Header** — RegimeBar sits on the right side of the search bar
6. **Fixed flow signal thresholds** for ETFs:
   - Lowered volume thresholds (1.3→0.8, 1.1→0.6) for ETF sensitivity
   - Added partial trading day detection: uses previous completed day's volume ratio when today is incomplete
7. **Verified Top 3 heading** already showed 'Today'/'This Week' based on timeframe selection (previously fixed)

### Files Modified (Phase 2)
- `backend/app/api/routers/__init__.py` — Added regime router
- `backend/app/api/main.py` — Registered regime router
- `frontend/src/types/sector.ts` — Added regime types
- `frontend/src/api/sectorRotation.ts` — Added `fetchMarketRegime()` client
- `frontend/src/components/layout/Header.tsx` — Integrated RegimeBar
- `backend/app/api/routers/sector_rotation.py` — Fixed flow signal thresholds, partial day volume detection

### Files Created (Phase 2)
- `backend/app/api/routers/regime.py` — 320 lines
- `frontend/src/store/market.ts` — 21 lines
- `frontend/src/components/layout/RegimeBar.tsx` — 204 lines

## Phase 3 — Rate Limit & Loading State Fixes

### Issues Found & Fixed

1. **`lru_cache` TTL was fake** — `regime.py` used `@lru_cache(maxsize=1)` with a decorative `ttl=int` parameter. Python's `lru_cache` ignores TTL — it caches the first result **forever**. The method signature suggested 30s expiry but data was only refreshed on process restart.

2. **No caching on sector rotation** — `_cached_sector_data()` was **defined but never called**. All 3 routes (`/`, `/history`, `/{symbol}`) called `_fetch_all_sector_data()` directly, making **11 fresh yfinance calls per API request**. With auto-refresh every 60s, that's **11 yfinance calls/minute** just from sector rotation.

3. **Regime loading state destroyed pill button** — When background refresh errored (rate limit), `setError()` triggered `if (error || !regime)` which replaced the pill button with a "Loading..." div. User saw popup vanish.

4. **Sector breadth re-fetches** — `_fetch_sector_breadth()` was also uncached, making 11 more yfinance calls per regime request.

### Fixes Applied

| Fix | File | Detail |
|-----|------|--------|
| Replaced `lru_cache` with timestamp TTL | `regime.py` | Module-level `_MACRO_CACHE` with 300s expiry check |
| Cached sector breadth | `regime.py` | `_SECTOR_BREADTH_CACHE` with 300s TTL |
| Cached sector data | `sector_rotation.py` | `_SECTOR_CACHE` with module-level timestamp |
| Actually use cached sector data | `sector_rotation.py` | All 3 call sites now use `_get_cached_sector_data()` |
| Preserve pill button on refresh error | `RegimeBar.tsx` | Local `fetchError` state instead of global `error` — keeps stale data visible |
| Show stale indicator | `RegimeBar.tsx` | Tiny warning icon on collapsed button + "Stale data" note in expanded panel |
| Reduced polling to 5 min | `RegimeBar.tsx` | 300_000ms interval (from 60s) |
| Reduced sector rotation refresh | `SectorRotationPage.tsx` | 300_000ms interval (from 60s) |
| Cleaned unused imports | Both routers | Removed `functools`, `math`, `numpy` (regime), `Field` (both) |

### Current yfinance Call Budget

| Source | yfinance Calls | Refresh | Calls per 5 min |
|--------|---------------|---------|-----------------|
| Regime macro data | 6 (VIX, SPY, TLT, GLD, SHY, DXY) | Every 5 min | 6 |
| Regime sector breadth | 11 (via separate fetch) | Every 5 min | 11 |
| Sector rotation | 11 | Every 5 min | 11* |
| **Total** | **28 max per full refetch** | **Every 5 min** | **28 calls / 5 min** |

\* Sector rotation sector breadth overlaps with regime's. With 5-min TTL and aligned refresh cycles, most calls serve cached data.

## Phase 4 — Remove Sector Rotation Auto-Refresh

### Motivation
User requested: "sector we are keep calling even if the user is not on sectors page, I think a button to refresh sectors would be ideal so whenever user is on sector page and wants the updated data then only we make calls."

With auto-refresh removed, sector rotation data is fetched **only** on:
1. **Initial mount** — page load (single fetch)
2. **Manual "Refresh" button click** — user-initiated reload

### Changes Made

| Change | Detail |
|--------|--------|
| Removed `autoRefresh` state | No more toggle tracking |
| Removed auto-refresh `useEffect` | No more `setInterval(loadData, 300_000)` |
| Removed "Auto" toggle button | No more auto/manual toggle in UI |
| Added `lastUpdated` timestamp | Shows `Updated HH:MM:SS AM/PM` next to Refresh button |
| Updated `setLastUpdated` | Timestamp set in `finally` block after each loadData call |

### Rationale
- **Regime (header)** still auto-refreshes every 5 min — it's a global indicator visible on every page
- **Sector rotation** is page-specific — no point burning yfinance calls when user is on Screener, Charts, Backtest, or Risk pages
- Manual refresh gives user control over when to burn yfinance budget

### Files Modified
- `frontend/src/components/sector-rotation/SectorRotationPage.tsx` — Removed auto-refresh state, interval, and toggle; added lastUpdated timestamp display

## Phase 4b — Fix RegimeBar Popup Z-Index

### Issue
When clicking the regime pill to expand the detail panel, the popup rendered **behind** the main page content. Root cause: the `<header>` element came before `<main>` in the DOM, and `<main>` naturally stacked above it. The regime popup's `z-50` was limited to the header's stacking context (created by `backdrop-blur`), which had no explicit z-index — so main always won.

### Fix
Added `relative z-10` to the `<header>` element, lifting the entire header + its stacking context above `<main>`. The regime popup at `z-50` now renders correctly on top of everything.

### File Modified
- `frontend/src/components/layout/Header.tsx` — Added `relative z-10` to header className

## Phase 5 — Timeframe-Aware Volume Metrics

### Issue
Volume indicator (`Vol: 0.9x avg`) showed the same value regardless of 1D/1W toggle. The backend stored only a single `volume_vs_avg` field (daily volume / 20d avg), and it was used for both timeframes. When toggling to 1W, price returns correctly switched to `change_1w` but volume stayed on the daily metric.

### Fix
1. **Backend** — Added `volume_vs_avg_1w` field to `SectorPerformance` model and `_fetch_all_sector_data()` function:
   - 1D: `latest_daily_volume / 20_day_average_daily_volume` (unchanged)
   - 1W: `sum(last_5_days_volume) / average_of_all_rolling_5day_sums`
   - Both computed in a single pass during data fetch
2. **Frontend** — `SectorHeatMap.tsx` now selects `volume_vs_avg` (1D mode) or `volume_vs_avg_1w` (1W mode) via a `volKey` variable, matching how `changeKey` and `rsKey` already work

### Files Modified
- `backend/app/api/routers/sector_rotation.py` — Added volume_vs_avg_1w to model, computation in _fetch_all_sector_data, set on performance objects in get_sector_rotation
- `frontend/src/types/sector.ts` — Added volume_vs_avg_1w to SectorPerformance interface
- `frontend/src/components/sector-rotation/SectorHeatMap.tsx` — Switched to timeframe-aware volKey

## Verification
- **Frontend:** `tsc --noEmit` passes clean ✅
- **Backend:** Python AST parse + compile pass ✅
- **Playwright E2E:** 0 JS errors, 3 warnings (pre-existing React Router flags + WS) ✅
- **Regime API:** `GET /api/v1/market/regime` returns 200 with real data (52.0 Neutral) ✅
- **Sector Rotation API:** Returns 200 with flow signals (XLV Strong inflow, XLB Strong outflow, etc.) ✅
- **1D toggle:** Headers show "Today" / "1 Day" ✅
- **1W toggle:** Headers show "This Week" / "1 Week" ✅
- **RegimeBar:** Score 52 "Neutral" visible in header with expandable detail panel ✅
- **Regime panel expanded:** Shows VIX (60), Risk Appetite (28), Sector Breadth (45), Safe Haven (85), Yield Curve (55) ✅
- **Pre-existing error:** `opentelemetry` import in main.py (conditional import)
- **Phase 4:** Auto-refresh removed ✅; manual refresh + last updated timestamp ✅
- **Refresh button:** Timestamp updates from `11:34:00 AM` → `11:34:28 AM` after click ✅
- **Phase 5:** Volume metrics now timeframe-aware ✅
  - 1D Vol: 0.6x (XLV daily), 1.7x (XLB daily) — catches daily spikes
  - 1W Vol: 1.1x (XLV weekly), 1.0x (XLB weekly) — smooths to weekly norm

## Next Steps
- Add sector ETF holdings/components detail
- Add historical regime chart (regime score over time)
- Consider adding alerts for regime phase changes
- Add regime score to the sidebar or global nav
- Consider Playwright test for manual refresh interaction
- Regime stale-data optimization (2026-07-07):
  - Backend cache TTL: 5min → 6hr (daily data only changes at close)
  - Frontend polling: 5min → 1hr
  - Added "As of HH:MM" timestamp in regime pill
