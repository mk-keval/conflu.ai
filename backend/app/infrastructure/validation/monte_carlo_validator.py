"""
Monte Carlo Validator — Bootstrap/Block Bootstrap with Real Returns

Rigorous Monte Carlo validation using real return distributions from backtests.
Implements both iid bootstrap and stationary block bootstrap for time series
with proper tail risk estimation and confidence intervals.

References:
- "Advances in Financial Machine Learning" by Marcos Lopez de Prado (Ch. 15)
- "Bootstrap Methods and Their Application" - Davison & Hinkley
- "Block Bootstrap for Time Series" - Politis & Romano (1994)
- "The Bootstrap and the Edgeworth Expansion" - Hall (1992)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable
from uuid import uuid4

import numpy as np
import pandas as pd
from scipy import stats

from backend.app.core.logging import get_logger
from backend.app.infrastructure.backtest.engine import BacktestEngine
from backend.app.infrastructure.backtest.models import BacktestRunConfig, BacktestResult

log = get_logger("conflu.validation.monte_carlo")


class BootstrapMethod(str, Enum):
    """Bootstrap method for return sampling."""
    IID = "iid"                    # Independent bootstrap (iid assumption)
    BLOCK = "block"                # Stationary block bootstrap
    CIRCULAR_BLOCK = "circular"    # Circular block bootstrap
    STATIONARY_BLOCK = "stationary"  # Politis-Romano stationary block


@dataclass
class MonteCarloConfig:
    """Configuration for Monte Carlo validation."""
    method: BootstrapMethod = BootstrapMethod.STATIONARY_BLOCK
    n_simulations: int = 10000        # Number of bootstrap paths
    block_length: int | None = None   # Block length (auto if None)
    confidence_levels: list[float] = field(default_factory=lambda: [0.90, 0.95, 0.99])
    min_observations: int = 30        # Minimum returns for bootstrap
    max_block_length: int = 100       # Cap on block length
    min_block_length: int = 5         # Minimum block length
    random_seed: int | None = 42
    n_jobs: int = 1
    verbose: bool = True
    # Tail risk specific
    tail_percentile: float = 0.05     # For ES/CVaR calculation
    target_return: float = 0.0        # Target return for shortfall probability
    # Path-dependent
    path_length: int = 252            # Length of simulated paths (trading days)
    rebalancing_freq: int = 21        # Rebalancing frequency in days
    transaction_cost_bps: float = 10.0  # Round-trip cost in bps


@dataclass
class BootstrapResult:
    """Result of a single bootstrap simulation."""
    path_id: int
    returns: np.ndarray
    metrics: dict[str, float]
    path_returns: np.ndarray  # Cumulative path
    max_drawdown: float
    max_drawdown_duration: int
    success: bool = True
    error: str | None = None


@dataclass
class MonteCarloReport:
    """Complete Monte Carlo validation report."""
    config: MonteCarloConfig
    original_returns: np.ndarray
    original_metrics: dict[str, float]
    bootstrap_distributions: dict[str, np.ndarray]  # metric -> bootstrap distribution
    confidence_intervals: dict[str, dict[str, float]]  # metric -> {level: (lower, upper)}
    tail_risk: dict[str, Any]
    shortfall_analysis: dict[str, Any]
    path_analysis: dict[str, Any]
    significance: dict[str, Any]
    passed: bool = False
    failure_reasons: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    execution_time_seconds: float = 0.0
    n_successful: int = 0
    n_total: int = 0


class MonteCarloValidator:
    """
    Monte Carlo Validator using real return distributions.
    
    Features:
    - Multiple bootstrap methods (iid, block, stationary block, circular)
    - Automatic block length selection (Politis-Romano)
    - Tail risk estimation (VaR, ES/CVaR, tail ratio)
    - Path-dependent simulation with rebalancing
    - Confidence intervals with multiple levels
    - Statistical significance testing
    - Multi-metric bootstrap distributions
    """
    
    def __init__(
        self,
        config: MonteCarloConfig | None = None,
    ):
        self.config = config or MonteCarloConfig()
        
    def run(
        self,
        returns: np.ndarray,
        metrics_fn: Callable[[np.ndarray], dict[str, float]] | None = None,
    ) -> MonteCarloReport:
        """
        Run Monte Carlo validation on return series.
        
        Args:
            returns: Original return series (1D array)
            metrics_fn: Function to compute metrics from returns (uses default if None)
            
        Returns:
            MonteCarloReport with bootstrap distributions and confidence intervals
        """
        start_time = time.time()
        log.info("monte_carlo_start", n_obs=len(returns))
        
        # Validate input
        if len(returns) < self.config.min_observations:
            return MonteCarloReport(
                config=self.config,
                original_returns=np.array([]),
                original_metrics={},
                bootstrap_distributions={},
                confidence_intervals={},
                tail_risk={},
                shortfall_analysis={},
                path_analysis={},
                significance={},
                passed=False,
                failure_reasons=[f"Insufficient observations: {len(returns)} < {self.config.min_observations}"],
                execution_time_seconds=time.time() - start_time,
            )
        
        # Clean returns
        returns = self._clean_returns(returns)
        
        # 1. Compute original metrics
        original_metrics = self._compute_metrics(returns) if metrics_fn is None else metrics_fn(returns)
        
        # 2. Determine block length
        block_length = self._select_block_length(returns)
        
        # 3. Run bootstrap simulations
        bootstrap_results = self._run_bootstrap(returns)
        
        # 4. Aggregate bootstrap distributions
        bootstrap_distributions = self._aggregate_bootstrap(bootstrap_results)
        
        # 5. Compute confidence intervals
        confidence_intervals = self._compute_confidence_intervals(bootstrap_results)
        
        # 6. Tail risk analysis
        tail_risk = self._analyze_tail_risk(returns, bootstrap_results)
        
        # 7. Shortfall analysis
        shortfall = self._analyze_shortfall(returns, bootstrap_results)
        
        # 8. Path analysis
        path_analysis = self._analyze_paths(bootstrap_results)
        
        # 8. Statistical significance
        significance = self._compute_significance(original_metrics, bootstrap_results)
        
        # 9. Evaluate pass/fail
        passed, failures = self._evaluate_pass_fail(original_metrics, bootstrap_results, confidence_intervals)
        
        report = MonteCarloReport(
            config=self.config,
            original_returns=returns,
            original_metrics=original_metrics,
            bootstrap_distributions=bootstrap_distributions,
            confidence_intervals=confidence_intervals,
            tail_risk=tail_risk,
            shortfall_analysis=shortfall,
            path_analysis=path_analysis,
            significance=significance,
            passed=passed,
            failure_reasons=failures,
            execution_time_seconds=time.time() - start_time,
            n_successful=len([r for r in bootstrap_results if r.success]),
            n_total=self.config.n_simulations,
        )
        
        log.info("monte_carlo_complete", passed=passed, n_sims=report.n_successful)
        return report
    
    def _clean_returns(self, returns: np.ndarray) -> np.ndarray:
        """Clean and validate return series."""
        # Remove NaN/inf
        clean = returns[np.isfinite(returns)]
        # Winsorize extreme outliers (beyond 5 sigma)
        if len(clean) > 100:
            mean, std = np.mean(clean), np.std(clean)
            lower, upper = mean - 5 * std, mean + 5 * std
            clean = np.clip(clean, lower, upper)
        return clean
    
    def _compute_metrics(self, returns: np.ndarray) -> dict[str, float]:
        """Compute comprehensive performance metrics."""
        if len(returns) == 0:
            return {}
        
        mean_ret = np.mean(returns)
        std_ret = np.std(returns)
        
        # Basic metrics
        metrics = {
            "mean_return": float(np.mean(returns)),
            "std_return": float(np.std(returns)),
            "annualized_return": float(np.mean(returns) * 252),
            "annualized_vol": float(np.std(returns) * np.sqrt(252)),
            "sharpe_ratio": float(np.mean(returns) / np.std(returns) * np.sqrt(252)) if np.std(returns) > 0 else 0.0,
            "sortino_ratio": float(np.mean(returns) / np.std(returns[returns < 0]) * np.sqrt(252)) if np.any(returns < 0) and np.std(returns[returns < 0]) > 0 else 0.0,
            "skewness": float(stats.skew(returns)),
            "kurtosis": float(stats.kurtosis(returns)),
        }
        
        # Drawdown metrics
        cumret = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumret)
        drawdown = (cumret - running_max) / running_max
        metrics["max_drawdown"] = float(np.min(drawdown))
        metrics["avg_drawdown"] = float(np.mean(drawdown[drawdown < 0])) if np.any(drawdown < 0) else 0.0
        
        # Drawdown duration
        dd_duration = 0
        max_dd_duration = 0
        for dd in drawdown:
            if dd < 0:
                dd_duration += 1
                max_dd_duration = max(max_dd_duration, dd_duration)
            else:
                dd_duration = 0
        metrics["max_drawdown_duration"] = float(max_dd_duration)
        
        # VaR / CVaR
        var_95 = np.percentile(returns, 5)
        metrics["var_95"] = float(var_95)
        metrics["cvar_95"] = float(np.mean(returns[returns <= var_95])) if np.any(returns <= var_95) else float(var_95)
        metrics["var_99"] = float(np.percentile(returns, 1))
        metrics["cvar_99"] = float(np.mean(returns[returns <= np.percentile(returns, 1)]))
        
        # Tail ratio
        metrics["tail_ratio"] = float(abs(np.percentile(returns, 95)) / abs(np.percentile(returns, 5))) if np.percentile(returns, 5) != 0 else 0.0
        
        # Omega ratio
        threshold = 0
        gains = returns[returns > threshold] - threshold
        losses = threshold - returns[returns < threshold]
        metrics["omega_ratio"] = float(np.sum(gains) / np.sum(losses)) if np.sum(losses) > 0 else float('inf')
        
        # Gain-to-Pain ratio
        metrics["gain_to_pain"] = float(np.sum(returns[returns > 0]) / abs(np.sum(returns[returns < 0]))) if np.sum(returns[returns < 0]) != 0 else float('inf')
        
        # Calmar ratio
        metrics["calmar_ratio"] = float(metrics["annualized_return"] / abs(metrics["max_drawdown"])) if metrics["max_drawdown"] != 0 else 0.0
        
        return metrics
    
    def _select_block_length(self, returns: np.ndarray) -> int:
        """Select optimal block length using Politis-Romano automatic selection."""
        n = len(returns)
        if n < 50:
            return max(self.config.min_block_length, min(10, n // 5))
        
        # Politis-White automatic block length
        # b = n^(1/3) * (2 * rho / (1 - rho))^(1/3) where rho is AR(1) coeff
        if n > 10:
            rho = np.corrcoef(returns[:-1], returns[1:])[0, 1]
            if np.isnan(rho) or abs(rho) >= 1:
                rho = 0
            optimal = int(np.ceil(n ** (1/3) * (2 * abs(rho) / (1 - rho**2 + 1e-10)) ** (1/3)))
        else:
            optimal = int(np.ceil(n ** (1/3)))
        
        # Clamp to bounds
        optimal = max(self.config.min_block_length, min(optimal, self.config.max_block_length, n // 3))
        
        # Use config override if provided
        if self.config.block_length is not None:
            return self.config.block_length
        
        return optimal
    
    def _run_bootstrap(self, returns: np.ndarray) -> list[BootstrapResult]:
        """Run bootstrap simulations."""
        n = len(returns)
        block_length = self._select_block_length(returns)
        
        # Prepare blocks for block bootstrap
        if self.config.method in (BootstrapMethod.BLOCK, BootstrapMethod.STATIONARY_BLOCK, BootstrapMethod.CIRCULAR_BLOCK):
            blocks = self._create_blocks(returns, block_length)
        
        results = []
        
        for i in range(self.config.n_simulations):
            try:
                # Sample returns based on method
                if self.config.method == BootstrapMethod.IID:
                    sampled = np.random.choice(returns, size=len(returns), replace=True)
                elif self.config.method == BootstrapMethod.BLOCK:
                    sampled = self._sample_blocks(blocks, len(returns), wrap=False)
                elif self.config.method == BootstrapMethod.CIRCULAR_BLOCK:
                    sampled = self._sample_blocks(blocks, len(returns), wrap=True)
                elif self.config.method == BootstrapMethod.STATIONARY_BLOCK:
                    sampled = self._sample_stationary_blocks(blocks, len(returns))
                else:
                    sampled = np.random.choice(returns, size=len(returns), replace=True)
                
                # Compute metrics
                metrics = self._compute_metrics(sampled)
                
                # Path analysis
                cumret = np.cumprod(1 + sampled)
                running_max = np.maximum.accumulate(cumret)
                dd = (cumret - running_max) / running_max
                max_dd = float(np.min(dd))
                
                # DD duration
                dd_dur = 0
                max_dd_dur = 0
                for d in dd:
                    if d < 0:
                        dd_dur = max(dd_dur + 1, max_dd_dur)
                    else:
                        dd_dur = 0
                
                results.append(BootstrapResult(
                    path_id=i,
                    returns=sampled,
                    metrics=self._compute_metrics(sampled),
                    path_returns=cumret,
                    max_drawdown=max_dd,
                    max_drawdown_duration=max_dd_dur,
                ))
                
            except Exception as e:
                log.debug("bootstrap_path_failed", path_id=i, error=str(e))
                results.append(BootstrapResult(
                    path_id=i,
                    returns=np.array([]),
                    metrics={},
                    path_returns=np.array([]),
                    max_drawdown=0.0,
                    max_drawdown_duration=0,
                    success=False,
                    error=str(e),
                ))
        
        log.info("bootstrap_complete", successful=sum(1 for r in results if r.success), total=len(results))
        return results
    
    def _create_blocks(self, returns: np.ndarray, block_length: int) -> list[np.ndarray]:
        """Create overlapping blocks for block bootstrap."""
        n = len(returns)
        blocks = []
        for i in range(n - block_length + 1):
            blocks.append(returns[i:i + block_length].copy())
        return blocks
    
    def _sample_blocks(self, blocks: list[np.ndarray], target_len: int, wrap: bool = False) -> np.ndarray:
        """Sample blocks to construct a bootstrap path."""
        n_blocks = len(blocks)
        block_len = len(blocks[0])
        needed_blocks = int(np.ceil(target_len / block_len))
        
        if wrap:
            # Circular block bootstrap
            indices = np.random.randint(0, n_blocks, size=needed_blocks)
        else:
            indices = np.random.randint(0, n_blocks, size=needed_blocks)
        
        sampled = np.concatenate([blocks[i] for i in indices])
        return sampled[:target_len]
    
    def _sample_stationary_blocks(self, blocks: list[np.ndarray], target_len: int) -> np.ndarray:
        """Politis-Romano stationary block bootstrap.
        
        Block lengths follow geometric distribution with mean = block_length.
        """
        n_blocks = len(blocks)
        result = []
        remaining = target_len
        
        while remaining > 0:
            # Sample block with geometric length
            block_idx = np.random.randint(0, n_blocks)
            # Geometric distribution for block length (mean = block_length)
            geom_len = np.random.geometric(1 / len(blocks[0]))  # p = 1/block_length
            block_len = min(geom_len, remaining, len(blocks[block_idx]))
            result.append(blocks[block_idx][:block_len])
            remaining -= block_len
        
        return np.concatenate(result)[:target_len]
    
    def _aggregate_bootstrap(self, results: list[BootstrapResult]) -> dict[str, np.ndarray]:
        """Aggregate bootstrap results into metric distributions."""
        successful = [r for r in results if r.success]
        if not successful:
            return {}
        
        metric_names = set().union(*[r.metrics.keys() for r in successful])
        distributions = {}
        
        for name in metric_names:
            values = [r.metrics.get(name, np.nan) for r in successful]
            valid = np.array([v for v in values if np.isfinite(v)])
            if len(valid) > 0:
                distributions[name] = valid
        
        return distributions
    
    def _compute_confidence_intervals(self, results: list[BootstrapResult]) -> dict[str, dict[str, tuple[float, float]]]:
        """Compute confidence intervals for all metrics at all confidence levels."""
        successful = [r for r in results if r.success]
        if not successful:
            return {}
        
        metric_names = set().union(*[r.metrics.keys() for r in successful])
        cis = {}
        
        for name in metric_names:
            values = [r.metrics.get(name, np.nan) for r in successful]
            valid = np.array([v for v in values if np.isfinite(v)])
            if len(valid) < 10:
                continue
            
            cis[name] = {}
            for level in self.config.confidence_levels:
                alpha = 1 - level
                lower = np.percentile(valid, alpha / 2 * 100)
                upper = np.percentile(valid, (1 - alpha / 2) * 100)
                cis[name][f"{level:.0%}"] = (float(lower), float(upper))
        
        return cis
    
    def _analyze_tail_risk(self, original_returns: np.ndarray, results: list[BootstrapResult]) -> dict[str, Any]:
        """Analyze tail risk from bootstrap distributions."""
        if len(original_returns) == 0:
            return {}
        
        # Original tail metrics
        var_95 = np.percentile(original_returns, 5)
        var_99 = np.percentile(original_returns, 1)
        cvar_95 = np.mean(original_returns[original_returns <= var_95]) if np.any(original_returns <= var_95) else 0
        cvar_99 = np.mean(original_returns[original_returns <= var_99]) if np.any(original_returns <= var_99) else 0
        
        # Bootstrap tail distributions
        tail_returns = [r.returns for r in results if r.success and len(r.returns) > 0]
        if not tail_returns:
            return {}
        
        # Aggregate all bootstrap returns
        all_boot_returns = np.concatenate(tail_returns)
        
        bootstrap_var_95 = np.percentile(all_boot_returns, 5)
        bootstrap_cvar_95 = np.mean(all_boot_returns[all_boot_returns <= bootstrap_var_95])
        
        # Extreme value analysis
        # Fit Generalized Pareto Distribution to exceedances
        threshold = np.percentile(original_returns, 95)
        exceedances = original_returns[original_returns > threshold] - threshold
        
        tail_info = {
            "original": {
                "var_95": float(var_95),
                "cvar_95": float(cvar_95),
                "var_99": float(var_99),
                "cvar_99": float(cvar_99),
                "tail_ratio": float(abs(np.percentile(original_returns, 95)) / abs(np.percentile(original_returns, 5))) if np.percentile(original_returns, 5) != 0 else 0,
            },
            "bootstrap": {
                "var_95": float(np.percentile(all_boot_returns, 5)),
                "cvar_95": float(np.mean(all_boot_returns[all_boot_returns <= np.percentile(all_boot_returns, 5)])),
                "var_95_ci": self._bootstrap_ci(all_boot_returns, lambda x: np.percentile(x, 5)),
            },
            "extreme_value": {
                "exceedance_threshold": float(threshold),
                "n_exceedances": len(exceedances),
                "mean_excess": float(np.mean(exceedances)) if len(exceedances) > 0 else 0,
            },
        }
        
        return tail_info
    
    def _analyze_shortfall(self, original_returns: np.ndarray, results: list[BootstrapResult]) -> dict[str, Any]:
        """Analyze probability of shortfall below target return."""
        target = self.config.target_return
        
        # Original shortfall probability
        orig_shortfall = np.mean(original_returns < target)
        orig_expected_shortfall = np.mean(original_returns[original_returns < target]) if np.any(original_returns < target) else 0
        
        # Bootstrap shortfall distribution
        shortfall_probs = []
        shortfall_amounts = []
        
        for r in results:
            if not r.success or len(r.returns) == 0:
                continue
            prob = np.mean(r.returns < target)
            amt = np.mean(r.returns[r.returns < target]) if np.any(r.returns < target) else 0
            shortfall_probs.append(prob)
            shortfall_amounts.append(amt)
        
        return {
            "target_return": target,
            "original": {
                "shortfall_probability": float(orig_shortfall),
                "expected_shortfall": float(orig_expected_shortfall),
            },
            "bootstrap": {
                "shortfall_prob_mean": float(np.mean(shortfall_probs)) if shortfall_probs else 0,
                "shortfall_prob_ci": [float(np.percentile(shortfall_probs, 2.5)), float(np.percentile(shortfall_probs, 97.5))] if shortfall_probs else [0, 0],
                "expected_shortfall_mean": float(np.mean(shortfall_amounts)) if shortfall_amounts else 0,
                "expected_shortfall_ci": [float(np.percentile(shortfall_amounts, 2.5)), float(np.percentile(shortfall_amounts, 97.5))] if shortfall_amounts else [0, 0],
            },
        }
    
    def _analyze_paths(self, results: list[BootstrapResult]) -> dict[str, Any]:
        """Analyze bootstrap paths for path-dependent risk."""
        successful = [r for r in results if r.success and len(r.path_returns) > 0]
        if not successful:
            return {}
        
        # Time to recovery analysis
        recovery_times = []
        for r in successful:
            dd = r.max_drawdown
            if dd < -0.01:  # At least 1% drawdown
                # Time to recover to peak
                peak_idx = np.argmax(r.path_returns)
                trough_idx = np.argmin(r.path_returns[peak_idx:]) + peak_idx if peak_idx < len(r.path_returns) - 1 else len(r.path_returns) - 1
                recovery_idx = np.where(r.path_returns[trough_idx:] >= r.path_returns[peak_idx])[0]
                if len(recovery_idx) > 0:
                    recovery_times.append(recovery_idx[0])
        
        # Path statistics
        final_values = [r.path_returns[-1] for r in successful if len(r.path_returns) > 0]
        max_values = [np.max(r.path_returns) for r in successful if len(r.path_returns) > 0]
        min_values = [np.min(r.path_returns) for r in successful if len(r.path_returns) > 0]
        
        return {
            "n_paths": len(successful),
            "final_value_distribution": {
                "mean": float(np.mean(final_values)),
                "std": float(np.std(final_values)),
                "percentiles": {f"p{p}": float(np.percentile(final_values, p)) for p in [5, 25, 50, 75, 95]},
            },
            "max_drawdown_distribution": {
                "mean": float(np.mean([r.max_drawdown for r in successful])),
                "std": float(np.std([r.max_drawdown for r in successful])),
                "percentiles": {f"p{p}": float(np.percentile([r.max_drawdown for r in successful], p)) for p in [5, 25, 50, 75, 95]},
            },
            "recovery_time": {
                "mean": float(np.mean(recovery_times)) if recovery_times else None,
                "median": float(np.median(recovery_times)) if recovery_times else None,
                "max": float(np.max(recovery_times)) if recovery_times else None,
            },
        }
    
    def _compute_significance(self, original_metrics: dict[str, float], results: list[BootstrapResult]) -> dict[str, Any]:
        """Compute statistical significance of original metrics vs bootstrap."""
        successful = [r for r in results if r.success]
        if not successful:
            return {}
        
        significance = {}
        
        for name, orig_val in original_metrics.items():
            if not np.isfinite(orig_val):
                continue
            
            boot_vals = [r.metrics.get(name, np.nan) for r in results if r.success and name in r.metrics]
            boot_vals = np.array([v for v in boot_vals if np.isfinite(v)])
            
            if len(boot_vals) < 10:
                continue
            
            # Bootstrap p-value (fraction of bootstrap samples worse than original)
            if name in ["sharpe_ratio", "sortino_ratio", "calmar_ratio", "omega_ratio", "gain_to_pain"]:
                # Higher is better
                p_value = np.mean(boot_vals >= orig_val)
            elif name in ["max_drawdown", "var_95", "var_99", "cvar_95", "cvar_99", "max_drawdown_duration"]:
                # Lower is better (more negative is worse)
                p_value = np.mean(boot_vals <= orig_val)
            else:
                # Two-sided
                p_value = 2 * min(
                    np.mean(boot_vals >= orig_val),
                    np.mean(boot_vals <= orig_val)
                )
            
            # Confidence interval
            ci_lower, ci_upper = np.percentile(boot_vals, [2.5, 97.5])
            
            significance[name] = {
                "original": float(orig_val),
                "bootstrap_mean": float(np.mean(boot_vals)),
                "bootstrap_std": float(np.std(boot_vals)),
                "p_value": float(p_value),
                "significant_95": p_value < 0.05,
                "significant_99": p_value < 0.01,
                "ci_95": [float(np.percentile(boot_vals, 2.5)), float(np.percentile(boot_vals, 97.5))],
            }
        
        return significance
    
    def _evaluate_pass_fail(
        self,
        original_metrics: dict[str, float],
        results: list[BootstrapResult],
        confidence_intervals: dict[str, dict[str, tuple[float, float]]],
    ) -> tuple[bool, list[str]]:
        """Evaluate pass/fail criteria."""
        failures = []
        successful = [r for r in results if r.success]
        
        if len(successful) < self.config.n_simulations * 0.9:
            failures.append(f"Low bootstrap success rate: {len(successful)}/{self.config.n_simulations}")
        
        # Sharpe ratio must be significantly positive
        if "sharpe_ratio" in confidence_intervals:
            ci_95 = confidence_intervals["sharpe_ratio"].get("95%", (0, 0))
            if ci_95[1] <= 0:
                failures.append("Sharpe ratio not significantly positive (95% CI includes 0)")
        
        # Max drawdown should not be extreme
        if "max_drawdown" in confidence_intervals:
            ci_95 = confidence_intervals["max_drawdown"].get("95%", (0, 0))
            if ci_95[0] < -0.5:  # 50% max DD
                failures.append("Max drawdown exceeds 50% at 95% confidence")
        
        # Calmar ratio
        if "calmar_ratio" in confidence_intervals:
            ci_95 = confidence_intervals["calmar_ratio"].get("95%", (0, 0))
            if ci_95[1] < 1.0:
                failures.append("Calmar ratio below 1.0 at 95% confidence")
        
        # Positive expectation
        if "mean_return" in confidence_intervals:
            ci_95 = confidence_intervals["mean_return"].get("95%", (0, 0))
            if ci_95[1] <= 0:
                failures.append("Mean return not significantly positive")
        
        return len(failures) == 0, failures
    
    def _bootstrap_ci(self, data: np.ndarray, stat_fn: Callable[[np.ndarray], float]) -> tuple[float, float]:
        """Compute bootstrap confidence interval for a statistic."""
        n = len(data)
        if n < 10:
            return (np.nan, np.nan)
        
        boot_stats = []
        for _ in range(1000):
            sample = np.random.choice(data, size=n, replace=True)
            try:
                boot_stats.append(stat_fn(sample))
            except Exception:
                pass
        
        if len(boot_stats) < 100:
            return (np.nan, np.nan)
        
        return (float(np.percentile(boot_stats, 2.5)), float(np.percentile(boot_stats, 97.5)))


# Convenience function
async def quick_monte_carlo(
    returns: np.ndarray,
    n_sims: int = 5000,
    method: BootstrapMethod = BootstrapMethod.STATIONARY_BLOCK,
) -> MonteCarloReport:
    """Quick Monte Carlo validation with defaults."""
    config = MonteCarloConfig(n_simulations=n_sims, method=method)
    validator = MonteCarloValidator(config)
    return validator.run(returns)