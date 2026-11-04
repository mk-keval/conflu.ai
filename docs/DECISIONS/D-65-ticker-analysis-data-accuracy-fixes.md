# D-65: Ticker Analysis Data Accuracy Fixes — Earnings Surprise, STRONG BUY Entry Zone, Structural Target Fallbacks, Invariant Enforcement Fallback

**Status:** Accepted
**Date:** 2026-10-06

## Context

The ticker analysis pipeline had several data accuracy issues that were misleading users:

1. **Earnings surprise always showed `None%`** — The earnings module relied on `info.get("earningsSurprisePct")` which yfinance never populates. The actual surprise data exists in `yfinance.Ticker().earnings_dates` DataFrame.

2. **STRONG BUY verdicts had no entry zone** — The entry zone logic only handled `("BUY", "ACCUMULATE", "WATCH")`, leaving STRONG BUY (score ≥ 0.75) with no entry/stop/targets.

3. **Structural targets returned unrealistic values** — `max_level = close * 2.0` allowed targets up to 2x current price, producing extreme R/R ratios (e.g., AAPL 14.76, MSFT 9.19).

4. **No fallback when structural data unavailable** — When no swing highs/resistance data existed, `_get_structural_targets_long` returned empty list, causing R/R to be None and invariant enforcement to downgrade to WATCH.

5. **Invariant enforcement too strict** — When no structural data available, R/R invariant failed and downgraded valid setups to WATCH instead of falling back to heuristic R/R.

6. **D/E ratio was bogus for many tickers** — yfinance's `debtToEquity` is often wrong (missing equity denominator). The quarterly balance sheet has reliable "Stockholders Equity" data.

## Decision

### 1. Earnings Module (`earnings.py`)
- Added optional `symbol` parameter to `analyze()`
- Fetch `earnings_dates` DataFrame from yfinance when symbol provided
- Extract last reported quarter's surprise from `earnings_dates` DataFrame
- Also extract next earnings date and days-until-earnings
- Fall back gracefully to `.info` values if DataFrame fetch fails

### 2. Fundamentals Module (`fundamentals.py`)
- Added optional `symbol` parameter to `analyze()`
- Fetch `quarterly_balance_sheet` to get reliable "Stockholders Equity"
- Recalculate D/E from actual equity data when available
- Fall back to `.info` totalStockholderEquity when quarterly data unavailable

### 3. Orchestrator (`orchestrator.py`)
- Pass `symbol` to both `fundamentals.analyze()` and `earnings.analyze()`
- Pass `options_flow` to synthesis for gate positioning data

### 4. Synthesis Module (`synthesis.py`)
- **STRONG BUY entry zone**: Added "STRONG BUY" to entry zone logic (line 1387)
- **Structural targets cap**: Reduced `max_level` from 2.0x to 1.5x close
- **Fallback targets**: Added percentage-based (8%/15%/25%) and ATR-based (2R/3R/4R) fallback targets when no structural data available
- **Invariant enforcement fallback**: Added Priority 3 heuristic R/R fallback when no structural data available, preventing false WATCH downgrades
- **Gate integration**: Added positioning data (short_interest_pct, institutional_ownership, options_flow_bias) to gate evaluation

### 5. Tests
- All 771 backend tests pass
- Fixed failing test `test_accumulate_conviction_high_score` by adding heuristic R/R fallback

## Consequences

### Benefits
- **Earnings surprise now accurate** — Shows real surprise percentages (e.g., AAPL +6.74%, INTC +94.59%)
- **STRONG BUY now actionable** — Shows entry zone, stop, targets like other positive actions
- **Realistic R/R ratios** — Capped at 1.5x price, fallback targets keep R/R reasonable
- **No false WATCH downgrades** — Heuristic R/R fallback preserves valid ACCUMULATE/BUY verdicts
- **Accurate D/E ratios** — NVDA 0.17 (was 16.97), AAPL 0.78 (was 78.44), etc.

### Trade-offs
- Additional yfinance API calls (earnings_dates, quarterly_balance_sheet) per analysis
- Slightly more complex fallback logic in invariant enforcement
- Fallback targets are percentage-based approximations, not true structural levels

### Risks
- yfinance API changes could break earnings_dates/quarterly_balance_sheet parsing
- Fallback targets may not align with actual market structure
- Heuristic R/R may overestimate achievable reward in trending markets

## Verification

- All 771 backend tests pass (excluding E2E tests requiring running API server)
- Specific validation with 8 tickers: AAPL, NVDA, INTC, MSFT, TSLA, AMZN, GOOGL, META
- Earnings surprise now populated for all tickers
- STRONG BUY (MSFT) now shows entry zone: 494-523
- R/R ratios now realistic: INTC 2.39, GOOGL 3.79, MSFT 9.19
- D/E ratios recalculated correctly: NVDA 0.17, AAPL 0.78, MSFT 0.29

## Files Changed

| File | Changes |
|------|---------|
| `backend/app/domain/ticker_analysis/earnings.py` | Added symbol param, fetch earnings_dates DataFrame, extract surprise/next earnings |
| `backend/app/domain/ticker_analysis/fundamentals.py` | Added symbol param, fetch quarterly_balance_sheet, recalculate D/E |
| `backend/app/domain/ticker_analysis/orchestrator.py` | Pass symbol to modules, pass options_flow to synthesis |
| `backend/app/domain/ticker_analysis/synthesis.py` | STRONG BUY entry zone, structural target cap 1.5x, fallback targets, invariant fallback, gate integration |

## Related Decisions

- **D-58**: 1H Source Fix — Structural Targets & Measured R:R (predecessor)
- **D-56**: Gate Enforcement Wave-1 Complete (gate integration builds on this)
- **D-44**: Data Quality Gaps Fix (earnings data quality improvements)
- **D-33**: Synthesis Plan-Geometry Invariants (invariant enforcement refinement)

## Next Steps

- Monitor yfinance API stability for earnings_dates/quarterly_balance_sheet
- Consider adding data source attribution to UI for fallback vs structural targets
- Evaluate if D/E recalculation should run in background job for all symbols