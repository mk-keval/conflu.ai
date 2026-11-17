"""Event-study maths for signal information.

The baseline measures a signal and an exit design together. This module isolates
the signal: it marks forward close-to-open returns after each signal, subtracts a
same-date universe mean, and compares the result with matched-random event sets.

Everything here is pure: functions return frames, dicts or arrays and never print
or write files. The script in ``scripts/research_event_study.py`` owns I/O.

Conventions
-----------
- A signal is True at the CLOSE of day ``t`` (the setup's own boolean Series).
- The entry row ``e`` is the symbol's NEXT bar, the same row the engine uses.
- ``ret_h = close[e + h - 1] / open[e] - 1`` for ``h >= 1``. ``h=1`` is the
  entry day open-to-close; ``h=5`` holds through the fifth bar including the
  entry day. A row without ``close[e + h - 1]`` is left as NaN and dropped, never
  filled.
- An event needs a signal AND ``eligible()`` on the signal bar, an existing
  entry bar, and ``entry_date >= eval_start``.
- Cooldown: an event is dropped when the previous ACCEPTED event on the same
  symbol is at most ``cooldown`` bars earlier.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from backend.app.research.control import matched_random_signals
from backend.app.research.engine import NON_TRADABLE
from backend.app.research.setups import eligible

DEFAULT_HORIZONS = (1, 5, 10, 20, 60)
EVAL_START = "2016-01-01"
TRADABLE_BENCHMARK = frozenset({"SPY", "^VIX", "VIX"})


def forward_return_frame(
    df: pd.DataFrame,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
) -> pd.DataFrame:
    """Forward open-to-close returns for every possible entry bar.

    For entry row ``e`` and horizon ``h`` the value is
    ``close[e + h - 1] / open[e] - 1``. Rows without the future close are NaN.

    Args:
        df: OHLCV frame with an ascending DatetimeIndex.
        horizons: Positive integer trading-day horizons.

    Returns:
        DataFrame indexed like ``df`` with one ``ret_<h>`` column per horizon.
    """
    out = pd.DataFrame(index=df.index)
    for horizon in horizons:
        if int(horizon) < 1:
            raise ValueError(f"horizon must be >= 1, got {horizon}")
        future_close = df["close"].shift(-(int(horizon) - 1))
        out[f"ret_{int(horizon)}"] = future_close / df["open"] - 1.0
    return out


def eligibility_frame(
    data: Mapping[str, pd.DataFrame],
    exclude: Iterable[str] = TRADABLE_BENCHMARK,
) -> pd.DataFrame:
    """Boolean eligibility by date and tradable symbol.

    Mirrors the frame built by the control suite: columns are tradable symbols,
    the index is the union of their dates, and a missing bar is False.
    """
    excluded = set(exclude)
    tradable = sorted(s for s in data if s not in excluded and len(data[s]))
    union = pd.DatetimeIndex(sorted({d for s in tradable for d in data[s].index}))
    return pd.DataFrame(
        {s: eligible(data[s]).reindex(union, fill_value=False).astype(bool) for s in tradable},
        index=union,
    )


def apply_cooldown(positions: Sequence[int], cooldown: int) -> np.ndarray:
    """Drop positions that repeat within ``cooldown`` bars of an accepted one.

    A position ``i`` is dropped when the previous accepted position ``j`` has
    ``i - j <= cooldown``. A dropped position does not reset the cooldown.
    """
    if int(cooldown) < 0:
        raise ValueError(f"cooldown must be >= 0, got {cooldown}")
    accepted: list[int] = []
    last: int | None = None
    for position in positions:
        i = int(position)
        if last is None or i - last > int(cooldown):
            accepted.append(i)
            last = i
    return np.asarray(accepted, dtype=int)


def accepted_event_positions(
    signal: Sequence[bool] | pd.Series,
    eligible_flags: Sequence[bool] | pd.Series,
    cooldown: int = 5,
) -> np.ndarray:
    """Bar positions where the signal AND eligibility fire, after cooldown."""
    mask = np.asarray(signal, dtype=bool) & np.asarray(eligible_flags, dtype=bool)
    return apply_cooldown(np.flatnonzero(mask), cooldown)


def collect_events(
    data: Mapping[str, pd.DataFrame],
    signals: Mapping[str, pd.Series],
    elig: pd.DataFrame,
    cooldown: int = 5,
    eval_start: str = EVAL_START,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    forward: Mapping[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Build one row per accepted event with its forward returns.

    The returned frame has ``symbol``, ``signal_date``, ``entry_date``,
    ``entry_bar`` and one ``ret_<h>`` column per horizon. Horizon NaNs are kept
    here and dropped by :func:`event_stats`, so each horizon keeps its own n.

    Args:
        data: OHLCV + indicator frames (benchmarks are ignored).
        signals: Symbol -> boolean Series indexed like that symbol's frame.
        elig: Eligibility frame from :func:`eligibility_frame` (or a compatible
            DataFrame).
        cooldown: Minimum separation, in bars, between accepted events.
        eval_start: Inclusive entry-date lower bound.
        horizons: Horizons to attach.
        forward: Optional precomputed ``symbol -> forward_return_frame`` cache.
    """
    start = pd.Timestamp(eval_start)
    rows: list[dict] = []
    for symbol, df in data.items():
        if symbol in TRADABLE_BENCHMARK or symbol not in signals or len(df) < 2:
            continue
        signal = signals[symbol].reindex(df.index, fill_value=False).fillna(False).to_numpy(dtype=bool)
        if symbol in elig.columns:
            flags = elig[symbol].reindex(df.index, fill_value=False).to_numpy(dtype=bool)
        else:
            flags = eligible(df).to_numpy(dtype=bool)

        candidates = np.flatnonzero(signal & flags)
        candidates = np.asarray([i for i in candidates if i + 1 < len(df)], dtype=int)
        candidates = np.asarray(
            [i for i in candidates if df.index[i + 1] >= start],
            dtype=int,
        )
        positions = apply_cooldown(candidates, cooldown)
        if positions.size == 0:
            continue

        returns = forward[symbol] if forward is not None and symbol in forward else None
        if returns is None:
            returns = forward_return_frame(df, horizons)
        entry_rows = returns.iloc[positions + 1]

        for offset, bar in enumerate(positions):
            row = {
                "symbol": symbol,
                "signal_date": df.index[bar],
                "entry_date": df.index[bar + 1],
                "entry_bar": int(bar + 1),
            }
            for horizon in horizons:
                row[f"ret_{int(horizon)}"] = float(entry_rows.iloc[offset][f"ret_{int(horizon)}"])
            rows.append(row)

    columns = ["symbol", "signal_date", "entry_date", "entry_bar"] + [
        f"ret_{int(h)}" for h in horizons
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns)


def universe_benchmark(
    data: Mapping[str, pd.DataFrame],
    elig: pd.DataFrame,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    eval_start: str = EVAL_START,
    forward: Mapping[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Mean forward return of all eligible symbols, by entry date.

    A symbol contributes to entry date ``e`` when it was eligible on the bar
    BEFORE ``e`` and has the forward data for that horizon. The result is the
    same-date universe mean subtracted from every event in :func:`event_stats`.
    """
    parts: list[pd.DataFrame] = []
    for symbol, df in data.items():
        if symbol in TRADABLE_BENCHMARK or len(df) < 2:
            continue
        flags = elig[symbol].reindex(df.index, fill_value=False).to_numpy(dtype=bool)
        previous_eligible = np.zeros(len(df), dtype=bool)
        previous_eligible[1:] = flags[:-1]
        if not previous_eligible.any():
            continue
        returns = forward[symbol] if forward is not None and symbol in forward else forward_return_frame(df, horizons)
        returns = returns.copy()
        returns.loc[~previous_eligible] = np.nan
        parts.append(returns)

    if not parts:
        return pd.DataFrame(columns=[f"ret_{int(h)}" for h in horizons])
    stacked = pd.concat(parts)
    benchmark = stacked.groupby(level=0).mean()
    return benchmark[benchmark.index >= pd.Timestamp(eval_start)]


def month_block_bootstrap_ci(
    values: Sequence[float],
    entry_dates: Sequence[pd.Timestamp],
    n_resamples: int = 2000,
    seed: int = 42,
) -> tuple[float, float]:
    """95% percentile CI of the mean, resampling entry year-months.

    Whole months are resampled with replacement so clustered entries widen the
    interval the same way they do in the baseline report's block bootstrap.
    """
    blocks: dict[str, list[float]] = {}
    for value, date in zip(values, entry_dates):
        key = pd.Timestamp(date).strftime("%Y-%m")
        blocks.setdefault(key, []).append(float(value))
    if len(values) < 2 or not blocks:
        return (float("nan"), float("nan"))

    months = list(blocks.values())
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_resamples):
        pooled: list[float] = []
        for _ in range(len(months)):
            pooled.extend(months[rng.randrange(len(months))])
        means.append(sum(pooled) / len(pooled))
    means.sort()
    low = means[int(0.025 * n_resamples)]
    high = means[int(0.975 * n_resamples) - 1]
    return (float(low), float(high))


def _excess_frame(
    events: pd.DataFrame,
    benchmark: pd.DataFrame,
    horizon: int,
) -> pd.DataFrame:
    """Rows with a finite event return and a finite same-date benchmark."""
    column = f"ret_{int(horizon)}"
    if events.empty or column not in events:
        return pd.DataFrame(columns=["entry_date", "ret", "bench", "excess"])
    frame = events[["entry_date", column]].rename(columns={column: "ret"}).copy()
    frame["bench"] = benchmark[column].reindex(frame["entry_date"]).to_numpy()
    frame = frame.dropna(subset=["ret", "bench"])
    frame["excess"] = frame["ret"] - frame["bench"]
    return frame


def mean_excess(
    events: pd.DataFrame,
    benchmark: pd.DataFrame,
    horizon: int,
) -> float:
    """Event-weighted mean excess return, or NaN when no event has data."""
    frame = _excess_frame(events, benchmark, horizon)
    if frame.empty:
        return float("nan")
    return float(frame["excess"].mean())


def event_stats(
    events: pd.DataFrame,
    benchmark: pd.DataFrame,
    horizon: int,
    n_resamples: int = 2000,
    seed: int = 42,
    cost_bps: float = 30.0,
) -> dict:
    """Per-horizon event statistics, including a month-block CI and by-year means.

    Returns ``n``, ``n_dates``, ``mean_excess_bp``, ``ci95_excess_bp``,
    ``hit_rate`` (share with excess > 0), ``raw_mean``,
    ``raw_mean_minus_cost`` (30 bps = 0.0030 by default) and ``by_year`` with
    the same mean excess in basis points for h=5 / h=20 reporting.
    """
    frame = _excess_frame(events, benchmark, horizon)
    if frame.empty:
        return {
            "horizon": int(horizon),
            "n": 0,
            "n_dates": 0,
            "mean_excess_bp": float("nan"),
            "ci95_excess_bp": [float("nan"), float("nan")],
            "hit_rate": float("nan"),
            "raw_mean": float("nan"),
            "raw_mean_minus_cost": float("nan"),
            "by_year": {},
        }

    excess = frame["excess"].to_numpy(dtype=float)
    raw = frame["ret"].to_numpy(dtype=float)
    low, high = month_block_bootstrap_ci(
        excess,
        frame["entry_date"].to_list(),
        n_resamples=n_resamples,
        seed=seed,
    )
    years = pd.to_datetime(frame["entry_date"]).dt.year
    by_year: dict[str, dict] = {}
    for year in sorted(years.unique()):
        mask = (years == year).to_numpy()
        year_excess = excess[mask]
        by_year[str(int(year))] = {
            "n": int(year_excess.size),
            "mean_excess_bp": float(year_excess.mean() * 10_000.0),
            "hit_rate": float((year_excess > 0).mean()),
        }

    return {
        "horizon": int(horizon),
        "n": int(excess.size),
        "n_dates": int(frame["entry_date"].nunique()),
        "mean_excess_bp": float(excess.mean() * 10_000.0),
        "ci95_excess_bp": [low * 10_000.0, high * 10_000.0],
        "hit_rate": float((excess > 0).mean()),
        "raw_mean": float(raw.mean()),
        "raw_mean_minus_cost": float(raw.mean() - cost_bps / 10_000.0),
        "by_year": by_year,
    }


def p_values(real_value: float, null_values: Sequence[float]) -> dict:
    """One-sided null p-values with the ``(count + 1) / (n + 1)`` correction."""
    values = np.asarray([v for v in null_values if not math.isnan(float(v))], dtype=float)
    n = int(values.size)
    if n == 0:
        return {
            "n_null": 0,
            "null_mean": float("nan"),
            "null_std": float("nan"),
            "p_high": 1.0,
            "p_low": 1.0,
        }
    return {
        "n_null": n,
        "null_mean": float(values.mean()),
        "null_std": float(values.std()),
        "p_high": float(((values >= real_value).sum() + 1) / (n + 1)),
        "p_low": float(((values <= real_value).sum() + 1) / (n + 1)),
    }


def null_distribution(
    data: Mapping[str, pd.DataFrame],
    signals: Mapping[str, pd.Series],
    elig: pd.DataFrame,
    benchmark: pd.DataFrame,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    n_null: int = 200,
    cooldown: int = 5,
    eval_start: str = EVAL_START,
    base_seed: int = 50000,
    forward: Mapping[str, pd.DataFrame] | None = None,
    progress=None,
) -> dict[int, list[float]]:
    """Matched-random null means of the event-weighted excess, per horizon.

    Each draw uses :func:`backend.app.research.control.matched_random_signals`
    with the setup's daily entry counts, then the same eligibility, cooldown and
    statistics as the real event set. Seeds are ``base_seed + i``. ``progress``
    is an optional callable invoked with the number of completed draws; the
    function itself does no I/O.
    """
    if forward is None:
        forward = {
            symbol: forward_return_frame(df, horizons)
            for symbol, df in data.items()
            if symbol not in TRADABLE_BENCHMARK and len(df) >= 2
        }
    values: dict[int, list[float]] = {int(h): [] for h in horizons}
    for i in range(int(n_null)):
        random_signals = matched_random_signals(data, signals, seed=base_seed + i, elig=elig)
        random_events = collect_events(
            data,
            random_signals,
            elig,
            cooldown=cooldown,
            eval_start=eval_start,
            horizons=horizons,
            forward=forward,
        )
        for horizon in horizons:
            values[int(horizon)].append(mean_excess(random_events, benchmark, horizon))
        if progress is not None:
            progress(i + 1)
    return values
