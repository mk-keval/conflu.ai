"""Incremental Parquet writer with dedup and idempotency."""

from __future__ import annotations

from datetime import UTC, datetime

import duckdb
import pandas as pd

from backend.app.core.database import get_db, partition_path
from backend.app.core.logging import get_logger
from backend.app.infrastructure.ingest.quality import QualityReport, validate_ohlcv

log = get_logger("conflu.ingest.writer")


def write_incremental(
    df: pd.DataFrame,
    asset_class: str,
    timeframe: str,
) -> tuple[int, int, QualityReport]:
    """Append new candles to Parquet partitions, returning (new_rows, bytes_written, quality_report).

    Steps:
    1. Validate OHLCV data quality
    2. Ensure symbol column exists (extract from ticker if needed)
    3. Group by symbol, year, month
    4. For each group: check existing max timestamp, append only new rows
    5. Write to Parquet via DuckDB COPY with deterministic ordering
    6. Track bytes written from file sizes

    Idempotent: re-running with same data produces identical results.
    """
    if df.empty:
        return 0, 0, QualityReport()

    # 1. Validate
    clean_df, quality_report = validate_ohlcv(df)
    if clean_df.empty:
        log.warning(
            "write_no_valid_rows",
            asset_class=asset_class,
            timeframe=timeframe,
            total_rows=len(df),
        )
        return 0, 0, quality_report

    # 2. Ensure symbol, timestamp, timeframe columns
    if "symbol" not in clean_df.columns and "ticker" in clean_df.columns:
        clean_df["symbol"] = clean_df["ticker"].apply(lambda t: str(t).split(":")[-1] if ":" in str(t) else str(t))

    if "timeframe" not in clean_df.columns:
        clean_df["timeframe"] = timeframe

    # 3. Parse timestamps and add partition columns
    # Handle both 'timestamp' and 'time' (Unix timestamp from TV)
    if "timestamp" in clean_df.columns:
        ts_col = clean_df["timestamp"]
    elif "time" in clean_df.columns:
        ts_col = pd.to_datetime(clean_df["time"], unit="s", utc=True)
        clean_df["timestamp"] = ts_col
    else:
        raise ValueError("No timestamp/time column found in data")

    if not pd.api.types.is_datetime64_any_dtype(ts_col):
        ts_col = pd.to_datetime(ts_col, utc=True)
    clean_df["year"] = ts_col.dt.year.astype(int)
    clean_df["month"] = ts_col.dt.month.astype(int)

    # 4. Group by (symbol, year, month) for partition writes
    total_new = 0
    total_bytes = 0

    with get_db() as con:
        for (symbol, year, month), group_df in clean_df.groupby(["symbol", "year", "month"], sort=False):
            symbol_norm = str(symbol)
            group_df = group_df.copy()

            # Ensure asset_class column exists
            if "asset_class" not in group_df.columns:
                group_df["asset_class"] = asset_class

            # Reorder columns to match ohlcv table schema: symbol, timestamp, open, high, low, close, volume, timeframe, asset_class, year, month
            ohlcv_order = [
                "symbol",
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "timeframe",
                "asset_class",
                "year",
                "month",
            ]
            group_df = group_df[[c for c in ohlcv_order if c in group_df.columns]]

            # 5. Check existing max timestamp for this (symbol, timeframe)
            existing_max = con.sql(
                "SELECT MAX(timestamp) FROM ohlcv WHERE symbol = ? AND timeframe = ?",
                params=[symbol_norm, timeframe],
            ).fetchone()[0]

            if existing_max is not None:
                # Filter to only rows with timestamp > existing max
                group_df = group_df[group_df["timestamp"] > existing_max]

            if group_df.empty:
                continue

            # 6. Determine partition file path
            year_int = int(year)
            month_int = int(month)
            parquet_path = partition_path(
                asset_class=asset_class,
                year=year_int,
                month=month_int,
                symbol=symbol_norm,
                timeframe=timeframe,
            )
            parquet_path.parent.mkdir(parents=True, exist_ok=True)

            # 7. Write to Parquet via DuckDB COPY
            con.execute("CREATE TEMP TABLE IF NOT EXISTS _write_staging AS SELECT * FROM ohlcv WHERE 1=0")
            con.execute("DELETE FROM _write_staging")

            # Insert the new rows into staging
            con.execute(
                "INSERT INTO _write_staging SELECT * FROM group_df",
            )

            # Append to main table
            con.execute(
                "INSERT INTO ohlcv SELECT * FROM _write_staging",
            )

            # Write partition file with deterministic ordering
            con.execute(
                f"""
                COPY (
                    SELECT * FROM _write_staging
                    ORDER BY symbol, timestamp
                ) TO '{parquet_path}' (FORMAT PARQUET)
                """
            )

            con.execute("DROP TABLE IF EXISTS _write_staging")

            new_count = len(group_df)
            total_new += new_count
            total_bytes += parquet_path.stat().st_size if parquet_path.exists() else 0

            log.info(
                "partition_written",
                symbol=symbol_norm,
                asset_class=asset_class,
                timeframe=timeframe,
                year=year_int,
                month=month_int,
                new_rows=new_count,
                path=str(parquet_path),
            )

    return total_new, total_bytes, quality_report


def write_incremental_multi(
    df: pd.DataFrame,
    asset_class: str,
) -> dict[str, tuple[int, int, QualityReport]]:
    """Write data for multiple timeframes in one DataFrame.

    Iterates over unique timeframes and calls write_incremental() per timeframe.
    Returns dict of {asset_class/timeframe: (new_rows, bytes_written, quality_report)}.
    """
    if df.empty:
        return {}

    timeframes = df["timeframe"].unique() if "timeframe" in df.columns else ["1D"]
    results: dict[str, tuple[int, int, QualityReport]] = {}

    for tf in timeframes:
        tf_df = df[df["timeframe"] == tf] if "timeframe" in df.columns else df
        new_rows, bytes_written, quality_report = write_incremental(tf_df, asset_class, tf)
        key = f"{asset_class}/{tf}"
        results[key] = (new_rows, bytes_written, quality_report)

    return results


def update_symbol_metadata(con: duckdb.DuckDBPyConnection, symbols: list[dict]) -> None:
    """Upsert symbols into symbol_metadata table.

    Args:
        con: DuckDB connection.
        symbols: List of dicts with keys: symbol, asset_class, exchange, tv_ticker, timezone.
    """
    now = datetime.now(UTC)
    for sym in symbols:
        con.execute(
            """
            INSERT INTO symbol_metadata (symbol, asset_class, exchange, tv_ticker, timezone, active, last_seen_at)
            VALUES (?, ?, ?, ?, ?, true, ?)
            ON CONFLICT (symbol) DO UPDATE SET
                last_seen_at = EXCLUDED.last_seen_at,
                active = true
            """,
            [
                sym.get("symbol"),
                sym.get("asset_class", ""),
                sym.get("exchange", ""),
                sym.get("tv_ticker", ""),
                sym.get("timezone", "UTC"),
                now,
            ],
        )
