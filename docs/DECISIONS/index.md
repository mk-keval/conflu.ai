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

- [D-16: Prometheus Metrics](D-16-prometheus-metrics.md)
- [D-17: OpenTelemetry Optional](D-17-opentelemetry-optional.md)
- [D-18: Error Response Envelope](D-19-error-response-envelope.md)
- [D-19: Scoring Evaluation Round 2](D-20-scoring-evaluation-round2.md)
- [D-20: Scoring Smoothing & Rationale](D-21-scoring-smoothing-and-rationale.md)
- [D-21: ColumnCustomizer Portal for Z-Index Escape](D-22-column-customizer-portal-stacking.md)
25: - [D-22: IndicatorCache Backend for Screener Indicators](D-23-indicator-cache-backend.md)
26: - [D-23: Fund Instrument Detection Framework](D-24-synthesis-fund-instrument-detection.md)
27: - [D-24: TemplateDropdown Portal for Pointer-Events Escape](D-25-template-dropdown-portal-stacking.md)
28: 
29: ## Other Decision Records
30: - [Phase 9: Advanced Backtest](2026-06-19-phase9-advanced-backtest.md) — ATR-based sizing, vectorized signals, parameter optimization, monte carlo, multi-symbol backtest
31: 
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
