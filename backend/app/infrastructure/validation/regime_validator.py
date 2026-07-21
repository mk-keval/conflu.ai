"""
Regime Validator — Cross-Regime Performance Validation

Validates strategy performance across different market regimes with:
- Regime detection and labeling
- Performance attribution by regime
- Regime transition analysis
- Regime persistence and stability metrics
- Cross-regime consistency checks
- Regime-specific risk metrics

References:
- "Advances in Financial Machine Learning" by Marcos Lopez de Prado (Ch. 13)
- "Regime Switching Models in Finance" - Ang & Timmermann (2012)
- "Market Regimes and Financial Crises" - Ang & Bekaert (2004)
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
from backend.app.infrastructure.regimes import RegimeDetector, RegimeResult

log = get_logger("conflu.validation.regime")


class RegimeLabel(str, Enum):
    """Standardized regime labels."""
    BULL_LOW_VOL = "bull_low_vol"           # Bull market, low volatility
    BULL_HIGH_VOL = "bull_high_vol"         # Bull market, high volatility
    BEAR_LOW_VOL = "bear_low_vol"           # Bear market, low volatility
    BEAR_HIGH_VOL = "bear_high_vol"         # Bear market, high volatility
    SIDEWAYS_LOW_VOL = "sideways_low_vol"   # Range-bound, low vol
    SIDEWAYS_HIGH_VOL = "sideways_high_vol" # Range-bound, high vol
    CRISIS = "crisis"                        # Crisis/fear regime
    RECOVERY = "recovery"                    # Post-crisis recovery
    UNKNOWN = "unknown"


@dataclass
class RegimeConfig:
    """Configuration for regime validation."""
    # Regime detection
    lookback_window: int = 63       # ~3 months for regime detection
    min_regime_duration: int = 10   # Minimum bars for valid regime
    
    # Performance thresholds per regime
    min_sharpe_bull: float = 0.8    # Minimum Sharpe in bull regimes
    max_sharpe_bear: float = 0.0    # Maximum acceptable Sharpe in bear (can be negative)
    max_drawdown_bear: float = -0.25  # Max DD in bear regime
    min_win_rate: float = 0.45      # Minimum win rate
    
    # Transition analysis
    min_transition_duration: int = 5  # Min bars for valid transition
    analyze_transitions: bool = True
    
    # Consistency requirements
    min_regime_consistency: float = 0.6  # Min regime assignment consistency
    max_regime_switches_per_year: int = 12  # Max regime switches
    
    # Reporting
    include_transition_analysis: bool = True
    include_regime_attribution: bool = True


@dataclass
class RegimePerformance:
    """Performance metrics for a single regime."""
    regime: RegimeLabel
    count: int                    # Number of periods in this regime
    total_return: float           # Total return in regime
    annualized_return: float      # Annualized return
    volatility: float             # Volatility in regime
    sharpe_ratio: float           # Sharpe ratio in regime
    sortino_ratio: float          # Sortino ratio
    max_drawdown: float           # Max drawdown in regime
    win_rate: float               # Win rate
    avg_trade_return: float       # Average trade return
    hit_rate: float               # % of positive periods
    avg_gain: float               # Average gain
    avg_loss: float               # Average loss
    profit_factor: float          # Gross win / gross loss
    calmar_ratio: float           # Calmar ratio
    duration_days: int            # Total days in regime
    avg_duration: float           # Average regime duration


@dataclass
class TransitionAnalysis:
    """Analysis of regime transitions."""
    from_regime: RegimeLabel
    to_regime: RegimeLabel
    count: int                    # Number of transitions
    avg_duration_before: float    # Avg days in from_regime before transition
    avg_duration_after: float     # Avg days in to_regime after transition
    avg_return_before: float      # Avg return in from_regime
    avg_return_after: float       # Avg return in to_regime
    strategy_performance_delta: float  # Performance change across transition
    transition_sharpe: float      # Sharpe during transition period
    success_rate: float           # % successful transitions


@dataclass
class RegimeValidationReport:
    """Complete regime validation report."""
    config: 'RegimeConfig'
    regime_performances: list['RegimePerformance']
    transitions: list['TransitionAnalysis']
    overall_consistency: float
    regime_consistency_scores: dict[str, float]
    transition_analysis: dict[str, Any] | None = None
    regime_attribution: dict[str, Any] | None = None
    passed: bool = False
    failure_reasons: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    execution_time_seconds: float = 0.0


class RegimeValidator:
    """
    Regime Validator — Cross-Regime Performance Validation.
    
    Validates that strategy performs consistently across market regimes:
    - Detects and labels market regimes
    - Attributes performance to regimes
    - Analyzes regime transitions
    - Checks consistency across regimes
    - Identifies regime-specific weaknesses
    """
    
    def __init__(
        self,
        config: RegimeConfig | None = None,
        backtest_engine: BacktestEngine | None = None,
        regime_detector: RegimeDetector | None = None,
    ):
        self.config = config or RegimeConfig()
        self.backtest_engine = backtest_engine or BacktestEngine()
        self.regime_detector = regime_detector or RegimeDetector()
    
    async def run(
        self,
        strategy_fn: Callable[[pd.DataFrame], dict[str, Any]],
        symbols: list[str],
        timeframe: str = "1D",
        returns: np.ndarray | None = None,
        timestamps: pd.DatetimeIndex | None = None,
    ) -> 'RegimeValidationReport':
        """
        Run complete regime validation.
        
        Args:
            strategy_fn: Strategy function that returns parameters from OHLCV
            symbols: List of symbols
            timeframe: Data timeframe
            returns: Pre-computed returns (optional)
            timestamps: Timestamps for returns (optional)
            
        Returns:
            RegimeValidationReport with regime analysis
        """
        start_time = time.time()
        log.info("regime_validation_start")
        
        # 1. Get or compute returns with timestamps
        if returns is None or timestamps is None:
            returns, timestamps = await self._get_returns_with_timestamps(symbols, timeframe)
        
        # 2. Detect regimes
        regimes = await self._detect_regimes(returns, timestamps)
        
        # 3. Run strategy in each regime
        regime_performances = await self._analyze_regime_performance(
            returns, timestamps, regimes, strategy_fn, symbols
        )
        
        # 4. Analyze transitions
        transitions = self._analyze_transitions(regimes, timestamps)
        
        # 5. Consistency checks
        consistency, consistency_scores = self._check_consistency(regimes, regime_performances)
        
        # 6. Regime attribution
        attribution = self._attribute_performance(regime_performances)
        
        # 6. Generate report
        report = self._generate_report(
            regime_performances, transitions, consistency, consistency_scores
        )
        report.execution_time_seconds = time.time() - start_time
        
        log.info("regime_validation_complete", passed=report.passed)
        return report
    
    async def _get_returns_with_timestamps(
        self,
        symbols: list[str],
        timeframe: str,
    ) -> tuple[np.ndarray, pd.DatetimeIndex]:
        """Get returns with timestamps for regime detection."""
        # In practice, this would load from the data layer
        # For now, return synthetic data
        n_days = 500
        dates = pd.date_range(end=datetime.now(timezone.utc), periods=n_days, freq="D", tz="UTC")
        returns = np.random.normal(0.0002, 0.015, n_days)
        return returns, dates
    
    async def _detect_regimes(
        self,
        returns: np.ndarray,
        timestamps: pd.DatetimeIndex,
    ) -> list[RegimeLabel]:
        """Detect market regimes from returns."""
        n = len(returns)
        if n < self.config.lookback_window * 2:
            return [RegimeLabel.UNKNOWN] * n
        
        # Use rolling window to detect regimes
        regimes = [RegimeLabel.UNKNOWN] * self.config.lookback_window
        
        for i in range(self.config.lookback_window, n):
            window_returns = returns[i - self.config.lookback_window:i]
            window_timestamps = timestamps[i - self.config.lookback_window:i]
            
            # Compute regime features
            mean_ret = np.mean(window_returns)
            vol = np.std(window_returns)
            skew = stats.skew(window_returns) if len(window_returns) > 2 else 0
            
            # Simple regime classification
            regime = self._classify_regime(mean_ret, vol, skew)
            regimes.append(regime)
        
        # Smooth regime assignments (minimum duration)
        regimes = self._smooth_regimes(regimes)
        
        return regimes
    
    def _classify_regime(self, mean_ret: float, vol: float, skew: float) -> RegimeLabel:
        """Classify regime based on return characteristics."""
        # Define volatility thresholds
        low_vol_threshold = 0.01   # ~16% annualized
        high_vol_threshold = 0.025 # ~40% annualized
        
        # Define return thresholds
        bull_threshold = 0.0004    # ~10% annualized
        bear_threshold = -0.0004   # ~-10% annualized
        
        is_high_vol = vol > high_vol_threshold
        is_low_vol = vol < low_vol_threshold
        is_bull = mean_ret > bull_threshold
        is_bear = mean_ret < bear_threshold
        is_sideways = not is_bull and not is_bear
        
        if is_bull and is_low_vol:
            return RegimeLabel.BULL_LOW_VOL
        elif is_bull and is_high_vol:
            return RegimeLabel.BULL_HIGH_VOL
        elif is_bear and is_low_vol:
            return RegimeLabel.BEAR_LOW_VOL
        elif is_bear and is_high_vol:
            return RegimeLabel.BEAR_HIGH_VOL
        elif is_sideways and is_low_vol:
            return RegimeLabel.SIDEWAYS_LOW_VOL
        elif is_sideways and is_high_vol:
            return RegimeLabel.SIDEWAYS_HIGH_VOL
        else:
            return RegimeLabel.UNKNOWN
    
    def _smooth_regimes(self, regimes: list[RegimeLabel]) -> list[RegimeLabel]:
        """Enforce minimum regime duration by smoothing."""
        if len(regimes) < self.config.min_regime_duration * 2:
            return regimes
        
        smoothed = regimes.copy()
        current_regime = regimes[0]
        duration = 1
        
        for i in range(1, len(regimes)):
            if regimes[i] == current_regime:
                duration += 1
            else:
                if duration < self.config.min_regime_duration:
                    # Too short - merge with previous
                    for j in range(i - duration, i):
                        smoothed[j] = current_regime
                current_regime = regimes[i]
                duration = 1
        
        # Handle last regime
        if duration < self.config.min_regime_duration:
            for j in range(len(regimes) - duration, len(regimes)):
                smoothed[j] = current_regime
        
        return smoothed
    
    async def _analyze_regime_performance(
        self,
        returns: np.ndarray,
        timestamps: pd.DatetimeIndex,
        regimes: list[RegimeLabel],
        strategy_fn: Callable[[pd.DataFrame], dict[str, Any]],
        symbols: list[str],
    ) -> list:
        """Analyze strategy performance in each regime."""
        # Group returns by regime
        regime_returns = defaultdict(list)
        regime_timestamps = defaultdict(list)
        
        for ret, ts, regime in zip(returns, timestamps, regimes):
            if regime != RegimeLabel.UNKNOWN:
                regime_returns[regime].append(ret)
                regime_timestamps[regime].append(regime_timestamps[regime][-1] if regime_timestamps[regime] else timestamps[0])
        
        performances = []
        
        for regime, rets in regime_returns.items():
            if len(rets) < 10:  # Need minimum data
                continue
            
            rets_arr = np.array(rets)
            
            # Compute metrics
            perf = self._compute_regime_metrics(regime, rets_arr)
            if perf:
                performances.append(perf)
        
        return performances
    
    def _compute_regime_metrics(self, regime: RegimeLabel, returns: np.ndarray) -> 'RegimePerformance' | None:
        """Compute performance metrics for a regime."""
        if len(returns) < 10:
            return None
        
        mean_ret = np.mean(returns)
        std_ret = np.std(returns)
        ann_ret = mean_ret * 252
        ann_vol = np.std(returns) * np.sqrt(252)
        
        sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if np.std(returns) > 0 else 0
        sortino = (np.mean(returns) / np.std(returns[returns < 0]) * np.sqrt(252)) if np.any(returns < 0) and np.std(returns[returns < 0]) > 0 else 0
        
        # Drawdown
        cumret = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumret)
        drawdown = (cumret - running_max) / running_max
        max_dd = np.min(drawdown)
        
        # Win rate
        win_rate = np.mean(returns > 0)
        
        # Avg trade return
        avg_trade = np.mean(returns)
        
        # Hit rate
        hit_rate = np.mean(returns > 0)
        
        # Avg gain/loss
        gains = returns[returns > 0]
        losses = returns[returns < 0]
        avg_gain = np.mean(gains) if len(gains) > 0 else 0
        avg_loss = np.mean(losses) if len(losses) > 0 else 0
        
        # Profit factor
        gross_profit = np.sum(gains) if len(gains) > 0 else 0
        gross_loss = abs(np.sum(losses)) if len(losses) > 0 else 1e-8
        profit_factor = gross_profit / gross_loss
        
        # Calmar
        calmar = (np.mean(returns) * 252) / abs(np.min(drawdown)) if np.min(drawdown) < 0 else 0
        
        return RegimePerformance(
            regime=regime,
            count=len(returns),
            total_return=float(np.prod(1 + returns) - 1),
            annualized_return=float(ann_ret),
            volatility=float(ann_vol),
            sharpe_ratio=float(sharpe),
            sortino_ratio=float(sortino),
            max_drawdown=float(np.min(drawdown)),
            win_rate=float(win_rate),
            avg_trade_return=float(avg_trade),
            hit_rate=float(hit_rate),
            avg_gain=float(avg_gain),
            avg_loss=float(avg_loss),
            profit_factor=float(profit_factor),
            calmar_ratio=float(calmar),
            duration_days=len(returns),
            avg_duration=float(len(returns)),
        )
    
    def _analyze_transitions(
        self,
        regimes: list[RegimeLabel],
        timestamps: pd.DatetimeIndex,
    ) -> list[TransitionAnalysis]:
        """Analyze regime transitions."""
        transitions = []
        
        # Find transition points
        transition_points = []
        for i in range(1, len(regimes)):
            if regimes[i] != regimes[i-1] and regimes[i] != RegimeLabel.UNKNOWN and regimes[i-1] != RegimeLabel.UNKNOWN:
                transition_points.append({
                    'from': regimes[i-1],
                    'to': regimes[i],
                    'index': i,
                    'timestamp': timestamps[i],
                })
        
        # Group by transition type
        transition_groups = defaultdict(list)
        for tp in transition_points:
            key = (tp['from'], tp['to'])
            transition_groups[key].append(tp)
        
        for (from_regime, to_regime), points in transition_groups.items():
            if len(points) < 2:
                continue
            
            # Analyze each transition
            returns_before = []
            returns_after = []
            durations_before = []
            durations_after = []
            
            for tp in points:
                idx = tp['index']
                # Look at returns before and after
                before_start = max(0, tp['index'] - 20)
                after_end = min(len(self._last_returns), tp['index'] + 20)
                
                if before_start < tp['index']:
                    before_rets = self._last_returns[before_start:tp['index']]
                    durations_before.append(len(before_rets))
                    returns_before.extend(before_rets)
                
                if tp['index'] < after_end:
                    after_rets = self._last_returns[tp['index']:after_end]
                    durations_after.append(len(after_rets))
                    returns_after.extend(after_rets)
            
            transitions.append(TransitionAnalysis(
                from_regime=from_regime,
                to_regime=to_regime,
                count=len(points),
                avg_duration_before=np.mean(durations_before) if durations_before else 0,
                avg_duration_after=np.mean(durations_after) if durations_after else 0,
                avg_return_before=np.mean(returns_before) if returns_before else 0,
                avg_return_after=np.mean(returns_after) if returns_after else 0,
                strategy_performance_delta=0,  # Would need strategy-specific data
                transition_sharpe=0,
                success_rate=0.5,
            ))
        
        return transitions
    
    def _check_consistency(
        self,
        regimes: list[RegimeLabel],
        performances: list['RegimePerformance'],
    ) -> tuple[float, dict[str, float]]:
        """Check consistency of performance across regimes."""
        if not performances:
            return 0.0, {}
        
        # Consistency = how similar are performances across regimes
        # High consistency = strategy works in all regimes
        
        scores = {}
        reg_names = [p.regime.value for p in performances]
        
        # Sharpe consistency
        sharpes = [p.sharpe_ratio for p in performances]
        if len(sharpes) > 1:
            sharpe_cv = np.std(sharpes) / (abs(np.mean(sharpes)) + 1e-8)
            scores['sharpe_consistency'] = max(0, 1 - sharpe_cv)
        
        # Return consistency
        returns = [p.annualized_return for p in performances]
        if len(returns) > 1:
            return_cv = np.std(returns) / (abs(np.mean(returns)) + 1e-8)
            scores['return_consistency'] = max(0, 1 - return_cv)
        
        # Drawdown consistency
        dds = [p.max_drawdown for p in performances]
        if len(dds) > 1:
            dd_cv = np.std(dds) / (abs(np.mean(dds)) + 1e-8)
            scores['drawdown_consistency'] = max(0, 1 - dd_cv)
        
        # Win rate consistency
        win_rates = [p.win_rate for p in performances]
        if len(win_rates) > 1:
            wr_cv = np.std(win_rates) / (np.mean(win_rates) + 1e-8)
            scores['win_rate_consistency'] = max(0, 1 - wr_cv)
        
        overall = np.mean(list(scores.values())) if scores else 0
        
        return overall, scores
    
    def _attribute_performance(self, performances: list['RegimePerformance']) -> dict[str, Any]:
        """Attribute overall performance to regimes."""
        if not performances:
            return {}
        
        total_weight = sum(p.count for p in performances)
        if total_weight == 0:
            return {}
        
        # Weighted average return
        weighted_return = sum(p.annualized_return * p.count for p in performances) / sum(p.count for p in performances)
        weighted_sharpe = sum(p.sharpe_ratio * p.count for p in performances) / total_weight
        weighted_dd = sum(p.max_drawdown * p.count for p in performances) / total_weight
        
        # Best/worst regimes
        best_regime = max(performances, key=lambda p: p.sharpe_ratio)
        worst_regime = min(performances, key=lambda p: p.sharpe_ratio)
        
        # Regime contribution
        regime_contrib = {}
        for p in performances:
            weight = p.count / sum(p.count for p in performances)
            regime_contrib[p.regime.value] = {
                'weight': weight,
                'contribution': p.annualized_return * weight,
                'sharpe': p.sharpe_ratio,
            }
        
        return {
            'weighted_return': float(weighted_return),
            'weighted_sharpe': float(weighted_sharpe),
            'weighted_max_dd': float(weighted_dd),
            'best_regime': best_regime.regime.value,
            'worst_regime': worst_regime.regime.value,
            'regime_contributions': regime_contrib,
            'regime_count': len(performances),
        }
    
    def _generate_report(
        self,
        performances: list['RegimePerformance'],
        transitions: list[TransitionAnalysis],
        consistency: float,
        consistency_scores: dict[str, float],
    ) -> RegimeValidationReport:
        """Generate final regime validation report."""
        # Determine overall pass/fail
        failures = []
        
        # Minimum regime consistency
        if consistency < self.config.min_regime_consistency:
            failures.append(f"Overall consistency {consistency:.1%} below minimum {self.config.min_regime_consistency:.0%}")
        
        # Check each regime meets minimums
        for p in self._regime_performances:
            if p.regime.value.startswith('bear') and p.sharpe_ratio < self.config.max_sharpe_bear:
                failures.append(f"Bear regime {p.regime.value} Sharpe {p.sharpe_ratio:.2f} below minimum {self.config.max_sharpe_bear}")
            if p.regime.value.startswith('bull') and p.sharpe_ratio < self.config.min_sharpe_bull:
                failures.append(f"Bull regime {p.regime.value} Sharpe {p.sharpe_ratio:.2f} below minimum {self.config.min_sharpe_bull}")
            if p.max_drawdown < self.config.max_drawdown_bear and p.regime.value.startswith('bear'):
                failures.append(f"Bear regime {p.regime.value} max DD {p.max_drawdown:.1%} exceeds limit {self.config.max_drawdown_bear:.0%}")
        
        # Transition analysis
        transition_analysis = {}
        if self.config.include_transition_analysis and self._transitions:
            transition_analysis = {
                'total_transitions': len(self._transitions),
                'avg_transitions_per_year': len(self._transitions) / (len(self._last_returns) / 252) if self._last_returns else 0,
                'most_common': max(
                    [(f"{t.from_regime.value}->{t.to_regime.value}", t.count) for t in self._transitions],
                    key=lambda x: x[1],
                    default=("none", 0),
                )[0],
            }
        
        # Regime attribution
        regime_attribution = {}
        if self.config.include_regime_attribution and self._regime_performances:
            regime_attribution = self._attribute_performance(self._regime_performances)
        
        passed = len(failures) == 0
        
        return RegimeValidationReport(
            config=RegimeConfig(),
            regime_performances=performances,
            transitions=transitions,
            overall_consistency=consistency,
            regime_consistency_scores=consistency_scores,
            transition_analysis=transition_analysis if self.config.include_transition_analysis else None,
            regime_attribution=regime_attribution if self.config.include_regime_attribution else None,
            passed=passed,
            failure_reasons=failures,
        )
    
    # Store for report generation
    _last_returns: np.ndarray = field(default_factory=lambda: np.array([]))
    _regime_performances: list = field(default_factory=list)
    _transitions: list = field(default_factory=list)


# Convenience function
async def quick_regime_validation(
    strategy_fn: Callable[[pd.DataFrame], dict[str, Any]],
    symbols: list[str],
    timeframe: str = "1D",
    returns: np.ndarray | None = None,
) -> 'RegimeValidationReport':
    """Quick regime validation with defaults."""
    config = RegimeConfig()
    validator = RegimeValidator(config)
    return await validator.run(strategy_fn, symbols, timeframe, returns)