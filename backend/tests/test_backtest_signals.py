"""Tests for signal adapter."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from backend.app.infrastructure.backtest.models import BacktestRunConfig, SignalSource
from backend.app.infrastructure.backtest.signals import SignalAdapter


@pytest.fixture
def sample_config() -> BacktestRunConfig:
    return BacktestRunConfig(
        symbols=["SPY", "QQQ"],
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 12, 31, tzinfo=UTC),
        signal_source=SignalSource(type="indicator_crossing"),
    )


class TestSignalAdapter:
    async def test_build_signals_returns_tuple_of_three(self, sample_config):
        adapter = SignalAdapter()
        result = await adapter.build_signals(["SPY", "QQQ"], sample_config)
        assert isinstance(result, tuple)
        assert len(result) == 3

    async def test_output_dataframes_correct_shape(self, sample_config):
        adapter = SignalAdapter()
        close, entries, exits = await adapter.build_signals(["SPY", "QQQ"], sample_config)
        assert isinstance(close, pd.DataFrame)
        assert isinstance(entries, pd.DataFrame)
        assert isinstance(exits, pd.DataFrame)
        # All should have same shape
        assert close.shape == entries.shape == exits.shape
        # 366 days in 2024 (leap year) at 1D
        assert close.shape[1] == 2  # 2 symbols

    async def test_indicator_crossing_signal_type(self, sample_config):
        adapter = SignalAdapter()
        close, entries, exits = await adapter.build_signals(["SPY"], sample_config)
        assert close.columns.tolist() == ["SPY"]
        assert entries.columns.tolist() == ["SPY"]
        assert exits.columns.tolist() == ["SPY"]

    async def test_filter_list_delegates_correctly(self, sample_config):
        config = sample_config.model_copy(update={"signal_source": SignalSource(type="filter_list")})
        adapter = SignalAdapter()
        result = await adapter.build_signals(["SPY"], config)
        # filter_list delegates to indicator_crossing in Phase 4
        assert len(result) == 3

    async def test_unknown_source_raises(self, sample_config):
        config = sample_config.model_copy(update={"signal_source": SignalSource(type="screen_config")})
        adapter = SignalAdapter()
        with pytest.raises(NotImplementedError, match="screen_config"):
            await adapter.build_signals(["SPY"], config)
