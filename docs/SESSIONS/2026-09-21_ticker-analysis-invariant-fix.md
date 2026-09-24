# 2026-09-21: Fix Invariant 2 Watch Promotion Logic

## Summary
Fixed a bug in the `_enforce_plan_geometry_invariants` function where WATCH plans due to RR invariant failure were incorrectly being promoted to ACCUMULATE. This caused the test `test_downgrade_to_watch_when_both_fail` to fail.

## Changes Made
- Modified the PROMOTION logic in `backend/app/domain/ticker_analysis/synthesis.py` (lines 247-259)
- Added check to only promote WATCH to ACCUMULATE when the WATCH status is NOT due to RR invariant failure
- This ensures that when both structural stop extension and target extension fail to achieve RR >= 2.0, the plan correctly remains in WATCH status

## Test Results
- Fixed: `tests/test_synthesis_geometry.py::TestInvariant2RiskReward::test_downgrade_to_watch_when_both_fail` now PASSES
- All other geometry tests continue to PASS (19/20 passing, 1 fixed)

## Related Work
- Builds upon D-56: Gate Enforcement Spine — Wave-1 Completion (1E/2B/2C/2D/1D/2E) + 0A-i Control Study
- Supports proper gate enforcement by ensuring WATCH status is maintained when RR invariants cannot be satisfied
- 0A-ii gate verdict tagging was previously verified as implemented (records gate_verdict and gate_failed_step)
- 0A-ii remains blocked until 1H (requires D-52 source fix per D-56)

## Verification
- Ran full test suite for synthesis geometry - all tests pass
- No regressions detected in related functionality
- Decision logged per auto-documentation rule