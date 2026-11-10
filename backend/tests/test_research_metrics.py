"""Tests for research metrics."""

import numpy as np
import pandas as pd
import pytest

from backend.app.research.metrics import compute_metrics, print_metrics, metrics_to_dict, BacktestMetrics
from backend.app.research.engine import Trade


def _make_test_trades(n=10, seed=42) -> list[Trade]:
    """Create test trades with known properties."""
    np.random.seed(seed)
    trades = []
    
    base_date = pd.Timestamp("2020-01-01")
    
    for i in range(n):
        # Alternate winners and losers
        is_winner = i % 2 == 0
        r_net = 1.5 if is_winner else -1.0
        entry_price = 100.0
        stop = 95.0
        target = 107.5 if is_winner else 95.0
        
        if is_winner:
            exit_price = 107.5
        else:
            exit_price = 95.0
            
        shares = 100
        pnl = shares * (exit_price - entry_price)
        
        trade = Trade(
            symbol=f"STK{i}",
            signal_date=base_date + pd.Timedelta(days=i*5),
            entry_date=base_date + pd.Timedelta(days=i*5 + 1),
            entry_price=entry_price,
            stop=stop,
            target=target,
            shares=shares,
            exit_date=base_date + pd.Timedelta(days=i*5 + 6),
            exit_price=exit_price,
            exit_reason="target" if is_winner else "stop",
            bars_held=5,
            r_gross=r_net,
            r_net=r_net,
            pnl_usd=pnl,
            censored=False
        )
        trades.append(trade)
    
    return trades


def _make_equity_curve(trades: list[Trade], start_equity=100000) -> pd.Series:
    """Create equity curve from trades."""
    dates = []
    equity = []
    current_equity = start_equity
    
    # Add initial point
    dates.append(trades[0].entry_date - pd.Timedelta(days=1))
    equity.append(current_equity)
    
    for t in trades:
        if not t.censored:
            current_equity += t.pnl_usd
            dates.append(t.exit_date)
            equity.append(current_equity)
    
    return pd.Series(equity, index=pd.DatetimeIndex(dates), name="equity")


def test_compute_metrics_basic():
    """Test basic metrics computation."""
    trades = _make_test_trades(10)
    equity = _make_equity_curve(trades)
    
    metrics = compute_metrics(trades, equity)
    
    assert metrics.n_trades == 10
    assert metrics.n_winners == 5
    assert metrics.n_losers == 5
    assert metrics.win_rate == 0.5
    
    # R-net: 5 * 1.5 + 5 * (-1.0) = 7.5 - 5.0 = 2.5
    assert abs(metrics.r_net_sum - 2.5) < 0.01
    assert abs(metrics.r_net_mean - 0.25) < 0.01
    
    # P&L: 5 * 750 + 5 * (-500) = 3750 - 2500 = 1250
    assert abs(metrics.pnl_usd_sum - 1250) < 1


def test_compute_metrics_empty():
    """Test metrics with empty trades."""
    trades = []
    equity = pd.Series([100000], index=pd.DatetimeIndex([pd.Timestamp("2020-01-01")]))
    
    metrics = compute_metrics(trades, equity)
    
    assert metrics.n_trades == 0
    assert metrics.win_rate == 0
    assert metrics.r_net_sum == 0


def test_compute_metrics_all_winners():
    """Test metrics with all winning trades."""
    np.random.seed(42)
    trades = []
    base_date = pd.Timestamp("2020-01-01")
    
    for i in range(5):
        trade = Trade(
            symbol=f"STK{i}",
            signal_date=base_date + pd.Timedelta(days=i*5),
            entry_date=base_date + pd.Timedelta(days=i*5 + 1),
            entry_price=100.0,
            stop=95.0,
            target=107.5,
            shares=100,
            exit_date=base_date + pd.Timedelta(days=i*5 + 6),
            exit_price=107.5,
            exit_reason="target",
            bars_held=5,
            r_gross=1.5,
            r_net=1.5,
            pnl_usd=750.0,
            censored=False
        )
        trades.append(trade)
    
    equity = _make_equity_curve(trades)
    metrics = compute_metrics(trades, equity)
    
    assert metrics.n_winners == 5
    assert metrics.n_losers == 0
    assert metrics.win_rate == 1.0
    assert metrics.profit_factor == 999.9  # Infinite, capped


def test_compute_metrics_all_losers():
    """Test metrics with all losing trades."""
    np.random.seed(42)
    trades = []
    base_date = pd.Timestamp("2020-01-01")
    
    for i in range(5):
        trade = Trade(
            symbol=f"STK{i}",
            signal_date=base_date + pd.Timedelta(days=i*5),
            entry_date=base_date + pd.Timedelta(days=i*5 + 1),
            entry_price=100.0,
            stop=95.0,
            target=107.5,
            shares=100,
            exit_date=base_date + pd.Timedelta(days=i*5 + 6),
            exit_price=95.0,
            exit_reason="stop",
            bars_held=5,
            r_gross=-1.0,
            r_net=-1.0,
            pnl_usd=-500.0,
            censored=False
        )
        trades.append(trade)
    
    equity = _make_equity_curve(trades)
    metrics = compute_metrics(trades, equity)
    
    assert metrics.n_winners == 0
    assert metrics.n_losers == 5
    assert metrics.win_rate == 0.0
    assert metrics.profit_factor == 0.0


def test_compute_metrics_with_censored():
    """Test metrics with censored trades."""
    trades = _make_test_trades(8)
    
    # Add 2 censored trades
    base_date = pd.Timestamp("2020-01-01")
    for i in range(2):
        trade = Trade(
            symbol=f"STK_C{i}",
            signal_date=base_date + pd.Timedelta(days=50 + i*5),
            entry_date=base_date + pd.Timedelta(days=51 + i*5),
            entry_price=100.0,
            stop=95.0,
            target=107.5,
            shares=100,
            exit_date=base_date + pd.Timedelta(days=56 + i*5),
            exit_price=102.0,
            exit_reason="eod_censored",
            bars_held=5,
            r_gross=0.4,
            r_net=0.4,
            pnl_usd=200.0,
            censored=True
        )
        trades.append(trade)
    
    equity = _make_equity_curve(trades)
    metrics = compute_metrics(trades, equity)
    
    assert metrics.n_trades == 8  # Only non-censored
    assert metrics.n_censored == 2
    assert metrics.censored_pct == 20.0  # 2/10 * 100


def test_sharpe_calculation():
    """Test Sharpe ratio calculation."""
    trades = _make_test_trades(20)
    equity = _make_equity_curve(trades)
    
    metrics = compute_metrics(trades, equity)
    
    # Sharpe should be computable
    assert not np.isnan(metrics.sharpe)
    assert not np.isinf(metrics.sharpe)


def test_sortino_calculation():
    """Test Sortino ratio calculation."""
    trades = _make_test_trades(20)
    equity = _make_equity_curve(trades)
    
    metrics = compute_metrics(trades, equity)
    
    # Sortino should be computable
    assert not np.isnan(metrics.sortino)
    assert not np.isinf(metrics.sortino)


def test_max_drawdown():
    """Test max drawdown calculation."""
    # Create equity curve with known drawdown
    dates = pd.date_range("2020-01-01", periods=10, freq="D")
    equity_vals = [100000, 105000, 110000, 108000, 102000, 98000, 95000, 100000, 103000, 108000]
    equity = pd.Series(equity_vals, index=dates)
    
    trades = _make_test_trades(5)
    metrics = compute_metrics(trades, equity)
    
    # Peak at 110000, trough at 95000 -> DD = (95000-110000)/110000 = -13.6%
    assert abs(metrics.max_drawdown_pct - (-13.63)) < 0.5


def test_cagr_calculation():
    """Test CAGR calculation."""
    # 2 years of data, 20% total return
    dates = pd.date_range("2020-01-01", periods=504, freq="D")  # ~2 years
    equity_vals = np.linspace(100000, 120000, 504)
    equity = pd.Series(equity_vals, index=dates)
    
    trades = _make_test_trades(10)
    metrics = compute_metrics(trades, equity)
    
    # CAGR = (1.2)^(1/2) - 1 = 9.54%
    assert abs(metrics.cagr - 9.54) < 0.5


def test_metrics_to_dict():
    """Test metrics serialization to dict."""
    trades = _make_test_trades(5)
    equity = _make_equity_curve(trades)
    
    metrics = compute_metrics(trades, equity)
    d = metrics_to_dict(metrics)
    
    assert isinstance(d, dict)
    assert d["n_trades"] == 5
    assert "r_net_mean" in d
    assert "sharpe" in d
    assert "exit_reasons" in d


def test_alpha_beta():
    """Test alpha/beta calculation."""
    trades = _make_test_trades(20)
    equity = _make_equity_curve(trades)
    
    # Create benchmark returns (SPY-like)
    dates = equity.index
    bench_returns = pd.Series(np.random.randn(len(dates)) * 0.01, index=dates)
    
    metrics = compute_metrics(trades, equity, benchmark_returns=bench_returns)
    
    # Alpha and beta should be computed
    assert not np.isnan(metrics.alpha)
    assert not np.isnan(metrics.beta)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])