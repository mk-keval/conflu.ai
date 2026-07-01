# D-20: Scoring Calibration Round 2 Evaluation

**Status:** Accepted  
**Date:** 2026-06-30  
**Author:** Trading Veteran (25+ yrs institutional)  

## Context

After implementing the scoring calibration changes from Round 1 evaluation (graded thresholds, MTF weighted stacking, volatility-adaptive stops, new SHORT screen templates), a second evaluation was commissioned to verify the fixes and identify remaining issues before taking the system live.

See: `TRADING-EVALUATION-ROUND2.md` (project root)

## Key Findings

### P0 Issues (Blocking — must fix before live)

1. **Scorer is direction-agnostic** — The `TVConfluenceScorer` always scores bullish even for SHORT-side screens (Breakdown, Distribution, Short Squeeze). Bearish stocks score 10–25/100, making short screens functionally useless and potentially misleading.
2. **First-target R:R always 1.0** — By construction (stop_mult == target_mult_1 across all 3 volatility regimes), every ticker's first profit target offers exactly even money. Swing traders need ≥1.5:1 on T1.

### P1 Issues (Should fix before live)

3. **EMA200/EMA50 thresholds reward late entry** — Top brackets (>20% above EMA200, >15% above EMA50) award maximum points to extended stocks most likely to pull back — opposite of swing trading needs.
4. **rel_vol 1.2→1.5 cliff** — Score doubles (3→6) for a 1% volume difference. Missing intermediate bracket at 1.35.
5. **Short Squeeze screen misconfigured** — Uses RSI>50 threshold (not overbought), effectively duplicating "Bullish Volume Surge" logic.

### P2 Issues (Polish before live)

6. Enable sort on Confluence column in UI
7. Add ADX 25–35 "trend initiation" bonus to quality scoring
8. Increase MTF min threshold from 15→30
9. Remove hardcoded ×1.5 volume highlight in UI
10. Add per-asset-class ATR regime thresholds for crypto

## Decision

The scoring calibration changes from Round 1 are directionally correct and represent genuine improvement. The system shifted from "dangerously false precision" (binary cliffs) to "reasonably ranked but direction-blind." The P0 direction-agnostic issue is the most critical remaining architectural limitation — the scorer must accept a `direction` parameter to produce valid results for bearish screens.

## Consequences

- **Positive**: Graded thresholds, regime-adaptive stops, and MTF stacking are all improvements. Long-side screens (Trend Follower, Momentum Breakout, Volume Surge) produce useful rankings.
- **Negative**: Short-side screens remain misleading until direction-aware scoring is implemented. The R:R issue means stop placement looks attractive but first-target math is actually break-even.
- **Risk**: A user running the "Distribution" screen and seeing all results at 15–25/100 will either ignore shorts entirely (lost opportunity) or trust the ranking and short the wrong ticker (loss of capital).
