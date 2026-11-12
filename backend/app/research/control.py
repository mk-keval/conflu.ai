"""Control/random baseline for research backtesting."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from backend.app.research.engine import (
    run_portfolio,
    ExitRules,
    PortfolioRules,
    Trade,
    NON_TRADABLE,
)
from backend.app.research.metrics import compute_metrics, BacktestMetrics
from backend.app.research.data import download_daily, load_universe
from backend.app.research.setups import eligible


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
        if symbol in NON_TRADABLE:
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
        if symbol in NON_TRADABLE:
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
        if symbol in NON_TRADABLE:
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


def matched_random_signals(
    data: dict[str, pd.DataFrame],
    real_signals: dict[str, pd.Series],
    seed: int,
    elig: pd.DataFrame | None = None,
) -> dict[str, pd.Series]:
    """Random control matched to the strategy's daily entry count.

    For every date on which the strategy fires, the control fires the same
    number of signals on a random sample of symbols that are liquid and have
    valid indicators on that date. This replaces the old control, which fired
    on 2% of every symbol every day regardless of eligibility.

    Args:
        data: Market data.
        real_signals: Real signals to match.
        seed: Random seed.
        elig: Optional precomputed eligibility frame (columns = tradable
            symbols, index = union of all dates).

    Returns:
        Dict of symbol -> boolean Series reindexed to that symbol's own index.
        Non-tradable symbols get an all-False Series.
    """
    tradable = sorted(s for s in data if s not in NON_TRADABLE)

    if elig is None:
        union = pd.DatetimeIndex(
            sorted({d for s in tradable for d in data[s].index})
        )
        elig = pd.DataFrame(
            {
                s: eligible(data[s]).reindex(union, fill_value=False).astype(bool)
                for s in tradable
            },
            index=union,
        )

    index = elig.index
    counts = pd.Series(0, index=index, dtype=int)
    for symbol in tradable:
        real_sig = real_signals.get(symbol)
        if real_sig is None:
            continue
        aligned = real_sig.reindex(index, fill_value=False).fillna(False).astype(bool)
        counts = counts + aligned.astype(int)

    rng = np.random.default_rng(seed)
    marks = pd.DataFrame(False, index=index, columns=tradable, dtype=bool)

    for date in index[counts.to_numpy() > 0]:
        pool = elig.columns[elig.loc[date].to_numpy(dtype=bool)].tolist()
        k = min(int(counts.loc[date]), len(pool))
        if k <= 0:
            continue
        chosen = rng.choice(pool, size=k, replace=False)
        marks.loc[date, chosen] = True

    signals = {}
    for symbol, df in data.items():
        if symbol in NON_TRADABLE:
            signals[symbol] = pd.Series(False, index=df.index)
        else:
            signals[symbol] = marks[symbol].reindex(df.index, fill_value=False)
    return signals


def run_control_suite(
    data: dict[str, pd.DataFrame],
    real_signals: dict[str, pd.Series],
    exit_rules: ExitRules,
    portfolio_rules: PortfolioRules,
    n_matched: int = 30,
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
        n_matched: Number of matched-random runs (same daily entry count as
            the strategy, random eligible symbol).
        n_random: Number of random signal runs.
        n_permuted: Number of permuted signal runs.
        n_shifted: Number of time-shifted runs (positive shifts).
        base_seed: Base seed for reproducibility.
        
    Returns:
        Dict with 'matched_random', 'random', 'permuted', 'shifted' lists.
    """
    results = {
        "matched_random": [],
        "random": [],
        "permuted": [],
        "shifted": []
    }

    # Eligibility depends only on the panel, so build it once.
    tradable = sorted(s for s in data if s not in NON_TRADABLE)
    union = pd.DatetimeIndex(sorted({d for s in tradable for d in data[s].index}))
    elig = pd.DataFrame(
        {
            s: eligible(data[s]).reindex(union, fill_value=False).astype(bool)
            for s in tradable
        },
        index=union,
    )

    # Matched random signals (same entry count per day, random eligible symbol)
    for i in range(n_matched):
        seed = base_seed + 30000 + i
        signals = matched_random_signals(data, real_signals, seed, elig=elig)
        trades, equity = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=seed)
        metrics = compute_metrics(trades, equity)
        results["matched_random"].append(ControlResult(
            name=f"matched_random_{i}",
            seed=seed,
            trades=trades,
            equity=equity,
            metrics=metrics
        ))

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
    """Compute one-sided p-values vs control distributions.

    The p-value always answers the same question: how often does a control do
    at least as well as the real strategy? It is ``p_raw = mean(control >=
    real)`` followed by the finite-sample correction ``p = (p_raw*n + 1)/(n +
    1)``. The direction is never flipped for negative results.
    
    Args:
        real_metrics: Metrics from real signals.
        control_results: Results from control suite.
        metric_name: Which metric to test (e.g., 'r_net_mean', 'sharpe').
        
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
        
        # One-sided: proportion of controls at least as good as the real result.
        p = np.mean(control_values >= real_value)
            
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