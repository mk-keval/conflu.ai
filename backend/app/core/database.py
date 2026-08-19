"""DuckDB connection management and Parquet partitioning utilities."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

import duckdb

from backend.app.core.config import settings

# SQL DDL for the OHLCV table
OHLCV_DDL = """
CREATE TABLE IF NOT EXISTS ohlcv (
    symbol VARCHAR,
    timestamp TIMESTAMPTZ,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE,
    timeframe VARCHAR,
    asset_class VARCHAR,
    year INTEGER,
    month INTEGER
);
CREATE INDEX IF NOT EXISTS idx_ohlcv_lookup ON ohlcv (symbol, timeframe, timestamp);
CREATE INDEX IF NOT EXISTS idx_ohlcv_partition ON ohlcv (asset_class, year, month);
"""

# Parquet partition path pattern
# Example: data/equities/2025/01/AAPL_1D.parquet
PARTITION_TEMPLATE = "{asset_class}/{year:04d}/{month:02d}/{symbol}_{timeframe}.parquet"


def partition_path(
    asset_class: str,
    year: int,
    month: int,
    symbol: str,
    timeframe: str,
    *,
    data_dir: str | None = None,
) -> Path:
    """Build the Parquet file path for a given partition.

    Partition scheme: {data_dir}/{asset_class}/{year}/{month}/{symbol}_{timeframe}.parquet

    Args:
        asset_class: Asset class (e.g., 'equities', 'crypto', 'forex').
        year: Calendar year of the data.
        month: Calendar month (1-12) of the data.
        symbol: Normalized symbol name (e.g., 'AAPL', 'BTCUSDT').
        timeframe: Timeframe string (e.g., '1D', '1h', '15m').
        data_dir: Override data directory. Defaults to settings.core.duckdb_data_dir.

    Returns:
        Absolute Path to the Parquet file.
    """
    base = Path(data_dir or settings.core.duckdb_data_dir)
    relative = PARTITION_TEMPLATE.format(
        asset_class=asset_class,
        year=year,
        month=month,
        symbol=symbol,
        timeframe=timeframe,
    )
    return (base / relative).resolve()


def normalize_symbol(symbol: str) -> str:
    """Normalize a symbol to a filesystem-safe representation.

    Removes characters that are problematic in file paths and uppercases.

    Args:
        symbol: Raw symbol string (e.g., 'BTC/USDT', 'BRK.B').

    Returns:
        Normalized symbol (e.g., 'BTCUSDT', 'BRK_B').
    """
    return (
        symbol.replace("/", "")
        .replace("\\", "")
        .replace(":", "")
        .replace("*", "")
        .replace("?", "")
        .replace('"', "")
        .replace("<", "")
        .replace(">", "")
        .replace("|", "")
        .replace(".", "_")
        .upper()
    )


def _connect_with_timeout(db_path: str, *, read_only: bool, timeout_s: float) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection, aborting if it takes longer than ``timeout_s``.

    DuckDB's Python API has no native connect timeout, so the connect runs in a
    daemon worker thread and is abandoned if it exceeds the budget. A wedged
    connect (e.g. a locked database file) therefore surfaces as a
    ``TimeoutError`` instead of hanging the caller indefinitely.
    """
    import threading

    result: dict[str, object] = {}

    def _open() -> None:
        try:
            result["conn"] = duckdb.connect(db_path, read_only=read_only)
        except BaseException as exc:  # noqa: BLE001 - propagate any connect failure
            result["error"] = exc

    thread = threading.Thread(target=_open, daemon=True)
    thread.start()
    thread.join(timeout_s)
    if thread.is_alive():
        raise TimeoutError(f"DuckDB connect timed out after {timeout_s}s")
    if "error" in result:
        raise result["error"]  # type: ignore[misc]
    return result["conn"]  # type: ignore[return-value]


@contextmanager
def get_db(
    read_only: bool = False, timeout_s: float | None = None
) -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Get a DuckDB connection via context manager.

    DuckDB is embedded — each call creates a new connection to the same database
    file. Multiple read-only connections are safe concurrently. Writes serialize.

    Args:
        read_only: If True, open connection in read-only mode.
        timeout_s: Optional connect timeout in seconds. When set, the connect is
            abandoned (raising ``TimeoutError``) if it does not complete within
            the budget. Used by health checks so readiness probes fail fast
            instead of hanging on a locked database.

    Yields:
        DuckDB connection instance.

    Example:
        with get_db() as con:
            result = con.sql("SELECT COUNT(*) FROM ohlcv")
    """
    db_path = settings.core.duckdb_path
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if timeout_s is None:
        conn = duckdb.connect(db_path, read_only=read_only)
    else:
        conn = _connect_with_timeout(db_path, read_only=read_only, timeout_s=timeout_s)
    try:
        yield conn
    finally:
        conn.close()


@asynccontextmanager
async def get_db_async(read_only: bool = False) -> AsyncGenerator[duckdb.DuckDBPyConnection, None]:
    """Async wrapper around get_db() using asyncio.to_thread.

    DuckDB's Python API is synchronous. This wrapper runs the connection
    lifecycle in a thread pool to avoid blocking the async event loop.

    Args:
        read_only: If True, open connection in read-only mode.

    Yields:
        DuckDB connection instance (running in executor thread).
    """
    import asyncio

    loop = asyncio.get_running_loop()
    conn: duckdb.DuckDBPyConnection = await loop.run_in_executor(
        None, lambda: duckdb.connect(settings.core.duckdb_path, read_only=read_only)
    )
    try:
        yield conn
    finally:
        await loop.run_in_executor(None, conn.close)


# Symbol metadata for multi-asset class tracking
SYMBOL_METADATA_DDL = """
CREATE TABLE IF NOT EXISTS symbol_metadata (
    symbol VARCHAR PRIMARY KEY,
    asset_class VARCHAR NOT NULL,
    exchange VARCHAR,
    tv_ticker VARCHAR,
    timezone VARCHAR DEFAULT 'UTC',
    active BOOLEAN DEFAULT true,
    added_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
"""

# Ingestion health tracking for the /health/ingestion endpoint
INGESTION_HEALTH_DDL = """
CREATE TABLE IF NOT EXISTS ingestion_health (
    id INTEGER PRIMARY KEY,
    last_successful_run TIMESTAMPTZ,
    last_run_duration_ms DOUBLE,
    symbols_processed INTEGER DEFAULT 0,
    candles_written INTEGER DEFAULT 0,
    error_rate DOUBLE DEFAULT 0.0,
    circuit_breaker_state VARCHAR DEFAULT 'CLOSED',
    is_running BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
"""


# Indicator cache table (tall format — one row per indicator value per timestamp per symbol)
INDICATOR_VALUES_DDL = """
CREATE TABLE IF NOT EXISTS indicator_values (
    symbol VARCHAR,
    timestamp TIMESTAMPTZ,
    indicator_name VARCHAR,
    value DOUBLE,
    timeframe VARCHAR,
    params VARCHAR,
    computed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_iv_lookup ON indicator_values (symbol, indicator_name, timeframe, timestamp);
CREATE INDEX IF NOT EXISTS idx_iv_scan ON indicator_values (indicator_name, timeframe, timestamp DESC);
"""

# Optional wide snapshot for screening performance (created on demand)
INDICATOR_SNAPSHOT_DDL = """
CREATE TABLE IF NOT EXISTS indicator_snapshot (
    symbol VARCHAR,
    timestamp TIMESTAMPTZ,
    timeframe VARCHAR DEFAULT '1D',
    rsi_14 DOUBLE,
    macd_line DOUBLE,
    macd_signal DOUBLE,
    macd_hist DOUBLE,
    ema_20 DOUBLE,
    ema_50 DOUBLE,
    ema_200 DOUBLE,
    sma_50 DOUBLE,
    sma_200 DOUBLE,
    atr_14 DOUBLE,
    obv DOUBLE,
    vwap DOUBLE,
    bb_lower_20 DOUBLE,
    bb_middle_20 DOUBLE,
    bb_upper_20 DOUBLE,
    stoch_k_14 DOUBLE,
    stoch_d_14 DOUBLE,
    adx_14 DOUBLE,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_is_scan ON indicator_snapshot (timeframe, symbol);
"""


# Backtest results tables
BACKTEST_RESULTS_DDL = """
CREATE TABLE IF NOT EXISTS backtest_results (
    run_id VARCHAR PRIMARY KEY,
    config_hash VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    timeframe VARCHAR NOT NULL,
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ NOT NULL,
    initial_cash DOUBLE NOT NULL,
    position_sizing VARCHAR NOT NULL,
    metrics_json VARCHAR,
    stats_json VARCHAR,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    duration_ms DOUBLE
);
"""

BACKTEST_TRADES_DDL = """
CREATE TABLE IF NOT EXISTS backtest_trades (
    run_id VARCHAR NOT NULL REFERENCES backtest_results(run_id),
    trade_index INTEGER NOT NULL,
    symbol VARCHAR NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ,
    entry_price DOUBLE NOT NULL,
    exit_price DOUBLE,
    size DOUBLE NOT NULL,
    direction VARCHAR NOT NULL,
    pnl DOUBLE,
    fees DOUBLE DEFAULT 0.0,
    mae DOUBLE,
    mfe DOUBLE,
    hold_duration_bars INTEGER,
    exit_reason VARCHAR,
    signal_metadata_json VARCHAR,
    PRIMARY KEY (run_id, trade_index)
);
"""

BACKTEST_EQUITY_CURVES_DDL = """
CREATE TABLE IF NOT EXISTS backtest_equity_curves (
    run_id VARCHAR NOT NULL REFERENCES backtest_results(run_id),
    timestamp TIMESTAMPTZ NOT NULL,
    equity DOUBLE NOT NULL,
    returns DOUBLE,
    drawdown DOUBLE,
    PRIMARY KEY (run_id, timestamp)
);
"""

BACKTEST_OPTIMIZATION_RESULTS_DDL = """
CREATE TABLE IF NOT EXISTS backtest_optimization_results (
    run_id VARCHAR NOT NULL REFERENCES backtest_results(run_id),
    fold_index INTEGER NOT NULL,
    param_set_index INTEGER NOT NULL,
    params_json VARCHAR NOT NULL,
    in_sample_metrics_json VARCHAR,
    out_of_sample_metrics_json VARCHAR,
    is_selected BOOLEAN DEFAULT false,
    PRIMARY KEY (run_id, fold_index, param_set_index)
);
"""

BACKTEST_MC_RESULTS_DDL = """
CREATE TABLE IF NOT EXISTS backtest_mc_results (
    run_id VARCHAR NOT NULL REFERENCES backtest_results(run_id),
    n_paths INTEGER NOT NULL,
    method VARCHAR NOT NULL,
    final_equity_p5 DOUBLE,
    final_equity_p50 DOUBLE,
    final_equity_mean DOUBLE,
    final_equity_p95 DOUBLE,
    max_drawdown_p50 DOUBLE,
    sharpe_p50 DOUBLE,
    cagr_p50 DOUBLE,
    ruin_probability DOUBLE,
    paths_parquet VARCHAR,
    results_json VARCHAR
);
"""

BACKTEST_OPTIMIZATION_TRIALS_DDL = """
CREATE TABLE IF NOT EXISTS backtest_optimization_trials (
    study_id VARCHAR NOT NULL,
    trial_number INTEGER NOT NULL,
    symbol VARCHAR NOT NULL,
    method VARCHAR NOT NULL,
    params_json VARCHAR NOT NULL,
    objective_values_json VARCHAR,
    is_pareto BOOLEAN DEFAULT false,
    state VARCHAR DEFAULT 'complete',
    duration_ms DOUBLE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (study_id, trial_number)
);
"""

BACKTEST_REGIME_RESULTS_DDL = """
CREATE TABLE IF NOT EXISTS backtest_regime_results (
    run_id VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    regime_label INTEGER NOT NULL,
    regime_name VARCHAR,
    method VARCHAR NOT NULL,
    confidence DOUBLE,
    features_json VARCHAR,
    PRIMARY KEY (run_id, symbol, timestamp)
);
"""

BACKTEST_REPORTS_DDL = """
CREATE TABLE IF NOT EXISTS backtest_reports (
    report_id VARCHAR PRIMARY KEY,
    run_id VARCHAR NOT NULL REFERENCES backtest_results(run_id),
    format VARCHAR NOT NULL,
    template VARCHAR NOT NULL,
    report_path VARCHAR,
    report_data_json VARCHAR,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    size_bytes INTEGER DEFAULT 0
);
"""

BACKTEST_COMPARISON_RESULTS_DDL = """
CREATE TABLE IF NOT EXISTS backtest_comparison_results (
    comparison_id VARCHAR PRIMARY KEY,
    run_ids_json VARCHAR NOT NULL,
    run_labels_json VARCHAR,
    n_strategies INTEGER NOT NULL,
    best_run_id VARCHAR,
    metrics_comparison_json VARCHAR,
    significance_json VARCHAR,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
"""


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

SCREEN_CONFIGS_DDL = """
CREATE TABLE IF NOT EXISTS screen_configs (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR DEFAULT 'default',
    name VARCHAR NOT NULL,
    description VARCHAR DEFAULT '',
    filter_json VARCHAR NOT NULL,
    asset_classes VARCHAR DEFAULT '["equities","crypto"]',
    timeframes VARCHAR DEFAULT '["1D","4h"]',
    tags VARCHAR DEFAULT '[]',
    version INT NOT NULL DEFAULT 1,
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_screen_configs_user ON screen_configs (user_id);
CREATE INDEX IF NOT EXISTS idx_screen_configs_name ON screen_configs (name);
CREATE INDEX IF NOT EXISTS idx_screen_configs_public ON screen_configs (is_public);
"""

SCREEN_VERSIONS_DDL = """
CREATE TABLE IF NOT EXISTS screen_versions (
    id VARCHAR PRIMARY KEY,
    screen_config_id VARCHAR NOT NULL,
    version INT NOT NULL,
    name VARCHAR NOT NULL,
    filter_json VARCHAR NOT NULL,
    asset_classes VARCHAR NOT NULL,
    timeframes VARCHAR NOT NULL,
    tags VARCHAR DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    snapshot_data VARCHAR
);
CREATE INDEX IF NOT EXISTS idx_screen_versions_parent ON screen_versions (screen_config_id, version DESC);
"""

ALERTS_DDL = """
CREATE TABLE IF NOT EXISTS alerts (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR DEFAULT 'default',
    name VARCHAR NOT NULL,
    description VARCHAR DEFAULT '',
    alert_type VARCHAR NOT NULL,
    condition_json VARCHAR NOT NULL,
    symbols VARCHAR DEFAULT '[]',
    timeframes VARCHAR DEFAULT '["1D"]',
    is_active BOOLEAN DEFAULT TRUE,
    cooldown_seconds INT DEFAULT 300,
    last_triggered_at TIMESTAMPTZ,
    trigger_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts (user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts (is_active);
"""

ALERT_HISTORY_DDL = """
CREATE TABLE IF NOT EXISTS alert_history (
    id VARCHAR PRIMARY KEY,
    alert_id VARCHAR NOT NULL,
    symbol VARCHAR,
    triggered_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    condition_matched VARCHAR,
    value_at_trigger DOUBLE,
    threshold DOUBLE,
    dismissed BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_alert_history_alert ON alert_history (alert_id, triggered_at DESC);
"""

SCREEN_REPLAY_RESULTS_DDL = """
CREATE TABLE IF NOT EXISTS screen_replay_results (
    id VARCHAR PRIMARY KEY,
    screen_config_id VARCHAR NOT NULL,
    version INT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    total_days INT NOT NULL,
    avg_match_count DOUBLE,
    max_match_count INT,
    min_match_count INT,
    total_signals INT,
    win_rate DOUBLE,
    avg_return DOUBLE,
    total_return DOUBLE,
    sharpe DOUBLE,
    max_drawdown DOUBLE,
    equity_curve_json VARCHAR,
    match_series_json VARCHAR,
    computed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_replay_screen ON screen_replay_results (screen_config_id, version);
"""


def initialize_database() -> None:
    """Initialize the DuckDB database: create tables and indexes."""
    with get_db() as con:
        con.execute(OHLCV_DDL)
        con.execute(SYMBOL_METADATA_DDL)
        con.execute(INGESTION_HEALTH_DDL)
        con.execute(INDICATOR_VALUES_DDL)
        con.execute(INDICATOR_SNAPSHOT_DDL)
        con.execute(BACKTEST_RESULTS_DDL)
        con.execute(BACKTEST_TRADES_DDL)
        con.execute(BACKTEST_EQUITY_CURVES_DDL)
        con.execute(BACKTEST_OPTIMIZATION_RESULTS_DDL)
        con.execute(BACKTEST_MC_RESULTS_DDL)
        con.execute(BACKTEST_OPTIMIZATION_TRIALS_DDL)
        con.execute(BACKTEST_REGIME_RESULTS_DDL)
        con.execute(BACKTEST_REPORTS_DDL)
        con.execute(BACKTEST_COMPARISON_RESULTS_DDL)
        con.execute(RISK_BETA_DDL)
        con.execute(RISK_CORRELATION_DDL)
        con.execute(RISK_VAR_DDL)
        con.execute(RISK_KELLY_DDL)
        con.execute(RISK_HEDGE_DDL)
        con.execute(SCREEN_CONFIGS_DDL)
        con.execute(SCREEN_VERSIONS_DDL)
        con.execute(ALERTS_DDL)
        con.execute(ALERT_HISTORY_DDL)
        con.execute(SCREEN_REPLAY_RESULTS_DDL)
