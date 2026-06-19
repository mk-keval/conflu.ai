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


@contextmanager
def get_db(read_only: bool = False) -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Get a DuckDB connection via context manager.

    DuckDB is embedded — each call creates a new connection to the same database
    file. Multiple read-only connections are safe concurrently. Writes serialize.

    Args:
        read_only: If True, open connection in read-only mode.

    Yields:
        DuckDB connection instance.

    Example:
        with get_db() as con:
            result = con.sql("SELECT COUNT(*) FROM ohlcv")
    """
    db_path = settings.core.duckdb_path
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = duckdb.connect(db_path, read_only=read_only)
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


def initialize_database() -> None:
    """Initialize the DuckDB database: create tables and indexes."""
    with get_db() as con:
        con.execute(OHLCV_DDL)
        con.execute(SYMBOL_METADATA_DDL)
        con.execute(INGESTION_HEALTH_DDL)
        con.execute(INDICATOR_VALUES_DDL)
        con.execute(INDICATOR_SNAPSHOT_DDL)
