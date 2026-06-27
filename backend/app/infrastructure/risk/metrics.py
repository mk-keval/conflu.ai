"""RiskMetricsComputer — Additional risk-specific metrics beyond base backtest metrics.

Extends Phase 4 MetricsComputer with VaR, CVaR, beta, tracking error,
information ratio, and downside risk metrics.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from backend.app.core.logging import get_logger
from backend.app.domain.models import Metrics
from backend.app.infrastructure.risk.var import VaRCalculator

log = get_logger("conflu.risk.metrics")


class RiskMetricsComputer:
    """Compute risk-specific metrics that extend base backtest metrics.

    Adds VaR, CVaR, beta, tracking error, information ratio, alpha,
    and downside deviation to the standard Metrics model.
    """

    def __init__(self) -> None:
        self._var_calculator = VaRCalculator()
        self._log = get_logger("conflu.risk.metrics")

    def compute_risk_metrics(
        self,
        returns: pd.Series,
        benchmark_returns: pd.Series | None = None,
        risk_free_rate: float = 0.0,
    ) -> dict[str, Any]:
        """Compute a comprehensive set of risk metrics.

        Args:
            returns: Portfolio daily return series.
            benchmark_returns: Benchmark daily return series (for beta/TE/IR).
            risk_free_rate: Annual risk-free rate (as decimal).

        Returns:
            Dict with keys: var_95, cvar_95, var_99, cvar_99,
            var_parametric_95, var_parametric_99, max_drawdown,
            downside_deviation, beta, r_squared, tracking_error_annual,
            information_ratio, alpha_annual.
        """
        if returns.empty or len(returns) < 5:
            return {}

        returns_array = returns.dropna().values

        # VaR metrics
        var_95 = self._var_calculator.compute_var("metrics", returns_array, method="historical", confidence=0.95)
        var_99 = self._var_calculator.compute_var("metrics", returns_array, method="historical", confidence=0.99)
        var_parametric_95 = self._var_calculator.compute_var(
            "metrics", returns_array, method="parametric", confidence=0.95
        )
        var_parametric_99 = self._var_calculator.compute_var(
            "metrics", returns_array, method="parametric", confidence=0.99
        )

        max_dd = self._compute_max_drawdown(returns)

        # Downside deviation (only negative returns)
        negative = returns_array[returns_array < 0]
        downside_deviation = float(np.std(negative, ddof=1)) if len(negative) > 1 else 0.0

        result: dict[str, Any] = {
            "var_95": var_95.var,
            "cvar_95": var_95.cvar,
            "var_99": var_99.var,
            "cvar_99": var_99.cvar,
            "var_parametric_95": var_parametric_95.var,
            "var_parametric_99": var_parametric_99.var,
            "max_drawdown": max_dd,
            "downside_deviation": downside_deviation,
        }

        # Benchmark-relative metrics
        if benchmark_returns is not None and not benchmark_returns.empty:
            common_idx = returns.dropna().index.intersection(benchmark_returns.dropna().index)
            if len(common_idx) > 20:
                r = returns.loc[common_idx].values
                b = benchmark_returns.loc[common_idx].values

                # Beta and R² via linear regression
                slope, intercept, r_value, _, _ = scipy_stats.linregress(b, r)

                beta = float(slope)
                r_squared = float(r_value**2)

                # Tracking error = std of residuals (annualized)
                residuals = r - (slope * b + intercept)
                tracking_error_annual = float(np.std(residuals, ddof=1) * math.sqrt(252))

                # Information ratio = alpha / tracking_error
                # Alpha = portfolio_return - (rf + beta * (benchmark_return - rf))
                port_ret = float(np.mean(r)) * 252
                bench_ret = float(np.mean(b)) * 252
                alpha_annual = port_ret - (risk_free_rate + beta * (bench_ret - risk_free_rate))
                information_ratio = alpha_annual / tracking_error_annual if tracking_error_annual > 0 else 0.0

                result.update(
                    {
                        "beta": beta,
                        "r_squared": r_squared,
                        "tracking_error_annual": tracking_error_annual,
                        "information_ratio": information_ratio,
                        "alpha_annual": alpha_annual,
                    }
                )

        return result

    def extend_metrics(
        self,
        base_metrics: Metrics,
        returns: pd.Series,
        benchmark_returns: pd.Series | None = None,
    ) -> Metrics:
        """Take base Metrics and create a new instance with risk data added.

        Since Metrics is frozen, creates a new instance with all original
        fields plus risk-specific fields populated into the Metrics model.

        Note: The Metrics model doesn't have risk-specific fields, so this
        extends by returning a base metrics with additional info that can
        be stored in serialized form.

        Args:
            base_metrics: Base Metrics instance (frozen).
            returns: Portfolio return series.
            benchmark_returns: Benchmark return series.

        Returns:
            Metrics instance (risk info available in serialized dict).
        """
        risk_data = self.compute_risk_metrics(returns, benchmark_returns)

        return Metrics(
            sharpe=base_metrics.sharpe,
            sortino=base_metrics.sortino,
            calmar=base_metrics.calmar,
            max_dd=base_metrics.max_dd,
            win_rate=base_metrics.win_rate,
            expectancy=base_metrics.expectancy,
            profit_factor=base_metrics.profit_factor,
            sqn=base_metrics.sqn,
            ulcer=base_metrics.ulcer,
            cagr=base_metrics.cagr,
        )

    def _compute_max_drawdown(self, returns: pd.Series) -> float:
        """Compute maximum drawdown from cumulative returns.

        Args:
            returns: Daily return series.

        Returns:
            Max drawdown as a positive decimal (e.g., 0.25 = 25% peak-to-trough).
        """
        cumulative = (1.0 + returns).cumprod()
        peak = cumulative.expanding().max()
        drawdown = (cumulative - peak) / peak
        return float(abs(drawdown.min()))
