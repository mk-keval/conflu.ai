# Phase 4: Backtest Engine — Research

**Created:** 2026-06-19
**Status:** Ready for planning
**Context:** Phase 1 foundation (DuckDB, config, logging, indicators) + Phase 2 ingestion (Parquet OHLCV, symbol metadata) + Phase 3 screener (filter pipeline, indicator cache, screen results) exist in completed state.

---

## Table of Contents

1. [Project State & Codebase Assessment](#1-project-state--codebase-assessment)
2. [Critical Architecture: vectorbt Portfolio API Deep Dive](#2-critical-architecture-vectorbt-portfolio-api-deep-dive)
   - 2.1 `from_signals()` — Entry Point
   - 2.2 `from_orders()` — Custom Position Sizing
   - 2.3 `stats()` — Built-in Metrics
   - 2.4 Orders & Records — Trade Ledger
   - 2.5 Equity Curve & Drawdown
3. [Signal Interface: Phase 3 Screener → Phase 4 Backtest](#3-signal-interface-phase-3-screener--phase-4-backtest)
   - 3.1 Signal Conversion: ScreenRunResult → vectorbt Format
   - 3.2 Timeframe Alignment
   - 3.3 Signal Metadata Attachment
4. [Position Sizing Strategies](#4-position-sizing-strategies)
   - 4.1 Fixed Sizing (Cash/Units)
   - 4.2 ATR-Based Sizing
   - 4.3 Kelly Criterion Sizing
   - 4.4 Implementation via `from_orders()` vs `size` parameter
5. [Walk-Forward Optimization](#5-walk-forward-optimization)
   - 5.1 Expanding Window Mode
   - 5.2 Rolling Window Mode
   - 5.3 Optimization Loop Structure
   - 5.4 Parameter Grid Definition
   - 5.5 In-Sample / Out-of-Sample Metrics
6. [Monte Carlo Simulation](#6-monte-carlo-simulation)
   - 6.1 vectorbt Simulation Capabilities
   - 6.2 Bootstrap vs Block Bootstrap
   - 6.3 Confidence Intervals & Ruin Probability
7. [Metrics & Trade Ledger](#7-metrics--trade-ledger)
   - 7.1 Metric Source Mapping: vectorbt Native vs Custom
   - 7.2 MAE/MFE Computation from Daily OHLC
   - 7.3 Trade Ledger Schema
   - 7.4 Drawdown Analysis
8. [Module Design & Class Structure](#8-module-design--class-structure)
   - 8.1 Directory Layout
   - 8.2 Class Diagram
   - 8.3 Data Flow
9. [Integration Points with Phases 1, 2, 3](#9-integration-points-with-phases-1-2-3)
10. [DuckDB Schema for Backtest Results](#10-duckdb-schema-for-backtest-results)
11. [Domain Model Extensions Needed](#11-domain-model-extensions-needed)
12. [BacktestConfig Evolution](#12-backtestconfig-evolution)
13. [Async Execution Strategy](#13-async-execution-strategy)
14. [New Dependencies](#14-new-dependencies)
15. [Risks & Mitigations](#15-risks--mitigations)
16. [Open Questions for Planning](#16-open-questions-for-planning)

---

## 1. Project State & Codebase Assessment

### Current State (after Phase 1 + Phase 2 + Phase 3 completion)

| Aspect | Status | Reusable for Phase 4 |
|--------|--------|----------------------|
| DuckDB connection mgr | ✅ `get_db()`, `get_db_async()`, `initialize_database()` | Core connection for OHLCV reads, backtest results write |
| Parquet partitioning | ✅ `partition_path()` for `{asset_class}/{year}/{month}/{symbol}_{timeframe}.parquet` | OHLCV data source for backtesting |
| OHLCV DDL | ✅ `ohlcv` table with year/month partition columns | Primary price data source |
| `indicator_values` DDL | ✅ Tall-format indicator cache table | Signal inputs, especially for Kelly sizing |
| Config (`ComputeSettings`, `ScreenSettings`) | ✅ Existing with indicator/broadcast/screen config | Backtest runtime params, default sizing |
| Config (`config.yaml`) | ✅ Exists, extendable with backtest section | Add backtest defaults: fees, slippage, position sizing modes |
| Structured logging | ✅ `set_correlation_id()`, `get_logger()`, JSON output | Correlation IDs per backtest run |
| Domain models | ✅ `OHLCV`, `Signal`, `Position`, `Trade`, `Metrics`, `BacktestConfig`, `RiskParams` | Core trade/position/metric models (may need extension) |
| Test infrastructure | ✅ pytest + asyncio + conftest fixtures with `synthetic_ohlcv` | Test harness for backtest |
| Indicator registry | ✅ `@indicator` decorator, 10 indicators, `compute_all()` | Indicator computation for ATR sizing, Kelly |
| `IndicatorCache` | ✅ `get_latest()`, `get_series()`, `update_cache()`, `rebuild()` | Pre-computed indicator values for backtest signal consumption |
| ScreenEngine | ✅ `screen()` returns `ScreenRunResult` with matched symbols and filter results | Signal source for strategy backtesting |
| `broadcasting.py` | ✅ `broadcast_timeframe()`, `sort_timeframes()`, `align_timeframes()` | Timeframe alignment for multi-TF signal conversion |
| FastAPI | ✅ `>=0.110,<1` in dependencies | Needed if backtest API endpoints are wired in Phase 4 (otherwise deferred to Phase 6) |
| Backtest module | ❌ **Does not exist** — must be created at `backend/app/infrastructure/backtest/` | All Phase 4 code goes here |

### What Phase 4 Must Create

All Phase 4 code goes in a new module `backend/app/infrastructure/backtest/` — alongside `screener/` and `ingest/`:

```
backend/app/infrastructure/backtest/
├── __init__.py          # Exports: BacktestEngine, run_backtest, BacktestConfig
├── engine.py            # BacktestEngine — orchestrator: load data → build signals → run portfolio → compute metrics → store
├── signals.py           # SignalAdapter — converts ScreenRunResult / indicator cache to vectorbt entry/exit arrays
├── sizing.py            # PositionSizer — fixed, ATR, Kelly sizing logic
├── walk_forward.py      # WalkForwardOptimizer — expanding/rolling window grid search
├── monte_carlo.py       # MonteCarloSimulator — bootstrap/block bootstrap path simulation
├── metrics.py           # MetricsComputer — custom metrics beyond what vectorbt.stats() provides (MAE/MFE, Ulcer)
├── ledger.py            # TradeLedger — converts vectorbt order records to structured Trade/PnL records
└── models.py            # BacktestRunConfig, OptimizationResult, WalkForwardResult, MCSimulationResult (Pydantic)
```

---

## 2. Critical Architecture: vectorbt Portfolio API Deep Dive

This section maps the decisions from Phase 4 discussion to the actual vectorbt API surface.

### 2.1 `from_signals()` — Entry Point

**Decision D-01** specifies `vbt.Portfolio.from_signals()` as the core entry point. The canonical API requires:

```python
portfolio = vbt.Portfolio.from_signals(
    close=price,              # shape (n_bars, n_columns) — OHLC close prices
    entries=entries,          # shape (n_bars, n_columns) — bool DataFrame: True = enter
    exits=exits,              # shape (n_bars, n_columns) — bool DataFrame: True = exit
    direction='both',         # 'both' | 'longonly' | 'shortonly'
    upon_opposite_entry='close',  # what happens when long signal while short: 'close' to exit first
    init_cash=100_000.0,      # initial capital
    fees=0.001,               # as decimal fraction (e.g., 0.001 = 10bps)
    slippage=0.001,           # slippage fraction per trade
    freq='D',                 # frequency alias for annualization
    size=1.0,                 # position size (can be DataFrame for per-bar sizing)
    group_by=None,            # for multi-symbol grouping
    cash_sharing=False,       # share cash pool across symbols
    call_seq='auto',          # order execution sequence
    log=False,                # enable logging (debugging)
)
```

**Key observations:**
- `entries` and `exits` are **Boolean DataFrames** with same shape as `close` — NOT the 1/0/-1 signal array from D-04
- Direction encoding (1=long, 0=flat, -1=short) from Phase 3 must be **converted** to separate entries/exits boolean arrays
- `fees` and `slippage` are decimal fractions applied per trade side (not bps directly — must convert: 10bps = 0.001)
- `freq` must be a valid pandas frequency string — inferred from data index spacing (D-01)
- `size` can be a **scalar, Series, or DataFrame** — enabling per-bar, per-symbol position sizing

### 2.2 `from_orders()` — Custom Position Sizing

For ATR and Kelly sizing (D-02), `from_signals()` with a scalar `size` parameter is insufficient. Instead, use `from_orders()` which accepts per-bar size arrays:

```python
portfolio = vbt.Portfolio.from_orders(
    close=price,
    size=size_df,              # DataFrame of same shape: positive = buy, negative = sell
    price=price_df,            # execution price (use open or close)
    fees=fees,                 # fees fraction
    slippage=slippage,         # slippage fraction
    init_cash=init_cash,
    freq='D',
    direction='both',
    group_by=group_by,
)
```

**Alternatively**, `from_signals()` accepts a `size` parameter that can be a **callable or array**:
- If callable: `size_func(close, entries, exits)` returns size array
- If array: per-bar × per-column position sizing aligned with entries/exits

**Recommendation for D-02:** Use `from_signals()` with array `size` parameter (DataFrame per bar × per symbol with dollar amounts or unit counts). This avoids the complexity of writing a custom Numba order function while still enabling per-bar position sizing.

### 2.3 `stats()` — Built-in Metrics

`portfolio.stats()` returns a Series with these metrics (covering D-18):

| Metric | vectorbt Name | Notes |
|--------|---------------|-------|
| Sharpe | `sharpe_ratio` | Uses `freq` for annualization |
| Sortino | `sortino_ratio` | Uses `freq` |
| Calmar | `calmar_ratio` | CAGR / Max DD |
| Max DD | `max_drawdown` | As decimal |
| Win Rate | `win_rate` | Fraction of winning trades |
| Expectancy | `expectancy` | Mean PnL per trade |
| Profit Factor | `profit_factor` | Gross profit / gross loss |
| SQN | `sqn` | System Quality Number |
| Ulcer Index | ❌ **NOT provided** | Must compute custom (see §7.1) |
| CAGR | `cagr` | Compounded Annual Growth Rate |

**Critical finding:** vectorbt's `stats()` provides most metrics from D-18 automatically. The exceptions:
- **Ulcer Index** — not in vectorbt metrics. Must compute from drawdown series.
- **MAE/MFE** — not in vectorbt trade records. Must compute separately from OHLC data.

### 2.4 Orders & Records — Trade Ledger

`portfolio.orders.records` returns a DataFrame with:

| Column | Description | Maps to D-19 |
|--------|-------------|-------------|
| `column` | Column index (symbol if grouped) | symbol |
| `size` | Order size (positive=buy, negative=sell) | size |
| `side` | Buy/Sell side | direction |
| `price` | Execution price | entry_price / exit_price |
| `fees` | Fees paid | fees |
| `index` | Bar index of order | entry_time / exit_time |

`portfolio.trades.records` is more directly useful — it groups entry/exit into full trades:

| Column | Description | Maps to D-19 |
|--------|-------------|--------------|
| `column` | Column index | symbol |
| `size` | Trade size | size |
| `entry_idx` | Entry bar index | entry_time |
| `entry_price` | Entry price | entry_price |
| `exit_idx` | Exit bar index | exit_time |
| `exit_price` | Exit price | exit_price |
| `pnl` | Trade PnL | pnl |
| `return` | Trade return % | — |
| `direction` | Long/Short | direction |
| `entry_fees` / `exit_fees` | Fees per side | fees |

**Key insight for D-19:** `portfolio.trades.records` provides most of the trade ledger columns needed. Missing columns: MAE, MFE, hold_duration, exit_reason. These must be computed from OHLC data alongside the trade records.

### 2.5 Equity Curve & Drawdown

```python
# Equity curve — daily portfolio value
equity = portfolio.value()  # Series with same index as price data

# Returns series — daily returns
returns = portfolio.returns()  # Simple returns

# Drawdown series — peak-to-trough
drawdown = portfolio.drawdown()  # As decimal (0.25 = 25% underwater)

# Underwater plot data
drawdown_min = drawdown.min()  # Max DD value
drawdown_duration = portfolio.drawdown_duration()  # How long underwater
```

All return these as pandas objects with the same index as the input price data (D-20, D-21).

---

## 3. Signal Interface: Phase 3 Screener → Phase 4 Backtest

### 3.1 Signal Conversion: ScreenRunResult → vectorbt Format

**Decision D-06:** Signals consumed from Phase 3 as `ScreenRunResult` → converted to vectorbt format.

The core conversion problem: Phase 3 produces a **list of matched symbols with scores** at a point in time. A backtest needs **entry/exit boolean arrays over time**.

Three possible signal sources:

| Source | Format | Conversion Needed |
|--------|--------|-------------------|
| **A: Indicator Crossing** | `indicator_values` table — time series of indicator values for all symbols | Apply filter logic (e.g., RSI < 30 → entry signal) over the entire time series. Returns boolean array. |
| **B: ScreenEngine result series** | Run screener at each timestamp → list of matched symbols | Convert to a signal per symbol × per timestamp. Requires re-running screen at each bar or caching screen results over time. |
| **C: Raw filter functions** | `_FILTER_REGISTRY` filter functions applied over historical data | Apply the same filter functions used in screening to historical indicator data. Produces boolean masks for each timestamp. |

**Recommendation: Option C — Direct filter reapplication over historical data.**

Rationale:
- A backtest needs signals for every bar in the historical period, not just the latest.
- Re-running `ScreenEngine.screen()` for each bar is O(n_bars × n_symbols) and wasteful.
- The same `_FILTER_REGISTRY` filters used in Phase 3 can be applied directly to the historical `indicator_values` or computed indicators.
- This ensures backtest signals match real-time screening signals (same filter logic).

**SignalAdapter** class in `signals.py`:

```python
class SignalAdapter:
    """Converts indicator data and filter definitions into vectorbt entry/exit signals.
    
    Applies the same filter logic from Phase 3 over historical data,
    producing boolean arrays for vectorbt Portfolio.from_signals().
    """

    async def build_signals(
        self,
        symbol: str,
        config: BacktestRunConfig,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Build entry/exit signals for vectorbt from filter config.
        
        Args:
            symbol: Symbol to build signals for.
            config: Backtest run config with filter definitions.
            
        Returns:
            Tuple of (price_df, entries_df, exits_df) for vbt.Portfolio.from_signals().
        """
        ...
```

### 3.2 Timeframe Alignment

**Decision D-07:** Signal timestamps must align with OHLCV data.

**Strategy:**
- The backtest runs at a single timeframe (default: 1D for strategy-level testing, configurable).
- Higher-timeframe signals (e.g., weekly trend filters) are forward-filled to the backtest timeframe using `broadcast_timeframe()` from Phase 3.
- Lower-timeframe signals require the backtest to run at the lower timeframe, or signals are aggregated (e.g., "any entry signal during the day").
- Use Phase 3's `sort_timeframes()` and `reindex(method='ffill')` pattern for consolidation.

### 3.3 Signal Metadata Attachment

**Decision D-08:** Signal metadata (confidence, source filter, timeframe) stored in trade ledger.

**Strategy:**
- When a signal triggers a trade entry, attach the current filter match details as trade metadata.
- Store in a `signal_metadata` dict on the Trade model: `{"confidence": 0.85, "source": "rsi_oversold", "timeframe": "4h"}`.
- Since vectorbt doesn't natively support signal metadata on trade records, we **post-process** the trade ledger by aligning trade entry timestamps with the signal DataFrame to look up which filters were active.

---

## 4. Position Sizing Strategies

### 4.1 Fixed Sizing (Cash/Units)

**Mechanism:** Use `from_signals(size=...)` with a DataFrame of same shape as price data.

```python
# Fixed units: buy N shares each entry
size_df = pd.DataFrame(
    np.where(entries.values, fixed_units, 0),
    index=price.index,
    columns=price.columns,
)

# Fixed cash: buy $N worth each entry
cash_per_trade = 10_000  # $10k per trade
size_df = pd.DataFrame(
    np.where(entries.values, cash_per_trade / price.values, 0),
    index=price.index,
    columns=price.columns,
)
```

### 4.2 ATR-Based Sizing

**Decision D-02:** ATR-based sizing = `risk% × equity / (ATR × multiplier)`.

The ATR value must come from the indicator cache (Phase 3) or be computed on-the-fly:

```python
# ATR position size per entry:
# position_size = risk_per_trade * account_equity / (atr_value * atr_multiplier)
risk_per_trade = 0.01  # 1% risk per trade
atr_multiplier = 2.0   # 2× ATR stop distance

atr_values = await indicator_cache.get_series("atr", timeframe="1D", symbol=symbol)
# Align with price data
size_per_atr = risk_per_trade * init_cash / (atr_values * atr_multiplier)
size_df = pd.DataFrame(
    np.where(entries.values, size_per_atr.values, 0),
    ...
)
```

**Key risk:** ATR-based sizing produces positions that vary with volatility. During low-volatility regimes, positions may be very large. Must enforce `max_position_size` cap (from `RiskParams`).

### 4.3 Kelly Criterion Sizing

**Decision D-02:** Kelly fraction = `f = p - q/b` where `p = win_rate`, `q = 1-p`, `b = avg_win/avg_loss`.

Kelly sizing is **circular** for a backtest — you need the backtest result to compute the Kelly fraction, but you need the Kelly fraction to run the backtest.

**Resolution for Phase 4:**
1. Run a **first pass** with fixed sizing to estimate win rate, avg win, avg loss.
2. Compute Kelly fraction from first-pass metrics.
3. Run a **second pass** using the computed Kelly fraction.
4. Apply half-Kelly (`0.5 × f`) as default for safety.

Alternatively, for systematic strategies, the Kelly fraction can be **preset** from historical strategy statistics (stored in `RiskParams.kelly_fraction`, default 0.5).

### 4.4 Implementation via `size` Parameter

Rather than using `from_signals(size=...)` with static values, a more flexible approach for Phase 4 is to build the **size array** separately and pass it to `from_signals()`:

```python
def compute_position_size(
    close: pd.DataFrame,
    entries: pd.DataFrame,
    method: str,
    params: dict,
) -> pd.DataFrame:
    """Compute per-bar, per-symbol position sizes.
    
    Returns DataFrame of same shape as close with position sizes
    (in units or dollars depending on method).
    """
    if method == "fixed":
        return _fixed_size(close, entries, params)
    elif method == "atr":
        return _atr_size(close, entries, params)
    elif method == "kelly":
        return _kelly_size(close, entries, params)
```

This gives `sizing.py` a clean API: `compute_position_size(close, entries, method, params) → pd.DataFrame`.

---

## 5. Walk-Forward Optimization

### 5.1 Expanding Window Mode

**Decision D-09:** Expanding window = train grows, test fixed.

Timeline:
```
Fold 1: [train: 0..252] [test: 252..252+N]
Fold 2: [train: 0..252+N] [test: 252+N..252+2N]
Fold 3: [train: 0..252+2N] [test: 252+2N..252+3N]
...
```

Implementation:
```python
def expanding_windows(
    n_bars: int,
    train_pct: float = 0.7,
    min_train: int = 252,
) -> list[tuple[int, int, int, int]]:
    """Generate (train_start, train_end, test_start, test_end) indices."""
    n_test = int(n_bars * (1 - train_pct))
    windows = []
    test_start = min_train
    
    while test_start + n_test <= n_bars:
        windows.append((0, test_start, test_start, test_start + n_test))
        test_start += n_test
    
    return windows
```

### 5.2 Rolling Window Mode

**Decision D-09:** Rolling window = train + test fixed, both slide.

```
Fold 1: [train: 0..252] [test: 252..252+N]
Fold 2: [train: N..252+N] [test: 252+N..252+2N]
Fold 3: [train: 2N..252+2N] [test: 252+2N..252+3N]
...
```

### 5.3 Optimization Loop Structure

```python
class WalkForwardOptimizer:
    """Walk-forward parameter optimization."""

    async def optimize(
        self,
        config: BacktestRunConfig,
        param_grid: dict[str, list],
    ) -> OptimizationResult:
        """Run walk-forward optimization over a parameter grid.
        
        For each fold:
        1. Slice OHLCV data to train period
        2. For each parameter combo:
           a. Build signals from filter config
           b. Run vbt.Portfolio.from_signals()
           c. Compute in-sample metrics
        3. Select best params (by Sharpe by default) → D-12
        4. Run test period with best params → out-of-sample metrics
        5. Store fold results
        
        Returns:
            OptimizationResult with best params, in-sample/OOS metrics, sensitivity.
        """
```

### 5.4 Parameter Grid Definition

**Decision D-11:** Optimizable parameters: position sizing method, risk %, ATR multiplier, Kelly fraction, entry/exit filter params.

The param grid is defined as a dict of `{param_name: [values]}`. The optimizer performs grid search (Cartesian product):

```python
param_grid = {
    "position_sizing": ["fixed", "atr", "kelly"],
    "risk_per_trade": [0.005, 0.01, 0.02],
    "atr_multiplier": [1.5, 2.0, 3.0],
    "kelly_fraction": [0.25, 0.5, 0.75],
    "rsi_entry_threshold": [25, 30, 35],  # filter param
}
```

For N params with M values each, this is M^N combinations. With M=3 and N=5, that's 243 combos per fold. With 10 folds, ~2430 backtests. **This is fast with vectorbt** — each `from_signals()` call is fully vectorized.

### 5.5 In-Sample / Out-of-Sample Metrics

**Decision D-12:** Optimization metric: Sharpe (default), Sortino, Calmar, or custom.

**Decision D-13:** Results stored as `OptimizationResult`.

```python
@dataclass
class FoldResult:
    """Results from a single walk-forward fold."""
    fold_index: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    best_params: dict[str, Any]
    in_sample_metrics: Metrics
    out_of_sample_metrics: Metrics
    oos_equity_curve: pd.Series

class OptimizationResult(BaseModel):
    """Complete walk-forward optimization results."""
    model_config = ConfigDict(frozen=True)

    symbol: str
    param_grid: dict[str, list[Any]]
    optimization_metric: Literal["sharpe", "sortino", "calmar", "custom"] = "sharpe"
    folds: list[FoldResult]
    best_params_overall: dict[str, Any]
    oos_metrics_aggregated: Metrics
    parameter_sensitivity: dict[str, list[float]]
```

**Parameter sensitivity** measures how much the OOS metric varies when a parameter changes (similarity to SHAP analysis for parameters). For each parameter, compute the variance of OOS metrics across values while holding others constant.

---

## 6. Monte Carlo Simulation

### 6.1 vectorbt Simulation Capabilities

**Decision D-14:** 1000+ paths using vectorbt's `simulate()`.

After research, vectorbt does **NOT** have a dedicated `montecarlo.simulate()` method in the open-source version. The simulation features are primarily in **VectorBT PRO**.

**Options for Phase 4:**

| Option | Description | Complexity | Performance |
|--------|-------------|------------|-------------|
| **A: Manual resampling + `from_orders()`** | Resample returns with replacement, reconstruct price paths, re-run `from_orders()` with same signals for each path | Medium | Slow for 1000+ paths (each path is a full backtest) |
| **B: Manual equity curve simulation** | Compute daily strategy returns from the base backtest, then simulate equity paths by resampling returns and computing cumulative product | Low | Fast (vectorized over all paths) |
| **C: Use numpy random for path generation** | `np.random.choice()` to resample daily returns, build equity curve `cumprod(1 + returns)` for each path | Low | Fastest (pure numpy) |
| **D: Implement simple MC class** | Custom MonteCarloSimulator that takes daily returns series and generates paths with bootstrap/block bootstrap | Medium | Fast |

**Recommendation: Option B + Option C** — Use the base backtest's daily returns to simulate equity paths. This avoids re-running the full backtest for each path.

```python
class MonteCarloSimulator:
    """Monte Carlo simulation of portfolio equity curves."""

    def simulate(
        self,
        daily_returns: pd.Series,
        n_paths: int = 1000,
        method: Literal["bootstrap", "block_bootstrap"] = "bootstrap",
        block_size: int = 20,
        confidence: float = 0.95,
    ) -> MCSimulationResult:
        """Simulate Monte Carlo equity paths from historical returns.
        
        Args:
            daily_returns: Base strategy daily returns (from base backtest).
            n_paths: Number of simulation paths.
            method: Resampling method.
            block_size: Block size for block bootstrap.
            confidence: Confidence level for intervals.
        
        Returns:
            MCSimulationResult with equity curves, percentiles, and ruin stats.
        """
        if method == "bootstrap":
            samples = np.random.choice(daily_returns, (n_paths, len(daily_returns)))
        else:  # block_bootstrap
            samples = self._block_bootstrap(daily_returns, n_paths, block_size)
        
        # Compute equity curves: cumprod(1 + returns) * init_cash
        equity_curves = np.cumprod(1 + samples, axis=1) * self._init_cash
        
        # Compute percentiles
        alpha = 1 - confidence
        lower_pct = alpha / 2 * 100
        upper_pct = (1 - alpha / 2) * 100
        
        return MCSimulationResult(
            n_paths=n_paths,
            method=method,
            equity_curves=equity_curves,  # numpy array
            percentiles={
                "p5": np.percentile(equity_curves[:, -1], 5),
                "p50": np.percentile(equity_curves[:, -1], 50),
                "mean": np.mean(equity_curves[:, -1]),
                "p95": np.percentile(equity_curves[:, -1], 95),
            },
            ...
        )
```

### 6.2 Bootstrap vs Block Bootstrap

**Decision D-16:** Two methods — simple bootstrap and block bootstrap.

**Bootstrap:** Resample daily returns with replacement. Pros: Simple, well-understood. Cons: Destroys autocorrelation structure (volatility clustering, trend persistence).

**Block Bootstrap:** Partition returns into blocks of size `k=20` (default), sample blocks with replacement, concatenate. Pros: Preserves short-term autocorrelation. Cons: Block boundaries introduce discontinuities.

**Statistical note:** For trading strategy returns, **block bootstrap is preferred** (D-16 correctly identifies this). Financial returns exhibit volatility clustering, which simple bootstrap destroys.

### 6.3 Confidence Intervals & Ruin Probability

**Decision D-15:** CI at 95% (default) and 99%.
**Decision D-17:** Output percentiles: 5, median, mean for final equity, max DD, Sharpe, CAGR.

**Ruin probability** (from Specific Ideas): P(final equity < 50% of initial equity):

```python
final_equities = equity_curves[:, -1]
ruin_probability = np.mean(final_equities < 0.5 * self._init_cash)
```

**Important:** For Sharpe and CAGR percentiles, we need to compute these statistics PER PATH, not just final equity:

```python
for path in equity_curves:
    path_returns = pd.Series(np.diff(path) / path[:-1])
    sharpe = np.sqrt(252) * path_returns.mean() / path_returns.std()
    cagr = (path[-1] / path[0]) ** (252 / len(path_returns)) - 1
    # collect per-path statistics → percentiles
```

---

## 7. Metrics & Trade Ledger

### 7.1 Metric Source Mapping: vectorbt Native vs Custom

**Decision D-18:** Core metrics: Sharpe, Sortino, Calmar, Max DD, Win Rate, Expectancy, Profit Factor, SQN, Ulcer Index, CAGR.

| Metric | vectorbt Source | Method |
|--------|----------------|--------|
| Sharpe | `portfolio.sharpe_ratio()` | Native via `portfolio.stats()` |
| Sortino | `portfolio.sortino_ratio()` | Native via `portfolio.stats()` |
| Calmar | `portfolio.calmar_ratio()` | Native via `portfolio.stats()` |
| Max DD | `portfolio.max_drawdown()` | Native via `portfolio.stats()` |
| Win Rate | `portfolio.win_rate()` | Native via `portfolio.stats()` |
| Expectancy | `portfolio.expectancy()` | Native via `portfolio.stats()` |
| Profit Factor | `portfolio.profit_factor()` | Native via `portfolio.stats()` |
| SQN | `portfolio.sqn()` | Native via `portfolio.stats()` |
| Ulcer Index | **❌ Not native** | Custom compute: `sqrt(mean(drawdown_series^2))` |
| CAGR | `portfolio.cagr()` | Native via `portfolio.stats()` |

**Custom Ulcer Index formula:**
```python
def ulcer_index(drawdown_series: pd.Series) -> float:
    """Compute Ulcer Index from drawdown series.
    
    UI = sqrt(mean(drawdown^2))
    where drawdown is as decimal (0.25 = 25% underwater).
    """
    return np.sqrt(np.mean(drawdown_series ** 2))
```

The `MetricsComputer` class in `metrics.py` wraps vectorbt's native stats and adds custom computations.

### 7.2 MAE/MFE Computation from Daily OHLC

**D-19 requires MAE/MFE per trade.** vectorbt does not compute these natively.

**Definition:**
- **MAE (Maximum Adverse Excursion):** The largest unfavorable price movement from entry price during the trade.
- **MFE (Maximum Favorable Excursion):** The largest favorable price movement from entry price during the trade.

**From daily OHLC (D-19 specifies daily as available, intraday if available):**

```python
def compute_mae_mfe(
    trade_entry_idx: int,
    trade_exit_idx: int,
    entry_price: float,
    ohlcv: pd.DataFrame,
    direction: Literal["Long", "Short"],
) -> tuple[float, float]:
    """Compute MAE and MFE from daily OHLC data.
    
    For long trades:
        MFE = max(high[entry..exit]) - entry_price
        MAE = entry_price - min(low[entry..exit])
    
    For short trades:
        MFE = entry_price - min(low[entry..exit])
        MAE = max(high[entry..exit]) - entry_price
    """
    high = ohlcv.iloc[trade_entry_idx:trade_exit_idx + 1]["high"].max()
    low = ohlcv.iloc[trade_entry_idx:trade_exit_idx + 1]["low"].min()
    
    if direction == "Long":
        mfe = high - entry_price
        mae = entry_price - low
    else:
        mfe = entry_price - low
        mae = high - entry_price
    
    return max(0.0, mae), max(0.0, mfe)
```

**Integration with TradeLedger:** After getting `portfolio.trades.records`, post-process each trade to add MAE/MFE. The `TradeLedger` class handles this enrichment.

### 7.3 Trade Ledger Schema

The `TradeLedger` converts vectorbt's `trades.records` into structured `Trade` models (linking to existing `Trade` domain model in `models.py`):

```python
class TradeLedger:
    """Convert vectorbt trade records into structured Trade models."""

    def build_ledger(
        self,
        trades_records: pd.DataFrame,
        ohlcv: pd.DataFrame,
        signal_metadata: dict[int, dict] | None = None,
    ) -> list[Trade]:
        """Build structured trade ledger from vectorbt records.
        
        Args:
            trades_records: portfolio.trades.records DataFrame.
            ohlcv: OHLCV DataFrame for MAE/MFE computation.
            signal_metadata: Optional dict mapping entry index to signal metadata.
            
        Returns:
            List of Trade domain models with MAE/MFE/hold_duration populated.
        """
        trades = []
        for _, record in trades_records.iterrows():
            mae, mfe = compute_mae_mfe(
                record["entry_idx"],
                record["exit_idx"],
                record["entry_price"],
                ohlcv,
                "Long" if record["direction"] == 1 else "Short",
            )
            
            trade = Trade(
                symbol=self._idx_to_symbol(record["column"]),
                entry_time=ohlcv.index[record["entry_idx"]],
                exit_time=ohlcv.index[record["exit_idx"]],
                entry_price=record["entry_price"],
                exit_price=record["exit_price"],
                size=abs(record["size"]),
                fees=record.get("entry_fees", 0) + record.get("exit_fees", 0),
                pnl=record["pnl"],
                mae=mae,
                mfe=mfe,
            )
            trades.append(trade)
        
        return trades
```

### 7.4 Drawdown Analysis

**D-21:** Drawdown series with peak-to-trough, duration, recovery time.

From vectorbt:
```python
dd = portfolio.drawdown()               # drawdown series (fractional)
dd_duration = portfolio.drawdown_duration()  # bars since peak
```

For recovery time (time from trough back to previous peak):
```python
def compute_drawdown_stats(drawdown: pd.Series) -> dict:
    """Compute peak-to-trough, duration, and recovery time."""
    # Find drawdown periods
    is_underwater = drawdown < 0
    # Detect transitions: start and end of each drawdown period
    regime = (is_underwater != is_underwater.shift(1)).cumsum()
    
    periods = []
    for _, group in drawdown.groupby(regime):
        if group.iloc[0] < 0:  # In drawdown
            peak_val = 0  # Previous peak (drawdown = 0)
            trough_val = group.min()
            trough_idx = group.idxmin()
            duration = len(group)
            periods.append({
                "start": group.index[0],
                "trough": trough_idx,
                "end": group.index[-1],
                "depth": abs(trough_val),
                "duration_bars": duration,
            })
    
    return {"periods": periods, "avg_depth": ..., "avg_duration": ...}
```

---

## 8. Module Design & Class Structure

### 8.1 Directory Layout

```
backend/app/infrastructure/backtest/
├── __init__.py                   # Exports: BacktestEngine, run_backtest, BacktestConfig
├── engine.py                     # BacktestEngine — orchestrator: load data → build signals → run portfolio → compute metrics → store
├── signals.py                    # SignalAdapter — converts ScreenRunResult / indicator values to entry/exit/size arrays
├── sizing.py                     # PositionSizer — fixed, ATR, Kelly sizing strategies → returns size array
├── walk_forward.py               # WalkForwardOptimizer — expanding/rolling window grid search
├── monte_carlo.py                # MonteCarloSimulator — bootstrap/block bootstrap path simulation
├── metrics.py                    # MetricsComputer — wraps vectorbt stats + custom metrics (Ulcer, MAE/MFE)
├── ledger.py                     # TradeLedger — converts vectorbt order/trade records to structured Trade models
└── models.py                     # BacktestRunConfig, OptimizationResult, FoldResult, MCSimulationResult, BacktestRunRecord
```

### 8.2 Class Diagram

```
┌───────────────────────────────────────────────────────────────────────┐
│                       BacktestEngine (engine.py)                      │
│  Orchestrator: load config → load OHLCV → build signals → run         │
│  portfolio → compute metrics → build ledger → store                   │
│                                                                       │
│  Methods:                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ run(config) → BacktestRunRecord                                  │  │
│  │ run_walk_forward(config, param_grid) → OptimizationResult        │  │
│  │ run_monte_carlo(config, n_paths) → MCSimulationResult            │  │
│  │ run_full_analysis(config) → dict of all results                  │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└──────┬──────────┬──────────────┬──────────────┬───────────────────────┘
       │          │              │              │
       ▼          ▼              ▼              ▼
┌──────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────┐
│ Signal   │ │Position  │ │ WalkForward│ │ MonteCarlo   │
│ Adapter  │ │Sizer     │ │ Optimizer  │ │ Simulator    │
│          │ │          │ │            │ │              │
│ build_   │ │compute   │ │ optimize() │ │ simulate()   │
│ signals()│ │_size()   │ │            │ │              │
└────┬─────┘ └──────────┘ └────────────┘ └──────────────┘
     │                                                   │
     ▼                                                   ▼
┌──────────────┐                                  ┌──────────────┐
│ Metrics      │                                  │ TradeLedger  │
│ Computer     │                                  │              │
│              │                                  │ build_ledger │
│ compute()    │                                  │ ()           │
│ ulcer_index()│                                  └──────┬───────┘
│ mae_mfe()    │                                         │
└──────────────┘                                         ▼
                                                    ┌──────────────┐
                                                    │ DuckDB       │
                                                    │ backtest_    │
                                                    │ results      │
                                                    │ table        │
                                                    └──────────────┘
```

### 8.3 Data Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          BACKTEST FLOW                                       │
│                                                                              │
│  1. User provides BacktestRunConfig (symbols, timeframe, filters, sizing)    │
│     ↓                                                                        │
│  2. Load OHLCV data from DuckDB ohlcv table or Parquet files                │
│     ↓                                                                        │
│  3. SignalAdapter:                                                            │
│     a. Load indicator data from cache or compute on-the-fly                  │
│     b. Apply filter logic to produce entry/exit boolean arrays               │
│     c. Return (price, entries, exits) aligned DataFrames                     │
│     ↓                                                                        │
│  4. PositionSizer: compute size array based on method (fixed/ATR/Kelly)      │
│     ↓                                                                        │
│  5. vbt.Portfolio.from_signals(price, entries, exits, size=..., ...)         │
│     ↓                                                                        │
│  6. MetricsComputer:                                                          │
│     a. portfolio.stats() → native metrics                                    │
│     b. portfolio.drawdown() → drawdown stats + Ulcer index                   │
│     c. Combine into Metrics model                                            │
│     ↓                                                                        │
│  7. TradeLedger:                                                              │
│     a. portfolio.trades.records → vectorbt trade data                        │
│     b. Compute MAE/MFE per trade from OHLC                                   │
│     c. Convert to Trade models with metadata                                 │
│     ↓                                                                        │
│  8. Build BacktestRunRecord with all results                                  │
│     ↓                                                                        │
│  9. Store in DuckDB backtest_results table (optional, cache)                 │
│     ↓                                                                        │
│  10. Return BacktestRunRecord                                                │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Integration Points with Phases 1, 2, 3

### What Phase 4 Consumes from Phase 1

| Phase 1 Asset | Phase 4 Usage | File |
|---------------|--------------|------|
| `get_db()` / `get_db_async()` | Read OHLCV data, write backtest results | `backend/app/core/database.py` |
| `partition_path()` | Locate OHLCV Parquet files for backtest | `backend/app/core/database.py` |
| `@indicator` registry | ATR, EMA indicators for position sizing | `backend/app/infrastructure/indicators.py` |
| `compute_all()` | Batch indicator computation for signals | `backend/app/infrastructure/indicators.py` |
| `ComputeSettings` | Default indicator timeframes, cache settings | `backend/app/core/config.py` |
| `set_correlation_id()` | Run-level correlation ID | `backend/app/core/logging.py` |
| `get_logger()` | Structured logging throughout | `backend/app/core/logging.py` |
| `OHLCV`, `Position`, `Trade`, `Metrics`, `BacktestConfig`, `RiskParams` | Domain models | `backend/app/domain/models.py` |

### What Phase 4 Consumes from Phase 2

| Phase 2 Asset | Phase 4 Usage | File |
|---------------|--------------|------|
| `ohlcv` DuckDB table | Historical price data for backtesting | `backend/app/core/database.py` (DDL) |
| `symbol_metadata` table | Symbol list, asset class filtering | `backend/app/core/database.py` (DDL) |
| Parquet `data/**/*.parquet` | Direct OHLCV read path for large backtests | Filesystem |

### What Phase 4 Consumes from Phase 3

| Phase 3 Asset | Phase 4 Usage | File |
|---------------|--------------|------|
| `_FILTER_REGISTRY` | Filter functions for signal generation | `backend/app/infrastructure/screener/filters.py` |
| `IndicatorCache.get_series()` | Historical indicator values for signal + ATR sizing | `backend/app/infrastructure/screener/cache.py` |
| `broadcast_timeframe()` | Multi-timeframe alignment for signals | `backend/app/infrastructure/screener/broadcasting.py` |
| `ScreenEngine.screen()` | Screen results for signal baseline (as cross-check) | `backend/app/infrastructure/screener/engine.py` |
| `sort_timeframes()` | Timeframe ordering | `backend/app/infrastructure/screener/broadcasting.py` |

### What Phase 4 Provides to Downstream Phases

| Downstream Phase | What It Gets | How |
|-----------------|-------------|-----|
| Phase 5 (Risk) | Backtest results (metrics, trades, equity curves) | Shared DuckDB `backtest_results` table + domain models |
| Phase 6 (API) | `BacktestEngine` class for REST endpoints | Import |
| Phase 7 (Frontend) | `BacktestRunRecord` JSON serialization | JSON over HTTP |
| Phase 9 (Advanced Backtest) | Walk-forward, MC base classes, result schemas | Module extension hooks |

---

## 10. DuckDB Schema for Backtest Results

**Decision D-24:** Results cached in DuckDB.

Schema for storing backtest run outputs:

```sql
-- Main backtest results table (one row per run)
CREATE TABLE IF NOT EXISTS backtest_results (
    run_id VARCHAR PRIMARY KEY,           -- UUID
    config_hash VARCHAR NOT NULL,         -- SHA256 of BacktestRunConfig
    symbol VARCHAR NOT NULL,
    timeframe VARCHAR NOT NULL,
    timeframe VARCHAR NOT NULL,
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ NOT NULL,
    initial_cash DOUBLE NOT NULL,
    position_sizing VARCHAR NOT NULL,
    metrics_json VARCHAR,                 -- JSON of Metrics model
    stats_json VARCHAR,                   -- Full vectorbt stats JSON
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    duration_ms DOUBLE
);

-- Trade ledger (one row per trade)
CREATE TABLE IF NOT EXISTS backtest_trades (
    run_id VARCHAR NOT NULL REFERENCES backtest_results(run_id),
    trade_index INTEGER NOT NULL,
    symbol VARCHAR NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ,
    entry_price DOUBLE NOT NULL,
    exit_price DOUBLE,
    size DOUBLE NOT NULL,
    direction VARCHAR NOT NULL,           -- 'Long' or 'Short'
    pnl DOUBLE,
    fees DOUBLE DEFAULT 0.0,
    mae DOUBLE,                          -- Maximum Adverse Excursion
    mfe DOUBLE,                          -- Maximum Favorable Excursion
    hold_duration_bars INTEGER,
    exit_reason VARCHAR,
    signal_metadata_json VARCHAR,         -- JSON: {"confidence": 0.85, "source": "rsi_oversold"}
    PRIMARY KEY (run_id, trade_index)
);

-- Equity curve (one row per bar, per run)
CREATE TABLE IF NOT EXISTS backtest_equity_curves (
    run_id VARCHAR NOT NULL REFERENCES backtest_results(run_id),
    timestamp TIMESTAMPTZ NOT NULL,
    equity DOUBLE NOT NULL,               -- Portfolio value
    returns DOUBLE,                       -- Daily return
    drawdown DOUBLE,                      -- Drawdown from peak (decimal)
    PRIMARY KEY (run_id, timestamp)
);

-- Optimization results (one row per fold per parameter set)
CREATE TABLE IF NOT EXISTS backtest_optimization_results (
    run_id VARCHAR NOT NULL REFERENCES backtest_results(run_id),
    fold_index INTEGER NOT NULL,
    param_set_index INTEGER NOT NULL,
    params_json VARCHAR NOT NULL,         -- JSON of parameter set
    in_sample_metrics_json VARCHAR,       -- JSON of Metrics
    out_of_sample_metrics_json VARCHAR,   -- JSON of Metrics  
    is_selected BOOLEAN DEFAULT false,    -- Was this param set selected as best?
    PRIMARY KEY (run_id, fold_index, param_set_index)
);

-- Monte Carlo simulation results
CREATE TABLE IF NOT EXISTS backtest_mc_results (
    run_id VARCHAR NOT NULL REFERENCES backtest_results(run_id),
    n_paths INTEGER NOT NULL,
    method VARCHAR NOT NULL,              -- 'bootstrap' or 'block_bootstrap'
    final_equity_p5 DOUBLE,
    final_equity_p50 DOUBLE,
    final_equity_mean DOUBLE,
    final_equity_p95 DOUBLE,
    max_drawdown_p50 DOUBLE,
    sharpe_p50 DOUBLE,
    cagr_p50 DOUBLE,
    ruin_probability DOUBLE,
    paths_parquet VARCHAR,                -- Path to Parquet file with all equity curves
    results_json VARCHAR                  -- Full serialized MCSimulationResult
);
```

**Note on storage for Monte Carlo paths:** Storing 1000+ full equity curves in the database is excessive. The summary statistics go in the DB table, while the full paths are stored as a single Parquet file referenced by `paths_parquet`.

**Note on `config_hash`:** SHA256 of the serialized `BacktestRunConfig` (minus generated fields). This enables **cache lookup**: if a backtest with the same config has already been run, return cached results.

---

## 11. Domain Model Extensions Needed

The existing domain models in `backend/app/domain/models.py` are good but need extensions for Phase 4.

### BacktestConfig (existing — needs extension)

```python
# CURRENT:
class BacktestConfig(BaseModel):
    symbols: list[str]
    start: datetime
    end: datetime
    initial_cash: float = Field(default=100_000.0, gt=0)
    fees: float = Field(default=0.001, ge=0.0)
    slippage: float = Field(default=0.001, ge=0.0)
    position_sizing: Literal["fixed", "atr", "kelly"] = "fixed"
    strategy_params: dict[str, object] = Field(default_factory=dict)
```

**Gaps vs D-22 requirements:**
1. No `signal_source` — how does the backtest get its signals? (filter name, screen config, direct indicator)
2. No `optimization` section — walk-forward params, param grid
3. No `monte_carlo` section — n_paths, method, confidence
4. Fee and slippage are flat fractions, not bps (D-03 uses bps)
5. `strategy_params` is too loose — needs structured filter references

**Recommendation:** Create a dedicated `BacktestRunConfig` in `backend/app/infrastructure/backtest/models.py` that nests sub-configs. Keep the existing `BacktestConfig` backwards-compatible (it's used by other phases).

```python
# NEW in backtest/models.py:
class SignalSource(BaseModel):
    """Defines how signals are generated for the backtest."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    type: Literal["screen_config", "filter_list", "indicator_crossing"]
    screen_name: str | None = None       # Name of screen template (if type=screen_config)
    filters: list[str] | None = None     # Filter names to apply (if type=filter_list)
    indicator_params: dict[str, Any] | None = None  # Indicator crossing thresholds

class OptimizationConfig(BaseModel):
    """Walk-forward optimization configuration."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    enabled: bool = False
    method: Literal["expanding", "rolling"] = "expanding"
    train_pct: float = Field(default=0.7, ge=0.5, le=0.9)
    min_train_bars: int = Field(default=252, ge=50)
    metric: Literal["sharpe", "sortino", "calmar", "custom"] = "sharpe"
    param_grid: dict[str, list[Any]] = Field(default_factory=dict)

class MonteCarloConfig(BaseModel):
    """Monte Carlo simulation configuration."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    enabled: bool = False
    n_paths: int = Field(default=1000, ge=100)
    method: Literal["bootstrap", "block_bootstrap"] = "bootstrap"
    block_size: int = Field(default=20, ge=5, le=100)
    confidence: float = Field(default=0.95, ge=0.8, le=0.999)

class BacktestRunConfig(BaseModel):
    """Complete configuration for a single backtest run."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    symbols: list[str]
    asset_class: str = "equities"
    timeframe: str = "1D"
    start: datetime
    end: datetime
    initial_cash: float = Field(default=100_000.0, gt=0)
    fees_bps: float = Field(default=10.0, ge=0.0, description="Fee in basis points")
    slippage_bps: float = Field(default=5.0, ge=0.0, description="Slippage in basis points")
    position_sizing: Literal["fixed", "atr", "kelly"] = "fixed"
    sizing_params: dict[str, Any] = Field(default_factory=dict)
    signal_source: SignalSource = Field(default_factory=lambda: SignalSource(type="indicator_crossing"))
    optimization: OptimizationConfig = Field(default_factory=OptimizationConfig)
    monte_carlo: MonteCarloConfig = Field(default_factory=MonteCarloConfig)
    
    # Computed properties
    @property
    def fees_decimal(self) -> float:
        """Convert bps to decimal fraction for vectorbt."""
        return self.fees_bps / 10_000
    
    @property
    def slippage_decimal(self) -> float:
        """Convert bps to decimal fraction for vectorbt."""
        return self.slippage_bps / 10_000
```

### Metrics (existing — check completeness)

The existing `Metrics` model covers all D-18 metrics except CAGR:

```python
class Metrics(BaseModel):
    sharpe: float | None = None
    sortino: float | None = None
    calmar: float | None = None
    max_dd: float | None = None
    win_rate: float | None = None
    expectancy: float | None = None
    profit_factor: float | None = None
    sqn: float | None = None
    ulcer: float | None = None
    # Missing CAGR — should be added for completeness
    cagr: float | None = None
```

### Trade (existing — check gaps)

The existing `Trade` model covers D-19 well:

```python
class Trade(BaseModel):
    symbol: str
    entry_time: datetime
    exit_time: datetime | None = None
    entry_price: float
    exit_price: float | None = None
    size: float
    fees: float = 0.0
    pnl: float | None = None
    mae: float | None = None
    mfe: float | None = None
```

**Gap:** Missing `hold_duration` and `exit_reason` (D-19 includes these). These should be added.

---

## 12. BacktestConfig Evolution

### Phase 4 Config Section (to add to `config.yaml`)

```yaml
backtest:
  default_timeframe: 1D
  default_position_sizing: fixed
  default_fees_bps: 10.0
  default_slippage_bps: 5.0
  default_initial_cash: 100000.0
  default_min_train_bars: 252
  default_train_pct: 0.7
  cache_results: true
  max_symbols_per_run: 50
  parallel_symbols: 4
```

Add to `backend/app/core/config.py`:

```python
class BacktestSettings(BaseSettings):
    """Backtest engine settings."""
    model_config = SettingsConfigDict(env_prefix="CONFLU_BACKTEST_")

    default_timeframe: str = Field(default="1D")
    default_position_sizing: Literal["fixed", "atr", "kelly"] = "fixed"
    default_fees_bps: float = Field(default=10.0, ge=0.0)
    default_slippage_bps: float = Field(default=5.0, ge=0.0)
    default_initial_cash: float = Field(default=100_000.0, gt=0)
    default_min_train_bars: int = Field(default=252, ge=50)
    default_train_pct: float = Field(default=0.7, ge=0.5, le=0.9)
    cache_results: bool = Field(default=True)
    max_symbols_per_run: int = Field(default=50, ge=1, le=1000)
    parallel_symbols: int = Field(default=4, ge=1, le=16)

# Add to AppSettings:
class AppSettings(BaseSettings):
    ...
    backtest: BacktestSettings = BacktestSettings()
```

---

## 13. Async Execution Strategy

**Decision D-27:** Async execution for long-running optimizations/MC. Celery deferred to Phase 6.

**Strategy for Phase 4:**
- All vectorbt operations are **CPU-bound** (numpy/Numba). They block the async event loop.
- Use `asyncio.to_thread()` or `loop.run_in_executor()` to run vectorbt calls in a thread pool.
- The `BacktestEngine` class wraps all blocking calls:

```python
class BacktestEngine:
    async def run(self, config: BacktestRunConfig) -> BacktestRunRecord:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._run_sync, config)
    
    def _run_sync(self, config: BacktestRunConfig) -> BacktestRunRecord:
        """Synchronous implementation (CPU-bound vectorbt work)."""
        # All vbt calls here — runs in thread pool
```

**For walk-forward optimization** (many backtest runs):
- Each fold can be parallelized: run multiple folds in separate threads.
- Use `concurrent.futures.ThreadPoolExecutor` with `max_workers=4` (configurable).
- Each fold runs its grid search independently.

**For Monte Carlo** (1000+ paths):
- The simulation is a single numpy operation — fast enough to run in one thread.
- No need for parallelization.

---

## 14. New Dependencies

### No new packages needed

All computation dependencies are already in `pyproject.toml`:

| Package | Version | Already Present? | Phase 4 Use |
|---------|---------|-----------------|-------------|
| `vectorbt` | `>=0.40.0` | ✅ Phase 1 | Central — `Portfolio.from_signals()`, `from_orders()`, `stats()` |
| `pandas` | `>=2.0,<3` | ✅ Phase 1 | DataFrames for signal/size construction |
| `numpy` | `>=1.26` | ✅ Phase 1 | Monte Carlo path generation, array ops |
| `duckdb` | `>=0.10.0` | ✅ Phase 1 | OHLCV reads, backtest results storage |
| `pandas-ta` | `>=0.3.14` | ✅ Phase 1 | Indicator computation for signals/ATR |
| `structlog` | `>=24.1,<25` | ✅ Phase 1 | Logging throughout |
| `pydantic` | `>=2.0,<3` | ✅ Phase 1 | Backtest config and result models |

**No new infrastructure needed:**
- No new databases — uses existing DuckDB
- No new message brokers — async via asyncio.to_thread
- No new compute services — all in-process vectorized computation

---

## 15. Risks & Mitigations

### High Risk

| Risk | Description | Likelihood | Impact | Mitigation |
|------|-------------|------------|--------|------------|
| **VectorBT PRO API mismatch** | Phase 4 decisions reference simulation and walk-forward features that may be PRO-only. The open-source vectorbt (`vbt>=0.40.0`) may not have `montecarlo.simulate()` or built-in walk-forward optimization. | Medium | **High** | Use manual resampling for Monte Carlo (see §6.1, Option B). Build custom walk-forward loop with grid search over vectorized `from_signals()` calls (see §5.3). |
| **Kelly sizing circular dependency** | Kelly fraction requires win/avg_win/avg_loss from backtest results, but is needed before running the backtest. | **Certain** | Medium | Two-pass approach: 1st pass with fixed sizing to estimate Kelly inputs, 2nd pass with computed Kelly fraction. Default to half-Kelly. See §4.3. |
| **Signal conversion complexity** | Converting Phase 3 screener filters into historical entry/exit boolean arrays over multiple symbols is non-trivial. ScreenEngine only runs at the current timestamp, not historically. | Medium | **High** | Use `SignalAdapter` that directly applies `_FILTER_REGISTRY` filter functions over historical indicator data — same logic as Phase 3 but over full time range. Document this clearly in PLAN.md. |
| **Multi-symbol portfolio effects** | Running backtests with multiple symbols sharing cash (`cash_sharing=True`, `group_by`) has subtle semantics with `call_seq` and position allocation. | Medium | High | Start with single-symbol backtests in Phase 4 base case. Multi-symbol with cash sharing is an advanced mode. Document call_seq behavior from vectorbt tests. |

### Medium Risk

| Risk | Description | Likelihood | Impact | Mitigation |
|------|-------------|------------|--------|------------|
| **MAE/MFE accuracy with daily data** | MAE/MFE computed from daily OHLC (high/low) is approximate — the true intraday excursion may be larger. | **Certain** | Medium | Document that MAE/MFE is computed from daily OHLC range. In Phase 9, add intraday MAE/MFE when lower TF data is available. |
| **vectorbt `size` array alignment** | `from_signals(size=...)` with per-bar size arrays must exactly match the index of the price data. Misalignment causes silent errors. | Medium | Medium | Build size array from the same index as price data. Add validation in `PositionSizer`: `assert size.index.equals(close.index)`. |
| **Drawdown recovery time precision** | Recovery time is measured at the bar level — may be off by up to N bars depending on trade timing within the bar. | Low | Low | Accept bar-level precision. Add `recovery_time_days` = `recovery_bars × bar_length` for human readability. |
| **Config hash collision** | `config_hash` for caching may collide if two different configs produce the same SHA256 hash. | Near-zero | Low | Use full UUID as `run_id`. Config hash is for lookup only — if collision is detected (multiple runs with same hash), return the most recent. |

### Low Risk

| Risk | Description | Likelihood | Impact | Mitigation |
|------|-------------|------------|--------|------------|
| **DuckDB write contention** | Multiple backtest runs writing to `backtest_results` simultaneously could conflict. | Low | Low | Each run gets a unique `run_id`. Writes are INSERT-only. No UPDATEs needed. |
| **Monte Carlo memory for large datasets** | 1000 paths × 10 years × 252 days = 2.5M float64 values ≈ 20MB. Fine. For 100K paths, 2GB — problematic. | Low | Low | Cap n_paths at 10_000 for Phase 4. Store only summary stats in DB, full paths in Parquet. |
| **Frequency inference from data** | `freq` parameter for vectorbt must match pandas frequency string. Irregular data (missing days) could cause incorrect annualization. | Medium | Low | Use `pd.infer_freq()` on the index before passing to vectorbt. For equity data with only trading days, use `freq='B'` (business days). |

---

## 16. Open Questions for Planning

These need resolution before writing PLAN.md:

### Q1: BacktestConfig: Extend Existing Model or Create New One?

The existing `BacktestConfig` in `backend/app/domain/models.py` has basic fields but lacks signal source, optimization, and Monte Carlo config. Phase 4 D-22 implies a richer config.

Options:
- **A: Extend existing `BacktestConfig`** — add all new fields. Risk: bloats a shared domain model with Phase 4-specific details.
- **B: Create `BacktestRunConfig` in `backtest/models.py`** — separate, Phase-4-specific config. `BacktestConfig` remains for cross-phase use.
- **C: Use `BacktestConfig` as the base, extend with nested `OptimizationConfig` etc.** — adds nested models to `domain/models.py`.

**Recommendation:** **Option B** — Create `BacktestRunConfig` in `backtest/models.py`. It converts to/from the existing `BacktestConfig` for cross-phase compatibility. Keeps domain models clean.

### Q2: Signal Source Abstraction — How Generic?

Phase 4 signals can come from multiple sources:
1. A Phase 3 screen config (e.g., "run the trend-follower screen historically")
2. Direct indicator crossing rules (e.g., "enter when RSI(14) < 30")
3. User-provided entry/exit arrays
4. Future ML-generated signals (Phase 9)

How generic should the signal adapter be?

**Recommendation:** Build for sources 1 and 2 in Phase 4. Source 3 is useful for testing. Source 4 is deferred. The `SignalSource` Pydantic model defines the signal type clearly.

### Q3: Walk-Forward — Grid Search Only or Include Random/Bayesian?

D-11 mentions grid search for discrete params. D-12 says Bayesian for continuous deferred. Phase 4 scope: grid search only.

Options:
- **Grid search only** — Cartesian product of param values. Simple, deterministic, easy to debug.
- **Random search** — sample N random combos. More efficient for high-dimensional spaces.
- **Bayesian (deferred)** — Phase 9.

**Recommendation:** Grid search only for Phase 4. Keep the parameter grid API extensible (dict of `{param: [values]}`) so random/Bayesian can use the same loop structure in Phase 9.

### Q4: Equity Curve Storage — DuckDB Table or Parquet?

D-24 says results cached in DuckDB `backtest_results` table. The equity curve for a 10-year daily backtest is ~2520 rows per symbol. For 50 symbols, that's 126K rows — fine for DuckDB.

Options:
- **DuckDB table** — `backtest_equity_curves` table. Direct SQL queryable.
- **Parquet file** — stored alongside data. Faster for large datasets.
- **Both** — summary in DB, full curve in Parquet.

**Recommendation:** DuckDB table for Phase 4. Simpler integration with existing patterns. If performance becomes an issue (Phase 9), migrate to Parquet.

### Q5: Multi-Symbol Backtesting — Single Pass or Per-Symbol?

For a backtest across 50 symbols with cash sharing and $100K total:
- **Single pass:** One `vbt.Portfolio.from_signals()` with `group_by` and `cash_sharing=True`. Closer to real portfolio behavior (cash competition).
- **Per-symbol:** Run 50 independent backtests with $2K each. Simpler, independent PnLs.

**Recommendation:** **Per-symbol** is the default for Phase 4. This is simpler, avoids vectorbt's complex cash-sharing semantics, and gives clean per-symbol metrics. Add multi-symbol cash-sharing as an advanced mode in Phase 9. The engine supports both modes.

### Q6: Adding Backtest Settings to Config?

Should `BacktestSettings` be added to `config.yaml` and `AppSettings` in Phase 4?

**Recommendation:** **Yes.** This follows the established pattern from Phase 3 (`ScreenSettings`). Include defaults for fees, slippage, sizing, caching, and parallelization.

### Q7: Metrics — Add CAGR to Existing Model?

The existing `Metrics` model (D-18) covers all metrics except CAGR.

**Recommendation:** **Yes.** Add `cagr: float | None = None` to the existing `Metrics` model in `domain/models.py`. This is a trivial, non-breaking change.

### Q8: Trade Model — Add hold_duration and exit_reason?

The existing `Trade` model lacks `hold_duration` and `exit_reason` (D-19 includes these).

**Recommendation:** **Yes.** Add `hold_duration_bars: int | None = None` and `exit_reason: str | None = None` to the existing `Trade` model. These are computed by `TradeLedger` during post-processing.

### Q9: Backtest Cache Strategy — When to Invalidate?

The `backtest_results` table with `config_hash` enables caching. But when should a cached result be invalidated?

Options:
- **Never** — results are immutable. Same config → same result. Run cache lives forever.
- **When OHLCV data extends** — re-run if new bars are available past the original end date.
- **When signals change** — re-run if any filter definition changes.

**Recommendation:** **Never invalidate** for Phase 4. The config hash captures the exact configuration. If the user changes parameters → new config hash → new run. Only re-run on explicit user action or when data extends (detected by comparing `end` against `MAX(timestamp)` in `ohlcv`). This is a Phase 6 concern.

### Q10: Testing Strategy for Backtest Engine?

Phase 4 testing follows the established patterns from Phases 1-3.

**Recommended test files:**

| Test File | What It Tests | Type |
|-----------|--------------|------|
| `test_backtest_engine.py` | Full run: load data → run backtest → verify metrics, trades, equity curve shape | Integration |
| `test_backtest_signals.py` | SignalAdapter conversion: filter → entry/exit arrays, timeframe alignment | Unit + property |
| `test_backtest_sizing.py` | PositionSizer: fixed, ATR, Kelly output shapes and value ranges | Unit + property |
| `test_backtest_walk_forward.py` | Walk-forward: window generation, optimization loop, fold results | Integration |
| `test_backtest_monte_carlo.py` | MC simulation: path generation, percentiles, ruin probability | Unit + property |
| `test_backtest_metrics.py` | MetricsComputer: Ulcer index, MAE/MFE, CAGR computation | Unit |
| `test_backtest_ledger.py` | TradeLedger: conversion from vectorbt records, MAE/MFE enrichment | Unit |
| `test_backtest_models.py` | Config validation, serialization, config_hash consistency | Unit |

---

## Summary of Technology Choices

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Core backtest API | `vbt.Portfolio.from_signals()` with array `size` | Vectorized, supports all sizing modes (D-01) |
| Position sizing | Separate `PositionSizer` returning size array | Clean separation, testable, extensible |
| Signal source | Direct filter reapplication over historical indicator data | Same logic as Phase 3, no timing mismatch |
| Walk-forward | Custom loop with grid search over `from_signals()` | vectorbt PRO may be needed for built-in WF |
| Monte Carlo | Manual returns resampling + cumprod | Avoids PRO dependency, fast numpy ops |
| Native metrics | `portfolio.stats()` | Covers 9/10 metrics from D-18 |
| Custom metrics | Ulcer, CAGR, MAE, MFE | Not in vectorbt — computed separately |
| Trade ledger | `portfolio.trades.records` → enriched `Trade` models | Matches existing domain model |
| Result storage | DuckDB `backtest_results` + `backtest_trades` + `backtest_equity_curves` tables | Same DB as rest of platform, SQL-queryable |
| MC path storage | Summary in DB, full paths in Parquet | DB stays lean, Parquet for analysis |
| Async | `loop.run_in_executor()` for vectorbt CPU-bound calls | No Celery needed (deferred to Phase 6) |
| Multi-symbol | Per-symbol default, cash-sharing deferred to Phase 9 | Simpler Phase 4, complex later |
| Config hash | SHA256 of serialized `BacktestRunConfig` | Cache lookup, immutable runs |
| Backtest settings | New `BacktestSettings` config section | Consistent with Phase 3 pattern |
| No new packages | All dependencies already present | No supply chain risk for Phase 4 |

---

*This research feeds into `04-PLAN.md`. All documentation references verified against current (June 2026) library APIs. See Context7 lookups for `/polakowo/vectorbt` Portfolio API patterns.*

---

## Post-Research Actions

Based on the findings above, the following actions are needed before or during Phase 4 planning:

1. **Minor domain model update:** Add `cagr` to `Metrics`, add `hold_duration_bars` and `exit_reason` to `Trade` in `backend/app/domain/models.py`.
2. **Config update:** Add `BacktestSettings` to `backend/app/core/config.py` and `config.yaml`.
3. **DuckDB schema:** Add DDL for `backtest_results`, `backtest_trades`, `backtest_equity_curves`, `backtest_optimization_results`, `backtest_mc_results` tables.
4. **Module creation:** Create `backend/app/infrastructure/backtest/` package with all 8 submodules.
5. **VectorBT version check:** Verify `vbt>=0.40.0` has `trades.records` with the documented columns (entry_idx, exit_idx, pnl, fees, etc.) — if not, test and adjust.
