"""Self-closing exit inference (plan Sec.2E).

Turns raw OHLCV bars into a conservative, unambiguous exit for a long
entry. Pure function — no I/O. The paper-trade script (1D) calls it with the
entry's plan tuple + symbol OHLCV (from ``technical._fetch_daily_ohlcv``) to
backfill ``date_closed``/``exit_price``/``exit_reason`` on rows that never got
one, and to measure ``mfe_r``/``mae_r`` for every row.

Fill rules (conservative — when a bar touches both a stop and a target, the
stop wins, i.e. the WORSE outcome is recorded, and the fill is flagged):

1. Gap through stop       — ``open <= stop``      → fill at ``open`` (worse).
2. Stop touched           — ``low  <= stop``      → fill at ``stop``.
3. Target 2 reached       — ``high >= target_2``  → fill at ``target_2``.
4. Target 1 reached       — ``high >= target_1``  → fill at ``target_1``.
5. Time stop              — held >= max_hold_days → fill at that bar's close.

Metrics (plan Sec.2E): ``mfe_r``/``mae_r`` are the max favorable / max adverse
excursion in R units over the held bars, ending at the fill bar. For EOD
entries pass ``exclude_entry_bar_excursions=True``: bar 0 is the entry day,
and its high/low happened *before* the close fill — counting them would
inflate the excursions with pre-entry price action (bug R4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

EXIT_STOP = "stop"
EXIT_TARGET_1 = "target_1"
EXIT_TARGET_2 = "target_2"
EXIT_TIME = "time_stop"


@dataclass
class ExitFill:
    """One inferred exit from a bar series."""

    exit_price: float | None
    exit_date: str | None
    exit_reason: str | None
    bars_held: int
    ambiguous: bool          # a single bar touched stop AND a target → stop wins, flagged
    mfe_r: float | None      # max favorable excursion in R over the hold
    mae_r: float | None      # max adverse excursion in R over the hold

    def as_row(self) -> dict[str, Any]:
        return {
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason,
            "date_closed": self.exit_date,
            "mfe_r": None if self.mfe_r is None else round(self.mfe_r, 2),
            "mae_r": None if self.mae_r is None else round(self.mae_r, 2),
        }


def _bar_values(bar: dict[str, Any]) -> tuple[float, float, float, float] | None:
    try:
        return (
            float(bar["open"]), float(bar["high"]),
            float(bar["low"]), float(bar["close"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def infer_exit(
    bars: list[dict[str, Any]],
    *,
    entry: float,
    stop: float,
    targets: list[float] | None = None,
    max_hold_days: int | None = None,
    exclude_entry_bar_excursions: bool = False,
) -> ExitFill:
    """Walk bars AFTER the entry bar and return the first exit that fires.

    ``bars`` is a list of daily-bar dicts ``{date, open, high, low, close}``
    ascending by date, beginning on (or after) the entry date. Returns a row
    with ``exit_date=None`` when no rule fires within the data.
    """
    if not bars or entry <= 0 or stop <= 0 or stop >= entry:
        return ExitFill(None, None, None, 0, False, None, None)

    targets = list(targets or [])
    t1 = targets[0] if len(targets) >= 1 else None
    t2 = targets[1] if len(targets) >= 2 else (targets[0] if targets else None)
    if len(targets) == 1:
        t2 = None  # single target — never mislabel t1 as t2

    risk = entry - stop
    assert risk > 0

    prev_valid = _bar_values(bars[0]) is not None
    max_high: float | None = None
    min_low: float | None = None

    for idx, bar in enumerate(bars):
        vals = _bar_values(bar)
        if vals is None:
            continue
        _open, high, low, _close = vals

        # Bars before the entry bar cannot trigger an exit (entry happens at/before bar 0).
        if idx == 0 and prev_valid:
            # EOD entry: bar 0's excursion happened before the close fill.
            if not exclude_entry_bar_excursions:
                max_high = high if max_high is None else max(max_high, high)
                min_low = low if min_low is None else min(min_low, low)
            continue

        # Track excursion over the hold (from the first valid post-entry bar).
        max_high = high if max_high is None else max(max_high, high)
        min_low = low if min_low is None else min(min_low, low)

        date = str(bar.get("date") or "")
        bars_held = idx + 1  # entry bar counts as the first hold day

        hit_stop = _open <= stop or low <= stop
        hit_t2 = t2 is not None and high >= t2
        hit_t1 = t1 is not None and high >= t1 and not hit_t2
        time_stop = max_hold_days is not None and bars_held >= max_hold_days

        # Stop is checked FIRST (conservative). A bar that also touched a
        # target is flagged ambiguous — shadows a same-bar limit-out.
        if hit_stop:
            ambiguous = hit_t2 or hit_t1
            fill_price = _open if _open <= stop else stop
            return ExitFill(fill_price, date, EXIT_STOP, bars_held, ambiguous,
                            (max_high - entry) / risk, (min_low - entry) / risk)
        if hit_t2:
            return ExitFill(t2, date, EXIT_TARGET_2, bars_held, False,
                            (max_high - entry) / risk, (min_low - entry) / risk)
        if hit_t1:
            return ExitFill(t1, date, EXIT_TARGET_1, bars_held, False,
                            (max_high - entry) / risk, (min_low - entry) / risk)
        if time_stop:
            return ExitFill(_close, date, EXIT_TIME, bars_held, False,
                            (max_high - entry) / risk, (min_low - entry) / risk)

    return ExitFill(None, None, None, len(bars), False,
                    (max_high - entry) / risk if max_high else None,
                    (min_low - entry) / risk if min_low else None)


def as_bars(ohlcv_rows: list[Any]) -> list[dict[str, Any]]:
    """Normalize raw OHLCV rows (dicts or tuples) into ``infer_exit`` bars.

    Accepts tuples ``(date, open, high, low, close)`` or dicts with any of
    ``date``/``timestamp``/``datetime`` keys, ascending already.
    """
    out: list[dict[str, Any]] = []
    for row in ohlcv_rows:
        if isinstance(row, dict):
            date = (
                row.get("date") or row.get("timestamp")
                or row.get("datetime") or ""
            )
            out.append({
                "date": str(date),
                "open": row["open"], "high": row["high"],
                "low": row["low"], "close": row["close"],
            })
        elif isinstance(row, (tuple, list)) and len(row) >= 5:
            d, o, h, lo, c, *_ = row
            out.append({"date": str(d), "open": o, "high": h, "low": lo, "close": c})
    return out


__all__ = ["EXIT_STOP", "EXIT_TARGET_1", "EXIT_TARGET_2", "EXIT_TIME",
           "ExitFill", "infer_exit", "as_bars"]