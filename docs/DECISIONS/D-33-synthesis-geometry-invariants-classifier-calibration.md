# D-33: Synthesis Plan-Geometry Invariants & Classifier Calibration (Swing Parity Wave 1)

**Status:** Accepted
**Date:** 2026-08-21
**Evidence:** Stage-3 Parity Replays (live API, 2026-08-21); plan `.sisyphus/plans/swing-parity-upgrade.md` v1.1; Oracle + Elite-Trader critiques

## Context

Parity replay against an elite swing trader's 5 picks exposed correctness bugs in verdict emission:

1. **Invalid geometry**: BULL emitted ACCUMULATE with stop *inside* its own entry zone (8.13 inside 7.71–8.97).
2. **Sub-2:1 R/R plans**: MELI emitted WATCH c:2 with a complete plan at RR 1.6 while structural liquidity for RR ≥ 2.8 existed.
3. **Wrongful refusals**: KURA (commercial biotech, ~$77M TTM product revenue from FDA-approved KOMZIFTI) refused as "clinical-stage"; MSTR refused via GAAP-loss despite being a BTC-treasury proxy.
4. **Structural-target extension was broken twice**: `sorted(...)[:3]` kept the *nearest* levels (truncating exactly the far liquidity added for R/R repair), and no measured-move projection existed for names trading above all known structure.

## Decision

### P0.2 — Plan geometry invariants (`synthesis.py`)

Enforced on any LONG-oriented plan that emitted full levels (**including WATCH-with-levels**, which is how live marginal setups actually appear):

- **Invariant 1 (stop beyond zone):** stop < entry_zone_low, anchored to structure. If anchor ≥ entry_low → widen zone to anchor×0.99 and recompute; zone >15% wide → WATCH with explicit reason.
- **Anchor selection:** most recent swing low below price = **last match in chronological order** (swing lists are produced oldest-first; verified against live TV data where list heads are 52-week extremes). Swing lows are the equity invalidation point; trend MAs are NOT structure. Treasury assets use SMA20/SMA50 anchors only (NAV-trend proxy).
- **Invariant 2 (R/R ≥ 2.0) via Oracle priority rule:** (1) adopt structural stop when valid and different from pct-stop (adoption guarded by `structural_stop < entry_low` so it can never violate Invariant 1); (2) extend targets to structural liquidity (key resistance ∪ swing highs ∪ measured-move projection, bounded ≤ 2× current price, keeping the **highest** three); (3) only then downgrade to WATCH with explicit "R/R invariant failed" reason. **R/R is validated from actual plan geometry (zone-midpoint → last target over real risk)**, replacing the heuristic estimate when validated.
- **Promotion rule:** a WATCH that emitted full levels and passes geometry earns ACCUMULATE (conviction floor 4) — a structurally valid setup with room is actionable, not watchlist material. Invariant-2 failure downgrades back cleanly with the reason attached.
- **Invariant 3:** confirmed breakout AND breakout-candle rvol ≥ 1.5 ⇒ conviction floor 6. Recalibration now runs **after** geometry enforcement so promoted actions receive the floor.
- **HOLD consistency:** HOLD previously leaked stop/targets computed without an entry zone, emitting sub-2R plans outside invariant coverage. HOLD now strips trading levels like AVOID/REDUCE (a neutral stance has no trade plan).

### P0.3 — Classifier calibration (`fundamentals.py`)

- **Product-revenue signal, two paths:** (a) explicit product-revenue field > 0, or (b) totalRevenue > $20M TTM with commercial keywords — where (b) is **sector-scoped**: for biotech, product-level evidence phrases ("commercial product", "approved product", "fda-approved", "marketed", …) suffice **without a profitability gate** (launch-phase biotechs run deep losses by design while selling approved drugs; KURA live: −350% op margin on real sales). For non-biotech, the profitability requirement (op_margin > −0.5) is retained as the ASTS-trap guard.
- **Pre-profit demotion exemption:** both standalone demotion checks skip companies with `has_product_revenue` (real product revenue + deep losses = growth investment, not development stage).
- **Treasury asset path:** `asset_category == "treasury_asset"` + bullish MA + non-extreme volatility ⇒ emit a real plan with conviction cap 6, position cap 3%, mandatory NAV-framework caveat (thesis + red flags). Guards failing ⇒ refusal retained, but with regime-based reasons instead of the old GAAP-loss kill.

### Test-fixture corrections (documented deviations)

- `test_valid_structural_stop_used`: swing_lows reordered to `[95, 92, 90]` (chronological, matching producer contract); intent unchanged (~89.55 stop from the recent low at 90).
- `test_treasury_bullish_ma_emits_plan_with_caps`: thesis-caveat needle lowercased to match its own `.lower()` haystack (original mixed-case needle could never be a substring of lowered text).

## Consequences

- **Positive (live replay, same day):** ADBE RR 1.8→2.58 (bar "not degraded" ✓); MELI WATCH c2 RR1.6 → ACCUMULATE c4 RR 2.92 with targets 2173/2374 vs veteran 2150/2400 (near-exact parity); BULL stop-inside-zone fixed → valid plan, target ≈12.63 vs veteran 12.50; KURA wrongful refusal eliminated; MSTR classified treasury_asset+operating with honest guard reasons.
- **Positive:** every emitted plan now satisfies stop-outside-zone and geometric R/R ≥ 2.0 or carries an explicit machine-readable refusal reason (parity bar b/e/f groundwork for `scripts/parity_replay.py`, Wave 5).
- **Risk:** promotion can move weak-score-but-valid WATCHes to ACCUMULATE; mitigated by requiring full level-set + passing both invariants (meme-cap regression test confirms downgraded paths still cap size).
- **Risk:** measured-move projection assumes prior swing range persists; bounded at ≤2× price and used only during R/R repair.
- **Neutral:** KURA/MSTR final *action* upside now depends on module scoring and market regime (P1 territory), not correctness bugs.

## Verification

- `test_synthesis_geometry.py` 19/19 green; `test_ticker_classification.py` 61/61 (incl. new live-shape deep-loss commercial-biotech fixture); full backend suite 459 passed / 4 pre-existing unrelated failures (missing screen YAMLs ×2, asyncio event-loop integration config ×2). lsp clean on all touched files. `gitnexus_detect_changes`: MEDIUM risk, scope confined to screener-discover flows (P0.1) + ticker-analysis flow. No model/schema changes (`models.py` untouched) → additive-only mandate held.
