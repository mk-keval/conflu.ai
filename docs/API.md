# API Reference — conflu.ai

**Last Updated:** 2026-06-19

## Base URL
`/api/v1`

---

## Backtest API (`/api/v1/backtest`)
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/` | Run a new backtest |
| GET | `/{run_id}` | Get backtest run status & metrics |
| POST | `/optimize-v2` | Run parameter optimization (grid/random/bayesian) |
| POST | `/{run_id}/regimes` | Detect market regimes for a completed run |
| POST | `/{run_id}/report` | Generate backtest report (HTML/PDF/JSON) |
| POST | `/compare` | Compare multiple backtest runs |
| GET | `/{run_id}/trades` | Get trades for a backtest run |
| GET | `/{run_id}/equity` | Get equity curve for a backtest run |
| GET | `/{run_id}/timeline` | Get regime timeline for a backtest run (from regimes table) |
| GET | `/{run_id}/optimization` | Get optimization results for a run |

## Request/Response Schemas

### POST `/backtest/` (existing)
- **Body:** Symbol, startDate, endDate, initialCapital, strategy config, tradeConfig
- **Response:** runId, status, metrics

### POST `/backtest/optimize-v2`
- **Request:** `OptimizeRequest` — symbol, dates, initialCapital, strategyParams, searchSpace (OptimizationSearchSpace with method, parameters, objectives, maxTrials)
- **Response:** `OptimizeResponse` — bestParams, bestObjective, totalTrials, trials[], elapsed

### POST `/backtest/{run_id}/regimes`
- **Request:** `RegimeRequest` — method (hmm/volatility), nRegimes, lookback
- **Response:** `RegimeResult[]` — date, regime, probability, volatility

### POST `/backtest/{run_id}/report`
- **Request:** `ReportRequest` — formats (html/pdf/json), includeCharts, includeTrades
- **Response:** `ReportResult[]` — format, reportId, downloadUrl, generatedAt

### POST `/backtest/compare`
- **Request:** `CompareRequest` — runIds[], metrics[], normalize
- **Response:** `StrategyComparisonResult` — comparisons[] with metrics, equityCurves[]

## Websocket Events
- `backtest.progress` — Real-time progress updates during backtest execution
- `backtest.complete` — Final result notification
- Channel: `backtest:${runId}`
