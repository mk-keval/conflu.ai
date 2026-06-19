"""VaRCalculator — Value at Risk and Conditional VaR computation.

Supports three methods:
- Historical: Empirical percentile of return distribution
- Parametric: Gaussian VaR using mean, std, and norm.ppf
- Monte Carlo: Bootstrap from empirical returns (captures real-market skew/kurtosis)

Also provides Component VaR and Marginal VaR for portfolio decomposition,
and √N time scaling.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np
from scipy.stats import norm as norm_dist

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.infrastructure.risk.models import VaRResult

log = get_logger("conflu.risk.var")


class VaRCalculator:
    """Value at Risk and Conditional VaR computation.

    Supports Historical, Parametric (Gaussian), and Monte Carlo methods.
    Computes VaR, CVaR (Expected Shortfall), component VaR, and marginal VaR.
    """

    def __init__(self) -> None:
        self._default_methods = settings.risk.var_methods
        self._default_confidence_levels = settings.risk.var_confidence_levels
        self._default_horizons = settings.risk.var_horizon_days
        self._n_mc_paths = settings.risk.var_monte_carlo_paths
        self._log = get_logger("conflu.risk.var")

    def compute_var(
        self,
        portfolio_id: str,
        returns: np.ndarray | None = None,
        trade_pnl: np.ndarray | None = None,
        method: str = "historical",
        confidence: float = 0.95,
        horizon_days: int = 1,
        weights: np.ndarray | None = None,
        covariance_matrix: np.ndarray | None = None,
        n_simulations: int | None = None,
    ) -> VaRResult:
        """Compute VaR/CVaR from available data sources.

        Priority: if returns provided, use portfolio-returns VaR.
        If only trade_pnl, use trade-based VaR approximation.

        Args:
            portfolio_id: Portfolio identifier.
            returns: Portfolio daily return series (preferred).
            trade_pnl: Per-trade PnL array (position-level VaR).
            method: VaR method: 'historical', 'parametric', or 'monte_carlo'.
            confidence: Confidence level (e.g., 0.95 for 95% VaR).
            horizon_days: Time horizon in days.
            weights: Position weights for component/marginal VaR.
            covariance_matrix: Covariance matrix for component/marginal VaR.
            n_simulations: Number of MC simulations (overrides default).

        Returns:
            VaRResult with VaR, CVaR, and optional decomposition.
        """
        data = returns if returns is not None else trade_pnl
        if data is None or len(data) == 0:
            return VaRResult(
                portfolio_id=portfolio_id,
                method=method,
                confidence=confidence,
                horizon_days=horizon_days,
                var=0.0,
                computed_at=datetime.now(timezone.utc),
            )

        # Ensure numpy array
        if isinstance(data, (list,)):
            data = np.array(data, dtype=np.float64)

        data = data[~np.isnan(data)]

        if len(data) < 5:
            return VaRResult(
                portfolio_id=portfolio_id,
                method=method,
                confidence=confidence,
                horizon_days=horizon_days,
                var=0.0,
                computed_at=datetime.now(timezone.utc),
            )

        n_sim = n_simulations or self._n_mc_paths

        # Compute 1-day VaR/CVaR
        var_1d, cvar_1d = self._compute_var_1d(data, method, confidence, n_sim)

        # Time scaling (√N rule)
        var = self._scale_var(var_1d, horizon_days)
        cvar = self._scale_var(cvar_1d, horizon_days) if cvar_1d is not None else None

        # Component/Marginal VaR decomposition
        component_var: list[float] | None = None
        marginal_var: list[float] | None = None
        if weights is not None and covariance_matrix is not None and len(weights) > 1:
            comp_var, marg_var = self._decompose_var(weights, covariance_matrix, var)
            component_var = comp_var.tolist()
            marginal_var = marg_var.tolist()

        return VaRResult(
            portfolio_id=portfolio_id,
            method=method,
            confidence=confidence,
            horizon_days=horizon_days,
            var=float(var),
            cvar=float(cvar) if cvar is not None else None,
            component_var=component_var,
            marginal_var=marginal_var,
            n_simulations=n_sim if method == "monte_carlo" else None,
            computed_at=datetime.now(timezone.utc),
        )

    def _compute_var_1d(
        self,
        data: np.ndarray,
        method: str,
        confidence: float,
        n_simulations: int,
    ) -> tuple[float, float | None]:
        """Compute 1-day VaR and CVaR using the specified method.

        Args:
            data: Clean return/PnL array.
            method: 'historical', 'parametric', or 'monte_carlo'.
            confidence: Confidence level.
            n_simulations: MC simulation count.

        Returns:
            Tuple of (var, cvar). Both are positive = expected loss.
        """
        if method == "historical":
            return self._historical_var(data, confidence)
        elif method == "parametric":
            return self._parametric_var(data, confidence)
        elif method == "monte_carlo":
            return self._monte_carlo_var(data, confidence, n_simulations)
        else:
            log.warning("unknown_var_method", method=method)
            return self._historical_var(data, confidence)

    def _historical_var(self, data: np.ndarray, confidence: float) -> tuple[float, float | None]:
        """Historical VaR: empirical percentile of returns.

        VaR = -percentile(returns, 1 - confidence)
        CVaR = average of losses beyond VaR

        Args:
            data: Return/PnL array.
            confidence: Confidence level.

        Returns:
            Tuple of (var, cvar).
        """
        alpha = 1.0 - confidence
        var = float(-np.percentile(data, alpha * 100))

        # CVaR = Expected Shortfall = mean of losses beyond VaR
        threshold = -var
        losses = data[data < threshold]
        cvar = float(-np.mean(losses)) if len(losses) > 0 else var

        return var, cvar

    def _parametric_var(self, data: np.ndarray, confidence: float) -> tuple[float, float | None]:
        """Parametric (Gaussian) VaR.

        VaR = -(mean + z_score × std)
        CVaR = -(mean - std × φ(z) / (1 - confidence))

        Where z_score = norm.ppf(1 - confidence)

        Args:
            data: Return/PnL array.
            confidence: Confidence level.

        Returns:
            Tuple of (var, cvar).
        """
        mu = float(np.mean(data))
        sigma = float(np.std(data, ddof=1))
        alpha = 1.0 - confidence
        z = float(norm_dist.ppf(alpha))

        var = -(mu + z * sigma)

        # CVaR = -(mean - std × φ(z) / (1 - confidence))
        phi_z = float(norm_dist.pdf(z))
        cvar = -(mu - sigma * phi_z / (1.0 - confidence))

        return max(0.0, var), max(0.0, cvar)

    def _monte_carlo_var(
        self,
        data: np.ndarray,
        confidence: float,
        n_simulations: int,
    ) -> tuple[float, float | None]:
        """Monte Carlo VaR via bootstrap from empirical returns.

        Resamples with replacement from historical returns, computes
        the mean return for each simulated path, then computes VaR
        from the distribution of simulated means.

        This captures real-market skew/kurtosis (unlike synthetic lognormal).

        Args:
            data: Historical return array.
            confidence: Confidence level.
            n_simulations: Number of bootstrap simulations.

        Returns:
            Tuple of (var, cvar).
        """
        rng = np.random.default_rng(seed=42)
        n = len(data)
        alpha = 1.0 - confidence

        # Bootstrap: resample with replacement
        indices = rng.integers(0, n, size=(n_simulations, n))
        samples = data[indices]

        # Mean return for each simulation
        simulated_means = samples.mean(axis=1)

        # VaR from simulated distribution
        var = float(-np.percentile(simulated_means, alpha * 100))

        # CVaR = average of losses beyond VaR
        threshold = -var
        losses = simulated_means[simulated_means < threshold]
        cvar = float(-np.mean(losses)) if len(losses) > 0 else var

        return var, cvar

    def _scale_var(self, var_1d: float, horizon_days: int) -> float:
        """Scale VaR from 1-day to N-day horizon using √N rule.

        VaR_N = VaR_1 × √N

        Args:
            var_1d: 1-day VaR value.
            horizon_days: Target horizon in days.

        Returns:
            Scaled VaR for the specified horizon.
        """
        if horizon_days <= 1:
            return var_1d
        return var_1d * math.sqrt(horizon_days)

    def _decompose_var(
        self,
        weights: np.ndarray,
        covariance_matrix: np.ndarray,
        portfolio_var: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Compute Component VaR and Marginal VaR.

        Component VaR = w_i × (Σw)_i / σ_p × VaR_p
        Sum of component VaRs = portfolio VaR (decomposition property).

        Marginal VaR = ∂(VaR) / ∂(w_i) = (Σw)_i / σ_p × VaR_p / σ_p

        Args:
            weights: Position weights (must sum to 1.0).
            covariance_matrix: N×N covariance matrix.
            portfolio_var: Portfolio VaR value.

        Returns:
            Tuple of (component_var, marginal_var) arrays.
        """
        portfolio_std = float(np.sqrt(weights.T @ covariance_matrix @ weights))
        if portfolio_std <= 0:
            return np.zeros_like(weights), np.zeros_like(weights)

        # Marginal contribution: (Σw)_i / σ_p
        marginal_contrib = (covariance_matrix @ weights) / portfolio_std

        # Component VaR: w_i × marginal_contrib / σ_p × VaR_p
        component_var = weights * marginal_contrib / portfolio_std * portfolio_var

        # Marginal VaR: marginal_contrib × VaR_p / σ_p
        marginal_var = marginal_contrib * portfolio_var / portfolio_std

        return component_var, marginal_var
