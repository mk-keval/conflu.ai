# Session: Filter Sweep Backtest Fixes & VectorBT/Plotly Compatibility Issue

**Date:** 2026-09-25  
**Branch:** `fix/technical-tab-empty`  
**Last Commit:** Previous `56889fb` - "feat: Gate Enforcement Spine Wave-1 complete"

---

## ✅ What Was Accomplished

### 1. Frontend TypeScript Build Fixes
All TypeScript build errors blocking the filter sweep UI have been resolved:

| File | Issues Fixed |
|------|--------------|
| `FilterSweepForm.tsx` | Removed unused state (`_presets`, `setPresets`, `_availableParams`, `_setAvailableParams`), fixed `optimization_metric` type casts at 3 select elements, removed unused `cn` import |
| `FilterSweepResults.tsx` | Fixed duplicate `avg_hold_days` property, added missing imports (`ChevronRight`, `Download`, `Plus`), removed unused imports, removed unused variables (`metricInfo`, `selectedResult`, `sweep_id`, `param_sensitivity`, `error_message`, `metricKey`, `onBack`) |
| `FilterSweepPage.tsx` | Removed unused `cn` import, removed unused `handleNewSweep` function, added `onSweepComplete` prop support to `FilterSweepForm` |
| `api/backtest.ts` | Removed unused imports (`FilterSweepPreset`, `FilterParamRange`) and re-exports |

**Result:** `npm run build` passes successfully ✅

### 2. Filter Sweep API Routing Fix
The `filter_sweep_router` was exported but not included in `backend/app/api/main.py`. Added import and `app.include_router(filter_sweep_router, prefix="/api/v1")`.

### 3. Sweep Parameter Names Alignment
Updated `DEFAULT_FILTER_PARAM_RANGES` and `PRESET_SWEEPS` in `filter_sweep.py` to use parameter names that match actual TV screener FILTER_MAP indicator names:

| Old Parameter | New Parameter | TV Filter Indicator |
|---------------|---------------|---------------------|
| `rs_rank_min` | `market_cap_gt` | `market_cap_gt` |
| `atr_pct_min`/`atr_pct_max` | `atr_pct_below` | `atr_pct_below` |
| `avg_daily_volume_usd_min` | `avg_volume_gt` | `avg_volume_gt` |
| `rvol_min` | `rvol_high` | `rvol_high` |
| `rsi_min`/`rsi_max` | `rsi_in_range`/`rsi_in_range_max` | `rsi_in_range` |
| `adx_min` | `adx_trending` | `adx_trending` |
| `rsi_entry_min`/`rsi_entry_max` | `rsi_oversold` | `rsi_oversold` |
| `volume_contraction_days` | `bb_squeeze` | `bb_squeeze` |
| `breakout_volume_mult` | `volume_gt` | `volume_gt` |
| `ma_stack_required` | `price_above_ema` | `price_above_ema` |

Updated all 5 preset sweeps (`trend_follower_optimization`, `high_conviction_optimization`, `breakout_optimization`, `pullback_optimization`, `institutional_quality_optimization`) to use correct parameter names matching their respective screen templates.

### 4. Parameter Mapping Fix in Engine
Fixed `_apply_params_to_screen` in `filter_sweep_engine.py` to correctly map sweep parameter names to filter indicator parameter keys (e.g., `market_cap_gt` → `value`, `rvol_high` → `threshold`, `rsi_in_range` → `min`/`max`).

### 5. Exception Handling for Plotly Template Error
Added comprehensive exception handling in `_run_sync` method to catch `ValueError` from plotly template validation (`scattermapbox` → `scattermap` rename in plotly v6). The handler logs the error and returns a minimal valid `BacktestRunRecord`.

### 6. FilterSweepResult Default Values Fix
Fixed `_run_single_backtest` to use `0` instead of `None` for `max_consecutive_wins` and `max_consecutive_losses` when metrics is None, matching the model defaults.

---

## 🚧 Known Issue: VectorBT/Plotly Compatibility

### The Problem
**Every single backtest fails** with:
```
ValueError: Invalid property specified for object of type plotly.graph_objs.layout.template.Data: 'scattermapbox'
```

### Root Cause
- **vectorbt 1.0.0** (latest) uses plotly internally for statistics visualization
- **plotly 6.x** renamed `scattermapbox` to `scattermap` (breaking change)
- vectorbt's internal template still references `scattermapbox`
- The error occurs when `portfolio.stats()` is called, which triggers plotly template creation

### Constraints
- vectorbt versions: only `<0.40.0` or `>=1.0.0` available (no middle ground)
- Currently using vectorbt 1.0.0 with plotly 5.24.1 (pinned)
- Downgrading vectorbt not feasible due to version gap
- Patching vectorbt's internal template is complex (template created at import time)

### Attempted Fixes (All Failed)
1. Pin plotly <6.0 → vectorbt 1.0.0 still uses internal template with old name
2. Monkey-patch `go.layout.Template` at module level → template data is a property, not mutable dict
3. Monkey-patch `TemplateData.__setattr__`/`__setitem__` → validation happens at class definition time
4. Try/except around `portfolio.stats()` → error raised during template creation, not stats computation
5. Catch `BaseException` in `_run_sync` → catches error but minimal record has 0 trades → marked invalid

### Impact
- **All 2000 sweep combinations fail** → no valid results to analyze
- Filter sweep framework works end-to-end (API, UI, parameter mapping)
- Backtest engine cannot produce valid results due to dependency issue

---

## 📋 Current State Summary

### ✅ Working
- Frontend build passes
- Filter sweep API endpoints (presets, params, run, status, result, list, delete)
- Parameter sweep configuration with 5 presets
- Parameter mapping to TV screener filters
- Frontend UI components (FilterSweepForm, FilterSweepResults, FilterSweepPage)
- Exception handling for plotly errors (graceful degradation)

### ❌ Blocked
- Backtest engine cannot produce valid results
- All sweep combinations return failed results (0 trades → invalid)
- No valid sweep results to analyze

---

## 🎯 Recommended Next Steps

### Option 1: Alternative Backtest Approach (Recommended)
Implement a lightweight custom backtest engine that:
- Uses the same signal generation (TV screener filters)
- Computes metrics directly from trade records
- Avoids vectorbt/plotly entirely
- Can run within the existing sweep framework

### Option 2: VectorBT Patch
Fork vectorbt and patch the internal template to use `scattermap` instead of `scattermapbox`. Requires maintaining a fork.

### Option 3: Downgrade VectorBT (Not Feasible)
No version between 0.40.0 and 1.0.0 exists.

### Option 4: Accept Limitation & Document
- Mark backtest engine as "experimental - known plotly compatibility issue"
- Use sweep framework for parameter configuration only
- Run actual backtests externally or with alternative tooling

---

## 📁 Key Files Modified

| File | Changes |
|------|---------|
| `frontend/src/components/backtest/FilterSweepForm.tsx` | TypeScript fixes, prop types |
| `frontend/src/components/backtest/FilterSweepResults.tsx` | Imports, duplicates, unused vars |
| `frontend/src/components/backtest/FilterSweepPage.tsx` | Imports, prop handling |
| `frontend/src/api/backtest.ts` | Unused imports/exports |
| `backend/app/api/main.py` | Added filter_sweep_router |
| `backend/app/infrastructure/backtest/filter_sweep.py` | Parameter names, presets |
| `backend/app/infrastructure/backtest/filter_sweep_engine.py` | Parameter mapping, exception handling, default values |
| `backend/app/infrastructure/backtest/engine.py` | Exception handling for plotly error |

---

## 📝 Session Log Reference
- Previous: `2026-09-24_filter-sweep-backtest-framework-gate-enforcement.md`
- This session: `2026-09-25_filter-sweep-backtest-fixes.md`

---

*Generated: 2026-09-25 | Branch: fix/technical-tab-empty*