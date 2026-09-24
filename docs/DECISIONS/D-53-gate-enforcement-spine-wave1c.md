# D-53: Gate Enforcement Spine — Wave-1C Backend Gate Evaluator + Verdict Wiring

Date: 2026-09-18
Status: Accepted (Wave-1C implementation; journal/sizing/exit slices remain reserved under this spine)

## Context

The approved gate-enforcement spine plan (`.sisyphus/plans/gate-enforcement-spine.md`, Sec. 1C) requires the backend to attach an honest 7-step gate result to every `AnalysisVerdict`, evaluated after all final conviction mutations. Prior constraints established by D-51 (REV7) and the plan:

- The gate contract is `gate: GateResult | None` on `AnalysisVerdict`, evaluated after final conviction adjustments (D-55/plan Sec. 1C).
- No false-PASS stub, no unrelated validation-pipeline enum (D-55). The workflow evaluator must exist before verdict wiring.
- Gate Step 5 runs with 5a/5b/5c live; the 2.5:1 R:R floor (5d) defers to plan phase 1H (D-51, REV7) — the deferred item is reserved separately as D-52.
- Wave-1 gate is a skeleton with honest CONDITIONAL degradation on missing inputs; steps 1-4, 6, 7 evaluated; Step 5 = consistency check.
- D-55 zero-dollar-volume preservation: `avg_daily_volume_usd_calc` of 0.0 must remain evidence of illiquidity (lightning-fast FAIL for the Liquidity step), and the $100K critical-illiquidity scoring threshold is separate from the gate's $10M workflow liquidity rule.
- GitNexus index: `synthesise` impact LOW; `evaluate_stop_distance` was not in the graph (only caller: `test_synthesis_geometry.py:32` via re-import — moving it preserves the call).

## Decision

1. **New backend module `backend/app/domain/workflow/gate.py`** is the single source of truth for the backend 7-step gate (Wave-1). It ports the frontend `gate.ts` semantics (teacher-first philosophy, CONDITIONAL degradation on missing data) into the backend:
   - `GateInput` dataclass carries all step inputs.
   - `evaluate_stop_distance(entry, stop, max_stop_distance_pct=None)` moved here from `synthesis.py` (5a/5b); returns CONDITIONAL "policy not configured" when ceiling is None (D-8 not selected — synthesis wires it unset).
   - Step evaluators: Liquidity ($10M ADV workflow floor; < $5M half-floor is a hard FAIL including zero-ADV), Structure (daily/weekly MA alignment → CONDITIONAL when missing), Positioning (Wave-1 CONDITIONAL, not wired), Catalyst (bullish PASS / bearish FAIL / neutral-missing CONDITIONAL), Risk/Reward (5a/5b stop-distance + 5c R:R consistency assertion within ±0.35; 5d floor NOT enforced), Portfolio Fit (Wave-1 CONDITIONAL), Conviction (≥7 PASS, ≥4 CONDITIONAL, else FAIL; score clamped 0-10).
   - `compute_gate(steps) -> Literal["PASS","FAIL","CONDITIONAL"]`: any hard FAIL → FAIL, else any CONDITIONAL → CONDITIONAL, else PASS.
   - `evaluate_gate(input) -> GateResult` builds the 7 steps in plan order, records `data_gaps` = names of CONDITIONAL steps, `evaluated_at` UTC ISO.

2. **`synthesis.py` is wired at the single verdict construction site**: gate evaluation runs after the D-44 conviction-cap block (the last conviction mutation), feeding `build_gate_input(...)` from `tv_data` (`avg_daily_volume_usd_calc`, `relative_volume_10d_calc`, `catalyst_bias_direction`), `technical`/`technical_weekly` MA alignment, price/entry zone/stop/targets/rr, and final conviction. `evaluate_stop_distance` is re-exported from gate.py so the existing synthesis geometry test keeps its `synthesis.evaluate_stop_distance` import.

3. **Typing**: `AnalysisVerdict.gate` remains `GateResult | None` (additive, `extra="forbid"`-safe — no construction-site breakage). The runtime contract is strengthened: `synthesise()` now always populates it.

## Consequences

- Every `AnalysisVerdict` now carries a typed, honest gate verdict — the backend decider the plan's enforcement spine requires. No step can false-PASS in Wave-1.
- Advancing to a full-enforcement output (rejection paths, journal `gate_verdict`/`gate_failed_step` columns, Portfolio Fit wiring, R:R 5d floor) remains future work under this spine (slices 1A/1D/2A-2E and phase 1H/D-52).
- `data_gaps` names the teaching opportunities (exactly the CONDITIONAL steps) — the learning slice (D-54, pending) can render `gate_failed_step`/`data_gaps` plain-English.
- Moving `evaluate_stop_distance` changes no public behavior: verified by the retained `test_synthesis_geometry` suite and gitnexus (LOW).

## Verification

- New `backend/tests/test_gate.py`: 7 tests — verdict always carries a gate; gate reads post-binary-risk conviction (no pre-cap leakage); honest CONDITIONAL is not a false PASS; liquidity PASS above $25M ADV; zero-ADV is a hard Liquidity FAIL (verdict overall FAIL); catalyst bias drives the Catalyst step (bullish PASS / bearish FAIL); 5d R:R floor still deferred.
- Related suites: `test_synthesis_geometry` + `test_synthesis_momentum_regime` + `test_technical_orchestrator_integration` + `test_narration` + `test_gate` = **76 passed in 3.51s**.
- LSP clean on `gate.py`, `synthesis.py`, `test_gate.py` (and pre-existing orchestrator.py warnings are out of scope, unchanged).
- No commits created. No routes/architecture changed. No delegation used (user instructed self-completion after prior agent 429 failures).

See [session log](../SESSIONS/2026-09-18_gate-wave1c-verdict-wiring.md).