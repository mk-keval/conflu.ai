"""RiskEngine — Orchestrator coordinating all risk computations.

Data flow:
1. Load portfolio returns from DuckDB
2. Run VaR (95%, 99%), beta, and correlation in parallel via asyncio.gather()
3. Check risk limit breaches → generate RiskAlert list
4. Compute composite risk_score (0-100)
5. Return complete RiskAssessment
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.logging import get_logger
from backend.app.infrastructure.risk.beta import BetaHedger
from backend.app.infrastructure.risk.correlation import CorrelationAnalyzer
from backend.app.infrastructure.risk.kelly import KellyOptimizer
from backend.app.infrastructure.risk.models import (
    CorrelationResult,
    PortfolioBetaResult,
    RiskAlert,
    RiskAssessment,
    VaRResult,
)
from backend.app.infrastructure.risk.position_sizing import PositionSizingRefiner
from backend.app.infrastructure.risk.var import VaRCalculator

log = get_logger("conflu.risk.engine")


class RiskEngine:
    """Orchestrator for all risk management computations.

    Coordinates beta, correlation, VaR, Kelly, and position sizing
    components into a unified risk assessment per portfolio.
    """

    def __init__(self) -> None:
        self._beta = BetaHedger()
        self._correlation = CorrelationAnalyzer()
        self._var = VaRCalculator()
        self._kelly = KellyOptimizer()
        self._sizing = PositionSizingRefiner()
        self._log = get_logger("conflu.risk.engine")

    async def analyze_portfolio(
        self,
        portfolio_id: str,
        symbols: list[str],
        positions: dict[str, float] | None = None,
        benchmark: str | None = None,
    ) -> RiskAssessment:
        """Full portfolio risk analysis.

        Runs VaR (95%, 99%), beta, and correlation in parallel,
        then checks risk limits and computes composite score.

        Args:
            portfolio_id: Portfolio identifier.
            symbols: Asset symbols in the portfolio.
            positions: Dict mapping symbol -> market value. If None,
                      equal-weighted positions are assumed.
            benchmark: Benchmark symbol. If None, resolves from config.

        Returns:
            RiskAssessment with all metrics and alerts.
        """
        positions = positions or dict.fromkeys(symbols, 1.0)

        # Load portfolio returns
        portfolio_returns = self._load_portfolio_returns(symbols)

        # Run computations in parallel
        var_95_task = asyncio.to_thread(
            self._var.compute_var,
            portfolio_id,
            returns=portfolio_returns.values if portfolio_returns is not None else None,
            method="historical",
            confidence=0.95,
            horizon_days=1,
        )

        var_99_task = asyncio.to_thread(
            self._var.compute_var,
            portfolio_id,
            returns=portfolio_returns.values if portfolio_returns is not None else None,
            method="historical",
            confidence=0.99,
            horizon_days=1,
        )

        beta_task = asyncio.to_thread(
            self._beta.compute_portfolio_beta,
            portfolio_id,
            positions,
            benchmark,
        )

        corr_task = asyncio.to_thread(
            self._correlation.compute_correlation,
            symbols,
        )

        var_95, var_99, portfolio_beta, correlation = await asyncio.gather(
            var_95_task,
            var_99_task,
            beta_task,
            corr_task,
        )

        # Check risk limits and generate alerts
        alerts = self._check_risk_limits(var_95, portfolio_beta, correlation)

        # Compute composite risk score
        risk_score = self._compute_risk_score(var_95, correlation)

        return RiskAssessment(
            portfolio_id=portfolio_id,
            timestamp=datetime.now(UTC),
            var_95=var_95,
            var_99=var_99,
            portfolio_beta=portfolio_beta,
            correlation=correlation,
            kelly=None,
            hedge_recommendations=[],
            risk_score=risk_score,
            alerts=alerts,
        )

    async def compute_position_size(
        self,
        close: pd.DataFrame,
        entries: pd.DataFrame,
        method: str,
        cash: float,
        params: dict[str, Any] | None = None,
        atr: pd.Series | None = None,
        corr_matrix: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Compute position sizes with risk constraints.

        Delegates to PositionSizingRefiner (not PositionSizer directly).

        Args:
            close: Price DataFrame.
            entries: Entry signal DataFrame.
            method: Sizing method.
            cash: Account equity.
            params: Sizing parameters.
            atr: ATR series.
            corr_matrix: Correlation matrix for correlation limits.

        Returns:
            Constrained position size DataFrame.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self._sizing.compute_size_with_risk_constraints,
            close,
            entries,
            method,
            cash,
            params,
            atr,
            corr_matrix,
        )

    async def compute_beta(
        self,
        symbols: list[str],
        benchmark: str | None = None,
        window: int | None = None,
    ) -> list[dict]:
        """Convenience wrapper around BetaHedger.compute_beta().

        Args:
            symbols: Asset symbols.
            benchmark: Benchmark symbol.
            window: Rolling window.

        Returns:
            List of beta result dicts.
        """
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, self._beta.compute_beta, symbols, benchmark, window)
        return [r.model_dump() for r in results]

    async def compute_correlation(
        self,
        symbols: list[str],
        window: int | None = None,
        group_by: str | None = None,
    ) -> dict:
        """Convenience wrapper around CorrelationAnalyzer.compute_correlation().

        Args:
            symbols: Asset symbols.
            window: Rolling window.
            group_by: Grouping column.

        Returns:
            Correlation result dict.
        """
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, self._correlation.compute_correlation, symbols, window, 15, group_by)
        return result.model_dump()

    async def compute_var(
        self,
        portfolio_id: str,
        returns: np.ndarray | None = None,
        method: str = "historical",
        confidence: float = 0.95,
        horizon: int = 1,
    ) -> dict:
        """Convenience wrapper around VaRCalculator.compute_var().

        Args:
            portfolio_id: Portfolio identifier.
            returns: Return array.
            method: VaR method.
            confidence: Confidence level.
            horizon: Time horizon.

        Returns:
            VaR result dict.
        """
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, self._var.compute_var, portfolio_id, returns, None, method, confidence, horizon
        )
        return result.model_dump()

    async def compute_kelly(
        self,
        backtest_run_id: str | None = None,
        trades: list[dict] | None = None,
        max_dd: float | None = None,
    ) -> dict:
        """Convenience wrapper around KellyOptimizer.optimize_from_backtest().

        Args:
            backtest_run_id: Backtest run ID.
            trades: Trade list.
            max_dd: Max drawdown target.

        Returns:
            Kelly recommendation dict.
        """
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, self._kelly.optimize_from_backtest, backtest_run_id, trades, max_dd)
        return result.model_dump()

    def _load_portfolio_returns(self, symbols: list[str]) -> pd.Series | None:
        """Load equal-weighted portfolio daily returns from DuckDB.

        Args:
            symbols: Portfolio symbols.

        Returns:
            Series of equal-weighted portfolio daily returns, or None.
        """
        try:
            with get_db(read_only=True) as con:
                placeholders = ",".join("?" * len(symbols))
                result = con.sql(
                    f"""
                    SELECT symbol, timestamp, close
                    FROM ohlcv
                    WHERE symbol IN ({placeholders})
                      AND timeframe = '1D'
                    ORDER BY symbol, timestamp
                    """,
                    params=[*symbols],
                ).fetchdf()
        except Exception:
            self._log.exception("Failed to load portfolio returns")
            return None

        if result.empty:
            return None

        # Pivot and compute returns
        pivoted = result.pivot(index="timestamp", columns="symbol", values="close")
        returns = pivoted.pct_change().dropna(how="all")

        # Equal-weighted portfolio returns
        portfolio_returns = returns.mean(axis=1)
        return portfolio_returns

    def _check_risk_limits(
        self,
        var_95: VaRResult | None,
        portfolio_beta: PortfolioBetaResult | None,
        correlation: CorrelationResult | None,
    ) -> list[RiskAlert]:
        """Check all risk limits and generate alerts.

        Args:
            var_95: VaR at 95% confidence.
            portfolio_beta: Portfolio beta.
            correlation: Correlation result.

        Returns:
            List of RiskAlert objects for limit breaches.
        """
        alerts: list[RiskAlert] = []

        # Check VaR limit (max_var_pct from config)
        if var_95 is not None and var_95.var > 0:
            max_var = settings.risk.default_risk_per_trade  # Use as reference
            if var_95.var > max_var * 2:
                alerts.append(
                    RiskAlert(
                        severity="warning",
                        category="var",
                        message=f"VaR(95%) {var_95.var:.2%} exceeds threshold",
                        current_value=var_95.var,
                        threshold=max_var * 2,
                        timestamp=datetime.now(UTC),
                    )
                )

        # Check beta exposure
        if portfolio_beta is not None and portfolio_beta.weighted_beta is not None:
            beta = portfolio_beta.weighted_beta
            if abs(beta) > 1.5:
                alerts.append(
                    RiskAlert(
                        severity="warning",
                        category="beta",
                        message=f"Portfolio beta {beta:.2f} exceeds 1.5",
                        current_value=beta,
                        threshold=1.5,
                        timestamp=datetime.now(UTC),
                    )
                )

        # Check concentration from correlation
        if correlation is not None and correlation.diversification_score is not None:
            if correlation.diversification_score < 0.3:
                alerts.append(
                    RiskAlert(
                        severity="warning",
                        category="correlation",
                        message=f"Low diversification score: {correlation.diversification_score:.2f}",
                        current_value=correlation.diversification_score,
                        threshold=0.3,
                        timestamp=datetime.now(UTC),
                    )
                )

        # Check high-correlation pairs
        if correlation is not None and correlation.high_correlation_pairs:
            for pair in correlation.high_correlation_pairs:
                symbols_str = "-".join(pair.get("symbols", []))
                corr_val = pair.get("correlation", 0)
                if abs(corr_val) > 0.95:
                    alerts.append(
                        RiskAlert(
                            severity="info",
                            category="correlation",
                            message=f"High correlation {symbols_str}: {corr_val:.2f}",
                            symbol=symbols_str,
                            current_value=abs(corr_val),
                            threshold=0.95,
                            timestamp=datetime.now(UTC),
                        )
                    )

        return alerts

    def _compute_risk_score(
        self,
        var_95: VaRResult | None,
        correlation: CorrelationResult | None,
    ) -> float:
        """Compute composite risk score (0-100).

        Components:
        - VaR (40 points): Lower VaR = lower risk
        - Diversification (30 points): Higher diversification = lower risk
        - Beta (30 points): Lower absolute beta = lower risk

        Score interpretation:
        - 0-20: Low risk (good)
        - 21-40: Moderate risk
        - 41-60: Elevated risk
        - 61-80: High risk
        - 81-100: Extreme risk

        Args:
            var_95: VaR at 95%.
            correlation: Correlation result.

        Returns:
            Composite risk score 0-100.
        """
        score = 0.0

        # VaR contribution (40 points)
        if var_95 is not None and var_95.var > 0:
            var_pct = min(var_95.var, 0.10)  # cap at 10%
            score += (var_pct / 0.10) * 40.0

        # Diversification contribution (30 points)
        if correlation is not None and correlation.diversification_score is not None:
            # Lower diversification = higher risk
            div = max(0.0, min(correlation.diversification_score, 1.0))
            score += (1.0 - div) * 30.0

        # Beta contribution (30 points) — use from correlation if available
        score += 15.0  # Default moderate beta risk

        return min(100.0, max(0.0, score))
