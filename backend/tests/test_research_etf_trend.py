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


def test_old_timing_is_not_applied():
    n = 320
    idx = pd.bdate_range("2020-01-01", periods=n)
    s_pos = 261  # actual month-end signal date
    spy = np.linspace(80.0, 100.0, n)
    shy = np.full(n, 100.0)
    aaa = np.linspace(80.0, 100.0, n)
    # Make AAA selected at s with strong momentum and trend pass.
    aaa[s_pos - 252] = 50.0
    aaa[s_pos - 21 : s_pos + 1] = 100.0
    # Jump +10% on day s+1 (close-to-close return on s+1), flat before, +10% again on s+2.
    aaa[s_pos + 1] = 110.0
    aaa[s_pos + 2] = 121.0
    aaa[s_pos + 3 :] = 121.0
    data = {"AAA": _make_df(aaa), "SPY": _make_df(spy), "SHY": _make_df(shy)}
    res = simulate(data, idx, cost_bps=0.0, n_slots=1, min_bars=253, risk_assets=("AAA",), cash_asset="SHY")
    s1 = idx[s_pos + 1]
    s2 = idx[s_pos + 2]
    # Previous weights (SHY) earn s+1; AAA selected at close s+1, earns s+2 onward.
    assert res.portfolio_returns.loc[s1] == pytest.approx(0.0)
    assert res.weights.loc[s1, "AAA"] == pytest.approx(1.0)
    assert res.portfolio_returns.loc[s2] == pytest.approx(0.10)


def test_cost_charged_on_old_weights_drifted():
    n = 320
    idx = pd.bdate_range("2020-01-01", periods=n)
    s_pos = 261
    spy = np.linspace(80.0, 100.0, n)
    shy = np.full(n, 100.0)
    aaa = np.linspace(80.0, 100.0, n)
    aaa[s_pos - 252] = 50.0
    aaa[s_pos - 21 : s_pos + 1] = 100.0
    aaa[s_pos + 1 :] = 100.0
    data = {"AAA": _make_df(aaa), "SPY": _make_df(spy), "SHY": _make_df(shy)}
    res = simulate(data, idx, cost_bps=10.0, n_slots=1, min_bars=253, risk_assets=("AAA",), cash_asset="SHY")
    s1 = idx[s_pos + 1]
    # Previous weights 100% SHY, target 100% AAA: turnover abs sum = 2, cost = 0.002
    assert res.costs.loc[s1] == pytest.approx(0.002)
    assert res.portfolio_returns.loc[s1] == pytest.approx(0.0 - 0.002)


def test_drift_uses_gross_return():
    n = 40
    idx = pd.bdate_range("2021-01-01", periods=n)
    # Two assets, no signals/executions: start 50/50 by forcing weights via direct schedule? 
    # Easier: simulate with no eligible risk assets so stays in SHY? No, need two assets held.
    # Build: AAA and BBB selected as 50/50 at first execution and held; check drift on later days.
    aaa = np.full(n, 100.0)
    bbb = np.full(n, 100.0)
    spy = np.linspace(80.0, 100.0, n)
    shy = np.full(n, 100.0)
    # Make both eligible and selected at s_pos.
    s_pos = 21  # we'll set min_bars small via direct simulate? simulate has min_bars param.
    # Build prices so both have momentum/trend at a signal.
    # Use simpler: construct 260+ days.
    n = 320
    idx = pd.bdate_range("2020-01-01", periods=n)
    aaa = np.linspace(80.0, 100.0, n)
    bbb = np.linspace(80.0, 100.0, n)
    spy = np.linspace(80.0, 100.0, n)
    shy = np.full(n, 100.0)
    s_pos = 261
    aaa[s_pos - 252] = 50.0
    bbb[s_pos - 252] = 50.0
    aaa[s_pos - 21 : s_pos + 1] = 100.0
    bbb[s_pos - 21 : s_pos + 1] = 100.0
    # After execution, give different returns on s+2,s+3,s+4 with no rebalance expected.
    # s+1 execution day: flat
    aaa[s_pos + 1] = 100.0
    bbb[s_pos + 1] = 100.0
    aaa[s_pos + 2] = 110.0  # +10%
    bbb[s_pos + 2] = 100.0  # 0%
    aaa[s_pos + 3] = 121.0  # +10%
    bbb[s_pos + 3] = 95.0   # -5%
    aaa[s_pos + 4 :] = 121.0
    bbb[s_pos + 4 :] = 95.0
    data = {"AAA": _make_df(aaa), "BBB": _make_df(bbb), "SPY": _make_df(spy), "SHY": _make_df(shy)}
    res = simulate(data, idx, cost_bps=0.0, n_slots=2, min_bars=253, risk_assets=("AAA", "BBB"), cash_asset="SHY")
    # After s+1 execution, end-of-day weights 50/50. Check s+2 drift (no rebalance).
    d2 = idx[s_pos + 2]
    r_aaa_2 = 110.0 / 100.0 - 1.0
    r_bbb_2 = 0.0
    gross2 = 0.5 * r_aaa_2 + 0.5 * r_bbb_2
    w_aaa_2 = 0.5 * (1 + r_aaa_2) / (1 + gross2)
    w_bbb_2 = 0.5 * (1 + r_bbb_2) / (1 + gross2)
    assert res.weights.loc[d2, "AAA"] == pytest.approx(w_aaa_2)
    assert res.weights.loc[d2, "BBB"] == pytest.approx(w_bbb_2)
    # s+3 drift from s+2 end-of-day weights using gross return on s+3.
    d3 = idx[s_pos + 3]
    r_aaa_3 = 121.0 / 110.0 - 1.0
    r_bbb_3 = 95.0 / 100.0 - 1.0
    gross3 = w_aaa_2 * r_aaa_3 + w_bbb_2 * r_bbb_3
    w_aaa_3 = w_aaa_2 * (1 + r_aaa_3) / (1 + gross3)
    w_bbb_3 = w_bbb_2 * (1 + r_bbb_3) / (1 + gross3)
    assert res.weights.loc[d3, "AAA"] == pytest.approx(w_aaa_3)
    assert res.weights.loc[d3, "BBB"] == pytest.approx(w_bbb_3)


def test_bootstrap_cagr_ci_is_sane():
    rng = np.random.default_rng(123)
    dates = pd.bdate_range("2018-01-01", periods=1260)  # ~5y
    strat = pd.Series(rng.normal(0.0006, 0.01, len(dates)), index=dates)
    bench = pd.Series(rng.normal(0.0004, 0.012, len(dates)), index=dates)
    out = paired_month_bootstrap(strat, bench, n=2000, seed=17000)
    ci = out["cagr_diff"]
    assert ci["ci_low"] <= ci["point"] <= ci["ci_high"]
    assert abs(ci["ci_low"]) < 1.0
    assert abs(ci["ci_high"]) < 1.0
    assert ci["ci_high"] - ci["ci_low"] < 0.51  # user-authorized relaxation from 0.5 after F8 STOP; observed width ~0.5006


def test_bootstrap_identical_series_gives_zero_cagr_diff():
    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2019-01-01", periods=800)
    r = pd.Series(rng.normal(0.0003, 0.01, len(dates)), index=dates)
    out = paired_month_bootstrap(r, r.copy(), n=500, seed=17000)
    ci = out["cagr_diff"]
    assert ci["point"] == pytest.approx(0.0, abs=1e-12)
    assert ci["ci_low"] == pytest.approx(0.0, abs=1e-12)
    assert ci["ci_high"] == pytest.approx(0.0, abs=1e-12)


def test_metrics_years_override():
    idx = pd.bdate_range("2020-01-01", periods=252)
    r = pd.Series(np.full(252, 0.001), index=idx)
    m2 = metrics(r, years=2.0)
    end_equity = float((1.0 + r).prod())
    assert m2["cagr"] == pytest.approx(end_equity ** (1 / 2.0) - 1.0)
    m_none = metrics(r, years=None)
    m_default = metrics(r)
    assert m_none["cagr"] == pytest.approx(m_default["cagr"])
    assert m_none["sharpe"] == pytest.approx(m_default["sharpe"])
    assert m_none["max_drawdown"] == pytest.approx(m_default["max_drawdown"])


def test_sharpe_and_ratio_cis_unchanged_by_years_fix():
    rng = np.random.default_rng(123)
    dates = pd.bdate_range("2018-01-01", periods=1260)  # ~5y
    strat = pd.Series(rng.normal(0.0006, 0.01, len(dates)), index=dates)
    bench = pd.Series(rng.normal(0.0004, 0.012, len(dates)), index=dates)
    res = paired_month_bootstrap(strat, bench, n=2000, seed=17000)
    # Pre-fix values captured before F8 edit (git show HEAD:backend/app/research/etf_trend.py)
    assert res["sharpe_diff"]["point"] == pytest.approx(0.9997790340111061, abs=1e-9)
    assert res["sharpe_diff"]["ci_low"] == pytest.approx(-0.19452343949139025, abs=1e-9)
    assert res["sharpe_diff"]["ci_high"] == pytest.approx(2.250281114037276, abs=1e-9)
    assert res["maxdd_ratio"]["point"] == pytest.approx(0.43113156570528777, abs=1e-9)
    assert res["maxdd_ratio"]["ci_low"] == pytest.approx(0.23903684507568235, abs=1e-9)
    assert res["maxdd_ratio"]["ci_high"] == pytest.approx(1.1779554477261305, abs=1e-9)
