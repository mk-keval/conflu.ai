"""Tests for the survivorship size-estimate helpers (E9)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from backend.app.research.survivorship import (
    annual_gap_table,
    average_annual_gap,
    calendar_year_returns,
    cumulative_return,
    equal_weight_returns,
    symbols_with_data_by_year,
)


def _closes(values: dict[str, list[float]], dates: list[str]) -> pd.DataFrame:
    return pd.DataFrame(values, index=pd.to_datetime(dates))


def test_equal_weight_return_matches_the_hand_calculation():
    closes = _closes(
        {"AAA": [100.0, 110.0], "BBB": [100.0, 90.0], "CCC": [100.0, 100.0]},
        ["2020-01-02", "2020-01-03"],
    )

    returns = equal_weight_returns(closes)

    assert math.isclose(returns.iloc[1], 0.0, abs_tol=1e-12)


def test_symbol_missing_a_bar_is_excluded_from_that_day_only():
    closes = _closes(
        {
            "AAA": [100.0, 110.0, 121.0],
            "BBB": [100.0, np.nan, 100.0],
            "CCC": [100.0, 100.0, 100.0],
        },
        ["2020-01-02", "2020-01-03", "2020-01-06"],
    )

    returns = equal_weight_returns(closes)

    # Day 2: BBB has no bar, so only AAA (+10%) and CCC (0%) contribute.
    assert math.isclose(returns.iloc[1], 0.05, abs_tol=1e-12)
    # Day 3: BBB's previous close is missing, so it is excluded again.
    assert math.isclose(returns.iloc[2], 0.05, abs_tol=1e-12)


def test_calendar_year_compounding_matches_the_product():
    daily = pd.Series(
        [0.01, 0.02, -0.01],
        index=pd.to_datetime(["2020-01-02", "2020-06-01", "2020-12-31"]),
    )

    annual = calendar_year_returns(daily)

    assert set(annual) == {2020}
    assert math.isclose(annual[2020], 1.01 * 1.02 * 0.99 - 1.0)
    assert math.isclose(cumulative_return(daily), annual[2020])


def test_gap_is_panel_minus_rsp_in_percentage_points():
    dates = pd.to_datetime(["2020-12-31", "2021-12-31"])
    panel = pd.Series([0.10, -0.05], index=dates)
    rsp = pd.Series([0.07, -0.02], index=dates)
    spy = pd.Series([0.08, 0.01], index=dates)

    table = annual_gap_table(panel, rsp, spy, {2020: 500, 2021: 498})

    assert math.isclose(table[2020]["gap_pp"], 3.0)
    assert math.isclose(table[2021]["gap_pp"], -3.0)
    assert math.isclose(table[2020]["spy_return"], 0.08)
    assert table[2020]["symbols"] == 500
    assert math.isclose(average_annual_gap(table), 0.0)


def test_symbols_with_data_by_year_counts_columns_with_a_close():
    closes = _closes(
        {"AAA": [100.0, 101.0], "BBB": [np.nan, 50.0], "CCC": [np.nan, np.nan]},
        ["2020-12-31", "2021-01-04"],
    )

    counts = symbols_with_data_by_year(closes)

    assert counts == {2020: 1, 2021: 2}
