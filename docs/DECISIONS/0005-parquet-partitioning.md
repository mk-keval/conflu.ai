# ADR-005: Parquet Partitioning Strategy

**Status:** Accepted
**Date:** 2026-06-18

## Context
Need an efficient storage format for time-series OHLCV data that supports fast analytical queries, incremental updates, and columnar compression.

## Decision
Store OHLCV data in Parquet format with hierarchical partitioning: asset_class/year/month/symbol/timeframe. Use DuckDB for SQL querying over partitioned Parquet files.

## Consequences
- **Positive**: Excellent compression, predicate pushdown for fast queries, incremental append-only updates
- **Negative**: Not ideal for point lookups or frequent small writes
- **Mitigation**: Redis for hot data caching, batch ingestion pipeline
