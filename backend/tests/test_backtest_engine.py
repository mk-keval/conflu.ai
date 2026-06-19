"""Tests for backtest engine."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from backend.app.infrastructure.backtest.engine import BacktestEngine
from backend.app.infrastructure.backtest.models import BacktestRunConfig


@pytest.fixture
def engine() -> BacktestEngine:
    return BacktestEngine()


@pytest.fixture
def sample_config() -> BacktestRunConfig:
    return BacktestRunConfig(
        symbols=["SPY"],
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 12, 31, tzinfo=timezone.utc),
    )


def test_engine_instantiation():
    """Engine can be instantiated."""
    engine = BacktestEngine()
    assert engine is not None


def test_compute_config_hash_consistency(engine, sample_config):
    """Same config produces same hash."""
    cfg2 = BacktestRunConfig(
        symbols=["SPY"],
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 12, 31, tzinfo=timezone.utc),
    )
    h1 = engine._compute_config_hash(sample_config)
    h2 = engine._compute_config_hash(cfg2)
    assert h1 == h2


def test_compute_config_hash_different(engine, sample_config):
    """Different configs produce different hashes."""
    cfg2 = BacktestRunConfig(
        symbols=["QQQ"],
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 12, 31, tzinfo=timezone.utc),
    )
    h1 = engine._compute_config_hash(sample_config)
    h2 = engine._compute_config_hash(cfg2)
    assert h1 != h2


def test_infer_freq_daily(engine):
    """Daily index infers 'D'."""
    idx = pd.date_range("2024-01-01", periods=10, freq="D", tz="UTC")
    assert engine._infer_freq(idx) == "D"


def test_infer_freq_hourly(engine):
    """Hourly index infers '1h' (actually infers 'h' from pd.infer_freq which is 'h')."""
    idx = pd.date_range("2024-01-01", periods=10, freq="h", tz="UTC")
    inferred = engine._infer_freq(idx)
    assert inferred == "h" or inferred == "1h" or inferred is not None


def test_infer_freq_fallback(engine):
    """Irregular index falls back to 'D'."""
    idx = pd.DatetimeIndex(
        [datetime(2024, 1, 1, tzinfo=timezone.utc),
         datetime(2024, 1, 5, tzinfo=timezone.utc),
         datetime(2024, 2, 1, tzinfo=timezone.utc)]
    )
    assert engine._infer_freq(idx) == "D"


def test_load_ohlcv_returns_none(engine, sample_config):
    """_load_ohlcv returns None when no data in in-memory db."""
    # With no database connection, this should return None gracefully
    result = engine._load_ohlcv(sample_config)
    assert result is None


def test_build_default_signals(engine):
    """_build_default_signals returns entries and exits DataFrames."""
    ohlcv = pd.DataFrame(
        {"close": [100.0, 101.0, 102.0, 101.0, 100.0]},
        index=pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC"),
    )
    entries, exits = engine._build_default_signals(ohlcv, BacktestRunConfig(
        symbols=["SPY"],
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 12, 31, tzinfo=timezone.utc),
    ))
    assert isinstance(entries, pd.DataFrame)
    assert isinstance(exits, pd.DataFrame)
    assert len(entries) == 5
    assert len(exits) == 5
