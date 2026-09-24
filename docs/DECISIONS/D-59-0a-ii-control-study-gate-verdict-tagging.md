# Decision Record: D-59 — 0A-ii Control Study Re-run & D1 Tiered Sizing Activation

**Date:** 2026-09-22  
**Status:** IMPLEMENTED  
**Branch:** `fix/technical-tab-empty`

## Summary

Re-ran the **0A-ii Control Study** with the 2.5:1 R:R floor now active (post D-58 1H Source Fix), and implemented **D1 Tiered Sizing** in the gate — adding a CONDITIONAL tier at R/R ≥ 2.0 with r1 ≥ 1.0 (half-size) between the existing FAIL (<2.0) and PASS (≥2.5) tiers.

## Control Study Re-run Results (0A-ii)

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

The +1.093R expectancy on the CONDITIONAL cohort (which would trade at half-size via D1 tier) is directionally positive but n=31 is far below statistical significance.

## D1 Tiered Sizing Implementation

### Gate Logic Change (`backend/app/domain/workflow/gate.py`)

Added D1 tier in `evaluate_risk_reward()` (lines ~330-380):

```python
# 5d floor: enforce R/R >= 2.5 for PASS
# D1 tier: CONDITIONAL at 2.0:1 with r1 >= 1.0 (half size)
if rr_to_check is not None:
    if rr_to_check >= RISK_REWARD_PASS:           # 2.5
        sub.append(GateStepResult(passed=True, ...))  # FULL PASS
    elif rr_to_check >= RISK_REWARD_CONDITIONAL:  # 2.0
        # Check r1 >= 1.0 (first target gives at least 1R)
        if entry and stop and targets:
            risk = entry - stop
            r1 = (targets[0] - entry) / risk
            if r1 >= 1.0:
                sub.append(GateStepResult(passed=False, conditional=True,
                    note=f"D1 tier: R/R {rr:.2f} >= 2.0 with r1={r1:.2f} >= 1.0 — half-size CONDITIONAL"))
            else:
                sub.append(GateStepResult(passed=False, conditional=False,
                    note=f"R/R {rr:.2f} >= 2.0 but r1={r1:.2f} < 1.0 — D1 tier not met"))
    else:
        sub.append(GateStepResult(passed=False, conditional=False,
            note=f"R/R floor not met: {rr:.2f} < 2.5"))
```

### Sizing Integration (`backend/app/domain/workflow/sizing.py`)

Already had `CONDITIONAL_HALVING = 0.5` (line 32) — when gate verdict is CONDITIONAL, position size is halved. The paper trade script (`paper_trade_from_brief.py` line 307) applies this automatically.

### Three-Tier R:R Ladder

| Tier | R:R Requirement | r1 Requirement | Gate Verdict | Sizing |
|------|-----------------|----------------|--------------|--------|
| **PASS** | ≥ 2.5 | N/A | PASS | 100% |
| **D1 CONDITIONAL** | ≥ 2.0 | **≥ 1.0** | CONDITIONAL | **50%** (half-size) |
| **FAIL** | < 2.0 | N/A | FAIL | 0% (blocked) |

**Critical:** D1 tier requires **both** R/R ≥ 2.0 **AND** r1 ≥ 1.0. This prevents accepting setups where the first target is too close to entry (e.g., R/R=2.2 but T1 only gives 0.4R).

## Test Coverage Added

New tests in `backend/tests/test_gate.py`:

| Test | Scenario | Expected |
|------|----------|----------|
| `test_rr_floor_active_enforces_min_2_5` | R/R=2.0, r1=2.0 | CONDITIONAL (D1 tier) |
| `test_d1_tier_requires_r1_ge_1_0` | R/R=2.2, r1=0.5 | FAIL (r1 < 1.0) |
| `test_d1_tier_conditional_at_rr_2_0` | R/R=2.0, r1=1.0 | CONDITIONAL (D1 tier) |
| `test_full_pass_tier_at_rr_2_5` | R/R=2.5 | PASS |

All **834 backend tests pass** (including 4 new D1 tier tests).

## Verification Commands

```bash
# Backend tests (all pass)
python -m pytest backend/tests/ -x -q

# Gate-specific tests
python -m pytest backend/tests/test_gate.py -v

# Frontend typecheck
cd frontend && npm run typegen && npx tsc --noEmit

# Control study re-run
python backend/scripts/control_study_voided_cohort.py --backfill-exits

# Manual D1 gate test
python -c "
from backend.app.domain.workflow.gate import evaluate_gate, build_gate_input
# D1 tier: R/R=2.2, r1=1.5
inp = build_gate_input(symbol='TEST', avg_daily_volume_usd=50_000_000, 
    daily_trend='bullish', weekly_trend='bullish', price=100, entry_low=99, 
    entry_high=101, stop_loss=95, targets=[105, 110], risk_reward=2.2, 
    conviction=7, catalyst_bias='bullish', sector='Tech')
result = evaluate_gate(inp)
print(f'Overall: {result.overall}')  # Should be CONDITIONAL
for s in result.steps:
    status = 'PASS' if s.passed and not s.conditional else 'CONDITIONAL' if s.conditional else 'FAIL'
    print(f'  {s.name}: {status} - {s.note[:80]}')
"
```

## Next Steps

1. **Live Paper Trading Validation** (Daily Touchpoints):
   - Pre-market: `python backend/scripts/paper_trade_from_brief.py --apply`
   - After-close: `python backend/scripts/paper_trade_from_brief.py --sync-exits --apply`

2. **Frontend Gate Renderer (D4)** — Update `frontend/src/workflow/gate.ts` to render three-tier verdict (PASS/CONDITIONAL/FAIL) with D1 tier explanation.

3. **Monitor D1 tier outcomes** — Track win rate / expectancy for CONDITIONAL (half-size) vs PASS (full-size) trades in the paper journal.

## Files Changed

| File | Change |
|------|--------|
| `backend/app/domain/workflow/gate.py` | Added D1 tier logic in `evaluate_risk_reward()` |
| `backend/tests/test_gate.py` | Added 4 D1 tier test cases |
| `docs/SESSIONS/2026-09-18_ungated-cohort-control-study.md` | Control study report (auto-generated) |

## Related Decisions

- **D-58** (1H Source Fix) — Unblocked measured R:R for gate enforcement
- **D-56** (Gate Enforcement Wave-1 Complete) — Established 7-step gate spine
- **D-55** (Mentor Liquidity) — Single liquidity check, zero dollar volume preserved