# Session Log — Gate Wave-1C: Backend Gate Evaluator + Verdict Wiring

**Date:** 2026-09-18 · **Branch:** `fix/technical-tab-empty` · **Type:** Wave-1C implementation (application code)

**Related:** `docs/DECISIONS/D-53-gate-enforcement-spine-wave1c.md`, `docs/SESSIONS/2026-09-16_gate-enforcement-spine-planning.md`

---

## Context

Continuation of the gate-enforcement spine. The planning passes (2026-09-16) and the D-55 liquidity correction (2026-09-17) established the constraints. This session implements **Wave-1C exactly as D-55's limit note demanded**: *"The planned workflow evaluator must exist before verdict wiring can be completed."* Both halves now exist.

Wave-1C scope (plan Sec. 1C): `gate: GateResult | None` on `AnalysisVerdict`, evaluated after final conviction mutations — Step 5 with 5a/5b/5c live, the 2.5:1 R:R floor (5d) deferred to 1H/D-52, teach-first CONDITIONAL degradation, no PASS stub, no validation-pipeline enum.

## Action taken

All work performed directly in the main session. No delegation: the user's standing instruction after repeated agent timeouts/429s ("dont assign task to other model, you can finish it yourself") forbade sub-agents, and the window was small.

### 1. Pre-recon (read-only verification)

| Claim | Verified |
|---|---|
| `tv_data["avg_daily_volume_usd_calc"]` exists | Yes — `technical.py:429` computes it; `orchestrator.py:565-566` merges it into `tv_data` |
| `tv_data["relative_volume_10d_calc"]` exists | Yes — `technical.py:415` |
| `tv_data["catalyst_bias_direction"]` exists | Yes — `orchestrator.py:689-692`; `_analyze_catalyst_bias` at `:258`; values bullish/bearish/neutral |
| `GateStepResult` / `GateResult` / `AnalysisVerdict.gate` present | Yes — `models.py:242-260, 267` (pre-existing from planning phase) |
| `evaluate_stop_distance` callers | Only `test_synthesis_geometry.py:32` via `synthesis.evaluate_stop_distance` — a re-export preserves it |
| Frontend gate semantics | Read `frontend/src/workflow/gate.ts` — thresholds + CONDITIONAL degrades on missing data |
| GitNexus impact | `synthesise`: LOW risk. `evaluate_stop_distance`: not in graph (moved function is safe; only caller is the test import) |

### 2. Created `backend/app/domain/workflow/gate.py` (new module)

The backend gate source of truth (frontend `gate.ts` semantics ported to Python):

- **Constants**: `LIQUIDITY_MIN_AVG_DAILY_USD = 10_000_000`, `RISK_REWARD_PASS = 2.5`, `RISK_REWARD_CONDITIONAL = 2.0`, `CONVICTION_HIGH = 7`, `CONVICTION_LOW = 4`, `RR_CONSISTENCY_TOL = 0.35`.
- **`GATE_STEPS`** — the 7 teach-first questions in plan order: Liquidity, Structure, Positioning, Catalyst, Risk/Reward, Portfolio Fit, Conviction.
- **`GateInput` dataclass** — all step inputs (ADV, volume ratio, daily/weekly MA alignment, price, entry zone, stop, targets, rr, conviction, catalyst bias).
- **`evaluate_stop_distance(entry, stop, max_stop_distance_pct=None)`** — moved from `synthesis.py` (5a/5b). Returns CONDITIONAL "policy not configured" when the ceiling is `None` (D-8 not selected; synthesis wires it unset — honest).
- **Step evaluators**:
  - `evaluate_liquidity` — $10M workflow floor; ADV < $5M half-floor is a hard FAIL (including **zero-ADV, per D-55**); missing data → CONDITIONAL.
  - `evaluate_structure` — daily + weekly MA alignment; missing either → CONDITIONAL.
  - `evaluate_positioning` — Wave-1: CONDITIONAL "not wired yet", never a PASS.
  - `evaluate_catalyst` — bullish → PASS, bearish → FAIL, neutral/missing → CONDITIONAL.
  - `_rr_consistency` (5c) — `|(last_target − entry_basis)/(entry_basis − stop) − rr| ≤ 0.35`.
  - `evaluate_risk_reward` — 5a/5b via `evaluate_stop_distance`, 5c via `_rr_consistency`; **5d floor not enforced** (deferred).
  - `evaluate_portfolio_fit` — Wave-1: CONDITIONAL, never a PASS.
  - `evaluate_conviction` — ≥7 PASS, ≥4 CONDITIONAL, <4 FAIL; score clamped 0-10.
- **`compute_gate(steps)`** → `Literal["PASS","FAIL","CONDITIONAL"]`: any hard FAIL → FAIL; else any CONDITIONAL → CONDITIONAL; else PASS.
- **`evaluate_gate(input)`** → `GateResult`: runs all 7 steps in order, clamps conviction, records `data_gaps` = names of CONDITIONAL steps (the teaching opportunities), `evaluated_at` = UTC ISO timestamp.
- **`build_gate_input(...)`** — keyword adapter matching synthesis' available data.

### 3. Wired `synthesis.py` (single verdict construction site)

- Removed the local `evaluate_stop_distance` def; added `from backend.app.domain.workflow.gate import (build_gate_input, evaluate_gate, evaluate_stop_distance)`.
- Removed now-unused imports (`from math import isfinite`, `GateResult`/`GateStepResult` from models — grep verified only import-line matches remained).
- Inserted the gate block **after the D-44 conviction-cap block** (the final conviction mutation), before `return AnalysisVerdict(...)` (line 1652+):
  - `build_gate_input` reads `tv_data` (`avg_daily_volume_usd_calc`, `relative_volume_10d_calc`, `catalyst_bias_direction`), `technical.ma_alignment`, `technical_weekly.ma_alignment`, `price`, entry zone, stop, targets, `rr`, final `conviction`.
  - `gate_result = evaluate_gate(gate_input)`.
  - `gate=gate_result` in the returned `AnalysisVerdict`.

### 4. Tests — `backend/tests/test_gate.py` (new, 7 tests)

| Test | Proves |
|---|---|
| `test_verdict_always_carries_a_gate_result` | Every `synthesise()` attaches a typed `GateResult`; all 7 steps in plan order; overall ∈ {PASS, FAIL, CONDITIONAL}; conviction score matches verdict |
| `test_gate_reads_post_binary_risk_conviction` | earnings `days_until_earnings=2` → binary_risk True, conviction ≤5; gate sees the SAME capped number (no pre-cap leakage) |
| `test_gate_is_honest_conditional_not_false_pass` | Positioning + Portfolio Fit are CONDITIONAL in Wave-1; overall cannot be PASS with any conditional step |
| `test_gate_passes_liquidity_when_adv_above_floor` | $25M ADV → Liquidity PASS |
| `test_gate_conditionally_fails_tiny_adv` | **zero-ADV (D-55) → hard Liquidity FAIL, verdict overall FAIL** |
| `test_gate_uses_verdict_catalyst_bias` | bullish → Catalyst PASS; bearish → Catalyst FAIL |
| `test_rr_floor_still_deferred` | Low R:R does NOT hard-fail via the 2.5 floor (5d deferred) |

Local helpers `_make_technical`/`_make_fundamental`/`_synthesise` mirror the existing `test_synthesis_geometry.py` pattern (calls `synthesise` with `sentiment=None, risk=None, regime=None`).

### 5. Verification results

- Type-safety fix: `gate` is `GateResult | None` — added `assert verdict.gate is not None` narrowing in the test file (LSP-clean after fix).
- **76 passed in 3.51s** across `test_gate.py` + `test_synthesis_geometry.py` + `test_synthesis_momentum_regime.py` + `test_technical_orchestrator_integration.py` + `test_narration.py`.
- LSP clean on `gate.py`, `synthesis.py`, `test_gate.py`, `test_synthesis_geometry.py` (the transient `evaluate_stop_distance` attribution error was a stale index after the multi-file change — cleared on re-check).
- Pre-existing `orchestrator.py` LSP errors (pandas_ta stubs, datetime unbound) are unrelated, untouched, and out of scope.

## Limitations / notes

- The gate is attached but **not yet enforced** downstream (rejection paths, journal `gate_verdict`/`gate_failed_step` columns, Portfolio Fit wiring, 5d floor) — those are later slices under D-53's spine.
- `data_gaps` naming CONDITIONAL steps is the ready hook for the D-54 learning-surface rendering (still pending user confirmation).
- No commits created. No routes or architecture changed. No sub-agents used (user instruction).

## Next steps (outside this session's scope)

1. Wave-1D+ enforcement consumers (rejection path, journal columns).
2. Phase 1H / D-52: R:R source fix in `synthesis.py` (`_calculate_dynamic_rr` removal from target construction) — unblocks the 5d floor.
3. D-54: render `gate_failed_step` / `data_gaps` teaching copy in the UI.