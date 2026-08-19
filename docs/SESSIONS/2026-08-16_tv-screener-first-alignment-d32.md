# Session Log — 2026-08-16: TV Screener-First Alignment + Correctness Wave (D-32)

**Branch:** fix/morning-pro-load-and-blocking

## Context

After a 5-track read-only architecture review (backend API, analytics domain, data layer, frontend, ops), the user confirmed the core architecture intent: **this is a TV Screener-first smart system, NOT a traditional "ingest overnight + precompute indicators" platform.** Docs were updated to say exactly that, and a full correctness wave was executed against the TV-first core.

## What changed

### Docs (D-32)
- **ADR-001 amended**: DuckDB is optional & non-load-bearing — only on-demand backtest/risk OHLCV; explicitly states discovery/scoring/analysis/charts never depend on it.
- **D-23 retired**: indicator-cache precompute path (939K-row `indicator_values` warehouse) is dead; charts already compute indicators on-demand from live yfinance.
- **D-32 created**: records the alignment decision.
- **ARCHITECTURE.md** updated: intro rewritten to TV-first; added "Live everywhere; no overnight batch" + "DuckDB is optional" design decisions; automation-gaps table marks indicator cache retired.
- **INDEX.md + docs/index.md + docs/DECISIONS/index.md** refreshed with the D-32 entry.

### Backend correctness (all verified by tests)
- **B1** `/health/ready`: `get_db` now accepts `timeout_s` (thread-based connect timeout) and health.py wires `settings.api.health_db_timeout_s` — readiness no longer always 503.
- **B2** backtest equity endpoint: `backtest_equity` → `backtest_equity_curves`.
- **B4** `deep_analyze`: `include_backtest`/`include_risk` now actually skip backtest/risk work (was response-field-stripping only) — the blocking/perf bug.
- **B5** `TVScreenEngine` is now a module singleton (`_ENGINE` + `get_tv_engine`) used by all 3 endpoints — TV cache (60s) + rate limiter (25/min) finally work across requests.
- **B6/B7** Morning Brief: `_rating_to_verdict` now maps confluence letter ratings (A+→STRONG_BUY … D→AVOID); `screen_score` uses `confluence.total/100` instead of nonexistent "score" key; education RSI hint reads TV's `"RSI"` column.
- **FIX 6** `tradingview-screener` pinned `>=3.2.1,<4` and installed to 3.2.1 in the env — `where2()` now unwraps to flat `filter2` (3.2.0 returned the full universe for every screen).
- **FIX 7** loosened 7 zero-match screen presets (high-conviction-stack, trend-leader, bull-flag-continuation, mean-reversion, volatility-expansion, statistical-mean-reversion, trend-follower): rvol 1.5→1.2, avg_volume 1M→500K, adx 25→20.
- **FIX 8** retired indicator-cache machinery: removed crashing `refresh_indicator_cache` task + its beat entry + chained call; intraday beat job now uses `periodic_intraday_ingestion` (filters 1D).
- **Dead code**: removed broken `dependencies.py` imports (ScreenEngine/ScreenReplay/ScreenSharing), dead `run_screen` task, unused `RateLimitError`/`EngineError`.

### Ops/observability
- Prometheus **request middleware activated** (`instrumentator.instrument`) with a FastAPI 0.138 `_IncludedRouter` patch — `/metrics` now emits `http_requests_total`/`http_request_duration_seconds` (HighErrorRate/HighLatency alerts live).
- `rate_limit_exceeded_total` incremented on 429; `_buckets` TTL eviction added; 429 envelope now includes `request_id`.
- Docker compose: worker/beat healthchecks + `stop_grace_period: 60s`, secrets passthrough (`CONFLU_PROFESSIONAL__SENDGRID_API_KEY`, `CONFLU_API__API_KEYS`), grafana password overridable via `${GRAFANA_ADMIN_PASSWORD:-admin}`.
- `.env` support restored (dotenv_settings in source priority); removed hardcoded `share.secret_key` default with loud warning.
- Removed dead `CacheHitRateLow` alert.

## Backend verification
- `pytest backend/tests`: **279 passed, 1 pre-existing failure** (`test_short_squeeze_loads` references a `short-squeeze.yaml` template that never existed at HEAD — unrelated to this session).
- `from backend.app.api.main import app` imports clean; `/metrics` returns 200.
- Beat schedule correct: `['daily-full-ingestion', 'intraday-ingestion']` only.

## Frontend (completed same session)
- **API envelope standardization**: all 11 `src/api/*.ts` modules now use a single `apiGet`/`apiPost` wrapper (client.ts) — removed 4 divergent unwrap patterns, `as unknown as` double-casts, and the manual `any` snake→camel mapping in professional.ts.
- **Type dedup**: `OptionsChainResponse`/`NewsResponse`/`ChartDataResponse`/etc. now live only in `src/types/tickerAnalysis.ts`; api module + TickerAnalysisPage import from there (fixed the broken re-export the aborted agent left).
- **Server-state → react-query (FIX C)**: new `src/hooks/useMarketRegime.ts` (shared `useMarketRegime` + `useSectorRotation` hooks). RegimeBar now hydrates via the hook (store kept as mirror for legacy consumers); WorkflowPage/DashboardPage consolidated onto the hooks; ScreenerPage's 3 raw `fetchSectorRotation` sites (page-level, MarketOverviewPanel, SectorFocusBanner) + TickerAnalysisPage's SectorContextBadge all moved to the shared cache.
- **Query-key factory (FIX D)**: `src/lib/queryKeys.ts` created; fixed the `['education']` vs `['professional','education']` collision (EducationTooltip).
- **Verification**: `npx tsc --noEmit` exit 0; `npm run build` succeeds (chunk-size warning only).

## Additional fix during verification
- **G13 duplicate metric registration** (ops audit rank 15): `observability._init_metrics` now registry-guards all 4 metrics (reuse existing collectors) — mirrors ws/handler.py's pattern. This fixed `test_professional_api_endpoints` (was crashing with `DuplicateTimeseries: ws_connections_active`) and any app-create-twice scenario.

## Backend verification (final)
- `pytest backend/tests`: **416 passed, 4 failed — ALL 4 pre-existing** (verified by stashing all session changes and re-running: identical 4 failures at HEAD):
  - `test_short_squeeze_loads` / `test_distribution_loads` — reference screen templates that never existed at HEAD (removed in the 14-screen library commit).
  - `test_morning_brief_generation_mock_regime` / `test_professional_api_endpoints` — full-suite event-loop pollution; **pass when the file runs in isolation (12/12)**, and the file fails identically at HEAD.
- Pro-mode integration file: **12/12 pass** (the DuplicateTimeseries crash we fixed).
- `from backend.app.api.main import app` imports clean (16 routes); `/metrics` returns 200 with real request metrics.

## Structural wave (regime extraction — D-32 follow-up)
- **Regime service extracted to `backend/app/infrastructure/market/regime.py`** — all pure computation moved verbatim (macro fetch, 5 scoring functions, composite weights, `compute_market_regime_sync`, `get_market_regime_sync`, market events) plus a new fallback-aware `get_market_regime_async()`.
- **`api/routers/regime.py` is now a thin HTTP wrapper** (3 endpoints only; re-exports for backward compat).
- **Domain→API layering violation fixed**: `domain/ticker_analysis/orchestrator.py` and `macro_overlay.py` + `infrastructure/professional/morning_brief.py` no longer import from `api.routers.regime` — they use `infrastructure.market.regime` directly. Orphaned `ApiResponse` imports removed from both domain files.
- **Verified**: app imports clean, all 3 `/market/*` routes present, pro-mode tests 12/12, full suite 416 passed (same 4 pre-existing failures as HEAD).

## Structural wave 2 — unify entry/exit math + frontend type codegen
- **Shared ATR trade-levels math** → new `backend/app/infrastructure/analysis/levels.py` (`compute_atr_levels`, `compute_fallback_levels`, `vol_regime_multipliers`, `TradeLevels`). The 5 duplicated entry/stop/target computations now route through ONE module with parameterized multipliers — byte-identical outputs (levels NOT rounded, `risk_reward` 2dp, same float behavior). Callers refactored: `confluence_scorer.py` (regime-adaptive policy), `deep_analysis.py` (fixed 2x/2x/3x policy). Golden tests: `backend/tests/test_levels.py` (12 tests) pin historical outputs including exact floats.
- **Frontend type codegen**: installed `openapi-typescript` (devDep); dump pipeline `npm run typegen` = backend OpenAPI → `frontend/src/types/__generated__/openapi.json` → `api.ts` (47 paths / 47 schemas, committed). `typegen:check` (with `git diff --exit-code`) makes drift between backend schemas and frontend types a CI-visible failure. Generated types are the canonical wire contract; component migration to `components["schemas"]` is incremental.
- **Verified**: backend 416 passed (same 4 pre-existing), `test_levels.py` 12/12, frontend `tsc --noEmit` exit 0.

## Structural wave 3 — scorer-parity decision + type drift tripwire (deferred items)
- **Item 1 — EliteSignalProcessor snapshot vs TVConfluenceScorer**: ran golden baseline (`backend/scripts/compare_scorers.py`, 6 diverse rows). Result: **mean per-factor divergence 2.97 pts (small), but conviction flips on 2/6 rows (~33%)**. Decision per "preserve behavior" mandate: **keep the snapshot** (replacing it would change UI conviction labels materially); added `backend/tests/test_elite_snapshot_parity.py` (3 tests) as a drift guard so the two scorers can't silently diverge further.
- **Item 2 — frontend type codegen migration**: added `frontend/src/types/api.drift-check.ts` — statically links hand-written camelCase UI types to the generated wire schema (`components['schemas'][...]`). It's a **compile-time tripwire**: any backend schema rename/type change fails `tsc --noEmit` in one file instead of silently drifting across 23 consumers. Tripwire proven working (temporary nonexistent-schema reference correctly broke tsc, then removed). Codegen pipeline (`npm run typegen` / `typegen:check`) remains wired.

## E2E verification (Docker rebuild + Playwright)
- **Docker**: rebuilt `api` + `frontend` images, recreated containers — all healthy (`api` healthy, `frontend` up, `redis` healthy).
- **Probes inside api container**: `/health` **200**, `/health/ready` **200** (B1 fix verified live — was always 503), `/metrics` emitting real `http_requests_total`/`http_request_duration_seconds`/`rate_limit_exceeded_total` (Prometheus middleware live).
- **Playwright browser pass (localhost:5173, 0 console errors across all pages)**:
  - `/pro` Morning Brief: regime NEUTRAL 60, 11 sectors, 14 top picks; **CVX/COP/MPC show STRONG BUY** (B6 verdict fix live) and **"Score: 0.8"** (B7 screen_score fix live).
  - `/screener`: Low-Vol 433 matches (988ms); selected **Trend Follower** (previously 0 matches) → **now returns SHC score 75** (FIX 7 + tradingview-screener 3.2.1 pin live). Clicked row → `/ticker/SHC`.
  - `/ticker/SHC`: full deep analysis — 5 module scores, buy/sell triggers, red flags (with D/E data-error guard), position sizing 12%, trade plan, 8 tabs.
  - `/sector-rotation`: heatmap, smart-money flows, RS ratings. `/dashboard`: Start Here + upcoming events. `/backtest`: full config form. `/risk`: 4 tool tabs. `/workflow`: Swing Desk institutional flow.
- **E2E caught a real bug (pre-existing data-quality)**: Charts crashed with `Candlestick series item data value of open must be a number, got=object, value=null` at `ChartPane.tsx:94` — root cause: CVX 1D has a yfinance placeholder row (2026-02-17) with all-null OHLC that lightweight-charts rejects, blanking the page via ErrorBoundary. **Fixed**: ChartPane now filters null-OHLC rows before `setData`. After fix: `/charts` renders CVX 15m candlesticks + indicators (RSI 67.14, MACD 4.13, EMA20 192.69), 0 errors.
- **Post-fix verification**: `tsc` exit 0, `npm run build` succeeds (11.47s), all 14 exercised API handlers returned 2xx per `/metrics`, containers still healthy.

## Status
- Backend + ops + docs + frontend + structural refactors + **E2E-verified in Docker** complete. Backend 431 passed (same 4 pre-existing failures as HEAD), frontend type-check + build green, browser pass 0 errors after the ChartPane fix.