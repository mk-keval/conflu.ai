# TV Cache — In-memory TTL cache for TV Screener results
"""
Caches TV Screener discovery results to reduce API calls.
TTL-based: results expire after 60 seconds, but stay serveable as *stale*
data for a further `stale_ttl` window (stale-while-revalidate): callers get
the stale value immediately and refresh in the background, preferring
stale-with-freshness-label over hammering the upstream provider.
LRU eviction: max 50 entries.

Usage:
    cache = TVCache()
    result = cache.get(key)
    if result is None:
        result = await discover(config)
        cache.set(key, result)

Stale-while-revalidate:
    value, is_stale = cache.get_with_freshness(key)
    if value is not None:
        serve(value)  # label freshness when is_stale
        if is_stale:
            schedule background refresh
Empty cached states are never served (fresh or stale).
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from typing import Any

import pandas as pd

from backend.app.core.logging import get_logger

log = get_logger("conflu.screener.tv_cache")


class TVCache:
    """In-memory TTL cache for TV Screener results.

    Key is a hash of the ScreenConfig dict + limit.
    Values are cached with a TTL; LRU eviction when maxsize exceeded.
    Entries older than `ttl` but younger than `stale_ttl` remain
    serveable via :meth:`get_with_freshness` for stale-while-revalidate
    flows; they are hard-evicted once past `stale_ttl`.
    """

    def __init__(
        self,
        ttl: float = 60.0,
        maxsize: int = 50,
        stale_ttl: float = 300.0,
    ) -> None:
        self.ttl = ttl
        self.maxsize = maxsize
        self.stale_ttl = stale_ttl
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._hits: int = 0
        self._misses: int = 0
        self._stale_hits: int = 0

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def size(self) -> int:
        return len(self._cache)

    def _make_key(self, config_dict: dict[str, Any], limit: int) -> str:
        """Create a deterministic cache key from config data."""
        payload = json.dumps({"config": config_dict, "limit": limit}, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def get(self, key: str) -> Any | None:
        """Get cached value. Returns None if missing or expired."""
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None

        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._cache[key]
            self._misses += 1
            return None

        # Move to end (MRU) on access
        self._cache.move_to_end(key)
        self._hits += 1
        return value

    def get_with_freshness(self, key: str) -> tuple[Any | None, bool]:
        """Stale-while-revalidate lookup.

        Returns ``(value, is_stale)``:

        - fresh hit (age <= ttl): ``(value, False)``
        - stale hit (ttl < age <= stale_ttl): ``(value, True)`` — the entry
          is retained so a background refresh can overwrite it in place
        - miss or hard-expired (age > stale_ttl): ``(None, False)``

        Empty cached states are never served (see :meth:`_is_serveable`).
        """
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None, False

        expires_at, value = entry
        now = time.monotonic()
        age = now - (expires_at - self.ttl)

        if age > self.stale_ttl:
            del self._cache[key]
            self._misses += 1
            return None, False

        if age > self.ttl:
            if not self._is_serveable(value):
                del self._cache[key]
                self._misses += 1
                return None, False
            # Retain the entry; caller schedules a background refresh.
            self._cache.move_to_end(key)
            self._stale_hits += 1
            log.info("stale_served", key=key, age_s=round(age, 1))
            return value, True

        self._cache.move_to_end(key)
        self._hits += 1
        return value, False

    @staticmethod
    def _is_serveable(value: Any) -> bool:
        """Guard: never serve silently-empty cached states.

        Discovery results whose raw_data is missing or an empty DataFrame
        are treated as unserveable so transient upstream failures can't be
        laundered into long-lived "0 matches" answers.
        """
        if value is None:
            return False
        raw = getattr(value, "raw_data", None)
        if isinstance(raw, pd.DataFrame):
            return not raw.empty
        return True

    def set(self, key: str, value: Any) -> None:
        """Set a cached value with TTL."""
        expires_at = time.monotonic() + self.ttl
        self._cache[key] = (expires_at, value)
        self._cache.move_to_end(key)

        # Evict LRU entries if over maxsize
        while len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)

    def make_key(self, config: Any, limit: int = 500) -> str:
        """Helper to create a key from a ScreenConfig object."""
        return self._make_key(config.model_dump(mode="python"), limit)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        self._stale_hits = 0
        log.info("cache_cleared")

    def stats(self) -> dict[str, Any]:
        return {
            "size": self.size,
            "maxsize": self.maxsize,
            "ttl": self.ttl,
            "stale_ttl": self.stale_ttl,
            "hits": self.hits,
            "misses": self.misses,
            "stale_hits": self._stale_hits,
            "hit_rate": round(self.hits / max(1, self.hits + self.misses) * 100, 1),
        }
