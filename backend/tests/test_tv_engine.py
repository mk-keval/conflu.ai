"""Tests for TV Screen Engine — orchestrator with rate limiter + cache.

Unit tests with mocked specialist to avoid live TV API calls.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from backend.app.infrastructure.screener.tv_engine import TVScreenEngine
from backend.app.infrastructure.screener.tv_specialist import TVDiscoveryResult
from backend.app.infrastructure.screener.configs import ScreenConfig, FilterRule
from backend.app.infrastructure.screener.tv_rate_limiter import TVRateLimiter
from backend.app.infrastructure.screener.tv_cache import TVCache
from backend.app.infrastructure.screener.tv_circuit_breaker import TVCircuitBreaker


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


def _make_result(
    tickers: list[str],
    *,
    empty: bool = False,
) -> TVDiscoveryResult:
    """Build a TVDiscoveryResult with the given tickers (or an empty one)."""
    if empty:
        return TVDiscoveryResult(
            screen_name="Test",
            total_matches=0,
            tickers=[],
            execution_ms=10,
            raw_data=pd.DataFrame(),
            timeframe="1D",
        )
    return TVDiscoveryResult(
        screen_name="Test",
        total_matches=len(tickers),
        tickers=tickers,
        execution_ms=100,
        raw_data=pd.DataFrame({
            "ticker": [f"NASDAQ:{t}" for t in tickers],
            "close": [180.0] * len(tickers),
        }),
        timeframe="1D",
    )


def _age_entry(cache: TVCache, key: str, seconds: float) -> None:
    """Rewind a cache entry's expiry to simulate the passage of time."""
    expires_at, value = cache._cache[key]
    cache._cache[key] = (expires_at - seconds, value)


class TestTVCacheStaleWhileRevalidate:
    """Stale-while-revalidate semantics on TVCache (swing-parity P1.0)."""

    def test_fresh_hit_returns_not_stale(self) -> None:
        cache = TVCache(ttl=60.0, stale_ttl=300.0)
        cache.set("k", _make_result(["AAPL"]))
        value, is_stale = cache.get_with_freshness("k")
        assert value is not None
        assert is_stale is False
        assert cache.hits == 1
        assert cache._stale_hits == 0

    def test_stale_within_stale_ttl_served_with_label(self) -> None:
        cache = TVCache(ttl=60.0, stale_ttl=300.0)
        cache.set("k", _make_result(["AAPL"]))
        _age_entry(cache, "k", seconds=100)  # past ttl, inside stale window

        value, is_stale = cache.get_with_freshness("k")
        assert value is not None
        assert is_stale is True
        assert cache._stale_hits == 1

    def test_legacy_get_never_serves_stale_entries(self) -> None:
        """The pre-SWR getter keeps strict freshness semantics."""
        cache = TVCache(ttl=60.0, stale_ttl=300.0)
        cache.set("k", _make_result(["AAPL"]))
        _age_entry(cache, "k", seconds=100)

        assert cache.get("k") is None  # expired → miss (and evicted)
        assert cache.size == 0

    def test_hard_expired_beyond_stale_ttl_dropped(self) -> None:
        cache = TVCache(ttl=60.0, stale_ttl=300.0)
        cache.set("k", _make_result(["AAPL"]))
        _age_entry(cache, "k", seconds=301)

        value, is_stale = cache.get_with_freshness("k")
        assert value is None
        assert is_stale is False
        assert cache.size == 0  # entry evicted

    def test_empty_result_never_served_stale(self) -> None:
        """Defensive guard: silently-empty cached states are unserveable."""
        cache = TVCache(ttl=60.0, stale_ttl=300.0)
        cache.set("k", _make_result([], empty=True))
        _age_entry(cache, "k", seconds=100)

        value, is_stale = cache.get_with_freshness("k")
        assert value is None
        assert is_stale is False

    def test_stats_include_stale_fields(self) -> None:
        cache = TVCache(ttl=60.0, stale_ttl=120.0)
        stats = cache.stats()
        assert stats["stale_ttl"] == 120.0
        assert stats["stale_hits"] == 0


class TestTVCircuitBreaker:
    """Sliding-window circuit breaker guarding upstream call volume."""

    def test_below_threshold_not_open(self) -> None:
        breaker = TVCircuitBreaker(max_calls=20, window_seconds=60.0)
        for i in range(20):
            breaker.record_call(now=float(i))
        assert breaker.calls_in_window(now=30.0) == 20
        assert breaker.is_open(now=30.0) is False

    def test_opens_above_threshold(self) -> None:
        breaker = TVCircuitBreaker(max_calls=20, window_seconds=60.0)
        for i in range(21):
            breaker.record_call(now=float(i))
        assert breaker.is_open(now=30.0) is True

    def test_window_prune_closes_breaker(self) -> None:
        breaker = TVCircuitBreaker(max_calls=20, window_seconds=60.0)
        for i in range(25):
            breaker.record_call(now=float(i))  # calls at t=0..24s
        assert breaker.is_open(now=30.0) is True
        # After the burst ages out of the 60s window the breaker closes.
        assert breaker.calls_in_window(now=100.0) == 0
        assert breaker.is_open(now=100.0) is False

    def test_opened_count_edge_triggered_once_per_episode(self) -> None:
        breaker = TVCircuitBreaker(max_calls=5, window_seconds=60.0)
        for i in range(10):
            breaker.record_call(now=float(i))
        assert breaker.is_open(now=30.0) is True
        assert breaker.is_open(now=31.0) is True  # still open — no double count
        assert breaker.opened_count == 1

    def test_reset_clears_state(self) -> None:
        breaker = TVCircuitBreaker(max_calls=5, window_seconds=60.0)
        for i in range(10):
            breaker.record_call(now=float(i))
        breaker.is_open()
        breaker.reset()
        assert breaker.calls_in_window() == 0
        assert breaker.is_open() is False
        assert breaker.stats()["calls_in_window"] == 0

    def test_stats_structure(self) -> None:
        breaker = TVCircuitBreaker(max_calls=20, window_seconds=60.0)
        stats = breaker.stats()
        assert stats["max_calls"] == 20
        assert stats["window_seconds"] == 60.0
        assert stats["open"] is False
        assert stats["opened_count"] == 0


class TestDiscoverStaleWhileRevalidate:
    """Engine-level SWR behavior: serve stale fast, refresh in background."""

    @pytest.mark.asyncio
    async def test_stale_hit_serves_immediately_then_refreshes(
        self, sample_config: ScreenConfig
    ) -> None:
        eng = TVScreenEngine()
        result_a = _make_result(["AAPL"])
        result_b = _make_result(["AAPL", "MSFT"])

        mock = MagicMock()
        mock.discover = AsyncMock(side_effect=[result_a, result_b])
        eng.specialist = mock

        first = await eng.discover(sample_config)
        assert first.tickers == ["AAPL"]
        assert mock.discover.call_count == 1

        key = eng.cache.make_key(sample_config, 500)
        _age_entry(eng.cache, key, seconds=100)  # stale but within stale_ttl

        second = await eng.discover(sample_config)
        assert second.tickers == ["AAPL"], "stale value must be served immediately"
        assert mock.discover.call_count == 1, "provider must NOT be called synchronously"

        # Deterministically await the scheduled background refresh.
        tasks = list(eng._refresh_tasks)
        assert tasks, "stale serve must schedule exactly one refresh"
        await asyncio.gather(*tasks)

        assert mock.discover.call_count == 2, "background refresh should hit provider once"
        refreshed = eng.cache.get(key)
        assert refreshed is not None
        assert refreshed.tickers == ["AAPL", "MSFT"], "cache must be updated in place"

    @pytest.mark.asyncio
    async def test_background_refresh_empty_keeps_stale_entry(
        self, sample_config: ScreenConfig
    ) -> None:
        eng = TVScreenEngine()
        good = _make_result(["AAPL"])
        empty = _make_result([], empty=True)

        mock = MagicMock()
        mock.discover = AsyncMock(side_effect=[good, empty])
        eng.specialist = mock

        await eng.discover(sample_config)
        key = eng.cache.make_key(sample_config, 500)
        _age_entry(eng.cache, key, seconds=100)

        served = await eng.discover(sample_config)
        assert served.tickers == ["AAPL"]

        tasks = list(eng._refresh_tasks)
        assert tasks
        await asyncio.gather(*tasks)

        cached, is_stale = eng.cache.get_with_freshness(key)
        assert cached is not None
        assert cached.tickers == ["AAPL"], "empty refresh must not overwrite good data"
        assert is_stale is True, "entry must remain in the stale window (not overwritten)"

    @pytest.mark.asyncio
    async def test_background_refresh_failure_is_swallowed(
        self, sample_config: ScreenConfig
    ) -> None:
        eng = TVScreenEngine()
        good = _make_result(["AAPL"])

        mock = MagicMock()
        mock.discover = AsyncMock(side_effect=[good, RuntimeError("upstream boom")])
        eng.specialist = mock

        await eng.discover(sample_config)
        key = eng.cache.make_key(sample_config, 500)
        _age_entry(eng.cache, key, seconds=100)

        served = await eng.discover(sample_config)
        assert served.tickers == ["AAPL"]

        tasks = list(eng._refresh_tasks)
        assert tasks
        await asyncio.gather(*tasks)

        cached, _ = eng.cache.get_with_freshness(key)
        assert cached is not None, "failed refresh must leave the stale entry intact"
        assert eng._inflight_refreshes == set()

    @pytest.mark.asyncio
    async def test_discover_records_circuit_breaker_calls(
        self, engine: TVScreenEngine, sample_config: ScreenConfig
    ) -> None:
        assert engine.circuit_breaker.calls_in_window() == 0
        await engine.discover(sample_config)  # miss → 1 upstream call
        assert engine.circuit_breaker.calls_in_window() == 1
        await engine.discover(sample_config)  # fresh hit → no upstream call
        assert engine.circuit_breaker.calls_in_window() == 1
