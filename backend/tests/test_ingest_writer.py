"""Tests for incremental Parquet writer."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import duckdb
import pandas as pd
import pytest

from backend.app.infrastructure.ingest.writer import (
    write_incremental,
    write_incremental_multi,
)


@pytest.fixture
def in_memory_db() -> duckdb.DuckDBPyConnection:
    """Create in-memory DuckDB with ohlcv table."""
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE ohlcv (
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
        )
    """)
    return con


def test_write_incremental_empty() -> None:
    """Empty DataFrame returns (0, 0, report)."""
    new_rows, bytes_written, report = write_incremental(
        pd.DataFrame(), "equities", "1D"
    )
    assert new_rows == 0
    assert bytes_written == 0
    assert report.passed


def test_write_incremental_new_data(in_memory_db: duckdb.DuckDBPyConnection) -> None:
    """Writes new rows to DuckDB."""
    df = pd.DataFrame({
        "symbol": ["AAPL"],
        "timestamp": [datetime(2024, 1, 1, 10, 0, tzinfo=UTC)],
        "open": [150.0],
        "high": [152.0],
        "low": [149.0],
        "close": [151.0],
        "volume": [10000],
        "timeframe": ["1h"],
    })

    with patch("backend.app.infrastructure.ingest.writer.get_db") as mock_db:
        mock_db.return_value.__enter__.return_value = in_memory_db
        new_rows, bytes_written, report = write_incremental(df, "equities", "1h")
        assert new_rows > 0
        assert report.passed


def test_write_incremental_multi(in_memory_db: duckdb.DuckDBPyConnection) -> None:
    """write_incremental_multi processes multiple timeframes."""
    df = pd.DataFrame({
        "symbol": ["AAPL", "AAPL"],
        "timestamp": [
            datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
            datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
        ],
        "open": [150.0, 151.0],
        "high": [152.0, 153.0],
        "low": [149.0, 150.0],
        "close": [151.0, 152.0],
        "volume": [10000, 11000],
        "timeframe": ["1h", "1D"],
    })

    with patch("backend.app.infrastructure.ingest.writer.get_db") as mock_db:
        mock_db.return_value.__enter__.return_value = in_memory_db
        results = write_incremental_multi(df, "equities")
        assert len(results) > 0
        for key, (new_rows, bytes_written, report) in results.items():
            assert key.startswith("equities/")


def test_write_incremental_quality_filter() -> None:
    """Bad quality rows are filtered before write."""
    df = pd.DataFrame({
        "symbol": ["AAPL", "AAPL"],
        "timestamp": [
            datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
            datetime(2024, 1, 1, 11, 0, tzinfo=UTC),
        ],
        "open": [150.0, 0.0],  # second row has zero price
        "high": [152.0, 100.0],
        "low": [149.0, 95.0],
        "close": [151.0, 98.0],
        "volume": [10000, 1000],
        "timeframe": ["1h", "1h"],
    })

    db = duckdb.connect(":memory:")
    db.execute("""
        CREATE TABLE ohlcv (
            symbol VARCHAR, timestamp TIMESTAMPTZ, open DOUBLE, high DOUBLE,
            low DOUBLE, close DOUBLE, volume DOUBLE, timeframe VARCHAR,
            asset_class VARCHAR, year INTEGER, month INTEGER
        )
    """)
    with patch("backend.app.infrastructure.ingest.writer.get_db") as mock_db:
        mock_db.return_value.__enter__.return_value = db
        new_rows, bytes_written, report = write_incremental(df, "equities", "1h")
        # Only the first row should be written (second has zero price)
        assert new_rows <= 1
        assert report.rows_discarded > 0
    db.close()


def test_write_incremental_multi_empty() -> None:
    """write_incremental_multi with empty DataFrame returns empty dict."""
    results = write_incremental_multi(pd.DataFrame(), "equities")
    assert results == {}
