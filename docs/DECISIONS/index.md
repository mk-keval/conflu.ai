# Architecture Decision Records

This section contains Architecture Decision Records (ADRs) for significant project decisions.

## Index

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
