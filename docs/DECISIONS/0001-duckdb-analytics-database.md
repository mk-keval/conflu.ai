# ADR-001: DuckDB as Analytics Database

**Status:** Accepted
**Date:** 2026-06-18

## Context
Need an embedded analytical database for local-first trading data storage. Requirements: columnar storage, SQL interface, no external server, Parquet support.

## Decision
Use DuckDB as the primary analytics database with Parquet partitioning by asset_class/year/month/symbol/timeframe.

## Consequences
- **Positive**: Zero-config, embedded, fast analytical queries, native Parquet support
- **Negative**: Not suitable for OLTP workloads, no built-in replication
- **Mitigation**: DuckDB used only for analytics; Redis for caching/queues
