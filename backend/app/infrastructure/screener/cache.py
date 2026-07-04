"""Indicator cache — reads pre-computed indicator values from DuckDB.

The indicator_values table is populated by the data ingestion pipeline.
This module provides a thin async wrapper for querying it.
"""

from __future__ import annotations

import asyncio
from typing import Any

import duckdb
import pandas as pd

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

log = get_logger("conflu.screener.cache")


class IndicatorCache:
    """Read-only cache wrapper for pre-computed indicator values.

    Queries the ``indicator_values`` table which stores one row per
    (symbol, timeframe, indicator_name, timestamp).

    All public methods are async-safe (queries run via ``asyncio.to_thread``).
    """

    def __init__(self) -> None:
        self._db_path = settings.core.duckdb_path
        self._lock = asyncio.Lock()

    # ── public API ──────────────────────────────────────────────────────────

    async def get_series(
        self,
        *,
        indicator_name: str,
        timeframe: str,
        symbol: str,
        limit: int = 200,
    ) -> pd.DataFrame | None:
        """Return a DataFrame with ``timestamp`` and ``value`` columns.

        Returns ``None`` when no data exists for the given parameters.
        Rows are ordered descending by timestamp (newest first).
        """
        rows = await self._query(
            """
            SELECT timestamp, value
            FROM indicator_values
            WHERE symbol = ?
              AND indicator_name = ?
              AND timeframe = ?
              AND value IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            params=[symbol, indicator_name, timeframe, limit],
        )
        if rows is None or rows.empty:
            return None
        # DuckDB may return pd.NaT for NULL values when column type is ambiguous;
        # drop any remaining null-like entries to prevent float(NaT) crashes downstream.
        rows = rows.dropna(subset=["value"])
        if rows.empty:
            return None
        return rows

    async def get_latest_value(
        self,
        *,
        indicator_name: str,
        timeframe: str,
        symbol: str,
    ) -> dict[str, Any] | None:
        """Return the most recent ``{timestamp, value}`` dict or ``None``."""
        series = await self.get_series(
            indicator_name=indicator_name,
            timeframe=timeframe,
            symbol=symbol,
            limit=1,
        )
        if series is None or series.empty:
            return None
        row = series.iloc[0]
        return {
            "timestamp": row["timestamp"].isoformat()
            if hasattr(row["timestamp"], "isoformat")
            else str(row["timestamp"]),
            "value": float(row["value"]),
        }

    async def get_bulk(
        self,
        *,
        symbols: list[str],
        indicator_name: str,
        timeframe: str,
        limit: int = 1,
    ) -> dict[str, pd.DataFrame | None]:
        """Return a dict mapping each symbol to its indicator series."""
        result: dict[str, pd.DataFrame | None] = {}
        for sym in symbols:
            result[sym] = await self.get_series(
                indicator_name=indicator_name,
                timeframe=timeframe,
                symbol=sym,
                limit=limit,
            )
        return result

    async def list_available(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> list[str]:
        """List indicator names that have data for the given symbol+timeframe."""
        rows = await self._query(
            """
            SELECT DISTINCT indicator_name
            FROM indicator_values
            WHERE symbol = ? AND timeframe = ?
            ORDER BY indicator_name
            """,
            params=[symbol, timeframe],
        )
        if rows is None or rows.empty:
            return []
        return rows["indicator_name"].tolist()

    # ── internals ───────────────────────────────────────────────────────────

    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(self._db_path, read_only=True)

    async def _query(
        self,
        sql: str,
        params: list[Any] | None = None,
    ) -> pd.DataFrame | None:
        """Run a read-only query via ``asyncio.to_thread``."""
        try:
            return await asyncio.to_thread(self._query_sync, sql, params)
        except Exception:
            log.exception("indicator_cache_query_failed: %s", sql[:80])
            return None

    def _query_sync(
        self,
        sql: str,
        params: list[Any] | None = None,
    ) -> pd.DataFrame | None:
        con = self._connect()
        try:
            result = con.execute(sql, params or [])
            return result.fetchdf()
        finally:
            con.close()
