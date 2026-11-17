"""Volatility-matched controls and percent-return measurement (E4).

The E1 event study and E2 exit study compared strategies with a control that
sampled random eligible symbols of ANY volatility.  The strategy pools are not
volatility-neutral (``low_vol_setup`` selects low-ATR names, for example), so
the old control's spread was much smaller than the strategy's own month-block
uncertainty, and the E2 R metric (``1R = 2 * ATR``) made the same percent move
count as more R for low-volatility names.  This module adds the measurement
layer that fixes both problems:

- :func:`vol_bucket_frame` assigns each eligible symbol/date to an ``atr_pct``
  rank bucket, using only information available on that date.
- :func:`vol_matched_random_signals` draws random signals with the same
  per-date/per-bucket counts as the strategy.
- :func:`bucket_benchmark` builds a previous-bar volatility-bucket benchmark
  for the event study.
- :func:`add_event_bucket`, :func:`bucket_excess_frame` attach the signal-date
  bucket and compute the bucket-relative event excess.
- :func:`add_pct_returns` adds cost-aware percent returns so R and percent
  metrics can be compared.
- :func:`block_summary` and :func:`z_crit` implement the honest significance
  rule (month-block CI and a Bonferroni ``block_t`` threshold).

Everything here is pure: functions return frames/dicts and never print or write
files.  The script ``scripts/research_vol_matched.py`` owns I/O.  The event and
exit maths are imported from :mod:`backend.app.research.events` and
:mod:`backend.app.research.exit_study` rather than copied.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from backend.app.research import events
from backend.app.research.engine import NON_TRADABLE

EVAL_START = events.EVAL_START
DEFAULT_N_BUCKETS = 10
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 42
CI_Z = 1.96
ALPHA = 0.05


def vol_bucket_frame(
    data: Mapping[str, pd.DataFrame],
    elig: pd.DataFrame,
    n_buckets: int = DEFAULT_N_BUCKETS,
) -> pd.DataFrame:
    """Volatility bucket of every eligible symbol on every date.

    On each date the eligible symbols are ranked by ``atr_pct`` with
    ``rank(pct=True, method="first")`` and assigned
    ``bucket = ceil(pct * n_buckets) - 1`` clipped to ``0..n_buckets-1``.
    Symbols that are not eligible (or have a NaN ``atr_pct``) get ``-1``.

    Args:
        data: Symbol -> OHLCV + indicator frame containing ``atr_pct``.
        elig: Boolean eligibility frame; its index and columns define the
            output shape.
        n_buckets: Number of volatility buckets (default 10).

    Returns:
        Integer DataFrame indexed like ``elig`` with one column per symbol.
    """
    if int(n_buckets) < 1:
        raise ValueError(f"n_buckets must be >= 1, got {n_buckets}")
    n_buckets = int(n_buckets)
    columns = list(elig.columns)
    atr = pd.DataFrame(
        {
            symbol: (
                data[symbol]["atr_pct"].reindex(elig.index)
                if symbol in data and "atr_pct" in data[symbol]
                else np.nan
            )
            for symbol in columns
        },
        index=elig.index,
    )
    mask = elig.reindex(index=elig.index, columns=columns).fillna(False).astype(bool)
    mask = mask & atr.notna()

    ranked = atr.where(mask).rank(axis=1, pct=True, method="first")
    values = np.ceil(ranked.to_numpy(dtype=float) * n_buckets) - 1.0
    values = np.clip(values, 0, n_buckets - 1)
    values = np.where(mask.to_numpy(dtype=bool), values, -1.0)
    values = np.where(np.isfinite(values), values, -1.0)
    return pd.DataFrame(values.astype(int), index=elig.index, columns=columns)


def vol_matched_random_signals(
    data: Mapping[str, pd.DataFrame],
    real_signals: Mapping[str, pd.Series],
    seed: int,
    elig: pd.DataFrame,
    buckets: pd.DataFrame,
    stats: dict | None = None,
) -> dict[str, pd.Series]:
    """Random control matched to the strategy's per-date/per-bucket counts.

    For every date and every volatility bucket in which the real setup fires
    ``c`` times, draw ``k = min(c, pool size)`` distinct symbols from the
    symbols that are eligible AND in that bucket on that date.  Dates and
    buckets are visited in sorted order, so a fixed seed is reproducible.

    Args:
        data: Market data.
        real_signals: Real signals, already restricted to eligible bars.
        seed: Random seed.
        elig: Eligibility frame (index = dates, columns = tradable symbols).
        buckets: Volatility buckets from :func:`vol_bucket_frame`.
        stats: Optional dict.  When given, ``stats["requested"]`` and
            ``stats["drawn"]`` are incremented so shortfalls are visible.

    Returns:
        Symbol -> boolean Series reindexed to that symbol's own index.
        Non-tradable symbols get an all-False Series.
    """
    tradable = sorted(s for s in data if s not in NON_TRADABLE)
    index = elig.index
    bucket_frame = buckets.reindex(index=index, columns=tradable)
    bucket_values = bucket_frame.fillna(-1).to_numpy(dtype=int)
    elig_values = (
        elig.reindex(index=index, columns=tradable).fillna(False).to_numpy(dtype=bool)
    )
    column_position = {symbol: i for i, symbol in enumerate(tradable)}

    counts = np.zeros((len(index), len(tradable)), dtype=np.int64)
    for symbol, series in real_signals.items():
        position = column_position.get(symbol)
        if position is None:
            continue
        aligned = series.reindex(index, fill_value=False).fillna(False)
        counts[:, position] = aligned.to_numpy(dtype=bool)

    marks = np.zeros((len(index), len(tradable)), dtype=bool)
    rng = np.random.default_rng(int(seed))
    requested = 0
    drawn = 0

    for row in range(len(index)):
        row_counts = counts[row]
        if not row_counts.any():
            continue
        row_buckets = bucket_values[row]
        row_eligible = elig_values[row]
        firing_buckets = np.unique(row_buckets[row_counts > 0])
        for bucket in firing_buckets:
            if bucket < 0:
                # Ineligible signals cannot be matched by a plausible control.
                continue
            requested_count = int(row_counts[row_buckets == bucket].sum())
            pool = np.flatnonzero(row_eligible & (row_buckets == bucket))
            k = min(requested_count, int(pool.size))
            requested += requested_count
            drawn += k
            if k > 0:
                chosen = rng.choice(pool, size=k, replace=False)
                marks[row, chosen] = True

    if stats is not None:
        stats["requested"] = int(stats.get("requested", 0)) + requested
        stats["drawn"] = int(stats.get("drawn", 0)) + drawn

    signals: dict[str, pd.Series] = {}
    for symbol, df in data.items():
        position = column_position.get(symbol)
        if symbol in NON_TRADABLE or position is None:
            signals[symbol] = pd.Series(False, index=df.index)
            continue
        series = pd.Series(marks[:, position], index=index, dtype=bool)
        signals[symbol] = series.reindex(df.index, fill_value=False)
    return signals


def bucket_benchmark(
    data: Mapping[str, pd.DataFrame],
    elig: pd.DataFrame,
    buckets: pd.DataFrame,
    horizons: Sequence[int],
    eval_start: str = EVAL_START,
    forward: Mapping[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Mean forward return by ``(entry_date, previous_bar_bucket)``.

    A symbol contributes to entry date ``e`` and bucket ``b`` when its bucket
    on the bar BEFORE ``e`` was ``b`` and it has the forward data.  Shifting the
    bucket series by one bar mirrors :func:`events.universe_benchmark`'s
    previous-bar eligibility and prevents look-ahead.

    Returns:
        DataFrame indexed by ``(entry_date, bucket)`` with one ``ret_<h>``
        column per horizon, restricted to ``entry_date >= eval_start``.
    """
    horizon_list = [int(h) for h in horizons]
    ret_columns = [f"ret_{h}" for h in horizon_list]
    empty_index = pd.MultiIndex.from_arrays(
        [pd.DatetimeIndex([]), pd.Index([], dtype=int)],
        names=["entry_date", "bucket"],
    )
    parts: list[pd.DataFrame] = []
    for symbol, df in data.items():
        if symbol in NON_TRADABLE or len(df) < 2 or symbol not in buckets.columns:
            continue
        bucket_series = buckets[symbol].reindex(df.index, fill_value=-1)
        bucket_series = bucket_series.fillna(-1).to_numpy(dtype=int)
        previous_bucket = np.full(len(df), -1, dtype=int)
        previous_bucket[1:] = bucket_series[:-1]
        if not (previous_bucket >= 0).any():
            continue
        returns = (
            forward[symbol]
            if forward is not None and symbol in forward
            else events.forward_return_frame(df, horizon_list)
        )
        frame = returns.copy()
        frame["bucket"] = previous_bucket
        frame.loc[previous_bucket < 0, ret_columns] = np.nan
        parts.append(frame)

    if not parts:
        return pd.DataFrame(columns=ret_columns, index=empty_index)

    stacked = pd.concat(parts)
    stacked.index.name = "entry_date"
    grouped = (
        stacked.reset_index()
        .groupby(["entry_date", "bucket"], sort=True)[ret_columns]
        .mean()
    )
    grouped = grouped[
        grouped.index.get_level_values("entry_date") >= pd.Timestamp(eval_start)
    ]
    return grouped


def add_event_bucket(events_frame: pd.DataFrame, buckets: pd.DataFrame) -> pd.DataFrame:
    """Add a ``bucket`` column taken from ``(symbol, signal_date)``.

    The bucket is the one on the SIGNAL date, so only data up to the signal bar
    is used.  Events whose symbol/date is missing from ``buckets`` get ``-1``.
    """
    out = events_frame.copy()
    if out.empty:
        out["bucket"] = pd.Series(dtype=int)
        return out
    if "symbol" not in out or "signal_date" not in out:
        raise KeyError("events frame needs 'symbol' and 'signal_date' columns")

    row_position = buckets.index.get_indexer(pd.DatetimeIndex(out["signal_date"]))
    column_position = buckets.columns.get_indexer(pd.Index(out["symbol"]))
    matrix = buckets.to_numpy(dtype=int)
    values = np.full(len(out), -1, dtype=int)
    valid = (row_position >= 0) & (column_position >= 0)
    values[valid] = matrix[row_position[valid], column_position[valid]]
    out["bucket"] = values
    return out


def bucket_excess_frame(
    events_frame: pd.DataFrame,
    benchmark: pd.DataFrame,
    horizon: int,
) -> pd.DataFrame:
    """Event return, bucket benchmark and excess for one horizon.

    Returns columns ``entry_date``, ``ret``, ``bench`` and ``excess``.  Rows
    with a NaN event return or a NaN bucket benchmark are dropped, never filled.
    """
    column = f"ret_{int(horizon)}"
    if (
        events_frame.empty
        or column not in events_frame
        or "bucket" not in events_frame
        or benchmark is None
        or column not in benchmark
    ):
        return pd.DataFrame(columns=["entry_date", "ret", "bench", "excess"])

    frame = (
        events_frame[["entry_date", column, "bucket"]]
        .rename(columns={column: "ret"})
        .copy()
    )
    keys = pd.MultiIndex.from_arrays(
        [pd.DatetimeIndex(frame["entry_date"]), frame["bucket"].to_numpy(dtype=int)],
        names=["entry_date", "bucket"],
    )
    frame["bench"] = benchmark[column].reindex(keys).to_numpy(dtype=float)
    frame = frame.dropna(subset=["ret", "bench"])
    frame["excess"] = frame["ret"].astype(float) - frame["bench"].astype(float)
    return frame[["entry_date", "ret", "bench", "excess"]].reset_index(drop=True)


def add_pct_returns(trades: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    """Add percent returns to an exit-study trade frame.

    The task defines the cost-aware percent return as
    ``exit_price * (1 - c) / (entry_price * (1 + c)) - 1`` with
    ``c = cost_bps / 10_000``.  That formula is stored in ``ret_gross_pct``
    exactly as specified and mirrored in ``ret_net_pct``, the name the Part 2
    report uses.  Trades with NaN prices stay NaN, never filled.
    """
    out = trades.copy()
    if out.empty:
        out["ret_gross_pct"] = pd.Series(dtype=float)
        out["ret_net_pct"] = pd.Series(dtype=float)
        return out
    cost = float(cost_bps) / 10_000.0
    entry = out["entry_price"].astype(float)
    exit_price = out["exit_price"].astype(float)
    pct = exit_price * (1.0 - cost) / (entry * (1.0 + cost)) - 1.0
    out["ret_gross_pct"] = pct
    out["ret_net_pct"] = pct
    return out


def block_summary(
    values: Sequence[float],
    entry_dates: Sequence[pd.Timestamp],
    reference: float,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict:
    """Month-block CI and honest ``block_t`` for one metric.

    ``se_block = (ci_high - ci_low) / (2 * 1.96)`` and
    ``block_t = (mean - reference) / se_block``.  ``reference_in_ci`` says
    whether the reference sits inside the 95% month-block CI.  A cell can only
    pass when the CI excludes the reference AND ``|block_t|`` clears the
    Bonferroni threshold from :func:`z_crit`.
    """
    raw_values = np.asarray(list(values), dtype=float)
    raw_dates = list(entry_dates)
    finite = np.isfinite(raw_values)
    if finite.all():
        clean_values = raw_values
        clean_dates = raw_dates
    else:
        clean_values = raw_values[finite]
        clean_dates = [date for date, keep in zip(raw_dates, finite) if keep]

    n = int(clean_values.size)
    reference_value = float(reference)
    if n == 0:
        return {
            "n": 0,
            "mean": float("nan"),
            "ci_low": float("nan"),
            "ci_high": float("nan"),
            "se_block": float("nan"),
            "reference_in_ci": False,
            "block_t": float("nan"),
        }

    mean = float(clean_values.mean())
    low, high = events.month_block_bootstrap_ci(
        clean_values,
        clean_dates,
        n_resamples=int(n_resamples),
        seed=int(seed),
    )
    if math.isfinite(low) and math.isfinite(high):
        se_block = (high - low) / (2.0 * CI_Z)
        reference_in_ci = bool(low <= reference_value <= high)
    else:
        se_block = float("nan")
        reference_in_ci = False

    if math.isfinite(se_block) and se_block > 0 and math.isfinite(reference_value):
        block_t = (mean - reference_value) / se_block
    else:
        block_t = float("nan")

    return {
        "n": n,
        "mean": mean,
        "ci_low": float(low),
        "ci_high": float(high),
        "se_block": float(se_block),
        "reference_in_ci": reference_in_ci,
        "block_t": float(block_t),
    }


def z_crit(m: int) -> float:
    """Two-sided Bonferroni critical value for ``m`` cells.

    ``z_crit(m) = NormalDist().inv_cdf(1 - 0.05 / (2 * m))``; ``m = 20`` gives
    about ``3.023``.  ``statistics.NormalDist`` is standard-library only.
    """
    if int(m) < 1:
        raise ValueError(f"m must be >= 1, got {m}")
    return float(statistics.NormalDist().inv_cdf(1.0 - ALPHA / (2.0 * int(m))))


def cell_passes(block_t: float, reference_in_ci: bool, z: float) -> bool:
    """A cell passes only if ``|block_t| >= z`` and the reference is outside the CI."""
    return bool(
        math.isfinite(float(block_t))
        and abs(float(block_t)) >= float(z)
        and not bool(reference_in_ci)
    )
