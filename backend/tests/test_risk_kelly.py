"""Tests for KellyOptimizer — Kelly formula, max DD validation, empty trades."""

from __future__ import annotations

import pytest

from backend.app.infrastructure.risk.kelly import KellyOptimizer


@pytest.fixture
def kelly_optimizer():
    return KellyOptimizer()


class TestKellyFormula:
    def test_known_case_win_rate_06(self, kelly_optimizer):
        """p=0.6, b=1 → f*=0.2"""
        # f* = 0.6 - 0.4/1.0 = 0.2
        f_star = kelly_optimizer._compute_kelly_fraction(0.6, 1.0)
        assert abs(f_star - 0.2) < 0.001

    def test_kelly_clamp_to_zero(self, kelly_optimizer):
        """Bad odds → f* clamped to 0"""
        f_star = kelly_optimizer._compute_kelly_fraction(0.3, 0.5)
        # f* = 0.3 - 0.7/0.5 = 0.3 - 1.4 = -1.1 → clamped to 0
        assert f_star == 0.0

    def test_kelly_property_range(self, kelly_optimizer):
        """0 ≤ f* ≤ 1 for various win rates"""
        for wr in [0.3, 0.5, 0.6, 0.7, 0.8]:
            for ratio in [0.5, 1.0, 2.0, 3.0]:
                f_star = kelly_optimizer._compute_kelly_fraction(wr, ratio)
                assert 0.0 <= f_star <= 1.0, f"f*={f_star} out of range for wr={wr}, ratio={ratio}"

    def test_constrained_kelly_le_full_kelly(self, kelly_optimizer):
        """constrained_kelly ≤ full_kelly"""
        recommendation = kelly_optimizer.optimize_from_backtest(
            trades=[{"pnl": 100}, {"pnl": 200}, {"pnl": -50}, {"pnl": 150}, {"pnl": 300}, {"pnl": -75}, {"pnl": 120}, {"pnl": -30}, {"pnl": 80}, {"pnl": 250}],
        )
        if recommendation.full_kelly is not None and recommendation.constrained_kelly is not None:
            assert recommendation.constrained_kelly <= recommendation.full_kelly

    def test_half_kelly_default(self, kelly_optimizer):
        """With use_half_kelly=True, recommended_kelly ≤ 0.5 × full_kelly"""
        recommendation = kelly_optimizer.optimize_from_backtest(
            trades=[{"pnl": 100}, {"pnl": 200}, {"pnl": 150}, {"pnl": -50}, {"pnl": 120}],
            use_half_kelly=True,
        )
        if recommendation.full_kelly is not None and recommendation.recommended_kelly is not None:
            assert recommendation.recommended_kelly <= recommendation.full_kelly * 0.5 + 0.001  # Allow small rounding


class TestMaxDDValidation:
    def test_d17_formula(self, kelly_optimizer):
        """D-17: max_dd_kelly = 2 × target / (1 + target)"""
        target = 0.25
        expected = 2.0 * target / (1.0 + target)  # = 0.4
        result = kelly_optimizer.validate_kelly_fraction(0.5, 0.3, max_dd_target=target)
        assert abs(result["max_dd_kelly"] - expected) < 0.001
        assert result["constrained_kelly"] <= result["max_dd_kelly"]


class TestEmptyTrades:
    def test_empty_trades_returns_defaults(self, kelly_optimizer):
        """No trades → is_valid=False with default sizing."""
        recommendation = kelly_optimizer.optimize_from_backtest(trades=[])
        assert recommendation.is_valid is False
        assert recommendation.suggested_params["risk_per_trade"] == 0.01
        assert recommendation.suggested_params["kelly_fraction"] == 0.5
