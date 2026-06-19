# Phase 5: Risk Management Engine — Plan

**Created:** 2026-06-19
**Status:** Ready for execution
**Depends on:** Phase 1 (Foundation), Phase 4 (Backtest Engine)
**Consumes:** DuckDB OHLCV, Phase 4 `PositionSizer`, Phase 4 `TradeLedger`, Phase 4 `BacktestEngine` results, Phase 3 `IndicatorCache`, Phase 1 `@indicator` registry (ATR)

---

## Frontmatter

```yaml
phase: 5
name: risk-management-engine
waves:
  - number: 1
    name: foundation
    parallel: true
    description: Package structure, config, domain models, DuckDB schema, dependency
  - number: 2
    name: core-computation
    parallel: true
    depends_on: [1]
    description: Individual risk component implementations (beta, correlation, VaR, Kelly, position sizing)
  - number: 3
    name: orchestration
    parallel: false
    depends_on: [2]
    description: RiskEngine orchestrator, WebSocket streaming, risk metrics computer
  - number: 4
    name: reporting-and-tests
    parallel: true
    depends_on: [2]
    description: Risk report generation, comprehensive test suite
files_modified:
  - backend/app/domain/models.py
  - backend/app/core/config.py
  - backend/app/core/database.py
  - config.yaml
  - pyproject.toml
files_created:
  - backend/app/infrastructure/risk/__init__.py
  - backend/app/infrastructure/risk/models.py
  - backend/app/infrastructure/risk/beta.py
  - backend/app/infrastructure/risk/correlation.py
  - backend/app/infrastructure/risk/var.py
  - backend/app/infrastructure/risk/kelly.py
  - backend/app/infrastructure/risk/position_sizing.py
  - backend/app/infrastructure/risk/engine.py
  - backend/app/infrastructure/risk/streaming.py
  - backend/app/infrastructure/risk/reporting.py
  - backend/app/infrastructure/risk/metrics.py
  - backend/tests/test_risk_engine.py
  - backend/tests/test_risk_beta.py
  - backend/tests/test_risk_correlation.py
  - backend/tests/test_risk_var.py
  - backend/tests/test_risk_kelly.py
  - backend/tests/test_risk_position_sizing.py
  - backend/tests/test_risk_models.py
  - backend/tests/test_risk_streaming.py
autonomous: true
```

---

## must_haves

These conditions MUST be met for the phase to be complete (derived from Phase 5 goal and success criteria):

1. `RiskEngine` orchestrator exists and coordinates all sub-components (beta, correlation, VaR, Kelly, position sizing)
2. `BetaHedger.compute_beta()` computes rolling 60-day OLS beta vs configurable benchmark with R² and tracking error
3. `CorrelationAnalyzer` computes 30-day rolling Pearson correlation matrix with sector/asset-class aggregation
4. `VaRCalculator` supports Historical, Parametric, and Monte Carlo methods at 95%/99% confidence, 1-day/10-day horizons
5. `KellyOptimizer.compute_kelly_from_backtest()` extracts win_rate, avg_win, avg_loss from Phase 4 trades and computes optimal f*
6. `PositionSizingRefiner` composes on Phase 4 `PositionSizer` (NOT a rewrite) and adds correlation-aware limits + VaR-based caps
7. `RiskSettings` class exists in `config.py` and `risk:` section exists in `config.yaml`
8. `RiskParams` in `domain/models.py` is extended with var_confidence, var_horizon_days, max_var_pct, max_leverage, max_correlation, hedge_min_effectiveness, var_method fields
9. DuckDB risk cache tables (`risk_beta_history`, `risk_correlation_snapshots`, `risk_var_history`, `risk_kelly_results`, `risk_hedge_recommendations`) DDL exists and `initialize_database()` creates them
10. `scipy>=1.11,<2` added to `pyproject.toml` dependencies
11. `RiskStreamManager` follows Phase 3 `ConnectionManager` pattern for on-demand WebSocket streaming
12. All risk computation components have unit tests with property-based tests for mathematical invariants
13. Risk engine functions return frozen Pydantic models with clear metadata (data source, computation time, recency)
14. `mypy strict` passes on all new code
15. `pytest` passes on all new tests

---

## Wave 1: Foundation (parallel)

### Task 1.1 — Add scipy dependency

**<read_first>**
- pyproject.toml (existing dependencies structure)
**</read_first>**

**<action>**
Add `scipy = ">=1.11,<2"` to the `[project.dependencies]` list in `pyproject.toml`. Place it after `numpy>=1.26`.

Also add `"jinja2>=3.1,<4"` and `"matplotlib>=3.7,<4"` to `[project.optional-dependencies] dev` section for report generation.

Then run `pip install scipy jinja2 matplotlib` to install locally.
**</action>**

**<acceptance_criteria>**
- `pyproject.toml` contains `scipy = ">=1.11,<2"`
- `pyproject.toml` contains `jinja2>=3.1,<4` and `matplotlib>=3.7,<4` under `[project.optional-dependencies] dev`
- `python -c "import scipy; print(scipy.__version__)"` succeeds
- `python -c "import jinja2; print(jinja2.__version__)"` succeeds
- `python -c "import matplotlib; print(matplotlib.__version__)"` succeeds
**</acceptance_criteria>**

---

### Task 1.2 — Extend RiskParams domain model

**<read_first>**
- backend/app/domain/models.py (existing RiskParams class at line 164)
**</read_first>**

**<action>**
Extend the existing `RiskParams` class in `backend/app/domain/models.py` by adding these new fields AFTER the existing `kelly_fraction` field:

```python
    var_confidence: float = Field(default=0.95, ge=0.8, le=0.999, description="VaR confidence level")
    var_horizon_days: int = Field(default=1, ge=1, le=252, description="VaR time horizon in days")
    var_method: str = Field(default="historical", description="Default VaR method: historical, parametric, monte_carlo")
    max_var_pct: float = Field(default=0.05, ge=0.01, le=1.0, description="Max VaR as fraction of portfolio (5%)")
    max_leverage: float = Field(default=1.0, ge=1.0, le=10.0, description="Max leverage ratio")
    max_correlation: float = Field(default=0.85, ge=0.5, le=1.0, description="Max allowed pairwise correlation")
    hedge_min_effectiveness: float = Field(default=0.5, ge=0.0, le=1.0, description="Min R² for hedge recommendation")
```

These are all non-breaking additions with defaults. Do NOT remove or modify any existing fields.
**</action>**

**<acceptance_criteria>**
- `backend/app/domain/models.py` contains `var_confidence: float = Field(default=0.95, ge=0.8, le=0.999, ...)`
- `backend/app/domain/models.py` contains `var_horizon_days: int = Field(default=1, ge=1, le=252, ...)`
- `backend/app/domain/models.py` contains `var_method: str = Field(default="historical", ...)`
- `backend/app/domain/models.py` contains `max_var_pct: float = Field(default=0.05, ...)`
- `backend/app/domain/models.py` contains `max_leverage: float = Field(default=1.0, ...)`
- `backend/app/domain/models.py` contains `max_correlation: float = Field(default=0.85, ...)`
- `backend/app/domain/models.py` contains `hedge_min_effectiveness: float = Field(default=0.5, ...)`
- All existing RiskParams fields remain unchanged
- `lsp_diagnostics` passes on the file
**</acceptance_criteria>**

---

### Task 1.3 — Add RiskSettings to config.py and config.yaml

**<read_first>**
- backend/app/core/config.py (existing settings pattern, especially ScreenSettings and BacktestSettings)
- config.yaml (existing sections)
**</read_first>**

**<action>**
**Part A — config.py:**

Add a new `RiskSettings` class BEFORE `AppSettings` (after `FrontendSettings`):

```python
class RiskSettings(BaseSettings):
    """Risk management engine settings."""
    model_config = SettingsConfigDict(env_prefix="CONFLU_RISK_")

    default_risk_per_trade: float = Field(default=0.01, ge=0.001, le=0.1, description="Default risk per trade as fraction of equity (1%)")
    default_atr_multiplier: float = Field(default=2.0, ge=1.0, le=5.0, description="Default ATR multiplier")
    beta_window_days: int = Field(default=60, ge=20, le=252, description="Rolling window for beta in days")
    beta_benchmark_map: dict[str, str] = Field(default={"equities": "SPY", "crypto": "BTCUSDT", "forex": "EURUSD", "commodities": "GC1!", "indices": "SPX"}, description="Benchmark per asset class")
    correlation_window_days: int = Field(default=30, ge=10, le=252, description="Rolling window for correlation in days")
    var_confidence_levels: list[float] = Field(default=[0.95, 0.99], description="Confidence levels for VaR")
    var_horizon_days: list[int] = Field(default=[1, 10], description="Time horizons for VaR in days")
    var_methods: list[str] = Field(default=["historical", "parametric", "monte_carlo"], description="Active VaR methods")
    var_monte_carlo_paths: int = Field(default=10000, ge=1000, le=100000, description="Paths for MC VaR")
    default_kelly_fraction: float = Field(default=0.5, ge=0.0, le=1.0, description="Default Kelly fraction (0.5 = half-Kelly)")
    max_dd_target: float = Field(default=0.25, ge=0.1, le=0.5, description="Max acceptable drawdown")
    risk_ws_path: str = Field(default="/api/v1/ws/risk/{portfolio_id}", description="WebSocket endpoint template")
    report_max_symbols: int = Field(default=50, description="Max symbols in risk report")
    cache_risk_results: bool = Field(default=True, description="Cache risk results in DuckDB")
    max_correlation_symbols: int = Field(default=100, description="Max symbols in correlation matrix (0=unlimited)")
```

Then in `AppSettings`, add: `risk: RiskSettings = RiskSettings()` after `frontend:`.

**Part B — config.yaml:**

Add a `risk:` section at the end of config.yaml:

```yaml
risk:
  default_risk_per_trade: 0.01
  default_atr_multiplier: 2.0
  beta_window_days: 60
  beta_benchmark_map:
    equities: SPY
    crypto: BTCUSDT
    forex: EURUSD
    commodities: GC1!
    indices: SPX
  correlation_window_days: 30
  var_confidence_levels:
    - 0.95
    - 0.99
  var_horizon_days:
    - 1
    - 10
  var_methods:
    - historical
    - parametric
    - monte_carlo
  var_monte_carlo_paths: 10000
  default_kelly_fraction: 0.5
  max_dd_target: 0.25
  risk_ws_path: /api/v1/ws/risk/{portfolio_id}
  report_max_symbols: 50
  cache_risk_results: true
  max_correlation_symbols: 100
```
**</action>**

**<acceptance_criteria>**
- `config.py` contains `class RiskSettings(BaseSettings):` with all 15 fields
- `AppSettings` has `risk: RiskSettings = RiskSettings()`
- `config.yaml` contains a `risk:` section with all matching keys
- `lsp_diagnostics` passes on config.py
- `python -c "from backend.app.core.config import settings; print(settings.risk.default_risk_per_trade)"` outputs `0.01`
**</acceptance_criteria>**

---

### Task 1.4 — Create risk DuckDB DDLs + update initialize_database()

**<read_first>**
- backend/app/core/database.py (existing DDL patterns, initialize_database())
**</read_first>**

**<action>**
Add the following DDL constants to `backend/app/core/database.py` BEFORE `initialize_database()` (after `BACKTEST_MC_RESULTS_DDL`):

```python
# Risk management cache tables
RISK_BETA_DDL = """
CREATE TABLE IF NOT EXISTS risk_beta_history (
    symbol VARCHAR NOT NULL,
    benchmark VARCHAR NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    beta DOUBLE,
    alpha DOUBLE,
    r_squared DOUBLE,
    std_err DOUBLE,
    tracking_error DOUBLE,
    window_days INTEGER DEFAULT 60,
    computed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, benchmark, timestamp)
);
"""

RISK_CORRELATION_DDL = """
CREATE TABLE IF NOT EXISTS risk_correlation_snapshots (
    timestamp TIMESTAMPTZ NOT NULL,
    window_days INTEGER NOT NULL,
    symbols_json VARCHAR NOT NULL,
    matrix_json VARCHAR NOT NULL,
    sector_matrix_json VARCHAR,
    symbol_count INTEGER NOT NULL,
    computed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (timestamp, window_days)
);
"""

RISK_VAR_DDL = """
CREATE TABLE IF NOT EXISTS risk_var_history (
    portfolio_id VARCHAR NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    method VARCHAR NOT NULL,
    confidence DOUBLE NOT NULL,
    horizon_days INTEGER DEFAULT 1,
    var DOUBLE NOT NULL,
    cvar DOUBLE,
    component_var_json VARCHAR,
    marginal_var_json VARCHAR,
    computed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (portfolio_id, timestamp, method, confidence, horizon_days)
);
"""

RISK_KELLY_DDL = """
CREATE TABLE IF NOT EXISTS risk_kelly_results (
    backtest_run_id VARCHAR NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    win_rate DOUBLE,
    avg_win_loss_ratio DOUBLE,
    full_kelly DOUBLE,
    constrained_kelly DOUBLE,
    recommended_kelly DOUBLE,
    max_dd_target DOUBLE,
    backtest_max_dd DOUBLE,
    is_valid BOOLEAN,
    PRIMARY KEY (backtest_run_id)
);
"""

RISK_HEDGE_DDL = """
CREATE TABLE IF NOT EXISTS risk_hedge_recommendations (
    portfolio_id VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    benchmark VARCHAR NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    beta DOUBLE,
    hedge_ratio DOUBLE,
    hedge_value DOUBLE,
    hedge_instrument VARCHAR,
    recommendation VARCHAR,
    effectiveness_r2 DOUBLE,
    tracking_error DOUBLE,
    computed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (portfolio_id, symbol, benchmark, timestamp)
);
"""
```

Then add these to `initialize_database()` after the existing backtest DDL calls:

```python
        con.execute(RISK_BETA_DDL)
        con.execute(RISK_CORRELATION_DDL)
        con.execute(RISK_VAR_DDL)
        con.execute(RISK_KELLY_DDL)
        con.execute(RISK_HEDGE_DDL)
```
**</action>**

**<acceptance_criteria>**
- `database.py` contains all 5 risk DDL constants with column definitions matching the spec
- `initialize_database()` calls all 5 `con.execute(RISK_*_DDL)` after backtest DDLs
- `lsp_diagnostics` passes on database.py
**</acceptance_criteria>**

---

### Task 1.5 — Create risk/ package skeleton + models.py

**<read_first>**
- backend/app/infrastructure/screener/__init__.py (existing package init pattern)
- backend/app/infrastructure/backtest/__init__.py
**</read_first>**

**<action>**
Create the `backend/app/infrastructure/risk/` directory with `__init__.py` and `models.py`.

**`__init__.py`:** Exports all risk components (BetaHedger, CorrelationAnalyzer, VaRCalculator, KellyOptimizer, PositionSizingRefiner, RiskEngine, RiskStreamManager) and all models.

**`models.py`:** Create all 8 frozen Pydantic models:
- `BetaResult` — symbol, benchmark, beta, alpha, r_squared, std_err, p_value, tracking_error, window_days, n_observations, computed_at
- `PortfolioBetaResult` — portfolio_id, benchmark, weighted_beta, symbol_betas, computed_at
- `CorrelationResult` — timestamp, window_days, symbols, matrix, sector_matrix, sector_labels, high_correlation_pairs, diversification_score
- `VaRResult` — portfolio_id, method, confidence, horizon_days, var, cvar, component_var, marginal_var, ci_lower, ci_upper, n_simulations, computed_at
- `KellyRecommendation` — backtest_run_id, asset_class, win_rate, avg_win_loss_ratio, full_kelly, constrained_kelly, recommended_kelly, max_dd_target, is_valid, suggested_position_sizing, suggested_params
- `HedgeRecommendation` — symbol, asset_class, beta, r_squared, tracking_error, hedge_ratio, hedge_value, hedge_units, hedge_instrument, recommendation, hedge_cost_annual_pct, computed_at
- `RiskAlert` — severity (Literal["info","warning","critical"]), category (Literal["var","correlation","concentration","leverage","beta"]), message, symbol, current_value, threshold, timestamp
- `RiskAssessment` — portfolio_id, timestamp, var_95, var_99, portfolio_beta, correlation, kelly, hedge_recommendations, risk_score, alerts

All models use `model_config = ConfigDict(frozen=True)`.
**</action>**

**<acceptance_criteria>**
- `backend/app/infrastructure/risk/__init__.py` exists and exports all risk components
- `backend/app/infrastructure/risk/models.py` exists with all 8 Pydantic model classes
- Each model has `model_config = ConfigDict(frozen=True)`
- `lsp_diagnostics` passes on both files
- `python -c "from backend.app.infrastructure.risk.models import VaRResult, BetaResult, CorrelationResult, KellyRecommendation, HedgeRecommendation, RiskAssessment, RiskAlert, PortfolioBetaResult"` succeeds
**</acceptance_criteria>**

---

## Wave 2: Core Risk Computation (parallel, depends on Wave 1)

### Task 2.1 — Implement BetaHedger

**<read_first>**
- backend/app/infrastructure/risk/models.py (BetaResult, PortfolioBetaResult)
- backend/app/core/config.py (RiskSettings.beta_window_days, beta_benchmark_map)
- backend/app/core/database.py (DuckDB OHLCV access pattern)
**</read_first>**

**<action>**
Create `backend/app/infrastructure/risk/beta.py` with `BetaHedger` class:

**Public methods:**
- `compute_beta(symbols, benchmark, window, min_periods) -> list[BetaResult]` — Rolling OLS beta via vectorized covariance formula `β = Cov(r_asset, r_benchmark) / Var(r_benchmark)`, with full regression stats via `scipy.stats.linregress()` for the latest window
- `compute_portfolio_beta(portfolio_id, positions, benchmark, window) -> PortfolioBetaResult` — Market-value-weighted portfolio beta
- `recommend_hedge(symbol, asset_class, position_value, benchmark_price, beta_result, contract_multiplier) -> HedgeRecommendation` — Hedge ratio `= beta × position_value / (benchmark_price × multiplier)`, recommendation logic: `beta>0.5 & R²>0.7 → required`, `beta>0.3 & R²>0.4 → optional`, else `none`

**Internal methods:**
- `_load_returns(symbols, benchmark) -> (returns_matrix, benchmark_series)` — Queries DuckDB `ohlcv` for daily `1D` close, pivots to returns matrix via `pct_change()`
- `_compute_beta_vectorized(returns_matrix, benchmark_returns, window) -> pd.DataFrame` — Vectorized rolling beta across all symbols using pandas rolling cov/var
- `resolve_benchmark(asset_class, override) -> str` — Resolves benchmark from `beta_benchmark_map`
**</action>**

**<acceptance_criteria>**
- `BetaHedger` has methods: `compute_beta`, `compute_portfolio_beta`, `recommend_hedge`
- `compute_beta` uses vectorized covariance formula for performance
- `compute_beta` uses `scipy.stats.linregress()` for full regression statistics
- Hedge recommendation implements the 3-tier rule (required/optional/none)
- `lsp_diagnostics` passes
- `python -c "from backend.app.infrastructure.risk import BetaHedger"` succeeds
**</acceptance_criteria>**

---

### Task 2.2 — Implement CorrelationAnalyzer

**<read_first>**
- backend/app/infrastructure/risk/models.py (CorrelationResult)
- backend/app/core/config.py (RiskSettings.correlation_window_days)
**</read_first>**

**<action>**
Create `backend/app/infrastructure/risk/correlation.py` with `CorrelationAnalyzer` class:

**Public methods:**
- `compute_correlation(symbols, window, min_periods, group_by) -> CorrelationResult` — Rolling Pearson correlation via `pandas.DataFrame.rolling().corr(pairwise=True)` (fully vectorized). Returns latest N×N matrix, sector aggregation, high-correlation pairs, diversification score.

**Internal methods:**
- `_load_returns_matrix(symbols) -> pd.DataFrame` — Loads daily returns from DuckDB `ohlcv`
- `_get_group_map(symbols, group_by) -> dict[str, str]` — Queries `symbol_metadata` for asset_class/sector → group mapping. Defaults to "Unclassified".
- `_aggregate_by_group(correlation_matrix, group_map, symbols) -> (sector_matrix, labels)` — Average intra-group (upper triangle) and inter-group correlations
- `_find_high_correlation_pairs(matrix, symbols, threshold=0.8, max_pairs=20) -> list[dict]` — Top correlated pairs
- `_compute_diversification_score(matrix, symbols) -> float` — Score = 1 - mean absolute pairwise correlation (0=perfectly correlated, 1=perfectly uncorrelated)
**</action>**

**<acceptance_criteria>**
- `CorrelationAnalyzer` has `compute_correlation` method
- Uses `pandas.DataFrame.rolling().corr(pairwise=True)` (fully vectorized, no Python loops)
- Returns `CorrelationResult` with matrix, sector aggregation, high_correlation_pairs, diversification_score
- `lsp_diagnostics` passes
- `python -c "from backend.app.infrastructure.risk import CorrelationAnalyzer"` succeeds
**</acceptance_criteria>**

---

### Task 2.3 — Implement VaRCalculator

**<read_first>**
- backend/app/infrastructure/risk/models.py (VaRResult)
- backend/app/core/config.py (RiskSettings.var_confidence_levels, var_horizon_days, var_methods)
**</read_first>**

**<action>**
Create `backend/app/infrastructure/risk/var.py` with `VaRCalculator` class:

**Public methods:**
- `compute_var(portfolio_id, returns, trade_pnl, method, confidence, horizon_days, weights, covariance_matrix, n_simulations) -> VaRResult` — Main entry point. Accepts either `returns` (portfolio daily returns, preferred) or `trade_pnl` (per-trade PnL, position-level VaR). Returns VaRResult with var, cvar, optional component/marginal VaR.

**VaR methods (private):**
- `_compute_var_1d(data, method, confidence, n_simulations) -> (var, cvar)` — Dispatches to the three methods
- **Historical VaR:** `var = -np.percentile(returns, alpha*100)`, `cvar = -mean(losses_beyond_var)`
- **Parametric VaR:** `var = -(mean + norm.ppf(alpha) × std)`, `cvar = -(mean - std × φ(z) / confidence)` using `scipy.stats.norm`
- **Monte Carlo VaR:** Bootstrap from empirical returns (NOT synthetic lognormal — this captures real-market skew/kurtosis). Resamples with replacement, computes percentile of simulated means.

**Time scaling:**
- `_scale_var(var_1d, horizon_days)` — √N rule: `VaR_N = VaR_1 × √N`

**Decomposition:**
- `_decompose_var(weights, covariance_matrix, portfolio_var) -> (component_var, marginal_var)` — Component VaR = `w_i × (Σw)_i / σ_p × VaR_p`. Sum of component VaR = portfolio VaR (decomposition property).
**</action>**

**<acceptance_criteria>**
- `VaRCalculator` supports `historical`, `parametric`, and `monte_carlo` methods
- Historical VaR uses `np.percentile()`
- Parametric VaR uses `scipy.stats.norm.ppf()`
- MC VaR bootstraps from empirical returns (NOT synthetic lognormal)
- CVaR = Expected Shortfall (average of losses beyond VaR)
- `_scale_var` implements √N rule
- `_decompose_var` computes component and marginal VaR
- `lsp_diagnostics` passes
- `python -c "from backend.app.infrastructure.risk import VaRCalculator"` succeeds
**</acceptance_criteria>**

---

### Task 2.4 — Implement KellyOptimizer

**<read_first>**
- backend/app/infrastructure/risk/models.py (KellyRecommendation)
- backend/app/domain/models.py (Trade, Metrics)
- backend/app/core/config.py (RiskSettings.default_kelly_fraction, max_dd_target)
- backend/app/infrastructure/backtest/models.py (BacktestRunRecord)
**</read_first>**

**<action>**
Create `backend/app/infrastructure/risk/kelly.py` with `KellyOptimizer` class:

**Public methods:**
- `optimize_from_backtest(backtest_run_id, trades, max_dd_target, use_half_kelly) -> KellyRecommendation` — Full pipeline: load trades from DuckDB → compute stats → Kelly formula → max DD validation → half-Kelly adjustment
- `validate_kelly_fraction(kelly_fraction, backtest_max_dd, max_dd_target) -> dict` — D-17 formula: `max_dd_kelly = 2 × max_dd_target / (1 + max_dd_target)`

**Internal methods:**
- `_compute_trade_stats(trades) -> (win_rate, avg_win_loss_ratio)` — Separates winning/losing trades, computes mean PnL
- `_compute_kelly_fraction(win_rate, avg_win_loss_ratio) -> float` — D-15: `f* = win_rate - (1 - win_rate) / avg_win_loss_ratio`, clamped to [0, 1]
- `_validate_against_max_dd(kelly, backtest_max_dd, target) -> float` — Constrains Kelly to max_dd_kelly
- `_load_trades(backtest_run_id) -> list[Trade]` — Loads trades from DuckDB `backtest_trades` table

**Key behavior:** If no trades available (no backtest run), returns KellyRecommendation with `is_valid=False` and default sizing params (risk_per_trade: 0.01, kelly_fraction: 0.5). Never fails — always returns sensible defaults.
**</action>**

**<acceptance_criteria>**
- `KellyOptimizer` has `optimize_from_backtest` and `validate_kelly_fraction` methods
- `optimize_from_backtest` loads trades from DuckDB if not provided
- Kelly formula: `f* = win_rate - (1 - win_rate) / avg_win_loss_ratio`
- Max DD validation implements D-17 formula: `max_dd_kelly = 2 × target / (1 + target)`
- Half-Kelly is default (`use_half_kelly=True`)
- Returns `KellyRecommendation` with full_kelly, constrained_kelly, recommended_kelly
- `is_valid=False` with default sizing when no trades available
- `lsp_diagnostics` passes
**</acceptance_criteria>**

---

### Task 2.5 — Implement PositionSizingRefiner

**<read_first>**
- backend/app/infrastructure/backtest/sizing.py (PositionSizer — import + compose, NOT rewrite)
- backend/app/core/config.py (RiskSettings.default_risk_per_trade, default_atr_multiplier)
**</read_first>**

**<action>**
Create `backend/app/infrastructure/risk/position_sizing.py` with `PositionSizingRefiner` class:

**CRITICAL RULE:** Do NOT reimplement ATR or Kelly formulas. Import `PositionSizer` from `backend.app.infrastructure.backtest.sizing` and compose on top.

**Public methods:**
- `compute_size_with_risk_constraints(close, entries, method, initial_cash, params, atr_series, correlation_matrix, position_var, portfolio_var, beta_values, max_correlation, max_var_pct, max_leverage) -> pd.DataFrame` — 5-step pipeline:
  1. **Base sizing** via `self._sizer.compute_position_size()`
  2. **Correlation limit** — Reduce combined sizing for pairs exceeding `max_correlation`
  3. **VaR cap** — No position exceeds `max_var_pct × portfolio_var / position_var`
  4. **Beta constraint** — Reduce high-beta (>1.5) positions by factor `1.5/beta`
  5. **Leverage bound** — Scale all positions if total leverage exceeds `max_leverage`

**Internal methods:**
- `_apply_correlation_limit(constrained, base, corr_matrix, max_corr, cash, close)` — Proportional reduction for |corr| > limit
- `_apply_var_cap(constrained, base, pos_var, port_var, max_var_pct)` — Clip per symbol to VaR-based max
- `_apply_beta_constraint(constrained, base, betas, cash)` — Scale down high-beta positions
**</action>**

**<acceptance_criteria>**
- `PositionSizingRefiner` imports `PositionSizer` from Phase 4 (NOT a rewrite)
- `compute_size_with_risk_constraints` first calls `self._sizer.compute_position_size()`, then applies overlays
- Overlay methods: `_apply_correlation_limit`, `_apply_var_cap`, `_apply_beta_constraint`
- No ATR or Kelly formula reimplemented
- `lsp_diagnostics` passes
- `python -c "from backend.app.infrastructure.risk import PositionSizingRefiner"` succeeds
**</acceptance_criteria>**

---

## Wave 3: Orchestration & Streaming (depends on Wave 2)

### Task 3.1 — Implement RiskEngine orchestrator

**<read_first>**
- backend/app/infrastructure/backtest/engine.py (BacktestEngine orchestration pattern)
- backend/app/infrastructure/risk/beta.py, correlation.py, var.py, kelly.py, position_sizing.py
- backend/app/infrastructure/risk/models.py (RiskAssessment)
**</read_first>**

**<action>**
Create `backend/app/infrastructure/risk/engine.py` with `RiskEngine` class:

**Public methods:**
- `analyze_portfolio(portfolio_id, symbols, positions, benchmark) -> RiskAssessment` — Full risk analysis:
  1. Load portfolio returns from DuckDB
  2. Run VaR (95%, 99%), beta, and correlation in parallel via `asyncio.gather()`
  3. Check risk limit breaches → generate `RiskAlert` list
  4. Compute composite `risk_score` (0-100: VaR=40pts, diversification=30pts, beta=30pts)
  5. Return complete `RiskAssessment`
- `compute_position_size(close, entries, method, cash, params, atr, corr_matrix) -> pd.DataFrame` — Delegates to `PositionSizingRefiner`
- `compute_beta(symbols, benchmark, window) -> list[dict]` — Convenience wrapper
- `compute_correlation(symbols, window, group_by) -> dict` — Convenience wrapper
- `compute_var(portfolio_id, returns, method, confidence, horizon) -> dict` — Convenience wrapper
- `compute_kelly(backtest_run_id, trades, max_dd) -> dict` — Convenience wrapper

**Internal methods:**
- `_load_portfolio_returns(symbols) -> pd.Series | None` — Loads equal-weighted portfolio daily returns
- `_compute_risk_score(var_95, diversification, beta) -> float` — Composite 0-100 score
**</action>**

**<acceptance_criteria>**
- `RiskEngine` has methods: `analyze_portfolio`, `compute_position_size`, `compute_beta`, `compute_correlation`, `compute_var`, `compute_kelly`
- `analyze_portfolio` runs VaR/beta/correlation in parallel via `asyncio.gather`
- Uses `PositionSizingRefiner` (not `PositionSizer` directly)
- Returns `RiskAssessment` with all metrics and alerts
- `_compute_risk_score` produces composite 0-100 score
- `lsp_diagnostics` passes
**</acceptance_criteria>**

---

### Task 3.2 — Implement RiskStreamManager

**<read_first>**
- backend/app/infrastructure/screener/streaming.py (ConnectionManager pattern)
- backend/app/core/config.py (RiskSettings.risk_ws_path)
**</read_first>**

**<action>**
Create `backend/app/infrastructure/risk/streaming.py` with `RiskStreamManager` class:

Follows the Phase 3 `ConnectionManager` pattern exactly:

**Methods:**
- `register(portfolio_id, websocket)` — Register connection, send full snapshot on connect (replay history)
- `unregister(portfolio_id, websocket)` — Remove connection, clean up empty sets
- `broadcast_risk_update(portfolio_id, update_type, data)` — Sequence-numbered message to all connected clients, stores in history for reconnection replay
- `start_background_updates(portfolio_id, update_coro, interval_s)` — Periodic polling loop while clients connected
- `close_all()` — Close all connections
- `has_connections(portfolio_id) -> bool` — Check active connections
- `active_portfolios -> list[str]` — List portfolios with active connections

**Message format:** `{type, portfolio_id, timestamp, sequence, data}`

**Design:** On-demand — only computes/broadcasts when at least one client is connected. The actual WebSocket endpoint is wired in Phase 6 (API layer).
**</action>**

**<acceptance_criteria>**
- `RiskStreamManager` has: `register`, `unregister`, `broadcast_risk_update`, `start_background_updates`, `close_all`
- Message format includes `type`, `portfolio_id`, `timestamp`, `sequence`, `data`
- Supports reconnection with history replay
- On-demand design (only broadcasts when connections exist)
- `lsp_diagnostics` passes
- `python -c "from backend.app.infrastructure.risk import RiskStreamManager"` succeeds
**</acceptance_criteria>**

---

### Task 3.3 — Implement RiskMetricsComputer

**<read_first>**
- backend/app/infrastructure/backtest/metrics.py (MetricsComputer pattern)
- backend/app/domain/models.py (Metrics)
**</read_first>**

**<action>**
Create `backend/app/infrastructure/risk/metrics.py` with `RiskMetricsComputer` class:

**Public methods:**
- `compute_risk_metrics(returns, benchmark_returns, risk_free_rate) -> dict[str, float | None]` — Computes: var_95, cvar_95, var_99, cvar_99, var_parametric_95, var_parametric_99, max_drawdown, downside_deviation, beta, r_squared, tracking_error_annual, information_ratio, alpha_annual
- `extend_metrics(base_metrics, returns, benchmark_returns) -> Metrics` — Takes base `Metrics` (frozen, so creates new instance with risk data)

**Internal methods:**
- `_compute_max_drawdown(returns) -> float` — Standard cumulative max drawdown formula
**</action>**

**<acceptance_criteria>**
- `RiskMetricsComputer` has `compute_risk_metrics` and `extend_metrics`
- `compute_risk_metrics` returns dict with var_95, var_99, cvar, beta, tracking_error, information_ratio
- `extend_metrics` takes base `Metrics` and returns extended `Metrics`
- `lsp_diagnostics` passes
**</acceptance_criteria>**

---

## Wave 4: Reporting & Tests (parallel, depends on Wave 2)

### Task 4.1 — Implement RiskReportGenerator

**<read_first>**
- backend/app/infrastructure/risk/models.py (CorrelationResult, VaRResult, etc.)
**</read_first>**

**<action>**
Create `backend/app/infrastructure/risk/reporting.py` with `RiskReportGenerator` class:

**Public methods:**
- `generate_html_report(assessment, title) -> str` — Generates full HTML risk report with inline CSS. Sections:
  1. Executive Summary (summary cards: VaR, beta, diversification, risk score)
  2. VaR/CVaR Breakdown (table: method, confidence, horizon, VaR, CVaR)
  3. Beta & Hedging (table: symbol, benchmark, beta, R², tracking error)
  4. Correlation (diversification score, high-correlation pair alerts)
  5. Kelly Optimization (table: full, constrained, recommended Kelly)
  6. Risk Alerts (severity-colored alert boxes)
- `save_report(assessment, filepath) -> str` — Saves HTML to disk (default: `reports/risk_{portfolio_id}_{date}.html`)

**Design:** No Jinja2/matplotlib dependency required. Pure string-based HTML generation with inline CSS. For advanced PDF/Matplotlib charts, defer to Phase 9.
**</action>**

**<acceptance_criteria>**
- `RiskReportGenerator` has `generate_html_report` and `save_report`
- `generate_html_report` returns valid HTML string with executive summary, VaR, beta, correlation, Kelly, and alerts sections
- `save_report` writes HTML to disk and returns filepath
- HTML uses inline CSS with responsive grid layout
- `lsp_diagnostics` passes
**</acceptance_criteria>**

---

### Task 4.2 — Write test suite

**<read_first>**
- backend/tests/conftest.py (existing fixtures)
- backend/tests/test_backtest_metrics.py, test_backtest_sizing.py (test patterns)
**</read_first>**

**<action>**
Create the following test files:

**`test_risk_models.py`** — Pydantic model tests:
- `TestBetaResult`: default creation, frozen enforcement, full creation
- `TestVaRResult`: default creation, full creation with component/marginal VaR
- `TestKellyRecommendation`: default valid, invalid fallback with default sizing
- `TestRiskAlert`: warning creation, invalid severity/category rejection (Literal validation)
- `TestRiskAssessment`: empty assessment defaults
- `TestCorrelationResult`: simple matrix creation
- `TestHedgeRecommendation`: no-hedge default

**`test_risk_beta.py`** — Beta computation tests:
- Vectorized beta formula matches definition `β = Cov / Var`
- Tracking error = std of regression residuals
- Hedge ratio formula: `hedge_value = beta × position_value`
- Hedge recommendation logic (3-tier rules)
- Property: portfolio_beta = Σ(weight_i × beta_i)

**`test_risk_correlation.py`** — Correlation computation tests:
- Property: `corr(i,j) = corr(j,i)` (symmetry)
- Property: `corr(i,i) = 1.0` (self-correlation)
- Property: `0 ≤ diversification_score ≤ 1`
- Group aggregation correctness (Tech intra-group vs Crypto-Tech cross-group)

**`test_risk_var.py`** — VaR computation tests:
- Property: `0 ≤ VaR_95 ≤ VaR_99` (higher confidence → larger loss)
- Property: `CVaR ≥ VaR` (Expected Shortfall ≥ VaR threshold)
- Parametric VaR ≈ Historical VaR for normal returns (large sample)
- Single-position component VaR = portfolio VaR
- Time scaling: `VaR_10 = VaR_1 × √10`
- MC VaR non-negative, MC VaR(99%) > MC VaR(95%)

**`test_risk_kelly.py`** — Kelly optimization tests:
- Known case: p=0.6, b=1 → f*=0.2
- Property: `0 ≤ constrained_kelly ≤ full_kelly ≤ 1` for various win rates
- Half-Kelly: recommended ≤ 0.5 × full_kelly
- Max DD validation: D-17 formula correct
- Empty trades → `is_valid=False` with defaults

**`test_risk_position_sizing.py`** — Position sizing refiner tests:
- Size generation delegates to Phase 4 PositionSizer
- Correlation limit reduces correlated pair sizes
- VaR cap applied correctly

**`test_risk_streaming.py`** — Streaming tests:
- Register/unregister connections
- Sequence number increments
- History replay on reconnect
- Broadcast skips when no connections

**`test_risk_engine.py`** — Integration tests:
- RiskEngine initializes all sub-components
- `analyze_portfolio` returns RiskAssessment with correct structure
- All convenience wrappers return correct types
**</action>**

**<acceptance_criteria>**
- All 8 test files exist in `backend/tests/`
- `pytest backend/tests/test_risk_*.py -v` passes
- Hypothesis property-based tests are included where applicable
- Test coverage includes: normal cases, edge cases (NaN returns, empty trades), property invariants
**</acceptance_criteria>**

---

## Verification Criteria (post-execution gate)

After all tasks are complete, verify:

1. `mypy --strict backend/app/infrastructure/risk/ backend/app/core/config.py backend/app/domain/models.py backend/app/core/database.py` — zero errors
2. `pytest backend/tests/test_risk_*.py -v --tb=short` — all tests pass
3. `python -c "from backend.app.core.config import settings; print(settings.risk.default_risk_per_trade)"` — prints `0.01`
4. `python -c "from backend.app.domain.models import RiskParams; p=RiskParams(); print(p.var_confidence)"` — prints `0.95`
5. `python -c "from backend.app.infrastructure.risk import RiskEngine"` — succeeds
6. `python -c "from backend.app.core.database import initialize_database; print('DDL OK')"` — succeeds (run once with actual DuckDB to validate DDLs)
7. All files pass `lsp_diagnostics`
8. `ruff check backend/app/infrastructure/risk/` — zero lint errors
</parameter>
