# Session Log — 2026-08-23: Ticker Page UX Fixes + News/Dealbreaker Pipeline Repair

## Context
Follow-up to the swing-trading validation session. User filed 5 UI/data issues on the
frontend (ticker page + screener) and one architecture question about number consistency
between the screener table and the ticker-analysis page.

## Question #1 — Screener vs Ticker Numbers (ANSWERED, no code change)
The two pipelines are **intentionally different products**, not a bug:

| | Screener Table | Ticker Page |
|---|---|---|
| Data feed | TV snapshot columns ONLY | TV columns + yfinance OHLCV (6mo daily, 2y weekly) |
| Entry | Point (= last close) | Zone (low–high band, MA-aware) |
| Stop/Targets | `vol_regime_multipliers()` ATR multiples (R:R ~1.5–1.67 by design) | Structural: swing highs/lows, key S/R, measured-move projections |
| Guardrails | none | `_enforce_plan_geometry_invariants()` can downgrade to WATCH and strip levels → N/A fields |

Shared math lives in `backend/app/infrastructure/analysis/levels.py` (consolidated for
locality; policies deliberately NOT unified). Divergence causes ranked:
(1) different formulas/policies, (2) screener uses cached TV snapshot vs ticker fresh
yfinance fetch (timestamps differ), (3) ticker adds OHLCV structure the screener never sees.
Recommendation: label screener levels "ATR-projection" in UI copy; full unification is a
product decision, not a bug fix.

## Changes

### Backend (3 files)
1. `backend/app/domain/ticker_analysis/models.py` — added `dealbreakers: list[str] = []`
   to `AnalysisVerdict` (distinct from advisory `key_red_flags`).
2. `backend/app/domain/ticker_analysis/synthesis.py` — main verdict construction now
   populates `dealbreakers=` from the existing local list (was silently merged into
   key_red_flags at line ~1288).
3. `backend/app/api/routers/ticker_analysis.py` — news endpoint rewritten with
   `_extract_news_item()`: dual-schema support for yfinance (legacy flat
   title/link/publisher keys AND current nested `content.clickThroughUrl.url` /
   `content.canonicalUrl.url` / `content.provider.displayName` / `content.pubTime`).
   Root cause of broken News tab: yfinance schema change left `link=''`, so frontend
   rendered dead `<a href="">` anchors.

### Frontend (4 files)
4. `frontend/src/components/ticker-analysis/TickerAnalysisPage.tsx`
   - Technical tab: adaptive grid (`weekly ? md:grid-cols-2 : grid-cols-1`) — Daily
     no longer orphaned at half-width when Weekly data is absent.
   - New **Deal Breakers** block (loss-red, OctagonX, "blocks the setup" badge) rendered
     above Red Flags; Red Flags now dedupes dealbreakers; fallback path preserved for
     old payloads.
   - Walkthrough renderer: parses `\n`-structured explanations into numbered step cards
     with prose paragraphs + bulleted evidence lists (`• ` lines), score pill colored
     PASS/issues.
5. `frontend/src/types/tickerAnalysis.ts` — added `dealbreakers?: string[]`.
6. `frontend/src/components/screener/filterDescriptions.ts` — added 12 missing indicator
   labels actually used across the 16 screen YAMLs (market_cap_gt w/ humanized $B/$M/$K,
   exchange_in, country_in, close_above, avg_volume_gt, volume_gt, ema_stack_bullish/
   bearish, eps_positive, pe_max, rsi_macd_bullish, bb_squeeze_tight); added
   `fundamental`→"Quality Gates" category + per-category "why it matters" hints;
   exported CATEGORY_HINTS.
7. `frontend/src/components/screener/TemplateInfoStrip.tsx` — "View filters" expander
   now renders grouped rule cards per category with check-listed human-readable rules,
   rule counts, and why-it-matters hints (uses existing `filtersByCategory`).

## Verification
- `python -m py_compile` on 3 backend files: OK
- `npm run typecheck` (tsc --noEmit): OK after fixing CATEGORY_HINTS export/import
- `npm run build`: ✓ built in 26.2s (chunk-size warning pre-existing)
- Live API probe `/api/v1/ticker/AAPL/news?limit=3`: real URLs + publishers returned ✓
- Live API probe POST `/api/v1/ticker/AU/analyze`: `verdict.dealbreakers` populated with
  R/R-invariant failure ✓

## Known Gaps / Follow-ups
- ESLint v9 lacks flat config in repo (`npm run lint` fails) — pre-existing.
- Screener-vs-ticker level unification = product decision; UI labeling suggested above.
- LSP typescript-language-server not installed globally; used project tsc instead.

## Addendum — Weekly Technical Root-Cause Fix (same session)
User asked WHY weekly was empty (not just the layout symptom). Investigation:

1. `technical.analyze(include_weekly=True)` WORKS — live probe returned
   `{'daily': ..., 'weekly': ...}` with real data (AAPL weekly RSI 57.0).
2. Orchestrator extracts `tech_weekly`, feeds MTF verdict alignment… then
   **`TickerAnalysisResponse(technical=tech_daily)` dropped it at line ~654**.
3. Response model only accepted flat `TechnicalAnalysis`; frontend's
   `'daily' in data` multi-TF branch could never activate. Dead feature path.

Fix:
- `models.py`: new `MultiTimeframeTechnical(daily, weekly)` model;
  response field widened to `TechnicalAnalysis | MultiTimeframeTechnical | None`.
- `orchestrator.py`: build full payload when module returned a dict; legacy
  flat shape preserved for short-circuit/failure paths.
- Offline proof: both shapes serialize correctly via model_dump(mode='json');
  delisted-ticker early-return path unaffected.
- Pre-existing py_compile diagnostics (pandas_ta dynamic exports, function-local
  datetime import) untouched; zero new static errors from this change.

⚠️ OPERATIONAL NOTE: the running backend did NOT hot-reload these changes
(stale OpenAPI schema; port 8000 owned by non-Windows-visible process — likely
WSL/Docker). Backend restart required to ship weekly to the frontend. Frontend
already handles both shapes — no FE change needed for this fix.

## Addendum 2 — Docker Rebuild + End-to-End Verification
Environment truth: backend = `conflu-api` container (compose, `./backend` volume
mount, uvicorn --reload). Reload had silently stopped picking up changes.

1. `docker compose up -d --build api` → image rebuilt, container recreated, healthy.
2. First post-restart probe STILL returned flat technical → caught a **wiring bug in
   my own fix**: `technical_payload` was constructed but line 667 still passed
   `technical=tech_daily` to the response. Fixed (`technical=technical_payload`),
   `docker restart conflu-api`.
3. Container env verified independently: yfinance 0.2.66 accepts interval='1wk'
   (105 rows for AAPL); module returns {'daily','weekly'} inside container.

FINAL LIVE VERIFICATION (all via running stack):
- GET health → healthy
- POST /ticker/AAPL/analyze → technical keys = {daily, weekly};
  daily ma=mixed rsi=48.3 · weekly rsi=57.0 adx=19.3
- POST /ticker/AU/analyze → verdict.dealbreakers = ["R/R invariant failed:
  cannot achieve R/R >= 2.0 (current 1.7)..."]; tech keys {daily, weekly}
- GET /ticker/AAPL/news → all items carry non-empty clickable links
- Playwright browser check on /ticker?symbol=AAPL → Technical tab renders
  BOTH Daily and Weekly sections

Note: first probe after recreate showed degraded/empty values — cold-start
yfinance cookie/crumb warmup, self-resolved; not a code issue.
