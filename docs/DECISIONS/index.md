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

- [D-16: Prometheus Metrics](D-16-prometheus-metrics.md)
- [D-17: OpenTelemetry Optional](D-17-opentelemetry-optional.md)
- [D-19: Error Response Envelope](D-19-error-response-envelope.md)
- [D-20: Scoring Evaluation Round 2](D-20-scoring-evaluation-round2.md)
- [D-21: Scoring Smoothing & Rationale](D-21-scoring-smoothing-and-rationale.md)
- [D-22: ColumnCustomizer Portal for Z-Index Escape](D-22-column-customizer-portal-stacking.md)
- [D-23: IndicatorCache Backend for Screener Indicators](D-23-indicator-cache-backend.md)
- [D-24: Fund Instrument Detection Framework](D-24-synthesis-fund-instrument-detection.md)

## Other Decision Records
- [Phase 9: Advanced Backtest](2026-06-19-phase9-advanced-backtest.md) — ATR-based sizing, vectorized signals, parameter optimization, monte carlo, multi-symbol backtest

## Template

```markdown
# ADR-NNN: Title

**Status:** [Proposed | Accepted | Deprecated | Superseded]
**Date:** YYYY-MM-DD

## Context
What is the issue motivating this decision?

## Decision
What is the chosen approach?

## Consequences
What are the trade-offs, benefits, and risks?
```
