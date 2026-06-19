"""Tests for RiskEngine — initialization, convenience wrappers, structure."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.app.infrastructure.risk.engine import RiskEngine


@pytest.fixture
def risk_engine():
    return RiskEngine()


class TestRiskEngineInit:
    def test_initializes_sub_components(self, risk_engine):
        """RiskEngine initializes all sub-components."""
        assert risk_engine._beta is not None
        assert risk_engine._correlation is not None
        assert risk_engine._var is not None
        assert risk_engine._kelly is not None
        assert risk_engine._sizing is not None


class TestRiskScore:
    def test_risk_score_range(self, risk_engine):
        """Risk score is always 0-100."""
        # Test with no data
        score = risk_engine._compute_risk_score(None, None)
        assert 0 <= score <= 100

    def test_risk_score_lower_is_better(self, risk_engine):
        """Lower VaR → lower risk score."""
        from backend.app.infrastructure.risk.models import VaRResult

        var_low = VaRResult(portfolio_id="test", method="historical", confidence=0.95, var=0.01)
        var_high = VaRResult(portfolio_id="test", method="historical", confidence=0.95, var=0.08)

        score_low = risk_engine._compute_risk_score(var_low, None)
        score_high = risk_engine._compute_risk_score(var_high, None)

        assert score_low < score_high


class TestConvenienceWrappers:
    def test_compute_beta_wrapper(self, risk_engine):
        """compute_beta returns list of dicts."""
        import asyncio
        result = asyncio.run(risk_engine.compute_beta(["AAPL"]))
        assert isinstance(result, list)

    def test_compute_var_wrapper(self, risk_engine):
        """compute_var returns dict."""
        import asyncio
        returns = np.random.default_rng(42).normal(0, 0.02, 100)
        result = asyncio.run(risk_engine.compute_var("test", returns=returns))
        assert isinstance(result, dict)
        assert "var" in result
        assert result["var"] >= 0

    def test_compute_kelly_empty_wrapper(self, risk_engine):
        """compute_kelly returns dict even with no trades."""
        import asyncio
        result = asyncio.run(risk_engine.compute_kelly())
        assert isinstance(result, dict)
        assert result.get("is_valid") is False

    def test_compute_correlation_wrapper(self, risk_engine):
        """compute_correlation returns dict."""
        import asyncio
        result = asyncio.run(risk_engine.compute_correlation(["AAPL", "MSFT"]))
        assert isinstance(result, dict)


class TestAnalyzePortfolio:
    def test_analyze_portfolio_structure(self, risk_engine):
        """analyze_portfolio returns RiskAssessment with correct structure."""
        import asyncio
        assessment = asyncio.run(risk_engine.analyze_portfolio("test", ["AAPL", "MSFT"]))
        assert assessment.portfolio_id == "test"
        assert assessment.risk_score is not None
        assert 0 <= assessment.risk_score <= 100


class TestCheckRiskLimits:
    def test_high_var_generates_alert(self, risk_engine):
        """VaR above threshold generates alert."""
        from backend.app.infrastructure.risk.models import VaRResult

        var_high = VaRResult(portfolio_id="test", method="historical", confidence=0.95, var=0.05)
        alerts = risk_engine._check_risk_limits(var_high, None, None)
        assert len(alerts) >= 1
        assert alerts[0].category == "var"

    def test_high_beta_generates_alert(self, risk_engine):
        """Beta > 1.5 generates alert."""
        from backend.app.infrastructure.risk.models import PortfolioBetaResult

        beta_high = PortfolioBetaResult(portfolio_id="test", benchmark="SPY", weighted_beta=2.0)
        alerts = risk_engine._check_risk_limits(None, beta_high, None)
        assert len(alerts) >= 1
        assert alerts[0].category == "beta"
