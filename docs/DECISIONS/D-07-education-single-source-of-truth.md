# D-07: Education Content Single Source of Truth (education.json + Bands DSL)

**Date:** 2026-08-25 · **Status:** Accepted · **Scope:** Core/education layer, frontend+backend

## Context
Teaching content was triple-written (backend templates in `education.py`, frontend lessons in `ticker-analysis/education.ts`, static tooltip pairs in `EducationTooltip.tsx`) with drifting thresholds (RSI >70 vs >85 taught inconsistently), duplicated lessons, and rendering bugs ($-prefix artifacts, enum leaks). Any content fix required 3 edits and inevitably drifted.

## Decision
1. **One file owns all user-facing teaching content**: `frontend/src/content/education.json` (~165 entries). Frontend imports at build time; backend loads the same file at startup via Docker read-only mount (`/app/education/education.json`) + `EDUCATION_CONTENT_PATH`.
2. **Dynamic value-based wording uses a declarative "bands" DSL** (`valueInterpretation.bands[{if,text}]`, ordered first-match with mandatory unconditional fallback band) instead of JS functions or Python ternary mini-language. One evaluator per side (`evaluateBands.ts` / `education_bands.py`) locked by a **shared parity fixture** consumed by both test suites.
3. **Canonical rendering rules**: default float display trims to 2dp (mirrors narration `_fmt`); `plain` transform passes through verbatim; percent/ratio/compactNumber/money transforms standardized once.
4. **Validation gate on every content commit**: JSON Schema + bands grammar + related-key resolution + intra-section duplicate labels (`npm run validate:education`; backend validates fail-fast at startup).
5. **LLM enhancement flag-gated, implemented (Phase 5)**: Gemini 2.0 Flash enriches only `value_context` when `llm_education_enabled` + key are set; advice-shaped fields suppressed; any failure falls back to curated text untouched. UI "Deep dive" always shows curated content first — the model is a footnote, never the source of truth.

## Alternatives Rejected
- Backend-served JSON API for content (D6): adds round-trips/loading states for static teaching text; rejected for tooltips, kept endpoint only for value-aware server rendering.
- Frontend-TS-only source: excludes backend narration from the truth; rejected.
- Keeping ternary template strings in Python: authoring-hostile, already produced the $-prefix bug class.

## Consequences
- Content fixes are one-file commits validated automatically; FE/BE wording can never drift again (parity tests enforce evaluator identity).
- Adding a metric = add one json entry (+optional alias); tooltip, deep-dive, Learn hub, and API all pick it up.
- Cross-section label overlap (glossary mirrors lesson names) is intentional — TermLink resolution is per-section namespace.
- Known debt: TermLink auto-linking deferred; glossary stubs need enrichment; Gemini wiring pending flag work.
