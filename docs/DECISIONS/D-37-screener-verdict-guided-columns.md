# D-37: Screener Plain-English Verdict + Guided Column Defaults

**Status:** Accepted
**Date:** 2026-08-28
**Branch:** feat/swing-parity-upgrade
**Evidence:** Backend scenario tests in-container (`verify_verdict.py` — ESTC-like caution / clean BUY / WATCH / AVOID / degenerate null-safe); 572 backend tests pass (no regression); `tsc --noEmit` clean on changed frontend files; Playwright live-render (Verdict column + hidden-by-default advanced columns + Advanced customizer group).

## Context

The beginner working-professional persona walkthrough (`docs/PERSONA_VALIDATION_ANALYSIS.md`) exposed two concrete friction points on the Screener for a zero-knowledge user:

1. **No plain-English "second opinion"** — the top candidates surfaced (ESTC with RSI 78, BWT down -4.6%) gave the user no way to tell one was overbought and the other broken (gap #2).
2. **Cryptic institutional proxy columns** — `Confluence T26·M14·V10·Q8·F7`, `Conv`, `RS Rtg`, `Inst Q`, `ADX`, `ATR%` have no plain-English key and are noise for a novice (gap #1).

The user explicitly required that we **keep these proxy columns available for experienced traders** ("keep those columns as well so if some experienced trader wants to use it we have them") rather than removing them.

## Decision

- **New backend `verdict`** per screened ticker: `Verdict` dataclass (`action`/`tone`/`summary`/`reasons`) built by `build_verdict()` from the confluence `breakdown`, TV snapshot (`RSI ≥70` → overbought ⚠️, `ADX <20` → choppy), and elite signals (low conviction / factor conflicts / score floor). Action uses the **same vocabulary as the ticker page and Morning Brief** (`STRONG_BUY/BUY/ACCUMULATE/WATCH/AVOID`) so a screen-level verdict never contradicts the deep-analysis verdict. Null-safe on all inputs. Exposed as an **optional** `verdict` field on `ScoredTickerResponse` — purely additive, backward compatible.
- **Frontend `Verdict` column**: default-visible, left-aligned, tone-colored chip + truncated plain-English summary (hover = full text), sortable by action rank (STRONG_BUY=6…AVOID=1).
- **Proxy columns become `advanced`**: `confluence`, `rs_rating`, `inst_qual`, `conviction`, `adx`, `atr_pct` flagged `advanced: true` and excluded from `DEFAULT_VISIBLE_COLUMNS`. The show/hide `ColumnCustomizer` now groups them under an **"Advanced"** section so expert users re-enable each one. (`confluence` also corrected from `alwaysOn` to normal so it's re-addable.)

## Consequences

- **Positive:** Guided (default) view is immediately comprehensible to a beginner while expert columns remain one click away — satisfies the user's "keep them" requirement without front-loading jargon.
- **Positive:** Verdict vocabulary consistency across Screener / Ticker / Morning Brief prevents beginner confusion when moving from screen-level to ticker-level analysis.
- **Positive:** Additive API change (optional `verdict` field) carries **LOW** blast radius; no consumer breakage.
- **Risk / not done yet:** Lower-level elite UX (Daily Mission wizard, Validation Gate, Execution Engine, Apprenticeship Mode) from `ELITE_SWING_TRADING_BLUEPRINT.md` Phase 1 remains — this feature addresses gaps #1/#2 at the screener; gap #3 (plain-English trade-plan narrative) and gap #4 (in-flow guided learning) are the next layer.

## Files Touched
- `backend/app/infrastructure/screener/verdict.py` (new — `Verdict`, `build_verdict`)
- `backend/app/infrastructure/screener/tv_models.py` (`VerdictResponse` + optional `verdict` on `ScoredTickerResponse`)
- `backend/app/api/routers/tv_screener.py` (`build_verdict` + `VerdictResponse` wiring in `_build_scored_response`)
- `frontend/src/types/screener.ts` (`TVVerdict` + `verdict` on `TVScoredTicker`)
- `frontend/src/components/screener/ScreenerTable.tsx` (`advanced` flag, `Verdict` column + `CellVerdict`, `DEFAULT_VISIBLE_COLUMNS`)
- `frontend/src/components/screener/ScreenerPage.tsx` (`ColumnCustomizer` Advanced group)
