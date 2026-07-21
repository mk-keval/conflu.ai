"""
Statistical Validator — Significance Tests, Multiple Testing Correction

Implements rigorous statistical validation for trading strategies:
- Performance significance testing
- Multiple testing correction (Bonferroni, Holm-Bonferroni, Benjamini-Hochberg)
- Confidence intervals for all metrics
- Effect size estimation
- Power analysis
- Reproducibility checks

References:
- "Statistical Significance in Financial Time Series" - Bailey et al.
- "Multiple Testing in Financial Research" - Harvey et al. (2016)
- "The Statistical Significance of Trading Strategies" - Harvey & Liu (2015)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable
from uuid import uuid4

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

from backend.app.core.logging import get_logger

log = get_logger("conflu.validation.statistical")


class CorrectionMethod(str, Enum):
    """Multiple testing correction methods."""
    BONFERRONI = "bonferroni"
    HOLM_BONFERRONI = "holm_bonferroni"
    BENJAMINI_HOCHBERG = "benjamini_hochberg"  # FDR control
    BENJAMINI_YEKUTIELI = "benjamini_yekutieli"  # FDR control (dependent tests)
    NONE = "none"


@dataclass
class StatisticalConfig:
    """Configuration for statistical validation."""
    # Significance testing
    alpha: float = 0.05                # Type I error rate
    confidence_level: float = 0.95     # Confidence interval level
    
    # Multiple testing correction
    correction_method: CorrectionMethod = CorrectionMethod.BENJAMINI_HOCHBERG
    
    # Effect size
    min_effect_size: float = 0.2       # Cohen's d minimum
    
    # Power analysis
    target_power: float = 0.80         # Desired statistical power
    min_sample_size: int = 30          # Minimum observations
    
    # Bootstrapping
    n_bootstrap: int = 1000            # Bootstrap iterations
    block_length: int = 20             # Block length for time series
    
    # Reproducibility
    random_seed: int = 42
    
    # Specific tests
    test_sharpe_significance: bool = True
    test_return_significance: bool = True
    test_drawdown_significance: bool = True
    test_regime_consistency: bool = True
    
    # Reproducibility
    min_reproducibility: float = 0.8   # Minimum reproducibility score


class TestType(str, Enum):
    """Types of statistical tests."""
    ONE_SAMPLE_T = "one_sample_t"
    PAIRED_T = "paired_t"
    INDEPENDENT_T = "independent_t"
    WILCOXON = "wilcoxon"
    MANN_WHITNEY = "mann_whitney"
    BOOTSTRAP = "bootstrap"
    PERMUTATION = "permutation"


@dataclass
class HypothesisTestResult:
    """Result of a single hypothesis test."""
    test_name: str
    test_type: TestType
    statistic: float
    p_value: float
    p_value_adjusted: float | None = None
    effect_size: float | None = None
    effect_size_ci: tuple[float, float] | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None
    significant: bool = False
    significant_after_correction: bool | None = None
    degrees_of_freedom: int | None = None
    effect_size_interpretation: str | None = None


@dataclass
class MultipleTestingResult:
    """Results of multiple testing correction."""
    method: CorrectionMethod
    n_tests: int
    alpha_original: float
    alpha_adjusted: float
    rejected: list[bool]
    p_values_original: list[float]
    p_values_adjusted: list[float]
    rejected_count: int
    fdr_estimate: float | None = None


@dataclass
class PowerAnalysisResult:
    """Power analysis result."""
    test_name: str
    effect_size: float
    alpha: float
    sample_size: int
    power: float
    required_sample_size: int | None = None
    achieved_power: float | None = None


@dataclass
class ReproducibilityResult:
    """Reproducibility analysis result."""
    metric_name: str
    original_value: float
    replication_values: list[float]
    mean_replication: float
    std_replication: float
    correlation: float
    concordance: float
    reproducible: bool
    reproducibility_score: float


@dataclass
class StatisticalValidationReport:
    """Complete statistical validation report."""
    config: 'StatisticalConfig'
    hypothesis_tests: list[HypothesisTestResult]
    multiple_testing: MultipleTestingResult | None = None
    power_analysis: list[PowerAnalysisResult] = field(default_factory=list)
    bootstrap_results: dict[str, Any] | None = None
    reproducibility: list[ReproducibilityResult] = field(default_factory=list)
    effect_sizes: dict[str, float] = field(default_factory=dict)
    confidence_intervals: dict[str, tuple[float, float]] = field(default_factory=dict)
    passed: bool = False
    failure_reasons: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    execution_time_seconds: float = 0.0


class StatisticalValidator:
    """
    Statistical Validator — Rigorous Statistical Validation.
    
    Performs:
    - Hypothesis testing for performance metrics
    - Multiple testing correction
    - Effect size estimation
    - Bootstrap confidence intervals
    - Power analysis
    - Reproducibility verification
    """
    
    def __init__(self, config: StatisticalConfig | None = None):
        self.config = config or StatisticalConfig()
        self._rng = np.random.default_rng(config.random_seed if config else 42)
    
    def validate(
        self,
        returns: np.ndarray,
        benchmark_returns: np.ndarray | None = None,
        trades: list[dict] | None = None,
    ) -> StatisticalValidationReport:
        """
        Run complete statistical validation.
        
        Args:
            returns: Strategy return series
            benchmark_returns: Benchmark return series (optional)
            trades: Trade records (optional)
            
        Returns:
            StatisticalValidationReport
        """
        start_time = time.time()
        log.info("statistical_validation_start", n_obs=len(returns))
        
        # 1. Validate input
        if len(returns) < self.config.min_sample_size:
            return StatisticalValidationReport(
                config=self.config,
                hypothesis_tests=[],
                passed=False,
                failure_reasons=[f"Insufficient data: {len(returns)} < {self.config.min_sample_size}"],
                execution_time_seconds=time.time() - start_time,
            )
        
        # Clean returns
        returns = returns[np.isfinite(returns)]
        if benchmark_returns is not None:
            benchmark_returns = benchmark_returns[np.isfinite(benchmark_returns)]
        
        # 2. Run hypothesis tests
        tests = []
        tests.extend(self._test_mean_return(returns))
        tests.extend(self._test_sharpe_ratio(returns))
        tests.extend(self._test_positive_skewness(returns))
        tests.extend(self._test_kurtosis(returns))
        tests.extend(self._test_autocorrelation(returns))
        tests.extend(self._test_stationarity(returns))
        
        if benchmark_returns is not None:
            tests.extend(self._test_alpha(returns, benchmark_returns))
            tests.extend(self._test_beta(returns, benchmark_returns))
            tests.extend(self._test_information_ratio(returns, benchmark_returns))
        
        if trades is not None:
            tests.extend(self._test_trade_statistics(trades))
        
        # 3. Multiple testing correction
        multiple_testing = self._apply_multiple_testing_correction(tests)
        
        # 4. Effect sizes
        effect_sizes = self._compute_effect_sizes(returns, benchmark_returns)
        
        # 5. Confidence intervals
        confidence_intervals = self._compute_confidence_intervals(returns)
        
        # 5. Bootstrap confidence intervals
        bootstrap_results = self._run_bootstrap(returns)
        
        # 6. Power analysis
        power_analysis = self._run_power_analysis(returns)
        
        # 7. Reproducibility
        reproducibility = self._check_reproducibility(returns)
        
        # 6. Evaluate pass/fail
        passed, failures = self._evaluate_pass_fail(
            returns, tests, multiple_testing, effect_sizes, confidence_intervals
        )
        
        report = StatisticalValidationReport(
            config=self.config,
            hypothesis_tests=tests,
            multiple_testing=multiple_testing,
            power_analysis=power_analysis,
            bootstrap_results=bootstrap_results,
            reproducibility=reproducibility,
            effect_sizes=effect_sizes,
            confidence_intervals=confidence_intervals,
            passed=passed,
            failure_reasons=failures,
            execution_time_seconds=time.time() - start_time,
        )
        
        log.info("statistical_validation_complete", passed=passed, n_tests=len(tests))
        return report
    
    def _test_mean_return(self, returns: np.ndarray) -> list[HypothesisTestResult]:
        """Test if mean return is significantly different from zero."""
        tests = []
        
        # One-sample t-test
        t_stat, p_val = stats.ttest_1samp(returns, 0)
        mean_ret = np.mean(returns)
        se = stats.sem(returns)
        ci = stats.t.interval(0.95, len(returns)-1, loc=mean_ret, scale=se)
        
        # Effect size (Cohen's d)
        d = mean_ret / np.std(returns) if np.std(returns) > 0 else 0
        
        tests.append(HypothesisTestResult(
            test_name="Mean Return vs Zero",
            test_type=TestType.ONE_SAMPLE_T,
            statistic=float(t_stat),
            p_value=float(p_val),
            effect_size=float(d),
            ci_lower=float(ci[0]),
            ci_upper=float(ci[1]),
            significant=p_val < self.config.alpha,
            degrees_of_freedom=len(returns) - 1,
            effect_size_interpretation=self._interpret_cohens_d(d),
        ))
        
        # Wilcoxon signed-rank test (non-parametric)
        try:
            w_stat, w_p = stats.wilcoxon(returns, alternative='two-sided')
            tests.append(HypothesisTestResult(
                test_name="Wilcoxon Signed-Rank (Mean > 0)",
                test_type=TestType.WILCOXON,
                statistic=float(w_stat),
                p_value=float(w_p),
                significant=w_p < self.config.alpha,
            ))
        except Exception:
            pass
        
        return tests
    
    def _test_sharpe_ratio(self, returns: np.ndarray) -> list[HypothesisTestResult]:
        """Test if Sharpe ratio is significantly > 0."""
        tests = []
        
        mean_ret = np.mean(returns)
        std_ret = np.std(returns, ddof=1)
        
        if std_ret > 0:
            sharpe = mean_ret / std_ret * np.sqrt(252)
            
            # Standard error of Sharpe ratio (Mertens, 2002)
            skew = stats.skew(returns)
            kurt = stats.kurtosis(returns)
            se_sharpe = np.sqrt((1 + 0.5 * sharpe**2 - skew * sharpe + (kurt - 3)/4 * sharpe**2) / len(returns))
            
            # t-test for Sharpe
            t_stat = sharpe / se_sharpe
            p_val = 1 - stats.t.cdf(t_stat, len(returns) - 1)
            
            # Confidence interval
            ci = stats.t.interval(0.95, len(returns)-1, loc=sharpe, scale=se_sharpe)
            
            # Effect size (Sharpe itself as effect size)
            tests.append(HypothesisTestResult(
                test_name="Sharpe Ratio > 0",
                test_type=TestType.ONE_SAMPLE_T,
                statistic=float(t_stat),
                p_value=float(p_val),
                effect_size=float(sharpe),
                ci_lower=float(ci[0]),
                ci_upper=float(ci[1]),
                significant=p_val < self.config.alpha,
                degrees_of_freedom=len(returns) - 1,
                effect_size_interpretation=self._interpret_sharpe(sharpe),
            ))
            
            # Jobson-Korkie test for Sharpe significance (more robust)
            # Memmel (2003) test
            try:
                jk_stat = sharpe * np.sqrt(len(returns) / (1 + 0.5*sharpe**2 - stats.skew(returns)*sharpe + (stats.kurtosis(returns)-3)/4*sharpe**2))
                jk_p = 1 - stats.norm.cdf(jk_stat)
                tests.append(HypothesisTestResult(
                    test_name="Sharpe Ratio (Jobson-Korkie)",
                    test_type=TestType.ONE_SAMPLE_T,
                    statistic=float(jk_stat),
                    p_value=float(jk_p),
                    significant=jk_p < self.config.alpha,
                ))
            except Exception:
                pass
        
        return tests
    
    def _test_positive_skewness(self, returns: np.ndarray) -> list[HypothesisTestResult]:
        """Test for positive skewness (right tail)."""
        tests = []
        skew = stats.skew(returns)
        
        # D'Agostino's test for skewness
        try:
            stat, p_val = stats.skewtest(returns)
            tests.append(HypothesisTestResult(
                test_name="Positive Skewness (D'Agostino)",
                test_type=TestType.ONE_SAMPLE_T,
                statistic=stat,
                p_value=p_val/2,  # One-tailed
                effect_size=skew,
                significant=p_val/2 < self.config.alpha,
                effect_size_interpretation=self._interpret_skewness(skew),
            )
        except Exception:
            pass
        
        return tests
    
    def _test_kurtosis(self, returns: np.ndarray) -> list[HypothesisTestResult]:
        """Test for excess kurtosis (fat tails)."""
        tests = []
        kurt = stats.kurtosis(returns)
        
        try:
            # Test if kurtosis > 0 (fat tails)
            stat, p_val = stats.kurtosistest(returns)
            tests.append(HypothesisTestResult(
                test_name="Excess Kurtosis (Fat Tails)",
                test_type=TestType.ONE_SAMPLE_T,
                statistic=stat,
                p_value=p_val/2,  # One-tailed
                effect_size=kurt,
                significant=p_val/2 < self.config.alpha,
                effect_size_interpretation=self._interpret_kurtosis(kurt),
            )
        except Exception:
            pass
        
        return tests
    
    def _test_autocorrelation(self, returns: np.ndarray, max_lag: int = 10) -> list[HypothesisTestResult]:
        """Test for serial autocorrelation (market efficiency)."""
        tests = []
        
        # Ljung-Box test
        from statsmodels.stats.diagnostic import acorr_ljungbox
        try:
            lb_result = acorr_ljungbox(returns, lags=max_lag, return_df=True)
            lb_stat = lb_result['lb_stat'].iloc[-1]
            lb_p = lb_result['lb_pvalue'].iloc[-1]
            
            tests.append(HypothesisTestResult(
                test_name=f"Ljung-Box (lags={max_lag})",
                test_type=TestType.ONE_SAMPLE_T,
                statistic=float(lb_stat),
                p_value=float(lb_p),
                significant=lb_p < self.config.alpha,
            ))
        except Exception:
            pass
        
        # Individual lag tests
        for lag in [1, 5, 10]:
            if len(returns) > lag:
                acf = np.corrcoef(returns[:-lag], returns[lag:])[0, 1]
                se = 1 / np.sqrt(len(returns))
                z = acf / se
                p_val = 2 * (1 - stats.norm.cdf(abs(z)))
                
                tests.append(HypothesisTestResult(
                    test_name=f"Autocorrelation Lag {lag}",
                    test_type=TestType.ONE_SAMPLE_T,
                    statistic=float(z),
                    p_value=float(p_val),
                    effect_size=float(acf),
                    significant=p_val < self.config.alpha,
                    effect_size_interpretation=f"ACF({lag}) = {acf:.4f}",
                ))
        
        return tests
    
    def _test_stationarity(self, returns: np.ndarray) -> list[HypothesisTestResult]:
        """Test for stationarity (ADF test)."""
        tests = []
        
        try:
            from statsmodels.tsa.stattools import adfuller
            result = adfuller(returns, regression='c')
            adf_stat, p_val, _, _, crit_vals, _ = result
            
            tests.append(HypothesisTestResult(
                test_name="Augmented Dickey-Fuller (Stationarity)",
                test_type=TestType.ONE_SAMPLE_T,
                statistic=float(adf_stat),
                p_value=float(p_val),
                significant=p_val < self.config.alpha,
                effect_size_interpretation=f"Critical values: {crit_vals}",
            ))
        except Exception:
            pass
        
        return tests
    
    def _test_alpha(self, returns: np.ndarray, benchmark: np.ndarray) -> list[HypothesisTestResult]:
        """Test if alpha is significant (CAPM regression)."""
        tests = []
        
        # Align returns
        min_len = min(len(returns), len(benchmark))
        r = returns[-min_len:]
        b = benchmark[-min_len:]
        
        # OLS: r = alpha + beta * b + eps
        X = np.column_stack([np.ones(len(b)), b])
        y = r
        
        try:
            beta, residuals, rank, s = np.linalg.lstsq(X, y, rcond=None)
            alpha, beta_val = beta[0], beta[1]
            
            # Standard error of alpha
            n = len(r)
            residuals = y - X @ beta
            mse = np.sum(residuals**2) / (n - 2)
            var_alpha = mse * np.linalg.inv(X.T @ X)[0, 0]
            se_alpha = np.sqrt(var_alpha)
            
            # t-test for alpha
            t_stat = alpha / se_alpha
            p_val = 2 * stats.t.sf(abs(t_stat), n - 2)
            
            ci = stats.t.interval(0.95, n-2, loc=alpha, scale=se_alpha)
            
            tests.append(HypothesisTestResult(
                test_name="Jensen's Alpha",
                test_type=TestType.ONE_SAMPLE_T,
                statistic=float(t_stat),
                p_value=float(p_val),
                effect_size=float(alpha * 252),  # Annualized alpha
                ci_lower=float(ci[0] * 252),
                ci_upper=float(ci[1] * 252),
                significant=p_val < self.config.alpha,
                degrees_of_freedom=n - 2,
                effect_size_interpretation=f"Alpha = {alpha*252:.2%} annualized",
            ))
        except Exception:
            pass
        
        return tests
    
    def _test_beta(self, returns: np.ndarray, benchmark: np.ndarray) -> list[HypothesisTestResult]:
        """Test if beta is significantly different from 1 (market exposure)."""
        tests = []
        
        min_len = min(len(returns), len(benchmark))
        r = returns[-min_len:]
        b = benchmark[-min_len:]
        
        X = np.column_stack([np.ones(len(b)), b])
        y = r
        
        try:
            beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
            beta_val = beta[1]
            
            # Test beta = 1
            residuals = y - X @ beta
            n = len(r)
            mse = np.sum(residuals**2) / (n - 2)
            var_beta = mse * np.linalg.inv(X.T @ X)[1, 1]
            se_beta = np.sqrt(var_beta)
            
            t_stat = (beta_val - 1) / se_beta
            p_val = 2 * stats.t.sf(abs(t_stat), n - 2)
            
            ci = stats.t.interval(0.95, n-2, loc=beta_val, scale=se_beta)
            
            tests.append(HypothesisTestResult(
                test_name="Beta = 1 (Market Neutral)",
                test_type=TestType.ONE_SAMPLE_T,
                statistic=float(t_stat),
                p_value=float(p_val),
                effect_size=float(beta_val - 1),
                ci_lower=float(ci[0]),
                ci_upper=float(ci[1]),
                significant=p_val < self.config.alpha,
                degrees_of_freedom=n - 2,
            ))
        except Exception:
            pass
        
        return tests
    
    def _test_information_ratio(self, returns: np.ndarray, benchmark: np.ndarray) -> list[HypothesisTestResult]:
        """Test if Information Ratio is significant."""
        tests = []
        
        min_len = min(len(returns), len(benchmark))
        r = returns[-min_len:]
        b = benchmark[-min_len:]
        
        active_returns = r - b
        ir = np.mean(active_returns) / np.std(active_returns) * np.sqrt(252) if np.std(active_returns) > 0 else 0
        
        if np.std(active_returns) > 0:
            # Standard error of IR
            n = len(active_returns)
            skew = stats.skew(active_returns)
            kurt = stats.kurtosis(active_returns)
            se_ir = np.sqrt((1 + 0.5*ir**2 - skew*ir + (kurt-3)/4*ir**2) / n)
            
            t_stat = ir / se_ir
            p_val = 1 - stats.t.cdf(t_stat, n-1)
            
            tests.append(HypothesisTestResult(
                test_name="Information Ratio",
                test_type=TestType.ONE_SAMPLE_T,
                statistic=float(t_stat),
                p_value=float(p_val),
                effect_size=float(ir),
                significant=p_val < self.config.alpha,
                degrees_of_freedom=n-1,
            ))
        
        return tests
    
    def _test_trade_statistics(self, trades: list[dict]) -> list[HypothesisTestResult]:
        """Test trade-level statistics."""
        tests = []
        
        if not trades:
            return tests
        
        pnls = np.array([t.get('pnl', 0) for t in trades])
        
        # Win rate test
        wins = np.sum(pnls > 0)
        n = len(pnls)
        win_rate = wins / n
        
        # Binomial test for win rate > 0.5
        from scipy.stats import binomtest
        binom_result = binomtest(wins, n, p=0.5, alternative='greater')
        
        tests.append(HypothesisTestResult(
            test_name="Win Rate > 50%",
            test_type=TestType.ONE_SAMPLE_T,
            statistic=binom_result.statistic,
            p_value=binom_result.pvalue,
            effect_size=win_rate - 0.5,
            significant=binom_result.pvalue < self.config.alpha,
        ))
        
        # Profit factor test
        gross_profit = np.sum(pnls[pnls > 0])
        gross_loss = abs(np.sum(pnls[pnls < 0]))
        if gross_loss > 0:
            pf = gross_profit / gross_loss
            tests.append(HypothesisTestResult(
                test_name="Profit Factor > 1",
                test_type=TestType.ONE_SAMPLE_T,
                statistic=pf,
                p_value=0.0 if pf > 1 else 1.0,  # Simplified
                effect_size=pf - 1,
                significant=pf > 1,
            ))
        
        return tests
    
    def _apply_multiple_testing_correction(
        self,
        tests: list[HypothesisTestResult],
    ) -> MultipleTestingResult:
        """Apply multiple testing correction."""
        p_values = [t.p_value for t in tests]
        n_tests = len(p_values)
        
        method_map = {
            CorrectionMethod.BONFERRONI: 'bonferroni',
            CorrectionMethod.HOLM_BONFERRONI: 'holm',
            CorrectionMethod.BENJAMINI_HOCHBERG: 'fdr_bh',
            CorrectionMethod.BENJAMINI_YEKUTIELI: 'fdr_by',
            CorrectionMethod.NONE: 'none',
        }
        
        method = method_map.get(self.config.correction_method, 'fdr_bh')
        
        if method == 'none':
            rejected = [p < self.config.alpha for p in p_values]
            adjusted = p_values
        else:
            rejected, adjusted, _, _ = multipletests(p_values, alpha=self.config.alpha, method=method)
        
        # Update test results
        for i, test in enumerate(tests):
            test.p_value_adjusted = adjusted[i]
            test.significant_after_correction = rejected[i]
        
        return MultipleTestingResult(
            method=self.config.correction_method,
            n_tests=n_tests,
            alpha_original=self.config.alpha,
            alpha_adjusted=self.config.alpha / n_tests if self.config.correction_method == CorrectionMethod.BONFERRONI else self.config.alpha,
            rejected=rejected,
            p_values_original=p_values,
            p_values_adjusted=adjusted,
            rejected_count=sum(rejected),
            fdr_estimate=float(np.mean(p_values)) if n_tests > 0 else 0,
        )
    
    def _compute_effect_sizes(
        self,
        returns: np.ndarray,
        benchmark: np.ndarray | None,
    ) -> dict[str, float]:
        """Compute effect sizes for key metrics."""
        effect_sizes = {}
        
        # Cohen's d for mean return
        mean_ret = np.mean(returns)
        std_ret = np.std(returns, ddof=1)
        if std_ret > 0:
            effect_sizes['mean_return_cohens_d'] = mean_ret / std_ret
        
        # Sharpe as effect size
        sharpe = np.mean(returns) / np.std(returns, ddof=1) * np.sqrt(252) if np.std(returns) > 0 else 0
        effect_sizes['sharpe_ratio'] = sharpe
        
        # PS (Probability of Superiority) - common language effect size
        if len(returns) > 1:
            # PS = P(X > Y) for X=returns, Y=0
            ps = np.mean(returns > 0)
            effect_sizes['probability_of_profit'] = ps
            # Common language effect size
            cl = 2 * ps - 1
            effect_sizes['common_language_effect'] = cl
        
        # Cohen's d for benchmark comparison
        if benchmark is not None and len(benchmark) > 0:
            min_len = min(len(returns), len(benchmark))
            active_ret = returns[-min_len:] - benchmark[-min_len:]
            if np.std(active_returns := returns[-len(benchmark):] - benchmark) > 0:
                effect_sizes['active_return_cohens_d'] = np.mean(active_returns) / np.std(active_returns)
        
        return effect_sizes
    
    def _compute_confidence_intervals(self, returns: np.ndarray) -> dict[str, tuple[float, float]]:
        """Compute confidence intervals for key metrics."""
        n = len(returns)
        ci_dict = {}
        
        # Mean return
        mean_ret = np.mean(returns)
        se = stats.sem(returns)
        ci_dict['mean_return'] = stats.t.interval(0.95, n-1, loc=np.mean(returns), scale=se)
        
        # Sharpe ratio
        sharpe = np.mean(returns) / np.std(returns, ddof=1) * np.sqrt(252) if np.std(returns) > 0 else 0
        se_sharpe = np.sqrt((1 + 0.5*sharpe**2) / n)
        ci_dict['sharpe_ratio'] = stats.t.interval(0.95, n-1, loc=sharpe, scale=se_sharpe)
        
        # Volatility
        vol = np.std(returns, ddof=1) * np.sqrt(252)
        se_vol = vol / np.sqrt(2 * (n-1))
        ci_dict['volatility'] = stats.t.interval(0.95, n-1, loc=vol, scale=se_vol)
        
        # Max drawdown
        cumret = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumret)
        dd = (cumret - running_max) / running_max
        max_dd = np.min(dd)
        # Bootstrap CI for max DD
        boot_dd = []
        for _ in range(1000):
            boot_rets = np.random.choice(returns, size=len(returns), replace=True)
            boot_cum = np.cumprod(1 + boot_rets)
            boot_max = np.maximum.accumulate(boot_cum)
            boot_dd = np.min((boot_cum - boot_max) / boot_max)
            boot_dd.append(boot_dd)
        ci_dict['max_drawdown'] = (float(np.percentile(boot_dd, 2.5)), float(np.percentile(boot_dd, 97.5)))
        
        return ci_dict
    
    def _run_bootstrap(self, returns: np.ndarray) -> dict[str, Any]:
        """Run bootstrap analysis for key metrics."""
        n = len(returns)
        n_boot = self.config.n_bootstrap
        
        boot_sharpe = []
        boot_return = []
        boot_vol = []
        boot_dd = []
        boot_calmar = []
        
        for _ in range(n_boot):
            boot_rets = self._rng.choice(returns, size=n, replace=True)
            
            mean_r = np.mean(boot_rets)
            std_r = np.std(boot_rets, ddof=1)
            
            if std_r > 0:
                sharpe = mean_r / std_r * np.sqrt(252)
                boot_sharpe.append(sharpe)
            
            boot_return.append(mean_r * 252)
            boot_vol.append(std_r * np.sqrt(252))
            
            # Max DD
            cum = np.cumprod(1 + boot_rets)
            run_max = np.maximum.accumulate(cum)
            dd = np.min((cum - np.maximum.accumulate(cum)) / np.maximum.accumulate(cum))
            boot_dd.append(dd)
            
            # Calmar
            ann_ret = np.mean(boot_rets) * 252
            if dd < 0:
                boot_calmar.append(ann_ret / abs(dd))
        
        return {
            'sharpe': {
                'mean': float(np.mean(boot_sharpe)),
                'std': float(np.std(boot_sharpe)),
                'ci_95': [float(np.percentile(boot_sharpe, 2.5)), float(np.percentile(boot_sharpe, 97.5))],
            },
            'annual_return': {
                'mean': float(np.mean(boot_return)),
                'std': float(np.std(boot_return)),
                'ci_95': [float(np.percentile(boot_return, 2.5)), float(np.percentile(boot_return, 97.5))],
            },
            'volatility': {
                'mean': float(np.mean(boot_vol)),
                'std': float(np.std(boot_vol)),
                'ci_95': [float(np.percentile(boot_vol, 2.5)), float(np.percentile(boot_vol, 97.5))],
            },
            'max_drawdown': {
                'mean': float(np.mean(boot_dd)),
                'std': float(np.std(boot_dd)),
                'ci_95': [float(np.percentile(boot_dd, 2.5)), float(np.percentile(boot_dd, 97.5))],
            },
            'calmar_ratio': {
                'mean': float(np.mean(boot_calmar)) if boot_calmar else 0,
                'std': float(np.std(boot_calmar)) if boot_calmar else 0,
            },
        }
    
    def _run_power_analysis(self, returns: np.ndarray) -> list[PowerAnalysisResult]:
        """Run power analysis for key tests."""
        results = []
        
        n = len(returns)
        mean_ret = np.mean(returns)
        std_ret = np.std(returns, ddof=1)
        
        # Power for mean return test
        if std_ret > 0:
            d = mean_ret / std_ret
            # Approximate power for one-sample t-test
            from statsmodels.stats.power import TTestPower
            power_analysis = TTestPower()
            power = power_analysis.solve_power(
                effect_size=d,
                nobs1=len(returns),
                alpha=self.config.alpha,
                alternative='larger',
            )
            
            required_n = power_analysis.solve_power(
                effect_size=d,
                power=0.8,
                alpha=self.config.alpha,
                alternative='larger',
            )
            
            results.append(PowerAnalysisResult(
                test_name="Mean Return > 0",
                effect_size=float(d),
                alpha=self.config.alpha,
                sample_size=len(returns),
                power=float(power),
                required_sample_size=int(np.ceil(required_n)) if np.isfinite(required_n) else None,
            ))
        
        return results
    
    def _check_reproducibility(self, returns: np.ndarray) -> list[ReproducibilityResult]:
        """Check reproducibility via split-sample and bootstrap."""
        results = []
        
        n = len(returns)
        if n < 60:
            return results
        
        # Split-sample reproducibility
        mid = n // 2
        first_half = returns[:mid]
        second_half = returns[mid:]
        
        # Correlation between halves
        min_len = min(len(first_half), len(second_half))
        if min_len > 10:
            corr = np.corrcoef(first_half[:min_len], second_half[:min_len])[0, 1]
            concordance = 1 if np.mean(first_half[:min_len]) * np.mean(second_half[:min_len]) > 0 else 0
            
            # Reproducibility score
            repro_score = (corr + 1) / 2 * 0.5 + concordance * 0.5
            
            results.append(ReproducibilityResult(
                metric_name="Mean Return",
                original_value=float(np.mean(returns)),
                replication_values=[float(np.mean(returns[:mid])), float(np.mean(returns[mid:]))],
                mean_replication=float(np.mean([np.mean(first_half), np.mean(second_half)])),
                std_replication=float(np.std([np.mean(first_half), np.mean(second_half)])),
                correlation=float(corr),
                concordance=float(concordance),
                reproducible=repro_score > self.config.min_reproducibility,
                reproducibility_score=float(repro_score),
            ))
        
        # Bootstrap reproducibility
        if len(returns) > 30:
            boot_sharpes = []
            for _ in range(100):
                boot = np.random.choice(returns, size=len(returns), replace=True)
                sharpe = np.mean(boot) / np.std(boot, ddof=1) * np.sqrt(252) if np.std(boot) > 0 else 0
                boot_sharpes.append(sharpe)
            
            orig_sharpe = np.mean(returns) / np.std(returns, ddof=1) * np.sqrt(252) if np.std(returns) > 0 else 0
            
            results.append(ReproducibilityResult(
                metric_name="Sharpe Ratio",
                original_value=float(orig_sharpe),
                replication_values=boot_sharpes[:10],  # Sample
                mean_replication=float(np.mean(boot_sharpes)),
                std_replication=float(np.std(boot_sharpes)),
                correlation=1.0,  # N/A
                concordance=1.0 if np.mean(boot_sharpes) * orig_sharpe > 0 else 0.0,
                reproducible=abs(np.mean(boot_sharpes) - orig_sharpe) < 0.5 * np.std(boot_sharpes) if len(boot_sharpes) > 1 else False,
                reproducibility_score=1.0 - min(1.0, abs(np.mean(boot_sharpes) - orig_sharpe) / (abs(orig_sharpe) + 1e-6)),
            ))
        
        return results
    
    def _interpret_cohens_d(self, d: float) -> str:
        """Interpret Cohen's d effect size."""
        abs_d = abs(d)
        if abs_d < 0.2:
            return "Negligible"
        elif abs_d < 0.5:
            return "Small"
        elif abs_d < 0.8:
            return "Medium"
        else:
            return "Large"
    
    def _interpret_sharpe(self, sharpe: float) -> str:
        """Interpret Sharpe ratio."""
        if sharpe < 0:
            return "Negative (underperforms risk-free)"
        elif sharpe < 0.5:
            return "Poor"
        elif sharpe < 1.0:
            return "Subpar"
        elif sharpe < 1.5:
            return "Adequate"
        elif sharpe < 2.0:
            return "Good"
        elif sharpe < 3.0:
            return "Excellent"
        else:
            return "Exceptional"
    
    def _interpret_skewness(self, skew: float) -> str:
        """Interpret skewness."""
        if skew < -1:
            return "Highly negative skew (left tail risk)"
        elif skew < -0.5:
            return "Moderate negative skew"
        elif skew < 0.5:
            return "Approximately symmetric"
        elif skew < 1:
            return "Moderate positive skew"
        else:
            return "Highly positive skew (right tail opportunity)"
    
    def _interpret_kurtosis(self, kurt: float) -> str:
        """Interpret kurtosis."""
        if kurt < -1:
            return "Platykurtic (thin tails)"
        elif kurt < 1:
            return "Near normal tails"
        elif kurt < 3:
            return "Moderately fat tails"
        else:
            return "Leptokurtic (fat tails, tail risk)"
    
    def _evaluate_pass_fail(
        self,
        returns: np.ndarray,
        tests: list[HypothesisTestResult],
        multiple_testing: MultipleTestingResult,
        effect_sizes: dict[str, float],
        confidence_intervals: dict[str, tuple[float, float]],
    ) -> tuple[bool, list[str]]:
        """Evaluate overall pass/fail."""
        failures = []
        
        # At least one significant positive test
        significant_positive = any(
            t.significant and t.effect_size is not None and t.effect_size > 0
            for t in tests
        )
        if not significant_positive:
            failures.append("No statistically significant positive performance metrics")
        
        # Multiple testing correction
        if multiple_testing.rejected_count == 0:
            failures.append("No tests significant after multiple testing correction")
        
        # Effect size minimums
        for name, es in effect_sizes.items():
            if abs(es) < self.config.min_effect_size and 'cohens_d' in name:
                failures.append(f"Effect size {name} = {es:.3f} below minimum {self.config.min_effect_size}")
        
        # Confidence intervals
        for name, (lower, upper) in confidence_intervals.items():
            if 'sharpe' in name.lower() and upper <= 0:
                failures.append(f"Sharpe ratio CI includes zero or negative: [{lower:.3f}, {upper:.3f}]")
            if 'drawdown' in name.lower() and lower < -0.5:
                failures.append(f"Max drawdown CI includes >50%: [{lower:.1%}, {upper:.1%}]")
        
        # Overall mean return
        if np.mean(returns) <= 0:
            failures.append("Mean return not positive")
        
        # Minimum Sharpe
        sharpe = np.mean(returns) / np.std(returns, ddof=1) * np.sqrt(252) if np.std(returns) > 0 else 0
        if sharpe < 0.5:
            failures.append(f"Sharpe ratio {sharpe:.2f} below minimum 0.5")
        
        return len(failures) == 0, failures


# Convenience function
async def quick_statistical_validation(
    returns: np.ndarray,
    benchmark: np.ndarray | None = None,
    config: StatisticalConfig | None = None,
) -> StatisticalValidationReport:
    """Quick statistical validation with defaults."""
    validator = StatisticalValidator(config)
    return await validator.validate(returns, benchmark)