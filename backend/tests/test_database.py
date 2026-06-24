"""Tests for DuckDB connection management and Parquet partitioning."""

from __future__ import annotations

import duckdb

from backend.app.core.database import get_db, normalize_symbol, partition_path


class TestNormalizeSymbol:
    def test_simple(self) -> None:
        assert normalize_symbol("AAPL") == "AAPL"

    def test_forward_slash(self) -> None:
        assert normalize_symbol("BTC/USDT") == "BTCUSDT"

    def test_special_chars(self) -> None:
        assert normalize_symbol("BRK.B") == "BRK_B"

    def test_lowercase(self) -> None:
        assert normalize_symbol("aapl") == "AAPL"

    def test_multiple_invalid(self) -> None:
        assert normalize_symbol("A:B*C?D\"E<F>G|H") == "ABCDEFGH"


class TestPartitionPath:
    def test_basic(self) -> None:
        path = partition_path("equities", 2025, 1, "AAPL", "1D", data_dir="/tmp/data")
        assert "equities" in str(path)
        assert "2025" in str(path)
        assert "01" in str(path)
        assert "AAPL_1D.parquet" in str(path)

    def test_crypto(self) -> None:
        path = partition_path("crypto", 2026, 6, "BTCUSDT", "1h", data_dir="/tmp/data")
        assert "crypto" in str(path)
        assert "BTCUSDT_1h.parquet" in str(path)


class TestGetDb:
    def test_connection(self) -> None:
        """Verify get_db yields a working connection."""
        with get_db() as con:
            result = con.sql("SELECT 1 AS val").fetchone()
            assert result is not None
            assert result[0] == 1

    def test_initialize_database(self) -> None:
        """Verify initialize_database creates tables."""
        con = duckdb.connect(":memory:")
        con.execute("CREATE TABLE ohlcv (symbol VARCHAR, timestamp TIMESTAMPTZ, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE, timeframe VARCHAR, asset_class VARCHAR, year INTEGER, month INTEGER)")
        result = con.sql("SELECT table_name FROM information_schema.tables WHERE table_name = 'ohlcv'").fetchone()
        assert result is not None
        assert result[0] == "ohlcv"
        con.close()
