# TV Cache — In-memory TTL cache for TV Screener results
"""
Caches TV Screener discovery results to reduce API calls.
TTL-based: results expire after 60 seconds.
LRU eviction: max 50 entries.

Usage:
    cache = TVCache()
    result = cache.get(key)
    if result is None:
        result = await discover(config)
        cache.set(key, result)
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from typing import Any

from backend.app.core.logging import get_logger

log = get_logger("conflu.screener.tv_cache")


class TVCache:
    """In-memory TTL cache for TV Screener results.

    Key is a hash of the ScreenConfig dict + limit.
    Values are cached with a TTL; LRU eviction when maxsize exceeded.
    """

    def __init__(self, ttl: float = 60.0, maxsize: int = 50) -> None:
        self.ttl = ttl
        self.maxsize = maxsize
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._hits: int = 0
        self._misses: int = 0

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
        log.info("cache_cleared")

    def stats(self) -> dict[str, Any]:
        return {
            "size": self.size,
            "maxsize": self.maxsize,
            "ttl": self.ttl,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / max(1, self.hits + self.misses) * 100, 1),
        }
