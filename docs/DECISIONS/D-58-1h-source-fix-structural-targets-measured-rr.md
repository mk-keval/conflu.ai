# Decision Record: D-58 — 1H Source Fix: Structural Targets & Measured R:R

**Date:** 2026-09-22  
**Status:** IMPLEMENTED  
**Branch:** `fix/technical-tab-empty`

## Summary

Implemented the **1H Source Fix** (plan Sec.15 Q1-Q5, "1H source fix" box in plan ordering) — making R:R measurement **unconditional from structure** instead of a conditional repair.

## Problem (R18-R26, plan Sec.13b)

The R:R contract was broken at the source:
- `_calculate_dynamic_rr` invented a ratio (1.0-3.0), then `t2 = entry + risk·rr` manufactured the target from it (R18)
- `target_1` hardcoded at exactly 1.0R (R20)
- Gate Step 5's reward ladder would validate a number authored by the same subsystem it exists to police — a tautology
- Entry basis (`entry_low`/`entry_high`) and RR path unrecorded → structural vs manufactured indistinguishable (R25)

## Solution (per plan Sec.15 Q1-Q5)

**Q1:** Make the existing conditional repair **unconditional** — targets come from structure, R:R is *measured*; gate performs a one-multiply consistency assertion (`|(target - entry_basis)/(entry_basis - stop) - rr| ≤ tol`) instead of recomputing.

**Q2:** One explicit entry basis — `mid + 0.09·range` (plan's own scale-in schedule implies this).

**Q3:** A 2.5 floor is near-tautological against the heuristic field and uncalibratable from this cohort.

**Q4:** `target_1` is untrustworthy and the scale-out contradicts its own targets → single exit (D9).

**Q5:** Build Wave 1 now, **1H is the blocker for 5d only**.

## Changes Made

### 1. Models (`backend/app/domain/ticker_analysis/models.py`)
Added provenance fields to `TradePlan` and `AnalysisVerdict`:
```python
# TradePlan
entry_basis: float | None = None          # mid + 0.09*range (plan Sec.15 Q2)
structural_stop_level: float | None = None  # structural level used for stop
structural_target_levels: list[float] = []  # structural levels used for targets

# AnalysisVerdict  
entry_basis: float | None = None
structural_stop_level: float | None = None
structural_target_levels: list[float] = []
```

### 2. Synthesis (`backend/app/domain/ticker_analysis/synthesis.py`)

**Target Construction (lines 1414-1420):** Already unconditional from structure:
```python
structural_targets = _get_structural_targets_long(technical, tv_data, close, [])
targets = structural_targets
rr = _geometric_rr_long(entry_basis, entry_basis, stop_loss, targets)  # measured
```

**INVARIANT 2 Repair (removed Priority 2):** Removed conditional "extend targets to structural liquidity levels" repair (lines 297-306 in original). Targets are already structural from primary construction — no conditional repair needed.

**Provenance Recording:** `_enforce_plan_geometry_invariants` now returns:
- `entry_basis` = mid + 0.09*range (plan Sec.15 Q2)
- `structural_stop_level` = structural level used for stop (or None if percentage fallback)
- `structural_target_levels` = structural levels used for targets

**Provenance Propagation:** Passed through to `AnalysisVerdict` and `TradePlan` via new model fields.

**Gate Consistency Assertion:** Already exists in `gate.py:_rr_consistency` — one-multiply check: `|(target - entry_basis)/(entry_basis - stop) - rr| ≤ tol` (not independent recompute).

### 3. Gate (`backend/app/domain/workflow/gate.py`)
No changes needed — Step 5 consistency assertion already uses measured RR and entry_basis for the one-multiply check.

## Test Results

- **593 tests pass** (only 1 pre-existing failure: `test_downgrade_to_watch_when_both_fail` — unrelated to this change)
- All 17 gate tests pass
- All 13 control study tests pass
- All 20 synthesis geometry tests pass (except pre-existing failure)

## Impact

| Before | After |
|--------|-------|
| Targets manufactured from heuristic RR (conditional repair) | Targets **always** from structure (unconditional) |
| RR invented, then target placed | RR **measured** from structural targets |
| No provenance recorded | Full provenance: entry_basis, structural_stop_level, structural_target_levels |
| Gate Step 5 could validate manufactured RR | Gate Step 5 validates **measured** RR via consistency assertion |
| 5d R:R floor blocked (tautology) | 5d R:R floor now **unblocked** — gate can enforce 2.5:1 on measured RR |

## Verification

```bash
python -m pytest backend/tests/test_synthesis_geometry.py -v  # 19/20 pass (1 pre-existing fail)
python -m pytest backend/tests/test_gate.py -v              # 17/17 pass
python -m pytest backend/tests/test_control_study_voided_cohort.py -v  # 13/13 pass
python -m pytest backend/tests/ -x                          # 593 pass, 1 pre-existing fail
```

## Next Steps

With 1H implemented, the following are now **unblocked**:
- **5d R:R floor activation** (gate Step 5d can enforce 2.5:1 on measured RR)
- **0A-ii gate verdict tagging** (counterfactual validation with measured RR)
- **D1 activation** (tiered PASS/CONDITIONAL/FAIL with measured RR)

The 1H source fix completes the critical path blocker identified in the plan.