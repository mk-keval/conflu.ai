"""Exit-shape study: apply different exit rules to the same entries.

The baseline couples signal information to one exit design. This module keeps the
entries fixed (signal at the close of ``t``, entry at the open of ``t+1``, ATR
from the signal bar) and varies only the exit, one trade at a time. It ignores
portfolio capacity, slot competition and position sizing, so it is a study of
exit shape, not a portfolio result.

Everything here is pure: functions take frames/arrays and return frames or
dicts. No printing, no file I/O. The script
``scripts/research_exit_study.py`` owns I/O.

Conventions
-----------
- ``1R`` is always ``2 * ATR`` (the initial stop distance), for every variant, so
  R values stay comparable even when a variant has no stop.
- Costs: ``c = 15 bps`` per side, ``r_net =
  (exit * (1 - c) - entry * (1 + c)) / (2 * ATR)`` and ``r_gross =
  (exit - entry) / (2 * ATR)`` (the engine's formulas).
- Stop order mirrors the engine: gap stop at the open, then the stop, then the
  gap target, then the target, then the time exit at the close. The stop wins
  ties.
- A trailing stop used on bar ``k`` is built from the highest HIGH of the OPEN
  trade's bars from the entry bar through ``k-1`` only and is never lowered. On
  the entry bar only the initial stop applies. Bar ``k``'s own high cannot move
  the stop used on bar ``k``.
- A trade whose path runs past the panel end is dropped, never marked to market.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from backend.app.research.control import matched_random_signals
from backend.app.research.engine import NON_TRADABLE
from backend.app.research.setups import eligible

EVAL_START = "2016-01-01"
DEFAULT_COST_BPS = 15.0
DEFAULT_NULL_BASE_SEED = 60000


@dataclass(frozen=True)
class ExitVariant:
    """One exit design.

    ``max_hold`` follows the engine's meaning: exit at the close of the bar
    where ``bars_held >= max_hold`` (``bars_held`` is 0 on the entry bar).
    ``B4`` uses ``max_hold=19`` so it exits at the close of the 20th bar
    including the entry day, the same point as the event study's ``h=20``.
    """

    name: str
    stop_atr: float | None
    target_atr: float | None
    trail_atr: float | None
    max_hold: int | None
    description: str


VARIANTS: dict[str, ExitVariant] = {
    "B0": ExitVariant(
        "B0", 2.0, 3.0, None, 15,
        "stop 2 ATR, target 3 ATR, max hold 15 (engine rules and order)",
    ),
    "B1": ExitVariant(
        "B1", 2.0, None, None, 15,
        "stop 2 ATR, no target, max hold 15",
    ),
    "B2": ExitVariant(
        "B2", 2.0, None, 3.0, 60,
        "stop 2 ATR plus 3 ATR trailing stop, no target, max hold 60",
    ),
    "B3": ExitVariant(
        "B3", 2.0, None, 2.0, 30,
        "stop 2 ATR plus 2 ATR trailing stop, no target, max hold 30",
    ),
    "B4": ExitVariant(
        "B4", None, None, None, 19,
        "no stop, no target, exit at the close of the 20th bar including entry (h=20)",
    ),
}


@dataclass(frozen=True)
class Entry:
    """One entry candidate: signal bar, entry bar and signal-bar ATR."""

    symbol: str
    signal_bar: int
    entry_bar: int
    atr: float


def trailing_stop_path(
    high: Sequence[float] | np.ndarray,
    entry_bar: int,
    end_bar: int,
    atr: float,
    trail_atr: float,
    initial_stop: float,
) -> np.ndarray:
    """Stop level used on each bar ``entry_bar..end_bar``, never decreasing.

    The entry bar uses ``initial_stop``. Each later bar uses the highest high of
    the open trade's bars through the previous bar, so a spike on bar ``k``
    raises the stop for bar ``k + 1``, never for bar ``k``.
    """
    high = np.asarray(high, dtype=float)
    stops = np.empty(end_bar - entry_bar + 1, dtype=float)
    stop = float(initial_stop)
    running_high = -math.inf
    for k in range(entry_bar, end_bar + 1):
        if k > entry_bar:
            candidate = running_high - float(trail_atr) * float(atr)
            if candidate > stop:
                stop = candidate
        stops[k - entry_bar] = stop
        if high[k] > running_high:
            running_high = float(high[k])
    return stops


def simulate_trade(
    open_: Sequence[float] | np.ndarray,
    high: Sequence[float] | np.ndarray,
    low: Sequence[float] | np.ndarray,
    close: Sequence[float] | np.ndarray,
    atr: float,
    entry_bar: int,
    variant: ExitVariant,
    cost_bps: float = DEFAULT_COST_BPS,
) -> dict | None:
    """Simulate one trade under ``variant``; ``None`` when it runs past the panel.

    Args:
        open_, high, low, close: Per-symbol price arrays.
        atr: ATR14 of the signal bar (the bar before ``entry_bar``).
        entry_bar: Bar index at whose open the trade enters.
        variant: Exit design.
        cost_bps: Cost per side in basis points (default 15).

    Returns:
        Dict with exit price/reason, bars held and R values, or ``None`` when
        the trade has no exit before the panel ends (dropped, not marked).
    """
    open_ = np.asarray(open_, dtype=float)
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close, dtype=float)
    n = close.size
    if entry_bar < 0 or entry_bar >= n:
        return None
    if not math.isfinite(float(atr)) or float(atr) <= 0:
        return None
    entry = float(open_[entry_bar])
    if not math.isfinite(entry) or entry <= 0:
        return None

    if variant.stop_atr is not None:
        stop = entry - variant.stop_atr * float(atr)
        # Match the engine exactly: risk is the distance from entry to the
        # INITIAL stop, and it never changes when a trailing stop rises.
        risk = entry - stop
    else:
        stop = -math.inf
        # No stop: 1R is still the standard 2 ATR so R values stay comparable.
        risk = 2.0 * float(atr)
    if variant.target_atr is not None:
        target = entry + variant.target_atr * float(atr)
    else:
        target = math.inf

    end_bar = n - 1
    if variant.max_hold is not None:
        end_bar = min(end_bar, entry_bar + int(variant.max_hold))
    cost = float(cost_bps) / 10_000.0
    running_high = -math.inf

    for k in range(entry_bar, end_bar + 1):
        if variant.trail_atr is not None and k > entry_bar:
            candidate = running_high - variant.trail_atr * float(atr)
            if candidate > stop:
                stop = candidate

        bar_open = float(open_[k])
        bar_high = float(high[k])
        bar_low = float(low[k])
        bars_held = k - entry_bar
        exit_price = None
        reason = None

        if variant.stop_atr is not None or variant.trail_atr is not None:
            if bar_open <= stop:
                exit_price = bar_open
                reason = "stop_gap"
            elif bar_low <= stop:
                exit_price = float(stop)
                reason = "stop"

        if exit_price is None and variant.target_atr is not None:
            if bar_open >= target:
                exit_price = bar_open
                reason = "target_gap"
            elif bar_high >= target:
                exit_price = float(target)
                reason = "target"

        if (
            exit_price is None
            and bars_held > 0
            and variant.max_hold is not None
            and bars_held >= int(variant.max_hold)
        ):
            exit_price = float(close[k])
            reason = "time"

        if bar_high > running_high:
            running_high = bar_high

        if exit_price is not None:
            r_gross = (exit_price - entry) / risk
            r_net = (exit_price * (1.0 - cost) - entry * (1.0 + cost)) / risk
            return {
                "entry_bar": int(entry_bar),
                "exit_bar": int(k),
                "entry_price": entry,
                "exit_price": float(exit_price),
                "exit_reason": reason,
                "bars_held": int(bars_held),
                "r_gross": float(r_gross),
                "r_net": float(r_net),
            }

    return None


def _symbol_arrays(df: pd.DataFrame) -> dict:
    """Price arrays built once per symbol."""
    return {
        "open": df["open"].to_numpy(dtype=float),
        "high": df["high"].to_numpy(dtype=float),
        "low": df["low"].to_numpy(dtype=float),
        "close": df["close"].to_numpy(dtype=float),
        "atr": df["atr14"].to_numpy(dtype=float),
        "index": df.index,
    }


def entry_candidates(
    data: Mapping[str, pd.DataFrame],
    signals: Mapping[str, pd.Series],
    elig: pd.DataFrame | None = None,
    eval_start: str = EVAL_START,
) -> list[Entry]:
    """All entries: signal AND eligible on ``t``, entry bar exists, ATR valid.

    The entry date must be on or after ``eval_start``. A missing/short entry bar,
    a NaN ATR or an ATR <= 0 is skipped, exactly as the engine does.
    """
    start = pd.Timestamp(eval_start)
    entries: list[Entry] = []
    for symbol, df in data.items():
        if symbol in NON_TRADABLE or symbol not in signals or len(df) < 2:
            continue
        signal = signals[symbol].reindex(df.index, fill_value=False)
        signal = signal.fillna(False).to_numpy(dtype=bool)
        if not signal.any():
            continue
        if elig is not None and symbol in elig.columns:
            flags = elig[symbol].reindex(df.index, fill_value=False).to_numpy(dtype=bool)
        else:
            flags = eligible(df).to_numpy(dtype=bool)
        atr = df["atr14"].to_numpy(dtype=float) if "atr14" in df else np.full(len(df), np.nan)
        dates = df.index
        for bar in np.flatnonzero(signal & flags):
            entry_bar = int(bar) + 1
            if entry_bar >= len(df):
                continue
            if dates[entry_bar] < start:
                continue
            atr_value = float(atr[bar])
            if not math.isfinite(atr_value) or atr_value <= 0:
                continue
            entries.append(Entry(symbol, int(bar), entry_bar, atr_value))
    return entries


def simulate_entries(
    data: Mapping[str, pd.DataFrame],
    entries: Sequence[Entry],
    variant: ExitVariant,
    cost_bps: float = DEFAULT_COST_BPS,
    cache: dict[str, dict] | None = None,
) -> pd.DataFrame:
    """Simulate every entry under one variant and return a trade frame.

    ``cache`` is an optional ``symbol -> _symbol_arrays`` dict reused across
    variants and null draws. Dropped trades (path past the panel end) are absent.
    """
    columns = [
        "symbol", "entry_bar", "exit_bar", "entry_date", "exit_date",
        "entry_price", "exit_price", "exit_reason", "bars_held", "r_gross", "r_net",
    ]
    if cache is None:
        cache = {}
    by_symbol: dict[str, list[Entry]] = {}
    for entry in entries:
        by_symbol.setdefault(entry.symbol, []).append(entry)

    rows: list[dict] = []
    for symbol, symbol_entries in by_symbol.items():
        df = data.get(symbol)
        if df is None:
            continue
        arrays = cache.get(symbol)
        if arrays is None:
            arrays = _symbol_arrays(df)
            cache[symbol] = arrays
        for entry in symbol_entries:
            result = simulate_trade(
                arrays["open"], arrays["high"], arrays["low"], arrays["close"],
                entry.atr, entry.entry_bar, variant, cost_bps=cost_bps,
            )
            if result is None:
                continue
            result["symbol"] = symbol
            result["entry_date"] = arrays["index"][result["entry_bar"]]
            result["exit_date"] = arrays["index"][result["exit_bar"]]
            rows.append(result)
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns)


def trade_stats(trades: pd.DataFrame) -> dict:
    """Summary stats for one variant: R means, win rate, PF, hold, exit mix."""
    if trades is None or trades.empty:
        return {
            "n": 0,
            "mean_r_net": float("nan"),
            "mean_r_gross": float("nan"),
            "win_rate": float("nan"),
            "avg_win_r": float("nan"),
            "avg_loss_r": float("nan"),
            "profit_factor": float("nan"),
            "mean_bars_held": float("nan"),
            "exit_share": {},
        }
    r_net = trades["r_net"].to_numpy(dtype=float)
    r_gross = trades["r_gross"].to_numpy(dtype=float)
    wins = r_net[r_net > 0]
    losses = r_net[r_net < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    elif gross_profit > 0:
        profit_factor = math.inf
    else:
        profit_factor = float("nan")
    exit_share = (
        trades["exit_reason"].value_counts(normalize=True).sort_index().round(6).to_dict()
    )
    return {
        "n": int(r_net.size),
        "mean_r_net": float(r_net.mean()),
        "mean_r_gross": float(r_gross.mean()),
        "win_rate": float((r_net > 0).mean()),
        "avg_win_r": float(wins.mean()) if wins.size else float("nan"),
        "avg_loss_r": float(losses.mean()) if losses.size else float("nan"),
        "profit_factor": float(profit_factor),
        "mean_bars_held": float(trades["bars_held"].mean()),
        "exit_share": {str(k): float(v) for k, v in exit_share.items()},
    }


def null_summary(real_mean: float, null_means: Sequence[float]) -> dict:
    """Null mean/std, gap, gap/std and one-sided p-values with ``(k+1)/(n+1)``."""
    values = np.asarray(
        [v for v in null_means if v is not None and math.isfinite(float(v))],
        dtype=float,
    )
    n = int(values.size)
    if n == 0 or not math.isfinite(float(real_mean)):
        return {
            "n_null": n,
            "null_mean": float("nan"),
            "null_std": float("nan"),
            "gap": float("nan"),
            "gap_over_std": float("nan"),
            "p_high": 1.0,
            "p_low": 1.0,
        }
    null_mean = float(values.mean())
    null_std = float(values.std())
    gap = float(real_mean) - null_mean
    return {
        "n_null": n,
        "null_mean": null_mean,
        "null_std": null_std,
        "gap": gap,
        "gap_over_std": gap / null_std if null_std > 0 else float("nan"),
        "p_high": float(((values >= real_mean).sum() + 1) / (n + 1)),
        "p_low": float(((values <= real_mean).sum() + 1) / (n + 1)),
    }


def mask_ineligible(
    data: Mapping[str, pd.DataFrame],
    signals: Mapping[str, pd.Series],
    elig: pd.DataFrame | None = None,
) -> dict[str, pd.Series]:
    """Signal series restricted to bars where the symbol is eligible.

    Passing this to :func:`matched_random_signals` makes the control's daily
    counts equal the real eligible-signal counts rather than raw setup fires.
    """
    masked: dict[str, pd.Series] = {}
    for symbol, df in data.items():
        signal = signals.get(symbol)
        if signal is None:
            masked[symbol] = pd.Series(False, index=df.index)
            continue
        if elig is not None and symbol in elig.columns:
            flags = elig[symbol].reindex(df.index, fill_value=False).fillna(False).astype(bool)
        else:
            flags = eligible(df)
        masked[symbol] = (
            signal.reindex(df.index, fill_value=False).fillna(False).astype(bool) & flags
        )
    return masked


def null_distributions(
    data: Mapping[str, pd.DataFrame],
    signals: Mapping[str, pd.Series],
    elig: pd.DataFrame,
    variants: Mapping[str, ExitVariant],
    n_null: int = 100,
    base_seed: int = DEFAULT_NULL_BASE_SEED,
    cost_bps: float = DEFAULT_COST_BPS,
    eval_start: str = EVAL_START,
    progress=None,
) -> dict[str, list[float]]:
    """Matched-random entry sets under every variant, returning mean r_net lists.

    Each draw uses :func:`backend.app.research.control.matched_random_signals`
    with the same daily eligible-signal counts, then the same entry, ATR and
    exit rules. Seeds are ``base_seed + i``. ``progress`` is an optional
    callable invoked with the number of completed draws; no I/O happens here.
    """
    names = list(variants)
    values: dict[str, list[float]] = {name: [] for name in names}
    cache: dict[str, dict] = {}
    for i in range(int(n_null)):
        random_signals = matched_random_signals(
            data, signals, seed=base_seed + i, elig=elig,
        )
        entries = entry_candidates(data, random_signals, elig, eval_start=eval_start)
        for name in names:
            trades = simulate_entries(
                data, entries, variants[name], cost_bps=cost_bps, cache=cache,
            )
            values[name].append(
                float(trades["r_net"].mean()) if not trades.empty else float("nan")
            )
        if progress is not None:
            progress(i + 1)
    return values
