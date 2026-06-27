# Codebase Intel

## Architecture Overview

```
TradingView Screener API (remote)
  ├── tv_specialist.py — Query builder, column registry, filter map
  ├── tv_engine.py — Async orchestration (discover → score → analyze)
  └── confluence_scorer.py — 5-factor scoring from TV data only

DuckDB (local, for backtest OHLCV only)
  ├── ingest/ — Data ingestion pipeline (Phase 2, retained)
  ├── backtest/ — vectorbt-based backtesting
  └── risk/ — Risk management engine

FastAPI (backend)
  ├── routers/tv_screener.py — TV screening endpoints
  ├── routers/backtest.py — Backtest endpoints
  └── routers/risk.py — Risk endpoints
```

## Key Modules

| Module | Description |
|--------|-------------|
| `infrastructure/screener/tv_specialist.py` | TV Screener specialist — column registry, filter map, query builder |
| `infrastructure/screener/tv_engine.py` | TVScreenEngine orchestrator — discovery + scoring + deep analysis |
| `infrastructure/screener/confluence_scorer.py` | Confluence scoring from TV data only |
| `infrastructure/screener/tv_models.py` | Pydantic models |
| `infrastructure/screener/configs.py` | ScreenConfig YAML model |
| `infrastructure/analysis/deep_analysis.py` | DeepAnalysisOrchestrator — on-demand OHLCV + backtest + risk |
| `infrastructure/backtest/engine.py` | vectorbt-based backtesting engine |
| `infrastructure/risk/engine.py` | Risk management engine |
| `infrastructure/indicators.py` | pandas-ta indicator compute |
| `api/routers/tv_screener.py` | TV screening API endpoints |

## Critical Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `tradingview-screener` | >=3.2.0 | TV Screener API client |
| `vectorbt` | >=0.43.0 | Vectorized backtesting |
| `pandas-ta` | >=0.3.14b | Technical indicators |
| `duckdb` | >=1.0 | OLAP database |
| `fastapi` | >=0.115 | REST/WebSocket framework |

## TV Screener Quick Reference

```python
from tradingview_screener import Query, Column, col

# Basic screen: close > EMA50 on S&P 500
q = Query().select('close', 'RSI', 'volume', 'EMA50', 'ATR')
q.set_markets('america')
q.set_property('interval', '1D')
q.set_index('SYML:SP;SPX')
q.where(Column('close') > Column('EMA50'))
q.limit(10)
total, df = q.get_scanner_data()
# df columns: ticker, close, RSI, volume, EMA50, ATR
# total: number of matches on TV server
```

## Confluence Scoring

```python
# 5-factor confluence score from TV data only
scorer = TVConfluenceScorer()
score: ConfluenceScore = scorer.score(df_row)

# score.total = 0-100
# score.breakdown = {"trend": 30, "momentum": 25, ...}
# score.entry, score.stop_loss (2xATR), score.targets (2:1, 3:1)
# score.rating = "A+"/"A"/"B+"/"B"/"C"/"D"
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/screen/tv` | Single timeframe screen |
| POST | `/api/v1/screen/tv/multi-tf` | Multi-timeframe intersection |
| POST | `/api/v1/screen/tv/analyze` | Deep analysis (OHLCV + backtest + risk) |
| GET | `/api/v1/screen/tv/templates` | List screen templates |
| GET | `/api/v1/screen/tv/templates/{name}` | Load template by name |

## Cleanup Complete (Phase 3 ✅)

All old DuckDB-dependent files from the v0.1 architecture have been removed:

- ✅ `backend/app/infrastructure/screener/engine.py` — deleted
- ✅ `backend/app/infrastructure/screener/cache.py` — deleted
- ✅ `backend/app/infrastructure/screener/filters.py` — deleted
- ✅ `backend/app/infrastructure/screener/scoring.py` — deleted
- ✅ `backend/app/infrastructure/screener/export.py` — deleted
- ✅ `backend/app/infrastructure/screener/streaming.py` — deleted
- ✅ `backend/app/infrastructure/screener/alerts.py` — deleted
- ✅ `backend/app/infrastructure/screener/broadcasting.py` — deleted
- ✅ `backend/app/infrastructure/screener/screen_replay.py` — deleted
- ✅ `backend/app/infrastructure/screener/sharing.py` — deleted
- ✅ `backend/app/infrastructure/screener/models.py` — deleted (TV uses tv_models.py)
- ✅ `backend/app/api/routers/screener.py` — deleted
- ✅ `backend/app/api/routers/screen_crud.py` — deleted
- ✅ `backend/app/api/routers/alerts.py` — deleted
- ✅ `backend/app/api/routers/replay.py` — deleted
- ✅ `backend/app/api/routers/sharing.py` — deleted
- ✅ 7 obsolete test files deleted
- ✅ Router registrations updated

**Kept:** `indicators.py` and `indicators_extended.py` still used by `deep_analysis.py` (compute_all)`
