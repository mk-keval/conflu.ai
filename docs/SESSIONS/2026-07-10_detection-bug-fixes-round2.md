# Detection Bug Fixes — Round 2

**Date:** 2026-07-10
**Branch:** `feature/ticker-analysis`
**Session:** Fix remaining detection bugs identified by API debug run (MPLT, PDI, IGD, FXLG, TOI)

---

## Summary

Fixed 5 detection bugs in `fundamentals.py` and re-verified all 17 tickers. Launched elite trader session 3 for cross-reference QA validation.

## Changes

### File: `backend/app/domain/ticker_analysis/fundamentals.py`

| Fix | Issue | Symptom | Resolution |
|-----|-------|---------|------------|
| 1 | Clinical-stage biotech miss | MPLT classified as bitcoin treasury | Added `industry` check (Biotechnology) alongside `sector` check |
| 2 | Clinical-stage false positive | TOI ($545M revenue, oncology services) classified as clinical_stage | Tightened to require `has_no_revenue` as primary gate |
| 3 | CEF/ETF detection gap | PDI, IGD classified as equity (yfinance returns quoteType=EQUITY) | Added name-based heuristic: "Fund" + Financial Services → CEF |
| 4 | OTC exchange miss | FXLG classified as foreign exchange | Added "OID" (OTC Markets OTCID) to OTC_EXCHANGES set |
| 5 | Dev-stage PE check | forwardPE exists for pre-profit companies preventing dev-stage detection | Changed from `has_no_pe` (trailing+forward) to `has_no_trailing_pe` (trailing only) |

### Verification

- API tested on all 5 problem tickers: MPLT (clinical_stage✔), PDI (cef✔), IGD (cef✔), FXLG (otc✔), TOI (operating✔)
- Full 17-ticker regression run: all verdicts consistent, no regressions
- Backend tests: 352 pass, TypeScript `tsc --noEmit`: 0 errors, Vite build: succeeds

## Elite Trader Session 3

Launched background task `bg_d045cb3c` with 17-ticker verdict CSV covering:
- Short Squeeze Screener overlaps
- Low-Vol Setup Screener overlaps
- Momentum Breakout Screener overlaps
- Cross-reference QA by institutional trader persona

## Next Steps

- Collect elite trader session 3 findings
- Address any remaining gaps
- Plan next iteration (session 4)
