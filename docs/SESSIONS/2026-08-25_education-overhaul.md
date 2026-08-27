# Session Log — 2026-08-25/26: Education Overhaul (Teaching Layer v2)

Plan: `.sisyphus/plans/education-overhaul.md` (Momus-reviewed; 2 blockers + 3 majors fixed pre-execution)

## What Was Built

### Wave A — Foundation
- `frontend/src/content/education.schema.json` — JSON Schema for all content sections
- `frontend/src/content/evaluateBands.ts` + backend `app/infrastructure/professional/education_bands.py` — bands-DSL evaluators under a **shared parity fixture** (`src/content/__fixtures__/bands-cases.json`, 18 cases): TS 32/32 + Py 12/12 on identical data. Canonical rules locked: default float rendering trims >2dp to 2dp (mirrors narration._fmt); plain transform = verbatim passthrough.
- `frontend/scripts/validate-education.ts` (`npm run validate:education`) — schema + bands grammar (mandatory "" fallback last) + related-key resolution + intra-section duplicate-label gate. Cross-section label overlap is BY DESIGN (glossary mirrors lesson keys for TermLink).
- Bug fixes in legacy code (pre-cutover): stray `$` before conditional blocks in 10 templates (renderer now defensively strips `${value <op>` artifacts); `bb_position` enum leak ("Price is above_upper…" → human words); EducationTooltip header Title Case instead of raw keys.
- Dedupe: `relative_volume`→`volume_ratio`, `days_to_cover`→`short_ratio` via `METRIC_LESSON_ALIASES` (verified identical computation in technical.py L736).

### Wave B — Content (165 entries in education.json)
48 metrics · 10 backtest metrics · 8 trade-plan concepts · 5 modules · 16 concepts · **78 glossary terms**.
Authored by 3+1 parallel agents into `.sisyphus/plans/fragments/*.json`, merged with dup policy (fund wins market_cap/avg_volume_20d; tech wins consecutive_gains), then W1.4-truth-check corrections applied at merge.

### Wave C — Cutover (single source of truth live)
- Frontend: `content/index.ts` typed accessors; `useEducation.ts` delegates; `EducationTooltip.tsx` rebuilt — **portal-based** (fixes real bug: inline tooltips were click-intercepted by ancestor scroll containers → "Explain more" never worked) with oneLiner summary + value-aware band line + "Deep dive" full lesson (replaces dead AI sparkle affordance).
- Backend: `education.py` rewritten to render from education.json via bands evaluator; aliases preserved; new `deep_dive()` method; response schema unchanged.
- Docker: compose mounts `./frontend/src/content/education.json:/app/education/education.json:ro` + `EDUCATION_CONTENT_PATH` env. Container verified serving wave-b content.
- Live probe `/api/v1/professional/education/pe_ratio?value=35&symbol=AAPL` returns dynamic wording.

### Wave D — Coverage
- ScreenerTable: `help` text on Scr/Rtg/RS Rtg/Inst Q/Conv columns (engine-verified facts incl. rating cutoffs A+≥80…D).
- NEW `ConfluenceDecoder.tsx`: T30·M19·V7·Q10·F8 codes clickable → per-pillar bars (T0-30/M0-25/V0-20/Q0-15/F0-10), plain-language meanings, regime-weighting footnote. Wired into Confluence column (14 rows live).
- MetricsCards: tooltips populated (pre-existing dead `tooltip?` field) + "How to read these results" teaching block (win-rate⇄R:R, PF thresholds, sample-size trap).
- BacktestPage: teaching empty state ("What is a backtest?").
- RiskPage: `RiskTabExplainer` strips per tab from education.json (correlation_matrix / suggested_position_size_pct / beta; VaR/CVaR tooltips present).
- TickerAnalysisPage: `ScoreLegendCard` (reconciles module −1..+1 vs screener 0-100 vs conviction 1-10; weights from synthesis.py DEFAULT_WEIGHTS) above Module Scores; PlanHelp info icons on Scale In/Scale Out/Trailing Stop/Time Stop/Risk Limits headings → tradePlan lessons.
- SectorFocusCard: score now expandable showing the FOCUS formula (weekly-RS 40% / flow 25% / momentum 20% / volume 15% + ≤10 improvement bonus + regime-cap note). Weight legend only — component values not exposed by API, never fabricated.

### Wave E — Learn Hub
- `/learn` route + sidebar nav (out of Pro-gating): searchable across all 165 entries, guided paths (first screen / reading a verdict / protect capital), category sections, expandable full lessons, glossary grid.

## Verification
- pytest: education_bands 12/12 + professional_mode integration 24 passed
- vitest: evaluateBands 32/32 (shared fixture)
- `validate:education`: green (165 entries)
- tsc --noEmit clean; production build ✓ (9s)
- Playwright: tooltip deep-dive expands (all sections); decoder opens w/ bars; ScoreLegendCard on ticker; FOCUS breakdown; /learn renders + search works

## Incidents
- Free-model rate limits (429) killed several background agents mid-Wave-B/D; fragments landed before dying; remaining work completed inline.
- Playwright coordinate-click races against the portal tooltip are harness artifacts; DOM-click verification used instead.

## Known Gaps / Follow-ups
- TermLink auto-linking (dotted jargon → popover) deferred — needs careful perf budget on narration-heavy pages.
- Gemini LLM enhancement = Phase 5 behind flag (user has AI Studio key; ~15 RPM free tier is sufficient; latency masked by curated-first design).
- Glossary stubs (interest_coverage etc.) need enrichment pass; docs/user-guide/backtest.md still thin.
- Morning Brief regime sub-labels (defensive_flight) explained via concepts.regime_states in Learn hub; inline popover near RegimeBar still pending.

## Files Touched (summary)
Backend: education.py (rewrite), education_bands.py (new), tests/test_education_bands.py (new), docker-compose.yml
Frontend: src/content/* (new), scripts/validate-education.ts (new), useEducation.ts, EducationTooltip.tsx (portal rebuild), ConceptExplorer.tsx, ScreenerTable.tsx, ConfluenceDecoder.tsx (new), MetricsCards.tsx, BacktestPage.tsx, RiskPage.tsx, TickerAnalysisPage.tsx, ScoreLegendCard.tsx (new), SectorFocusCard.tsx, learn/LearnPage.tsx (new), App.tsx, Sidebar.tsx, ticker-analysis/education.ts (dedupe), package.json (+vitest/tsx/ajv)

## Addendum — Continuation Pass (same session)

Deferred-but-in-scope items completed:
- **TermLink** (`src/components/learn/TermLink.tsx`): conservative glossary auto-linking (whole-word, ≥4 chars, max 3 links/passage, portal popover). Wired into ticker-page FindingList + verdict thesis. Live-verified: dotted "Trend" opens definition.
- **Glossary stubs enriched**: Interest Coverage / Payout Ratio / Quick Ratio / Bid-Ask Spread upgraded from one-liners to full definitions + related links (content v1.1.0).
- **RegimeBar explainer**: expanded pill now shows the label-specific regime explanation from concepts.regime_states ("Neutral: no clear directional bias…"). Caught & fixed a real hooks-order crash introduced mid-edit (useMemo after early return) via Playwright console verification.
- Validator extended: related[] may now resolve to glossary terms incl. snake_case forms.
- docs/user-guide/backtest.md synced with the in-app metric explanations (threshold tables + sample-size + overfitting signs).

Still user-gated: Gemini Phase 5 (flag-gated; awaiting go/no-go).

## Addendum 2 — Phase 5 Gemini Implementation (flag-gated, default OFF)

`_maybe_enhance_with_llm` implemented per plan:
- Triggers only when CONFLU_PROFESSIONAL_LLM_EDUCATION_ENABLED=true AND llm_api_key set (config fields pre-existed).
- gemini-2.0-flash via generativelanguage.googleapis.com, httpx timeout 6s, temperature 0.4, maxOutputTokens 120.
- System prompt forbids advice language; resp.actionable never populated from model output (advice-shaped field suppressed); value_context defensively truncated to 280 chars.
- Daily budget: max_daily_education_calls (default 500) via in-process counter.
- ANY failure (no key / flag off / HTTP error / rate limit / empty payload) → curated template response returned untouched. Verified: flag-off ✓, no-key ✓, bogus-key HTTP failure → source=template with full curated text ✓.
- Container rebuilt; live default remains OFF.

To enable: set llm_api_key (AIza...) + flip the flag; UI already labels LLM output "Source" separately from curated text.

## Addendum 3 — Teacher-Mode Audit (Playwright walkthrough, all pages)

Acted as stock-market course teacher; walked Morning Brief, Screener, Ticker (AAPL/MSFT/KO/NDAQ), Backtest, Risk, Sector Rotation, Charts, Learn hub.

PASS (verified live): regime pill explainer; RSI tooltip + Deep dive (all 9 sections); 14 confluence decoders w/ all 5 pillar meanings + regime note; 5 column-help popovers (Scr/Rtg/RS Rtg/Inst Q/Conv); ScoreLegendCard expands w/ correct weights; glossary button; backtest teaching empty-state; risk tab explainers + Position Size teaching; sector-rotation Learn panel (party analogy, cycle phases, mistakes); /learn search + PF lesson (overfit warning, 1.5 threshold); MSFT/KO verdicts render with legend.

Gaps found & FIXED in this pass:
1. Charts page had ZERO explanations (lost piece of a rate-limit-killed agent) → added EducationTooltip to ChartToolbar indicator buttons + IndicatorPanel rows (8 info icons live, RSI tooltip verified).
2. Verdict thesis used opaque "score 48%" (% of what?) → synthesis._generate_thesis now prints signed −1..+1 score with scale context ("score +0.12 on our −1 to +1 scale"); ACCUMULATE pullback line teaches "dips toward support, not drops below it". Live-probed: AAPL thesis now reads correctly. 96 synthesis/ticker tests pass.

Remaining observations (minor, logged for future):
- KO dividend case: Dividend Yield lesson exists in library but page didn't surface it for a dividend-heavy stock — candidate for conditional education hints on ticker page.
- Dashboard has no Learn icons yet (low priority — it's a summary surface).
