# Session Log: 2026-09-22 — 0A-ii Control Study Re-run & D1 Tiered Sizing

**Date:** 2026-09-22  
**Branch:** `fix/technical-tab-empty`  
**Related Decision:** D-59

## Summary

Completed the 0A-ii Control Study re-run with the 2.5:1 R:R floor now active (post D-58 1H Source Fix), and implemented D1 Tiered Sizing in the gate.

## Control Study Re-run (0A-ii)

**Command:** `python backend/scripts/control_study_voided_cohort.py --backfill-exits`

| Metric | Value |
|--------|-------|
| Cohort size | 31 rows from 7 files (archive, read-only) |
| Manufactured detector | 4 manufactured, 0 structural, 27 indeterminate |
| Gate verdict tagging | **0 PASS, 0 FAIL, 31 CONDITIONAL** |
| Exit replay (OHLCV) | 18 resolved, 13 unresolvable |
| Win rate | 77.8% |
| Expectancy | **+1.093R** |
| Profit factor | 5.683 |

**Key Finding:** All 31 rows returned **CONDITIONAL** at the Liquidity step because the historical bypass cohort lacks `avg_daily_volume_usd` data. This is a **data limitation**, not a gate bug — real validation will occur when live TV data flows through the gate.

## D1 Tiered Sizing Implementation

### Gate Logic Change (`backend/app/domain/workflow/gate.py`)

Added D1 tier in `evaluate_risk_reward()` — three-tier R:R ladder:

| Tier | R:R Requirement | r1 Requirement | Gate Verdict | Sizing |
|------|-----------------|----------------|--------------|--------|
| **PASS** | ≥ 2.5 | N/A | PASS | 100% |
| **D1 CONDITIONAL** | ≥ 2.0 | **≥ 1.0** | CONDITIONAL | **50%** (half-size) |
| **FAIL** | < 2.0 | N/A | FAIL | 0% |

**Critical:** D1 tier requires **both** R/R ≥ 2.0 **AND** r1 ≥ 1.0. This prevents accepting setups where the first target is too close to entry.

### Sizing Integration (`backend/app/domain/workflow/sizing.py`)

Already had `CONDITIONAL_HALVING = 0.5` (line 32) — when gate verdict is CONDITIONAL, position size is halved. The paper trade script (`paper_trade_from_brief.py` line 307) applies this automatically.

## Test Coverage Added

New tests in `backend/tests/test_gate.py`:
- `test_rr_floor_active_enforces_min_2_5` — R/R=2.0, r1=2.0 → CONDITIONAL (D1 tier)
- `test_d1_tier_requires_r1_ge_1_0` — R/R=2.2, r1=0.5 → FAIL (r1 < 1.0)
- `test_d1_tier_conditional_at_rr_2_0` — R/R=2.0, r1=1.0 → CONDITIONAL (D1 tier)
- `test_full_pass_tier_at_rr_2_5` — R/R=2.5 → PASS

**All 834 backend tests pass.**

## Files Changed

| File | Change |
|------|--------|
| `backend/app/domain/workflow/gate.py` | Added D1 tier logic in `evaluate_risk_reward()` |
| `backend/tests/test_gate.py` | Added 4 D1 tier test cases |
| `docs/DECISIONS/D-59-0a-ii-control-study-gate-verdict-tagging.md` | New decision record |
| `docs/DECISIONS/index.md` | Updated with D-59, D-58, D-57 |
| `docs/index.md` | Updated main docs index |

## Next Steps

1. **Live Paper Trading Validation** (Daily Touchpoints):
   - Pre-market: `python backend/scripts/paper_trade_from_brief.py --apply`
   - After-close: `python backend/scripts/paper_trade_from_brief.py --sync-exits --apply`

2. **Monitor D1 tier outcomes** — Track win rate / expectancy for CONDITIONAL (half-size) vs PASS (full-size) trades in the paper journal.