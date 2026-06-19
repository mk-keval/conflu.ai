"""Tests for multi-timeframe broadcasting utilities."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.app.infrastructure.screener.broadcasting import (
    broadcast_timeframe,
    sort_timeframes,
    timeframe_rank,
)


class TestTimeframeRank:
    """Test timeframe ranking and sorting."""

    def test_sort_descending(self) -> None:
        result = sort_timeframes(["1h", "1D", "4h"], descending=True)
        assert result == ["1D", "4h", "1h"]

    def test_sort_ascending(self) -> None:
        result = sort_timeframes(["1D", "4h", "1h"], descending=False)
        assert result == ["1h", "4h", "1D"]

    def test_rank_known(self) -> None:
        assert timeframe_rank("1D") == 8
        assert timeframe_rank("4h") == 6
        assert timeframe_rank("1h") == 4
        assert timeframe_rank("15m") == 2

    def test_rank_unknown_default(self) -> None:
        assert timeframe_rank("unknown") == 5


class TestBroadcastTimeframe:
    """Test broadcast_timeframe forward-fill behavior."""

    def test_forward_fill_basic(self) -> None:
        """Daily values are forward-filled into hourly timestamps."""
        daily = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC"),
            "value": [100.0, 200.0, 300.0],
        })
        hourly = pd.date_range(
            "2024-01-01 00:00", "2024-01-03 23:00", freq="12h", tz="UTC",
        )
        result = broadcast_timeframe(daily, hourly)
        assert len(result) == len(hourly)
        # First 2 entries (Jan 1 00:00, Jan 1 12:00) should be 100.0
        assert result.iloc[0]["value"] == 100.0
        assert result.iloc[1]["value"] == 100.0
        # Next 2 (Jan 2 00:00, Jan 2 12:00) should be 200.0
        assert result.iloc[2]["value"] == 200.0
        assert result.iloc[3]["value"] == 200.0

    def test_exact_timestamp_match(self) -> None:
        """When timestamps align exactly, values pass through unchanged."""
        daily = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC"),
            "value": [10.0, 20.0, 30.0],
        })
        # Same timestamps as daily
        result = broadcast_timeframe(daily, daily["timestamp"])
        assert len(result) == 3
        assert result.iloc[1]["value"] == 20.0

    def test_raises_on_non_datetime_index(self) -> None:
        """Raise ValueError when input lacks DatetimeIndex."""
        bad_df = pd.DataFrame({"value": [1.0, 2.0]})
        hourly = pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC")
        with pytest.raises(ValueError, match="DatetimeIndex"):
            broadcast_timeframe(bad_df, hourly)

    def test_custom_value_column(self) -> None:
        """Use a custom column name instead of default 'value'."""
        daily = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=2, freq="D", tz="UTC"),
            "price": [50.0, 60.0],
        })
        hourly = pd.date_range("2024-01-01 00:00", periods=4, freq="12h", tz="UTC")
        result = broadcast_timeframe(daily, hourly, value_column="price")
        assert "value" not in result.columns  # Default column name not used
        # Reindexed columns get the value_column name as column header

    def test_broadcast_empty_higher_tf(self) -> None:
        """Empty higher timeframe produces empty result (all NaN)."""
        daily = pd.DataFrame({
            "timestamp": pd.Series([], dtype="datetime64[ns, UTC]"),
            "value": pd.Series([], dtype="float64"),
        })
        hourly = pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC")
        result = broadcast_timeframe(daily, hourly)
        assert result.isna().all().all()
