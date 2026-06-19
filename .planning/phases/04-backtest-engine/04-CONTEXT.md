# Phase 4: Backtest Engine - Context

**Gathered:** 2026-06-19
**Status:** Ready for planning

<domain>
## Phase Boundary

VectorBT Portfolio simulation, walk-forward optimization, Monte Carlo simulation, comprehensive metrics, and trade ledger. This phase delivers the backtest engine that consumes signals from Phase 3 (Screener) and feeds risk analysis (Phase 5) and API (Phase 6).
</domain>

<decisions>
## Implementation Decisions

### VectorBT Portfolio Configuration
- **D-01:** Use `vbt.Portfolio.from_signals()` as the core entry point. All position sizing, fees, slippage handled via vectorbt native parameters.
- **D-02:** Support three position sizing modes: Fixed (units/cash), ATR-based (risk % × equity / (ATR × mult)), Kelly Criterion (f = p - q/b from backtest stats).
- **D-03:** Fees and slippage: `fees` as bps (default 10bps), `slippage` as bps (default 5bps), both applied per trade side.
- **D-04:** Support both long-only and long-short strategies. Short signals = -1, flat = 0, long = 1.
- **D-05:** Default initial cash: 100,000 (configurable). Compound returns by default.

### Signal Interface & Integration
- **D-06:** Signals consumed from Phase 3 screener: `ScreenResult` → converted to vectorbt format (DataFrame of shape (n_bars, n_symbols) with values 1/0/-1).
- **D-07:** Signal timestamps must align with OHLCV data. Use Phase 3's `broadcast_timeframe()` for multi-timeframe alignment.
- **D-08:** Support signal metadata: confidence score (0-1), source filter name, timeframe. Stored in trade ledger for analysis.

### Walk-Forward Optimization
- **D-09:** Two modes: Expanding window (train grows, test fixed) and Rolling window (train + test fixed, both slide).
- **D-10:** Default: 70% train / 30% test split. Minimum train window: 252 bars (1 year daily).
- **D-11:** Optimizable parameters: position sizing method, risk %, ATR multiplier, Kelly fraction, entry/exit filter params.
- **D-12:** Optimization metric: Sharpe (default), Sortino, Calmar, or custom. Grid search for discrete, Bayesian for continuous.
- **D-13:** Results stored as `OptimizationResult` with best params, in-sample/out-of-sample metrics, parameter sensitivity.

### Monte Carlo Simulation
- **D-14:** 1000+ paths by default (configurable). Uses vectorbt's `simulate()` with resampled returns.
- **D-15:** Confidence intervals: 95% (default), 99%. Output: equity curve percentiles, drawdown percentiles, ruin probability.
- **D-16:** Two resampling methods: Bootstrap (returns with replacement) and Block Bootstrap (preserves autocorrelation, block size = 20).
- **D-17:** Output percentiles: 5, median, mean for final equity, max drawdown, Sharpe, CAGR.

### Metrics & Trade Ledger
- **D-18:** Core metrics: Sharpe, Sortino, Calmar, Max DD, Win Rate, Expectancy, Profit Factor, SQN, Ulcer Index, CAGR.
- **D-19:** Trade ledger per trade: symbol, entry/exit timestamps, entry/exit prices, size, direction, PnL, fees, slippage, MAE, MFE, hold duration, exit reason.
- **D-20:** Daily equity curve and returns series for plotting. Resampled to daily frequency.
- **D-21:** Drawdown series: peak-to-trough, duration, recovery time.

### Configuration & Output
- **D-22:** Backtest config via Pydantic `BacktestConfig`: signals, OHLCV, initial_cash, fees, slippage, position_sizing, optimization, monte_carlo.
- **D-23:** Output formats: JSON (metrics + ledger), CSV (ledger), Parquet (equity curve + signals for large datasets).
- **D-24:** Results cached in DuckDB: `backtest_results` table (run_id, config_hash, metrics JSON, equity curve, ledger).

### OpenCode's Discretion
- **D-25:** Exact module structure for backtest package (submodules: portfolio, optimization, monte_carlo, metrics, ledger, config).
- **D-26:** VectorBT version pinning strategy (major.minor, patch updates auto).
- **D-27:** Async execution for long-running optimizations/MC (Celery or thread pool, deferred to Phase 6).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1-3 Foundations
- `.planning/phases/01-foundation-core-infrastructure/01-CONTEXT.md` — Core decisions D-01 through D-17
- `.planning/phases/02-data-ingestion-pipeline/02-CONTEXT.md` — Data decisions D-01 through D-20
- `.planning/phases/03-screener-engine/03-CONTEXT.md` — Screener decisions D-01 through D-22
- `.planning/phases/01-foundation-core-infrastructure/01-RESEARCH.md` — VectorBT, pandas-ta patterns
- `.planning/phases/03-screener-engine/03-RESEARCH.md` — VectorBT broadcasting, signal patterns

### Existing Code Assets
- `backend/app/infrastructure/screener/engine.py` — `ScreenEngine.screen()` returns signals
- `backend/app/infrastructure/screener/models.py` — `ScreenRunResult`, `FilterRunResult`
- `backend/app/domain/models.py` — `OHLCV`, `Signal`, `Position`, `Trade`, `Metrics`
- `backend/app/core/database.py` — `get_db()`, `get_db_async()`, `OHLCV_DDL`
- `backend/app/core/config.py` — `ComputeSettings`, `DataSettings`, `IngestionSettings`
- `backend/app/infrastructure/indicators.py` — `@indicator` registry pattern

### Project Requirements
- `REQUIREMENTS.md` — FR-004 (Backtest Engine), NFR-001 (Performance)
- `.planning/ROADMAP.md` — Phase 4 success criteria

### External Documentation
- VectorBT Portfolio: https://vectorbt.dev/api/portfolio/
- VectorBT Optimization: https://vectorbt.dev/api/portfolio/optimization/
- VectorBT Monte Carlo: https://vectorbt.dev/api/portfolio/simulation/
- DuckDB Parquet: https://duckdb.org/docs/stable/data/parquet/overview

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (from Phases 1-3)
- `backend/app/domain/models.py` — `Position`, `Trade`, `Metrics`, `BacktestConfig`, `RiskParams` Pydantic models
- `backend/app/infrastructure/screener/engine.py` — `ScreenEngine.screen()` returns `ScreenRunResult` with signals
- `backend/app/core/database.py` — DuckDB connection pool, `partition_path()`, `initialize_database()`
- `backend/app/infrastructure/indicators.py` — `@indicator` decorator for custom indicators
- `backend/app/infrastructure/screener/broadcasting.py` — `broadcast_timeframe()` for multi-TF alignment

### Established Patterns
- `@decorator` registry pattern for pluggable components
- Vectorized pandas/NumPy operations (no loops)
- DuckDB for analytical queries and Parquet I/O
- Async-first with semaphore concurrency control
- Pydantic models for data validation at boundaries

### Integration Points
- Phase 3 `ScreenEngine.screen()` → Phase 4 backtest signal input
- Phase 1 `OHLCV` model + DuckDB `ohlcv` table → price data source
- Phase 3 `indicator_cache` → pre-computed indicators for signal generation
- Phase 4 backtest results → Phase 5 risk engine input

</code_context>

<specifics>
## Specific Ideas

- Use `vbt.Portfolio.from_signals()` with `freq` inferred from data frequency
- Kelly fraction: `kelly_f = win_rate - (1 - win_rate) / (avg_win / avg_loss)` from in-sample stats
- Walk-forward: store OOS equity curves per fold for stability analysis
- Monte Carlo: track ruin probability (equity < 50% initial) across paths
- Trade ledger: compute MAE/MFE from intraday data if available, else from daily OHLC

</specifics>

<deferred>
## Deferred Ideas

- Bayesian optimization with Optuna (Phase 9)
- Multi-asset portfolio optimization (correlation-aware sizing)
- Real-time paper trading bridge (Phase 10)
- Alternative data integration for signal enhancement (future)

None — discussion stayed within phase scope
</deferred>

---

*Phase: 4-Backtest Engine*
*Context gathered: 2026-06-19*