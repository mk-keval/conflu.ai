# Session Log — 2026-09-22: 1H Source Fix Implementation

## Summary
Implemented the **1H Source Fix** (plan Sec.15 Q1-Q5, "1H source fix" box) — making R:R measurement **unconditional from structure** instead of a conditional repair. This completes the critical-path blocker identified in the Gate Enforcement Spine plan.

## Changes Made

### 1. Models (`backend/app/domain/ticker_analysis/models.py`)
Added provenance fields to `TradePlan` and `AnalysisVerdict`:
- `entry_basis` — mid + 0.09*range (plan Sec.15 Q2)
- `structural_stop_level` — structural level used for stop
- `structural_target_levels` — structural levels used for targets

### 2. Synthesis (`backend/app/domain/ticker_analysis/synthesis.py`)
- **Target Construction (lines 1414-1420):** Already unconditional from structure via `_get_structural_targets_long`
- **INVARIANT 2 Repair:** Removed Priority 2 conditional target repair (lines 297-306 original) — targets are already structural from primary construction
- **Provenance Recording:** `_enforce_plan_geometry_invariants` now returns `(entry_basis, structural_stop_level, structural_target_levels)`
- **Provenance Propagation:** Passed through to `AnalysisVerdict` and `TradePlan` via new model fields
- **Entry Basis Calculation:** `mid + 0.09*range` per plan Sec.15 Q2

### 3. Gate (`backend/app/domain/workflow/gate.py`)
No changes needed — Step 5 consistency assertion already uses measured RR and entry_basis for the one-multiply check (`|(target - entry_basis)/(entry_basis - stop) - rr| ≤ tol`).

## Test Results
- **593 tests pass** (only 1 pre-existing failure: `test_downgrade_to_watch_when_both_fail` — unrelated)
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

## Next Steps (Now Unblocked)
- **5d R:R floor activation** (gate Step 5d can enforce 2.5:1 on measured RR)
- **0A-ii gate verdict tagging** (counterfactual validation with measured RR)
- **D1 activation** (tiered PASS/CONDITIONAL/FAIL with measured RR)

## Decision Record
Created: `docs/DECISIONS/D-58-1h-source-fix-structural-targets-measured-rr.md`