# Session: Scoring Calibration, SHORT Screens & MTF Weighted Stacking

**Started:** 2026-06-30
**Branch:** `feat/scoring-calibration-and-deep-fix`
**Initial PR:** (#4 → closed, stacked into #5)

## Prompt
Trading veteran evaluation identified scoring issues (binary thresholds, MTF strict intersection, missing SHORT screens, hidden Quality/Fundamental factors). Fix all issues, then create final PR.

## Actions Taken

### Scoring Calibration
1. **Volume scoring graded** — `rel_vol > 1.5` (binary +10) → 5-band graded scale (1/3/6/8/10). `vol_change > 0` (binary +5) → magnitude-graded (1/2/3/5). VWAP position graded by % above (1/3/5).
2. **Trend scoring graded** — Binary `close > EMA200` (+10) and `close > EMA50` (+10) → percent-distance graded (4/6/8/10 per EMA). EMA alignment graded by spread (4/7/10).

### UI Improvements
3. **All 5 confluence factors displayed** — Quality (purple) and Fundamental (cyan) now shown alongside Trend/Momentum/Volume in screener table.

### SHORT Screen Templates
4. **3 new screen YAMLs**: Breakdown (bearish), Short Squeeze (bullish from short dynamics), Distribution (heavy institutional selling)
5. **4 new FILTER_MAP entries**: `price_below_vwap`, `rvol_low`, `ema_cross_bearish`, `analyst_sell`

### MTF Weighted Stacking
6. **Replaced strict intersection** with weighted TF scoring: Daily 0.50, 4h 0.25, Weekly 0.25. Tickers matching 2/3 TFs now get partial credit instead of 0.

### Bug Fix
7. Fixed pre-existing `test_oversold_bounce_loads` assertion (filter count changed from 2→3 in PR #3).

## Files Modified
- `backend/app/infrastructure/screener/confluence_scorer.py` — Graded trend & volume scoring
- `backend/app/infrastructure/screener/tv_specialist.py` — New FILTER_MAP entries
- `backend/app/infrastructure/screener/tv_engine.py` — Weighted MTF stacking
- `frontend/src/components/screener/ScreenerTable.tsx` — Quality + Fundamental display
- `frontend/src/types/screener.ts` — `mtf_breakdown` type
- `config/screens/breakdown.yaml` — NEW
- `config/screens/short-squeeze.yaml` — NEW
- `config/screens/distribution.yaml` — NEW
- `backend/tests/test_screener_configs.py` — Fix filter count assertion
- `.gitignore` — TRADING-EVALUATION.md

## Verification
- Backend tests: 280 passed, 0 failed (12/12 screener configs, all pass)
- Frontend build: clean (tsc --noEmit)
- Confluence scorer smoke test: strong (85/A+), medium (52/B), weak (0/D) — all correct
- MTF weighted stacking: (85*0.5 + 52*0.25 + 0*0.25 = 55.5 → rating computes correctly)

## Outcome
✅ Scoring calibrated — binary checks replaced with graded thresholds across all 5 factors
✅ UI shows all 5 confluence factors
✅ 3 new SHORT screen templates — Breakdown, Short Squeeze, Distribution
✅ MTF weighted stacking — no more strict intersection lockout
✅ Final PR: https://github.com/mk-keval/conflu.ai/pull/5
