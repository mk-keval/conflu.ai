"""Tests for backtest Pydantic models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.app.infrastructure.backtest.models import (
    BacktestRunConfig,
    BacktestRunRecord,
    MCSimulationResult,
    MonteCarloConfig,
    OptimizationConfig,
    OptimizationResult,
    SignalSource,
)


@pytest.fixture
def sample_start() -> datetime:
    return datetime(2024, 1, 1, tzinfo=UTC)


@pytest.fixture
def sample_end() -> datetime:
    return datetime(2024, 12, 31, tzinfo=UTC)


def test_backtest_run_config_required_fields(sample_start, sample_end):
    """BacktestRunConfig requires at minimum symbols, start, end."""
    cfg = BacktestRunConfig(symbols=["SPY"], start=sample_start, end=sample_end)
    assert cfg.symbols == ["SPY"]
    assert cfg.timeframe == "1D"
    assert cfg.position_sizing == "fixed"


def test_fees_slippage_decimal(sample_start, sample_end):
    """10 bps fees -> 0.001 decimal, 5 bps slippage -> 0.0005 decimal."""
    cfg = BacktestRunConfig(symbols=["SPY"], start=sample_start, end=sample_end)
    assert cfg.fees_decimal == 0.001
    assert cfg.slippage_decimal == 0.0005

    cfg2 = BacktestRunConfig(
        symbols=["SPY"],
        start=sample_start,
        end=sample_end,
        fees_bps=20.0,
        slippage_bps=10.0,
    )
    assert cfg2.fees_decimal == 0.002
    assert cfg2.slippage_decimal == 0.001


def test_signal_source_validation(sample_start, sample_end):
    """SignalSource defaults and validation."""
    src = SignalSource()
    assert src.type == "filter_list"

    src2 = SignalSource(type="indicator_crossing", indicator_params={"entry_threshold": 30})
    assert src2.type == "indicator_crossing"


def test_optimization_config_defaults():
    """OptimizationConfig has expected defaults."""
    cfg = OptimizationConfig()
    assert cfg.enabled is False
    assert cfg.method == "expanding"
    assert cfg.train_pct == 0.7
    assert cfg.min_train_bars == 252
    assert cfg.metric == "sharpe"
    assert cfg.param_grid == {}


def test_monte_carlo_config_validation():
    """MonteCarloConfig validates n_paths >= 100."""
    cfg = MonteCarloConfig()
    assert cfg.n_paths >= 100
    assert cfg.method == "bootstrap"
    assert cfg.confidence == 0.95

    with pytest.raises(ValidationError):
        MonteCarloConfig(n_paths=50)


def test_backtest_run_record_serialization():
    """BacktestRunRecord can be created with all fields."""
    now = datetime(2024, 6, 15, tzinfo=UTC)
    record = BacktestRunRecord(
        run_id="test-123",
        config_hash="abc123",
        symbol="SPY",
        timeframe="1D",
        start_date=now,
        end_date=now,
        initial_cash=100000.0,
        position_sizing="fixed",
        trades_count=10,
        total_fees=50.0,
    )
    assert record.run_id == "test-123"
    assert record.trades_count == 10
    assert record.total_fees == 50.0


def test_optimization_result_creation():
    """OptimizationResult can be created with required fields."""
    result = OptimizationResult(
        symbol="SPY",
        param_grid={"position_sizing": ["fixed", "atr"]},
    )
    assert result.symbol == "SPY"
    assert result.optimization_metric == "sharpe"
    assert result.folds == []
    assert result.best_params_overall == {}


def test_mc_simulation_result_creation():
    """MCSimulationResult can be created with all fields."""
    result = MCSimulationResult(
        n_paths=1000,
        method="bootstrap",
        final_equity_p5=50000.0,
        final_equity_p50=110000.0,
        final_equity_mean=115000.0,
        final_equity_p95=200000.0,
        ruin_probability=0.02,
    )
    assert result.n_paths == 1000
    assert result.ruin_probability == 0.02


def test_config_hash_consistency(sample_start, sample_end):
    """Same config should produce same hash (excluding run_id)."""
    cfg1 = BacktestRunConfig(symbols=["SPY"], start=sample_start, end=sample_end)
    cfg2 = BacktestRunConfig(symbols=["SPY"], start=sample_start, end=sample_end)

    import hashlib
    import json

    def get_hash(cfg):
        d = cfg.model_dump(mode="json", exclude={"run_id"})
        return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()

    assert get_hash(cfg1) == get_hash(cfg2)


def test_backtest_run_config_initial_cash_validation(sample_start, sample_end):
    """initial_cash must be positive."""
    with pytest.raises(ValidationError):
        BacktestRunConfig(symbols=["SPY"], start=sample_start, end=sample_end, initial_cash=-100)
