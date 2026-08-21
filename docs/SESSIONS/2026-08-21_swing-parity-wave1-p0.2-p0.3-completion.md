# Session Log — 2026-08-21: Swing Parity Wave 1 Complete (P0.2 + P0.3 finished, gates passed)

**Trigger:** Resume of `RESUME-2026-08-21-swing-parity.md` → **Outcome:** P0.2 geometry invariants complete (19/19) · P0.3 verified end-to-end + live-data divergence fixed · measured-move projection added · HOLD level-leak fixed · Wave-1 gate passed · D-33 recorded.

## What Happened

### 0. Preflight
- Subagent smoke test under new all-free config: **PASS** (explore agent via gemma-free, 29s, correct structured reply). Delegation available; direct implementation chosen for spec-coupled surgical work.
- Baseline: 13/19 geometry tests green; 6 red = remaining P0.2 spec.

### 1. P0.2 completion (`synthesis.py`) — root causes fixed
Traced all 19 fixtures by hand before editing. Six failures shared one design gap plus three helper bugs:
1. **Enforcement gated on BUY-family only** — live-realistic fixtures produce WATCH-*with-levels* (as live MELI did), so invariants/breakout-floor/treasury-caps never fired → enforcement now covers any LONG-oriented plan with a full emitted level set.
2. **Anchor selection mixed swing lows + SMAs via `max()`** — SMA20 could override the true invalidation point → swing-low-first semantics.
3. **Target extension kept the 3 *lowest* levels** (`sorted()[:3]`) — truncated exactly the far liquidity added for R/R repair → keep highest 3 within ≤2× price bound.
4. **R/R basis was entry-high heuristic** → geometric R/R from zone midpoint over real risk now validates/repairs plans.
5. **Breakout recalibration ran before enforcement** → moved after so promoted actions get the conviction floor.
6. New: **WATCH→ACCUMULATE promotion** on validated geometry; **adoption guard** (`structural_stop < entry_low`) so priority-1 can never re-break Invariant 1.

Iterations: 16/19 → caught adoption-above-entry-zone bug (BULL), SMA50-rescue bug (downgrade fixture), and an unsatisfiable test assertion (`"NAV"` vs `.lower()`); 19/19 green.

### 2. Live replay exposed two deeper issues (fixed)
- **Swing-list chronology:** live producer emits swings oldest-first; first-element anchor selection grabbed the 52-week low (BULL: stop anchored at 4.50 on a ~9.50 stock). Fix: most-recent = last match below price. Fixture `[90,92,95]` reordered to chronological with intent preserved.
- **Measured-move projection missing:** BULL/MELI traded above all known structure → zero extension candidates → wrongful downgrades. Added range projection (close + max-swing-high − min-swing-low, ≤2× price). BULL projects ≈12.63 vs veteran target 12.50.

### 3. P0.3 verification found fixture/live divergence (fixed)
Unit fixtures passed but **live KURA still classified clinical_stage**: yfinance summary's only evidence phrase is "first commercial product" (no "approved"/"marketed"), op margin −350% tripped the ASTS-trap profitability guard, AND the pre-profit demotion would have re-caught it downstream even if the signal fired. Fixes: biotech-scoped product-evidence path (no profitability gate), demotion exemption for `has_product_revenue`, plus a new regression fixture replicating today's exact live shape. MSTR verified: treasury_asset + operating ✓ (wrongful GAAP refusal gone).

### 4. Bonus correctness fix
KURA replay emitted **HOLD c2 with orphan levels** (stop/targets without entry zone, RR 1.4, bypassing invariants) — section 6 computed levels for any priced action while section 7 stripped only AVOID/REDUCE. HOLD now strips levels too (neutral stance = no trade plan).

### 5. Wave-1 gate results
| Gate | Result |
|---|---|
| Full pytest | **459 passed** / 4 pre-existing unrelated failures (missing screen YAMLs ×2, asyncio event-loop integration ×2) |
| lsp diagnostics | 0 errors across `ticker_analysis/` domain (10 files) and `tests/` (43 files) |
| gitnexus detect_changes | MEDIUM risk, scope exactly as intended (discover flows = P0.1, ticker-analysis flow = P0.2/P0.3) |
| Additive schemas | `models.py` untouched → zero API contract changes |
| Stage-3 parity replay (live API) | ADBE ACCUMULATE c3 RR **2.58** (was 1.8; bar ✓) · MELI ACCUMULATE c4 RR **2.92**, T 2173/2374 (veteran 2150/2400) · BULL ACCUMULATE c4 valid plan, stop outside zone ✓, T 12.63 (veteran 12.50) · KURA refusal eliminated (honest HOLD, weak module scores — scoring is P1 territory) · MSTR treasury_asset+operating ✓, guards legitimately fail today (ma=mixed, vol=extreme → spec-correct refusal reasons) |

### 6. Documentation
Decision record **D-33** (geometry invariants + classifier calibration), this log, indexes refreshed.

## Files touched this session
- `backend/app/domain/ticker_analysis/synthesis.py` — invariants rewrite, promotion, geo-R/R, projection, HOLD strip, recalibration reorder
- `backend/app/domain/ticker_analysis/fundamentals.py` — biotech product-revenue path, demotion exemptions, trailingPE pyright cleanup
- `backend/tests/test_synthesis_geometry.py` — fixture helpers typed (`model_copy`), chronological fixture, NAV needle case fix
- `backend/tests/test_ticker_classification.py` — new KURA live-shape test, typed helpers
- `docs/DECISIONS/D-33-*.md`, `docs/SESSIONS/*.md`, `INDEX.md`, `docs/index.md`, `docs/DECISIONS/index.md`

## Next (Wave 2 per plan v1.1)
P1: regime→screen yaml remap (RC1) · stale-while-revalidate in TVCache + circuit breaker BEFORE One-Snapshot-Multi-Screen flag (Oracle prerequisite) · RS-vs-index enrichment from same snapshot · catalyst badge · earnings chip. Wave 3 = mentor narration. Wave 5 = codify `scripts/parity_replay.py`.
