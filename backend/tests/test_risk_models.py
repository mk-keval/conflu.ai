"""Tests for risk Pydantic models — frozen enforcement, default values, validation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.app.infrastructure.risk.models import (
    BetaResult,
    CorrelationResult,
    HedgeRecommendation,
    KellyRecommendation,
    PortfolioBetaResult,
    RiskAlert,
    RiskAssessment,
    VaRResult,
)


class TestBetaResult:
    def test_default_creation(self):
        result = BetaResult(symbol="AAPL", benchmark="SPY")
        assert result.symbol == "AAPL"
        assert result.benchmark == "SPY"
        assert result.beta is None
        assert result.window_days == 60
        assert result.n_observations == 0

    def test_full_creation(self):
        result = BetaResult(
            symbol="AAPL",
            benchmark="SPY",
            beta=1.15,
            alpha=0.002,
            r_squared=0.65,
            std_err=0.08,
            p_value=0.001,
            tracking_error=0.12,
            window_days=60,
            n_observations=252,
        )
        assert result.beta == 1.15
        assert result.r_squared == 0.65
        assert result.n_observations == 252

    def test_frozen_enforcement(self):
        result = BetaResult(symbol="AAPL", benchmark="SPY")
        with pytest.raises(ValidationError):
            result.beta = 1.2  # type: ignore[misc]


class TestVaRResult:
    def test_default_creation(self):
        result = VaRResult(portfolio_id="test", method="historical", confidence=0.95, var=0.02)
        assert result.portfolio_id == "test"
        assert result.method == "historical"
        assert result.confidence == 0.95
        assert result.horizon_days == 1
        assert result.var == 0.02

    def test_full_creation(self):
        result = VaRResult(
            portfolio_id="test",
            method="historical",
            confidence=0.99,
            horizon_days=10,
            var=0.05,
            cvar=0.08,
            component_var=[0.02, 0.03],
            marginal_var=[0.15, 0.25],
        )
        assert result.var == 0.05
        assert result.cvar == 0.08
        assert result.component_var == [0.02, 0.03]


class TestKellyRecommendation:
    def test_default_valid(self):
        kelly = KellyRecommendation()
        assert kelly.is_valid is True
        assert kelly.suggested_params["risk_per_trade"] == 0.01
        assert kelly.suggested_params["kelly_fraction"] == 0.5
        assert kelly.asset_class == "unknown"

    def test_invalid_fallback(self):
        kelly = KellyRecommendation(is_valid=False)
        assert kelly.is_valid is False

    def test_full_creation(self):
        kelly = KellyRecommendation(
            backtest_run_id="run_001",
            asset_class="equities",
            win_rate=0.6,
            avg_win_loss_ratio=2.0,
            full_kelly=0.3,
            constrained_kelly=0.25,
            recommended_kelly=0.125,
            is_valid=True,
        )
        assert kelly.win_rate == 0.6
        assert kelly.full_kelly == 0.3
        assert kelly.recommended_kelly == 0.125


class TestRiskAlert:
    def test_warning_creation(self):
        alert = RiskAlert(
            severity="warning",
            category="var",
            message="VaR exceeded threshold",
            current_value=0.06,
            threshold=0.05,
        )
        assert alert.severity == "warning"
        assert alert.category == "var"

    def test_invalid_severity_rejection(self):
        with pytest.raises(ValidationError):
            RiskAlert(severity="invalid", category="var", message="test")  # type: ignore[arg-type]

    def test_invalid_category_rejection(self):
        with pytest.raises(ValidationError):
            RiskAlert(severity="info", category="invalid", message="test")  # type: ignore[arg-type]


class TestRiskAssessment:
    def test_empty_assessment_defaults(self):
        assessment = RiskAssessment(portfolio_id="test")
        assert assessment.portfolio_id == "test"
        assert assessment.alerts == []
        assert assessment.hedge_recommendations == []
        assert assessment.risk_score is None

    def test_full_assessment(self):
        var_95 = VaRResult(portfolio_id="test", method="historical", confidence=0.95, var=0.02)
        assessment = RiskAssessment(
            portfolio_id="test",
            var_95=var_95,
            risk_score=35.5,
            alerts=[RiskAlert(severity="info", category="var", message="test")],
        )
        assert assessment.var_95 is not None
        assert assessment.var_95.var == 0.02
        assert assessment.risk_score == 35.5
        assert len(assessment.alerts) == 1


class TestCorrelationResult:
    def test_simple_matrix_creation(self):
        result = CorrelationResult(
            timestamp=datetime.now(UTC),
            symbols=["AAPL", "MSFT"],
            matrix=[[1.0, 0.85], [0.85, 1.0]],
            diversification_score=0.15,
        )
        assert len(result.symbols) == 2
        assert result.matrix[0][1] == 0.85
        assert result.diversification_score == 0.15


class TestHedgeRecommendation:
    def test_no_hedge_default(self):
        hr = HedgeRecommendation(symbol="AAPL")
        assert hr.recommendation == "none"
        assert hr.beta is None


class TestPortfolioBetaResult:
    def test_empty_portfolio(self):
        result = PortfolioBetaResult(portfolio_id="test", benchmark="SPY")
        assert result.weighted_beta is None
        assert result.symbol_betas == {}
