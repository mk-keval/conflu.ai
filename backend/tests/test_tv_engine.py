"""Tests for TV Screen Engine — orchestrator with rate limiter + cache.

Unit tests with mocked specialist to avoid live TV API calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.infrastructure.screener.tv_engine import TVScreenEngine
from backend.app.infrastructure.screener.tv_specialist import TVDiscoveryResult
from backend.app.infrastructure.screener.configs import ScreenConfig, FilterRule
from backend.app.infrastructure.screener.tv_rate_limiter import TVRateLimiter
from backend.app.infrastructure.screener.tv_cache import TVCache


@pytest.fixture
def mock_specialist() -> MagicMock:
    """Mock TVScreenerSpecialist returning a canned discovery result."""
    import pandas as pd

    mock = MagicMock()
    result = TVDiscoveryResult(
        screen_name="Test",
        total_matches=1,
        tickers=["AAPL"],
        execution_ms=100,
        raw_data=pd.DataFrame({
            "ticker": ["NASDAQ:AAPL"],
            "close": [180.0],
            "RSI": [45.0],
            "ADX": [28.0],
            "volume": [50_000_000],
        }),
        timeframe="1D",
    )
    mock.discover = AsyncMock(return_value=result)
    return mock


@pytest.fixture
def engine(mock_specialist: MagicMock) -> TVScreenEngine:
    """Create engine with mocked specialist."""
    eng = TVScreenEngine()
    eng.specialist = mock_specialist
    return eng


@pytest.fixture
def sample_config() -> ScreenConfig:
    return ScreenConfig(
        name="Test Screen",
        filters=[FilterRule(category="momentum", indicator="rsi_oversold")],
    )


class TestTVScreenEngine:
    """Test TVScreenEngine orchestrator."""

    @pytest.mark.asyncio
    async def test_discover_returns_result(self, engine: TVScreenEngine, sample_config: ScreenConfig) -> None:
        result = await engine.discover(sample_config)
        assert result.total_matches == 1
        assert result.tickers == ["AAPL"]
        assert result.raw_data is not None

    @pytest.mark.asyncio
    async def test_screen_returns_ranked_tickers(self, engine: TVScreenEngine, sample_config: ScreenConfig) -> None:
        result = await engine.screen(sample_config)
        assert result["total_matches"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_screen_with_limit(self, engine: TVScreenEngine, sample_config: ScreenConfig) -> None:
        result = await engine.screen(sample_config, limit=10)
        assert result["screen_name"] == "Test Screen"
        assert "execution_ms" in result

    def test_rate_limiter_stats(self, engine: TVScreenEngine) -> None:
        stats = engine.rate_limiter_stats()
        assert "tokens" in stats
        assert "total_blocked" in stats

    def test_cache_stats(self, engine: TVScreenEngine) -> None:
        stats = engine.cache_stats()
        assert "size" in stats
        assert "maxsize" in stats
        assert "hit_rate" in stats


class TestDiscoverCacheBehavior:
    """Regression tests for sticky-empty-cache fix (swing-parity P0.1).

    Empty discoveries are valid "no matches" answers but must never be
    cached: a cached empty result gets served back in ~16ms for the whole
    TTL, masking transient upstream failures as persistent dead screens.
    """

    @pytest.fixture
    def empty_result(self) -> TVDiscoveryResult:
        import pandas as pd

        return TVDiscoveryResult(
            screen_name="Test",
            total_matches=0,
            tickers=[],
            execution_ms=16,
            raw_data=pd.DataFrame(),
            timeframe="1D",
        )

    @pytest.mark.asyncio
    async def test_empty_result_returned_but_not_cached(
        self, sample_config: ScreenConfig, empty_result: TVDiscoveryResult
    ) -> None:
        eng = TVScreenEngine()
        mock = MagicMock()
        mock.discover = AsyncMock(return_value=empty_result)
        eng.specialist = mock

        first = await eng.discover(sample_config)

        assert first.total_matches == 0
        key = eng.cache.make_key(sample_config, 500)
        assert eng.cache.get(key) is None, "empty discovery must not be written to cache"

        # Second call must re-query upstream instead of serving the empty cache
        second = await eng.discover(sample_config)
        assert mock.discover.call_count == 2
        assert second.total_matches == 0

    @pytest.mark.asyncio
    async def test_none_raw_data_not_cached(self, sample_config: ScreenConfig) -> None:
        import pandas as pd

        eng = TVScreenEngine()
        none_result = TVDiscoveryResult(
            screen_name="Test",
            total_matches=0,
            tickers=[],
            execution_ms=10,
            raw_data=pd.DataFrame(),
            timeframe="1D",
        )
        # Force raw_data to None to simulate upstream failure path
        none_result.raw_data = None  # type: ignore[assignment]
        mock = MagicMock()
        mock.discover = AsyncMock(return_value=none_result)
        eng.specialist = mock

        result = await eng.discover(sample_config)
        key = eng.cache.make_key(sample_config, 500)
        assert result.raw_data is None
        assert eng.cache.get(key) is None
        assert mock.discover.call_count == 1

    @pytest.mark.asyncio
    async def test_nonempty_result_still_cached(self, sample_config: ScreenConfig) -> None:
        import pandas as pd

        eng = TVScreenEngine()
        populated = TVDiscoveryResult(
            screen_name="Test",
            total_matches=1,
            tickers=["AAPL"],
            execution_ms=100,
            raw_data=pd.DataFrame({
                "ticker": ["NASDAQ:AAPL"],
                "close": [180.0],
                "RSI": [45.0],
                "ADX": [28.0],
                "volume": [50_000_000],
            }),
            timeframe="1D",
        )
        mock = MagicMock()
        mock.discover = AsyncMock(return_value=populated)
        eng.specialist = mock

        await eng.discover(sample_config)

        key = eng.cache.make_key(sample_config, 500)
        assert eng.cache.get(key) is not None
        assert mock.discover.call_count == 1

        # Second call served from cache — specialist not invoked again
        cached_result = await eng.discover(sample_config)
        assert mock.discover.call_count == 1
        assert cached_result.total_matches == 1


class TestTVRateLimiter:
    """Test TVRateLimiter token bucket behavior."""

    @pytest.mark.asyncio
    async def test_acquire_returns_zero_when_tokens_available(self) -> None:
        limiter = TVRateLimiter(max_rate=25, interval=60.0, burst=5)
        wait = await limiter.acquire()
        assert wait == 0.0
        assert limiter.tokens < 5

    @pytest.mark.asyncio
    async def test_context_manager_acquires_token(self) -> None:
        limiter = TVRateLimiter(max_rate=25, interval=60.0, burst=5)
        async with limiter:
            pass
        assert limiter.tokens < 5

    @pytest.mark.asyncio
    async def test_token_refill(self) -> None:
        """After exhausting tokens, some wait time should be reported on next acquire."""
        limiter = TVRateLimiter(max_rate=1000, interval=1.0, burst=3)
        # Exhaust burst tokens
        for _ in range(3):
            await limiter.acquire()
        # Next acquire should report a wait
        wait = await limiter.acquire()
        assert wait > 0


class TestTVCache:
    """Test TVCache TTL + LRU behavior."""

    def test_set_and_get(self) -> None:
        cache = TVCache(ttl=60.0, maxsize=50)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_miss_returns_none(self) -> None:
        cache = TVCache()
        assert cache.get("nonexistent") is None

    def test_hit_rate(self) -> None:
        cache = TVCache()
        cache.set("k", "v")
        cache.get("k")  # hit
        cache.get("x")  # miss
        assert cache.hits == 1
        assert cache.misses == 1

    def test_make_key_is_deterministic(self) -> None:
        cache = TVCache()
        config = ScreenConfig(name="Test")
        key1 = cache.make_key(config)
        key2 = cache.make_key(config)
        assert key1 == key2
        assert len(key1) == 16

    def test_lru_eviction(self) -> None:
        cache = TVCache(ttl=60.0, maxsize=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)
        assert cache.get("a") is None  # evicted
        assert cache.get("b") is not None
        assert cache.get("c") is not None
        assert cache.get("d") is not None

    def test_clear_resets_stats(self) -> None:
        cache = TVCache()
        cache.set("k", "v")
        cache.get("k")
        cache.clear()
        assert cache.size == 0
        assert cache.hits == 0
        assert cache.misses == 0

    def test_stats_structure(self) -> None:
        cache = TVCache(ttl=30.0, maxsize=100)
        stats = cache.stats()
        assert stats["ttl"] == 30.0
        assert stats["maxsize"] == 100
        assert stats["hit_rate"] == 0.0
