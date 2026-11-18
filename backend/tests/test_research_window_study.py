"""Tests for the pre-2016 window-study helpers and script defaults (E8)."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from backend.app.research.window_study import (
    assert_no_data_after,
    by_year_excess,
    eligible_symbols_by_year,
    primary_cell_passes,
)
from scripts.research_window_study import build_parser

PREREGISTERED = {
    "start": "2005-01-01",
    "end": "2015-12-31",
    "eval_start": "2006-01-01",
}


def _excess_frame():
    return pd.DataFrame(
        {
            "entry_date": pd.to_datetime(
                ["2020-01-02", "2020-06-01", "2021-03-01"]
            ),
            "ret": [0.03, 0.02, 0.01],
            "bench": [0.02, 0.025, 0.008],
            "excess": [0.01, -0.005, 0.002],
        }
    )


def test_by_year_excess_matches_hand_computation():
    result = by_year_excess(_excess_frame())

    assert set(result) == {2020, 2021}
    assert result[2020]["n"] == 2
    assert math.isclose(result[2020]["mean_excess_bp"], 25.0)
    assert math.isclose(result[2020]["hit_rate"], 0.5)
    assert result[2021]["n"] == 1
    assert math.isclose(result[2021]["mean_excess_bp"], 20.0)
    assert math.isclose(result[2021]["hit_rate"], 1.0)
    assert by_year_excess(pd.DataFrame(columns=["entry_date", "excess"])) == {}


def test_eligible_symbols_by_year_counts_symbols_eligible_at_least_once():
    index = pd.to_datetime(
        ["2020-01-02", "2020-12-31", "2021-01-04", "2021-12-31"]
    )
    elig = pd.DataFrame(
        {
            "AAA": [True, False, False, False],
            "BBB": [False, False, True, False],
            "CCC": [False, True, False, True],
        },
        index=index,
    )

    result = eligible_symbols_by_year(elig)

    assert result == {2020: 2, 2021: 2}
    assert eligible_symbols_by_year(pd.DataFrame()) == {}


def test_assert_no_data_after_raises_on_a_later_row():
    data = {
        "AAA": pd.DataFrame({"close": [1.0, 2.0]}, index=pd.to_datetime(["2015-12-30", "2015-12-31"])),
        "BBB": pd.DataFrame({"close": [1.0, 2.0]}, index=pd.to_datetime(["2015-12-31", "2016-01-04"])),
    }

    with pytest.raises(ValueError, match="BBB has a row after 2015-12-31"):
        assert_no_data_after(data, "2015-12-31")

    assert_no_data_after({"AAA": data["AAA"]}, "2015-12-31")


def test_primary_cell_passes_requires_all_three_conditions():
    assert primary_cell_passes(10.0, 1.0, 2.5) is True

    # One failing condition at a time must fail the cell.
    assert primary_cell_passes(-0.1, 1.0, 2.5) is False
    assert primary_cell_passes(10.0, -0.1, 2.5) is False
    assert primary_cell_passes(10.0, 1.0, 1.95) is False

    # Exactly z_crit(1) passes; non-finite inputs fail.
    assert primary_cell_passes(10.0, 1.0, 1.96) is True
    assert primary_cell_passes(float("nan"), 1.0, 2.5) is False


def test_script_defaults_equal_the_pre_registered_values():
    args = build_parser().parse_args([])

    assert args.start == PREREGISTERED["start"]
    assert args.end == PREREGISTERED["end"]
    assert args.eval_start == PREREGISTERED["eval_start"]
