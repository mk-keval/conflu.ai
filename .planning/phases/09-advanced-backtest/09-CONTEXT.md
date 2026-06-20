# Phase 9: Advanced Backtest - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Advanced Backtest: Build on the Phase 4 backtest engine and Phase 7/8 frontend foundation to add parameter optimization, market regime detection, automated report generation, and strategy comparison capabilities. This phase transforms the backtest engine from a single-run tool into a comprehensive strategy research and validation platform.
</domain>

<decisions>
## Implementation Decisions

### Parameter Optimization
- **D-01:** Support three optimization modes: Grid search (exhaustive), Random search (efficient exploration), Bayesian optimization (Optuna integration for intelligent parameter search).
- **D-02:** Optimization space defined per strategy: each strategy declares its optimizable parameters with bounds, types (int/float/categorical), and optional constraints.
- **D-03:** Multi-objective support: optimize for multiple metrics simultaneously (Sharpe, Sortino, Max DD, Win Rate) with configurable weights or Pareto frontier.
- **D-04:** Walk-forward integration: Optimization runs within walk-forward folds to prevent overfitting. Expanding/rolling window modes supported.
- **D-05:** Early stopping: Prune unpromising trials based on intermediate results (e.g., median stopping rule, minimum improvement threshold).
- **D-06:** Parallel execution: Distribute trials across CPU cores using joblib or Dask. Configurable max parallel jobs.

### Market Regime Detection
- **D-07:** Hidden Markov Model (HMM) for regime detection: 2-4 state Gaussian HMM on returns/volatility. Train on rolling window (default 252 days), infer current regime.
- **D-08:** Alternative: Volatility regime detection via GARCH(1,1) or rolling volatility quantiles (simpler, no HMM dependency).
- **D-09:** Regime features: Volatility level, trend direction, correlation structure. Output: regime label per timestamp.
- **D-10:** Regime-aware backtesting: Apply different strategy parameters per regime. Strategy config includes regime-specific parameter overrides.
- **D-11:** Regime transition alerts: Detect regime changes in real-time via WebSocket (reusing Phase 6/7 WS infrastructure).

### Automated Report Generation
- **D-13:** Report templates: HTML (WeasyPrint for PDF) and Jinja2 templates for HTML. Sections: Executive summary, parameter settings, equity curve, drawdown analysis, trade analysis, risk metrics, regime analysis, conclusion.
- **D-14:** Report formats: HTML (interactive with Plotly.js), PDF (WeasyPrint), JSON (raw data). One-click download from backtest results page.
- **D-15:** Report scheduling: Generate automatically on backtest completion, or on-demand via API. Store in `backtest_reports` table with metadata.
- **D-16:** Template customization: User-defined sections, branding (logo, colors), custom metrics.

### Strategy Comparison
- **D-17:** Multi-backtest comparison: Run multiple strategies/configs side-by-side. Unified results view with aligned time axes.
- **D-18:** Visualization: Overlaid equity curves (normalized), drawdown overlays, rolling metric charts (Sharpe, DD, win rate), metric comparison table with statistical significance tests (t-test, bootstrap).
- **D-19:** Statistical significance: Pairwise comparison with bootstrapped confidence intervals. Highlight statistically significant differences.
- **D-20:** Strategy versioning: Link comparison to specific strategy versions (from Phase 8 screen configs). Support A/B/C... labeling.

### Configuration
- **D-21:** BacktestSettings extension: `optimization` (enabled, mode, max_trials, timeout_s), `regime_detection` (enabled, method, window), `reporting` (enabled, formats, template), `comparison` (enabled, max_strategies).
- **D-22:** API key management for external optimization services (Optuna dashboard URL, optional).

### Frontend Integration
- **D-23:** Backtest page: "Optimize" tab with parameter space builder, live trial progress, Pareto frontier visualization.
- **D-24:** "Regimes" tab in backtest results: regime timeline overlay, regime-specific metrics.
- **D-25:** Report viewer: Interactive HTML with download buttons (HTML/PDF/JSON). Strategy comparison page with synchronized charts.

### OpenCode's Discretion
- **D-25:** Exact Optuna integration pattern (storage: DuckDB vs SQLite vs PostgreSQL).
- **D-26:** HMM library choice (hmmlearn vs custom implementation vs regime-switching library).
- **D-27:** Report template system (Jinja2 + WeasyPrint vs ReportLab vs custom).
- **D-28:** Statistical test library (scipy.stats vs pingouin vs custom bootstrap).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1-4-8 Foundations
- `.planning/phases/04-backtest-engine/04-CONTEXT.md` — Backtest engine decisions
- `.planning/phases/04-backtest-engine/04-RESEARCH.md` — VectorBT patterns, walk-forward, Monte Carlo
- `.planning/phases/07-frontend-core/07-CONTEXT.md` — Frontend architecture decisions
- `.planning/phases/07-frontend-core/07-RESEARCH.md` — Frontend patterns (React Query, Lightweight Charts, Zustand)

### Existing Code Assets
- `backend/app/infrastructure/backtest/engine.py` — BacktestEngine, walk-forward, Monte Carlo
- `backend/app/infrastructure/backtest/metrics.py` — MetricsComputer
- `backend/app/infrastructure/backtest/ledger.py` — TradeLedger, MAE/MFE
- `backend/app/infrastructure/backtest/models.py` — BacktestRunConfig, BacktestRunRecord
- `backend/app/api/routers/backtest.py` — Phase 6 backtest endpoints
- `backend/app/infrastructure/backtest/walk_forward.py` — WalkForwardOptimizer pattern
- `backend/app/infrastructure/backtest/monte_carlo.py` — MonteCarloSimulator
- `backend/app/infrastructure/backtest/sizing.py` — PositionSizer (fixed, ATR, Kelly)
- `frontend/src/components/backtest/` — BacktestPage, EquityCurveChart, DrawdownChart, MetricsCards, TradesTable

### Project Requirements
- `REQUIREMENTS.md` — FR-012 (Optimization), FR-013 (Regime Detection), FR-014 (Reports), FR-015 (Comparison)
- `.planning/ROADMAP.md` — Phase 9 success criteria

### External Documentation
- Optuna: https://optuna.org/
- hmmlearn: https://hmmlearn.readthedocs.io/
- WeasyPrint: https://weasyprint.org/
- Jinja2: https://jinja.palletsprojects.com/
- SciPy stats: https://docs.scipy.org/doc/scipy/reference/stats.html

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (from Phases 4, 7)
- `WalkForwardOptimizer` in `backtest/walk_forward.py` — Expanding/rolling windows, grid search, result aggregation
- `MonteCarloSimulator` in `monte_carlo.py` — Bootstrap/block bootstrap, path generation, percentile computation
- `MetricsComputer` in `metrics.py` — 10+ metrics, extendable
- `BacktestEngine` — `run()`, `run_walk_forward()`, `run_monte_carlo()` methods
- `PositionSizer` — Fixed, ATR, Kelly sizing; extensible for regime-aware sizing
- `Backend app.api.routers.backtest` — REST endpoints for run, optimize, monte-carlo
- Frontend: `BacktestPage`, `EquityCurveChart`, `DrawdownChart`, `TradesTable`, `MetricsCards`, `TradeDetail`, `BacktestResultPage`

### Established Patterns
- `@dataclass` + Pydantic for config objects, frozen models
- Vectorized pandas/numpy operations (no loops over symbols)
- DuckDB for storage, Parquet for data
- Async-first with `asyncio.to_thread` for CPU-bound work
- Pydantic models for request/response, frozen=True, extra="forbid"

### Integration Points
- Phase 4 backtest engine → optimization wraps `BacktestEngine.run()`
- Phase 4 Monte Carlo → reuse `MonteCarloSimulator` for MC VaR and optimization sampling
- Phase 7 frontend → backtest dashboard, new tabs for optimization/regimes/reports
- Phase 6 API → new endpoints for optimize, regimes, reports, compare
- Phase 8 risk engine → reuse VaR/CVaR, Kelly from risk engine

</code_context>

<specifics>
## Specific Ideas

- Optimization: Start with grid search (exhaustive), then random, then Optuna TPE for efficiency
- Regime detection: Start with simple volatility quantile buckets (4 regimes), upgrade to HMM
- Reports: HTML first (easy via Jinja2 + Plotly), PDF via WeasyPrint as enhancement
- Comparison: REST endpoint `POST /api/v1/backtest/compare` with array of configs
- Regime-aware backtest: Pass regime labels to `BacktestEngine.run()` for per-regime sizing

</specifics>

<deferred>
## Deferred Ideas

- Multi-objective Pareto optimization with interactive frontier exploration
- Genetic algorithm for parameter search (DEAP library)
- Factor model risk attribution in reports (Fama-French, PCA)
- Live paper trading integration from optimized params
- Distributed optimization across multiple machines (Ray/Dask)

None — discussion stayed within phase scope
</deferred>

---

*Phase: 9-Advanced Backtest*
*Context gathered: 2026-06-20*