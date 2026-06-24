"""Tests for Monte Carlo simulator."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from backend.app.infrastructure.backtest.models import BacktestRunConfig
from backend.app.infrastructure.backtest.monte_carlo import MonteCarloSimulator


@pytest.fixture
def simulator() -> MonteCarloSimulator:
    return MonteCarloSimulator()


@pytest.fixture
def sample_config() -> BacktestRunConfig:
    return BacktestRunConfig(
        symbols=["SPY"],
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 12, 31, tzinfo=UTC),
    )


class TestGenerateSyntheticReturns:
    def test_correct_length(self, simulator):
        returns = simulator._generate_synthetic_returns(100)
        assert len(returns) == 100

    def test_returns_are_numeric(self, simulator):
        returns = simulator._generate_synthetic_returns(100)
        assert np.issubdtype(returns.dtype, np.floating)

    def test_plausible_statistics(self, simulator):
        """Generated returns should have plausible mean and std."""
        returns = simulator._generate_synthetic_returns(2520)
        # Mean should be near 0.08/252 ≈ 0.000317
        assert abs(returns.mean()) < 0.01
        # Std should be near 0.20/sqrt(252) ≈ 0.0126
        assert 0.005 < returns.std() < 0.05


class TestBlockBootstrap:
    def test_correct_shape(self, simulator):
        returns = np.random.default_rng(42).normal(0, 0.01, 1000)
        result = simulator._block_bootstrap(returns, 10, 20, 100)
        assert result.shape == (10, 100)

    def test_different_paths(self, simulator):
        """Different paths should not all be identical."""
        returns = np.random.default_rng(42).normal(0, 0.01, 1000)
        result = simulator._block_bootstrap(returns, 5, 20, 100)
        # At least some paths should differ
        assert not np.allclose(result[0], result[1])


class TestSimulate:
    async def test_simulate_returns_mc_result(self, simulator, sample_config):
        result = await simulator.simulate(sample_config, n_paths=10)
        assert result.n_paths == 10
        assert result.method == "bootstrap"

    async def test_percentiles_ordered(self, simulator, sample_config):
        """p5 < p50 < p95."""
        result = await simulator.simulate(sample_config, n_paths=100)
        if result.final_equity_p5 is not None and result.final_equity_p50 is not None and result.final_equity_p95 is not None:
            assert result.final_equity_p5 <= result.final_equity_p50 <= result.final_equity_p95

    async def test_ruin_probability_range(self, simulator, sample_config):
        """Ruin probability is between 0 and 1."""
        result = await simulator.simulate(sample_config, n_paths=50)
        assert 0.0 <= result.ruin_probability <= 1.0

    async def test_equity_curves_start_at_cash(self, simulator, sample_config):
        """First bar of each path should be initial_cash."""
        result = await simulator.simulate(sample_config, n_paths=10)
        if result.equity_curves is not None and len(result.equity_curves) > 0:
            for path in result.equity_curves:
                assert path[0] == pytest.approx(sample_config.initial_cash, abs=0.01)

    async def test_block_bootstrap_method(self, simulator, sample_config):
        """Block bootstrap method produces results."""
        result = await simulator.simulate(
            sample_config,
            n_paths=10,
            method="block_bootstrap",
            block_size=20,
        )
        assert result.method == "block_bootstrap"
        assert result.n_paths == 10
