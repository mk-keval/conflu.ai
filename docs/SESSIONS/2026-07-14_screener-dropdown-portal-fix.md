# Session: Screener Dropdown Portal Fix

**Started:** 2026-07-14
**Branch:** screener-fixes-elite-trader
**Files Modified:** 1 (frontend)

## Prompt
Fix the TemplateDropdown pointer-events interception bug where items below the visible scroll area couldn't be clicked.

## Problem
The TemplateDropdown used absolute positioning within the component hierarchy. When scrolling to items below the fold (e.g., "Distribution"), the results table's `div.flex-1.overflow-auto` from the `div.flex-1.overflow-hidden.relative` subtree intercepted pointer events. This happened because the parent container created a stacking context that trapped pointer events, making the dropdown items unclickable.

## Root Cause
- The results table container `div.flex-1.overflow-hidden.relative` creates a stacking context
- The dropdown, even with `z-50` or `z-[100]`, lives in the parent component's stacking context
- When the dropdown extends below the header into the results area, the `overflow-auto` div captures pointer events
- `z-index` alone cannot fix this because the stacking contexts are separate

## Fix
Converted TemplateDropdown from absolute positioning to portal-based fixed positioning (same pattern used by ColumnCustomizer - D-22):

- Added `createPortal` from `react-dom`
- Added `btnRef` (button ref) to measure trigger button position
- Added `dropdownStyle` state for dynamic positioning via `getBoundingClientRect()`
- Rendered dropdown menu via `createPortal` to `document.body` with `position: fixed` and `zIndex: 9999`
- Updated outside-click handler to check both the parent wrapper AND the portal dropdown

## Files Changed
- `frontend/src/components/screener/ScreenerPage.tsx` (TemplateDropdown component)

## Verification
- Playwright test: Header shows "Breakout" template, dropdown opens on click
- "Distribution" (mid-list item) — **CLICKED SUCCESSFULLY** ✅
- "Institutional Accumulation" (last item, bottom of list) — **CLICKED SUCCESSFULLY** ✅
- Selected template loads API data correctly
- Dropdown closes on selection and on outside click

## Related Decisions
- D-22: ColumnCustomizer Portal for Z-Index Escape (same pattern)
- D-25: TemplateDropdown Portal for Pointer-Events Escape (this fix)

## Next Steps
- None — dropdown fully functional for all 22 templates
