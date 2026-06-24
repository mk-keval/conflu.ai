"""Tests for IndicatorCache with in-memory DuckDB."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator

import pandas as pd
import pytest

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.infrastructure.screener.cache import IndicatorCache


class TestIndicatorCacheInit:
    """Test IndicatorCache initialization."""

    def test_cache_initializes(self) -> None:
        cache = IndicatorCache()
        assert cache is not None
        assert hasattr(cache, "update_cache")
        assert hasattr(cache, "get_latest")
        assert hasattr(cache, "get_series")
        assert hasattr(cache, "rebuild")
        assert hasattr(cache, "cache_status")

    def test_cache_config_values(self) -> None:
        cache = IndicatorCache()
        assert len(cache._cached_indicators) > 0
        assert "rsi" in cache._cached_indicators


class TestIndicatorCacheWithDB:
    """Test IndicatorCache with DuckDB."""

    @pytest.fixture(autouse=True)
    def setup_db(self, monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
        """Create a temporary DuckDB database file for the cache tests."""
        # Use a temp file so we don't pollute the real database
        tmp_dir = tempfile.mkdtemp()
        tmp_db = os.path.join(tmp_dir, "test_conflu.duckdb")
        monkeypatch.setattr(settings.core, "duckdb_path", tmp_db)
        # Initialize the database (creates the file and indicator_values table)
        with get_db(read_only=False) as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS indicator_values (
                    symbol VARCHAR,
                    timestamp TIMESTAMPTZ,
                    indicator_name VARCHAR,
                    value DOUBLE,
                    timeframe VARCHAR,
                    params VARCHAR,
                    computed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)
        yield
        # Clean up temp file
        try:
            os.unlink(tmp_db)
            os.rmdir(tmp_dir)
        except OSError:
            pass

    def test_cache_status_returns_dict(self) -> None:
        cache = IndicatorCache()

        async def _check() -> None:
            status = await cache.cache_status()
            assert isinstance(status, dict)
            assert "enabled" in status
            assert "cached_indicators" in status
            assert "total_rows" in status
            assert "last_update" in status

        import asyncio
        asyncio.run(_check())

    def test_get_latest_with_empty_cache(self) -> None:
        """Getting latest from empty cache returns empty DataFrame."""
        cache = IndicatorCache()

        async def _check() -> None:
            df = await cache.get_latest("rsi", timeframe="1D")
            assert isinstance(df, pd.DataFrame)

        import asyncio
        asyncio.run(_check())

    def test_get_series_with_empty_cache(self) -> None:
        """Getting series from empty cache returns empty DataFrame."""
        cache = IndicatorCache()

        async def _check() -> None:
            df = await cache.get_series("rsi", timeframe="1D")
            assert isinstance(df, pd.DataFrame)

        import asyncio
        asyncio.run(_check())

    def test_update_cache_disabled(self) -> None:
        """When cache is disabled, update returns 0."""
        cache = IndicatorCache()
        cache._enabled = False

        async def _check() -> None:
            count = await cache.update_cache(timeframes=["1D"])
            assert count == 0

        import asyncio
        asyncio.run(_check())
