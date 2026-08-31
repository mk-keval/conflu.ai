# Architecture Decision Records

This section contains Architecture Decision Records (ADRs) for significant project decisions.

## Index

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
