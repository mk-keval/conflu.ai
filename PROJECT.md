# conflu.ai - Professional Multi-Asset Trading Platform

## Vision
Build a **production-grade, fully vectorized multi-asset trading platform** with real-time screening, backtesting, and risk management. No loops, no lag, no compromises.

## Core Requirements

### 1. Data Layer (DuckDB + Parquet + TradingView Screener)
- **Local-first storage**: DuckDB with partitioned Parquet files (year/month/symbol/timeframe)
- **Source**: `tradingview-screener` for global equity/crypto/forex screening
- **Timeframes**: 1m, 5m, 15m, 1h, 4h, 1D
- **Assets**: US Equities, Crypto (spot/perp), Forex, Commodities, Indices
- **Schema**: symbol, timestamp, open, high, low, close, volume, timeframe, asset_class

### 2. Compute Layer (Fully Vectorized - NO LOOPS)
- **vectorbt**: All backtesting, portfolio simulation, signal generation
- **pandas-ta**: 100+ technical indicators (RSI, MACD, EMA, ATR, VWAP, SuperTrend, etc.)
- **Multi-timeframe vectorization**: Compute indicators across timeframes in parallel using vectorbt's broadcasting
- **Signal Engine**: Composable signal builder (AND/OR/NOT logic, crossover, threshold, slope)

### 3. Screener (Async + Chunked + Vectorized)
- **Async chunked screening**: Process 500+ symbols concurrently using asyncio + semaphore
- **Vectorized filter pipeline**: All filters applied via boolean masks on DataFrames
- **Pre-computed indicator cache**: Store computed indicators in DuckDB for instant screening
- **Real-time WebSocket streaming**: TradingView Lightweight Charts WebSocket feed

### 4. Backtest Engine (vectorbt PRO patterns)
- **Portfolio.from_signals()**: Vectorized entry/exit, position sizing, fees, slippage
- **Walk-forward optimization**: Rolling window parameter optimization
- **Monte Carlo simulation**: 1000+ paths for confidence intervals
- **Metrics**: Sharpe, Sortino, Calmar, Max DD, Win Rate, Expectancy, SQN, Ulcer Index

### 5. Risk Engine (ATR + Beta + Correlation)
- **ATR-based position sizing**: Risk % × Account Equity / (ATR × multiplier)
- **Beta hedging**: Rolling 60-day beta vs SPY/BTC for crypto, SPY for equities
- **Correlation matrix**: 30-day rolling correlation heatmap (sector/asset class)
- **Kelly Criterion / Half-Kelly**: Optimal position sizing from backtest stats
- **Portfolio VaR / CVaR**: 95%/99% confidence levels

### 6. API Layer (FastAPI + WebSocket)
- **REST**: Screening, backtest results, indicator data, risk metrics
- **WebSocket**: Real-time price stream, indicator updates, signal alerts
- **Authentication**: JWT (optional, for future multi-user)

### 7. Frontend (React + TradingView Lightweight Charts + Tailwind)
- **Charts**: Multi-timeframe synchronized charts with indicator overlays
- **Screener Table**: Virtualized, sortable, filterable, real-time updates
- **Backtest Dashboard**: Equity curve, drawdown, trades list, metrics table
- **Risk Dashboard**: Correlation heatmap, position sizer, beta exposure

## Technical Constraints (NON-NEGOTIABLE)
1. **ZERO explicit loops** in signal/indicator computation - use vectorbt/pandas vectorization
2. **Async-first** for all I/O (data fetching, screening, API)
3. **Columnar storage** - Parquet partitioned by (asset_class, year, month, symbol, timeframe)
4. **Type safety** - Full type hints, pydantic models, strict mypy
5. **Testing** - pytest + hypothesis for property-based testing of vectorized ops

## Success Criteria
- Screen 5000+ symbols in <30 seconds (warm cache)
- Backtest 10-year daily data in <2 seconds
- WebSocket latency <50ms local
- 95%+ test coverage on compute layer
- Zero mypy errors (strict mode)