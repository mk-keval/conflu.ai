"""Multi-timeframe broadcasting utilities for indicator alignment.

Uses pandas reindex with forward-fill (not vectorbt broadcast) for
timeframe alignment — simpler, correct semantics, well-understood.
"""

from __future__ import annotations

import pandas as pd

_TIME_FRAME_RANK: dict[str, int] = {
    "1m": 0,
    "5m": 1,
    "15m": 2,
    "30m": 3,
    "1h": 4,
    "2h": 5,
    "4h": 6,
    "12h": 7,
    "1D": 8,
    "1W": 9,
}


def timeframe_rank(tf: str) -> int:
    """Return numeric rank for a timeframe (higher = longer period).

    Args:
        tf: Timeframe string (e.g., '1D', '4h', '15m').

    Returns:
        Integer rank: 1m=0, 5m=1, ..., 1D=8, 1W=9.
    """
    return _TIME_FRAME_RANK.get(tf, 5)


def sort_timeframes(timeframes: list[str], descending: bool = True) -> list[str]:
    """Sort timeframes by duration.

    Args:
        timeframes: List of timeframe strings.
        descending: If True, sort highest-to-lowest (1D, 4h, 1h).

    Returns:
        Sorted timeframe list.
    """
    return sorted(timeframes, key=timeframe_rank, reverse=descending)


def broadcast_timeframe(
    higher_tf_df: pd.DataFrame,
    lower_tf_timestamps: pd.DatetimeIndex,
    value_column: str = "value",
) -> pd.DataFrame:
    """Broadcast higher-timeframe indicator to lower-timeframe timestamps.

    Uses forward-fill: the value from the higher timeframe applies
    to all lower-timeframe bars until the next higher-timeframe update.

    Args:
        higher_tf_df: DataFrame with 'timestamp' column and value_column.
            Must have a DatetimeIndex or 'timestamp' column.
        lower_tf_timestamps: DatetimeIndex of the target timeframe.
        value_column: Name of the value column to broadcast.

    Returns:
        DataFrame indexed by lower_tf_timestamps with broadcast values.

    Example:
        daily_rsi has daily timestamps.
        hourly_timestamps = pd.date_range(...) for 4h bars.
        broadcast_timeframe(daily_rsi, hourly_timestamps)
        -> forward-fills daily RSI values into each 4h bar.
    """
    # Ensure we have a proper DatetimeIndex
    if "timestamp" in higher_tf_df.columns:
        higher_tf_df = higher_tf_df.set_index("timestamp")

    if not isinstance(higher_tf_df.index, pd.DatetimeIndex):
        msg = "higher_tf_df must have a DatetimeIndex or 'timestamp' column"
        raise ValueError(msg)

    # Reindex to lower timeframe with forward-fill
    broadcast = (
        higher_tf_df[[value_column]]
        .reindex(lower_tf_timestamps, method="ffill")
        .reindex(lower_tf_timestamps)  # ensure exact alignment
    )

    broadcast.index.name = "timestamp"
    return broadcast


def align_timeframes(
    dataframes: dict[str, pd.DataFrame],
    target_timeframe: str,
) -> dict[str, pd.DataFrame]:
    """Align multiple timeframe indicator DataFrames to a target timeframe.

    Higher timeframes are forward-filled down, same timeframe is kept,
    lower timeframes are not upsampled (would create false data).

    Args:
        dataframes: Dict mapping timeframe -> DataFrame with timestamp index.
        target_timeframe: The timeframe to align to.

    Returns:
        Dict of {timeframe: aligned_df} — only timeframes >= target.
    """
    # This is a stub for now — full multi-TF alignment will be in ScreenEngine
    pass
