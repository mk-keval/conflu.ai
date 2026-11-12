"""Tests for the research control suite."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from backend.app.research.control import compute_control_pvalues, matched_random_signals
from backend.app.research.indicators import add_indicators
from backend.app.research.setups import eligible


def _frame(n=260, price=100.0):
    """Liquid OHLCV frame with indicators (small drift so CCI/ADX are defined)."""
    dates = pd.bdate_range("2019-01-01", periods=n)
    rng = np.random.default_rng(0)
    close = price * (1 + np.cumsum(rng.normal(0, 0.001, n)))
    df = pd.DataFrame(
        {
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.full(n, 1_000_000.0),
        },
        index=dates,
    )
    return add_indicators(df)


def _signals(data, marks):
    signals = {s: pd.Series(False, index=df.index) for s, df in data.items()}
    for symbol, positions in marks.items():
        for i in positions:
            signals[symbol].iloc[i] = True
    return signals


def _marked(signals, i):
    return sorted(s for s in signals if bool(signals[s].iloc[i]))


def test_matched_random_matches_daily_count_and_is_reproducible():
    """Same number of entries per day as the strategy, and deterministic by seed."""
    data = {"AAA": _frame(), "BBB": _frame(), "CCC": _frame()}
    d1, d2 = 210, 211
    real = _signals(data, {"AAA": [d1], "BBB": [d1], "CCC": [d2]})

    out1 = matched_random_signals(data, real, seed=7)
    out2 = matched_random_signals(data, real, seed=7)

    assert len(_marked(out1, d1)) == 2
    assert len(_marked(out1, d2)) == 1
    for i in range(len(data["AAA"])):
        if i not in (d1, d2):
            assert _marked(out1, i) == []

    for symbol in data:
        pd.testing.assert_series_equal(out1[symbol], out2[symbol])


def test_matched_random_respects_eligibility():
    """A symbol below the liquidity gate is never picked by the control."""
    data = {"LIQ": _frame(price=100.0), "ILLIQ": _frame(price=5.0)}
    assert not eligible(data["ILLIQ"]).iloc[210]

    real = _signals(data, {"ILLIQ": [210, 211]})
    out = matched_random_signals(data, real, seed=1)

    assert not out["ILLIQ"].any()
    # The two signals are re-homed onto the only eligible symbol.
    assert out["LIQ"].sum() == 2


def _control(values):
    return {
        "matched_random": [
            SimpleNamespace(metrics=SimpleNamespace(r_net_mean=v)) for v in values
        ]
    }


def _real(value):
    return SimpleNamespace(r_net_mean=value)


def test_pvalue_negative_real_is_not_flipped():
    """A losing strategy must not look significant: p is near 1, not near 0."""
    p = compute_control_pvalues(_real(-5.0), _control([0.0] * 10), "r_net_mean")
    assert p["matched_random"] > 0.9


def test_pvalue_beats_every_control():
    """Real +5 vs ten controls at 0 gives the finite-sample floor 1/11."""
    p = compute_control_pvalues(_real(5.0), _control([0.0] * 10), "r_net_mean")
    assert p["matched_random"] == pytest.approx(1.0 / 11.0, abs=1e-9)


def test_pvalue_control_better_gives_one():
    """Controls at 8 beat a real 5, so the one-sided p-value is 1.0."""
    p = compute_control_pvalues(_real(5.0), _control([8.0] * 10), "r_net_mean")
    assert p["matched_random"] == pytest.approx(1.0, abs=1e-9)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
