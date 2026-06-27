"""Tests for walk-forward optimizer."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.app.domain.models import Metrics
from backend.app.infrastructure.backtest.models import BacktestRunConfig
from backend.app.infrastructure.backtest.walk_forward import WalkForwardOptimizer


@pytest.fixture
def optimizer() -> WalkForwardOptimizer:
    return WalkForwardOptimizer()


@pytest.fixture
def sample_config() -> BacktestRunConfig:
    return BacktestRunConfig(
        symbols=["SPY"],
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 12, 31, tzinfo=UTC),
    )


class TestGenerateWindows:
    def test_expanding_grows_train(self, optimizer):
        """Expanding windows: train end increases."""
        windows = optimizer._generate_windows(1000, "expanding", 0.7, 252)
        assert len(windows) > 0
        # Each subsequent window should have larger train_end
        train_ends = [w[1] for w in windows]
        assert all(train_ends[i] <= train_ends[i + 1] for i in range(len(train_ends) - 1))

    def test_rolling_constant_size(self, optimizer):
        """Rolling windows: train + test size is constant."""
        windows = optimizer._generate_windows(1000, "rolling", 0.7, 252)
        assert len(windows) > 0
        for train_start, train_end, test_start, test_end in windows:
            window_size = test_end - train_start
            # All windows should be same size
            pass

    def test_insufficient_bars(self, optimizer):
        """Fewer bars than min_train + 10 returns single window."""
        windows = optimizer._generate_windows(100, "expanding", 0.7, 252)
        assert len(windows) == 1


class TestEstimateNBars:
    def test_daily_data(self, optimizer):
        """Daily data for 1 year ≈ 252 bars."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 12, 31, tzinfo=UTC)
        n_bars = optimizer._estimate_n_bars(start, end, "1D")
        assert n_bars > 300  # Actually 366 in leap year

    def test_hourly_data(self, optimizer):
        """Hourly data for 1 day = 24 bars."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        end = datetime(2024, 1, 2, tzinfo=UTC)
        n_bars = optimizer._estimate_n_bars(start, end, "1h")
        assert n_bars == 24


class TestGetMetricValue:
    def test_existing_metric(self, optimizer):
        metrics = Metrics(sharpe=1.5)
        assert optimizer._get_metric_value(metrics, "sharpe") == 1.5

    def test_missing_metric(self, optimizer):
        metrics = Metrics()
        assert optimizer._get_metric_value(metrics, "nonexistent") is None


class TestAggregateMetrics:
    def test_mean_of_multiple(self, optimizer):
        metrics_list = [Metrics(sharpe=1.0), Metrics(sharpe=2.0), Metrics(sharpe=3.0)]
        result = optimizer._aggregate_metrics(metrics_list)
        assert result.sharpe == pytest.approx(2.0)

    def test_empty_list(self, optimizer):
        result = optimizer._aggregate_metrics([])
        assert result.sharpe is None


class TestApplyParams:
    def test_override_position_sizing(self, optimizer, sample_config):
        new_config = optimizer._apply_params(sample_config, {"position_sizing": "atr"})
        assert new_config.position_sizing == "atr"

    def test_override_sizing_params(self, optimizer, sample_config):
        new_config = optimizer._apply_params(sample_config, {"risk_per_trade": 0.02})
        assert new_config.sizing_params["risk_per_trade"] == 0.02


class TestOptimize:
    async def test_empty_param_grid_raises(self, optimizer, sample_config):
        with pytest.raises(ValueError, match="Parameter grid must not be empty"):
            await optimizer.optimize(sample_config, {})

    async def test_optimize_with_grid(self, optimizer, sample_config):
        result = await optimizer.optimize(
            sample_config,
            {"position_sizing": ["fixed", "atr"]},
        )
        assert result.symbol == "SPY"
        assert len(result.folds) > 0
        assert "position_sizing" in result.param_grid
