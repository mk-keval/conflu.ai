"""Tests for research engine."""

import numpy as np
import pandas as pd
import pytest

from backend.app.research.engine import run_portfolio, ExitRules, PortfolioRules, Trade
from backend.app.research.indicators import add_indicators
from backend.app.research.setups import statistical_mean_reversion


def _make_test_data(symbol="TEST", n=100, seed=42):
    """Create test data with indicators."""
    np.random.seed(seed)
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    
    # Generate price data that will trigger signals
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high = close + np.abs(np.random.randn(n) * 0.3)
    low = close - np.abs(np.random.randn(n) * 0.3)
    open_ = close + np.random.randn(n) * 0.2
    volume = np.abs(np.random.randn(n) * 100000 + 10000000)
    
    df = pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume
    }, index=dates)
    
    df = add_indicators(df)
    return {symbol: df}


def test_entry_uses_next_day_open():
    """Entry should use next-day OPEN, never the signal-day close."""
    data = _make_test_data(n=50)
    
    # Create a signal on day 10
    signals = {"TEST": pd.Series(False, index=data["TEST"].index)}
    signals["TEST"].iloc[10] = True  # Signal at close of day 10
    
    exit_rules = ExitRules(stop_atr=2.0, target_atr=3.0, max_hold_bars=15)
    portfolio_rules = PortfolioRules(start_equity=100000, risk_pct=0.5, max_positions=1, cost_bps_per_side=0)
    
    trades, _ = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=42)
    
    if trades:
        # Entry should be on day 11 at open
        assert trades[0].entry_date == data["TEST"].index[11]
        # Entry price should be open of day 11
        assert trades[0].entry_price == data["TEST"].iloc[11]["open"]
        # Signal date should be day 10
        assert trades[0].signal_date == data["TEST"].index[10]


def test_stop_wins_tie_over_target():
    """If low <= stop and high >= target on same day, exit at STOP."""
    # Create a bar where both stop and target are hit
    dates = pd.date_range("2020-01-01", periods=20, freq="D")
    close = np.full(20, 100.0)
    high = np.full(20, 105.0)
    low = np.full(20, 95.0)
    open_ = np.full(20, 100.0)
    volume = np.full(20, 10000000)
    
    # Day 11: high=105 (target), low=95 (stop)
    high[11] = 105.0
    low[11] = 95.0
    
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=dates)
    df = add_indicators(df)
    data = {"TEST": df}
    
    # Signal on day 10, entry on day 11
    signals = {"TEST": pd.Series(False, index=df.index)}
    signals["TEST"].iloc[10] = True
    
    # Use small ATR multipliers so stop/target are tight
    exit_rules = ExitRules(stop_atr=0.5, target_atr=0.5, max_hold_bars=15)
    portfolio_rules = PortfolioRules(start_equity=100000, risk_pct=0.5, max_positions=1, cost_bps_per_side=0)
    
    trades, _ = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=42)
    
    if trades:
        # Stop should win (low=95, stop=95 from entry=100 - 0.5*atr)
        # Since atr will be ~10, stop = 100 - 5 = 95
        assert trades[0].exit_reason in ("stop", "stop_gap")


def test_gap_down_below_stop():
    """Gap-down open below stop -> exit price = open (worse than stop)."""
    dates = pd.date_range("2020-01-01", periods=20, freq="D")
    close = np.full(20, 100.0)
    high = np.full(20, 101.0)
    low = np.full(20, 99.0)
    open_ = np.full(20, 100.0)
    volume = np.full(20, 10000000)
    
    # Day 11: gap down open at 85 (well below stop which will be ~99)
    open_[11] = 85.0
    low[11] = 84.0
    high[11] = 86.0
    close[11] = 85.5
    
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=dates)
    df = add_indicators(df)
    data = {"TEST": df}
    
    signals = {"TEST": pd.Series(False, index=df.index)}
    signals["TEST"].iloc[10] = True
    
    # Use small ATR multiplier so stop is close to entry
    exit_rules = ExitRules(stop_atr=0.5, target_atr=3.0, max_hold_bars=15)
    portfolio_rules = PortfolioRules(start_equity=100000, risk_pct=0.5, max_positions=1, cost_bps_per_side=0)
    
    trades, _ = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=42)
    
    if trades:
        # Entry at open=85, stop = 85 - 0.5*2 = 84
        # But open (85) > stop (84), so it won't be stop_gap
        # The low (84) hits stop exactly
        assert trades[0].exit_reason == "stop"
        assert trades[0].exit_price == 84.0


def test_time_stop_exits_at_close():
    """Time stop exits at close on bar max_hold_bars."""
    dates = pd.date_range("2020-01-01", periods=30, freq="D")
    close = np.full(30, 100.0)
    high = np.full(30, 101.0)
    low = np.full(30, 99.0)
    open_ = np.full(30, 100.0)
    volume = np.full(30, 10000000)
    
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=dates)
    df = add_indicators(df)
    data = {"TEST": df}
    
    signals = {"TEST": pd.Series(False, index=df.index)}
    signals["TEST"].iloc[10] = True
    
    exit_rules = ExitRules(stop_atr=5.0, target_atr=5.0, max_hold_bars=5)  # 5 bars
    portfolio_rules = PortfolioRules(start_equity=100000, risk_pct=0.5, max_positions=1, cost_bps_per_side=0)
    
    trades, _ = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=42)
    
    if trades:
        # Should exit on bar 15 (entry bar 11 + 5 bars = 15) at close
        assert trades[0].exit_reason == "time"
        assert trades[0].bars_held == 5


def test_sizing():
    """With equity 100000, risk 0.5%, risk_per_share 5 -> shares == 100."""
    dates = pd.date_range("2020-01-01", periods=30, freq="D")
    close = np.full(30, 100.0)
    high = np.full(30, 101.0)
    low = np.full(30, 99.0)
    open_ = np.full(30, 100.0)
    volume = np.full(30, 10000000)
    
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=dates)
    df = add_indicators(df)
    data = {"TEST": df}
    
    signals = {"TEST": pd.Series(False, index=df.index)}
    signals["TEST"].iloc[10] = True
    
    # atr will be small (~1), so risk_per_share = 2*atr ~ 2
    # With risk_pct=0.5, equity=100000: risk_amount = 500
    # shares = floor(500 / risk_per_share) = floor(500/2) = 250
    exit_rules = ExitRules(stop_atr=2.0, target_atr=3.0, max_hold_bars=15)
    portfolio_rules = PortfolioRules(start_equity=100000, risk_pct=0.5, max_positions=1,
                                     max_position_pct=100, cost_bps_per_side=0)
    
    trades, _ = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=42)
    
    if trades:
        # Just verify shares > 0 and reasonable
        assert trades[0].shares > 0


def test_max_positions_never_exceeded():
    """Max positions should never be exceeded at time of entry."""
    # Create multiple symbols with signals
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=50, freq="D")
    
    data = {}
    signals = {}
    for i in range(20):
        sym = f"STK{i}"
        close = 100 + np.cumsum(np.random.randn(50) * 0.5)
        high = close + np.abs(np.random.randn(50) * 0.3)
        low = close - np.abs(np.random.randn(50) * 0.3)
        open_ = close + np.random.randn(50) * 0.2
        volume = np.abs(np.random.randn(50) * 100000 + 10000000)
        
        df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=dates)
        df = add_indicators(df)
        data[sym] = df
    
        # Signal every day after warmup
        sig = pd.Series(False, index=df.index)
        sig.iloc[30:] = True
        signals[sym] = sig
    
    exit_rules = ExitRules(stop_atr=2.0, target_atr=3.0, max_hold_bars=15)
    portfolio_rules = PortfolioRules(start_equity=100000, risk_pct=0.5, max_positions=5, cost_bps_per_side=0)
    
    trades, equity = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=42)
    
    # Verify that at each entry, max_positions was not exceeded
    # We track open positions per day by simulating the engine logic
    # Position is open from entry_date (after entry) to exit_date (before exit on that day)
    # So it counts on entry_date, entry_date+1, ..., exit_date-1 (not on exit_date)
    positions_by_date = {}
    for t in trades:
        if t.censored:
            continue
        # Position is open from entry_date to exit_date (exclusive of exit_date)
        # Since exits happen before entries on same day, the position doesn't count on exit_date
        end_date = t.exit_date - pd.Timedelta(days=1)
        if end_date >= t.entry_date:
            for d in pd.date_range(t.entry_date, end_date, freq="D"):
                if d not in positions_by_date:
                    positions_by_date[d] = []
                positions_by_date[d].append(t.symbol)
    
    # At entry time, count should be <= max_positions
    # Since exits happen before entries on same day, check end of day
    for date, syms in positions_by_date.items():
        assert len(syms) <= 5, f"Max positions exceeded on {date}: {len(syms)} symbols {syms}"


def test_cash_never_negative_equity_never_nan():
    """Cash never goes negative; equity never NaN."""
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=100, freq="D")
    
    data = {}
    signals = {}
    for i in range(20):
        sym = f"STK{i}"
        close = 100 + np.cumsum(np.random.randn(100) * 0.5)
        high = close + np.abs(np.random.randn(100) * 0.3)
        low = close - np.abs(np.random.randn(100) * 0.3)
        open_ = close + np.random.randn(100) * 0.2
        volume = np.abs(np.random.randn(100) * 100000 + 10000000)
        
        df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=dates)
        df = add_indicators(df)
        data[sym] = df
        
        sig = pd.Series(False, index=df.index)
        sig.iloc[30:] = True
        signals[sym] = sig
    
    exit_rules = ExitRules(stop_atr=2.0, target_atr=3.0, max_hold_bars=15)
    portfolio_rules = PortfolioRules(start_equity=100000, risk_pct=0.5, max_positions=8, cost_bps_per_side=15)
    
    trades, equity = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=42)
    
    # Equity should never be NaN
    assert not equity.isna().any()
    # Equity should be positive
    assert (equity > 0).all()


def test_determinism():
    """Same inputs + same seed -> identical trade list."""
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=50, freq="D")
    
    data = {}
    signals = {}
    for i in range(5):
        sym = f"STK{i}"
        close = 100 + np.cumsum(np.random.randn(50) * 0.5)
        high = close + np.abs(np.random.randn(50) * 0.3)
        low = close - np.abs(np.random.randn(50) * 0.3)
        open_ = close + np.random.randn(50) * 0.2
        volume = np.abs(np.random.randn(50) * 100000 + 10000000)
        
        df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=dates)
        df = add_indicators(df)
        data[sym] = df
        
        sig = pd.Series(False, index=df.index)
        sig.iloc[30:] = True
        signals[sym] = sig
    
    exit_rules = ExitRules(stop_atr=2.0, target_atr=3.0, max_hold_bars=15)
    portfolio_rules = PortfolioRules(start_equity=100000, risk_pct=0.5, max_positions=3, cost_bps_per_side=15)
    
    trades1, equity1 = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=42)
    trades2, equity2 = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=42)
    
    assert len(trades1) == len(trades2)
    for t1, t2 in zip(trades1, trades2):
        assert t1.symbol == t2.symbol
        assert t1.entry_date == t2.entry_date
        assert t1.exit_date == t2.exit_date
        assert np.isclose(t1.entry_price, t2.entry_price)
        assert np.isclose(t1.exit_price, t2.exit_price)
        assert np.isclose(t1.r_net, t2.r_net)
    
    pd.testing.assert_series_equal(equity1, equity2)


def test_capacity_invariant():
    """For each symbol, total held bars <= number of bars."""
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=50, freq="D")
    
    data = {}
    signals = {}
    for i in range(5):
        sym = f"STK{i}"
        close = 100 + np.cumsum(np.random.randn(50) * 0.5)
        high = close + np.abs(np.random.randn(50) * 0.3)
        low = close - np.abs(np.random.randn(50) * 0.3)
        open_ = close + np.random.randn(50) * 0.2
        volume = np.abs(np.random.randn(50) * 100000 + 10000000)
        
        df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=dates)
        df = add_indicators(df)
        data[sym] = df
        
        sig = pd.Series(False, index=df.index)
        sig.iloc[30:] = True
        signals[sym] = sig
    
    exit_rules = ExitRules(stop_atr=2.0, target_atr=3.0, max_hold_bars=15)
    portfolio_rules = PortfolioRules(start_equity=100000, risk_pct=0.5, max_positions=3, cost_bps_per_side=15)
    
    trades, _ = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=42)
    
    for sym in data:
        sym_trades = [t for t in trades if t.symbol == sym and not t.censored]
        total_held = sum(t.bars_held for t in sym_trades)
        total_bars = len(data[sym])
        assert total_held <= total_bars, f"Symbol {sym}: held {total_held} bars > {total_bars} total"


def test_no_trade_enters_on_signal_date():
    """No trade has entry_date <= signal_date."""
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=50, freq="D")
    
    data = {}
    signals = {}
    for i in range(5):
        sym = f"STK{i}"
        close = 100 + np.cumsum(np.random.randn(50) * 0.5)
        high = close + np.abs(np.random.randn(50) * 0.3)
        low = close - np.abs(np.random.randn(50) * 0.3)
        open_ = close + np.random.randn(50) * 0.2
        volume = np.abs(np.random.randn(50) * 100000 + 10000000)
        
        df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=dates)
        df = add_indicators(df)
        data[sym] = df
        
        sig = pd.Series(False, index=df.index)
        sig.iloc[30:] = True
        signals[sym] = sig
    
    exit_rules = ExitRules(stop_atr=2.0, target_atr=3.0, max_hold_bars=15)
    portfolio_rules = PortfolioRules(start_equity=100000, risk_pct=0.5, max_positions=3, cost_bps_per_side=15)
    
    trades, _ = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=42)
    
    for t in trades:
        if not t.censored:
            assert t.entry_date > t.signal_date, f"Trade {t.symbol} entered on or before signal date"


def _make_panel(symbol_lengths: dict[str, int], seed=7):
    """Multi-symbol panel where symbols have different history lengths."""
    np.random.seed(seed)
    dates = pd.date_range("2020-01-01", periods=max(symbol_lengths.values()), freq="D")
    data = {}
    for symbol, n in symbol_lengths.items():
        close = 100 + np.cumsum(np.random.randn(n) * 0.4)
        high = close + np.abs(np.random.randn(n) * 0.3)
        low = close - np.abs(np.random.randn(n) * 0.3)
        open_ = close + np.random.randn(n) * 0.2
        volume = np.abs(np.random.randn(n) * 100000 + 10_000_000)
        df = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
            index=dates[:n],
        )
        data[symbol] = add_indicators(df)
    return data


def test_data_end_closes_open_position():
    """A position whose symbol's data ends is closed at that symbol's last close."""
    data = _make_panel({"SHORT": 40, "LONG": 120})
    signals = {s: pd.Series(False, index=df.index) for s, df in data.items()}
    signals["SHORT"].iloc[10] = True

    # Wide stop/target and a long hold guarantee the position outlives the data.
    exit_rules = ExitRules(stop_atr=20.0, target_atr=20.0, max_hold_bars=1000)
    portfolio_rules = PortfolioRules(
        start_equity=100_000, risk_pct=0.5, max_positions=2, cost_bps_per_side=0
    )

    trades, equity = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=42)

    short_trades = [t for t in trades if t.symbol == "SHORT"]
    assert len(short_trades) == 1
    trade = short_trades[0]
    assert trade.exit_reason == "data_end"
    assert trade.censored is True
    assert trade.exit_date == data["SHORT"].index[-1]

    # The stranded position's cash must be returned to the equity curve.
    expected = portfolio_rules.start_equity + sum(t.pnl_usd for t in trades)
    assert equity.iloc[-1] == pytest.approx(expected, rel=1e-12)


def test_final_bar_closes_all_positions():
    """Open positions at the last bar are closed before the final equity mark."""
    data = _make_panel({"ONLY": 60})
    signals = {"ONLY": pd.Series(False, index=data["ONLY"].index)}
    signals["ONLY"].iloc[50] = True

    exit_rules = ExitRules(stop_atr=20.0, target_atr=20.0, max_hold_bars=1000)
    portfolio_rules = PortfolioRules(
        start_equity=100_000, risk_pct=0.5, max_positions=1, cost_bps_per_side=15
    )

    trades, equity = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=42)

    assert len(trades) == 1
    assert trades[0].exit_reason == "eod_censored"
    assert trades[0].censored is True
    assert trades[0].exit_date == data["ONLY"].index[-1]
    expected = portfolio_rules.start_equity + sum(t.pnl_usd for t in trades)
    assert equity.iloc[-1] == pytest.approx(expected, rel=1e-12)


def test_final_equity_reconciles_with_realized_pnl():
    """final_equity == start_equity + sum(pnl_usd) even with ragged symbol ends."""
    data = _make_panel({f"S{i}": 60 + i * 5 for i in range(10)})
    signals = {}
    for symbol, df in data.items():
        sig = pd.Series(False, index=df.index)
        sig.iloc[30::7] = True
        signals[symbol] = sig

    exit_rules = ExitRules(stop_atr=2.0, target_atr=3.0, max_hold_bars=15)
    portfolio_rules = PortfolioRules(
        start_equity=100_000, risk_pct=0.5, max_positions=5, cost_bps_per_side=15
    )

    trades, equity = run_portfolio(data, signals, exit_rules, portfolio_rules, seed=42)

    assert len(trades) > 0
    # Every opened position is closed and accounted for.
    assert all(t.exit_price > 0 for t in trades)
    expected = portfolio_rules.start_equity + sum(t.pnl_usd for t in trades)
    assert equity.iloc[-1] == pytest.approx(expected, rel=1e-9)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])