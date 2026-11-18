"""Pure helpers for the pre-2016 window study (E8 / H-16).

The study itself lives in ``scripts/research_window_study.py``.  This module
holds the small, testable pieces so the pre-registered pass rule and the
report's per-year tables cannot drift:

- :func:`by_year_excess` aggregates a bucket-excess frame by calendar year.
- :func:`eligible_symbols_by_year` counts symbols eligible at least once in a
  year, to show how the panel thins going back in time.
- :func:`assert_no_data_after` enforces the pre-registered end date.
- :func:`primary_cell_passes` is the single pre-registered PASS rule
  (``mean > 0`` AND ``ci_low > 0`` AND ``block_t >= z_crit(1)``).
"""

from __future__ import annotations

import math

import pandas as pd

Z_CRIT_ONE = 1.96


def by_year_excess(excess_frame: pd.DataFrame) -> dict[int, dict]:
    """Aggregate ``entry_date``/``excess`` rows by calendar year.

    Args:
        excess_frame: Frame from ``matched_control.bucket_excess_frame`` with at
            least ``entry_date`` and ``excess`` columns.  Empty frames are
            allowed.

    Returns:
        ``{year: {"n": int, "mean_excess_bp": float, "hit_rate": float}}``,
        where ``mean_excess_bp`` is the mean excess multiplied by 10,000 and
        ``hit_rate`` is the share of rows with ``excess > 0``.
    """
    if excess_frame is None or excess_frame.empty:
        return {}
    frame = excess_frame[["entry_date", "excess"]].copy()
    frame["year"] = pd.DatetimeIndex(frame["entry_date"]).year
    result: dict[int, dict] = {}
    for year, block in frame.groupby("year", sort=True):
        values = block["excess"].astype(float)
        result[int(year)] = {
            "n": int(len(values)),
            "mean_excess_bp": float(values.mean() * 10_000.0),
            "hit_rate": float((values > 0).mean()),
        }
    return result


def eligible_symbols_by_year(elig: pd.DataFrame) -> dict[int, int]:
    """Count symbols eligible on at least one day of each calendar year.

    Args:
        elig: Boolean eligibility frame indexed by date, one column per symbol.

    Returns:
        ``{year: number_of_symbols}`` for every year present in the index.
    """
    if elig is None or elig.empty:
        return {}
    frame = elig.fillna(False).astype(bool)
    years = pd.DatetimeIndex(frame.index).year
    result: dict[int, int] = {}
    for year, block in frame.groupby(years, sort=True):
        result[int(year)] = int(block.any(axis=0).sum())
    return result


def assert_no_data_after(data: dict[str, pd.DataFrame], end: str) -> None:
    """Raise ``ValueError`` when any frame has a row after ``end``.

    The pre-registered window ends on ``end``; a single later row would mean the
    panel was widened after the fact.  Frames ending exactly on ``end`` pass.
    """
    limit = pd.Timestamp(end)
    for symbol, df in data.items():
        if df is None or len(df) == 0:
            continue
        last = pd.DatetimeIndex(df.index).max()
        if last > limit:
            raise ValueError(
                f"{symbol} has a row after {limit.date()}: {last.date()}"
            )


def primary_cell_passes(
    mean: float,
    ci_low: float,
    block_t: float,
    z: float = Z_CRIT_ONE,
) -> bool:
    """The pre-registered PASS rule for the single primary cell.

    PASS requires all three conditions: the mean excess is positive, the 95%
    month-block CI lower bound is positive, and ``block_t`` reaches ``z``.
    Non-finite inputs fail.
    """
    values = (float(mean), float(ci_low), float(block_t), float(z))
    if not all(math.isfinite(value) for value in values):
        return False
    return bool(mean > 0.0 and ci_low > 0.0 and block_t >= z)
