"""
Validation Framework — Systematic, rigorous validation for the trading system.

This module provides a unified validation pipeline that replaces ad-hoc testing
with statistically rigorous, regime-aware validation suitable for institutional deployment.

Components:
- WalkForwardValidator: Proper OOS testing with real backtests (anchor/rolling windows)
- MonteCarloValidator: Bootstrap/block-bootstrap with real returns, tail risk
- StressTestValidator: Crisis scenarios, regime breakdowns, tail risk, correlation shock
- PaperTradingValidator: Virtual order execution with realistic fills, slippage, latency
- RegimeValidator: Cross-regime performance validation with regime-transition analysis
- StatisticalValidator: Significance tests, multiple testing correction, confidence intervals
- ValidationOrchestrator: Unified pipeline with pass/fail gates and reporting
"""

from __future__ import annotations

__version__ = "1.0.0"

# Re-export main classes for convenience
from backend.app.infrastructure.validation.walk_forward_validator import WalkForwardValidator
from backend.app.infrastructure.validation.monte_carlo_validator import MonteCarloValidator
from backend.app.infrastructure.validation.stress_test_validator import StressTestValidator
from backend.app.infrastructure.validation.paper_trading_validator import PaperTradingValidator
from backend.app.infrastructure.validation.regime_validator import RegimeValidator
from backend.app.infrastructure.validation.statistical_validator import StatisticalValidator
from backend.app.infrastructure.validation.orchestrator import ValidationOrchestrator

__all__ = [
    "WalkForwardValidator",
    "MonteCarloValidator",
    "StressTestValidator",
    "PaperTradingValidator",
    "RegimeValidator",
    "StatisticalValidator",
    "ValidationOrchestrator",
]