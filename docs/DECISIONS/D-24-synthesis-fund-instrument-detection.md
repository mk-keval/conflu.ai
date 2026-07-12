# D-24: Fund Instrument Detection Framework

**Status:** Accepted  
**Date:** 2026-07-10

## Context

The ticker analysis engine deployed `instrument_type` detection via `fundamentals.py` and synthesis overrides via `synthesis.py`. Elite trader session 5 revealed 7 P0 gaps where common instrument types (REIT, BDC, MLP, preferred stock, mining royalty, deSPAC, biotech milestone revenue) and 3 P1/P2 gaps (crypto miner misclassification, expert market OTC, dead code, extreme cash burn pre-profit, squeeze override bleed) were not handled.

## Decision

### Detection Architecture

Introduce a layered detection framework in `fundamentals.py` with explicit priority:

1. **quoteType-driven** (highest priority): Preferred stock via `quoteType="PREFERRED"`, CEF through name heuristic executed before `instrument_type` initialization
2. **Sector/industry-driven**: REIT (sector=Real Estate or industry~REIT), BDC (legalType + name/business summary)
3. **Name/business-driven**: MLP (name keywords + Energy sector), mining royalty (keywords + sector), crypto miner (mining + BTC keywords)
4. **Revenue/financial-driven**: DeSPAC (revenue + non-SPAC industry), biotech milestone (partnership revenue + negative margins), >$100M pre-profit (extreme cash burn)

### Synthesis Layer

Fund instruments (preferred, CEF, ETF, mutual_fund) funnel into a unified `is_fund` gate that blocks:
- Squeeze override (misattributed short squeeze signals)
- Wrong lifecycle stages

### Risk Layer

New instrument types get capped position sizes:
- BDC: 10% max
- Preferred: 10% max, exempt from micro-cap cap

## Consequences

### Positive
- **Comprehensive coverage**: All major fund/special instrument types detected before downstream processing
- **Isolation by layer**: Each new type adds a narrow detection function without touching the main flow
- **No API breaking changes**: All new values extend existing enum-like string fields
- **Full regression**: 404/404 existing tests pass, 52/52 ticker classification tests pass

### Negative
- **Pattern matching dependency**: REIT/MLP/BDC detection relies on sector/industry strings from yfinance which can change upstream
- **Name heuristics fragile**: MLP and mining royalty keyword matching could false-positive on non-standard names

### Risk Assessment
- **HIGH**: Detection failures result in wrong verdicts (equity treated as fund or vice versa)
- **Mitigated**: 11 new synthetic tests cover each detection path; name/business heuristics bounded by secondary sector/legalType checks
