# D-38: Ticker-Page Narrative Auto-Glossing (persona gap #3)

**Status:** Accepted
**Date:** 2026-08-28
**Branch:** feat/swing-parity-upgrade
**Evidence:** `tsc --noEmit` clean in `conflu-frontend` (only pre-existing `vitest` test-file error); Playwright live probe — AAPL VerdictBanner thesis renders 3 glossed terms (bullish / support / liquidity) + billboard glosses; clicking a glossed term opens the Learn popover with a plain-English definition. `gitnexus_detect_changes` risk "critical" reflects **cumulative uncommitted branch scope** (prior chart-reading + screener work), not this session's isolated change.

## Context

The beginner working-professional persona walkthrough (`docs/PERSONA_VALIDATION_ANALYSIS.md`) exposed gap #3: the **trade-plan narrative on the ticker page assumes knowledge**. A zero-knowledge user reading the VerdictBanner thesis ("build position gradually on pullbacks toward support") or the trade-plan notes had no way to learn what *pullback*, *breakout*, or *confluence* mean — unlike the Scale In / Scale Out steps, which already had Learn tooltips.

The platform already had the mechanism — `TermLink` (dotted-underline auto-glossing with a Learn popover, fed by the 78-term `education.json` glossary) — but **not every narrative passage was routed through it**. Several passages were already glossed (FindingList triggers/red flags, Detailed Analysis thesis); two were not (VerdictBanner thesis, trade-plan notes).

## Decision

- **Wrap the VerdictBanner thesis paragraph** in `TermLink` so educational terms in the plain-English thesis are auto-glossed and clickable.
- **Wrap each trade-plan notes `<li>`** in `TermLink` so the plan's rationale is glossed in context.
- **Additive frontend-only, education-layer change**: it only changes how existing narrative text renders (adds dotted-underline glosses + Learn popovers). **No API contract, no data-shape change, no business-logic change** → LOW blast radius.

## Consequences

- **Positive:** A beginner can tap any financial term in the verdict thesis / trade-plan notes and get a plain-English definition in context — closing gap #3 without any backend or data changes.
- **Positive:** Reuses the existing `TermLink` / glossary infrastructure; consistent with how Scale In / Scale Out steps already educate.
- **Risk / known limitation:** `TermLink` matches whole words via `\b…\b` with a min 4 chars — plural/inflected forms (e.g. "pullbacks") don't gloss the base term "pullback". Pre-existing limitation, not introduced here. Could be addressed later by lemmatized lookup if it becomes a UX gap.
- **Not done yet:** gap #4 (in-flow guided learning) is planned next as Phase 1 (Daily Mission + Validation Gate + Execution Engine) per the blueprint, on user's confirmed "Option A" path.

## Files Touched
- `frontend/src/components/ticker-analysis/TickerAnalysisPage.tsx` (VerdictBanner thesis + trade-plan notes → wrapped in `TermLink`)
- `docs/index.md` (Recent Activity)
- `INDEX.md` (Recent Activity)
