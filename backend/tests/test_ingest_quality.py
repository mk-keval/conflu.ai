"""Tests for data quality validation — validate_ohlcv."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from backend.app.infrastructure.ingest.quality import (
    QualityReport,
    merge_quality_reports,
    validate_ohlcv,
    validate_ohlcv_strict,
)


@pytest.fixture
def valid_df() -> pd.DataFrame:
    """A valid OHLCV DataFrame."""
    return pd.DataFrame({
        "symbol": ["AAPL", "AAPL"],
        "timestamp": [
            datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
            datetime(2024, 1, 1, 11, 0, tzinfo=UTC),
        ],
        "open": [150.0, 151.0],
        "high": [152.0, 153.0],
        "low": [149.0, 150.0],
        "close": [151.0, 152.0],
        "volume": [10000, 11000],
        "timeframe": ["1h", "1h"],
    })


def test_valid_data_passes(valid_df: pd.DataFrame) -> None:
    """Valid OHLCV DataFrame passes all checks."""
    clean_df, report = validate_ohlcv(valid_df)
    assert report.passed
    assert len(clean_df) == len(valid_df)


def test_high_low_violation() -> None:
    """Rows where high < low are discarded."""
    df = pd.DataFrame({
        "symbol": ["AAPL"],
        "timestamp": [datetime(2024, 1, 1, tzinfo=UTC)],
        "open": [100.0],
        "high": [90.0],  # high < low
        "low": [95.0],
        "close": [92.0],
        "volume": [1000],
    })
    clean_df, report = validate_ohlcv(df)
    assert len(clean_df) == 0
    assert report.ohlc_inconsistencies > 0
    assert not report.passed


def test_ohlc_consistency() -> None:
    """Rows where high < max(open,close) are discarded."""
    df = pd.DataFrame({
        "symbol": ["AAPL"],
        "timestamp": [datetime(2024, 1, 1, tzinfo=UTC)],
        "open": [100.0],
        "high": [99.0],  # high < open
        "low": [95.0],
        "close": [98.0],
        "volume": [1000],
    })
    clean_df, report = validate_ohlcv(df)
    assert len(clean_df) == 0
    assert report.ohlc_inconsistencies > 0


def test_negative_volume() -> None:
    """Rows with volume < 0 are discarded."""
    df = pd.DataFrame({
        "symbol": ["AAPL"],
        "timestamp": [datetime(2024, 1, 1, tzinfo=UTC)],
        "open": [100.0],
        "high": [102.0],
        "low": [99.0],
        "close": [101.0],
        "volume": [-100],  # negative volume
    })
    clean_df, report = validate_ohlcv(df)
    assert len(clean_df) == 0
    assert report.negative_volume > 0
    assert not report.passed


def test_zero_price() -> None:
    """Rows with open=0 are discarded."""
    df = pd.DataFrame({
        "symbol": ["AAPL"],
        "timestamp": [datetime(2024, 1, 1, tzinfo=UTC)],
        "open": [0.0],  # zero price
        "high": [102.0],
        "low": [0.0],  # zero price
        "close": [101.0],
        "volume": [1000],
    })
    clean_df, report = validate_ohlcv(df)
    assert len(clean_df) == 0
    assert report.zero_negative_prices > 0


def test_nan_values(valid_df: pd.DataFrame) -> None:
    """Rows with NaN in any OHLCV column are removed."""
    df = valid_df.copy()
    df.loc[0, "close"] = np.nan
    clean_df, report = validate_ohlcv(df)
    assert len(clean_df) == 1
    assert report.nan_values == 1


def test_duplicate_timestamps() -> None:
    """Duplicate (symbol, timestamp, timeframe) are deduplicated."""
    ts = datetime(2024, 1, 1, tzinfo=UTC)
    df = pd.DataFrame({
        "symbol": ["AAPL", "AAPL"],
        "timestamp": [ts, ts],
        "open": [100.0, 100.0],
        "high": [102.0, 102.0],
        "low": [99.0, 99.0],
        "close": [101.0, 101.0],
        "volume": [1000, 1000],
        "timeframe": ["1h", "1h"],
    })
    clean_df, report = validate_ohlcv(df)
    assert len(clean_df) == 1
    assert report.duplicate_timestamps == 1


def test_empty_dataframe() -> None:
    """Empty DataFrame returns empty with clean report."""
    df = pd.DataFrame()
    clean_df, report = validate_ohlcv(df)
    assert clean_df.empty
    assert report.passed
    assert report.total_rows == 0


def test_ticker_to_symbol() -> None:
    """ticker column is converted to symbol when symbol missing."""
    df = pd.DataFrame({
        "ticker": ["NASDAQ:AAPL"],
        "timestamp": [datetime(2024, 1, 1, tzinfo=UTC)],
        "open": [100.0],
        "high": [102.0],
        "low": [99.0],
        "close": [101.0],
        "volume": [1000],
    })
    clean_df, report = validate_ohlcv(df)
    assert "symbol" in clean_df.columns
    assert clean_df.iloc[0]["symbol"] == "AAPL"


def test_quality_report_counts(valid_df: pd.DataFrame) -> None:
    """Verify report counts match expected discard numbers."""
    df = valid_df.copy()
    df.loc[1, "close"] = np.nan
    df.loc[0, "volume"] = -1
    clean_df, report = validate_ohlcv(df)
    assert report.total_rows == 2
    assert report.rows_discarded > 0


def test_validate_ohlcv_strict_passes(valid_df: pd.DataFrame) -> None:
    """validate_ohlcv_strict passes valid data."""
    clean_df = validate_ohlcv_strict(valid_df)
    assert len(clean_df) == 2


def test_validate_ohlcv_strict_raises() -> None:
    """validate_ohlcv_strict raises ValueError on bad data."""
    df = pd.DataFrame({
        "symbol": ["AAPL"],
        "timestamp": [datetime(2024, 1, 1, tzinfo=UTC)],
        "open": [100.0],
        "high": [99.0],  # high < open
        "low": [95.0],
        "close": [98.0],
        "volume": [1000],
    })
    with pytest.raises(ValueError, match="OHLCV validation failed"):
        validate_ohlcv_strict(df)


def test_merge_quality_reports() -> None:
    """merge_quality_reports aggregates correctly."""
    r1 = QualityReport(total_rows=10, rows_discarded=1, passed=True)
    r2 = QualityReport(total_rows=20, rows_discarded=3, passed=False)
    merged = merge_quality_reports([r1, r2])
    assert merged.total_rows == 30
    assert merged.rows_discarded == 4
    assert not merged.passed
