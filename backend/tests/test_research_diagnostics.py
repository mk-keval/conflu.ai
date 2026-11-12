"""Tests for the D-82 research diagnostics helpers."""

import pandas as pd
import pytest

from backend.app.research.engine import Trade
from scripts.research_diagnostics import (
    integrity_flags,
    interpolate_zero_crossing,
    r_net_stats,
    window_trades,
)


def _trade(r_net=0.1, exit_reason="target", exit_date="2016-06-01", censored=False, bars_held=5):
    return Trade(
        symbol="AAA",
        signal_date=pd.Timestamp("2016-05-31"),
        entry_date=pd.Timestamp("2016-06-01"),
        entry_price=10.0,
        stop=9.0,
        target=11.0,
        shares=100,
        exit_date=pd.Timestamp(exit_date),
        exit_price=11.0,
        exit_reason=exit_reason,
        bars_held=bars_held,
        r_gross=r_net,
        r_net=r_net,
        pnl_usd=100.0,
        censored=censored,
    )


def _frame(closes, index=None, volumes=None):
    n = len(closes)
    if index is None:
        index = pd.bdate_range("2019-01-01", periods=n)
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": volumes if volumes is not None else [1_000_000.0] * n,
        },
        index=index,
    )


def test_window_trades_and_stats():
    trades = [
        _trade(r_net=0.5, exit_date="2015-12-31"),          # 2015: warm-up
        _trade(r_net=0.2, exit_date="2016-01-04"),
        _trade(r_net=-0.4, exit_date="2017-01-04", exit_reason="stop"),
        _trade(r_net=9.0, exit_date="2017-01-04", censored=True),
    ]
    kept = window_trades(trades)
    assert [t.r_net for t in kept] == [0.2, -0.4]

    stats = r_net_stats(trades)
    assert stats["n"] == 2
    assert stats["mean"] == pytest.approx(-0.1)
    assert stats["std"] == pytest.approx(0.3)
    assert stats["min"] == pytest.approx(-0.4)
    assert stats["max"] == pytest.approx(0.2)


def test_interpolate_zero_crossing():
    assert interpolate_zero_crossing([0, 7.5, 15, 30], [0.2, 0.1, -0.1, -0.5]) == pytest.approx(11.25)
    assert interpolate_zero_crossing([0, 7.5, 15], [0.2, 0.1, 0.0]) == pytest.approx(15.0)
    assert interpolate_zero_crossing([0, 7.5, 15], [0.2, 0.1, 0.05]) is None
    assert interpolate_zero_crossing([0, 7.5, 15], [-0.2, -0.1, -0.05]) is None
    with pytest.raises(ValueError):
        interpolate_zero_crossing([0, 1], [0.1])


def test_integrity_flags_counts_known_defects():
    clean = integrity_flags(_frame([100.0, 101.0, 102.0]))
    assert clean["flagged_bars"] == 0
    assert clean["bars"] == 3

    jump = integrity_flags(_frame([100.0, 100.0, 100.0, 200.0]))
    assert jump["ret_gt_40pct"] == 1

    high_lt_low = _frame([100.0, 100.0])
    high_lt_low.loc[high_lt_low.index[1], "high"] = 90.0
    assert integrity_flags(high_lt_low)["high_lt_low"] == 1

    outside = _frame([100.0, 100.0])
    outside.loc[outside.index[1], "open"] = 120.0
    assert integrity_flags(outside)["ohlc_out_of_range"] == 1

    zero_volume = integrity_flags(_frame([100.0, 100.0], volumes=[0.0, 1000.0]))
    assert zero_volume["zero_volume"] == 1

    duplicated = _frame([100.0, 101.0], index=[pd.Timestamp("2019-01-01"), pd.Timestamp("2019-01-01")])
    assert integrity_flags(duplicated)["duplicate_dates"] == 1

    gapped = _frame(
        [100.0, 101.0],
        index=[pd.Timestamp("2019-01-01"), pd.Timestamp("2019-01-31")],
    )
    assert integrity_flags(gapped)["gap_gt_5bd"] == 1
