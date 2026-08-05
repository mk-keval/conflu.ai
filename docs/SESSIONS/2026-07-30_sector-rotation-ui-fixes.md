# Session: Sector Rotation UI Fixes

**Date**: 2026-07-30
**Branch**: fix/elite-trader-gaps

## Changes

### 1. RotationFlows timeframe-awareness (Bug fix)
**Files**: `frontend/src/components/sector-rotation/RotationFlows.tsx`

- Added `timeframe` prop to `RotationFlows` component
- Sorting now uses `relative_strength_1d` or `relative_strength_1w` based on the selected timeframe (was always using the fixed composite `momentum_score`)
- Flow arrows and volume indicators switch between 1D and 1W fields
- RS values now displayed per-sector with sign indicators
- Phase banner now shows "based on 1W data" label + actionable guidance text per phase
- Added `based on 1W data` badge on phase banner to clarify timeframe basis
- Removed unused imports, added `Info` icon for action tips

### 2. SectorRotationPage prop wiring
**Files**: `frontend/src/components/sector-rotation/SectorRotationPage.tsx`

- Passes `timeframe` prop to `<RotationFlows />` (was missing)
- Added "trailing 1W basis" subtitle on rotation phase metric card

### 3. EducationPanel rewrite
**Files**: `frontend/src/components/sector-rotation/EducationPanel.tsx`

- Replaced formula-based explanations with plain-English analogies (RS = "lap times on a track")
- Added actionable guidance: "what to do" per rotation phase
- Added sections:
  - **1D vs 1W** — explains why both matter and how to use them together (including today's scenario)
  - **Common Mistakes** — FOMO, timeframe conflicts, fighting the phase, treating all inflows equally
- New visual elements: highlight callout boxes for key insights, tip callouts per section
- Removed classic cycle theory section (moved into phase guide with actionable strategy)

### 4. Variable name cleanup in regime.py (no logic change)
**Files**: `backend/app/api/routers/regime.py`

- Renamed misleading `_5d` suffixes to `_1mo` in `_score_vix`, `_score_risk_appetite`, `_score_safe_haven`, `_score_yield_curve`
- The code was always computing trailing ~1-month returns (data fetched with `period="1mo"`, uses `iloc[0]` which is ~21 trading days back)
- Variable names said "5d" but computed "1mo" — fixed the names to match reality
- Added docstring notes explaining the 1-month lookback is intentional for swing trading
- Updated cache TTL comment to explain the 6-hour design rationale (swing trader checks 2-3x/day)
- Sector breadth function uses `period="1w"` and was correctly named — left unchanged

## Root Causes Fixed
1. `RotationFlows` was not receiving the `timeframe` prop → always showed composite momentum regardless of toggle
2. No explanation of why rotation phase can disagree with daily price action → added "based on 1W data" labels
3. Education content was too theoretical (formulas, cycle theory) → rewritten as actionable trading guidance
4. `regime.py` variable names said `_5d` but computed `_1mo` returns — misleading for future developers
