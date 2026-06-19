"""Risk Management Engine — beta hedging, correlation, VaR/CVaR, Kelly optimization, position sizing.

Provides:
- BetaHedger — Rolling OLS beta computation, hedge ratio, effectiveness tracking
- CorrelationAnalyzer — Rolling Pearson correlation matrix, sector aggregation
- VaRCalculator — Historical, Parametric, Monte Carlo VaR/CVaR
- KellyOptimizer — Kelly fraction from backtest results, max DD validation
- PositionSizingRefiner — Position sizing with correlation, VaR, beta constraints
- RiskEngine — Orchestrator coordinating all risk computations
- RiskStreamManager — WebSocket streaming for real-time risk updates
- RiskReportGenerator — HTML risk report generation
- RiskMetricsComputer — Additional risk-specific metrics
"""

from __future__ import annotations

from backend.app.infrastructure.risk.beta import BetaHedger
from backend.app.infrastructure.risk.correlation import CorrelationAnalyzer
from backend.app.infrastructure.risk.engine import RiskEngine
from backend.app.infrastructure.risk.kelly import KellyOptimizer
from backend.app.infrastructure.risk.metrics import RiskMetricsComputer
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
from backend.app.infrastructure.risk.position_sizing import PositionSizingRefiner
from backend.app.infrastructure.risk.reporting import RiskReportGenerator
from backend.app.infrastructure.risk.streaming import RiskStreamManager
from backend.app.infrastructure.risk.var import VaRCalculator

__all__ = [
    "BetaHedger",
    "CorrelationAnalyzer",
    "VaRCalculator",
    "KellyOptimizer",
    "PositionSizingRefiner",
    "RiskEngine",
    "RiskStreamManager",
    "RiskReportGenerator",
    "RiskMetricsComputer",
    "BetaResult",
    "PortfolioBetaResult",
    "CorrelationResult",
    "VaRResult",
    "KellyRecommendation",
    "HedgeRecommendation",
    "RiskAlert",
    "RiskAssessment",
]
