# conflu.ai - Project Roadmap

## Milestone: v0.1 Foundation

### Phase 1: Foundation & Core Infrastructure
**Goal:** Establish core infrastructure — configuration management, DuckDB connection pool, vectorbt/pandas-ta compute primitives, structured logging, type-safe schemas, test infrastructure

**Success Criteria**:
1. DuckDB connection pool with context managers implemented
2. Parquet partitioning schema (asset_class/year/month/symbol/timeframe) defined
3. vectorbt + pandas-ta compute primitives (zero-loop indicator functions)
4. Pydantic models for all domain entities (OHLCV, Signal, Position, Trade, Metrics)
5. Structured logging (structlog) with correlation IDs
6. pytest + hypothesis test infrastructure configured
7. mypy strict mode passing
8. Docker Compose for local dev

**Plans:** 0

---

### Phase 2: Data Ingestion Pipeline
**Goal:** tradingview-screener integration, async chunked fetching, incremental Parquet updates, multi-asset support (equities, crypto, forex, commodities, indices)

**Success Criteria**:
1. tradingview-screener wrapper with rate limiting and retry logic
2. Async chunked fetching (semaphore: 50 concurrent) for 5000+ symbols
3. Incremental Parquet updates (append new candles only)
4. Multi-asset support with proper symbol normalization
5. Data quality validation (no gaps, no duplicates, OHLC consistency)

**Plans:** 0
**Depends on:** Phase 1

---

### Phase 3: Screener Engine
**Goal:** Multi-timeframe vectorized screening, composable filter pipeline, pre-computed indicator cache, real-time WebSocket streaming

**Success Criteria**:
1. Vectorized boolean filter pipeline (trend, momentum, volume, volatility, pattern)
2. Pre-computed indicator cache in DuckDB (materialized views)
3. Multi-timeframe broadcasting via vectorbt
4. Real-time WebSocket price/indicator streaming
5. Export results to CSV/JSON

**Plans:** 0
**Depends on:** Phase 1, Phase 2

---

### Phase 4: Backtest Engine
**Goal:** vectorbt Portfolio simulation, walk-forward optimization, Monte Carlo, comprehensive metrics

**Success Criteria**:
1. Portfolio.from_signals() with position sizing (fixed, ATR, Kelly), fees, slippage
2. Walk-forward optimization (expanding/rolling windows)
3. Monte Carlo simulation (1000+ paths) with confidence intervals
4. Metrics: Sharpe, Sortino, Calmar, Max DD, Win Rate, Expectancy, Profit Factor, SQN, Ulcer Index
5. Trade ledger with entry/exit timestamps, PnL, MAE/MFE

**Plans:** 0
**Depends on:** Phase 1, Phase 3

---

## Milestone: v0.2 Risk & API

### Phase 5: Risk Management Engine
**Goal:** ATR position sizing, beta hedging, correlation matrix, VaR/CVaR, Kelly optimization

**Success Criteria**:
1. ATR-based position sizing (risk% × equity / (ATR × multiplier))
2. Rolling 60-day beta vs benchmark (SPY for equities, BTC for crypto)
3. 30-day rolling correlation heatmap (sector/asset class)
4. Portfolio VaR/CVaR (historical, parametric, Monte Carlo) at 95%/99%
5. Kelly/Half-Kelly optimal sizing from backtest statistics

**Plans:** 0
**Depends on:** Phase 1, Phase 4

---

### Phase 6: API Layer
**Goal:** FastAPI REST + WebSocket, authentication, rate limiting, observability

**Success Criteria**:
1. REST endpoints: /screen, /backtest, /indicators/{symbol}, /risk/{symbol}, /data/{symbol}
2. WebSocket: /ws/stream for real-time price/indicator/signal updates
3. JWT authentication (optional, for future multi-user)
4. Rate limiting (token bucket)
5. Structured logging, Prometheus metrics, OpenTelemetry ready

**Plans:** 0
**Depends on:** Phase 1, Phase 3, Phase 4, Phase 5

---

### Phase 7: Frontend Core
**Goal:** React + TradingView Lightweight Charts + Tailwind, screener table, multi-timeframe charts, backtest dashboard

**Success Criteria**:
1. Screener: virtualized table (react-window), real-time updates, sortable/filterable columns
2. Charts: multi-timeframe synchronized charts with indicator overlays
3. Backtest: equity curve, drawdown chart, trades table, metrics cards
4. Risk: correlation heatmap, position size calculator, beta exposure view

**Plans:** 0
**Depends on:** Phase 6

---

## Milestone: v0.3 Polish & Production

### Phase 8: Advanced Screener
**Goal:** Saved screens, alerts, real-time WebSocket streaming, screen sharing

**Success Criteria**:
1. Save/load screen configurations
2. Price/indicator/signal alerts with WebSocket push
3. Screen sharing via URL
4. Historical screen backtest (replay)

**Plans:** 0
**Depends on:** Phase 3, Phase 7

---

### Phase 9: Advanced Backtest
**Goal:** Parameter optimization, regime detection, automated report generation

**Success Criteria**:
1. Grid/random/Bayesian parameter optimization
2. Market regime detection (HMM, volatility regimes)
3. PDF/HTML report generation with charts
4. Strategy comparison dashboard

**Plans:** 0
**Depends on:** Phase 4, Phase 7

---

### Phase 10: Production Hardening
**Goal:** CI/CD, Docker, monitoring, documentation, performance tuning

**Success Criteria**:
1. GitHub Actions CI/CD (lint, type-check, test, build, deploy)
2. Multi-stage Dockerfile (dev, prod)
3. Prometheus/Grafana dashboards
4. Comprehensive documentation (API, architecture, user guide)
5. Performance benchmarks: 5000 symbols < 30s, 10yr backtest < 2s

**Plans:** 0
**Depends on:** All prior phases