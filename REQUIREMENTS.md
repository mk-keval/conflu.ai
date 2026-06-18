# conflu.ai - Requirements Specification

## Functional Requirements

### FR-001: Multi-Asset Data Ingestion
- Fetch OHLCV data for 5000+ symbols across equities, crypto, forex
- Support timeframes: 1m, 5m, 15m, 1h, 4h, 1D
- Source: tradingview-screener (free, no API key required)
- Store in DuckDB with Parquet partitioning: asset_class/year/month/symbol/timeframe.parquet
- Incremental updates (append only new candles)

### FR-002: Vectorized Technical Indicators
- Compute 100+ indicators using pandas-ta (zero explicit loops)
- Multi-timeframe broadcasting via vectorbt
- Cache computed indicators in DuckDB (materialized views)
- Indicators: RSI, MACD, EMA/SMA, ATR, VWAP, SuperTrend, Bollinger Bands, Stochastic, ADX, OBV, CMF, etc.

### FR-003: Multi-Timeframe Screener
- Async chunked processing (semaphore: 50 concurrent)
- Vectorized boolean filter pipeline
- Composable filters: trend, momentum, volume, volatility, pattern
- Pre-computed indicator cache for instant re-screening
- Export results to CSV/JSON

### FR-004: Vectorized Backtesting
- vectorbt Portfolio.from_signals() for all strategies
- Support: long/short, position sizing (fixed, ATR, Kelly), fees, slippage
- Walk-forward optimization with expanding/rolling windows
- Monte Carlo simulation (1000+ paths)
- Metrics: Sharpe, Sortino, Calmar, Max DD, Win Rate, Expectancy, Profit Factor, SQN, Ulcer Index

### FR-005: Risk Management Engine
- ATR-based position sizing (risk% × equity / (ATR × mult))
- Rolling 60-day beta vs benchmark (SPY for equities, BTC for crypto)
- 30-day rolling correlation matrix
- Portfolio VaR/CVaR (historical, parametric, Monte Carlo)
- Kelly/Half-Kelly optimal sizing from backtest stats

### FR-006: REST API
- GET /api/v1/screen - run screener with filters
- GET /api/v1/backtest - run backtest with strategy config
- GET /api/v1/indicators/{symbol} - get indicator values
- GET /api/v1/risk/{symbol} - get risk metrics
- GET /api/v1/data/{symbol} - get OHLCV data
- WebSocket /api/v1/ws/stream - real-time price/indicator updates

### FR-007: Frontend Dashboard
- Screener: Virtualized table (react-window), real-time updates, sortable/filterable columns
- Charts: TradingView Lightweight Charts, multi-timeframe sync, indicator overlays
- Backtest: Equity curve, drawdown chart, trades table, metrics cards
- Risk: Correlation heatmap, position size calculator, beta exposure

## Non-Functional Requirements

### NFR-001: Performance
- Screen 5000 symbols < 30s (warm DuckDB cache)
- Backtest 10yr daily < 2s (vectorbt)
- WebSocket latency < 50ms (local)
- API p99 < 200ms

### NFR-002: Reliability
- 95%+ test coverage on compute layer
- Zero data loss on incremental updates
- Graceful degradation on data source failures

### NFR-003: Maintainability
- Strict mypy (--strict) passes
- Full type hints on all public APIs
- Pydantic models for all request/response
- Comprehensive docstrings

### NFR-004: Observability
- Structured logging (structlog)
- Metrics (Prometheus) on API latency, cache hit rate
- Distributed tracing (OpenTelemetry) ready

## Constraints
- 100% open-source dependencies (no paid APIs)
- Python 3.11+ backend, Node 20+ frontend
- DuckDB for local analytics (no external DB required)
- Docker Compose for local dev