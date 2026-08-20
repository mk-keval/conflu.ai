# ADR-001: DuckDB as Optional Analytics Database (Backtest/Risk OHLCV Only)

**Status:** Accepted (amended 2026-08-16)
**Date:** 2026-06-18

## Context
Need an embedded analytical database for optional local historical OHLCV storage used by on-demand deep analysis (backtest + risk). Requirements: columnar storage, SQL interface, no external server, Parquet support.

## Decision
Use DuckDB as the **optional, non-load-bearing** analytics store for historical OHLCV used by backtesting and risk metrics, with Parquet partitioning by asset_class/year/month/symbol/timeframe.

**Critical scope statement:** DuckDB is **NOT** part of the discovery, screening, scoring, or analysis paths. The system architecture is **TradingView Screener-first** (ADR-004): all ticker discovery and confluence scoring happen live against TradingView columns with **no OHLCV dependency**. Charts, indicators, ticker analysis, regime detection, sector rotation, and the Morning Brief all fetch data **live and on-demand** from TradingView / Yahoo Finance. DuckDB exists only as an optional cache for the on-demand `DeepAnalysisOrchestrator` (backtest + risk). Nothing user-facing requires it, and the app must never block on it.

## Consequences
- **Positive**: Zero-config, embedded, fast analytical queries, native Parquet support
- **Positive**: No traditional "fetch huge data overnight + precompute indicators" pipeline is load-bearing — the smart system is the live TV screener
- **Negative**: Not suitable for OLTP workloads, no built-in replication
- **Mitigation**: DuckDB used only for optional backtest/risk analytics; Redis for caching/queues
- **Mitigation**: If DuckDB/backtest data is missing or stale, screening, charts, indicators, and analysis must continue to work (they already do — they never read DuckDB)
