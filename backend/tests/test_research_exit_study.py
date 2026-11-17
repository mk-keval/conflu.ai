"""Tests for the exit-shape study (E2)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.app.research.engine import ExitRules, PortfolioRules, run_portfolio
from backend.app.research.exit_study import (
    VARIANTS,
    simulate_trade,
    trailing_stop_path,
)
from backend.app.research.indicators import add_indicators


def _flat_frame(n=60, price=100.0, high_pad=1.0, low_pad=1.0):
    """Flat OHLCV frame with indicators; ATR14 settles at high_pad + low_pad."""
    dates = pd.bdate_range("2020-01-01", periods=n)
    close = np.full(n, price)
    df = pd.DataFrame(
        {
            "open": close.copy(),
            "high": close + high_pad,
            "low": close - low_pad,
            "close": close.copy(),
            "volume": np.full(n, 10_000_000.0),
        },
        index=dates,
    )
    return add_indicators(df)


def _arrays(df):
    return (
        df["open"].to_numpy(dtype=float),
        df["high"].to_numpy(dtype=float),
        df["low"].to_numpy(dtype=float),
        df["close"].to_numpy(dtype=float),
    )


def test_b0_matches_engine_exit_price_reason_and_r_net():
    """B0 on one entry equals run_portfolio(max_positions=1) exactly."""
    df = _flat_frame(n=60)
    signal_bar = 20
    entry_bar = signal_bar + 1
    signal = pd.Series(False, index=df.index)
    signal.iloc[signal_bar] = True
    data = {"TEST": df}

    trades, _ = run_portfolio(
        data,
        {"TEST": signal},
        ExitRules(stop_atr=2.0, target_atr=3.0, max_hold_bars=15),
        PortfolioRules(max_positions=1, cost_bps_per_side=15.0),
        seed=42,
    )
    assert len(trades) == 1
    engine = trades[0]

    open_, high, low, close = _arrays(df)
    atr = float(df["atr14"].iloc[signal_bar])
    result = simulate_trade(
        open_, high, low, close, atr, entry_bar, VARIANTS["B0"],
        cost_bps=15.0,
    )

    assert result is not None
    assert result["exit_price"] == engine.exit_price
    assert result["exit_reason"] == engine.exit_reason
    assert result["r_net"] == engine.r_net
    assert result["r_gross"] == engine.r_gross
    assert result["bars_held"] == engine.bars_held
    assert engine.entry_date == df.index[entry_bar]


def test_trailing_stop_never_decreases():
    high = np.array([100.0, 104.0, 101.0, 108.0, 103.0, 99.0, 111.0, 107.0, 102.0, 105.0])

    stops = trailing_stop_path(high, 0, len(high) - 1, atr=1.0, trail_atr=2.0, initial_stop=90.0)

    assert np.all(np.diff(stops) >= 0.0)


def test_spike_high_does_not_move_stop_on_its_own_bar_but_does_on_the_next():
    high = np.full(10, 100.0)
    baseline = trailing_stop_path(high, 0, 9, atr=1.0, trail_atr=2.0, initial_stop=90.0)

    spiked = high.copy()
    spiked[5] = 110.0
    after_spike = trailing_stop_path(
        spiked, 0, 9, atr=1.0, trail_atr=2.0, initial_stop=90.0,
    )

    # The bar-5 stop uses highs through bar 4 only, so the spike cannot lift it.
    assert after_spike[5] == baseline[5]
    # Bar 6 sees the bar-5 high and lifts the stop.
    assert after_spike[6] > baseline[6]
    assert after_spike[6] == 108.0


def test_gap_below_stop_exits_at_the_open():
    n = 10
    open_ = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close = np.full(n, 100.0)
    open_[3] = 95.0
    high[3] = 96.0
    low[3] = 94.0
    close[3] = 95.5

    result = simulate_trade(
        open_, high, low, close, atr=1.0, entry_bar=1, variant=VARIANTS["B1"],
    )

    assert result is not None
    assert result["exit_bar"] == 3
    assert result["exit_price"] == 95.0
    assert result["exit_reason"] == "stop_gap"


def test_b4_exits_at_close_of_twentieth_bar_including_entry():
    n = 40
    open_ = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close = np.array([100.0 + i for i in range(n)])
    entry_bar = 0

    result = simulate_trade(
        open_, high, low, close, atr=1.0, entry_bar=entry_bar, variant=VARIANTS["B4"],
    )

    assert result is not None
    assert result["exit_bar"] == entry_bar + 19
    assert result["bars_held"] == 19
    assert result["exit_reason"] == "time"
    assert result["exit_price"] == close[entry_bar + 19]


def test_trade_running_past_the_panel_end_is_dropped():
    df = _flat_frame(n=20)
    open_, high, low, close = _arrays(df)
    atr = float(df["atr14"].iloc[-6])

    time_stop = simulate_trade(
        open_, high, low, close, atr, 15, VARIANTS["B1"],
    )
    no_stop = simulate_trade(
        open_, high, low, close, atr, 15, VARIANTS["B4"],
    )

    assert time_stop is None
    assert no_stop is None
