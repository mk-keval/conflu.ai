"""Tests for the event-study maths (E1)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.app.research.events import (
    accepted_event_positions,
    collect_events,
    event_stats,
    forward_return_frame,
    month_block_bootstrap_ci,
    p_values,
    universe_benchmark,
)


def _frame(closes, opens=None):
    """Minimal OHLCV frame; forward returns need only open and close."""
    closes = np.asarray(closes, dtype=float)
    opens = closes.copy() if opens is None else np.asarray(opens, dtype=float)
    dates = pd.bdate_range("2019-01-01", periods=len(closes))
    return pd.DataFrame(
        {
            "open": opens,
            "high": np.maximum(opens, closes) * 1.01,
            "low": np.minimum(opens, closes) * 0.99,
            "close": closes,
            "volume": np.full(len(closes), 1_000_000.0),
        },
        index=dates,
    )


def _elig(data):
    union = pd.DatetimeIndex(sorted({d for df in data.values() for d in df.index}))
    return pd.DataFrame(
        {symbol: pd.Series(True, index=union) for symbol in data},
        index=union,
    )


def test_forward_return_alignment_and_tail_drop():
    """ret_5 uses close[e+4]/open[e]-1 and the last four rows have no data."""
    closes = [100.0 + i for i in range(10)]
    opens = [50.0 + i for i in range(10)]
    frame = forward_return_frame(_frame(closes, opens), [5])

    assert frame["ret_5"].iloc[0] == closes[4] / opens[0] - 1.0
    assert frame["ret_5"].iloc[4] == closes[8] / opens[4] - 1.0
    assert frame["ret_5"].iloc[-4:].isna().all()
    assert frame["ret_5"].iloc[5] == closes[9] / opens[5] - 1.0


def test_event_on_every_eligible_symbol_has_zero_mean_excess():
    """When every eligible symbol is an event, each excess is versus itself."""
    data = {
        "AAA": _frame([100.0, 101.0, 102.0, 103.0, 104.0, 105.0]),
        "BBB": _frame([200.0, 203.0, 199.0, 205.0, 210.0, 208.0]),
        "CCC": _frame([50.0, 49.5, 51.0, 50.0, 52.5, 53.0]),
    }
    elig = _elig(data)
    signals = {
        symbol: pd.Series([True, False, False, False, False, False], index=df.index)
        for symbol, df in data.items()
    }

    real_events = collect_events(data, signals, elig, cooldown=5, horizons=[1])
    benchmark = universe_benchmark(data, elig, horizons=[1])
    stats = event_stats(real_events, benchmark, 1)

    assert stats["n"] == 3
    assert abs(stats["mean_excess_bp"]) < 1e-9


def test_cooldown_removes_back_to_back_events():
    """A repeat within ``cooldown`` bars of the previous accepted event is dropped."""
    signal = pd.Series(True, index=pd.bdate_range("2019-01-01", periods=20))
    eligible_flags = pd.Series(True, index=signal.index)

    positions = accepted_event_positions(signal, eligible_flags, cooldown=5)

    assert positions.tolist() == [0, 6, 12, 18]
    assert np.all(np.diff(positions) == 6)


def test_month_block_bootstrap_is_deterministic_and_contains_mean():
    values = [0.01, -0.02, 0.03, 0.00, 0.015, -0.01, 0.02, 0.005, -0.005, 0.025]
    dates = pd.date_range("2019-01-31", periods=10, freq="ME")

    low1, high1 = month_block_bootstrap_ci(values, dates, n_resamples=500, seed=42)
    low2, high2 = month_block_bootstrap_ci(values, dates, n_resamples=500, seed=42)

    assert (low1, high1) == (low2, high2)
    assert low1 <= float(np.mean(values)) <= high1


def test_forward_returns_do_not_leak_future_prices():
    """Changing closes after e+h-1 leaves ret_h at e unchanged."""
    frame = _frame([100.0 + i for i in range(12)], [50.0 + i for i in range(12)])
    original = forward_return_frame(frame, [5])

    changed = frame.copy()
    changed.loc[changed.index[5:], "close"] = changed.loc[changed.index[5:], "close"] * 10.0
    modified = forward_return_frame(changed, [5])

    # ret_5 at e=0 reads close[4], so it must be identical.
    assert original["ret_5"].iloc[0] == modified["ret_5"].iloc[0]
    # ret_5 at e=1 reads close[5], which was changed.
    assert original["ret_5"].iloc[1] != modified["ret_5"].iloc[1]


def test_null_p_values_are_in_unit_interval():
    real = 0.2
    null = [0.1, 0.2, 0.3]

    stats = p_values(real, null)

    assert 0.0 < stats["p_high"] <= 1.0
    assert 0.0 < stats["p_low"] <= 1.0
    assert stats["p_high"] == 0.75
    assert stats["p_low"] == 0.75
    assert stats["n_null"] == 3
