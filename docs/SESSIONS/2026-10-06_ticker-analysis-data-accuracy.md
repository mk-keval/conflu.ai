# Session Log: 2026-10-06 — Ticker Analysis Data Accuracy Fixes

**Date:** 2026-10-06
**Branch:** fix/technical-tab-empty (merged to main)
**Starting Commit:** 56889fb (Gate Enforcement Spine Wave-1 complete)

## Prompt
User reported data accuracy issues in ticker analysis:
1. Earnings surprise always showed `None%` for all tickers
2. STRONG BUY verdicts had no entry zone
3. Structural targets returned unrealistic values (R/R ratios too high)
4. No fallback when structural data unavailable
5. Invariant enforcement too strict (downgraded valid setups to WATCH)
6. D/E ratio was bogus for many tickers

## Summary of Changes

### 1. Earnings Module (`backend/app/domain/ticker_analysis/earnings.py`)
- Added optional `symbol` parameter to `analyze()`
- Fetch `earnings_dates` DataFrame from yfinance when symbol provided
- Extract last reported quarter's surprise from `earnings_dates` DataFrame
- Also extract next earnings date and days-until-earnings
- Fall back gracefully to `.info` values if DataFrame fetch fails

### 2. Fundamentals Module (`backend/app/domain/ticker_analysis/fundamentals.py`)
- Added optional `symbol` parameter to `analyze()`
- Fetch `quarterly_balance_sheet` to get reliable "Stockholders Equity"
- Recalculate D/E from actual equity data when available
- Fall back to `.info` totalStockholderEquity when quarterly data unavailable

### 3. Orchestrator (`backend/app/domain/ticker_analysis/orchestrator.py`)
- Pass `symbol` to both `fundamentals.analyze()` and `earnings.analyze()`
- Pass `options_flow` to synthesis for gate positioning data

### 4. Synthesis Module (`backend/app/domain/ticker_analysis/synthesis.py`)
- **STRONG BUY entry zone**: Added "STRONG BUY" to entry zone logic (was only BUY/ACCUMULATE/WATCH)
- **Structural targets cap**: Reduced `max_level` from 2.0x to 1.5x close
- **Fallback targets**: Added percentage-based (8%/15%/25%) and ATR-based (2R/3R/4R) fallback targets when no structural data available
- **Invariant enforcement fallback**: Added Priority 3 heuristic R/R fallback when no structural data available, preventing false WATCH downgrades
- **Gate integration**: Added positioning data (short_interest_pct, institutional_ownership, options_flow_bias) to gate evaluation

## Verification Results

All 771 backend tests pass (excluding E2E tests requiring running API server).

**Earnings surprise now accurate:**
- AAPL: +6.74% (22 days until earnings)
- NVDA: +6.16% (41 days)
- INTC: +94.59% (15 days) — legitimate huge beat
- MSFT: +11.81% (21 days)
- TSLA: -39.15% miss (14 days)

**STRONG BUY now actionable:**
- MSFT: STRONG BUY (c:10) with entry zone 494-523

**R/R ratios now realistic:**
- INTC: 2.39 (ACCUMULATE)
- GOOGL: 3.79 (ACCUMULATE)
- MSFT: 9.19 (STRONG BUY — still high but structural)

**D/E ratios recalculated correctly:**
- NVDA: 0.17 (was 16.97)
- AAPL: 0.78 (was 78.44)
- INTC: 0.58 (was 49.00)
- MSFT: 0.29 (was 29.12)
- TSLA: 0.19 (was 18.37)

**Tests:** All 771 backend tests pass (excluding E2E tests requiring running API server)

## Decision Record
Created D-65: [Ticker Analysis Data Accuracy Fixes](DECISIONS/D-65-ticker-analysis-data-accuracy-fixes.md)

## Files Changed
| File | Changes |
|------|---------|
| `backend/app/domain/ticker_analysis/earnings.py` | Added symbol param, fetch earnings_dates DataFrame, extract surprise/next earnings |
| `backend/app/domain/ticker_analysis/fundamentals.py` | Added symbol param, fetch quarterly_balance_sheet, recalculate D/E |
| `backend/app/domain/ticker_analysis/orchestrator.py` | Pass symbol to modules, pass options_flow to synthesis |
| `backend/app/domain/ticker_analysis/synthesis.py` | STRONG BUY entry zone, structural target cap 1.5x, fallback targets, invariant fallback, gate integration |
| `docs/DECISIONS/D-65-ticker-analysis-data-accuracy-fixes.md` | New decision record |
| `docs/DECISIONS/index.md` | Added D-65 to index |

## Next Steps
- Monitor yfinance API stability for earnings_dates/quarterly_balance_sheet
- Consider adding data source attribution to UI for fallback vs structural targets
- Evaluate if D/E recalculation should run in background job for all symbols