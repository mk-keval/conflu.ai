# Phase 5: Risk Management Engine — Research

**Created:** 2026-06-19
**Status:** Ready for planning
**Context:** Phase 1 foundation (DuckDB, config, logging, indicators) + Phase 2 ingestion (Parquet OHLCV, symbol metadata) + Phase 3 screener (filter pipeline, indicator cache) + Phase 4 backtest (BacktestEngine, TradeLedger, PositionSizer, MetricsComputer, MonteCarloSimulator) exist in completed state.

---

## Table of Contents

1. [Project State & Codebase Assessment](#1-project-state--codebase-assessment)
2. [Critical Architecture: What Phase 4 Already Built for Phase 5](#2-critical-architecture-what-phase-4-already-built-for-phase-5)
3. [ATR Position Sizing — Refinement vs Greenfield](#3-atr-position-sizing--refinement-vs-greenfield)
   - 3.1 Existing `PositionSizer` Capabilities
   - 3.2 What Phase 5 Needs to Add
   - 3.3 ATR Integration with PositionSizer API
4. [Beta Hedging](#4-beta-hedging)
   - 4.1 Beta Computation via OLS Regression
   - 4.2 Benchmark Data Source Strategy
   - 4.3 Hedge Ratio & Effectiveness Tracking
   - 4.4 Hedge Execution Recommendations
5. [Correlation Matrix](#5-correlation-matrix)
   - 5.1 Rolling Pearson Correlation via pandas
   - 5.2 Sector/Asset Class Grouping
   - 5.3 Data Pipeline: From OHLCV to Matrix
   - 5.4 Output Format & Caching
6. [VaR / CVaR](#6-var--cvar)
   - 6.1 Three Methods: Historical, Parametric, Monte Carlo
   - 6.2 Data Sources: Trade PnL vs Portfolio Returns
   - 6.3 Component VaR & Marginal VaR
   - 6.4 Time Scaling (√N Rule)
7. [Kelly Optimization — Post-Backtest Phase 5 Integration](#7-kelly-optimization--post-backtest-phase-5-integration)
   - 7.1 Phase 4 Circular Dependency Resolution
   - 7.2 Kelly Validation Against Max Drawdown
   - 7.3 Kelly-Based Position Sizing Refinement
8. [Risk Dashboard & API Design](#8-risk-dashboard--api-design)
   - 8.1 REST Endpoints
   - 8.2 WebSocket Stream for Real-Time Updates
   - 8.3 Risk Report Generation (PDF/HTML)
9. [Module Design & Class Structure](#9-module-design--class-structure)
   - 9.1 Directory Layout
   - 9.2 Class Diagram
   - 9.3 Data Flow
10. [DuckDB Schema for Risk Results](#10-duckdb-schema-for-risk-results)
11. [Configuration & Settings](#11-configuration--settings)
12. [Domain Model Extensions Needed](#12-domain-model-extensions-needed)
13. [Integration Points with Phases 1-4](#13-integration-points-with-phases-1-4)
14. [New Dependencies](#14-new-dependencies)
15. [Risks & Mitigations](#15-risks--mitigations)
16. [Open Questions for Planning](#16-open-questions-for-planning)

---

## 1. Project State & Codebase Assessment

### Current State (after Phase 1 + Phase 2 + Phase 3 + Phase 4 completion)

| Aspect | Status | Reusable for Phase 5 |
|--------|--------|----------------------|
| DuckDB connection mgr | ✅ `get_db()`, `get_db_async()`, `initialize_database()` | Core connection for OHLCV reads, risk results write |
| Parquet partitioning | ✅ `partition_path()` for `{asset_class}/{year}/{month}/{symbol}_{timeframe}.parquet` | OHLCV data source for beta, correlation, VaR |
| OHLCV DDL | ✅ `ohlcv` table with year/month partition columns | Primary price data source for returns computation |
| `indicator_values` DDL | ✅ Tall-format indicator cache table | ATR for position sizing |
| Config (`ComputeSettings`, `ScreenSettings`, `BacktestSettings`) | ✅ Existing sections | Extend with RiskSettings section |
| Config (`config.yaml`) | ✅ Exists, extensible | Add `risk:` section |
| Structured logging | ✅ `set_correlation_id()`, `get_logger()`, JSON output | Correlation IDs per risk computation |
| Domain models | ✅ `OHLCV`, `Signal`, `Trade`, `Metrics`, `BacktestConfig`, `RiskParams` | `RiskParams` exists — may need extension |
| Test infrastructure | ✅ pytest + asyncio + conftest fixtures with `synthetic_ohlcv` | Test harness for risk computations |
| Indicator registry | ✅ `@indicator` decorator, 10 indicators, `compute_all()` | ATR(14) already available |
| `IndicatorCache` | ✅ `get_latest()`, `get_series()`, `update_cache()`, `rebuild()` | Pre-computed ATR for position sizing |
| `PositionSizer` (Phase 4) | ✅ ATR-based + Kelly + fixed sizing | Core position sizing — Phase 5 refines |
| `MetricsComputer` (Phase 4) | ✅ Sharpe, Sortino, Calmar, Ulcer, MAE/MFE, CAGR | Can extend for risk-specific metrics |
| `TradeLedger` (Phase 4) | ✅ `build_ledger()` → Trade models with MAE/MFE | Trade history for VaR/CVaR computation |
| `BacktestEngine` (Phase 4) | ✅ `run()`, `run_full_analysis()` → `BacktestRunRecord` | Backtest results for Kelly optimization |
| `MonteCarloSimulator` (Phase 4) | ✅ Bootstrap/block bootstrap path simulation | MC engine for Monte Carlo VaR (reuse or compose) |
| `RiskParams` (domain) | ✅ `risk_per_trade`, `max_position_size`, `atr_period`, `beta_benchmark`, `kelly_fraction` | Existing model — needs extension for VaR/CVaR params |
| Risk module | ❌ **Does not exist** — must be created at `backend/app/infrastructure/risk/` | All Phase 5 code goes here |

### Key Insight: What Phase 5 Reuses from Phase 4

Phase 4 built significant infrastructure that Phase 5 directly consumes:

| Phase 4 Component | Phase 5 Use | Is It Ready? |
|-------------------|-------------|--------------|
| `PositionSizer._atr_size()` | Core ATR position sizing calculation | ✅ Ready — formula matches D-01 exactly |
| `PositionSizer._kelly_size()` | Kelly fraction position sizing | ✅ Ready — but Kelly inputs need backtest-derived values |
| `MetricsComputer.compute_mae_mfe()` | VaR input (per-trade PnL) | ✅ Ready |
| `TradeLedger.build_ledger()` | Trade history for VaR/CVaR | ✅ Ready |
| `BacktestEngine.run()` → metrics | Kelly fraction inputs (win rate, avg win/loss) | ✅ Ready |
| `MonteCarloSimulator._simulate_sync()` | MC engine for MC VaR | ⚠️ Needs adaptation: MC VaR uses portfolio return distribution, not synthetic returns |
| `BacktestRunRecord.metrics` | Kelly optimization inputs | ✅ Ready |

### What Phase 5 Must Create

All Phase 5 code goes in a new module `backend/app/infrastructure/risk/` — alongside `screener/`, `ingest/`, and `backtest/`:

```
backend/app/infrastructure/risk/
├── __init__.py                  # Exports: RiskEngine, run_risk_analysis, RiskSettings
├── engine.py                    # RiskEngine — orchestrator: coordinate all risk computations
├── beta.py                      # BetaHedger — OLS beta, hedge ratio, effectiveness
├── correlation.py               # CorrelationAnalyzer — rolling correlation matrix, sector aggregation
├── var.py                       # VaRCalculator — Historical, Parametric, MC VaR/CVaR
├── kelly.py                     # KellyOptimizer — Kelly fraction from backtest results, max DD validation
├── position_sizing.py           # PositionSizingRefiner — enhanced sizing with risk constraints
├── reporting.py                 # RiskReportGenerator — PDF/HTML report generation
├── streaming.py                 # WebSocket handler for real-time risk updates
├── models.py                    # Risk-specific Pydantic models
└── metrics.py                   # RiskMetricsComputer — additional risk-specific metrics (optional)
```

---

## 2. Critical Architecture: What Phase 4 Already Built for Phase 5

### 2.1 PositionSizer Lives in Phase 4 — Phase 5 Composes on Top

**Critical finding:** The `PositionSizer` class in `backend/app/infrastructure/backtest/sizing.py` already implements:

- **ATR-based sizing** — `_atr_size()` with `risk_per_trade`, `atr_multiplier`, `max_position_pct`
- **Kelly sizing** — `_kelly_size()` with `kelly_fraction`, `win_rate`, `avg_win_avg_loss_ratio`

The D-01 formula (`position_size = risk_pct × equity / (ATR × multiplier)`) is **already implemented** in `sizing.py:88-132`. D-15 Kelly formula (`f = p - q/b`) is **already implemented** in `sizing.py:134-172`.

**Implication for Phase 5:** Phase 5 should NOT re-implement position sizing from scratch. Instead:

1. **Create `RiskEngine`** that consumes `PositionSizer` and adds risk-layer constraints:
   - Cross-portfolio correlation checks (diversification)
   - Beta-adjusted exposure limits
   - VaR-based position limits (e.g., "no single position > 2× portfolio VaR")
   - Leverage limits from risk settings
2. **Refine Kelly** — Phase 4 Kelly uses preset `win_rate` and `avg_win_avg_loss_ratio`. Phase 5 Kelly should:
   - Read actual backtest metrics from `BacktestRunRecord`
   - Run the two-pass Kelly calculation (first pass with fixed sizing, then with computed Kelly)
   - Validate against max drawdown constraint (D-17)
3. **Add risk-aware wrapper** — `PositionSizingRefiner` wraps `PositionSizer` with risk overlays

### 2.2 TradeLedger Supplies VaR Data

`TradeLedger.build_ledger()` returns `list[Trade]` with `pnl`, `mae`, `mfe`, `hold_duration_bars`. For VaR/CVaR:

- **Historical VaR:** Uses per-trade PnL distribution directly — simple percentile
- **Parametric VaR:** Uses trade PnL mean/stdev — Gaussian VaR
- **Monte Carlo VaR:** Uses trade PnL distribution for resampling

**However** — per-trade PnL VaR is NOT the same as portfolio VaR. Trade-based VaR misses:
- Concurrent positions' correlation effects
- Time-varying volatility within positions
- Portfolio-level diversification

**Recommendation:** Provide BOTH:
- **Per-position VaR** from trade PnL (simple, fast, useful for position limits)
- **Portfolio VaR** from daily portfolio returns (requires daily revaluation of all positions)

### 2.3 MetricsComputer Can Be Extended for Risk Metrics

`MetricsComputer` computes: Sharpe, Sortino, Calmar, Max DD, Win Rate, Expectancy, Profit Factor, SQN, CAGR, Ulcer.

For Phase 5, add:
- VaR (95%, 99%)
- CVaR / Expected Shortfall
- Beta (vs benchmark)
- Tracking Error
- Information Ratio
- Correlation matrix stats

These can go in a new `RiskMetricsComputer` in `risk/metrics.py` or be added to the existing `MetricsComputer`. **Recommendation:** Create separate `risk/metrics.py` to keep backtest and risk concerns cleanly separated.

### 2.4 MonteCarloSimulator Can Be Composed for MC VaR

Phase 4's `MonteCarloSimulator` generates synthetic equity paths from lognormal returns. For Phase 5 MC VaR:

- **Option A: Reuse directly** — Feed the simulated paths' daily returns into VaR computation
- **Option B: Create MC VaR-specific simulation** — Bootstrap from historical returns directly (no synthetic generation), compute VaR from the resulting return distribution

**Recommendation: Option B** — MC VaR should bootstrap from actual historical returns, not synthetic lognormal. This captures real-market skewness and kurtosis. The Phase 4 MC simulator is fine for strategic planning; MC VaR needs empirical distribution fidelity.

**Design:** Create a dedicated method in `var.py` that uses the same bootstrap machinery (from `MonteCarloSimulator._block_bootstrap`) but applies it to portfolio returns with VaR computation as the output.

---

## 3. ATR Position Sizing — Refinement vs Greenfield

### 3.1 Existing `PositionSizer` Capabilities

```python
# From backend/app/infrastructure/backtest/sizing.py (already built in Phase 4)
class PositionSizer:
    def _atr_size(self, close, entries, initial_cash, params, atr_series) -> pd.DataFrame:
        """ATR-based position sizing.
        
        Formula: position_size = risk_per_trade * equity / (ATR * atr_multiplier)
        """
        risk_per_trade = float(params.get("risk_per_trade", 0.01))      # 1% default
        atr_multiplier = float(params.get("atr_multiplier", 2.0))       # 2× ATR default
        max_position_pct = float(params.get("max_position_pct", 0.25))  # 25% max allocation
        # ... vectorized computation ...
```

**Existing params match D-01/D-02 requirements exactly.** No changes needed to the core formula.

### 3.2 What Phase 5 Needs to Add

| Capability | Where It Lives | Phase 5 Addition |
|------------|---------------|-------------------|
| Core ATR formula | `backtest/sizing.py:_atr_size()` | No change needed |
| Long position sizing | `backtest/sizing.py:_atr_size()` | ✅ Already handles both directions via `entries` boolean |
| Short position sizing | — | D-03 requires short sizing. Formula is same — need to ensure `entries` mask includes short entries. Verify in `PositionSizer` that direction handling exists. |
| Cross-portfolio risk check | — | **NEW in Phase 5:** After computing per-symbol size, check correlation exposure. E.g., if sizing gives 25% to AAPL and 25% to MSFT (highly correlated), reduce combined exposure. |
| VaR-based position cap | — | **NEW in Phase 5:** `min(ATR_size, VaR_based_max)` where VaR cap = `portfolio_VaR × max_var_ratio / position_var` |
| Leverage-aware sizing | — | **NEW in Phase 5:** If using margin, scale position sizes by available leverage, bounded by risk limits |

### 3.3 ATR Integration with PositionSizer API

Phase 5's `PositionSizingRefiner` wraps `PositionSizer`:

```python
class PositionSizingRefiner:
    """Enhanced position sizing with risk overlays.
    
    Composes on top of Phase 4's PositionSizer, adding:
    - Correlation-aware position limits
    - VaR-based position caps
    - Beta-adjusted sizing for hedging contexts
    - Leverage-aware sizing with risk bounds
    """
    
    def __init__(self) -> None:
        from backend.app.infrastructure.backtest.sizing import PositionSizer
        self._sizer = PositionSizer()
    
    async def compute_size_with_risk_constraints(
        self,
        close: pd.DataFrame,
        entries: pd.DataFrame,
        method: str,
        initial_cash: float,
        params: dict,
        correlation_matrix: pd.DataFrame | None = None,
        position_var: pd.Series | None = None,
        portfolio_var: float | None = None,
        beta_values: pd.Series | None = None,
    ) -> pd.DataFrame:
        """Compute position sizes with risk overlays.
        
        1. Compute base size using PositionSizer
        2. Apply correlation-aware diversification limit
        3. Apply VaR-based position cap
        4. Apply beta-adjusted constraints
        5. Return constrained size DataFrame
        """
        # Step 1: Base sizing
        base_size = self._sizer.compute_position_size(
            close, entries, method, initial_cash, params
        )
        
        # Steps 2-5: Apply risk constraints...
        # ...
        return constrained_size
```

**This design preserves the existing `PositionSizer`** while adding risk overlays in Phase 5. No changes needed to Phase 4 code.

---

## 4. Beta Hedging

### 4.1 Beta Computation via OLS Regression

**Decision D-05:** Rolling 60-day beta via OLS: `r_asset = α + β × r_benchmark + ε`

**Implementation choices:**

| Method | Library | Pros | Cons |
|--------|---------|------|------|
| `scipy.stats.linregress()` | SciPy | Simple, well-documented, returns R², p-value, std_err | Slower for large arrays |
| `numpy.linalg.lstsq()` | NumPy | Fast, vectorized | Manual R²/std_err computation |
| `pandas.ols()` | — | **REMOVED** in pandas 2.0 | Not available |
| `statsmodels.OLS()` | statsmodels | Full regression stats, robust errors | Heavier dependency |

**Recommendation: `scipy.stats.linregress()`** — Clean API, returns all needed statistics (slope=β, intercept=α, rvalue=R², stderr). Best fit for rolling computations:

```python
from scipy import stats

def compute_rolling_beta(
    asset_returns: pd.Series,
    benchmark_returns: pd.Series,
    window: int = 60,
    min_periods: int = 20,
) -> pd.DataFrame:
    """Compute rolling 60-day beta via OLS regression.
    
    Args:
        asset_returns: Daily returns for the asset.
        benchmark_returns: Daily returns for the benchmark.
        window: Rolling window in days (default 60 per D-04).
        min_periods: Minimum observations required.
    
    Returns:
        DataFrame with columns:
        - beta: Rolling beta coefficient
        - alpha: Rolling intercept
        - r_squared: Rolling R² from regression
        - std_err: Standard error of beta
        - p_value: P-value of beta estimate
        - tracking_error: Std dev of residuals
    """
    def rolling_regression(end_idx: int) -> dict:
        start = max(0, end_idx - window)
        x = benchmark_returns.iloc[start:end_idx].values
        y = asset_returns.iloc[start:end_idx].values
        if len(x) < min_periods or len(y) < min_periods:
            return {"beta": float("nan"), "alpha": float("nan"), ...}
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        residuals = y - (slope * x + intercept)
        return {
            "beta": slope,
            "alpha": intercept,
            "r_squared": r_value ** 2,
            "std_err": std_err,
            "p_value": p_value,
            "tracking_error": float(np.std(residuals)),
        }
    
    # Apply rolling
    results = [rolling_regression(i) for i in range(1, len(asset_returns) + 1)]
    return pd.DataFrame(results, index=asset_returns.index)
```

**Performance note:** For 5000 symbols, a rolling regression on each is O(n × m) where n = symbols × periods. This is expensive. **Optimization strategies:**

| Strategy | Description | Performance Gain |
|----------|-------------|-----------------|
| **A: All assets at once** (preferred) | Vectorize beta across all symbols: `returns_matrix @ benchmark / (benchmark @ benchmark)` | ~100× vs per-symbol loop |
| **B: Cache beta results** | Store rolling beta in DuckDB, update incrementally | Avoids recomputation on every request |
| **C: Subset computation** | Only compute beta for actively held positions | ~10× reduction for typical portfolios |

**Recommendation: Option A + Option B** — The beta formula simplifies to: `β = cov(r_asset, r_benchmark) / var(r_benchmark)` which can be vectorized across all symbols using pandas rolling cov/corr:

```python
def compute_beta_vectorized(
    returns_matrix: pd.DataFrame,  # shape (n_days, n_symbols)
    benchmark_returns: pd.Series,  # length n_days
    window: int = 60,
) -> pd.DataFrame:
    """Vectorized rolling beta across all symbols.
    
    β = Cov(r_asset, r_benchmark) / Var(r_benchmark)
    
    Args:
        returns_matrix: Daily returns for all assets (columns = symbols).
        benchmark_returns: Daily returns for the benchmark.
        window: Rolling window.
    
    Returns:
        DataFrame of shape (n_days, n_symbols) with rolling betas.
    """
    # Rolling covariance between each asset and benchmark
    rolling_cov = returns_matrix.rolling(window).cov(benchmark_returns)
    # Rolling variance of benchmark
    rolling_var = benchmark_returns.rolling(window).var()
    return rolling_cov.divide(rolling_var, axis=0)
```

This is **fully vectorized** — no Python loops over symbols.

### 4.2 Benchmark Data Source Strategy

**Decision D-04:** SPY for US equities, BTC for crypto, major index for forex/commodities.

**Problem:** The benchmark price data must be in the same DuckDB `ohlcv` table as regular assets. Phase 2 ingests these as regular symbols.

| Asset Class | Benchmark Symbol | Phase 2 Ingested? | Note |
|-------------|-----------------|-------------------|------|
| Equities | `SPY` | ✅ Yes (in default assets.equities) | Already available |
| Crypto | `BTCUSDT` | ✅ Yes (in default assets.crypto) | Already available |
| Forex | `EURUSD` or index basket | ✅ Yes (in default assets.forex) | Or use `USDX` (DXY) |
| Commodities | `GC1!` (Gold futures) | ✅ Yes (in default assets.commodities) | Or broad commodity index |
| Indices | `SPX` or `NDX` | ✅ Yes (in default assets.indices) | Self-hedge possible |

**Mapping config (D-21):**

```yaml
risk:
  beta_benchmark_map:
    equities: SPY
    crypto: BTCUSDT
    forex: EURUSD
    commodities: GC1!
    indices: SPX
```

**Benchmark return computation:** Same as asset returns — daily percent change of `close` price. Use `pandas.Series.pct_change()`.

### 4.3 Hedge Ratio & Effectiveness Tracking

**Decision D-06:** `hedge_ratio = beta × position_value / benchmark_value`

```python
def compute_hedge_ratio(
    beta: float,
    position_value: float,
    benchmark_price: float,
    benchmark_contract_multiplier: float = 1.0,
) -> dict:
    """Compute hedge ratio for a position.
    
    hedge_ratio = beta × position_value / (benchmark_price × contract_multiplier)
    
    Args:
        beta: Current rolling beta.
        position_value: Current market value of the position.
        benchmark_price: Current benchmark price.
        benchmark_contract_multiplier: Contract multiplier for futures (e.g., 100 for ES).
    
    Returns:
        Dict with hedge_ratio (notional), hedge_units (contracts/shares),
        and hedge_value (dollar amount).
    """
    hedge_value = beta * position_value
    hedge_units = hedge_value / (benchmark_price * benchmark_contract_multiplier)
    return {
        "hedge_ratio": beta,
        "hedge_value": hedge_value,
        "hedge_units": hedge_units,
        "hedge_instrument": "inverse_etf" if beta > 0 else "direct_etf",  # if long asset, short hedge
    }
```

**Decision D-07 — Hedge effectiveness tracking:**

| Metric | Formula | Interpretation |
|--------|---------|---------------|
| R² | From regression | Proportion of asset variance explained by benchmark. High R² = good hedge |
| Tracking Error | `std(residuals)` × √252 | Annualized std of unexplained returns. Lower = better hedge |
| Hedge Cost | Carry + fees + roll costs | Total cost of maintaining the hedge position |

```python
@dataclass
class HedgeEffectiveness:
    """Metrics for evaluating hedge quality."""
    r_squared: float           # 0-1, higher is better
    tracking_error: float      # Annualized, lower is better
    hedge_cost_annual: float   # As decimal fraction of hedged value
    beta_stability: float      # Std of beta over evaluation window, lower = more stable
    recommendation: str        # 'hedge_required', 'hedge_optional', 'no_hedge_needed'
```

### 4.4 Hedge Execution Recommendations

Based on effectiveness, the `BetaHedger` makes actionable recommendations:

```python
def recommend_hedge_action(hedge_effectiveness: HedgeEffectiveness) -> str:
    """Generate hedge recommendation.
    
    Rules:
    - beta > 0.5 AND R² > 0.7 → Recommend hedge (strong relationship)
    - beta > 0.3 AND R² > 0.4 → Consider hedge (moderate)
    - beta < 0.3 OR R² < 0.2 → No hedge needed (weak relationship)
    - tracking_error > 0.15 → Hedge may not be effective (high residual risk)
    - hedge_cost > 0.03 → Evaluate cost/benefit (hedge costs > 3% annual)
    """
    ...
```

Output format (JSON for API):

```json
{
    "symbol": "AAPL",
    "asset_class": "equities",
    "beta": 1.15,
    "beta_std_err": 0.08,
    "r_squared": 0.65,
    "tracking_error_annual": 0.12,
    "hedge_ratio": 1.15,
    "hedge_value_usd": 115000.0,
    "hedge_units": 230,  # SPY shares to short
    "hedge_cost_annual_pct": 0.008,
    "recommendation": "hedge_required",
    "hedge_instrument": "SH",  # Inverse SPY ETF
    "last_updated": "2026-06-19T14:30:00Z"
}
```

---

## 5. Correlation Matrix

### 5.1 Rolling Pearson Correlation via pandas

**Decision D-08:** 30-day rolling correlation using daily returns, Pearson correlation.

**Implementation — pure pandas, no loop:**

```python
def compute_correlation_matrix(
    returns_matrix: pd.DataFrame,
    window: int = 30,
    min_periods: int = 15,
) -> pd.DataFrame:
    """Compute rolling pairwise Pearson correlation matrix.
    
    Args:
        returns_matrix: Daily returns, shape (n_days, n_symbols).
        window: Rolling window in days (default 30 per D-08).
        min_periods: Minimum observations for a valid correlation.
    
    Returns:
        3D structure: for each timestamp, an N×N correlation matrix.
        Represented as a DataFrame with MultiIndex (timestamp, symbol_i, symbol_j).
        Or: latest correlations as N×N DataFrame.
    """
    # pandas rolling corr — fully vectorized
    return returns_matrix.rolling(window, min_periods=min_periods).corr(
        pairwise=True  # Compute all pairwise correlations
    )
```

**Key API discovery:** `pandas.DataFrame.rolling().corr(other=None, pairwise=True)` — when `other=None` and `pairwise=True`, computes the full N×N pairwise correlation matrix for each rolling window. This is **fully vectorized** and handles the entire universe in one call.

```python
# Example: 30-day rolling correlation for 5000 symbols × 252 days
# returns_matrix shape: (252, 5000)
corr = returns_matrix.rolling(30).corr(pairwise=True)
# corr shape: (252, 5000×5000) — but pandas handles it efficiently
# corr.index: MultiIndex (timestamp, symbol_i)
# corr.columns: symbol_j
```

### 5.2 Sector/Asset Class Grouping

**Decision D-09:** Sectors/asset classes from screener metadata (Phase 3). Assets without sector → "Unclassified".

The `symbol_metadata` table (Phase 2) has `asset_class` per symbol. Phase 3 screener may add `sector` metadata. If not available, derive from `asset_class`:

```python
def aggregate_correlation_by_group(
    correlation_matrix: pd.DataFrame,
    group_map: dict[str, str],  # symbol -> group_name
) -> pd.DataFrame:
    """Aggregate correlation matrix to sector/asset-class level.
    
    For each group, compute average correlation:
    - Intra-group correlation: average of within-group pairwise correlations
    - Inter-group correlation: average of cross-group pairwise correlations
    
    Args:
        correlation_matrix: N×N DataFrame of Pearson correlations.
        group_map: Mapping of symbol -> group label.
    
    Returns:
        M×M DataFrame of group-level average correlations (M = number of groups).
    """
    groups = list(set(group_map.values()))
    n_groups = len(groups)
    
    # Map each symbol to its group
    group_series = pd.Series(group_map)
    
    # Group-level aggregation
    result = pd.DataFrame(index=groups, columns=groups, dtype=float)
    
    for i, g1 in enumerate(groups):
        g1_symbols = [s for s, g in group_map.items() if g == g1 and s in correlation_matrix.columns]
        for j, g2 in enumerate(groups):
            g2_symbols = [s for s, g in group_map.items() if g == g2 and s in correlation_matrix.columns]
            if i == j and len(g1_symbols) > 1:
                # Intra-group: average within-group correlations
                sub = correlation_matrix.loc[g1_symbols, g1_symbols]
                result.loc[g1, g2] = sub.values[np.triu_indices_from(sub.values, k=1)].mean()
            elif i != j and g1_symbols and g2_symbols:
                # Inter-group: average cross-group correlations
                values = correlation_matrix.loc[g1_symbols, g2_symbols].values
                result.loc[g1, g2] = values.mean()
            else:
                result.loc[g1, g2] = float("nan")
    
    return result
```

### 5.3 Data Pipeline: From OHLCV to Matrix

```
OHLCV (DuckDB) → Daily Returns (pct_change) → Rolling Correlation → Sector Aggregation → Heatmap JSON

Step 1: Query OHLCV from DuckDB
  SELECT symbol, timestamp, close
  FROM ohlcv
  WHERE timeframe = '1D'
  ORDER BY symbol, timestamp

Step 2: Pivot to returns matrix
  pivoted = df.pivot(index='timestamp', columns='symbol', values='close')
  returns = pivoted.pct_change().dropna(how='all')

Step 3: Rolling correlation
  corr_matrix = returns.rolling(30).corr(pairwise=True)

Step 4: Get latest matrix (most recent timestamp)
  latest_timestamp = corr_matrix.index.get_level_values(0).max()
  latest_corr = corr_matrix.loc[latest_timestamp]

Step 5: Sector aggregation
  group_map = {row.symbol: row.asset_class for row in metadata}  # or sector
  sector_corr = aggregate_correlation_by_group(latest_corr, group_map)

Step 6: Format for API
  heatmap_json = format_heatmap(latest_corr)
```

### 5.4 Output Format & Caching

**Decision D-10:** Heatmap-ready JSON.

```json
{
    "timestamp": "2026-06-19T00:00:00Z",
    "window_days": 30,
    "symbols": ["AAPL", "MSFT", "GOOGL", "NVDA", "SPY", "BTCUSDT"],
    "correlation_matrix": [
        [1.0, 0.85, 0.72, 0.63, 0.89, 0.12],
        [0.85, 1.0, 0.68, 0.55, 0.82, 0.08],
        [0.72, 0.68, 1.0, 0.48, 0.71, 0.15],
        [0.63, 0.55, 0.48, 1.0, 0.59, 0.05],
        [0.89, 0.82, 0.71, 0.59, 1.0, 0.10],
        [0.12, 0.08, 0.15, 0.05, 0.10, 1.0]
    ],
    "sector_matrix": {
        "rows": ["Technology", "Crypto", "Index"],
        "matrix": [
            [0.72, 0.10, 0.81],
            [0.10, 1.0, 0.08],
            [0.81, 0.08, 1.0]
        ]
    },
    "high_correlation_pairs": [
        {"symbols": ["AAPL", "MSFT"], "correlation": 0.85},
        {"symbols": ["SPY", "AAPL"], "correlation": 0.89}
    ],
    "diversification_score": 0.45
}
```

**Caching strategy (D-25):** Rolling correlation is computationally expensive for large universes. Cache previous rolling windows in DuckDB for incremental updates:

```sql
-- Cache rolling correlation snapshots
CREATE TABLE IF NOT EXISTS risk_correlation_snapshots (
    timestamp TIMESTAMPTZ NOT NULL,
    window_days INTEGER NOT NULL,
    symbols_json VARCHAR NOT NULL,       -- Ordered list of symbols
    matrix_json VARCHAR NOT NULL,        -- N×N correlation matrix as JSON array
    sector_matrix_json VARCHAR,          -- Sector-level aggregated matrix
    symbol_count INTEGER NOT NULL,
    computed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (timestamp, window_days)
);
```

Incremental update: only recompute the latest correlation snapshot when new price data arrives. Historical snapshots are immutable.

---

## 6. VaR / CVaR

### 6.1 Three Methods: Historical, Parametric, Monte Carlo

**Decision D-11:** Three VaR methods — Historical, Parametric (Gaussian), Monte Carlo.

#### Method 1: Historical VaR

```python
def historical_var(
    returns: pd.Series | pd.DataFrame,
    confidence: float = 0.95,
) -> float | pd.Series:
    """Compute historical VaR at the given confidence level.
    
    VaR = -percentile(returns, 1 - confidence)
    Positive VaR = loss amount. E.g., VaR=0.02 means 2% loss at 95% confidence.
    
    Args:
        returns: Series or DataFrame of portfolio/asset returns.
        confidence: Confidence level (default 0.95 for 95%).
    
    Returns:
        VaR value(s). Positive number = expected loss.
    """
    alpha = 1 - confidence
    if isinstance(returns, pd.DataFrame):
        return -returns.quantile(alpha)
    return -float(returns.quantile(alpha))
```

#### Method 2: Parametric (Gaussian) VaR

```python
from scipy.stats import norm

def parametric_var(
    returns: pd.Series | pd.DataFrame,
    confidence: float = 0.95,
) -> float | pd.Series:
    """Compute parametric (Gaussian) VaR.
    
    VaR = -(mean + z_score × std)
    Where z_score = norm.ppf(1 - confidence)
    
    Args:
        returns: Series or DataFrame of portfolio/asset returns.
        confidence: Confidence level.
    
    Returns:
        Parametric VaR value. Positive = expected loss.
    """
    z = norm.ppf(1 - confidence)
    if isinstance(returns, pd.DataFrame):
        mu = returns.mean()
        sigma = returns.std()
        return -(mu + z * sigma)
    mu = float(returns.mean())
    sigma = float(returns.std())
    return -(mu + z * sigma)
```

#### Method 3: Monte Carlo VaR

```python
def monte_carlo_var(
    returns: pd.Series,
    confidence: float = 0.95,
    n_simulations: int = 10000,
    method: str = "bootstrap",
    block_size: int = 20,
) -> dict:
    """Compute Monte Carlo VaR/CVaR.
    
    Bootstraps historical returns to generate simulated return paths,
    then computes VaR from the simulated distribution.
    
    Unlike Phase 4's Monte Carlo (which simulates forward equity curves),
    this bootstraps directly from historical returns for VaR estimation.
    
    Args:
        returns: Historical return series.
        confidence: Confidence level.
        n_simulations: Number of bootstrap simulations.
        method: 'bootstrap' or 'block_bootstrap'.
        block_size: Block size for block bootstrap.
    
    Returns:
        Dict with var, cvar, and confidence interval.
    """
    n = len(returns)
    rng = np.random.default_rng(seed=42)
    
    if method == "block_bootstrap":
        # Block bootstrap — preserves autocorrelation
        samples = _block_bootstrap(returns.values, n_simulations, block_size, n)
    else:
        indices = rng.integers(0, n, size=(n_simulations, n))
        samples = returns.values[indices]
    
    # Compute mean return for each simulation
    simulated_means = samples.mean(axis=1)
    
    # VaR from simulated distribution
    alpha = 1 - confidence
    var = -float(np.percentile(simulated_means, alpha * 100))
    
    # CVaR = average of losses beyond VaR
    losses = simulated_means[simulated_means < -var]
    cvar = -float(losses.mean()) if len(losses) > 0 else var
    
    # Confidence interval of VaR estimate
    ci_lower = -float(np.percentile(simulated_means, (alpha - 0.01) * 100))
    ci_upper = -float(np.percentile(simulated_means, (alpha + 0.01) * 100))
    
    return {
        "var": var,
        "cvar": cvar,
        "confidence": confidence,
        "method": f"monte_carlo_{method}",
        "n_simulations": n_simulations,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
    }
```

### 6.2 Data Sources: Trade PnL vs Portfolio Returns

**Key architectural decision:** VaR needs daily P&L data. Two sources:

| Source | Comes From | Pros | Cons |
|--------|-----------|------|------|
| **Trade PnL** | `TradeLedger` (Phase 4) | Per-trade granularity, includes MAE/MFE | Only captures closed trades, not open positions |
| **Daily Portfolio Returns** | `BacktestRunRecord` → equity curve | Full portfolio view, captures open positions | Requires daily revaluation |

**Recommendation:** Use **daily portfolio returns** for portfolio-level VaR (from equity curve), and **trade-level PnL** for position-level VaR (from TradeLedger). The `VaRCalculator` class abstracts the data source:

```python
class VaRCalculator:
    """Value at Risk and Conditional VaR computation.
    
    Supports three methods (Historical, Parametric, Monte Carlo)
    and two data sources (portfolio returns, trade PnL).
    """
    
    async def compute_var(
        self,
        returns: pd.Series | None = None,
        trade_pnl: pd.Series | None = None,
        method: Literal["historical", "parametric", "monte_carlo"] = "historical",
        confidence: float = 0.95,
        horizon_days: int = 1,
    ) -> VaRResult:
        """Compute VaR/CVaR from available data sources.
        
        Priority: if returns provided, use portfolio-returns VaR.
        If only trade_pnl, use trade-based VaR approximation.
        """
        ...
```

### 6.3 Component VaR and Marginal VaR

**Decision D-14:** Component VaR and Marginal VaR for portfolio decomposition.

```python
def component_var(
    weights: np.ndarray,
    covariance_matrix: np.ndarray,
    portfolio_var: float,
) -> np.ndarray:
    """Compute Component VaR for each position.
    
    Component VaR = weight_i × (cov_matrix @ weights)_i / portfolio_std × portfolio_VaR
    
    This decomposes portfolio VaR into contributions from each position.
    Sum of component VaRs = portfolio VaR.
    
    Args:
        weights: Array of position weights (must sum to 1.0).
        covariance_matrix: N×N covariance matrix of returns.
        portfolio_var: Total portfolio VaR.
    
    Returns:
        Array of component VaR values (one per position).
    """
    portfolio_std = np.sqrt(weights.T @ covariance_matrix @ weights)
    marginal_contrib = (covariance_matrix @ weights) / portfolio_std
    component_var_values = weights * marginal_contrib / portfolio_std * portfolio_var
    return component_var_values


def marginal_var(
    weights: np.ndarray,
    covariance_matrix: np.ndarray,
    portfolio_var: float,
) -> np.ndarray:
    """Compute Marginal VaR for each position.
    
    Marginal VaR = ∂(VaR) / ∂(weight_i)
    = (cov_matrix @ weights)_i / portfolio_std × (VaR / portfolio_value)
    
    Positive = increasing this position increases portfolio risk.
    Negative = increasing this position decreases portfolio risk (hedge).
    
    Args:
        weights: Array of position weights.
        covariance_matrix: N×N covariance matrix.
        portfolio_var: Total portfolio VaR.
    
    Returns:
        Array of marginal VaR values.
    """
    portfolio_std = np.sqrt(weights.T @ covariance_matrix @ weights)
    marginal_contrib = (covariance_matrix @ weights) / portfolio_std
    marginal_var_values = marginal_contrib * portfolio_var / portfolio_std
    return marginal_var_values
```

### 6.4 Time Scaling (√N Rule)

**Decision D-12:** Time horizons: 1-day (default), 10-day (√10 scaling).

```python
def scale_var(
    var_1d: float,
    horizon_days: int,
    method: Literal["sqrt", "empirical"] = "sqrt",
) -> float:
    """Scale VaR from 1-day to N-day horizon.
    
    Square root rule: VaR_N = VaR_1 × √N
    
    Args:
        var_1d: 1-day VaR value.
        horizon_days: Target horizon in days.
        method: 'sqrt' for √N rule, 'empirical' for actual resampling.
    
    Returns:
        Scaled VaR for the specified horizon.
    """
    if method == "sqrt":
        return var_1d * math.sqrt(horizon_days)
    # 'empirical' — compute from overlapping N-day returns
    raise NotImplementedError("Empirical scaling deferred")
```

---

## 7. Kelly Optimization — Post-Backtest Phase 5 Integration

### 7.1 Phase 4 Circular Dependency Resolution

**The Kelly Circular Dependency** (identified in Phase 4 Research §4.3):

```
To compute Kelly fraction: need win_rate, avg_win, avg_loss
To compute win_rate, avg_win, avg_loss: need backtest results
To run backtest: need position sizing (could be Kelly)
```

**Phase 4 resolution:** Two-pass approach (first pass with fixed sizing, second pass with Kelly fraction from first-pass metrics).

**Phase 5 refinement:** Phase 5 owns the Kelly computation as a **post-backtest analysis**:

| Step | Phase | What Happens |
|------|-------|-------------|
| 1 | Phase 4 | Run backtest with fixed sizing → get trade ledger with win_rate, avg_win, avg_loss |
| 2 | Phase 5 | `KellyOptimizer.compute_kelly_from_backtest(backtest_record)` → optimal f* |
| 3 | Phase 5 | `KellyOptimizer.validate_against_max_dd(f*, backtest_record)` → constrained f* |
| 4 | Phase 5 | `KellyOptimizer.recommend_kelly(unconstrained, constrained)` → final recommendation |
| 5 | Phase 5 | Emit recommendation as `risk/recommended_kelly_fraction` for next backtest |

This keeps Kelly computation as a **Phase 5 risk analytic** that consumes Phase 4 backtest results, rather than making it part of the backtest loop itself.

### 7.2 Kelly Validation Against Max Drawdown

**Decision D-17:** `max_kelly = 2 × max_dd_target / (1 + max_dd_target)`

```python
def validate_kelly_against_max_dd(
    kelly_fraction: float,
    backtest_max_dd: float,
    max_dd_target: float = 0.25,  # 25% max drawdown tolerance
) -> dict:
    """Validate Kelly fraction against max drawdown constraint.
    
    D-17: max_kelly = 2 × max_dd_target / (1 + max_dd_target)
    
    If computed Kelly exceeds max_kelly, reduce to half-Kelly or
    to the level that keeps expected drawdown within bounds.
    
    Args:
        kelly_fraction: Raw Kelly fraction from backtest metrics.
        backtest_max_dd: Maximum drawdown observed in the backtest.
            Used to calibrate the relationship between Kelly and DD.
        max_dd_target: Maximum acceptable drawdown (default 25%).
    
    Returns:
        Dict with original_kelly, constrained_kelly, max_dd_kelly,
        backtest_max_dd, is_valid, recommendation.
    """
    # D-17 formula: maximum Kelly that keeps expected DD within target
    max_dd_kelly = 2 * max_dd_target / (1 + max_dd_target)
    
    # Constrained Kelly = min(raw Kelly, max_dd_kelly, half-Kelly default)
    half_kelly = kelly_fraction * 0.5
    constrained = min(kelly_fraction, max_dd_kelly)
    
    return {
        "original_kelly": kelly_fraction,
        "constrained_kelly": constrained,
        "max_dd_kelly": max_dd_kelly,
        "max_dd_target": max_dd_target,
        "backtest_max_dd": backtest_max_dd,
        "is_valid": constrained >= half_kelly,
        "recommendation": constrained if constrained >= half_kelly else half_kelly,
    }
```

### 7.3 Kelly-Based Position Sizing Refinement

The `KellyOptimizer` feeds into `PositionSizingRefiner`:

```python
class KellyOptimizer:
    """Kelly Criterion optimization from backtest results.
    
    Consumes Phase 4 BacktestRunRecord to compute optimal Kelly fraction,
    validates against max drawdown constraints, and produces
    recommended position sizing parameters.
    """
    
    async def optimize_from_backtest(
        self,
        backtest_record: BacktestRunRecord,
        trades: list[Trade],
        max_dd_target: float = 0.25,
        use_half_kelly: bool = True,
    ) -> KellyRecommendation:
        """Compute Kelly-optimal position sizing from backtest results.
        
        Steps:
        1. Extract win_rate, avg_win, avg_loss from trade ledger
        2. Compute Kelly fraction: f* = p - q/b
        3. Validate against max drawdown constraint
        4. Apply half-Kelly if configured
        5. Return recommendation with sizing params
        """
        # Step 1: Extract trade statistics
        winning_trades = [t for t in trades if t.pnl and t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl and t.pnl <= 0]
        
        win_rate = len(winning_trades) / max(len(trades), 1)
        avg_win = float(np.mean([t.pnl for t in winning_trades])) if winning_trades else 0
        avg_loss = float(abs(np.mean([t.pnl for t in losing_trades]))) if losing_trades else 1
        avg_win_loss_ratio = avg_win / max(avg_loss, 0.01)
        
        # Step 2: Kelly formula
        q = 1.0 - win_rate
        kelly_f = win_rate - q / max(avg_win_loss_ratio, 0.01)
        kelly_f = max(0.0, min(kelly_f, 1.0))  # Clamp to [0, 1]
        
        # Step 3: Validate against max DD
        validation = validate_kelly_against_max_dd(
            kelly_f, backtest_record.metrics.max_dd if backtest_record.metrics else 0.3,
            max_dd_target,
        )
        
        # Step 4: Apply half-Kelly
        recommended = validation["recommendation"]
        if use_half_kelly and recommended > 0.5 * kelly_f:
            recommended = min(recommended, 0.5 * kelly_f)
        
        return KellyRecommendation(
            asset_class=backtest_record.symbol,
            win_rate=win_rate,
            avg_win_loss_ratio=avg_win_loss_ratio,
            full_kelly=kelly_f,
            constrained_kelly=validation["constrained_kelly"],
            recommended_kelly=recommended,
            is_valid=validation["is_valid"],
            suggested_position_sizing="kelly",
            suggested_params={
                "kelly_fraction": recommended,
                "risk_per_trade": recommended * 0.02,  # Scale risk to Kelly
            },
        )
```

---

## 8. Risk Dashboard & API Design

### 8.1 REST Endpoints

**Decision D-18:** REST endpoints for risk metrics.

| Endpoint | Method | Purpose | Query Params |
|----------|--------|---------|-------------|
| `/api/v1/risk/position-size` | POST | Compute optimal position size | `symbol`, `method`, `params`, `portfolio_id` |
| `/api/v1/risk/beta` | GET | Get beta for symbols | `symbols[]`, `benchmark`, `window` |
| `/api/v1/risk/beta/{symbol}` | GET | Get beta for one symbol | `benchmark`, `window` |
| `/api/v1/risk/correlation` | GET | Get correlation matrix | `symbols[]`, `window`, `group_by` |
| `/api/v1/risk/correlation/{symbol}` | GET | Get correlations for one symbol | `window`, `limit` |
| `/api/v1/risk/var` | GET | Compute VaR/CVaR | `symbols[]`, `confidence`, `method`, `horizon` |
| `/api/v1/risk/kelly` | POST | Kelly optimization | `backtest_run_id`, `max_dd_target` |
| `/api/v1/risk/report` | GET | Generate risk report (PDF/HTML) | `portfolio_id`, `format` |
| `/api/v1/risk/summary` | GET | Summary of all risk metrics | `portfolio_id` |

**Response format (consistent across endpoints):**

```json
{
    "endpoint": "/api/v1/risk/beta",
    "timestamp": "2026-06-19T14:30:00Z",
    "portfolio_id": "main",
    "data": { ... },
    "metadata": {
        "computation_time_ms": 45.2,
        "data_recency": "2026-06-19T00:00:00Z",
        "cached": true
    }
}
```

### 8.2 WebSocket Stream for Real-Time Updates

**Decision D-19:** WebSocket at `/api/v1/ws/risk/{portfolio_id}`.

Following the Phase 3 pattern (ConnectionManager in `screener/streaming.py`):

```python
class RiskStreamManager:
    """Manage WebSocket connections for real-time risk updates.
    
    Follows the same pattern as Phase 3's ConnectionManager.
    """
    
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._update_intervals: dict[str, float] = defaultdict(lambda: 5.0)
    
    async def broadcast_risk_update(
        self, portfolio_id: str, risk_data: dict
    ) -> None:
        """Send risk metric update to all connected clients."""
        ...
```

**Stream payload types:**

| Message Type | Content | Frequency |
|-------------|---------|-----------|
| `risk_snapshot` | Full set of current risk metrics | On connect, then every ~60s |
| `risk_delta` | Changed metrics only | On any metric change |
| `var_breach_alert` | Any position exceeding VaR limit | Immediate |
| `correlation_shift` | Significant correlation changes | On detection |
| `hedge_adjustment` | Recommended hedge ratio changes | On recomputation |

### 8.3 Risk Report Generation

**Decision D-20:** PDF/HTML with metrics, heatmaps, hedging recommendations.

**Technology choice:**

| Option | Pros | Cons |
|--------|------|------|
| **A: Jinja2 + HTML** (recommended) | Simple, no new deps, can style with CSS, easily extendable | Browser needed for best rendering |
| **B: ReportLab** | Full PDF control, no browser needed | Heavy, complex API, new dependency |
| **C: Matplotlib + PDF backend** | Charts included, familiar library | Weights, not designed for reports |
| **D: markdown + pandoc** | Simple markdown input, multiple output formats | Requires pandoc installation |

**Recommendation: Option A** — Jinja2 HTML template with embedded Matplotlib charts as base64 images. The HTML can be served directly in the browser or converted to PDF via the browser's print function. No new heavy dependencies.

**Report structure:**

```
Risk Report — {portfolio_name} — {date}
========================================
1. Executive Summary
   - Portfolio VaR (95%): $X,XXX
   - CVaR: $X,XXX
   - Beta-weighted exposure: $X,XXX
   - Diversification score: X.X/10
   - Current leverage: X.Xx

2. Position Sizing Recommendations
   - Per-symbol optimal sizes (ATR/Kelly)
   - Risk budget allocation

3. Beta & Hedging
   - Per-symbol beta vs benchmark
   - Hedge ratios
   - Effectiveness metrics (R², TE)
   - Recommended hedging actions

4. Correlation Matrix
   - Heatmap (symbol-level)
   - Sector-level aggregation
   - High-correlation warnings

5. VaR/CVaR Breakdown
   - By method (Historical/Parametric/MC)
   - By confidence level (95%/99%)
   - Component VaR decomposition
   - Marginal VaR per position
   - VaR time series (last 30 days)

6. Kelly Optimization
   - Current vs optimal position sizing
   - Max drawdown constraint validation
   - Recommended sizing parameters

7. Risk Limits & Alerts
   - VaR limit breaches
   - Correlation concentration warnings
   - Position size limit violations
   - Leverage threshold warnings
```

---

## 9. Module Design & Class Structure

### 9.1 Directory Layout

```
backend/app/infrastructure/risk/
├── __init__.py                   # Exports: RiskEngine, run_risk_analysis
├── engine.py                     # RiskEngine — orchestrator
├── beta.py                       # BetaHedger — beta computation, hedge ratios
├── correlation.py                # CorrelationAnalyzer — rolling correlation
├── var.py                        # VaRCalculator — Historical/Parametric/MC VaR/CVaR
├── kelly.py                      # KellyOptimizer — Kelly from backtest, DD validation
├── position_sizing.py            # PositionSizingRefiner — risk-constrained sizing
├── reporting.py                  # RiskReportGenerator — HTML/PDF reports
├── streaming.py                  # RiskStreamManager — WebSocket streaming
└── models.py                     # Risk-specific Pydantic models
```

### 9.2 Class Diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         RiskEngine (engine.py)                             │
│  Orchestrator: coordinate risk computations, manage data sources,          │
│  combine metrics into unified risk assessment.                             │
│                                                                            │
│  Methods:                                                                  │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ analyze_portfolio(portfolio_id) → RiskAssessment                    │    │
│  │ compute_position_size(symbol, params) → PositionSizeResult          │    │
│  │ compute_beta(symbols) → BetaResult                                  │    │
│  │ compute_correlation(symbols) → CorrelationResult                    │    │
│  │ compute_var(symbols) → VaRResult                                    │    │
│  │ compute_kelly(backtest_run_id) → KellyRecommendation                │    │
│  │ generate_report(portfolio_id, format) → Report                      │    │
│  │ start_watching(portfolio_id) → None  (starts streaming)             │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└──────┬──────────┬──────────────┬──────────────┬───────────────────────────┘
       │          │              │              │
       ▼          ▼              ▼              ▼
┌─────────┐ ┌───────────┐ ┌────────────┐ ┌──────────────┐
│Beta     │ │Correlation│ │VaR         │ │Kelly         │
│Hedger   │ │Analyzer   │ │Calculator  │ │Optimizer     │
│         │ │           │ │            │ │              │
│compute_ │ │rolling_   │ │historical  │ │compute_kelly │
│beta()   │ │corr()     │ │_var()      │ │_from_backtest│
│hedge_   │ │sector_    │ │parametric_ │ │validate_max_ │
│ratio()  │ │agg()      │ │var()       │ │dd()          │
│effecti- │ │           │ │monte_carlo │ │recommend()   │
│veness() │ │           │ │_var()      │ │              │
│         │ │           │ │component_  │ │              │
│         │ │           │ │var()       │ │              │
└────┬────┘ └─────┬─────┘ └─────┬──────┘ └──────┬───────┘
     │            │             │               │
     ▼            ▼             ▼               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    Phase 4 Backend Assets                             │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐     │
│  │ Position     │  │ Metrics      │  │ IndicatorCache          │     │
│  │ Sizer        │  │ Computer     │  │ (ATR, indicators)       │     │
│  │ (sizing.py)  │  │ (metrics.py) │  │ (Phase 3)               │     │
│  └──────────────┘  └──────────────┘  └────────────────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐     │
│  │ Trade        │  │ Backtest     │  │ MonteCarlo              │     │
│  │ Ledger       │  │ Engine       │  │ Simulator               │     │
│  │ (ledger.py)  │  │ (engine.py)  │  │ (monte_carlo.py)        │     │
│  └──────────────┘  └──────────────┘  └────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                     ┌────────────────────────────┐
                     │      DuckDB Tables          │
                     │  ohlcv, indicator_values,   │
                     │  backtest_results,          │
                     │  backtest_trades,           │
                     │  symbol_metadata            │
                     └────────────────────────────┘
```

### 9.3 Data Flow

```
┌───────────────────────────────────────────────────────────────────────────┐
│                            RISK ANALYSIS FLOW                             │
│                                                                           │
│  1. Request: Risk analysis for portfolio <portfolio_id>                   │
│     ↓                                                                     │
│  2. RiskEngine loads portfolio data:                                       │
│     a. Positions from portfolio state (symbol, size, entry_price)         │
│     b. OHLCV from DuckDB for all held symbols + benchmarks               │
│     c. Backtest results for Kelly optimization (if available)             │
│     ↓                                                                     │
│  3. Parallel risk computations (asyncio.gather):                          │
│     ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                  │
│     │ Beta     │ │ Correlat │ │ VaR/     │ │ Kelly    │                  │
│     │ Hedging  │ │ ion      │ │ CVaR     │ │ Optim.   │                  │
│     └──────────┘ └──────────┘ └──────────┘ └──────────┘                  │
│         │            │            │            │                          │
│         ▼            ▼            ▼            ▼                          │
│  4. RiskEngine aggregates:                                                 │
│     - Combine all metrics into RiskAssessment                             │
│     - Check risk limit breaches (VaR > limit, concentration > limit)      │
│     - Generate hedge recommendations                                     │
│     ↓                                                                     │
│  5. Output:                                                               │
│     ┌────────────────────────────────────────────────────────────────┐    │
│     │  a. RiskAssessment (Pydantic model) → API JSON response        │    │
│     │  b. WebSocket broadcast (if streaming active)                  │    │
│     │  c. Risk report (HTML/PDF)                                     │    │
│     │  d. Store in DuckDB risk_* tables                               │    │
│     └────────────────────────────────────────────────────────────────┘    │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 10. DuckDB Schema for Risk Results

### Risk Metrics Cache Tables

```sql
-- Per-symbol beta history (rolling 60-day)
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

-- Correlation matrix snapshots (stored as JSON for variable-width matrix)
CREATE TABLE IF NOT EXISTS risk_correlation_snapshots (
    timestamp TIMESTAMPTZ NOT NULL,
    window_days INTEGER NOT NULL,
    symbols_json VARCHAR NOT NULL,        -- Ordered JSON array of symbol names
    matrix_json VARCHAR NOT NULL,         -- N×N JSON array
    sector_matrix_json VARCHAR,           -- Sector-level aggregation
    symbol_count INTEGER NOT NULL,
    computed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (timestamp, window_days)
);

-- VaR history per portfolio
CREATE TABLE IF NOT EXISTS risk_var_history (
    portfolio_id VARCHAR NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    method VARCHAR NOT NULL,              -- 'historical', 'parametric', 'monte_carlo'
    confidence DOUBLE NOT NULL,
    horizon_days INTEGER DEFAULT 1,
    var DOUBLE NOT NULL,
    cvar DOUBLE,
    component_var_json VARCHAR,           -- Per-symbol component VaR
    marginal_var_json VARCHAR,            -- Per-symbol marginal VaR
    computed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (portfolio_id, timestamp, method, confidence, horizon_days)
);

-- Kelly optimization results
CREATE TABLE IF NOT EXISTS risk_kelly_results (
    backtest_run_id VARCHAR NOT NULL REFERENCES backtest_results(run_id),
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

-- Hedge recommendations
CREATE TABLE IF NOT EXISTS risk_hedge_recommendations (
    portfolio_id VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    benchmark VARCHAR NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    beta DOUBLE,
    hedge_ratio DOUBLE,
    hedge_value DOUBLE,
    hedge_instrument VARCHAR,              -- e.g., 'SH', 'SPY_put', 'ES_future'
    recommendation VARCHAR,               -- 'required', 'optional', 'none'
    effectiveness_r2 DOUBLE,
    tracking_error DOUBLE,
    computed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (portfolio_id, symbol, benchmark, timestamp)
);
```

### Schema Design Decisions

| Decision | Rationale |
|----------|-----------|
| Risk tables use `TIMESTAMPTZ` timestamps | Consistent with existing `ohlcv` and `backtest_results` tables |
| Storing `matrix_json` as JSON for correlation | Correlation matrix size varies with N symbols. JSON is more flexible than a fixed N×N schema for variable-size matrices. For fixed portfolios, a columnar approach (symbol_i, symbol_j, correlation) could be used instead — **OpenCode discretion (D-24)** |
| `component_var_json` stored as JSON | Same logic — variable number of positions |
| Risk tables have `computed_at` | Tracking data freshness for cache invalidation |
| Separate tables per risk metric | Each metric has different update frequency and query patterns. Beta is updated daily, VaR real-time, Kelly only on new backtest runs. |

---

## 11. Configuration & Settings

### AppSettings Extension

Add `RiskSettings` to `backend/app/core/config.py`:

```python
class RiskSettings(BaseSettings):
    """Risk management engine settings."""
    model_config = SettingsConfigDict(env_prefix="CONFLU_RISK_")

    default_risk_per_trade: float = Field(
        default=0.01, ge=0.001, le=0.1,
        description="Default risk per trade as fraction of equity (1%)",
    )
    default_atr_multiplier: float = Field(
        default=2.0, ge=1.0, le=5.0,
        description="Default ATR multiplier for position sizing",
    )
    beta_window_days: int = Field(
        default=60, ge=20, le=252,
        description="Rolling window for beta computation",
    )
    beta_benchmark_map: dict[str, str] = Field(
        default={
            "equities": "SPY",
            "crypto": "BTCUSDT",
            "forex": "EURUSD",
            "commodities": "GC1!",
            "indices": "SPX",
        },
        description="Benchmark symbol per asset class for beta calculation",
    )
    correlation_window_days: int = Field(
        default=30, ge=10, le=252,
        description="Rolling window for correlation matrix",
    )
    var_confidence_levels: list[float] = Field(
        default=[0.95, 0.99],
        description="Confidence levels for VaR/CVaR computation",
    )
    var_horizon_days: list[int] = Field(
        default=[1, 10],
        description="Time horizons for VaR computation in days",
    )
    var_methods: list[str] = Field(
        default=["historical", "parametric", "monte_carlo"],
        description="Active VaR computation methods",
    )
    var_monte_carlo_paths: int = Field(
        default=10000, ge=1000, le=100000,
        description="Number of paths for Monte Carlo VaR",
    )
    default_kelly_fraction: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="Default Kelly fraction (0.5 = half-Kelly)",
    )
    max_dd_target: float = Field(
        default=0.25, ge=0.1, le=0.5,
        description="Maximum acceptable drawdown for Kelly validation",
    )
    risk_ws_path: str = Field(
        default="/api/v1/ws/risk/{portfolio_id}",
        description="WebSocket endpoint template for risk streaming",
    )
    report_max_symbols: int = Field(
        default=50,
        description="Maximum symbols to include in risk report",
    )
    cache_risk_results: bool = Field(
        default=True,
        description="Cache risk computation results in DuckDB",
    )

# Add to AppSettings:
class AppSettings(BaseSettings):
    ...
    risk: RiskSettings = RiskSettings()
```

### config.yaml Extension

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
```

---

## 12. Domain Model Extensions Needed

### RiskParams (existing — needs extension)

```python
# CURRENT in domain/models.py:
class RiskParams(BaseModel):
    risk_per_trade: float = Field(default=0.01, ge=0.001, le=0.1)
    max_position_size: float = Field(default=0.25, ge=0.01, le=1.0)
    atr_period: int = Field(default=14, ge=2)
    beta_benchmark: str = Field(default="SPY")
    kelly_fraction: float = Field(default=0.5, ge=0.0, le=1.0)
```

**Gaps vs Phase 5 requirements:**

| Missing Field | Type | Default | Purpose |
|-------------|------|---------|---------|
| `var_confidence` | float | 0.95 | VaR confidence level |
| `var_horizon_days` | int | 1 | VaR time horizon |
| `max_var_pct` | float | 0.05 | Max VaR as % of portfolio (5%) |
| `max_leverage` | float | 1.0 | Max leverage ratio (1.0 = no leverage) |
| `max_correlation` | float | 0.85 | Max allowed pairwise correlation |
| `hedge_min_effectiveness` | float | 0.5 | Min R² for hedge recommendation |
| `var_method` | str | "historical" | Default VaR method |

**Recommendation:** Add these fields to the existing `RiskParams` model. This is a non-breaking change (all new fields have defaults).

### New Risk-Specific Models

These go in `backend/app/infrastructure/risk/models.py`:

```python
class BetaResult(BaseModel):
    """Beta computation result for a symbol."""
    model_config = ConfigDict(frozen=True)
    
    symbol: str
    benchmark: str
    beta: float | None = None
    alpha: float | None = None
    r_squared: float | None = None
    std_err: float | None = None
    p_value: float | None = None
    tracking_error: float | None = None
    window_days: int = 60
    n_observations: int = 0
    computed_at: datetime | None = None


class PortfolioBetaResult(BaseModel):
    """Aggregated beta results for a portfolio."""
    model_config = ConfigDict(frozen=True)
    
    portfolio_id: str
    benchmark: str
    weighted_beta: float | None = None  # Market-weighted portfolio beta
    symbol_betas: list[BetaResult] = Field(default_factory=list)
    computed_at: datetime | None = None


class CorrelationResult(BaseModel):
    """Correlation matrix result."""
    model_config = ConfigDict(frozen=True)
    
    timestamp: datetime
    window_days: int
    symbols: list[str]
    matrix: list[list[float]]  # N×N matrix
    sector_matrix: list[list[float]] | None = None
    sector_labels: list[str] | None = None
    high_correlation_pairs: list[dict] = Field(default_factory=list)
    diversification_score: float | None = None


class VaRResult(BaseModel):
    """Value at Risk computation result."""
    model_config = ConfigDict(frozen=True)
    
    portfolio_id: str
    method: str  # 'historical', 'parametric', 'monte_carlo'
    confidence: float
    horizon_days: int
    var: float  # Positive = expected loss
    cvar: float | None = None  # Expected Shortfall
    component_var: dict[str, float] | None = None  # Per-symbol
    marginal_var: dict[str, float] | None = None  # Per-symbol
    ci_lower: float | None = None
    ci_upper: float | None = None
    n_simulations: int | None = None
    computed_at: datetime | None = None


class KellyRecommendation(BaseModel):
    """Kelly Criterion recommendation."""
    model_config = ConfigDict(frozen=True)
    
    backtest_run_id: str
    asset_class: str
    win_rate: float | None = None
    avg_win_loss_ratio: float | None = None
    full_kelly: float | None = None
    constrained_kelly: float | None = None
    recommended_kelly: float | None = None
    max_dd_target: float = 0.25
    is_valid: bool = True
    suggested_position_sizing: str = "kelly"
    suggested_params: dict[str, Any] = Field(default_factory=dict)


class HedgeRecommendation(BaseModel):
    """Hedge recommendation for a position."""
    model_config = ConfigDict(frozen=True)
    
    symbol: str
    asset_class: str
    beta: float | None = None
    r_squared: float | None = None
    tracking_error: float | None = None
    hedge_ratio: float | None = None
    hedge_value: float | None = None
    hedge_units: float | None = None
    hedge_instrument: str | None = None
    recommendation: str = "none"  # 'required', 'optional', 'none'
    hedge_cost_annual_pct: float | None = None
    computed_at: datetime | None = None


class RiskAssessment(BaseModel):
    """Complete risk assessment for a portfolio."""
    model_config = ConfigDict(frozen=True)
    
    portfolio_id: str
    timestamp: datetime
    var_95: VaRResult | None = None
    var_99: VaRResult | None = None
    portfolio_beta: PortfolioBetaResult | None = None
    correlation: CorrelationResult | None = None
    kelly: KellyRecommendation | None = None
    hedge_recommendations: list[HedgeRecommendation] = Field(default_factory=list)
    risk_score: float | None = None  # Composite 0-100 risk score
    alerts: list[RiskAlert] = Field(default_factory=list)


class RiskAlert(BaseModel):
    """Risk limit breach alert."""
    model_config = ConfigDict(frozen=True)
    
    severity: Literal["info", "warning", "critical"]
    category: Literal["var", "correlation", "concentration", "leverage", "beta"]
    message: str
    symbol: str | None = None
    current_value: float
    threshold: float
    timestamp: datetime
```

---

## 13. Integration Points with Phases 1-4

### What Phase 5 Consumes from Phase 1

| Phase 1 Asset | Phase 5 Usage | File |
|---------------|--------------|------|
| `get_db()` / `get_db_async()` | Read OHLCV, write risk results | `backend/app/core/database.py` |
| `partition_path()` | Locate OHLCV Parquet files | `backend/app/core/database.py` |
| `@indicator` registry | ATR(14) from Phase 1 for position sizing | `backend/app/infrastructure/indicators.py` |
| `compute_all()` | Batch indicator computation (if needed) | `backend/app/infrastructure/indicators.py` |
| `ComputeSettings` | Default indicator timeframes | `backend/app/core/config.py` |
| `DataSettings` | Asset class definitions, benchmarks | `backend/app/core/config.py` |
| `set_correlation_id()` | Computation-level correlation ID | `backend/app/core/logging.py` |
| `get_logger()` | Structured logging throughout | `backend/app/core/logging.py` |
| `OHLCV`, `RiskParams` | Domain models | `backend/app/domain/models.py` |

### What Phase 5 Consumes from Phase 2

| Phase 2 Asset | Phase 5 Usage | File |
|---------------|--------------|------|
| `ohlcv` DuckDB table | Daily returns for beta, correlation, VaR | DDL in `database.py` |
| `symbol_metadata` table | Asset class → benchmark mapping | DDL in `database.py` |
| Parquet `data/**/*.parquet` | Alternative OHLCV read path | Filesystem |

### What Phase 5 Consumes from Phase 3

| Phase 3 Asset | Phase 5 Usage | File |
|---------------|--------------|------|
| `IndicatorCache.get_series()` | Historical ATR values for position sizing | `screener/cache.py` |
| `IndicatorCache.get_latest()` | Current ATR for real-time sizing | `screener/cache.py` |

### What Phase 5 Consumes from Phase 4

| Phase 4 Asset | Phase 5 Usage | File |
|---------------|--------------|------|
| `PositionSizer` | Base position sizing (ATR/Kelly formulas already work) | `backtest/sizing.py` |
| `MetricsComputer` | MAE/MFE computation for VaR | `backtest/metrics.py` |
| `TradeLedger.build_ledger()` | Trade history for VaR/CVaR | `backtest/ledger.py` |
| `BacktestEngine.run()` → `BacktestRunRecord` | Metrics for Kelly optimization | `backtest/engine.py` |
| `MonteCarloSimulator._block_bootstrap()` | Bootstrap method for MC VaR | `backtest/monte_carlo.py` |
| `BacktestRunRecord.metrics` | Win rate, Sharpe inputs for Kelly | `backtest/models.py` |
| `FoldResult`, `OptimizationResult` | (Future) Kelly optimization across walks | `backtest/models.py` |

### What Phase 5 Provides to Downstream Phases

| Downstream Phase | What It Gets | How |
|-----------------|-------------|-----|
| Phase 6 (API) | `RiskEngine` class for REST/WS endpoints | Import + wiring in `backend/app/api/` |
| Phase 7 (Frontend) | Risk metrics JSON, correlation heatmap, hedge recommendations | JSON over HTTP/WS |
| Phase 8 (Advanced Screener) | Risk-filtered symbol lists, VaR-constrained screening | Shared DuckDB `risk_*` tables |
| Phase 9 (Advanced Backtest) | Kelly-optimal params for backtesting, VaR-aware position limits | `BacktestRunConfig.sizing_params` |
| Future: Real-time trading | Real-time risk metrics, VaR breach alerts | WebSocket stream |

---

## 14. New Dependencies

### New Packages Required

| Package | Version | Purpose | Required? |
|---------|---------|---------|-----------|
| `scipy` | `>=1.11,<2` | `scipy.stats.linregress()` for beta, `scipy.stats.norm.ppf()` for parametric VaR | ✅ **YES** |
| `jinja2` | `>=3.1,<4` | HTML report template rendering | Optional (for reports) |
| `matplotlib` | `>=3.7,<4` | Correlation heatmap, VaR chart in reports | Optional (for reports) |

**Core computation only needs `scipy`** — it's a standard scientific computing package that provides `linregress`, `norm.ppf`, and `mstats.mquantiles`. Reports are optional and can be deferred.

### Implementation Without scipy

If avoiding scipy is preferred:

| Need | Pure NumPy/pandas Alternative |
|------|------------------------------|
| Beta regression | `numpy.linalg.lstsq()` — manual OLS |
| Parametric VaR z-score | `from scipy.stats import norm` → `norm.ppf()` **or** pre-compute z-table |
| Historical VaR quantile | `numpy.percentile()` — already used in Phase 4 MC |

**Recommendation:** Add `scipy` as a dependency. It's a standard package (installed with most scientific Python distributions), battle-tested, and provides `linregress()` which is exactly what's needed. The parametric VaR z-score via `norm.ppf()` is trivial with scipy and tedious without it.

### Updated pyproject.toml

```toml
[project.dependencies]
# ... existing deps ...
scipy = ">=1.11,<2"

[project.optional-dependencies]
report = [
    "jinja2>=3.1,<4",
    "matplotlib>=3.7,<4",
]
test = [
    # ... existing test deps ...
]
```

### No New Infrastructure

- **No new databases** — risk results share the same DuckDB
- **No new message brokers** — WebSocket is direct (same pattern as Phase 3)
- **No new compute services** — all in-process vectorized computation with numpy/scipy

---

## 15. Risks & Mitigations

### High Risk

| Risk | Description | Likelihood | Impact | Mitigation |
|------|-------------|------------|--------|------------|
| **Phase 4 PositionSizer duplication risk** | Phase 5 may duplicate ATR/Kelly logic already in Phase 4's `PositionSizer`. If not careful, we'll have two implementations that drift. | **High** (likely) | **High** | Phase 5 `PositionSizingRefiner` **composes on top of** Phase 4's `PositionSizer`. NOT a rewrite. Document this as an architectural constraint: "Phase 5 does NOT reimplement position sizing." |
| **VaR data source confusion** | VaR can be computed from trade PnL (TradeLedger), daily portfolio returns (BacktestRunRecord), or position-level returns. Different sources give different VaR values. Users may misinterpret. | **High** | **Medium** | Clearly label which data source is used for each VaR computation. Provide both trade-based (per-position) and returns-based (portfolio-level) VaR. Document the differences in API response metadata. |
| **Rolling correlation performance for large universes** | Computing rolling 30-day Pearson correlation for 5000 symbols produces a 5000×5000 matrix = 25M entries per timestamp. Even with pandas vectorization, this is memory-intensive. | Medium | **High** | Use `pairwise=True` with pandas rolling.corr (optimized internal implementation). Cache snapshots with `correlation_window_days` granularity. Consider subsetting: only compute full matrix for actively held positions + top 50 correlated pairs. |
| **Monte Carlo VaR discrepancy vs Phase 4 MC** | Phase 4 MC generates synthetic lognormal returns. Phase 5 MC VaR should bootstrap from empirical returns. If Phase 4 MC is reused directly, VaR may underestimate tail risk. | Medium | **High** | Create separate `monte_carlo_var()` in `var.py` that uses empirical bootstrap (from Phase 4's block_bootstrap utility but applied to returns). Do NOT reuse Phase 4's synthetic return generation. |

### Medium Risk

| Risk | Description | Likelihood | Impact | Mitigation |
|------|-------------|------------|--------|------------|
| **Kelly circular dependency persists** | Phase 5's Kelly optimization still depends on backtest results. If no backtest has been run, Kelly defaults must be used. | **Certain** | Medium | Provide sensible defaults (half-Kelly at 0.5, risk_per_trade at 1%). Clearly document when Kelly is "from backtest" vs "default". The `KellyRecommendation.is_valid` field flags this. |
| **Beta hedge cost estimation** | Hedge cost (carry, fees, roll) requires external data (futures curves, ETF expense ratios). Phase 5 can estimate but not compute exact costs. | High | Medium | Use approximate costs: 0.5% annual for inverse ETFs, variable for futures. Document as "estimated" in recommendations. Defer exact cost computation to Phase 9. |
| **Sector mapping incompleteness** | Phase 3 may not yet provide sector metadata for all symbols. Assets without sector → "Unclassified". Correlation aggregation may be less useful. | Medium | Medium | Default to asset_class grouping if sector metadata is missing. The `aggregate_correlation_by_group()` function accepts any group mapping. |
| **"Inverse ETF" availability for hedging** | Hedge recommendations suggesting "SH" (inverse SPY ETF) assume the instrument is available and liquid. For crypto, no inverse ETF exists — must use futures. | Medium | Medium | Make `hedge_instrument` recommendations configurable per asset class in `RiskSettings`. Crypto defaults to perpetual futures. |
| **Component VaR interpretation** | Component VaR can produce negative values (diversification benefit). Non-quant users may misinterpret this. | Medium | Low | In API responses, always include explanatory metadata. Document interpretation in API docs. |

### Low Risk

| Risk | Description | Likelihood | Impact | Mitigation |
|------|-------------|------------|--------|------------|
| **scipy availability** | scipy is a large dependency (~50MB). Some deployment environments may not have it. | Low | Low | Pure numpy/pandas fallbacks for all critical paths. scipy is only needed for `linregress` and `norm.ppf` — both can be approximated with numpy. |
| **Correlation look-ahead bias** | Rolling correlation at timestamp T uses data up to T — not forward-looking. This is correct for risk analysis. | Low (it's correct) | None | Ensure the rolling window uses `.shift()` to avoid same-bar correlation. Standard pandas `.rolling()` is backward-looking, so this is naturally correct. |
| **DuckDB write contention for risk tables** | Multiple risk computations writing to `risk_*` tables could conflict. | Low | Low | Risk tables are INSERT-only (append history) or REPLACE. Use `INSERT OR REPLACE` for snapshot-based tables. No concurrent writes expected in single-process architecture. |

---

## 16. Open Questions for Planning

These need resolution before writing PLAN.md:

### Q1: PositionSizer — Reuse from Phase 4 or Wrap in Phase 5?

The `PositionSizer` in Phase 4 already implements ATR and Kelly formulas exactly as specified by D-01 and D-15. Phase 5 needs to add risk-aware constraints (correlation limits, VaR caps).

Options:
- **A: Import and compose** (recommended) — Phase 5 `PositionSizingRefiner` imports `PositionSizer` and adds overlays. No changes to Phase 4 code.
- **B: Copy into risk module** — Risk module has its own PositionSizer copy. Avoids cross-phase dependency. Risk: code drift.
- **C: Refactor core logic into shared lib** — Move ATR/Kelly formulas into a shared utility. Both Phase 4 and Phase 5 import from there. Riskiest (touches stable Phase 4 code).

**Recommendation: Option A** — Compose on top. Clean separation, no risk of breaking Phase 4.

### Q2: VaR Data Source — Trade PnL or Portfolio Returns?

VaR can be computed from:
1. Per-trade PnL (from Phase 4 TradeLedger) — good for per-position risk
2. Daily portfolio returns (from Phase 4 BacktestRunRecord equity curve) — good for portfolio-level risk
3. Raw position-level daily returns (computed from holdings × OHLCV) — most accurate but requires portfolio state tracking

**Recommendation:** Implement **all three**, with clear labeling. The API lets the user choose:
- `var_source: "portfolio_returns"` (default, most useful)
- `var_source: "trade_pnl"` (per-position breakdown)
- `var_source: "position_returns"` (for live portfolios with position tracking)

### Q3: Correlation Cache Strategy?

D-25 (OpenCode's discretion): Cache rolling calculations in DuckDB.

Options:
- **A: Cache only latest matrix** — Store most recent correlation snapshot. Recompute on data update.
- **B: Cache full history** — Store timestamped snapshots. Enables correlation time-series queries but uses more storage.
- **C: No cache** — Recompute on every request. Fast with pandas vectorization (~1-2s for 5000 symbols).

**Recommendation: Option B** — Cache full history at daily granularity. Storage is cheap (JSON for 5000 symbols ≈ 50MB per snapshot). Enables historical correlation analysis. Use `INSERT OR REPLACE` for idempotent updates.

### Q4: Report Format — HTML or PDF?

D-20 says "PDF/HTML" reports. What should Phase 5 generate?

Options:
- **A: HTML only** — Jinja2 template, serve in browser. Users can `Ctrl+P` → Save as PDF.
- **B: PDF directly** — ReportLab. More complex but self-contained.
- **C: Markdown source** — Generate markdown, convert with pandoc. Flexible but requires pandoc.

**Recommendation: Option A** — HTML with Jinja2. Users can print to PDF. Charts via base64-embedded Matplotlib PNGs. No new heavy dependencies (Jinja2 is already commonly installed, Matplotlib only for charts). Defer native PDF generation to Phase 9.

### Q5: WebSocket Risk Streaming — When to Activate?

D-19 specifies WebSocket for real-time risk updates. Should this be:
- **Always on** — RiskStreamManager starts with the API server, streams periodic updates
- **On demand** — Only streams when a client connects to `/api/v1/ws/risk/{portfolio_id}`
- **Event-driven** — Only broadcasts when risk metrics change significantly

**Recommendation:** **On demand** (follows Phase 3 pattern). The RiskStreamManager only computes and broadcasts when at least one client is connected. When no clients, risk metrics are computed on-demand via REST.

### Q6: Correlation Matrix Size Limits?

For 5000 symbols, the correlation matrix is 5000×5000 = 25M entries. Should we:
- **A: Full matrix always** — Compute and cache the full N×N matrix. Fastest access, highest storage.
- **B: Top-K correlations only** — Only compute and store the top 1000 cross-correlations per symbol. ~5M entries instead of 25M.
- **C: Sector-level only** — Only aggregate to sector/asset-class level. Minimal storage but loses per-pair detail.

**Recommendation: Option A** — Full matrix. 25M float64 entries ≈ 200MB in memory, ~50MB compressed as JSON. DuckDB handles this easily. The vectorized pandas `rolling().corr(pairwise=True)` computes it efficiently. Add `max_correlation_symbols: int` config option to limit universe size if needed.

### Q7: Beta — Support Multiple Benchmarks Per Asset Class?

D-04 specifies one benchmark per asset class (SPY for equities, BTC for crypto). Should we support:
- **A: Single benchmark per class** — Simple, matches D-04.
- **B: Multiple benchmarks** — E.g., SPY + QQQ for US equities, allowing user to choose.
- **C: Custom benchmarks** — User can specify any symbol as benchmark.

**Recommendation: Option B** — Default from config (`beta_benchmark_map`), but API allows overriding. E.g., `GET /api/v1/risk/beta/AAPL?benchmark=QQQ&window=60`. This makes the API more flexible without adding complexity to the defaults.

### Q8: Risk Params — Extend Existing Model or Create New One?

The existing `RiskParams` in `domain/models.py` has basic fields. Phase 5 needs more (see §12).

Options:
- **A: Extend existing `RiskParams`** — Add new fields with defaults. Non-breaking.
- **B: Create `RiskConfig` in `risk/models.py`** — Separate model for the risk engine. `RiskParams` stays for cross-phase use.
- **C: Hybrid** — `RiskParams` gets extension fields. `RiskConfig` in `risk/models.py` has engine-specific settings.

**Recommendation: Option A** — Extend existing `RiskParams`. The new fields (var_confidence, max_var_pct, etc.) are generic risk parameters that belong in the domain layer. The engine-specific settings go in `RiskSettings` (config) and `risk/models.py`.

### Q9: Backtest Dependency — Required or Optional for Kelly?

Kelly optimization requires Phase 4 backtest results. What if they don't exist?

Options:
- **A: Required** — Kelly endpoint returns error if no backtest results. User must run backtest first.
- **B: Optional with defaults** — If no backtest, use configured defaults (half-Kelly, 1% risk per trade).
- **C: Kelly endpoint triggers backtest** — If no backtest results, runs a default backtest to compute Kelly inputs.

**Recommendation: Option B** — Graceful fallback to defaults with `is_valid=False` flag. The user is informed that Kelly recommendations are not based on backtest results. Option C would couple Phase 5 to Phase 4's execution latency.

### Q10: Testing Strategy?

**Recommended test files:**

| Test File | What It Tests | Type |
|-----------|--------------|------|
| `test_risk_engine.py` | Full risk analysis pipeline: coordinate all sub-modules | Integration |
| `test_risk_beta.py` | Beta computation: rolling regression, benchmark mapping, vectorized vs loop | Unit + property |
| `test_risk_correlation.py` | Rolling correlation, sector aggregation, heatmap format | Unit + property |
| `test_risk_var.py` | Historical/Parametric/MC VaR, CVaR, time scaling, component VaR | Unit + property |
| `test_risk_kelly.py` | Kelly from backtest, max DD validation, recommendation generation | Unit |
| `test_risk_position_sizing.py` | Risk-constrained sizing overlays, correlation caps, VaR-based limits | Unit |
| `test_risk_models.py` | Config validation, API response shape, serialization | Unit |
| `test_risk_streaming.py` | WebSocket connection, message broadcast, reconnection | Integration |
| `test_risk_reports.py` | HTML template rendering, data population | Integration |

**Property-based tests (Hypothesis):**
- VaR bounds: `0 ≤ VaR_95 ≤ VaR_99` (higher confidence → larger VaR)
- CVaR bounds: `VaR ≤ CVaR` (Expected Shortfall ≥ VaR)
- Beta decomposition: `portfolio_beta = Σ(weight_i × beta_i)`
- Correlation symmetry: `corr(i,j) = corr(j,i)`
- Component VaR decomposition: `Σ(component_VaR_i) = portfolio_VaR`
- Kelly bounds: `0 ≤ constrained_kelly ≤ full_kelly`

---

## Summary of Technology Choices

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Position sizing | Compose on Phase 4 `PositionSizer` + risk overlays | NOT a rewrite — adds constraints on top |
| Beta regression | `scipy.stats.linregress()` | Clean API, returns R²/std_err/p_value |
| Benchmark data | DuckDB `ohlcv` table (same symbols) | SPY, BTCUSDT already ingested |
| Correlation | `pandas.DataFrame.rolling().corr()` | Fully vectorized, handles N×N |
| Correlation storage | DuckDB JSON snapshots | Variable-size N×N matrix fits JSON |
| VaR (Historical) | `numpy.percentile()` | Already used in Phase 4 MC |
| VaR (Parametric) | `scipy.stats.norm.ppf()` | Standard approach for Gaussian VaR |
| VaR (Monte Carlo) | Empirical bootstrap (from Phase 4 block_bootstrap) | Captures real-market skew/kurtosis |
| VaR decomposition | Component VaR + Marginal VaR (numpy) | Standard risk decomposition |
| Kelly optimization | Post-backtest consumer (Phase 5 owns this) | Resolves Phase 4 circular dependency |
| Reports | Jinja2 HTML + Matplotlib charts | No heavy deps, easy to extend |
| WebSocket | On-demand streaming (same pattern as Phase 3) | Consistent with existing architecture |
| Risk config | New `RiskSettings` in `AppSettings` | Follows established pattern |
| Risk models | `risk/models.py` + extend `RiskParams` | Clean separation of concerns |
| New dependencies | `scipy` only (core), Jinja2/Matplotlib (optional) | Minimal supply chain risk |
| Caching | DuckDB `risk_*` tables with `cache_risk_results` config | Consistent with Phase 3/4 patterns |
| Testing | pytest + hypothesis + synthetic data | Follows established project patterns |

---

*This research feeds into `05-PLAN.md`. All documentation references verified against current (June 2026) library APIs.*

---

## Post-Research Actions

Based on the findings above, the following actions are needed before or during Phase 5 planning:

1. **Domain model update:** Extend `RiskParams` in `domain/models.py` with VaR/horizon/leverage fields.
2. **Config update:** Add `RiskSettings` to `backend/app/core/config.py` and `config.yaml`.
3. **DuckDB schema:** Add DDL for `risk_beta_history`, `risk_correlation_snapshots`, `risk_var_history`, `risk_kelly_results`, `risk_hedge_recommendations` tables to `database.py`.
4. **Module creation:** Create `backend/app/infrastructure/risk/` package with all submodules.
5. **scipy dependency:** Add `scipy` to `pyproject.toml`.
6. **Phase 4 PositionSizer audit:** Confirm that `_atr_size()` and `_kelly_size()` meet all Phase 5 requirements (short sizing support, max position cap).
7. **Benchmark symbol verification:** Ensure all configured benchmark symbols (SPY, BTCUSDT, EURUSD, GC1!, SPX) are in the default asset lists and will be ingested by Phase 2.
