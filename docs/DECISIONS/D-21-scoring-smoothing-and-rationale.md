# D-21: Scoring Smoothing, Rationale, and Educational Features

**Status:** Accepted  
**Date:** 2026-07-02  
**Author:** Code Analysis + Expert Review

## Context

After implementing scoring calibration (Round 1: graded thresholds, Round 2: direction-aware, MTF stacking, volatility-adaptive stops), a comprehensive product review identified remaining issues:

- ADX 20-25 was a "dead zone" scoring 4/10 — too low for early trend formation detection
- RSI 53-55→55+ had a 40% jump (5→7) — a mini-cliff in scoring
- rel_vol 1.35→1.5 had a 50% jump (4→6) — asymmetric smoothing needed
- DetailPanel showed dead `volatility`/`pattern` factors (always 0) instead of correct `quality`/`fundamental`
- Rating mapping used Buy/Hold/Sell labels but scorer returns A+/A/B+/B/C/D
- No educational features to help users understand WHY a score was assigned
- No sector information in the table
- Only 6 screen templates available

## Decision

1. **ADX 20-25 → 6 pts** — The 20-25 zone is "trend forming," not "weak." Raising from 4→6 captures earlier entries before ADX pops above 25.
2. **RSI 54-55 → 6 pts** — New intermediate bracket bridges the 5→7 gap, giving smoother momentum scoring.
3. **rel_vol 1.35-1.5 → 5 pts** — Raised from 4 to make the 1.35→1.5 transition proportional.
4. **Replace dead factors** — `volatility`→`quality`, `pattern`→`fundamental` in DetailPanel.
5. **Fix rating mapping** — A+/A green, B+/B neutral, C/D red (instead of Buy/Hold/Sell).
6. **Add rationale** — `generate_rationale()` maps each factor score bracket to a human-readable sentence. Exposed via API and rendered in DetailPanel.
7. **Add sector column** — Retrieved from TV Screener data, displayed as optional table column.
8. **Confluence tooltips** — Hovering over T/M/V/Q/F abbreviations explains each factor.
9. **Template descriptions** — Title attribute on all `<option>` elements shows YAML description.
10. **New templates**: 52-Week Breakout + Low-Vol Setup.

## Consequences

**Positive:**
- Smoother, more intuitive scoring curve (fewer edge cases near thresholds)
- Educational features help users learn WHY signals are generated
- Sector visibility improves pattern recognition
- 8 templates now available (up from 6)

**Neutral:**
- ADX 20-25 raising from 4→6 will score more tickers in the "trend forming" zone higher; this may change sort order slightly
- rel_vol 1.35 change affects ~5-10% of borderline volume cases

**Risks:**
- No historical backtesting yet — scoring changes are not backtest-validated (deferred)
- All improvements purely from TV Screener data (no database, no OHLCV)

**Verification:** `tsc --noEmit` clean, Python compile clean
