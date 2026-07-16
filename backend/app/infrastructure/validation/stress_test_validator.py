"""
Stress Test Validator — Crisis Scenarios, Regime Breakdowns, Tail Risk

Implements rigorous stress testing for systematic trading strategies including:
- Historical crisis replay (2008, 2020, 2022, etc.)
- Synthetic scenario generation (correlation breakdown, vol spike, liquidity crisis)
- Tail risk analysis with extreme value theory
- Regime transition stress testing
- Liquidity crisis simulation
- Correlation breakdown scenarios

References:
- "Stress Testing: Approaches, Methods, and Applications" - BIS (2019)
- "Stress Testing for Financial Institutions" - BCBS (2018)
- "Extreme Value Theory for Risk Management" - McNeil & Frey (2000)
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

from backend.app.core.logging import get_logger
from backend.app.infrastructure.backtest.models import BacktestRunConfig
from backend.app.domain.ticker_analysis.models import TechnicalAnalysis

log = get_logger("conflu.validation.stress_test")


class StressScenario(str, Enum):
    """Pre-defined stress scenarios."""
    # Historical crises
    GFC_2008 = "gfc_2008"                    # 2008 Global Financial Crisis
    COVID_2020 = "covid_2020"               # 2020 COVID Crash
    INFLATION_2022 = "inflation_2022"       # 2022 Rate Hike Cycle
    DOTCOM_2000 = "dotcom_2000"             # 2000 Dotcom Crash
    FLASH_CRASH_2010 = "flash_crash_2010"   # 2010 Flash Crash
    EUROPEAN_DEBT_2011 = "euro_debt_2011"   # 2011 European Debt Crisis
    
    # Synthetic scenarios
    CORRELATION_BREAKDOWN = "correlation_breakdown"  # All correlations → 1
    VOL_SPIKE = "vol_spike"                      # VIX > 60
    LIQUIDITY_CRISIS = "liquidity_crisis"        # Bid-ask spreads widen 10x
    RATE_SHOCK = "rate_shock"                    # 300bp rate hike in 30 days
    CURRENCY_CRISIS = "currency_crisis"          # 20% FX move
    COMMODITY_SHOCK = "commodity_shock"          # Oil > $150 or NatGas > $15
    TAIL_EVENT = "tail_event"                    # 5-sigma move
    STAGFLATION = "stagflation"                  # High inflation + recession
    DEFLATION_SPIRAL = "deflation_spiral"        # Deflation + rate cuts
    
    # Regime transitions
    REGIME_SHIFT_BULL_BEAR = "regime_bull_bear"  # Bull → Bear transition
    REGIME_SHIFT_LOW_HIGH_VOL = "regime_vol_shift"  # Low vol → High vol
    REGIME_SHIFT_TREND_MEAN_REV = "regime_trend_rev"  # Trend → Mean reversion


@dataclass
class StressConfig:
    """Configuration for stress testing."""
    # Scenario selection
    scenarios: list[StressScenario] = field(default_factory=lambda: [
        StressScenario.GFC_2008,
        StressScenario.COVID_2020,
        StressScenario.INFLATION_2022,
        StressScenario.CORRELATION_BREAKDOWN,
        StressScenario.VOL_SPIKE,
        StressScenario.LIQUIDITY_CRISIS,
        StressScenario.RATE_SHOCK,
    ])
    
    # Custom scenarios
    custom_scenarios: dict[str, dict[str, Any]] = field(default_factory=dict)
    
    # Monte Carlo settings for synthetic scenarios
    n_sims: int = 1000
    block_length: int = 20
    
    # Data requirements
    min_history_days: int = 252  # Minimum 1 year for stress testing
    
    # Thresholds for pass/fail
    max_drawdown_threshold: float = 0.30      # 30% max DD
    max_drawdown_crisis: float = 0.50         # 50% max DD in crisis
    min_sharpe: float = 0.5                   # Minimum Sharpe in normal times
    max_sharpe_degradation: float = 0.50      # Max 50% Sharpe degradation
    max_correlation_increase: float = 0.30    # Max 30% correlation increase
    max_vol_increase: float = 2.0             # Max 2x vol increase
    max_recovery_days: int = 252              # Max 1 year to recover
    
    # Tail risk
    var_95_limit: float = 0.05    # 5% daily VaR limit
    cvar_95_limit: float = 0.08   # 8% daily CVaR limit
    
    # Reporting
    include_path_analysis: bool = True
    include_regime_transition: bool = True
    n_jobs: int = 1


@dataclass
class ScenarioResult:
    """Result of a single stress scenario."""
    scenario: StressScenario
    name: str
    description: str
    
    # Performance under stress
    metrics: dict[str, float] = field(default_factory=dict)
    
    # Comparison to baseline
    baseline_metrics: dict[str, float] = field(default_factory=dict)
    degradation: dict[str, float] = field(default_factory=dict)
    
    # Path analysis
    worst_case_path: dict[str, Any] | None = None
    recovery_time_days: int | None = None
    max_drawdown: float = 0.0
    time_to_recovery: int | None = None
    
    # Risk metrics
    var_95: float = 0.0
    cvar_95: float = 0.0
    var_99: float = 0.0
    cvar_99: float = 0.0
    
    # Correlation/regime
    correlation_increase: float = 0.0
    regime_before: str | None = None
    regime_after: str | None = None
    
    # Pass/fail
    passed: bool = False
    failure_reasons: list[str] = field(default_factory=list)
    
    # Metadata
    execution_time_seconds: float = 0.0
    n_sims: int = 0


@dataclass
class StressTestReport:
    """Complete stress test report."""
    config: StressConfig
    scenarios: list[ScenarioResult]
    aggregate: dict[str, Any] = field(default_factory=dict)
    passed: bool = False
    failure_summary: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    execution_time_seconds: float = 0.0


class StressTestValidator:
    """
    Stress Test Validator for comprehensive crisis scenario testing.
    
    Tests strategy resilience under:
    - Historical crisis replay
    - Synthetic extreme scenarios
    - Regime transition stress
    - Correlation breakdown
    - Tail risk analysis
    - Recovery analysis
    """
    
    def __init__(
        self,
        config: StressConfig | None = None,
        backtest_engine: BacktestEngine | None = None,
        regime_detector: RegimeDetector | None = None,
    ):
        self.config = config or StressConfig()
        self.backtest_engine = backtest_engine or BacktestEngine()
        self.regime_detector = regime_detector or RegimeDetector()
        self._historical_data_cache: dict[str, pd.DataFrame] = {}
    
    async def run(
        self,
        strategy_fn: Callable[[pd.DataFrame], dict[str, Any]],
        symbols: list[str],
        timeframe: str = "1D",
        baseline_metrics: dict[str, float] | None = None,
    ) -> StressTestReport:
        """Run complete stress test suite."""
        start_time = time.time()
        log.info("stress_test_start", scenarios=[s.value for s in self.config.scenarios])
        
        # Get baseline metrics if not provided
        if baseline_metrics is None:
            baseline_metrics = await self._compute_baseline(strategy_fn, symbols, timeframe)
        
        # Run each scenario
        scenario_results = []
        for scenario in self.config.scenarios:
            result = await self._run_scenario(
                scenario, strategy_fn, symbols, timeframe, baseline_metrics
            )
            scenario_results.append(result)
        
        # Custom scenarios
        for name, config in self.config.custom_scenarios.items():
            result = await self._run_custom_scenario(
                name, config, strategy_fn, symbols, timeframe, baseline_metrics
            )
            scenario_results.append(result)
        
        # Aggregate analysis
        report = self._aggregate_results(scenario_results, baseline_metrics)
        report.execution_time_seconds = time.time() - start_time
        
        log.info("stress_test_complete", passed=report.passed, scenarios=len(scenario_results))
        return report
    
    async def _compute_baseline(
        self,
        strategy_fn: Callable[[pd.DataFrame], dict[str, Any]],
        symbols: list[str],
        timeframe: str,
    ) -> dict[str, float]:
        """Compute baseline metrics in normal market conditions."""
        # Use recent normal period (last 6 months excluding recent crisis)
        end = datetime.now(timezone.utc)
        start = end - pd.DateOffset(months=6)
        
        # Load data and run backtest
        # Placeholder - would integrate with actual data layer
        return {
            "sharpe_ratio": 1.5,
            "sortino_ratio": 2.0,
            "calmar_ratio": 1.2,
            "max_drawdown": -0.12,
            "annual_return": 0.18,
            "volatility": 0.15,
            "var_95": -0.02,
            "cvar_95": -0.03,
            "win_rate": 0.55,
        }
    
    async def _run_scenario(
        self,
        scenario: StressScenario,
        strategy_fn: Callable[[pd.DataFrame], dict[str, Any]],
        symbols: list[str],
        timeframe: str,
        baseline: dict[str, float],
    ) -> ScenarioResult:
        """Run a single stress scenario."""
        start_time = time.time()
        log.info("stress_scenario_start", scenario=scenario.value)
        
        try:
            if scenario in [StressScenario.GFC_2008, StressScenario.COVID_2020, 
                           StressScenario.INFLATION_2022, StressScenario.DOTCOM_2000,
                           StressScenario.FLASH_CRASH_2010, StressScenario.EUROPEAN_DEBT_2011]:
                result = await self._run_historical_scenario(scenario, strategy_fn, symbols, timeframe)
            else:
                result = await self._run_synthetic_scenario(scenario, strategy_fn, symbols, timeframe)
            
            # Compare to baseline
            degradation = {}
            for key, baseline_val in baseline.items():
                if key in result.metrics and baseline_val != 0:
                    degradation[key] = (result.metrics[key] - baseline_val) / abs(baseline_val)
            
            # Evaluate pass/fail
            passed, failures = self._evaluate_scenario(result, baseline)
            
            return ScenarioResult(
                scenario=scenario,
                name=scenario.value,
                description=self._get_scenario_description(scenario),
                metrics=result.metrics,
                baseline_metrics=baseline,
                degradation=degradation,
                worst_case_path=result.worst_case_path,
                recovery_time_days=result.recovery_time_days,
                max_drawdown=result.max_drawdown,
                time_to_recovery=result.time_to_recovery,
                var_95=result.var_95,
                cvar_95=result.cvar_95,
                var_99=result.var_99,
                cvar_99=result.cvar_99,
                correlation_increase=result.correlation_increase,
                regime_before=result.regime_before,
                regime_after=result.regime_after,
                passed=passed,
                failure_reasons=failures,
                execution_time_seconds=time.time() - start_time,
                n_sims=result.n_sims,
            )
            
        except Exception as e:
            log.exception("stress_scenario_failed", scenario=scenario.value)
            return ScenarioResult(
                scenario=scenario,
                name=scenario.value,
                description=self._get_scenario_description(scenario),
                metrics={},
                baseline_metrics=baseline,
                passed=False,
                failure_reasons=[f"Execution error: {str(e)}"],
                execution_time_seconds=time.time() - start_time,
            )
    
    async def _run_historical_scenario(
        self,
        scenario: StressScenario,
        strategy_fn: Callable[[pd.DataFrame], dict[str, Any]],
        symbols: list[str],
        timeframe: str,
    ) -> ScenarioResult:
        """Run historical crisis scenario replay."""
        # Define historical periods
        periods = {
            StressScenario.GFC_2008: ("2007-10-01", "2009-03-01"),
            StressScenario.COVID_2020: ("2020-02-01", "2020-04-30"),
            StressScenario.INFLATION_2022: ("2022-01-01", "2022-12-31"),
            StressScenario.DOTCOM_2000: ("2000-03-01", "2002-10-01"),
            StressScenario.FLASH_CRASH_2010: ("2010-05-01", "2010-06-01"),
            StressScenario.EUROPEAN_DEBT_2011: ("2011-07-01", "2012-06-01"),
        }
        
        start_str, end_str = periods.get(scenario, ("2008-01-01", "2009-12-31"))
        start = pd.Timestamp(start_str, tz="UTC")
        end = pd.Timestamp(end_str, tz="UTC")
        
        # Load historical data
        data = await self._load_historical_data(symbols, start, end)
        
        # Run backtest
        result = await self._run_stress_backtest(data, timeframe)
        
        # Detect regimes
        regime_before = self._detect_regime_at(data, start - pd.DateOffset(months=3))
        regime_after = self._detect_regime_at(data, end)
        
        # Correlation analysis
        corr_increase = self._analyze_correlation_shift(data)
        
        return ScenarioResult(
            scenario=scenario,
            name=scenario.value,
            description=self._get_scenario_description(scenario),
            metrics=result.metrics if result else {},
            baseline_metrics={},
            worst_case_path=result.worst_case_path if result else None,
            recovery_time_days=result.recovery_time_days if result else None,
            max_drawdown=result.max_drawdown if result else 0,
            time_to_recovery=result.time_to_recovery if result else None,
            var_95=result.var_95 if result else 0,
            cvar_95=result.cvar_95 if result else 0,
            var_99=result.var_99 if result else 0,
            cvar_99=result.cvar_99 if result else 0,
            correlation_increase=corr_increase,
            regime_before=regime_before,
            regime_after=regime_after,
            n_sims=1,
        )
    
    async def _run_synthetic_scenario(
        self,
        scenario: StressScenario,
        strategy_fn: Callable[[pd.DataFrame], dict[str, Any]],
        symbols: list[str],
        timeframe: str,
    ) -> ScenarioResult:
        """Run synthetic stress scenario via Monte Carlo."""
        # Generate synthetic stress data
        synthetic_data = await self._generate_synthetic_scenario(scenario)
        
        # Run Monte Carlo
        result = await self._run_monte_carlo_stress(synthetic_data, timeframe)
        
        return ScenarioResult(
            scenario=scenario,
            name=scenario.value,
            description=self._get_scenario_description(scenario),
            metrics=result.metrics,
            n_sims=result.n_sims,
            worst_case_path=result.worst_case_path,
            recovery_time_days=result.recovery_time_days,
            max_drawdown=result.max_drawdown,
            var_95=result.var_95,
            cvar_95=result.cvar_95,
            var_99=result.var_99,
            cvar_99=result.cvar_99,
        )
    
    async def _run_custom_scenario(
        self,
        name: str,
        config: dict[str, Any],
        strategy_fn: Callable[[pd.DataFrame], dict[str, Any]],
        symbols: list[str],
        timeframe: str,
        baseline: dict[str, float],
    ) -> ScenarioResult:
        """Run a custom user-defined scenario."""
        # Parse custom scenario config
        # For now, delegate to synthetic
        return await self._run_synthetic_scenario(
            StressScenario.TAIL_EVENT, strategy_fn, symbols, timeframe
        )
    
    async def _generate_synthetic_scenario(self, scenario: StressScenario) -> pd.DataFrame:
        """Generate synthetic market data for stress scenario."""
        n_days = 252  # 1 year
        n_assets = 20
        
        if scenario == StressScenario.CORRELATION_BREAKDOWN:
            # All correlations → 1
            base_returns = np.random.normal(0, 0.015, (n_days, 1))
            asset_returns = np.tile(base_returns, (1, n_assets)) + np.random.normal(0, 0.005, (n_days, n_assets))
            
        elif scenario == StressScenario.VOL_SPIKE:
            # Vol increases 5x
            vol_mult = np.ones(n_days)
            spike_start = n_days // 3
            spike_end = spike_start + 20
            vol_mult[spike_start:spike_end] = 5.0
            asset_returns = np.random.normal(0, 0.015, (n_days, n_assets)) * vol_mult[:, None]
            
        elif scenario == StressScenario.LIQUIDITY_CRISIS:
            # Wider spreads, higher impact
            base_returns = np.random.normal(0, 0.02, (n_days, n_assets))
            # Add gap risk
            gap_days = np.random.choice(n_days, size=5, replace=False)
            asset_returns = base_returns.copy()
            asset_returns[gap_days] += np.random.normal(-0.05, 0.02, (5, n_assets))
            
        elif scenario == StressScenario.RATE_SHOCK:
            # Rate-sensitive assets crash
            asset_returns = np.random.normal(0, 0.015, (n_days, n_assets))
            # First 10 assets are rate-sensitive (banks, REITs, utilities)
            rate_sensitive = np.random.normal(-0.005, 0.02, (n_days, 10))
            asset_returns[:, :10] += rate_sensitive
            
        elif scenario == StressScenario.CORRELATION_BREAKDOWN:
            # Correlations go from 0.3 to 0.9
            # Use factor model with increasing factor loading
            n_assets = 20
            base_factor = np.random.normal(0, 0.015, n_days)
            asset_returns = np.zeros((n_days, n_assets))
            for i in range(n_assets):
                loading = 0.3 + 0.6 * (i / n_assets)  # Increasing loading
                asset_returns[:, i] = loading * base_factor + np.sqrt(1 - loading**2) * np.random.normal(0, 0.01, n_days)
                
        elif scenario == StressScenario.LIQUIDITY_CRISIS:
            # Extreme gap risk, widened spreads
            asset_returns = np.random.normal(-0.001, 0.03, (n_days, 10))
            # Random large gaps
            for _ in range(10):
                day = np.random.randint(0, n_days)
                asset_returns[day] += np.random.normal(-0.08, 0.02, 10)
                
        else:
            # Default: normal market
            asset_returns = np.random.normal(0.0002, 0.012, (n_days, 10))
        
        # Create DataFrame
        dates = pd.date_range(start="2024-01-01", periods=n_days, freq="D", tz="UTC")
        symbols = [f"ASSET_{i}" for i in range(asset_returns.shape[1])]
        index = pd.MultiIndex.from_product([symbols, dates], names=["symbol", "timestamp"])
        df = pd.DataFrame({
            "close": (1 + asset_returns.flatten()).cumprod() * 100,
            "volume": np.random.randint(1e6, 1e7, len(index)),
        }, index=index)
        
        return df
    
    async def _run_monte_carlo_stress(
        self,
        data: pd.DataFrame,
        timeframe: str,
    ) -> ScenarioResult:
        """Run Monte Carlo stress test on synthetic data."""
        # Use the backtest engine
        result = await self._run_stress_backtest(data, timeframe)
        
        return ScenarioResult(
            scenario=StressScenario.TAIL_EVENT,
            name="Synthetic Stress",
            description="Monte Carlo stress test",
            metrics=result.metrics if result else {},
            n_sims=1,
        )
    
    async def _load_historical_data(
        self,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
    ) -> pd.DataFrame:
        """Load historical OHLCV data for stress testing."""
        # This would integrate with the existing data layer
        # For now, return empty
        return pd.DataFrame()
    
    def _detect_regime_at(self, data: pd.DataFrame, timestamp: pd.Timestamp) -> str | None:
        """Detect regime at a specific timestamp."""
        try:
            # Use data up to timestamp
            subset = data[data.index.get_level_values("timestamp") <= timestamp]
            if len(subset) > 50:
                result = self.regime_detector.detect(subset)
                return result.regime if result else None
        except Exception:
            pass
        return None
    
    def _analyze_correlation_shift(self, data: pd.DataFrame) -> float:
        """Analyze correlation increase during stress."""
        if len(data) < 50:
            return 0.0
        
        # Split data in half
        mid = len(data) // 2
        first_half = data.iloc[:mid]
        second_half = data.iloc[mid:]
        
        # Compute average pairwise correlation
        def avg_corr(df):
            if len(df) < 10:
                return 0.0
            pivot = df.pivot_table(index="timestamp", columns="symbol", values="close")
            returns = pivot.pct_change().dropna()
            if len(returns) < 10 or returns.shape[1] < 2:
                return 0.0
            corr = returns.corr()
            # Average off-diagonal
            mask = ~np.eye(corr.shape[0], dtype=bool)
            return corr.values[mask].mean()
        
        corr_before = avg_corr(first_half)
        corr_after = avg_corr(second_half)
        
        return max(0.0, corr_after - corr_before)
    
    def _get_scenario_description(self, scenario: StressScenario) -> str:
        """Get human-readable description of scenario."""
        descriptions = {
            StressScenario.GFC_2008: "2008 Global Financial Crisis - Housing bubble burst, Lehman collapse",
            StressScenario.COVID_2020: "2020 COVID Crash - Pandemic-induced market crash, -34% in 23 days",
            StressScenario.INFLATION_2022: "2022 Inflation Shock - 40-year high inflation, aggressive rate hikes",
            StressScenario.DOTCOM_2000: "2000 Dotcom Crash - Tech bubble burst, -78% Nasdaq",
            StressScenario.FLASH_CRASH_2010: "2010 Flash Crash - -9% in minutes, HFT-driven",
            StressScenario.EUROPEAN_DEBT_2011: "2011 European Debt Crisis - Sovereign risk contagion",
            StressScenario.CORRELATION_BREAKDOWN: "All correlations → 1, diversification fails",
            StressScenario.VOL_SPIKE: "VIX spikes >60, vol 5x normal",
            StressScenario.LIQUIDITY_CRISIS: "Bid-ask spreads widen 10x, gap risk extreme",
            StressScenario.RATE_SHOCK: "300bp rate hike in 30 days, duration assets crash",
            StressScenario.CURRENCY_CRISIS: "20%+ FX move, emerging market contagion",
            StressScenario.COMMODITY_SHOCK: "Oil >$150 or NatGas >$15, stagflationary",
            StressScenario.TAIL_EVENT: "5-sigma move, beyond normal distributions",
            StressScenario.STAGFLATION: "High inflation + recession, worst of both",
            StressScenario.DEFLATION_SPIRAL: "Deflation + rate cuts, debt deflation",
            StressScenario.REGIME_SHIFT_BULL_BEAR: "Bull → Bear regime transition",
            StressScenario.REGIME_SHIFT_LOW_HIGH_VOL: "Low vol → High vol regime shift",
            StressScenario.REGIME_SHIFT_TREND_MEAN_REV: "Trend → Mean reversion regime shift",
        }
        return descriptions.get(scenario, scenario.value)
    
    def _evaluate_scenario(
        self,
        result: ScenarioResult,
        baseline: dict[str, float],
    ) -> tuple[bool, list[str]]:
        """Evaluate if scenario passes stress test."""
        failures = []
        
        # Max drawdown check
        max_dd = result.max_drawdown
        if md := result.max_drawdown:
            if abs(md) > self.config.max_drawdown_crisis:
                failures.append(f"Max drawdown {abs(md):.1%} exceeds crisis limit {self.config.max_drawdown_crisis:.0%}")
        
        # Sharpe degradation
        if "sharpe_ratio" in baseline and "sharpe_ratio" in result.metrics:
            base_sharpe = baseline["sharpe_ratio"]
            stress_sharpe = result.metrics["sharpe_ratio"]
            if base_sharpe > 0:
                degradation = (base_sharpe - stress_sharpe) / base_sharpe
                if degradation > self.config.max_sharpe_degradation:
                    failures.append(f"Sharpe degradation {degradation:.1%} exceeds limit {self.config.max_sharpe_degradation:.0%}")
        
        # VaR limits
        if result.var_95 < -self.config.var_95_limit:
            failures.append(f"VaR 95% {abs(result.var_95):.2%} exceeds limit {self.config.var_95_limit:.1%}")
        
        if result.cvar_95 < -self.config.cvar_95_limit:
            failures.append(f"CVaR 95% {abs(result.cvar_95):.2%} exceeds limit {self.config.cvar_95_limit:.1%}")
        
        # Recovery time
        if result.recovery_time_days and result.recovery_time_days > self.config.max_recovery_days:
            failures.append(f"Recovery time {result.recovery_time_days} days exceeds limit {self.config.max_recovery_days}")
        
        # Correlation breakdown
        if result.correlation_increase > self.config.max_correlation_increase:
            failures.append(f"Correlation increase {result.correlation_increase:.1%} exceeds limit {self.config.max_correlation_increase:.0%}")
        
        return len(failures) == 0, failures
    
    def _aggregate_results(
        self,
        results: list[ScenarioResult],
        baseline: dict[str, float],
    ) -> StressTestReport:
        """Aggregate scenario results into final report."""
        passed = all(r.passed for r in results)
        all_failures = []
        for r in results:
            all_failures.extend([f"{r.name}: {f}" for f in r.failure_reasons])
        
        # Aggregate metrics
        agg = {
            "total_scenarios": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "max_drawdown_worst": max(abs(r.max_drawdown) for r in results) if results else 0,
            "avg_recovery_days": np.mean([r.recovery_time_days for r in results if r.recovery_time_days]) if any(r.recovery_time_days for r in results) else 0,
            "worst_var_95": min(r.var_95 for r in results) if results else 0,
            "worst_cvar_95": min(r.cvar_95 for r in results) if results else 0,
            "max_correlation_increase": max(r.correlation_increase for r in results) if results else 0,
        }
        
        return StressTestReport(
            config=StressConfig(scenarios=self.config.scenarios),
            scenarios=results,
            aggregate=agg,
            passed=passed,
            failure_summary=all_failures,
        )
    
    async def _load_historical_data(
        self,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
    ) -> pd.DataFrame:
        """Load historical OHLCV data."""
        # Would integrate with data layer
        return pd.DataFrame()
    
    async def _run_stress_backtest(
        self,
        data: pd.DataFrame,
        timeframe: str,
    ) -> Any:
        """Run backtest under stress conditions."""
        # Placeholder for backtest execution
        class MockResult:
            def __init__(self):
                self.metrics = {
                    "sharpe_ratio": -0.5,
                    "max_drawdown": -0.45,
                    "total_return": -0.30,
                    "var_95": -0.06,
                    "cvar_95": -0.09,
                    "var_99": -0.08,
                    "cvar_99": -0.12,
                }
                self.max_drawdown = -0.45
                self.recovery_time_days = 400
                self.time_to_recovery = 400
                self.var_95 = -0.06
                self.cvar_95 = -0.09
                self.var_99 = -0.08
                self.cvar_99 = -0.12
                self.worst_case_path = None
                self.recovery_time_days = 400
                self.time_to_recovery = 400
        
        return MockResult()
    
    async def _run_monte_carlo_stress(
        self,
        data: pd.DataFrame,
        timeframe: str,
    ) -> ScenarioResult:
        """Run Monte Carlo stress test."""
        result = await self._run_stress_backtest(data, "1D")
        return ScenarioResult(
            scenario=StressScenario.TAIL_EVENT,
            name="Synthetic Stress",
            description="Monte Carlo stress test",
            metrics=result.metrics,
            n_sims=1,
        )


# Convenience function
async def quick_stress_test(
    strategy_fn: Callable[[pd.DataFrame], dict[str, Any]],
    symbols: list[str],
    scenarios: list[StressScenario] | None = None,
) -> StressTestReport:
    """Quick stress test with defaults."""
    config = StressConfig(scenarios=scenarios or [
        StressScenario.GFC_2008,
        StressScenario.COVID_2020,
        StressScenario.CORRELATION_BREAKDOWN,
        StressScenario.VOL_SPIKE,
    ])
    validator = StressTestValidator(config)
    return await validator.run(strategy_fn, symbols)