"""Control/random baseline for research backtesting."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from backend.app.research.engine import run_portfolio, ExitRules, PortfolioRules, Trade
from backend.app.research.metrics import compute_metrics, BacktestMetrics
from backend.app.research.data import download_daily, load_universe


@dataclass
class ControlResult:
    """Result of a control run."""
    name: str
    seed: int
    trades: list[Trade]
    equity: pd.Series
    metrics: BacktestMetrics


def random_signals(
    data: dict[str, pd.DataFrame],
    signal_prob: float = 0.02,
    seed: int = 42,
    min_bars: int = 30
) -> dict[str, pd.Series]:
    """Generate random signals with given probability.
    
    Args:
        data: Dict of symbol -> DataFrame with OHLCV and indicators.
        signal_prob: Probability of signal per symbol per day.
        seed: Random seed.
        min_bars: Minimum bars before signals can start (warmup).
        
    Returns:
        Dict of symbol -> boolean Series (True = signal at close).
    """
    rng = np.random.default_rng(seed)
    signals = {}
    
    for symbol, df in data.items():
        if symbol in ("SPY", "VIX"):
            signals[symbol] = pd.Series(False, index=df.index)
            continue
            
        n = len(df)
        sig = np.zeros(n, dtype=bool)
        
        # No signals during warmup
        if n > min_bars:
            # Random signals after warmup
            random_mask = rng.random(n - min_bars) < signal_prob
            sig[min_bars:] = random_mask
        
        signals[symbol] = pd.Series(sig, index=df.index)
    
    return signals


def permuted_signals(
    data: dict[str, pd.DataFrame],
    real_signals: dict[str, pd.Series],
    seed: int = 42
) -> dict[str, pd.Series]:
    """Generate signals by permuting real signal dates (preserves frequency).
    
    Args:
        data: Dict of symbol -> DataFrame with OHLCV and indicators.
        real_signals: Real signals to permute.
        seed: Random seed.
        
    Returns:
        Dict of symbol -> permuted boolean Series.
    """
    rng = np.random.default_rng(seed)
    signals = {}
    
    for symbol, df in data.items():
        if symbol in ("SPY", "VIX"):
            signals[symbol] = pd.Series(False, index=df.index)
            continue
            
        real_sig = real_signals.get(symbol, pd.Series(False, index=df.index))
        signal_dates = real_sig[real_sig].index
        
        if len(signal_dates) == 0:
            signals[symbol] = pd.Series(False, index=df.index)
            continue
        
        # Permute signal dates across available dates (after warmup)
        available_dates = df.index[30:]  # After warmup
        if len(available_dates) < len(signal_dates):
            # Not enough dates, just use what we have
            permuted = rng.choice(available_dates, size=len(signal_dates), replace=False)
        else:
            permuted = rng.choice(available_dates, size=len(signal_dates), replace=False)
        
        sig = pd.Series(False, index=df.index)
        sig.loc[permuted] = True
        signals[symbol] = sig
    
    return signals


def time_shifted_signals(
    data: dict[str, pd.DataFrame],
    real_signals: dict[str, pd.Series],
    shift_bars: int = 20
) -> dict[str, pd.Series]:
    """Generate signals by time-shifting real signals (breaks temporal relationship).
    
    Args:
        data: Dict of symbol -> DataFrame with OHLCV and indicators.
        real_signals: Real signals to shift.
        shift_bars: Number of bars to shift (positive = future, negative = past).
        
    Returns:
        Dict of symbol -> shifted boolean Series.
    """
    signals = {}
    
    for symbol, df in data.items():
        if symbol in ("SPY", "VIX"):
            signals[symbol] = pd.Series(False, index=df.index)
            continue
            
        real_sig = real_signals.get(symbol, pd.Series(False, index=df.index))
        signal_dates = real_sig[real_sig].index
        
        if len(signal_dates) == 0:
            signals[symbol] = pd.Series(False, index=df.index)
            continue
        
        # Shift dates
        date_to_idx = {d: i for i, d in enumerate(df.index)}
        shifted_dates = []
        
        for d in signal_dates:
            if d in date_to_idx:
                new_idx = date_to_idx[d] + shift_bars
                if 0 <= new_idx < len(df.index):
                    shifted_dates.append(df.index[new_idx])
        
        sig = pd.Series(False, index=df.index)
        sig.loc[shifted_dates] = True
        signals[symbol] = sig
    
    return signals


def run_control_suite(
    data: dict[str, pd.DataFrame],
    real_signals: dict[str, pd.Series],
    exit_rules: ExitRules,
    portfolio_rules: PortfolioRules,
    n_random: int = 100,
    n_permuted: int = 50,
    n_shifted: int = 5,
    base_seed: int = 42
) -> dict[str, list[ControlResult]]:
    """Run full control suite.
    
    Args:
        data: Market data.
        real_signals: Real signals from setups.
        exit_rules: Exit rules.
        portfolio_rules: Portfolio rules.
        n_random: Number of random signal runs.
        n_permuted: Number of permuted signal runs.
        n_shifted: Number of time-shifted runs (positive shifts).
        base_seed: Base seed for reproducibility.
        
    Returns:
        Dict with 'random', 'permuted', 'shifted' lists of ControlResult.
    """
    results = {
        "random": [],
        "permuted": [],
        "shifted": []
    }
    
    # Random signals
    for i in range(n_random):
        seed = base_seed + i
        signals = random_signals(data, signal_prob=0.02, seed=seed)
        trades, equity = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=seed)
        metrics = compute_metrics(trades, equity)
        results["random"].append(ControlResult(
            name=f"random_{i}",
            seed=seed,
            trades=trades,
            equity=equity,
            metrics=metrics
        ))
    
    # Permuted signals (preserve signal frequency per symbol)
    for i in range(n_permuted):
        seed = base_seed + 10000 + i
        signals = permuted_signals(data, real_signals, seed=seed)
        trades, equity = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=seed)
        metrics = compute_metrics(trades, equity)
        results["permuted"].append(ControlResult(
            name=f"permuted_{i}",
            seed=seed,
            trades=trades,
            equity=equity,
            metrics=metrics
        ))
    
    # Time-shifted signals (breaks alpha, keeps market regime)
    for i in range(n_shifted):
        shift = 20 + i * 10  # 20, 30, 40, 50, 60 bars forward
        seed = base_seed + 20000 + i
        signals = time_shifted_signals(data, real_signals, shift_bars=shift)
        trades, equity = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=seed)
        metrics = compute_metrics(trades, equity)
        results["shifted"].append(ControlResult(
            name=f"shifted_{shift}bars",
            seed=seed,
            trades=trades,
            equity=equity,
            metrics=metrics
        ))
    
    return results


def compute_control_pvalues(
    real_metrics: BacktestMetrics,
    control_results: dict[str, list[ControlResult]],
    metric_name: str = "r_net_sum"
) -> dict[str, float]:
    """Compute p-values vs control distributions.
    
    Args:
        real_metrics: Metrics from real signals.
        control_results: Results from control suite.
        metric_name: Which metric to test (e.g., 'r_net_sum', 'sharpe', 'total_return_pct').
        
    Returns:
        Dict of control_type -> p_value.
    """
    real_value = getattr(real_metrics, metric_name)
    pvalues = {}
    
    for control_type, results in control_results.items():
        if not results:
            pvalues[control_type] = 1.0
            continue
            
        control_values = [getattr(r.metrics, metric_name) for r in results]
        control_values = np.array(control_values)
        
        # One-sided p-value: proportion of control >= real (for positive metrics)
        # If real is negative, we'd test proportion <= real
        if real_value >= 0:
            p = np.mean(control_values >= real_value)
        else:
            p = np.mean(control_values <= real_value)
            
        # Add 1/(n+1) correction for finite samples
        n = len(control_values)
        p = (p * n + 1) / (n + 1)
        
        pvalues[control_type] = float(p)
    
    return pvalues


def summarize_control_results(control_results: dict[str, list[ControlResult]]) -> pd.DataFrame:
    """Summarize control results as DataFrame."""
    rows = []
    for control_type, results in control_results.items():
        if not results:
            continue
        for r in results:
            rows.append({
                "type": control_type,
                "name": r.name,
                "seed": r.seed,
                "n_trades": r.metrics.n_trades,
                "win_rate": r.metrics.win_rate,
                "r_net_sum": r.metrics.r_net_sum,
                "r_net_mean": r.metrics.r_net_mean,
                "sharpe": r.metrics.sharpe,
                "total_return_pct": r.metrics.total_return_pct,
                "max_drawdown_pct": r.metrics.max_drawdown_pct,
                "cagr": r.metrics.cagr
            })
    
    return pd.DataFrame(rows)