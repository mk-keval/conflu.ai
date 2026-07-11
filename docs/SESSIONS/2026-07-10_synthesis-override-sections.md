# Synthesis Override Sections — Development Stage, Squeeze, Liquidity

**Date:** 2026-07-10  
**Branch:** feature/ticker-analysis  
**Type:** Feature Enhancement  

## Summary

Added 3 new override/dealbreaker checks to `synthesis.py`:
1. **Development-stage company override** (3a) — intercepts non-operating companies (clinical_stage, pre_revenue, development, distressed, cash_shell) before standard scoring
2. **Extreme short interest squeeze override** (3b) — intercepts when short_interest_pct > 30%
3. **Micro-cap liquidity dealbreaker** — adds dealbreaker when dollar_volume < $100K

## Changes

| File | Change |
|------|--------|
| `synthesis.py` | Added 3 new override/dealbreaker sections; renumbered existing overrides (3a→3f) |

### Override Chain (new ordering)

| # | Override | Trigger |
|---|----------|---------|
| 3a | Development-Stage Company | `lifecycle_stage != "operating"` |
| 3b | Extreme Short Interest / Squeeze | `short_interest_pct > 30` |
| 3c | M&A / Acquisition | `ma_offer_price` in tv_data |
| 3d | Treasury Asset Company | `asset_category == "treasury_asset"` |
| 3e | ETF / CEF / ETN | `instrument_type` in fund types |
| 3f | SPAC | `instrument_type == "spac"` |

### Dealbreakers (new entry between micro-cap and cash burn)

- Micro-cap with critical illiquidity — `dollar_volume < $100K` → -0.5 score penalty

## Verification

- **LSP Diagnostics:** Clean (0 errors)  
- **Tests:** 352 passed, 0 failed  
- **Existing overrides:** All intact (M&A, treasury, ETF/CEF/ETN, SPAC)  
