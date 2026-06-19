# ARCHITECTURE.md

## Project: conflu.ai — Trading Intelligence Platform

A modular trading platform with DuckDB-based storage, TradingView data ingestion, and async analysis pipeline.

## Directory Structure

```
backend/
├── app/
│   ├── core/              # Shared infrastructure
│   │   ├── config.py      # Pydantic settings (6 classes)
│   │   ├── database.py    # DuckDB connection + DDL + partition utils
│   │   └── logging.py     # structlog with correlation IDs
│   ├── domain/            # Domain models
│   │   └── models.py      # 8 frozen Pydantic models
│   ├── infrastructure/    # Technical implementations
│   │   ├── indicators.py  # @indicator decorator + 5 indicators
│   │   ├── ingest/        # Data ingestion pipeline
│   │   └── risk/          # Risk management engine
│   │       ├── __init__.py  # run_ingestion() orchestrator
│   │       ├── cli.py       # argparse CLI entry point
│   │       ├── scanner.py   # TradingView scanner + retry + circuit breaker
│   │       ├── symbol_map.py # TickerResolver (internal ↔ TV ticker)
│   │       ├── quality.py   # OHLCV validation (6 checks)
│   │       ├── models.py    # Ingestion-specific Pydantic models
│   │       ├── fetcher.py   # IngestionFetcher (semaphore + chunking)
│   │       ├── writer.py    # Incremental Parquet writer
│   │       └── metrics.py   # IngestionMetrics + health persistence
│   │   └── risk/          # Risk management engine
│   │       ├── __init__.py   # 20+ symbol exports
│   │       ├── models.py    # 8 frozen Pydantic models (BetaResult, VaRResult, etc.)
│   │       ├── beta.py      # BetaHedger — vectorized rolling beta, OLS, hedge ratio
│   │       ├── correlation.py # CorrelationAnalyzer — Pearson, sector agg, diversification
│   │       ├── var.py       # VaRCalculator — 3 methods (historical/parametric/MC)
│   │       ├── kelly.py     # KellyOptimizer — D-15 fractional Kelly, D-17 validation
│   │       ├── position_sizing.py # PositionSizingRefiner — 4 constraint layers
│   │       ├── engine.py    # RiskEngine — async orchestrator, composite risk score, alerts
│   │       ├── streaming.py # RiskStreamManager — WebSocket lifecycle, sequencing, replay
│   │       ├── metrics.py   # RiskMetricsComputer — risk-adjusted return metrics
│   │       └── reporting.py # RiskReportGenerator — HTML reports with inline CSS
│   └── api/               # FastAPI routes (future)
├── tests/
│   ├── conftest.py        # Shared fixtures
│   ├── test_config.py     # 11 tests
│   ├── test_database.py   # 7 tests
│   ├── test_models.py     # 12 tests
│   ├── test_indicators.py # 8 tests
│   ├── test_logging.py    # 6 tests
│   ├── test_ingest_scanner.py         # 7 tests
│   ├── test_ingest_symbol_map.py       # 11 tests
│   ├── test_ingest_quality.py         # 8 tests
│   ├── test_ingest_models.py          # 7 tests
│   ├── test_ingest_fetcher.py         # 6 tests
│   ├── test_ingest_writer.py          # 4 tests
│   ├── test_ingest_metrics.py         # 7 tests
│   ├── test_ingest_cli.py             # 11 tests
│   ├── test_risk_models.py            # 16 tests
│   ├── test_risk_beta.py              # 6 tests
│   ├── test_risk_correlation.py       # 5 tests
│   ├── test_risk_var.py               # 8 tests
│   ├── test_risk_kelly.py             # 7 tests
│   ├── test_risk_position_sizing.py   # 4 tests
│   ├── test_risk_streaming.py         # 7 tests
│   └── test_risk_engine.py            # 9 tests
│   ├── test_risk_models.py            # 16 tests
│   ├── test_risk_beta.py              # 6 tests
│   ├── test_risk_correlation.py       # 5 tests
│   ├── test_risk_var.py               # 8 tests
│   ├── test_risk_kelly.py             # 7 tests
│   ├── test_risk_position_sizing.py   # 4 tests
│   ├── test_risk_streaming.py         # 7 tests
│   └── test_risk_engine.py            # 9 tests
config.yaml              # Shared YAML configuration
Dockerfile               # Multi-stage Python build
docker-compose.yml       # 3 services: api, worker, redis
pyproject.toml           # Build config + deps + linting
```

## Data Flow

```
TradingView Scanner
    ↓ scan_with_retry() [circuit breaker + exponential backoff]
IngestionFetcher.fetch_asset_class()
    ↓ (semaphore 50, batch size 100)
QualityReport ← validate_ohlcv()
    ↓
write_incremental() [DuckDB staging table dedup]
    ↓
Parquet partitions: {asset_class}/{year}/{month}/{symbol}_{timeframe}.parquet
    ↓
DuckDB ohlcv table (parquet-backed)
```

## Key Design Decisions

- DuckDB as primary store (zero-config, columnar, Parquet-native)
- Append-only Parquet with idempotent incremental updates
- TradingView free tier (no API key needed)
- Semaphore-based concurrency (no unbounded parallelism)
- Partial failures don't stop pipeline (D-15)
- DuckDB 1.x has no SERIAL/GENERATED AS IDENTITY → manual id via MAX(id)+1
