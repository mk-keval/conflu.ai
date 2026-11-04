# D-57: Fix Invariant 2 Watch Promotion Logic

## Problem
The `_enforce_plan_geometry_invariants` function was incorrectly promoting WATCH plans to ACCUMULATE even when the WATCH status was due to RR invariant failure (Invariant 2). Specifically, when both structural stop extension and target extension failed to achieve RR >= 2.0, the function would:
1. Correctly downgrade to WATCH with RR failure reason
2. Then immediately promote that WATCH back to ACCUMULATE in the PROMOTION section

This caused the test `test_downgrade_to_watch_when_both_fail` to fail, expecting WATCH but getting ACCUMULATE.

## Solution
Modified the PROMOTION logic in `_enforce_plan_geometry_invariants` to only promote WATCH to ACCUMULATE when the WATCH status is NOT due to RR invariant failure.

Specifically:
- Added check: `is_due_to_rr_failure = any("R/R invariant failed" in f for f in dealbreakers)`
- Only promote to ACCUMULATE if `not is_due_to_rr_failure`

This ensures that when Invariant 2 fails (both structural stop and target extension fail to achieve RR >= 2.0), the plan remains in WATCH status with appropriate reasoning.

## Files Changed
- `backend/app/domain/ticker_analysis/synthesis.py` - Lines 247-259 (PROMOTION section)

## Test Impact
- Fixes: `tests/test_synthesis_geometry.py::TestInvariant2RiskReward::test_downgrade_to_watch_when_both_fail`
- All other geometry tests continue to pass

## Related Decisions
- D-56: Gate Enforcement Spine — Wave-1 Completion (1E/2B/2C/2D/1D/2E) + 0A-i Control Study
- This fix supports the gate enforcement logic by ensuring proper WATCH status when RR invariants cannot be satisfied