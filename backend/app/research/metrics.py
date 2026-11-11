"""Metrics computation for research backtesting."""

from dataclasses import dataclass
from typing import List
import numpy as np
import pandas as pd

from backend.app.research.engine import Trade


@dataclass
class BacktestMetrics:
    """Aggregated backtest metrics."""
    
    # Trade counts
    n_trades: int
    n_winners: int
    n_losers: int
    
    # R-metrics
    r_net_mean: float
    r_net_median: float
    r_net_std: float
    r_net_sum: float
    
    # Win rate
    win_rate: float
    
    # P&L
    pnl_usd_sum: float
    pnl_usd_mean: float
    
    # Risk-adjusted
    sharpe: float
    sortino: float
    profit_factor: float
    
    # Drawdown
    max_drawdown_pct: float
    max_drawdown_usd: float
    
    # Time
    avg_bars_held: float
    median_bars_held: float
    
    # Exit reasons
    exit_reasons: dict
    
    # Censored trades
    n_censored: int
    censored_pct: float
    
    # Equity curve stats
    final_equity: float
    total_return_pct: float
    cagr: float
    volatility_annual: float
    
    # Benchmark comparison (vs buy & hold)
    alpha: float = 0.0
    beta: float = 0.0

    # Realized P&L over every trade, including forced data-end/EOD closes.
    # ``pnl_usd_sum`` above covers strategy exits only.
    pnl_usd_all: float = 0.0


def compute_metrics(
    trades: list[Trade],
    equity_curve: pd.Series,
    benchmark_returns: pd.Series | None = None,
    start_equity: float | None = None
) -> BacktestMetrics:
    """Compute comprehensive metrics from trades and equity curve.
    
    Args:
        trades: List of completed trades.
        equity_curve: Series of equity values indexed by date.
        benchmark_returns: Optional benchmark returns for alpha/beta.
        start_equity: Configured starting equity. Defaults to the first equity
            point when omitted.
        
    Returns:
        BacktestMetrics dataclass with all computed metrics.
    """
    if not trades:
        return BacktestMetrics(
            n_trades=0, n_winners=0, n_losers=0,
            r_net_mean=0, r_net_median=0, r_net_std=0, r_net_sum=0,
            win_rate=0, pnl_usd_sum=0, pnl_usd_mean=0,
            sharpe=0, sortino=0, profit_factor=0,
            max_drawdown_pct=0, max_drawdown_usd=0,
            avg_bars_held=0, median_bars_held=0,
            exit_reasons={}, n_censored=0, censored_pct=0,
            final_equity=0, total_return_pct=0, cagr=0, volatility_annual=0
        )
    
    # Filter non-censored trades
    closed_trades = [t for t in trades if not t.censored]
    censored_trades = [t for t in trades if t.censored]
    
    if not closed_trades:
        return BacktestMetrics(
            n_trades=0, n_winners=0, n_losers=0,
            r_net_mean=0, r_net_median=0, r_net_std=0, r_net_sum=0,
            win_rate=0, pnl_usd_sum=0, pnl_usd_mean=0,
            sharpe=0, sortino=0, profit_factor=0,
            max_drawdown_pct=0, max_drawdown_usd=0,
            avg_bars_held=0, median_bars_held=0,
            exit_reasons={}, n_censored=len(censored_trades), censored_pct=100,
            final_equity=equity_curve.iloc[-1] if len(equity_curve) > 0 else 0,
            total_return_pct=0, cagr=0, volatility_annual=0,
            pnl_usd_all=float(sum(t.pnl_usd for t in trades))
        )
    
    # R-metrics
    r_nets = np.array([t.r_net for t in closed_trades])
    r_net_mean = float(np.mean(r_nets))
    r_net_median = float(np.median(r_nets))
    r_net_std = float(np.std(r_nets, ddof=1)) if len(r_nets) > 1 else 0.0
    r_net_sum = float(np.sum(r_nets))
    
    # Win/loss
    winners = [t for t in closed_trades if t.r_net > 0]
    losers = [t for t in closed_trades if t.r_net < 0]
    n_winners = len(winners)
    n_losers = len(losers)
    n_trades = len(closed_trades)
    win_rate = n_winners / n_trades if n_trades > 0 else 0
    
    # P&L
    pnl_usd = np.array([t.pnl_usd for t in closed_trades])
    pnl_usd_sum = float(np.sum(pnl_usd))
    pnl_usd_mean = float(np.mean(pnl_usd))
    
    # Risk-adjusted
    sharpe = r_net_mean / r_net_std * np.sqrt(252) if r_net_std > 0 else 0
    
    # Sortino (downside deviation)
    downside = r_nets[r_nets < 0]
    downside_std = float(np.std(downside, ddof=1)) if len(downside) > 1 else 0.0
    sortino = r_net_mean / downside_std * np.sqrt(252) if downside_std > 0 else 0
    
    # Profit factor
    gross_profit = float(np.sum([t.r_net for t in winners]))
    gross_loss = float(abs(np.sum([t.r_net for t in losers])))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf if gross_profit > 0 else 0
    
    # Drawdown from equity curve
    if len(equity_curve) > 0:
        running_max = equity_curve.expanding().max()
        drawdown = equity_curve - running_max
        drawdown_pct = drawdown / running_max
        max_drawdown_pct = float(drawdown_pct.min() * 100)
        max_drawdown_usd = float(drawdown.min())
    else:
        max_drawdown_pct = 0.0
        max_drawdown_usd = 0.0
    
    # Time metrics
    bars_held = np.array([t.bars_held for t in closed_trades])
    avg_bars_held = float(np.mean(bars_held))
    median_bars_held = float(np.median(bars_held))
    
    # Exit reasons
    exit_reasons = {}
    for t in closed_trades:
        exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1
    
    # Censored
    n_censored = len(censored_trades)
    censored_pct = n_censored / len(trades) * 100 if trades else 0
    
    # Equity curve stats
    final_equity = float(equity_curve.iloc[-1]) if len(equity_curve) > 0 else 0
    if start_equity is not None and start_equity > 0:
        start_equity_value = float(start_equity)
    else:
        start_equity_value = float(equity_curve.iloc[0]) if len(equity_curve) > 0 else 0
    total_return_pct = (final_equity / start_equity_value - 1) * 100 if start_equity_value > 0 else 0
    
    # CAGR
    n_days = len(equity_curve)
    if n_days > 1:
        years = n_days / 252.0
        cagr = (final_equity / start_equity_value) ** (1 / years) - 1 if start_equity_value > 0 else 0
        cagr *= 100
    else:
        cagr = 0.0
    
    # Annualized volatility
    if n_days > 1:
        daily_returns = equity_curve.pct_change().dropna()
        volatility_annual = float(daily_returns.std() * np.sqrt(252) * 100)
    else:
        volatility_annual = 0.0
    
    # Alpha/Beta vs benchmark
    alpha = 0.0
    beta = 0.0
    if benchmark_returns is not None and len(benchmark_returns) > 1:
        # ``benchmark_returns`` is already a return series. Differencing it a
        # second time yields inf on any flat close (division by zero), which
        # silently left alpha/beta at zero; regress the returns as given.
        common_dates = equity_curve.index.intersection(benchmark_returns.index)
        if len(common_dates) > 10:
            strat_rets = equity_curve.loc[common_dates].pct_change()
            bench_rets = benchmark_returns.loc[common_dates]
            joined = pd.concat(
                [strat_rets.rename("strat"), bench_rets.rename("bench")], axis=1
            ).dropna()
            joined = joined[np.isfinite(joined).all(axis=1)]
            if len(joined) > 10:
                s = joined["strat"]
                b = joined["bench"]
                cov = np.cov(s, b)[0, 1]
                var_b = np.var(b, ddof=1)  # match np.cov's sample convention
                if np.isfinite(var_b) and var_b > 0:
                    beta = float(cov / var_b)
                    # Annualized alpha
                    alpha = float((s.mean() - beta * b.mean()) * 252 * 100)
    
    return BacktestMetrics(
        n_trades=n_trades,
        n_winners=n_winners,
        n_losers=n_losers,
        r_net_mean=r_net_mean,
        r_net_median=r_net_median,
        r_net_std=r_net_std,
        r_net_sum=r_net_sum,
        win_rate=win_rate,
        pnl_usd_sum=pnl_usd_sum,
        pnl_usd_mean=pnl_usd_mean,
        sharpe=sharpe,
        sortino=sortino,
        profit_factor=profit_factor if profit_factor != np.inf else 999.9,
        max_drawdown_pct=max_drawdown_pct,
        max_drawdown_usd=max_drawdown_usd,
        avg_bars_held=avg_bars_held,
        median_bars_held=median_bars_held,
        exit_reasons=exit_reasons,
        n_censored=n_censored,
        censored_pct=censored_pct,
        final_equity=final_equity,
        total_return_pct=total_return_pct,
        cagr=cagr,
        volatility_annual=volatility_annual,
        alpha=alpha,
        beta=beta,
        pnl_usd_all=float(sum(t.pnl_usd for t in trades))
    )


def print_metrics(metrics: BacktestMetrics, title: str = "Backtest Results") -> None:
    """Pretty print metrics."""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Trades:           {metrics.n_trades} (W: {metrics.n_winners}, L: {metrics.n_losers})")
    print(f"Win Rate:         {metrics.win_rate:.1%}")
    print(f"R-net Mean:       {metrics.r_net_mean:.3f}")
    print(f"R-net Median:     {metrics.r_net_median:.3f}")
    print(f"R-net Sum:        {metrics.r_net_sum:.3f}")
    print(f"R-net Std:        {metrics.r_net_std:.3f}")
    print(f"Sharpe (ann):     {metrics.sharpe:.2f}")
    print(f"Sortino (ann):    {metrics.sortino:.2f}")
    print(f"Profit Factor:    {metrics.profit_factor:.2f}")
    print(f"Max DD:           {metrics.max_drawdown_pct:.1f}% (${metrics.max_drawdown_usd:,.0f})")
    print(f"Total Return:     {metrics.total_return_pct:.1f}%")
    print(f"CAGR:             {metrics.cagr:.1f}%")
    print(f"Vol (ann):        {metrics.volatility_annual:.1f}%")
    print(f"Avg Bars Held:    {metrics.avg_bars_held:.1f}")
    print(f"Median Bars Held: {metrics.median_bars_held:.1f}")
    print(f"Censored:         {metrics.n_censored} ({metrics.censored_pct:.1f}%)")
    print(f"Final Equity:     ${metrics.final_equity:,.0f}")
    print(f"Exit Reasons:     {metrics.exit_reasons}")
    if metrics.alpha != 0 or metrics.beta != 0:
        print(f"Alpha (ann):      {metrics.alpha:.1f}%")
        print(f"Beta:             {metrics.beta:.2f}")
    print(f"{'='*60}")


def metrics_to_dict(metrics: BacktestMetrics) -> dict:
    """Convert metrics to dictionary for serialization."""
    return {
        "n_trades": metrics.n_trades,
        "n_winners": metrics.n_winners,
        "n_losers": metrics.n_losers,
        "r_net_mean": metrics.r_net_mean,
        "r_net_median": metrics.r_net_median,
        "r_net_std": metrics.r_net_std,
        "r_net_sum": metrics.r_net_sum,
        "win_rate": metrics.win_rate,
        "pnl_usd_sum": metrics.pnl_usd_sum,
        "pnl_usd_mean": metrics.pnl_usd_mean,
        "sharpe": metrics.sharpe,
        "sortino": metrics.sortino,
        "profit_factor": metrics.profit_factor,
        "max_drawdown_pct": metrics.max_drawdown_pct,
        "max_drawdown_usd": metrics.max_drawdown_usd,
        "avg_bars_held": metrics.avg_bars_held,
        "median_bars_held": metrics.median_bars_held,
        "exit_reasons": metrics.exit_reasons,
        "n_censored": metrics.n_censored,
        "censored_pct": metrics.censored_pct,
        "final_equity": metrics.final_equity,
        "total_return_pct": metrics.total_return_pct,
        "cagr": metrics.cagr,
        "volatility_annual": metrics.volatility_annual,
        "alpha": metrics.alpha,
        "beta": metrics.beta,
        "pnl_usd_all": metrics.pnl_usd_all
    }