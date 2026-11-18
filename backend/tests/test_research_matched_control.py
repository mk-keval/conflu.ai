"""Tests for the volatility-matched control and percent-return layer (E4)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from backend.app.research import events
from backend.app.research.matched_control import (
    add_event_bucket,
    add_pct_returns,
    block_summary,
    bucket_benchmark,
    bucket_excess_frame,
    cell_passes,
    vol_bucket_frame,
    vol_matched_random_signals,
    z_crit,
)


def _frame(periods: int, start: str = "2019-01-01", price: float = 100.0):
    """Minimal OHLCV frame with a constant price."""
    dates = pd.bdate_range(start, periods=periods)
    close = np.full(periods, float(price))
    return pd.DataFrame(
        {
            "open": close.copy(),
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close.copy(),
            "volume": np.full(periods, 1_000_000.0),
        },
        index=dates,
    )


def _all_eligible(data):
    union = pd.DatetimeIndex(sorted({d for df in data.values() for d in df.index}))
    return pd.DataFrame(
        {symbol: pd.Series(True, index=union) for symbol in data}, index=union
    )


def _true_on(index, date):
    index = index if isinstance(index, pd.Index) else index.index
    out = pd.Series(False, index=index)
    out.loc[pd.Timestamp(date)] = True
    return out


def test_vol_bucket_frame_matches_hand_computed_buckets():
    """Three dates x ten symbols: buckets follow the rank formula; -1 when ineligible/NaN."""
    symbols = list("ABCDEFGHIJ")
    dates = pd.bdate_range("2019-01-01", periods=3)

    def frame(values):
        df = _frame(len(dates))
        df.index = dates
        df["atr_pct"] = values
        return df

    atr = {
        "A": [0.01, 0.10, 0.02],
        "B": [0.02, 0.09, 0.04],
        "C": [0.03, 0.08, 0.06],
        "D": [0.04, 0.07, np.nan],
        "E": [0.05, 0.06, 0.10],
        "F": [0.06, 0.05, 0.12],
        "G": [0.07, 0.04, 0.14],
        "H": [0.08, 0.03, 0.16],
        "I": [0.09, 0.02, 0.18],
        "J": [0.10, 0.01, 0.20],
    }
    data = {symbol: frame(atr[symbol]) for symbol in symbols}

    elig = _all_eligible(data)
    elig.loc[dates[2], "C"] = False

    buckets = vol_bucket_frame(data, elig, n_buckets=10)

    # Date 0: atr_pct 0.01..0.10 -> ranks 1..10 -> buckets 0..9.
    assert buckets.loc[dates[0], symbols].tolist() == list(range(10))
    # Date 1: reversed atr_pct -> buckets 9..0.
    assert buckets.loc[dates[1], symbols].tolist() == list(range(9, -1, -1))
    # Date 2: C is ineligible and D has NaN atr_pct -> both -1.  The eight
    # remaining symbols rank 1..8 of 8, and ceil(pct*10)-1 is 1,2,3,4,6,7,8,9.
    assert buckets.loc[dates[2], symbols].tolist() == [1, 2, -1, -1, 3, 4, 6, 7, 8, 9]
    assert buckets.dtypes.eq(int).all()


def _matched_panel():
    dates = pd.bdate_range("2019-01-01", periods=10)
    symbols = [f"S{i}" for i in range(6)]
    levels = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06]  # buckets 0,0,0,1,1,1
    data = {}
    for symbol, level in zip(symbols, levels):
        df = _frame(len(dates))
        df["atr_pct"] = level
        data[symbol] = df
    elig = _all_eligible(data)
    buckets = vol_bucket_frame(data, elig, n_buckets=2)
    return dates, symbols, data, elig, buckets


def test_vol_matched_counts_pool_membership_and_seed_determinism():
    """Counts match per date/bucket; draws are eligible, in-bucket and seeded."""
    dates, symbols, data, elig, buckets = _matched_panel()

    real = {symbol: pd.Series(False, index=dates) for symbol in symbols}
    real["S0"].loc[dates[:8]] = True  # bucket 0, one per date
    real["S5"].loc[dates[9]] = True   # bucket 1, one on the last date

    stats = {}
    first = vol_matched_random_signals(data, real, seed=1, elig=elig, buckets=buckets, stats=stats)
    second = vol_matched_random_signals(data, real, seed=1, elig=elig, buckets=buckets)
    third = vol_matched_random_signals(data, real, seed=2, elig=elig, buckets=buckets)

    for symbol in symbols:
        assert first[symbol].equals(second[symbol])
    assert any(not first[symbol].equals(third[symbol]) for symbol in symbols)

    marks = pd.DataFrame({symbol: first[symbol] for symbol in symbols})
    for date in dates:
        drawn = marks.columns[marks.loc[date].to_numpy(dtype=bool)].tolist()
        real_count = int(sum(bool(real[symbol].loc[date]) for symbol in symbols))
        assert len(drawn) == real_count
        if real_count == 0:
            continue
        expected_bucket = 1 if date == dates[9] else 0
        for symbol in drawn:
            assert bool(elig.loc[date, symbol])
            assert int(buckets.loc[date, symbol]) == expected_bucket

    assert stats["requested"] == 9
    assert stats["drawn"] == 9


def test_vol_matched_shortfall_when_bucket_pool_is_smaller_than_count():
    """requested > drawn when more real signals exist than eligible pool members."""
    dates = pd.bdate_range("2019-01-01", periods=3)
    symbols = [f"S{i}" for i in range(5)]
    data = {symbol: _frame(len(dates)) for symbol in symbols}
    elig = _all_eligible(data)
    elig.loc[dates[0], ["S2", "S3", "S4"]] = False

    buckets = pd.DataFrame(0, index=dates, columns=symbols, dtype=int)
    real = {symbol: pd.Series(False, index=dates) for symbol in symbols}
    for symbol in symbols:
        real[symbol].loc[dates[0]] = True

    stats = {}
    signals = vol_matched_random_signals(
        data, real, seed=7, elig=elig, buckets=buckets, stats=stats
    )

    assert stats["requested"] == 5
    assert stats["drawn"] == 2
    assert int(sum(bool(signals[symbol].loc[dates[0]]) for symbol in symbols)) == 2


def test_event_on_every_eligible_symbol_of_a_bucket_has_zero_excess():
    """When the whole bucket is the event set, every event is its own benchmark."""
    dates = pd.bdate_range("2019-01-01", periods=8)
    symbols = ["AAA", "BBB", "CCC", "DDD"]
    data = {}
    for i, symbol in enumerate(symbols):
        df = _frame(len(dates), price=100.0 + i)
        df["atr_pct"] = 0.01 * (i + 1)
        data[symbol] = df
    elig = _all_eligible(data)
    buckets = vol_bucket_frame(data, elig, n_buckets=1)
    signals = {symbol: _true_on(data[symbol].index, dates[0]) for symbol in symbols}

    horizon = 1
    forward = {
        symbol: events.forward_return_frame(df, [horizon]) for symbol, df in data.items()
    }
    real_events = events.collect_events(
        data, signals, elig, cooldown=5, horizons=[horizon], forward=forward
    )
    benchmark = bucket_benchmark(
        data, elig, buckets, [horizon], forward=forward
    )
    with_bucket = add_event_bucket(real_events, buckets)
    excess = bucket_excess_frame(with_bucket, benchmark, horizon)

    assert len(excess) == 4
    assert abs(float(excess["excess"].mean())) < 1e-12


def test_volatility_confound_universe_benchmark_vs_bucket_excess():
    """Forward returns rise with atr_pct: universe excess is large, bucket excess ~0."""
    dates = pd.bdate_range("2019-01-01", periods=6)
    symbols = [f"S{i}" for i in range(10)]
    data = {}
    for i, symbol in enumerate(symbols):
        atr_pct = 0.01 * (i + 1)
        target = 0.01 * (i + 1)  # ret_1 rises with atr_pct
        df = _frame(len(dates))
        df["open"] = 100.0
        df["close"] = 100.0 * (1.0 + target)
        df["high"] = df["close"] + 1.0
        df["low"] = df["open"] - 1.0
        df["atr_pct"] = atr_pct
        data[symbol] = df

    elig = _all_eligible(data)
    buckets = vol_bucket_frame(data, elig, n_buckets=10)
    top_bucket = int(buckets.loc[dates[1], symbols[-1]])
    assert top_bucket == 9

    signals = {symbol: pd.Series(False, index=dates) for symbol in symbols}
    signals[symbols[-1]].loc[dates[0]] = True

    horizon = 1
    forward = {
        symbol: events.forward_return_frame(df, [horizon]) for symbol, df in data.items()
    }
    real_events = events.collect_events(
        data, signals, elig, cooldown=5, horizons=[horizon], forward=forward
    )
    universe = events.universe_benchmark(
        data, elig, horizons=[horizon], forward=forward
    )
    bucket_bench = bucket_benchmark(
        data, elig, buckets, [horizon], forward=forward
    )
    with_bucket = add_event_bucket(real_events, buckets)
    excess = bucket_excess_frame(with_bucket, bucket_bench, horizon)

    old = events.event_stats(real_events, universe, horizon)
    assert old["n"] == 1
    assert old["mean_excess_bp"] > 300.0
    assert len(excess) == 1
    assert abs(float(excess["excess"].iloc[0])) < 1e-9


def test_add_pct_returns_matches_the_specified_formula():
    """Hand-built rows match gross and net formulas; costs separate them."""
    trades = pd.DataFrame(
        {
            "entry_price": [100.0, 50.0],
            "exit_price": [110.0, 40.0],
        }
    )
    cost_bps = 15.0
    cost = cost_bps / 10_000.0
    expected_gross = trades["exit_price"] / trades["entry_price"] - 1.0
    expected_net = trades["exit_price"] * (1.0 - cost) / (
        trades["entry_price"] * (1.0 + cost)
    ) - 1.0

    out = add_pct_returns(trades, cost_bps)

    assert np.allclose(
        out["ret_gross_pct"].to_numpy(dtype=float),
        expected_gross.to_numpy(dtype=float),
    )
    assert np.allclose(
        out["ret_net_pct"].to_numpy(dtype=float),
        expected_net.to_numpy(dtype=float),
    )
    assert math.isclose(out["ret_gross_pct"].iloc[0], 0.10)
    assert (out["ret_net_pct"] < out["ret_gross_pct"]).all()
    # 110 * 0.9985 / (100 * 1.0015) - 1
    assert math.isclose(out["ret_net_pct"].iloc[0], 110.0 * 0.9985 / 100.15 - 1.0)
    # Costs are the only difference between the columns, so they coincide at zero.
    free = add_pct_returns(trades, 0.0)
    assert np.allclose(
        free["ret_net_pct"].to_numpy(dtype=float),
        free["ret_gross_pct"].to_numpy(dtype=float),
    )
    at_8bps = add_pct_returns(trades, 8.0)
    assert (at_8bps["ret_net_pct"] < at_8bps["ret_gross_pct"]).all()
    empty = add_pct_returns(trades.iloc[0:0], cost_bps)
    assert "ret_net_pct" in empty and "ret_gross_pct" in empty


def test_block_summary_is_deterministic_and_uses_the_block_ci():
    """CI, se_block, block_t, reference_in_ci and z_crit(20) match hand maths."""
    values = [0.01, -0.02, 0.03, 0.00, 0.015, -0.01, 0.02, 0.005, -0.005, 0.025]
    dates = pd.date_range("2019-01-31", periods=10, freq="ME")
    n_resamples = 500

    first = block_summary(values, dates, 0.0, n_resamples=n_resamples, seed=42)
    second = block_summary(values, dates, 0.0, n_resamples=n_resamples, seed=42)
    low, high = events.month_block_bootstrap_ci(
        values, dates, n_resamples=n_resamples, seed=42
    )

    assert first == second
    assert first["n"] == len(values)
    assert first["ci_low"] == low and first["ci_high"] == high
    se_block = (high - low) / (2.0 * 1.96)
    assert math.isclose(first["se_block"], se_block)
    assert math.isclose(first["mean"], float(np.mean(values)))
    assert first["reference_in_ci"] == bool(low <= 0.0 <= high)
    assert math.isclose(
        first["block_t"], (float(np.mean(values)) - 0.0) / se_block
    )

    far = block_summary(values, dates, 1.0, n_resamples=n_resamples, seed=42)
    assert far["reference_in_ci"] is False
    assert math.isclose(far["block_t"], (float(np.mean(values)) - 1.0) / se_block)
    assert cell_passes(far["block_t"], far["reference_in_ci"], z_crit(20)) is True

    assert abs(z_crit(20) - 3.023) < 0.01


def test_buckets_do_not_look_ahead():
    """Changing atr_pct after date t cannot change any bucket on or before t."""
    dates = pd.bdate_range("2019-01-01", periods=4)
    symbols = [f"S{i}" for i in range(5)]
    data = {}
    for i, symbol in enumerate(symbols):
        df = _frame(len(dates))
        df.index = dates
        df["atr_pct"] = 0.01 * (i + 1)
        data[symbol] = df
    elig = _all_eligible(data)

    before = vol_bucket_frame(data, elig, n_buckets=5)

    changed = {symbol: df.copy() for symbol, df in data.items()}
    for i, symbol in enumerate(symbols):
        changed[symbol].loc[dates[3], "atr_pct"] = 100.0 * (i + 1)
        changed[symbol].loc[dates[2], "atr_pct"] = 50.0 * (i + 1)

    after = vol_bucket_frame(changed, elig, n_buckets=5)

    assert before.loc[dates[:2]].equals(after.loc[dates[:2]])
