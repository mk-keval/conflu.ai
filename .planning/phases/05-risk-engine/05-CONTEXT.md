# Phase 5: Risk Management Engine - Context

**Gathered:** 2026-06-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Risk Management Engine: ATR position sizing, beta hedging, correlation matrix, VaR/CVaR, Kelly optimization. This phase consumes backtest results (Phase 4) and screener data (Phase 3) to produce risk metrics and hedging recommendations.
</domain>

<decisions>
## Implementation Decisions

### ATR Position Sizing
- **D-01:** ATR-based position sizing formula: `position_size = (risk_pct × equity) / (ATR × multiplier)`. Uses 14-period ATR from Phase 1 indicators.
- **D-02:** Risk per trade configurable (default 1-2% of equity). ATR multiplier configurable (default 2.0).
- **D-03:** Position sizing applies to both long and short positions. Short position size = same formula applied to short entry.

### Beta Hedging
- **D-04:** Rolling 60-day beta vs benchmark: SPY for US equities, BTC for crypto, major index for forex/commodities.
- **D-05:** Beta computed via OLS regression: `r_asset = α + β × r_benchmark + ε`. Uses daily returns.
- **D-06:** Hedge ratio = beta × position_value / benchmark_value. Output: capital allocation to inverse ETF or futures.
- **D-07:** Hedge effectiveness tracked: R² from regression, tracking error, hedge cost (carry, fees).

### Correlation Matrix
- **D-08:** 30-day rolling correlation using daily returns. Pearson correlation.
- **D-09:** Sectors/asset classes grouping from screener metadata (Phase 3). Assets without sector get "Unclassified".
- **D-10:** Output: correlation matrix (N×N) + sector-level aggregated matrix. Heatmap-ready JSON.

### VaR / CVaR
- **D-11:** Three methods: Historical (empirical percentile), Parametric (Gaussian), Monte Carlo (from Phase 4 MC results).
- **D-12:** Confidence levels: 95% and 99%. Time horizons: 1-day, 10-day (√10 scaling).
- **D-13:** CVaR (Expected Shortfall) = average of losses beyond VaR threshold.
- **D-14:** Component VaR and Marginal VaR for portfolio decomposition.

### Kelly Optimization
- **D-15:** Kelly fraction from Phase 4 backtest: `f = (p × b - q) / b` where p=win rate, q=1-p, b=avg_win/avg_loss.
- **D-16:** Half-Kelly (0.5×) as default for risk aversion. Full Kelly available for aggressive.
- **D-17:** Kelly sizing validated against max drawdown constraint: `max_kelly = 2 × max_dd_target / (1 + max_dd_target)`.

### Risk Dashboard & API
- **D-18:** Risk metrics exposed via REST endpoints: `/api/v1/risk/position-size`, `/api/v1/risk/beta`, `/api/v1/risk/correlation`, `/api/v1/risk/var`, `/api/v1/risk/kelly`.
- **D-19:** WebSocket stream for real-time risk updates: `/api/v1/ws/risk/{portfolio_id}`.
- **D-20:** Risk report generation: PDF/HTML with metrics, heatmaps, hedging recommendations.

### Configuration
- **D-21:** RiskSettings in config.py: `default_risk_pct`, `atr_multiplier`, `beta_benchmark_map`, `var_confidence_levels`, `kelly_fraction`.
- **D-22:** RiskSettings in config.yaml under `risk:` section.

### OpenCode's Discretion
- **D-23:** Exact module structure for risk package.
- **D-24:** Statistical library choice: NumPy/SciPy for VaR/beta, pandas for correlation.
- **D-25:** Caching strategy for rolling calculations (DuckDB materialized views vs recomputation).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1-4 Foundations
- `.planning/phases/01-foundation-core-infrastructure/01-CONTEXT.md` — Core decisions
- `.planning/phases/02-data-ingestion-pipeline/02-CONTEXT.md` — Data decisions
- `.planning/phases/03-screener-engine/03-CONTEXT.md` — Screener decisions
- `.planning/phases/04-backtest-engine/04-CONTEXT.md` — Backtest decisions
- `.planning/phases/01-foundation-core-infrastructure/01-RESEARCH.md` — Indicators, DuckDB patterns
- `.planning/phases/03-screener-engine/03-RESEARCH.md` — Indicator cache, broadcasting
- `.planning/phases/04-backtest-engine/04-RESEARCH.md` — VectorBT, backtest patterns, Kelly circular dependency

### Existing Code Assets
- `backend/app/infrastructure/screener/engine.py` — `ScreenEngine.screen()` produces signals
- `backend/app/infrastructure/backtest/engine.py` — `BacktestEngine.run()` produces results
- `backend/app/infrastructure/backtest/metrics.py` — `MetricsComputer` computes backtest metrics
- `backend/app/infrastructure/backtest/ledger.py` — `TradeLedger` produces trade ledger
- `backend/app/infrastructure/backtest/sizing.py` — `PositionSizer` for position sizing
- `backend/app/infrastructure/indicators.py` — `@indicator` registry, ATR(14) available
- `backend/app/domain/models.py` — `RiskParams`, `Trade`, `Metrics`, `BacktestRunConfig`
- `backend/app/core/database.py` — DuckDB connection, `get_db()`, `partition_path()`
- `backend/app/core/config.py` — Settings classes pattern

### Project Requirements
- `REQUIREMENTS.md` — FR-005 (Risk Management Engine), NFR-001 (Performance)
- `.planning/ROADMAP.md` — Phase 5 success criteria

### External Documentation
- VaR/CVaR: https://en.wikipedia.org/wiki/Value_at_risk
- Beta hedging: https://www.investopedia.com/terms/b/beta.asp
- Kelly Criterion: https://en.wikipedia.org/wiki/Kelly_criterion
- SciPy stats: https://docs.scipy.org/doc/scipy/reference/stats.html
- DuckDB Parquet: https://duckdb.org/docs/stable/data/parquet/overview

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (from Phases 1-4)
- `PositionSizer` in `backtest/sizing.py` — already has ATR-based sizing, Kelly logic
- `MetricsComputer` in `backtest/metrics.py` — computes backtest metrics, can extend for risk
- `TradeLedger` in `backtest/ledger.py` — trade ledger with MAE/MFE, can compute VaR
- `IndicatorCache` in `screener/cache.py` — ATR(14) available for position sizing
- `TradeLedger` in `backtest/ledger.py` — trade records for VaR/CVaR computation
- `WalkForwardOptimizer` in `backtest/walk_forward.py` — optimization patterns
- `MonteCarloSimulator` in `backtest/monte_carlo.py` — MC patterns reusable for MC VaR

### Established Patterns
- `@decorator` registry pattern for pluggable components
- Vectorized pandas/NumPy operations (no loops)
- DuckDB for analytical queries and Parquet I/O
- Async-first with semaphore concurrency control
- Pydantic models for data validation at boundaries

### Integration Points
- Phase 3 `IndicatorCache` → ATR for position sizing
- Phase 4 `BacktestEngine` results → Kelly fraction, trade ledger for VaR
- Phase 4 `TradeLedger` → trade history for VaR/CVaR, beta regression
- Phase 3 `IndicatorCache` + Phase 2 OHLCV → correlation matrix
- Phase 4 backtest results → Kelly optimization validation

</code_context>

<specifics>
## Specific Ideas

- Use `scipy.stats.norm.ppf` for parametric VaR, `scipy.stats.mstats.mquantiles` for historical
- Beta regression via `numpy.linalg.lstsq` or `scipy.stats.linregress`
- Correlation via `pandas.DataFrame.corr()` with rolling window
- Kelly validation against max DD: use Phase 4 backtest max DD as constraint
- Cache rolling beta/correlation in DuckDB materialized views for fast dashboard queries
- Risk report template: metrics table + correlation heatmap + hedging recommendations + VaR waterfall

</specifics>

<deferred>
## Deferred Ideas

- Stress testing (historical scenarios, Monte Carlo scenarios)
- Factor model risk decomposition (Fama-French, PCA)
- Options-based hedging (delta, gamma, vega)
- Real-time portfolio margin monitoring
- Regime-dependent risk parameters (volatility regimes)

None — discussion stayed within phase scope
</deferred>

---

*Phase: 5-Risk Management Engine*
*Context gathered: 2026-06-19*