# Architecture Decision Records

This section contains Architecture Decision Records (ADRs) for significant project decisions.

## Index

- [D-77: Bundle A — Exit & Gate Geometry Frozen for FWD-v0.2](D-77-bundle-a-exit-geometry.md) — **user sign-off on all five Bundle A decisions**: the gate measures `T1 R` from the planned fill (`entry_low`), not the last target or a blend; targets are the nearest structural levels inside a family band, and a trade with no level in the band is rejected rather than given a manufactured target; exits are family-specific (trend 1/3+1/3+1/3, breakout 1/2+1/2, mean reversion/rotation/unknown 100% at T1) with breakeven at +1R and 2.0/2.5×ATR trails; mean reversion exits fully at T1 with a 10-day stop. Fixes the `target geometry` defect that let CRS pass at 4.32:1 while T1 was 21.2R from the planned entry. Spec frozen; **implementation pending; no v0.2 row exists** until the go-live commit flips `CURRENT_SAMPLE_VERSION`. D-75 bar and D-76 versioning unchanged.
- [D-76: Forward Sample Versioning — v0.1 Closed for Verdicts, v0.2 Scored](D-76-forward-sample-versioning.md) — **Q2 = C**: the v0.1 sample is closed for verdict purposes (1 closed CRS −1.00R; SF/IOSP remain open reference rows) and the daily loop continues as `interim` data, never evidence. Adds an immutable `sample_version` (`v0.1` / `interim` / `v0.2`) to `paper_trades` and `pending_orders`; the first migration backfills every existing row to v0.1, `upsert_entry` sets it on insert only, a filled order inherits its order's version, and legacy CSV imports default to v0.1. `scripts/scorecard.py` now scores only the scored version (v0.2) and prints v0.1/interim as a reference table; `verify_journal.py` fails on unknown versions or a fill/row version mismatch. **No trading rule changed and no past decision was rewritten**; the what-if is a separate labeled replay (H-09, `rules_version='v0.2'`).
- [D-75: Pass Bar — Expectancy, Profit Factor, Loss Control](D-75-pass-bar-expectancy-profit-factor.md) — **closes P0-4 with an explicit user sign-off**: the never-applied legacy `VISION.md` bar (WR > 50% AND avg R > 0.5) is replaced. At 30+ closed trades the sample passes when expectancy > 0 after costs, profit factor ≥ 1.3, and average loss ≤ 1.0R; win rate, average win, payoff ratio and MFE capture are reported, not gated. Adds an 8R/12R peak-to-trough drawdown circuit breaker. Kill rule unchanged. No code, target, gate, screen, sizing or exit change; sample continues; bar is not retroactive.
- [D-74: P0 Measurement Integrity — Canonical Dollar P&L, Plan Provenance, Phantom/P&L Verifier](D-74-p0-measurement-integrity.md) — **the measurement layer now tells the truth after the first valid fills**: `pnl_usd` was R × notional instead of R × dollar risk (CRS −$1,624.99 vs −$30.01 net), the gate's `risk_reward` and the stored plan's targets did not reconcile (CRS 4.32 vs 11.89; IOSP 6.15 vs 3.99; SF 6.47 vs 4.36) because `target_3` was never persisted and the gate field can be stale, and live dollars were gross while backtests were net. Adds `backend/app/domain/workflow/pnl.py` (gross/costs/net; R stays gross), `target_3`/`plan_rr`/`target_1_r`/`pnl_gross_usd`/`costs_usd` columns + backfill, `scripts/verify_journal.py` (PASS: 0 phantom, 0 P&L mismatch, 3 R:R warnings), `scripts/scorecard.py`, a pre-backfill DB backup, and the scorecard / pre-registration / hypothesis-log docs. **No trading decision changed**; targets, R:R gate, screens, sizing and exits remain frozen. CRS is the first review-A data point: T1 11.2R from the zone midpoint (27.7R from the fill), MFE +3.72R, stopped −1.00R.
- [D-73: Pending Orders + T+1 Fills — No Same-Day Paper Fills](D-73-pending-orders-t1-fills.md) — **the execution correction after four phantom fills (PM/AMGN/CCK/MMM)**: after-close signals become `pending_orders`; only actual bars strictly after the signal date can fill them (limit at `entry_low` by default, optional MOO inside `entry_high`, 3-session expiry, same-session stop but no same-session target). Pending orders reserve capital/slots/sector exposure; fills recompute shares capped by planned risk. The four invalid rows are voided (`voided=1`, visible, not positions, not scored) and the forward clock restarts at the first actual fill. Targets, R:R, screens and sizing remain frozen.
- [D-72: Forward-Sample Execution v0.1 — Measurement Integrity + Calendar-Day Time Stop](D-72-forward-sample-execution-v01.md) — **the pre-sample fix approved after the pipeline audit**: screen/confluence/regime attribution now comes from the brief ticker, sector from the analysis response (so the 30% cap actually binds), and `max_hold_days` is persisted and executed as calendar days (converted to the first session on/after the cutoff). Rejections store screen/regime; the 3 legacy rows (NTNX/WBD/NVDA) are flagged `exclude_from_stats=1` and skipped by expectancy/rolling metrics. Targets, R:R gate, screens and sizing are **unchanged** — review item A. Additive schema migration; 51 focused tests pass; **sample started 2026-10-19 (run id 1; PM accepted)**. Execution timing superseded by D-73 (sample restarted 2026-10-21).
- [D-71: Two-Month Paper-Trade Replay — Simulated Screen Ledger in the Journal](D-71-two-month-paper-replay.md) — **the live pipeline can't be rewound (TradingView answers only "now"), so the deployed screens were replayed over the last 2 months and surfaced as an inspectable ledger**: pure `compute_regime_from_frames` gives the regime as-of each signal day; `load_screen_mix` mirrors the live selector; 503-name S&P 500 universe fetched in 20-symbol yfinance chunks and cached (`.cache/replay/`); same D-70 mechanics (next-open entries, ATR 2/3, 15-bar cap, 10+5 bps/side); dedupe per `(signal_date, symbol)` by screen rank. New `replay_runs`/`replay_trades` tables (never feed expectancy/kill rule) + `GET/DELETE /workflow/replay` + Journal **Live / 2-month replay** toggle + `python run_paper_replay.py`. **Honest result: 371 entries, 114 W / 257 L, WR 30.7%, expectancy −0.203R, PF 0.63, −$99.8k at 1% risk** — the loss is concentrated on choppy-regime days (242 trades, −0.322R); only statistical-mean-reversion (+0.162R) and two trend screens were positive. Simulated evidence, not forward evidence; concrete input for the pending D-70 weight review.

- [D-70: Template Validation Honest Reset — Engine, Runner, and Fetcher Window Fix](D-70-template-validation-honest-reset.md) — **the numbers are now believable (they were not)**: D-61's PF 3–52 came from an engine with a 4h blind spot, silent skips and look-ahead/collapsed exits. Rewrote `external_backtest` v2 (full `signal_filters` rule objects, per-rule TFs with 4h resampled from 1h, next-open entries, ATR 2.0/3.0 exits with stop-first tie-break, `max_hold_bars`, direction-aware shorts, single CAGR formula) + honesty semantics (unavailable → recorded `not_applied_filters`; unknown rule → strict FAIL; no intraday → symbol hard-excluded). Mid-run discovery: `fetch_yahoo` ignored `start`/`end` on cold cache ("same backtest, different spans") → fixed `015d2fd` + regression tests; `.gitignore` scoping un-swallowed `backend/app/infrastructure/data/` (`fetcher.py` was never tracked). Corrected run: 19 templates × 30 symbols, 0 capacity violations — expectancy +0.07…+0.33 R, PF 1.0–1.9; deployed set mostly positive; bull-flag weakest deployed (PF 1.15); weights **not yet re-tuned (user decision)**. Supersedes all D-61 statistics; see `docs/backtests/VALIDATION_REPORT.md`.

- [D-69: Dependency Security Remediation — vite 7 / vitest 4 / starlette 1.9](D-69-dependency-security-remediation.md) — **CI audit gates clean again**: npm 24 → 10 (0 critical) via vite 7.3.7 (clears vite≤6.4.2 + esbuild GHSA-67mh-4wv8-2f99), vitest 4.1.12 (criticals were tinypool/@vitest/mocker), ajv 8.20.0, and removing the dead swc plugin (D-66 leftover); Python 0/120 advisories via starlette 1.9.0 / fastapi 0.148.0 / instrumentator 8.1.0 — "bump starlette to clear them for real" done and the five `--ignore-vuln` stubs deleted from `security-scan.yml`. **Deferred majors tracked**: tailwind 4 chain, react-router-dom 7 (moderate), React 19, eslint 10, lint-staged 17, vite 8. Backend 854 tests pass; the e2e tv multi-tf timeout is environment (live TradingView path).

- [D-68: Paper Journal → SQLite + One-Click EOD Combined Run (A+B)](D-68-paper-journal-sqlite-eod-combined-run.md) — **journal of record moves from CSV to `data/paper_trades.db`** (stdlib sqlite3, 3 tables: `paper_trades`/`rejections`/`workflow_runs`; DuckDB untouched); one-click after-close `run-close` endpoint runs A→B(apply); missed entry days stay honest gaps (exits self-heal); ET market dates; upsert kills the same-day file-overwrite bug; UI hydration fix + new Journal tab (runs strip, trades table, rejections, CSV export). Plan: `.sisyphus/plans/paper-journal-sqlite-eod.md`. **Supersedes the storage choice of D-7** (CSV → export format, not store).

- [D-67: `claude-mem` OpenCode V2 Plugin Restore — Install Upgraded 13.3.0 → 13.37.0](D-67-claude-mem-opencode-v2-restore.md) — **Environment/tooling (not app code)**: The deleted global `claude-mem.js` was the 13.3.0 bundle using the legacy V1 plugin shape, which OpenCode v2.0.28 rejects. Restored by aligning the whole install to **13.37.0** via the official installer (marketplace + cache + worker + `mcp.claude-mem` MCP server; legacy static `<claude-mem-context>` block removed from `AGENTS.md`). Satisfied the worker's new `claude_cli` dependency via `CLAUDE_CODE_PATH` → the CLI bundled with OpenCode's Agent SDK. Verified: plugin loads, MCP 19 tools, worker `13.37.0 degraded=false`, `/api/context/inject` HTTP 200, capture + search work. **Resolved:** provider auth via the user's local **OmniRoute** gateway (`openai-compatible`, model `openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`) — **no Claude login needed**; verified end-to-end (capture → AI summary → store → recall).

- [D-66: Frontend Build Fix — Tailwind CSS sucrase Parsing Issue](D-66-frontend-build-tailwind-sucrase-fix.md) — **Frontend production build now passes**: Moved CSS to `public/index.css` loaded via `<link>` tag, bypassing Vite's TypeScript parser (sucrase) that failed on `@tailwind` directives. Added manual dark color utilities (50-950 scale) for `bg-dark-*`, `text-dark-*`, `border-dark-*` used by 36 components. Removed Tailwind 4.x beta packages. Build passes in ~9s.

- [D-65: Ticker Analysis Data Accuracy Fixes — Earnings Surprise, STRONG BUY Entry Zone, Structural Target Fallbacks, Invariant Enforcement Fallback](D-65-ticker-analysis-data-accuracy-fixes.md) — **Earnings surprise now accurate**: Fetches from `earnings_dates` DataFrame instead of empty `.info` field — AAPL +6.74%, INTC +94.59%, MSFT +11.81%. **STRONG BUY entry zone fixed**: Added to entry zone logic (was only BUY/ACCUMULATE/WATCH). MSFT STRONG BUY now shows entry 494-523. **Structural targets capped at 1.5x**: Reduced from 2.0x to prevent extreme R/R (AAPL was 14.76, now realistic). **Fallback targets added**: Percentage-based (8%/15%/25%) and ATR-based (2R/3R/4R) when no structural data. **Invariant fallback heuristic R/R**: Prevents false WATCH downgrades when no structural data — test_accumulate_conviction_high_score now passes. **D/E recalculated from quarterly balance sheet**: NVDA 0.17 (was 16.97), AAPL 0.78 (was 78.44), INTC 0.58 (was 49.00). All 771 backend tests pass.

- [D-63: Morning Brief / Pro Page — Regime Screens Updated to Elite Templates](D-63-morning-brief-elite-templates.md) — **Morning Brief (`/pro`) now uses elite templates**: Updated `config/regime_screens.yaml` v2 to use 12 D-61 validated templates (>55% WR, >1.5 PF). Removed `short-squeeze` (0 trades), `trend-follower` → `trend-follower-v2`. Added `vcp-breakout`, `trend-pullback-v2`, `institutional-quality-v2`, `low-vol-setup`, `mean-reversion`, `distribution`. Morning Brief now picks tickers using templates with proven edge per regime.

- [D-62: Simple Backtest Mode for Filter Sweep Page](D-62-simple-backtest-mode.md) — **Simple Backtest mode added to Filter Sweep page**: Run single backtests with any of 19 templates, custom date ranges, custom symbols, custom timeframes. New API `runSimpleBacktest()` loads template signal_params, transforms backend response. Components: SimpleBacktestForm (template selector, date range, symbols, timeframe, advanced settings), SimpleBacktestResults (metrics cards, trade table, equity curve chart). Mode toggle in FilterSweepPage preserves Parameter Sweep. No backend changes.

- [D-61: Elite Template Deployment — Filter Sweep Backtest Results → Screener Integration](D-61-elite-template-deployment.md) — **Comprehensive backtest of 21 templates on Yahoo Finance OHLCV**: 12 elite templates (>55% WR, >1.5 PF, ≥10 trades) identified, 2 failed templates removed (rsi2-reversion, short-squeeze); regime mapping updated to recommend elite templates; **Infrastructure built**: OHLCVFetcher (Yahoo Finance, rate-limited, cached), ExternalBacktestEngine (pandas direct eval, pandas_ta indicators, fixed/ATR/Kelly sizing), comprehensive runner (21×10×730d); **Verification**: 60/60 screener tests pass, frontend build passes, 19 templates served via API

- [D-60: Filter Sweep Backtest Framework + Gate Enforcement Wave-1 Complete](D-60-filter-sweep-backtest-framework-gate-enforcement.md) — **Gate Enforcement Wave-1 complete**: 7-step backend gate evaluator, verdict wiring, frontend renderer, D1 tier sizing; **Filter Sweep Backtest Framework** for parameter sweep optimization of screener filters (18 params, 5 presets, walk-forward optimization, API endpoints); **Bug fixes**: duplicate DailyRoutine render, gate field alias mismatch, ticker route ordering, FindingList null safety; **Tests**: 20/20 gate tests, 20/20 synthesis tests, 5/5 Playwright E2E, 830 backend tests pass

- [D-59: 0A-ii Control Study Re-run & D1 Tiered Sizing Activation](D-59-0a-ii-control-study-gate-verdict-tagging.md) — **0A-ii re-run with 2.5:1 floor active**: 0 PASS, 0 FAIL, 31 CONDITIONAL (all Liquidity — data limitation, not gate bug); exit replay 77.8% win, +1.093R; **D1 tier implemented**: CONDITIONAL at R/R ≥ 2.0 with r1 ≥ 1.0 (half-size via existing CONDITIONAL_HALVING=0.5), PASS at ≥ 2.5, FAIL below 2.0; 834 backend tests pass

- [D-58: 1H Source Fix: Structural Targets & Measured R:R](D-58-1h-source-fix-structural-targets-measured-rr.md) — **unblocks 5d R:R floor & D1**: targets always from structure (unconditional), RR measured not invented, provenance recorded (entry_basis, structural_stop_level, structural_target_levels); gate consistency assertion validates measured RR; 593 tests pass

- [D-57: Fix Invariant-2 Watch Promotion Logic](D-57-fix-invariant-2-watch-promotion-logic.md)

- [D-56: Gate Enforcement Spine — Wave-1 Completion (1E/2B/2C/2D/1D/2E) + 0A-i Control Study](D-56-gate-enforcement-wave1-complete.md) - **closes the Wave-1 spine**: 10% stop ceiling + 5d stub surfacing (1E), journal reader (2B), real Portfolio Fit 8-pos/30%-sector (2C), risk-based sizing w/ CONDITIONAL halving (2D), gate enforcement in `paper_trade_from_brief.py` — PASS/CONDITIONAL×0.5/FAIL→REJECTIONS, blank stop always rejects (1D), auto exits `infer_exit` (2E); **0A-i control study** `control_study_voided_cohort.py` — re-reads the 31 voided rows read-only: 4/31 manufactured (PAGP, LNG, CVX×2 — exact R25 reproduction), 7/30 stops over the 10% ceiling, exit replay 14/31 resolved (win 85.7%, +1.31R, PF 10.2), 17 explicitly unresolvable; 79 tests pass. 0A-ii + 5d still blocked until 1H (D-52)

- [D-55: Preserve zero dollar volume and use one mentor liquidity check](D-55-mentor-liquidity-zero-and-single-gate.md)

- [ADR-001: DuckDB as Analytics Database](0001-duckdb-analytics-database.md)
- [ADR-002: vectorbt for Backtesting](0002-vectorbt-backtesting.md)
- [ADR-003: FastAPI for API Layer](0003-fastapi-api-layer.md)
- [ADR-004: TradingView Screener for Data](0004-tradingview-screener-data.md)
- [ADR-005: Parquet Partitioning Strategy](0005-parquet-partitioning.md)
- [ADR-006: structlog for Logging](0006-structlog-logging.md)
- [ADR-007: React + TypeScript Frontend](0007-react-typescript-frontend.md)
- [ADR-008: Prometheus + Grafana Observability](0008-prometheus-grafana-observability.md)
- [ADR-009: Comprehensive Validation Infrastructure](0009-validation-infrastructure.md)
- [ADR-010: Ticker Analysis Yahoo Finance Endpoints](0010-options-news-chart-endpoints-ux.md)
- [ADR-011: Ticker Analysis Elite Trader Upgrade](0011-ticker-analysis-elite-trader-upgrade.md)

- [D-16: Prometheus Metrics](D-16-prometheus-metrics.md)
- [D-17: OpenTelemetry Optional](D-17-opentelemetry-optional.md)
- [D-18: Error Response Envelope](D-19-error-response-envelope.md)
- [D-19: Scoring Evaluation Round 2](D-20-scoring-evaluation-round2.md)
- [D-20: Scoring Smoothing & Rationale](D-21-scoring-smoothing-and-rationale.md)
- [D-21: ColumnCustomizer Portal for Z-Index Escape](D-22-column-customizer-portal-stacking.md)
- [D-22: IndicatorCache Backend for Screener Indicators](D-23-indicator-cache-backend.md)
- [D-23: Fund Instrument Detection Framework](D-24-synthesis-fund-instrument-detection.md)
- [D-24: TemplateDropdown Portal for Pointer-Events Escape](D-25-template-dropdown-portal-stacking.md)
- [D-25: Portfolio Analysis System](D-25-portfolio-analysis-system.md)
- [D-26: Trading Workflow Redesign](D-26-trading-workflow-redesign.md)
- [D-27: Professional Mode Backend Architecture](D-27-professional-mode-backend-architecture.md)
- [D-28: Professional Mode UI & Integration](D-28-professional-mode-ui-integration.md)
- [D-10: Professional Mode Architecture](D-010-professional-mode-arch.md)
- [D-29: Glass Terminal Design System & Brand Identity](D-29-glass-terminal-design-system.md)
- [D-30: Remove Header TickerTape Component](D-30-remove-header-ticker-tape.md)
- [D-31: Morning Brief Caching & Non-Blocking yfinance Fetches](D-31-morning-brief-caching.md)
- [D-32: TV Screener-First Alignment — DuckDB Optional, IndicatorCache Retired](D-32-tv-screener-first-alignment.md)
- [D-33: Synthesis Plan-Geometry Invariants & Classifier Calibration](D-33-synthesis-geometry-invariants-classifier-calibration.md)
- [D-34: Discovery Flow Redesign — Regime Weights, Snapshot Multi-Screen, RS/Catalyst/Earnings Enrichment](D-34-discovery-redesign-snapshot-multiscreen.md)
- [D-36: Chart-Reading Instrumental Fixes — Populated Return Value + MTF Confluence + Structure-None Robustness](D-36-chart-reading-mtf-confluence-fix.md)
- [D-37: Screener Plain-English Verdict + Guided Column Defaults](D-37-screener-verdict-guided-columns.md)
- [D-38: Ticker-Page Narrative Auto-Glossing — TermLink-glossed VerdictBanner thesis + trade-plan notes (persona gap #3)](D-38-ticker-narrative-auto-glossing.md)
- [D-39: Phase-1 Guided Workflow — Persistence (DuckDB) + Approved 7-Sprint Plan (persona gap #4)](D-39-phase1-persistence-and-workflow-plan.md) — item 1 **SUPERSEDED by D-40**
- [D-40: Phase-1 Workflow Persistence — SUPERSEDE DuckDB → localStorage (frontend-only)](D-40-phase1-workflow-persistence-localstorage-supersede.md)
- [D-41: Housekeeping — Retire Zombie `indicator_values` Cache + GitNexus Re-index + Frontend Build Fix](D-41-retire-indicator-values-cache.md)
- [D-42: Web Mojibake Cleanup — Reverse CP1252→UTF-8 Double-Encoding in 5 Source Files](D-42-web-mojibake-cleanup.md)
- [D-43: Ticker Analysis Technical Tab Empty — `technical.analyze()` Missing OHLCV Kwargs](D-43-technical-tab-empty-analyze-kwargs.md)
- [D-44: Data Quality Gaps Fix — Weekly SMA200 + Narration D-36 Regression + Staleness + Binary-Risk + Conviction Calibration](D-44-data-quality-gaps-fix.md)
- [D-45: Momentum Regime Boost — Catch Post-Earnings Drift (Phase 1 of Regime-Native Overhaul)](D-45-momentum-regime-boost.md)
- [D-46: Five Missing Elite Trader Features (Catalyst Data Layer — Macro Context, Sector RS, Analyst Revisions, Insider Cluster, Options Flow)](D-46-elite-trader-catalyst-data.md)
- [D-47: Catalyst-Enriched Screener + Paper Trading Workflow (Phase 3 PR 1 — confluence filter, daily ritual, trade log)](D-47-catalyst-screener-paper-trading.md)
- [D-48: Real-Time Earnings Calendar (Phase 3 PR 2 — yfinance-backed, replaces empty hand-curated JSON)](D-48-yfinance-earnings-calendar.md)
- [D-50: Paper-Trade Measurement Loop - Exit-Capture Schema + Void the 2026-09 Bypass Cohort](D-50-paper-trade-exit-capture-schema.md) - 21-column schema, rejection log, cohort voided, README drift fixed; measurement before enforcement — **schema + one statistic AMENDED by D-51**
- [D-51: Paper-Trade Schema v2 (29 columns) + Gate Sequencing - Ship Enforcement Now, Defer the R:R Floor](D-51-paper-trade-schema-v2-and-gate-sequencing.md) - **amends D-50**; 21→29 cols (21 ENTRY + 8 EXIT), `shares` moved to ENTRY, adds `entry_low`/`entry_high`/`risk_reward_planned`/`gate_version`/`account_value`/`entry_type`/`gate_verdict`/`gate_failed_step`; corrects the "(7%)" R:R figure (T1-based → T2-based 11/30 = 37%, and *neither* is a selectivity measure); single exit for v1 (D9); gate ships with 5a/5b/5c, R:R floor deferred to 1H (REV7)
- [D-49: RESERVED](D-50-paper-trade-exit-capture-schema.md) - Windows cp1252 + `+nan%` fixes (referenced in the 2026-09-05 session log; formal record not yet written)
- **D-52: RESERVED** — phase 1H R:R source fix in `synthesis.py` (renumbered from the planning doc's original D-51 projection to avoid collision with the schema record)
- [D-53: Gate Enforcement Spine — Wave-1C Backend Gate Evaluator + Verdict Wiring](D-53-gate-enforcement-spine-wave1c.md) - **7-step gate backend evaluator implemented** (`backend/app/domain/workflow/gate.py`, `evaluate_gate`/`build_gate_input`, honest CONDITIONAL degradation, $10M ADV workflow floor incl. zero-ADV FAIL per D-55); wired last in `synthesis.synthesise()` after all conviction mutations with `gate=` on every verdict; `evaluate_stop_distance` moved + re-exported; 5d R:R floor still deferred to D-52/1H; 76 tests pass. Journal/sizing/exit slices remain reserved under this spine

## Other Decision Records
- [Phase 9: Advanced Backtest](2026-06-19-phase9-advanced-backtest.md) — ATR-based sizing, vectorized signals, parameter optimization, monte carlo, multi-symbol backtest 
32: ## Template
33: 
34: ```markdown
35: # ADR-NNN: Title
36: 
37: **Status:** [Proposed | Accepted | Deprecated | Superseded]
38: **Date:** YYYY-MM-DD
39: 
40: ## Context
41: What is the issue motivating this decision?
42: 
43: ## Decision
44: What is the chosen approach?
45: 
46: ## Consequences
47: What are the trade-offs, benefits, and risks?
48: ```
- [D-35: Education Content Single Source of Truth - education.json + Bands DSL](D-07-education-single-source-of-truth.md)
