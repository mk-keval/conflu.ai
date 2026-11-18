"""Survivorship / current-membership size estimate (E9).

Pure functions used by ``scripts/research_survivorship.py``.  The estimate is a
measurement, not a test: it compares a daily-rebalanced equal-weight portfolio
of today's S&P 500 constituents with RSP (equal-weight S&P 500 ETF with
point-in-time membership) and SPY.

Definitions (also printed in the report):

- Panel daily return: mean over panel symbols that have both ``close[d]`` and
  ``close[d-1]`` of ``close[d] / close[d-1] - 1`` (daily-rebalanced equal
  weight; no eligibility filter).
- Calendar-year return: ``product(1 + daily_return) - 1``.
- Gap: ``panel return - RSP return`` in percentage points.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def equal_weight_returns(closes: pd.DataFrame) -> pd.Series:
    """Daily-rebalanced equal-weight returns from a close-price frame.

    A symbol contributes on date ``d`` only when it has both ``close[d]`` and
    ``close[d-1]``.  Missing bars therefore drop out of that day only; the
    following day is also NaN for that symbol because its previous close is
    missing.  A row with no contributing symbol is NaN.
    """
    if closes is None or closes.empty:
        return pd.Series(dtype=float)
    frame = closes.sort_index()
    returns = frame / frame.shift(1) - 1.0
    return returns.mean(axis=1, skipna=True).astype(float)


def calendar_year_returns(daily_returns: pd.Series) -> dict[int, float]:
    """Compound daily returns into calendar-year returns."""
    if daily_returns is None or daily_returns.empty:
        return {}
    series = daily_returns.astype(float)
    years = pd.DatetimeIndex(series.index).year
    result: dict[int, float] = {}
    for year, block in series.groupby(years, sort=True):
        values = block.to_numpy(dtype=float)
        values = values[np.isfinite(values)]
        result[int(year)] = (
            float(np.prod(1.0 + values) - 1.0) if values.size else float("nan")
        )
    return result


def symbols_with_data_by_year(closes: pd.DataFrame) -> dict[int, int]:
    """Number of panel symbols with at least one close in each year."""
    if closes is None or closes.empty:
        return {}
    frame = closes.sort_index()
    years = pd.DatetimeIndex(frame.index).year
    result: dict[int, int] = {}
    for year, block in frame.groupby(years, sort=True):
        result[int(year)] = int(block.notna().any(axis=0).sum())
    return result


def cumulative_return(daily_returns: pd.Series) -> float:
    """Compound every finite daily return in the series."""
    if daily_returns is None or daily_returns.empty:
        return float("nan")
    values = daily_returns.to_numpy(dtype=float)
    values = values[np.isfinite(values)]
    if not values.size:
        return float("nan")
    return float(np.prod(1.0 + values) - 1.0)


def annual_gap_table(
    panel_daily: pd.Series,
    rsp_daily: pd.Series,
    spy_daily: pd.Series,
    symbols_by_year: dict[int, int],
) -> dict[int, dict]:
    """Per-year panel, RSP, SPY returns and the gap in percentage points."""
    panel = calendar_year_returns(panel_daily)
    rsp = calendar_year_returns(rsp_daily)
    spy = calendar_year_returns(spy_daily)
    years = sorted(set(panel) & set(rsp))
    table: dict[int, dict] = {}
    for year in years:
        gap_pp = (panel[year] - rsp[year]) * 100.0
        table[int(year)] = {
            "panel_return": panel[year],
            "rsp_return": rsp[year],
            "spy_return": spy.get(year, float("nan")),
            "gap_pp": gap_pp,
            "symbols": int(symbols_by_year.get(year, 0)),
        }
    return table


def average_annual_gap(table: dict[int, dict]) -> float:
    """Mean of the per-year gaps in percentage points."""
    values = [
        row["gap_pp"]
        for row in table.values()
        if math.isfinite(float(row["gap_pp"]))
    ]
    return float(np.mean(values)) if values else float("nan")
