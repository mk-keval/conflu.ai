"""Screen replay engine — evaluate screen configurations over historical data.

Replays a saved screen configuration at each historical timestamp
(daily granularity) and computes signal quality metrics.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.logging import get_logger
from backend.app.infrastructure.screener.cache import IndicatorCache
from backend.app.infrastructure.screener.configs import ScreenConfig
from backend.app.infrastructure.screener.engine import ScreenEngine
from backend.app.infrastructure.screener.filters import _FILTER_REGISTRY

log = get_logger("conflu.screener.replay")


@dataclass
class DailyReplaySnapshot:
    """Results from a single day's evaluation during replay."""
    date: str
    match_count: int
    total_symbols: int
    matched_symbols: list[str] = field(default_factory=list)


@dataclass
class SignalQualityMetrics:
    """Signal quality metrics computed from replay."""
    win_rate: float = 0.0
    avg_return: float = 0.0
    total_return: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    total_signals: int = 0


class ScreenReplay:
    """Replay a screen configuration over historical data.

    Evaluates the filter pipeline at each historical timestamp
    (daily granularity) and records match counts and signal quality.

    Uses IndicatorCache.get_as_of() for point-in-time indicator values
    at each historical date.
    """

    def __init__(self) -> None:
        self._engine = ScreenEngine()
        self._cache = IndicatorCache()
        self._log = get_logger("conflu.screener.replay")

    async def replay(
        self,
        screen_config: ScreenConfig,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        symbols: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run screen replay over historical date range.

        Args:
            screen_config: The screen configuration to replay.
            start_date: Start of replay period (default: 2 years ago).
            end_date: End of replay period (default: yesterday).
            symbols: Optional symbol subset (default: all from config).

        Returns:
            Dict with replay results including daily snapshots and metrics.
        """
        if end_date is None:
            end_date = datetime.now(UTC) - timedelta(days=1)
        if start_date is None:
            start_date = end_date - timedelta(
                days=settings.replay.default_years * 365,
            )

        self._log.info(
            "replay_started",
            screen=screen_config.name,
            start=start_date.date(),
            end=end_date.date(),
        )

        # Generate list of daily timestamps (skip weekends)
        daily_dates = self._generate_trading_days(start_date, end_date)
        self._log.info("replay_days", count=len(daily_dates))

        snapshots: list[DailyReplaySnapshot] = []
        total_symbols = 0

        for eval_date in daily_dates:
            snapshot = await self._evaluate_as_of(screen_config, eval_date, symbols)
            if snapshot.total_symbols > 0:
                total_symbols = snapshot.total_symbols
            snapshots.append(snapshot)

        # Compute metrics
        match_counts = [s.match_count for s in snapshots]
        metrics = self._compute_signal_quality(snapshots)

        # Build equity curve from match counts (simplified: treat each match as equal-weight signal)
        equity_curve = self._build_equity_curve(snapshots)

        result = {
            "screen_name": screen_config.name,
            "start_date": start_date.date().isoformat(),
            "end_date": end_date.date().isoformat(),
            "total_days": len(daily_dates),
            "avg_match_count": float(np.mean(match_counts)) if match_counts else 0.0,
            "max_match_count": int(np.max(match_counts)) if match_counts else 0,
            "min_match_count": int(np.min(match_counts)) if match_counts else 0,
            "total_signals": metrics.total_signals,
            "win_rate": metrics.win_rate,
            "avg_return": metrics.avg_return,
            "total_return": metrics.total_return,
            "sharpe": metrics.sharpe,
            "max_drawdown": metrics.max_drawdown,
            "match_series": [
                {"date": s.date, "match_count": s.match_count}
                for s in snapshots
            ],
            "equity_curve": equity_curve,
        }

        self._log.info("replay_completed", result_summary={
            "days": len(daily_dates),
            "avg_matches": result["avg_match_count"],
            "win_rate": result["win_rate"],
        })

        return result

    def _generate_trading_days(
        self,
        start: datetime,
        end: datetime,
    ) -> list[datetime]:
        """Generate list of daily timestamps (weekdays only)."""
        days: list[datetime] = []
        current = start
        while current <= end:
            # Skip weekends (Monday=0, Sunday=6)
            if current.weekday() < 5:
                days.append(current.replace(hour=0, minute=0, second=0, microsecond=0))
            current += timedelta(days=1)
        return days

    async def _evaluate_as_of(
        self,
        screen_config: ScreenConfig,
        as_of_date: datetime,
        symbols: list[str] | None = None,
    ) -> DailyReplaySnapshot:
        """Evaluate screen config with indicator data as of a specific date.

        Loads indicator values as of as_of_date, applies filters,
        and returns which symbols matched.
        """
        # Load indicator data as of this date
        all_indicators = self._get_registered_indicators()
        tfs = screen_config.timeframes or ["1D"]

        candidates: pd.Series | None = None
        matched_symbols: set[str] = set()

        for tf in tfs:
            tf_filters = [
                f for f in screen_config.filters
                if getattr(f, "timeframe", "1D") == tf
            ]
            if not tf_filters:
                continue

            # Get all indicator values as of this date
            data_frames: list[pd.DataFrame] = []
            for ind_name in all_indicators:
                try:
                    df = await self._cache.get_as_of(
                        indicator_name=ind_name,
                        timeframe=tf,
                        as_of_date=as_of_date,
                        symbols=symbols,
                    )
                    if df is not None and not df.empty:
                        df = df.rename(columns={"value": ind_name})
                        data_frames.append(df[["symbol", ind_name]])
                except Exception:
                    pass

            if not data_frames:
                continue

            # Merge
            indicator_data = data_frames[0]
            for df in data_frames[1:]:
                indicator_data = indicator_data.merge(df, on="symbol", how="outer")

            if indicator_data.empty:
                continue

            # Apply filters
            for flt in tf_filters:
                filter_def = _FILTER_REGISTRY.get(flt.indicator)
                if filter_def is None:
                    continue

                try:
                    mask = filter_def.func(indicator_data, **flt.params)
                    if flt.negate:
                        mask = ~mask
                    mask = mask.fillna(False)

                    if candidates is None:
                        candidates = mask
                    else:
                        candidates = candidates & mask
                except Exception:
                    pass

            if candidates is not None and candidates.any():
                matched = set(candidates[candidates].index.tolist())
                matched_symbols.update(matched)

        return DailyReplaySnapshot(
            date=as_of_date.date().isoformat(),
            match_count=len(matched_symbols),
            total_symbols=len(candidates) if candidates is not None else 0,
            matched_symbols=list(matched_symbols),
        )

    def _get_registered_indicators(self) -> list[str]:
        """Get list of all registered filter indicator names."""
        return list(_FILTER_REGISTRY.keys())

    def _compute_signal_quality(
        self,
        snapshots: list[DailyReplaySnapshot],
    ) -> SignalQualityMetrics:
        """Compute signal quality metrics from daily snapshots.

        Uses match count changes as a proxy for signal quality.
        A "good" signal is one where match counts are stable (low variance)
        and have positive autocorrelation (signals persist).
        """
        if len(snapshots) < 2:
            return SignalQualityMetrics()

        match_counts = np.array([s.match_count for s in snapshots], dtype=float)

        # Daily changes in match count (proxy for signal churn)
        daily_changes = np.diff(match_counts)

        # "Wins" = positive match count growth (more signals triggering)
        # "Losses" = negative match count growth
        wins = daily_changes[daily_changes > 0].sum()
        losses = abs(daily_changes[daily_changes < 0].sum())
        total_signals = int(wins + losses)

        if total_signals == 0:
            return SignalQualityMetrics()

        win_rate = wins / total_signals if total_signals > 0 else 0.0
        avg_return = float(np.mean(daily_changes)) if len(daily_changes) > 0 else 0.0

        # Simple Sharpe-like metric (mean / std of daily changes)
        std = float(np.std(daily_changes)) if len(daily_changes) > 0 else 1.0
        sharpe = avg_return / std if std > 0 else 0.0

        # Max drawdown of match count
        peak = np.maximum.accumulate(match_counts)
        drawdown = (match_counts - peak) / (peak + 1e-10)
        max_dd = float(np.min(drawdown))

        metrics = SignalQualityMetrics(
            win_rate=win_rate,
            avg_return=avg_return,
            total_return=float(np.sum(daily_changes)),
            sharpe=sharpe,
            max_drawdown=max_dd,
            total_signals=total_signals,
        )

        return metrics

    def _build_equity_curve(
        self,
        snapshots: list[DailyReplaySnapshot],
    ) -> list[dict[str, Any]]:
        """Build a simplified equity curve from match counts.

        Treats each matched symbol as an equal-weight position.
        """
        if not snapshots:
            return []

        equity = 100_000.0  # Starting equity
        curve: list[dict[str, Any]] = []

        for i, snapshot in enumerate(snapshots):
            if i == 0:
                curve.append({"date": snapshot.date, "equity": equity})
                continue

            prev_count = snapshots[i - 1].match_count
            curr_count = snapshot.match_count
            delta = curr_count - prev_count

            # Simplified: each net new match generates 0.1% return
            daily_return = delta * 0.001
            equity *= 1.0 + daily_return

            curve.append({"date": snapshot.date, "equity": round(equity, 2)})

        return curve

    async def cache_results(
        self,
        screen_config_id: str,
        version: int,
        result: dict[str, Any],
    ) -> str:
        """Cache replay results in DuckDB for future retrieval.

        Args:
            screen_config_id: UUID of the screen config.
            version: Version number.
            result: Replay result dict from replay().

        Returns:
            UUID of the cached result row.
        """
        import asyncio

        loop = asyncio.get_running_loop()
        result_id = str(uuid.uuid4())

        def _write() -> None:
            with get_db() as con:
                con.sql(
                    """
                    INSERT INTO screen_replay_results (
                        id, screen_config_id, version,
                        start_date, end_date, total_days,
                        avg_match_count, max_match_count, min_match_count,
                        total_signals, win_rate, avg_return, total_return,
                        sharpe, max_drawdown, equity_curve_json, match_series_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    params=[
                        result_id,
                        screen_config_id,
                        version,
                        result["start_date"],
                        result["end_date"],
                        result["total_days"],
                        result["avg_match_count"],
                        result["max_match_count"],
                        result["min_match_count"],
                        result["total_signals"],
                        result["win_rate"],
                        result["avg_return"],
                        result["total_return"],
                        result["sharpe"],
                        result["max_drawdown"],
                        json.dumps(result["equity_curve"]),
                        json.dumps(result["match_series"]),
                    ],
                )

        await loop.run_in_executor(None, _write)
        return result_id

    async def get_cached_results(
        self,
        screen_config_id: str,
        version: int,
    ) -> dict[str, Any] | None:
        """Get cached replay results if they exist.

        Args:
            screen_config_id: UUID of the screen config.
            version: Version number.

        Returns:
            Replay result dict or None if not cached.
        """
        import asyncio

        loop = asyncio.get_running_loop()

        def _query() -> dict[str, Any] | None:
            with get_db(read_only=True) as con:
                df = con.sql(
                    """
                    SELECT * FROM screen_replay_results
                    WHERE screen_config_id = ? AND version = ?
                    ORDER BY computed_at DESC LIMIT 1
                    """,
                    params=[screen_config_id, version],
                ).fetchdf()

            if df.empty:
                return None

            row = df.iloc[0].to_dict()
            # Parse JSON fields
            for field in ["equity_curve_json", "match_series_json"]:
                if isinstance(row.get(field), str):
                    try:
                        row[field.replace("_json", "")] = json.loads(row[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            return row

        return await loop.run_in_executor(None, _query)
