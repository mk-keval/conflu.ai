"""Synthetic deterministic tests for ETF trend research module (F4)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from backend.app.research.etf_trend import (
    CASH_ASSET,
    eligible_assets,
    load_snapshot,
    metrics,
    momentum_12_1,
    paired_month_bootstrap,
    signal_dates,
    simulate,
    target_weights,
    tier_flags,
    trend_pass,
)


def _make_df(prices, start="2020-01-01", col="Adj Close"):
    idx = pd.bdate_range(start, periods=len(prices))
    df = pd.DataFrame(
        {
            "Open": prices,
            "High": prices,
            "Low": prices,
            "Close": prices,
            "Adj Close": prices,
            "Volume": 1000.0,
            "Dividends": 0.0,
            "Stock Splits": 0.0,
        },
        index=idx,
    )
    return df


def _make_universe(prices_by_sym, n=300, start="2020-01-01"):
    idx = pd.bdate_range(start, periods=n)
    data = {}
    for sym, p in prices_by_sym.items():
        if np.isscalar(p):
            arr = np.full(n, float(p))
        else:
            arr = np.asarray(p, dtype=float)
            if len(arr) < n:
                pad = np.full(n - len(arr), arr[-1])
                arr = np.concatenate([arr, pad])
        data[sym] = pd.DataFrame(
            {
                "Open": arr,
                "High": arr,
                "Low": arr,
                "Close": arr,
                "Adj Close": arr,
                "Volume": 1000.0,
                "Dividends": 0.0,
                "Stock Splits": 0.0,
            },
            index=idx,
        )
    return data, idx


def test_signal_dates_last_trading_day_of_month():
    idx = pd.to_datetime(["2024-01-02", "2024-01-31", "2024-02-01", "2024-02-29", "2024-03-01"])
    out = signal_dates(idx)
    assert list(out) == list(pd.to_datetime(["2024-01-31", "2024-02-29", "2024-03-01"]))


def test_look_ahead_selection_uses_only_through_s():
    # Construct series where momentum at s picks AAA, but if future data were used BBB would look better.
    n = 300
    idx = pd.bdate_range("2020-01-01", periods=n)
    # Base rising prices so trend_pass is satisfied (current > 200d mean).
    aaa = np.linspace(80.0, 100.0, n)
    bbb = np.linspace(80.0, 100.0, n)
    spy = np.linspace(80.0, 100.0, n)
    shy = np.full(n, 100.0)
    # Pick an actual month-end signal date with enough history.
    s_pos = 261  # 2020-12-31 in this calendar
    s = idx[s_pos]
    # Make AAA have strong past momentum at s: low at s-252, higher at s-21
    aaa[s_pos - 252] = 50.0
    aaa[s_pos - 21 : s_pos + 1] = 100.0
    # BBB flat at s, but jumps massively after s (future) - should not be selected
    bbb[s_pos + 1 :] = 500.0
    data = {
        "AAA": _make_df(aaa),
        "BBB": _make_df(bbb),
        "SPY": _make_df(spy),
        "SHY": _make_df(shy),
    }
    # Eligible needs 253 bars; both have 300.
    elig = eligible_assets(data, s, min_bars=253, universe=["AAA", "BBB"])
    assert set(elig) == {"AAA", "BBB"}
    m_aaa = momentum_12_1(data["AAA"], s)
    m_bbb = momentum_12_1(data["BBB"], s)
    assert m_aaa > m_bbb  # BBB future jump not visible
    res = simulate(
        data,
        idx,
        cost_bps=0.0,
        n_slots=1,
        min_bars=253,
        risk_assets=("AAA", "BBB"),
        cash_asset="SHY",
    )
    ex = idx[s_pos + 1]  # s+1
    w = res.weights.loc[ex]
    assert w["AAA"] == pytest.approx(1.0)
    assert w["BBB"] == pytest.approx(0.0)


def test_weights_sum_to_one():
    data, idx = _make_universe({"AAA": 100, "BBB": 100, "CCC": 100, "SPY": 100, "SHY": 100}, n=320)
    res = simulate(data, idx, cost_bps=10.0, n_slots=5, min_bars=253, risk_assets=("AAA", "BBB", "CCC"), cash_asset="SHY")
    sums = res.weights.sum(axis=1)
    assert np.allclose(sums.values, 1.0)


def test_less_than_253_bars_ineligible():
    n = 300
    idx = pd.bdate_range("2020-01-01", periods=n)
    short = np.full(n, 100.0)
    long = np.full(n, 100.0)
    # Make SHORT have only 252 valid bars up to s by setting early values NaN
    short[: n - 252] = np.nan
    data = {"SHORT": _make_df(short), "LONG": _make_df(long), "SPY": _make_df(long), "SHY": _make_df(long)}
    s = idx[-1]
    elig = eligible_assets(data, s, min_bars=253, universe=["SHORT", "LONG"])
    assert "SHORT" not in elig
    assert "LONG" in elig


def test_below_200d_mean_goes_to_shy():
    n = 320
    idx = pd.bdate_range("2020-01-01", periods=n)
    spy = np.full(n, 100.0)
    shy = np.full(n, 100.0)
    bad = np.full(n, 100.0)
    # At s, bad is below its 200-day mean: make recent price drop.
    s_pos = 261  # actual month-end signal date
    bad[s_pos - 199 : s_pos] = 110.0
    bad[s_pos] = 90.0  # below mean of 200 window
    # good asset above mean
    good = np.full(n, 100.0)
    good[s_pos - 252] = 50.0
    good[s_pos - 21 : s_pos + 1] = 120.0
    data = {"BAD": _make_df(bad), "GOOD": _make_df(good), "SPY": _make_df(spy), "SHY": _make_df(shy)}
    assert trend_pass(data["BAD"], idx[s_pos], window=200) is False
    res = simulate(data, idx, cost_bps=0.0, n_slots=1, min_bars=253, risk_assets=("BAD", "GOOD"), cash_asset="SHY")
    ex = idx[s_pos + 1]
    assert res.weights.loc[ex, "GOOD"] == pytest.approx(1.0)
    assert res.weights.loc[ex, "BAD"] == pytest.approx(0.0)
    assert res.weights.loc[ex, "SHY"] == pytest.approx(0.0)


def test_alphabetical_ties():
    n = 320
    idx = pd.bdate_range("2020-01-01", periods=n)
    # AAA and BBB identical momentum and trend-pass.
    aaa = np.linspace(50, 100, n)
    bbb = np.linspace(50, 100, n)
    ccc = np.linspace(50, 100, n)
    data = {
        "CCC": _make_df(ccc),
        "BBB": _make_df(bbb),
        "AAA": _make_df(aaa),
        "SPY": _make_df(np.linspace(50, 100, n)),
        "SHY": _make_df(np.full(n, 100.0)),
    }
    s_pos = 261  # actual month-end signal date
    s = idx[s_pos]
    # momentum equal for all; sort should pick AAA, BBB first by symbol
    m = {sym: momentum_12_1(data[sym], s) for sym in ["AAA", "BBB", "CCC"]}
    assert m["AAA"] == pytest.approx(m["BBB"])
    res = simulate(data, idx, cost_bps=0.0, n_slots=2, min_bars=253, risk_assets=("CCC", "BBB", "AAA"), cash_asset="SHY")
    ex = idx[s_pos + 1]
    w = res.weights.loc[ex]
    assert w["AAA"] > 0
    assert w["BBB"] > 0
    assert w["CCC"] == pytest.approx(0.0)


def test_s1_execution_timing():
    n = 320
    idx = pd.bdate_range("2020-01-01", periods=n)
    spy = np.linspace(80.0, 100.0, n)
    shy = np.full(n, 100.0)
    # Asset AAA selected at s; its price jumps on s+2, not s+1.
    aaa = np.linspace(80.0, 100.0, n)
    s_pos = 261  # actual month-end signal date
    aaa[s_pos - 252] = 50.0  # gives momentum
    aaa[s_pos - 21 : s_pos + 2] = 100.0  # flat through s+1 so s1 return is 0
    aaa[s_pos + 2] = 110.0  # jump on s+2 (close-to-close return realized on s+2)
    aaa[s_pos + 3 :] = 110.0
    data = {"AAA": _make_df(aaa), "SPY": _make_df(spy), "SHY": _make_df(shy)}
    res = simulate(data, idx, cost_bps=0.0, n_slots=1, min_bars=253, risk_assets=("AAA",), cash_asset="SHY")
    s1 = idx[s_pos + 1]
    s2 = idx[s_pos + 2]
    # s1 should have AAA weight 1.0 (executed at close s1) but return for s1 is AAA return on s1 day.
    assert res.weights.loc[s1, "AAA"] == pytest.approx(1.0)
    # AAA return on s1 is (100/100 - 1)=0, on s2 is (110/100 - 1)=0.1
    assert res.portfolio_returns.loc[s1] == pytest.approx(0.0)
    assert res.portfolio_returns.loc[s2] == pytest.approx(0.10)


def test_cost_hand_computed():
    n = 320
    idx = pd.bdate_range("2020-01-01", periods=n)
    s_pos = 261  # actual month-end signal date
    aaa = np.linspace(80.0, 100.0, n)
    aaa[s_pos - 252] = 50.0
    aaa[s_pos - 21 : s_pos + 2] = 100.0  # flat through s+1 so gross return on ex is 0
    data = {"AAA": _make_df(aaa), "SPY": _make_df(np.linspace(80.0, 100.0, n)), "SHY": _make_df(np.full(n, 100.0))}
    res = simulate(data, idx, cost_bps=10.0, n_slots=1, min_bars=253, risk_assets=("AAA",), cash_asset="SHY")
    ex = idx[s_pos + 1]
    # Before execution: 100% SHY, target 100% AAA -> turnover abs sum = |1-0|+|0-1|=2, cost=10/10000*2=0.002
    assert res.costs.loc[ex] == pytest.approx(0.002)
    # Day return: gross 0 - cost 0.002
    assert res.portfolio_returns.loc[ex] == pytest.approx(-0.002)


def test_zero_turnover_zero_cost():
    n = 320
    idx = pd.bdate_range("2020-01-01", periods=n)
    aaa = np.linspace(80.0, 100.0, n)
    aaa[260 - 252] = 50.0
    aaa[260 - 21 :] = 100.0
    data = {"AAA": _make_df(aaa), "SPY": _make_df(np.linspace(80.0, 100.0, n)), "SHY": _make_df(np.full(n, 100.0))}
    res = simulate(data, idx, cost_bps=10.0, n_slots=1, min_bars=253, risk_assets=("AAA",), cash_asset="SHY")
    signal_idx = signal_dates(idx)
    ex_days = []
    for s in signal_idx:
        pos = idx.get_loc(s)
        if isinstance(pos, (slice, np.ndarray)):
            pos = int(np.flatnonzero(idx == s)[-1])
        if pos + 1 < len(idx):
            ex_days.append(idx[pos + 1])
    assert len(ex_days) >= 3
    # After first execution, AAA remains selected and already held -> zero turnover/cost.
    second = ex_days[2] if len(ex_days) > 2 else ex_days[1]
    assert res.costs.loc[second] == pytest.approx(0.0)
    assert res.turnover.loc[second] == pytest.approx(0.0)


def test_tier_flags_boundaries_and_equal_not_tier_b_pass():
    spy = {"cagr": 0.10, "sharpe": 1.0, "max_drawdown": -0.20}
    # Tier A requires abs(dd) < 0.6*abs(spy_dd)=0.12 AND sharpe >= 1.0
    strat_a = {"cagr": 0.05, "sharpe": 1.0, "max_drawdown": -0.119}
    out_a = tier_flags(strat_a, spy)
    assert out_a["tier_a"] is True
    strat_a_bad = {"cagr": 0.05, "sharpe": 1.0, "max_drawdown": -0.12}  # equal not less
    assert tier_flags(strat_a_bad, spy)["tier_a"] is False
    strat_a_sharpe = {"cagr": 0.05, "sharpe": 0.999, "max_drawdown": -0.10}
    assert tier_flags(strat_a_sharpe, spy)["tier_a"] is False

    # Tier B: CAGR_strategy > CAGR_SPY; equal not pass
    strat_b_eq = {"cagr": 0.10, "sharpe": 0.5, "max_drawdown": -0.30}
    assert tier_flags(strat_b_eq, spy)["tier_b"] is False
    strat_b_gt = {"cagr": 0.1001, "sharpe": 0.5, "max_drawdown": -0.30}
    assert tier_flags(strat_b_gt, spy)["tier_b"] is True
    assert tier_flags(strat_b_gt, spy)["label"] == "B only"

    both = {"cagr": 0.11, "sharpe": 1.1, "max_drawdown": -0.10}
    assert tier_flags(both, spy)["label"] == "both"
    neither = {"cagr": 0.09, "sharpe": 0.9, "max_drawdown": -0.30}
    assert tier_flags(neither, spy)["label"] == "neither"


def test_bootstrap_deterministic_and_ci_contains_point_estimate():
    idx = pd.bdate_range("2020-01-01", periods=500)
    rng = np.random.default_rng(123)
    strat = pd.Series(rng.normal(0.0005, 0.01, len(idx)), index=idx)
    bench = pd.Series(rng.normal(0.0003, 0.01, len(idx)), index=idx)
    a = paired_month_bootstrap(strat, bench, n=200, seed=17000)
    b = paired_month_bootstrap(strat, bench, n=200, seed=17000)
    assert a == b
    for key in ["sharpe_diff", "cagr_diff", "maxdd_ratio"]:
        assert a[key]["ci_low"] <= a[key]["point"] <= a[key]["ci_high"] or np.isnan(a[key]["point"])


def test_load_snapshot_raises_on_byte_change(tmp_path):
    # create tiny snapshot
    idx = pd.bdate_range("2024-01-01", periods=3)
    df = pd.DataFrame(
        {
            "Open": [1, 2, 3],
            "High": [1, 2, 3],
            "Low": [1, 2, 3],
            "Close": [1, 2, 3],
            "Adj Close": [1, 2, 3],
            "Volume": [10, 10, 10],
            "Dividends": [0, 0, 0],
            "Stock Splits": [0, 0, 0],
        },
        index=idx,
    )
    p = tmp_path / "SPY.csv.gz"
    df.to_csv(p, compression="gzip")
    import hashlib

    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {
        "entries": [
            {
                "symbol": "SPY",
                "file_name": "SPY.csv.gz",
                "sha256": sha,
                "rows": 3,
                "first_date": "2024-01-01",
                "last_date": "2024-01-03",
                "source": "yfinance",
                "auto_adjust": False,
                "yfinance_version": "1.0",
                "created_utc": "2026-01-01T00:00:00Z",
            }
        ]
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    data, m = load_snapshot(tmp_path)
    assert "SPY" in data
    # mutate byte
    b = bytearray(p.read_bytes())
    b[10] ^= 1
    p.write_bytes(bytes(b))
    with pytest.raises(ValueError, match="sha256 mismatch"):
        load_snapshot(tmp_path)
