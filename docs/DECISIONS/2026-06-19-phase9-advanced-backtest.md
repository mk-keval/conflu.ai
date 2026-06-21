# Decision Log: Phase 9 Advanced Backtest

**Date:** 2026-06-19
**Impact:** HIGH — 23 files changed; new API routes, new engine classes, new frontend components

## Architecture Decisions

### 1. Optimization Engine Strategy
- **Decision:** BacktestOptimizer supports 3 search methods — grid, random, Bayesian (Optuna TPESampler)
- **Rationale:** Best-practice approach for hyperparameter optimization; Optuna is industry-standard for Bayesian optimization
- **Fallback:** If Optuna not installed, gracefully degrades to random search (no crash)

### 2. Regime Detection Strategy
- **Decision:** RegimeDetector uses Hidden Markov Model (hmmlearn) as primary, volatility quantile as fallback
- **Rationale:** HMM is well-suited for latent regime detection in financial time series; volatility quantile is simple and always available
- **Tradeoff:** hmmlearn required without import guard fallback (must be installed)

### 3. Report Generation Strategy
- **Decision:** ReportGenerator supports HTML (Jinja2), PDF (WeasyPrint), JSON formats
- **Rationale:** HTML for interactive browser viewing, PDF for downloadable reports, JSON for programmatic consumption
- **Tradeoff:** WeasyPrint can be difficult to install on Windows; HTML/JSON always work without it

### 4. Comparison Methodology
- **Decision:** StrategyComparator uses DuckDB for metric calculation + bootstrap p-value approximation
- **Rationale:** Direct DuckDB queries on stored results avoids data duplication; bootstrap provides statistical significance measure
- **Tradeoff:** Requires pre-computed trial results in database; no on-the-fly comparison

### 5. API Route Design
- **Decision:** 4 new POST endpoints (not GET) — optimize-v2, regimes, report, compare
- **Rationale:** POST supports complex request bodies (search spaces, configs, filters); endpoints are action-oriented
- **Note:** Keep existing backtest run endpoint as-is for backward compatibility

### 6. Frontend Architecture
- **Decision:** Tabbed interface in BacktestPage (Run / Optimize / Compare); inline components in BacktestResult (RegimeTimeline + ReportDownload)
- **Rationale:** Clean separation of concerns; new components don't change existing UI behavior
- **Integration:** BacktestResult now shows regime timeline + report download below trades table

## Files Modified
- `backend/app/core/config.py` — 4 new settings classes
- `backend/app/core/database.py` — 4 DDL constants
- `backend/app/infrastructure/backtest/models.py` — 11 new models
- `backend/app/infrastructure/backtest/__init__.py` — exports 9->22
- `backend/app/api/schemas.py` — 6 new API models
- `backend/app/api/routers/backtest.py` — 4 new POST endpoints
- `config.yaml` — 4 new config sections
- `frontend/src/types/backtest.ts` — 8 new interfaces
- `frontend/src/api/backtest.ts` — 4 new API functions
- `frontend/src/store/backtest.ts` — comparisonRunIds + 5 actions
- `frontend/src/components/backtest/index.ts` — 4 new re-exports
- `frontend/src/components/backtest/BacktestPage.tsx` — tabbed UI
- `frontend/src/components/backtest/BacktestResult.tsx` — regime + report integration
- `frontend/src/App.tsx` — new /backtest/compare route

## Files Created
- `backend/app/infrastructure/backtest/optimization.py`
- `backend/app/infrastructure/backtest/regimes.py`
- `backend/app/infrastructure/backtest/reporting.py`
- `backend/app/infrastructure/backtest/comparison.py`
- `config/report_templates/backtest_report.html`
- `frontend/src/components/backtest/OptimizationForm.tsx`
- `frontend/src/components/backtest/ComparisonDashboard.tsx`
- `frontend/src/components/backtest/RegimeTimeline.tsx`
- `frontend/src/components/backtest/ReportDownload.tsx`
