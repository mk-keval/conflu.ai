# Bug Fixes — Elite Trader Findings

**Date:** 2026-07-09
**Branch:** `feature/ticker-analysis`
**Session:** Bug fixes from elite trader QA validation trust score 32/100

---

## Summary

Fixed all 4 critical/medium bugs identified by elite trader in QA validation round. All 53 relevant tests pass.

---

## Bugs Fixed

### Bug 1 — EMA/SMA Column Name Mismatch (CRITICAL)
- **Root Cause:** TV query selects `EMA20/50/200` but `technical.py` looked for `SMA20/50/200`
- **Fix:** Added fallback: if SMA key not found, try EMA key
- **File:** `backend/app/domain/ticker_analysis/technical.py` (lines 26-28)
- **Impact:** MA alignment was permanently "N/A" for TV data

### Bug 2 — No yfinance RSI/ADX/MACD Fallback (CRITICAL)
- **Root Cause:** When TV data not provided, only close/SMA50/SMA200 were populated from yfinance
- **Fix:** Added `_compute_missing_technicals()` using `pandas_ta` to compute RSI(14), ADX(14), MACD(12,26,9) from 6mo OHLCV history
- **File:** `backend/app/domain/ticker_analysis/orchestrator.py` (new function + wiring)
- **Impact:** RSI/ADX/MACD now populated even without TV data

### Bug 3 — Constant tech_score=-0.08 (MEDIUM)
- **Root Cause:** `weight_count` incremented unconditionally, so N/A indicators diluted score evenly
- **Fix:** Moved `weight_count += 1` inside data-availability guards for all 8 technical sections
- **File:** `backend/app/domain/ticker_analysis/technical.py`
- **Impact:** Score now reflects only indicators that actually had data (before fix: -0.08 for all tickers; after: 0.83 with full data)

### Bug 4 — Zero-Score Module Exclusion (MEDIUM)
- **Root Cause:** Filter `s != 0.0` excluded all zero-scoring modules, including legitimately neutral ones
- **Fix:** Changed to filter by `obj is not None` — only exclude modules that never ran
- **File:** `backend/app/domain/ticker_analysis/synthesis.py` (line 85)
- **Impact:** Neutral technical opinions now contribute to weighted score

---

## Verification

- `technical.analyze()`: score=0.83 with full EMA data (was -0.08), score=-0.68 bearish scenario — correct
- `synthesise()`: correctly includes neutral (score=0.0) technical module
- `pytest backend/tests/test_tv_specialist.py`: 25/25 passed (1 pre-existing exclusion)
- `pytest backend/tests/test_screener_configs.py backend/tests/test_models.py`: 28/28 passed
- LSP diagnostics: clean on all 3 changed files

---

## Files Changed (3)

1. `backend/app/domain/ticker_analysis/technical.py` — EMA fallback + weight_count fix
2. `backend/app/domain/ticker_analysis/orchestrator.py` — `_compute_missing_technicals()` + wiring
3. `backend/app/domain/ticker_analysis/synthesis.py` — zero-score filter fix

---

## Next Steps

1. Restart Docker and re-run ticker analysis on NTAP/PHVS/BBIO to verify scores changed
2. Spawn elite trader re-validation round to see if trust score improves
