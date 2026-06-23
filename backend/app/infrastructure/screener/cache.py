"""DuckDB indicator cache — pre-compute and store indicator values."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import duckdb
import pandas as pd

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.logging import get_logger
from backend.app.infrastructure.indicators import compute_all, list_indicators

log = get_logger("conflu.screener.cache")


class IndicatorCache:
    """Pre-compute and store indicator values in DuckDB.

    Uses the indicator_values table for tall-format storage.
    Supports incremental updates (compute only new bars) and
    full rebuilds (on parameter changes).
    """

    # Indicator-specific parameters for proper computation
    _INDICATOR_PARAMS: dict[str, dict[str, Any]] = {
        "rsi": {"length": 14},
        "macd": {"fast": 12, "slow": 26, "signal": 9},
        "ema": {"length": 20},  # Default, can be overridden
        "ema_20": {"length": 20},
        "ema_50": {"length": 50},
        "ema_200": {"length": 200},
        "sma": {"length": 50},
        "sma_20": {"length": 20},
        "sma_50": {"length": 50},
        "sma_200": {"length": 200},
        "atr": {"length": 14},
        "adx": {"length": 14},
        "obv": {},
        "bb": {"length": 20, "std": 2},
        "vwap": {},
        "stoch": {"k": 14, "d": 3, "smooth_k": 3},
    }

    def __init__(self) -> None:
        self._log = get_logger("conflu.screener.cache")
        self._cached_indicators: list[str] = list(settings.compute.cached_indicators)
        self._enabled: bool = settings.compute.indicator_cache_enabled

    async def update_cache(
        self,
        timeframes: list[str] | None = None,
        indicator_names: list[str] | None = None,
    ) -> int:
        """Refresh indicator cache incrementally after ingestion.

        For each (timeframe, indicator), computes indicator values for OHLCV
        bars that are newer than the latest cached value. Only processes
        the intersection of cached_indicators and registered indicators.

        Args:
            timeframes: Timeframes to update (default: all configured).
            indicator_names: Indicators to compute (default: all cached).

        Returns:
            Number of new indicator value rows written.
        """
        if not self._enabled:
            return 0

        import asyncio

        tfs = timeframes or list(settings.data.timeframes)
        names = indicator_names or self._cached_indicators
        total_new = 0

        for tf in tfs:
            # Load OHLCV data for this timeframe
            ohlcv_data = await self._load_ohlcv_for_timeframe(tf)
            if ohlcv_data is None or ohlcv_data.empty:
                continue

            # Compute and store each indicator
            for ind_name in names:
                # Check if indicator is registered or has a registered base (e.g., "ema_20" -> "ema")
                registered = ind_name in list_indicators()
                if not registered and "_" in ind_name:
                    base = ind_name.split("_")[0]
                    registered = base in list_indicators()
                
                if not registered:
                    self._log.warning("indicator_not_registered", indicator=ind_name)
                    continue

                try:
                    new_rows = await self._compute_and_store(
                        indicator_name=ind_name,
                        ohlcv=ohlcv_data,
                        timeframe=tf,
                    )
                    total_new += new_rows
                except Exception:
                    self._log.exception(
                        "indicator_cache_failed",
                        indicator=ind_name,
                        timeframe=tf,
                    )

        self._log.info("cache_update_complete", new_values=total_new)
        return total_new

    async def _load_ohlcv_for_timeframe(
        self,
        timeframe: str,
    ) -> pd.DataFrame | None:
        """Load latest OHLCV data for a timeframe from DuckDB.

        Gets the latest 500 bars per symbol (configurable in future).
        """
        import asyncio

        loop = asyncio.get_running_loop()

        def _query() -> pd.DataFrame:
            with get_db(read_only=True) as con:
                return con.sql(
                    """
                    SELECT symbol, timestamp, open, high, low, close, volume
                    FROM (
                        SELECT symbol, timestamp, open, high, low, close, volume,
                               ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY timestamp DESC) as rn
                        FROM ohlcv
                        WHERE timeframe = ?
                    )
                    WHERE rn <= 500
                    ORDER BY symbol, timestamp ASC
                    """,
                    params=[timeframe],
                ).fetchdf()

        return await loop.run_in_executor(None, _query)

    async def _compute_and_store(
        self,
        indicator_name: str,
        ohlcv: pd.DataFrame,
        timeframe: str,
    ) -> int:
        """Compute an indicator and store results incrementally.

        Steps:
        1. Check MAX(timestamp) per symbol in existing cache
        2. Filter OHLCV to rows newer than cached max
        3. Compute indicator on delta
        4. Insert new rows into indicator_values

        Returns number of rows written.
        """
        import asyncio

        loop = asyncio.get_running_loop()

        def _compute_and_insert() -> int:
            with get_db() as con:
                # 1. Get max cached timestamp per symbol
                cached_max = con.sql(
                    """
                    SELECT symbol, MAX(timestamp) as max_ts
                    FROM indicator_values
                    WHERE indicator_name = ? AND timeframe = ?
                    GROUP BY symbol
                    """,
                    params=[indicator_name, timeframe],
                ).fetchdf()

                # 2. Filter to new data only
                if not cached_max.empty:
                    merged = ohlcv.merge(
                        cached_max.rename(columns={"max_ts": "cached_until"}),
                        on="symbol",
                        how="left",
                    )
                    new_data = merged[
                        merged["cached_until"].isna()
                        | (merged["timestamp"] > merged["cached_until"])
                    ].drop(columns=["cached_until"])
                else:
                    new_data = ohlcv

                if new_data.empty:
                    return 0

                # Ensure data is sorted chronologically for indicator computation
                new_data = new_data.sort_values(["symbol", "timestamp"]).reset_index(drop=True)

                # 3. Compute indicator with proper parameters
                # Handle indicators with period suffixes (e.g., "ema_200" -> base="ema", period=200)
                # First check if indicator_name is directly registered
                if indicator_name in list_indicators():
                    base_indicator = indicator_name
                    params = self._INDICATOR_PARAMS.get(indicator_name, {})
                else:
                    # Try to extract base indicator (e.g., "ema_200" -> "ema")
                    base_indicator = indicator_name
                    params = self._INDICATOR_PARAMS.get(indicator_name, {})
                    if "_" in indicator_name:
                        base = indicator_name.split("_")[0]
                        if base in list_indicators():
                            base_indicator = base
                            params = self._INDICATOR_PARAMS.get(indicator_name, {})
                
                results = compute_all(new_data, indicators=[base_indicator], indicator_params={base_indicator: params})

                if base_indicator not in results:
                    return 0

                result_df = results[base_indicator].copy()
                
                # Rename indicator_name to match what filters expect (e.g., "ema_200")
                result_df["indicator_name"] = indicator_name

                # 4. Add timeframe and params columns
                params_json = json.dumps(params)

                result_df["timeframe"] = timeframe
                result_df["params"] = params_json

                # 5. Insert into indicator_values
                con.sql(
                    """
                    INSERT INTO indicator_values
                    SELECT symbol, timestamp, indicator_name, value,
                           timeframe, params, CURRENT_TIMESTAMP
                    FROM result_df
                    """,
                )

                return len(result_df)

        return await loop.run_in_executor(None, _compute_and_insert)

    async def get_latest(
        self,
        indicator_name: str,
        timeframe: str = "1D",
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        """Get latest indicator values for all (or specified) symbols.

        Returns DataFrame with columns: symbol, timestamp, value.
        One row per symbol (latest timestamp before or at current time).
        """
        import asyncio

        loop = asyncio.get_running_loop()

        def _query() -> pd.DataFrame:
            with get_db(read_only=True) as con:
                query = """
                    SELECT symbol, timestamp, value
                    FROM indicator_values
                    WHERE indicator_name = ?
                      AND timeframe = ?
                      AND timestamp <= CURRENT_TIMESTAMP
                """
                params: list[Any] = [indicator_name, timeframe]

                if symbols:
                    placeholders = ",".join("?" * len(symbols))
                    query += f" AND symbol IN ({placeholders})"
                    params.extend(symbols)

                # Get latest per symbol
                query = f"""
                    SELECT symbol, timestamp, value
                    FROM ({query}) sub
                    QUALIFY ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY timestamp DESC) = 1
                """
                return con.sql(query, params=params).fetchdf()

        return await loop.run_in_executor(None, _query)

    async def get_series(
        self,
        indicator_name: str,
        timeframe: str = "1D",
        symbol: str | None = None,
        limit: int = 500,
    ) -> pd.DataFrame:
        """Get time series for an indicator.

        Returns DataFrame with columns: symbol, timestamp, value.
        """
        import asyncio

        loop = asyncio.get_running_loop()

        def _query() -> pd.DataFrame:
            with get_db(read_only=True) as con:
                if symbol:
                    return con.sql(
                        """
                        SELECT symbol, timestamp, value
                        FROM indicator_values
                        WHERE indicator_name = ?
                          AND timeframe = ?
                          AND symbol = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                        """,
                        params=[indicator_name, timeframe, symbol, limit],
                    ).fetchdf()
                else:
                    return con.sql(
                        """
                        SELECT symbol, timestamp, value
                        FROM indicator_values
                        WHERE indicator_name = ?
                          AND timeframe = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                        """,
                        params=[indicator_name, timeframe, limit],
                    ).fetchdf()

        return await loop.run_in_executor(None, _query)

    async def get_as_of(
        self,
        indicator_name: str,
        timeframe: str = "1D",
        as_of_date: datetime | None = None,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        """Get indicator values as of a specific date.

        For each symbol, returns the most recent indicator value
        that is <= as_of_date. Used by ScreenReplay for historical evaluation.

        Args:
            indicator_name: The indicator to query.
            timeframe: Timeframe to query.
            as_of_date: Cutoff date (default: now).
            symbols: Optional symbol subset.

        Returns:
            DataFrame with columns: symbol, timestamp, value.
            One row per symbol (latest before or on as_of_date).
        """
        import asyncio

        loop = asyncio.get_running_loop()
        if as_of_date is None:
            as_of_date = datetime.now(timezone.utc)

        def _query() -> pd.DataFrame:
            with get_db(read_only=True) as con:
                query = """
                    SELECT symbol, timestamp, value
                    FROM indicator_values
                    WHERE indicator_name = ?
                      AND timeframe = ?
                      AND timestamp <= ?
                """
                params: list[Any] = [indicator_name, timeframe, as_of_date]

                if symbols:
                    placeholders = ",".join("?" * len(symbols))
                    query += f" AND symbol IN ({placeholders})"
                    params.extend(symbols)

                query = f"""
                    SELECT symbol, timestamp, value
                    FROM ({query}) sub
                    QUALIFY ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY timestamp DESC) = 1
                """
                return con.sql(query, params=params).fetchdf()

        return await loop.run_in_executor(None, _query)

    async def rebuild(
        self,
        indicator_name: str | None = None,
        timeframe: str | None = None,
    ) -> int:
        """Full recompute: delete existing cache and recompute from scratch.

        Args:
            indicator_name: Specific indicator to rebuild (None = all cached).
            timeframe: Specific timeframe to rebuild (None = all configured).

        Returns:
            Total number of rows written.
        """
        import asyncio

        loop = asyncio.get_running_loop()
        names = [indicator_name] if indicator_name else self._cached_indicators
        tfs = [timeframe] if timeframe else list(settings.data.timeframes)

        def _delete_and_recompute() -> int:
            with get_db() as con:
                for ind in names:
                    for tf in tfs:
                        con.sql(
                            "DELETE FROM indicator_values WHERE indicator_name = ? AND timeframe = ?",
                            params=[ind, tf],
                        )
            return 0  # Will be recomputed in update_cache call

        await loop.run_in_executor(None, _delete_and_recompute)
        # Recompute all
        return await self.update_cache(timeframes=tfs, indicator_names=names)

    async def cache_status(self) -> dict[str, Any]:
        """Return current cache status.

        Returns:
            Dict with enabled, cached_indicators, total_rows, last_update.
        """
        import asyncio

        loop = asyncio.get_running_loop()

        def _query() -> dict[str, Any]:
            with get_db(read_only=True) as con:
                total_rows = con.sql(
                    "SELECT COUNT(*) FROM indicator_values",
                ).fetchone()
                last_update = con.sql(
                    "SELECT MAX(computed_at) FROM indicator_values",
                ).fetchone()
            return {
                "enabled": self._enabled,
                "cached_indicators": list(self._cached_indicators),
                "total_rows": total_rows[0] if total_rows else 0,
                "last_update": last_update[0] if last_update and last_update[0] else None,
            }

        return await loop.run_in_executor(None, _query)
