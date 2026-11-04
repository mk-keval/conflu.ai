"""Shared test fixtures and configurations."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime

import duckdb
import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def synthetic_ohlcv() -> pd.DataFrame:
    """Generate synthetic OHLCV data with known patterns for property testing.

    Produces 1-hour bars for 2024 with a trending price and realistic
    high/low/volume.
    """
    rng = np.random.default_rng(seed=42)
    dates = pd.date_range("2024-01-01", "2024-12-31", freq="1h", tz="UTC")
    n = len(dates)

    close = 100.0 + np.cumsum(rng.normal(0, 0.5, n))
    open_ = close + rng.normal(0, 0.2, n)

    data: dict[str, object] = {
        "symbol": ["TEST"] * n,
        "timestamp": dates,
        "open": open_,
        "high": np.maximum(open_, close) + np.abs(rng.normal(0, 0.2, n)),
        "low": np.minimum(open_, close) - np.abs(rng.normal(0, 0.2, n)),
        "close": close,
        "volume": rng.integers(1000, 10000, n),
        "timeframe": "1h",
        "asset_class": "crypto",
    }
    return pd.DataFrame(data)


@pytest.fixture
def in_memory_db() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Create an in-memory DuckDB database with the OHLCV schema.

    The connection is yielded, then closed after the test completes.
    """
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
    yield con
    con.close()


@pytest.fixture(autouse=True)
def _isolated_journal_db(tmp_path: Path) -> Generator[Path, None, None]:
    """Point the paper-trade journal (D-68) at a per-test SQLite file.

    Tests must never touch ``data/paper_trades.db``; explicit path override
    also disables the store's first-boot CSV import, keeping tests hermetic.
    """
    from backend.app.domain.workflow import journal as journal_mod

    db_path = tmp_path / "paper_trades.db"
    journal_mod.set_db_path(db_path)
    yield db_path
    journal_mod.reset_db_path()


@pytest.fixture
def sample_ohlcv_row() -> dict[str, object]:
    """A single valid OHLCV data point for model construction tests."""
    return {
        "symbol": "AAPL",
        "timestamp": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
        "open": 150.0,
        "high": 152.0,
        "low": 149.0,
        "close": 151.5,
        "volume": 10_000_000,
        "timeframe": "1h",
        "asset_class": "equities",
    }
