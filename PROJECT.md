# conflu.ai — Professional Multi-Asset Trading Platform

## Vision
Build a **production-grade, fully vectorized multi-asset trading platform** with TV Screener-powered discovery, confluence scoring, backtesting, and risk management. No loops, no lag, no compromises.

## Core Flow

```
TV Screener Discovery (<2s, 12K+ symbols)
  → Confluence Scoring (from TV data only)
  → Deep Analysis (on-demand: OHLCV + backtest + risk)
```

## Architecture Layers

### 1. Discovery Layer (TradingView Screener)
- **Source**: `tradingview-screener` v3.2+ — free API, 12,000+ symbols, 50+ indicators
- **Markets**: US Equities (primary, via S&P 500 index components)
- **Timeframes**: 1m–1M, multi-TF via client-side intersection
- **Filters**: 26 pre-built screener filters (price/RSI/MACD/EMA/volume/ATR/ADX/BB/fundamentals)
- **Rate Limit**: ~30 req/min free tier, 15-min delayed data

### 2. Scoring Layer (Confluence from TV data only)
- **5-factor scoring** (0–100 pts): Trend (30), Momentum (25), Volume (20), Quality (15), Fundamental (10)
- **ATR-based entry/SL/targets**: 2×ATR stop, 2:1 / 3:1 R:R
- **Rating system**: A+ (80+) → D (<40)
- **No OHLCV needed** — all data comes from TV columns

### 3. Deep Analysis (On-Demand)
- **Trigger**: User clicks "Analyze" on a TV-discovered ticker
- **Pipeline**: Load OHLCV from DuckDB → compute indicators → backtest (vectorbt) → risk (VaR/beta/Kelly)
- **Entry/Exit/SL**: ATR-based, consistent with TV confluence scoring

### 4. Data Layer (DuckDB + Parquet)
- **Local-first storage**: DuckDB with partitioned Parquet files
- **Source for deep analysis**: Historical OHLCV for backtesting + risk
- **Not needed for screening/discovery** — TV Screener handles that

### 5. Compute Layer (Fully Vectorized)
- **vectorbt**: All backtesting, portfolio simulation, signal generation
- **pandas-ta**: 100+ technical indicators for deep analysis
- **ZERO explicit loops** in signal/indicator computation

### 6. Risk Engine (ATR + Beta + Correlation)
- ATR-based position sizing, beta hedging, correlation matrix
- Kelly Criterion / Half-Kelly, portfolio VaR / CVaR

### 7. API Layer (FastAPI + WebSocket)
- REST endpoints for screening, deep analysis, backtest, risk
- WebSocket for real-time updates

### 8. Frontend (React + Tailwind)
- Screen results table, deep analysis panels, charts, risk dashboard

## Technical Constraints (NON-NEGOTIABLE)
1. **ZERO explicit loops** in signal/indicator computation
2. **Async-first** for all I/O (data fetching, screening, API)
3. **TV Screener first** — discovery always goes through TV, not local OHLCV
4. **Type safety** — Full type hints, pydantic models, strict mypy
5. **Testing** — pytest + hypothesis for property-based testing

## Success Criteria
- Screen S&P 500 in <2 seconds (down from 30s+ old approach)
- Confluence score from TV data in <100ms per ticker
- Deep analysis (full backtest + risk) in <10s per ticker
- Zero mypy errors (strict mode)

## Project Skills (for AI Agents)
- **tvscreener-specialist**: Deep knowledge of `tradingview-screener` package — every column, filter, timeframe, rate limit, and error mode
- **gitnexus-***: Code intelligence (exploring, impact analysis, debugging, refactoring)
