"""Tests for VaRCalculator — historical, parametric, Monte Carlo VaR/CVaR."""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.stats import norm

from backend.app.infrastructure.risk.var import VaRCalculator


@pytest.fixture
def var_calculator():
    return VaRCalculator()


class TestVaRProperties:
    def test_var_95_lt_var_99(self, var_calculator):
        """Higher confidence → larger VaR"""
        rng = np.random.default_rng(seed=42)
        returns = rng.normal(0, 0.02, 1000)

        var_95 = var_calculator.compute_var("test", returns, method="historical", confidence=0.95)
        var_99 = var_calculator.compute_var("test", returns, method="historical", confidence=0.99)

        assert 0 <= var_95.var <= var_99.var

    def test_cvar_gte_var(self, var_calculator):
        """CVaR (Expected Shortfall) ≥ VaR"""
        rng = np.random.default_rng(seed=42)
        returns = rng.normal(0, 0.02, 1000)

        var_result = var_calculator.compute_var("test", returns, method="historical", confidence=0.95)

        assert var_result.cvar is not None
        assert var_result.cvar >= var_result.var

    def test_parametric_var_approximates_historical_for_normal(self, var_calculator):
        """For normal returns, parametric ≈ historical VaR (large sample)."""
        rng = np.random.default_rng(seed=42)
        returns = rng.normal(0, 0.02, 10000)

        hist = var_calculator.compute_var("test", returns, method="historical", confidence=0.95)
        param = var_calculator.compute_var("test", returns, method="parametric", confidence=0.95)

        assert abs(hist.var - param.var) < 0.005

    def test_time_scaling_sqrt_n(self, var_calculator):
        """VaR_10 = VaR_1 × √10"""
        rng = np.random.default_rng(seed=42)
        returns = rng.normal(0, 0.02, 1000)

        var_1d = var_calculator.compute_var("test", returns, method="historical", confidence=0.95, horizon_days=1)
        var_10d = var_calculator.compute_var("test", returns, method="historical", confidence=0.95, horizon_days=10)

        expected_var_10d = var_calculator._scale_var(var_1d.var, 10)
        assert abs(var_10d.var - expected_var_10d) < 1e-10

    def test_single_position_component_var_equals_portfolio_var(self, var_calculator):
        """With one position, component VaR = portfolio VaR"""
        weights = np.array([1.0])
        cov_matrix = np.array([[0.0004]])  # 0.02^2
        portfolio_var = 0.05

        comp_var, marg_var = var_calculator._decompose_var(weights, cov_matrix, portfolio_var)
        assert abs(float(comp_var[0]) - portfolio_var) < 0.001

    def test_mc_var_non_negative(self, var_calculator):
        """MC VaR should be non-negative."""
        rng = np.random.default_rng(seed=42)
        returns = rng.normal(0, 0.02, 500)

        mc = var_calculator.compute_var("test", returns, method="monte_carlo", confidence=0.95, n_simulations=1000)
        assert mc.var >= 0

    def test_mc_var_99_gt_mc_var_95(self, var_calculator):
        """MC VaR(99%) > MC VaR(95%)"""
        rng = np.random.default_rng(seed=42)
        returns = rng.normal(0, 0.02, 500)

        mc_95 = var_calculator.compute_var("test", returns, method="monte_carlo", confidence=0.95, n_simulations=1000)
        mc_99 = var_calculator.compute_var("test", returns, method="monte_carlo", confidence=0.99, n_simulations=1000)

        assert mc_99.var >= mc_95.var

    def test_empty_returns_returns_zero_var(self, var_calculator):
        """Empty returns should return VaR=0."""
        result = var_calculator.compute_var("test", np.array([]), method="historical", confidence=0.95)
        assert result.var == 0.0
