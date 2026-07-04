# conflu.ai — Requirements Specification

## Overview
conflu.ai is a **TradingView Screener-first** trading intelligence platform. Discovery always goes through TV Screener (12K+ symbols, <2s). Local OHLCV (DuckDB) is used only for on-demand deep analysis (backtesting + risk). No local screener engine — TV Screener handles all discovery.

---

## Functional Requirements

### FR-001: TV Screener Discovery
- Screen 12,000+ symbols via `tradingview-screener` v3.2+ (free API, no key required)
- Support timeframes: 1D (primary), 4H, 1H, 15m
- Markets: US Equities (S&P 500 components), expandable to crypto/forex
- Rate limit: ~30 req/min free tier, 15-min delayed data
- Multi-TF via client-side intersection with weighted aggregation

### FR-002: Confluence Scoring (TV Data Only)
- 5-factor scoring (0–100 pts): Trend (30), Momentum (25), Volume (20), Quality (15), Fundamental (10)
- All data from TV columns — no OHLCV needed for screening
- ATR-based entry/SL/targets from TV ATR column
- Rating system: A+ (80+) → D (<40)
- MTF weighted stacking: Daily (0.50), 4H (0.25), Weekly (0.25)
- SHORT screen support: Breakdown, Short Squeeze, Distribution

### FR-003: Screen-as-YAML Config
- All screens defined as YAML templates in `config/screens/*.yaml`
- No code changes needed for new screens (pure config)
- 8 pre-built templates: Breakout, Trend Follower, Mean Reversion, Oversold Bounce, Volume Surge, Breakdown, Short Squeeze, Distribution
- 20+ FILTER_MAP entries mapping screen filters to TV Column operations

### FR-004: On-Demand Deep Analysis
- **Trigger**: User clicks "Analyze" on a TV-discovered ticker
- Load OHLCV from DuckDB → compute indicators (pandas-ta) → backtest (vectorbt) → risk (VaR/beta/Kelly)
- ATR-based entry/SL/targets (consistent with TV confluence scoring)

### FR-005: Vectorized Backtesting
- vectorbt `Portfolio.from_signals()` for all strategies
- Support: long/short, position sizing (fixed, ATR, Kelly), fees, slippage
- Walk-forward optimization with expanding/rolling windows
- Monte Carlo simulation (1000+ paths)
- Metrics: Sharpe, Sortino, Calmar, Max DD, Win Rate, Expectancy, Profit Factor, SQN, Ulcer Index

### FR-006: Risk Management Engine
- ATR-based position sizing (risk% × equity / (ATR × mult))
- Rolling 60-day beta vs benchmark (SPY for equities, BTC for crypto)
- 30-day rolling correlation matrix
- Portfolio VaR/CVaR (historical, parametric, Monte Carlo)
- Kelly/Half-Kelly optimal sizing from backtest stats

### FR-007: REST API
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/v1/screen` | Run TV Screener with config |
| POST | `/api/v1/backtest` | Run backtest with strategy config |
| GET | `/api/v1/data/{symbol}` | Get OHLCV data |
| GET | `/api/v1/data/indicators/{symbol}` | Get indicator values |
| GET | `/api/v1/risk/{symbol}` | Get risk metrics |
| WebSocket | `/ws/stream` | Real-time price/indicator updates |

### FR-008: Frontend Dashboard
- Screener: Virtualized table, sortable columns, multi-template selector, detail panel
- Charts: TradingView Lightweight Charts, multi-timeframe grid, indicator overlays
- Backtest: Equity curve, drawdown chart, trades table, metrics cards
- Risk: Correlation heatmap, position size calculator, beta exposure

---

## Non-Functional Requirements

### NFR-001: Performance
- Screen 12,000+ symbols via TV API in <2s
- Confluence score in <100ms per ticker
- Deep analysis (full backtest + risk) in <10s per ticker
- WebSocket latency <50ms (local)
- API p99 <200ms

### NFR-002: Reliability
- 95%+ test coverage on compute layer
- Graceful degradation on data source failures (rate limits, timeouts)
- Idempotent incremental OHLCV updates (no data loss)

### NFR-003: Maintainability
- Strict mypy (`--strict`) passes
- Full type hints on all public APIs
- Pydantic models for all request/response (frozen, extra=forbid)
- YAML-driven screen configs (no code for new screens)

### NFR-004: Observability
- Structured logging (structlog with correlation IDs)
- Prometheus metrics on API latency, cache hit rate
- OpenTelemetry tracing (optional, console exporter if no OTLP endpoint)

## Constraints
- 100% open-source dependencies (no paid APIs)
- Python 3.11+ backend, Node 20+ frontend
- DuckDB for local OHLCV storage (no external DB required)
- Docker Compose for local dev (opt-in observability profile)
- TradingView Screener free tier (30 req/min, 15-min delayed data)
