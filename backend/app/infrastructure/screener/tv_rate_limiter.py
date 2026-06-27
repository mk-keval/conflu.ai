# TV Rate Limiter — Token bucket for TradingView Screener API
"""
TradingView free tier allows ~30 requests per minute.
This rate limiter enforces a conservative 25 req/min with burst support.

Usage:
    limiter = TVRateLimiter()
    async with limiter:
        result = await discover(config)
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any

from backend.app.core.logging import get_logger

log = get_logger("conflu.screener.tv_rate_limiter")


class TVRateLimiter:
    """Async token-bucket rate limiter for TV Screener API.

    Tokens refill every `interval` seconds. Each request consumes one token.
    If no tokens available, waits for the next refill.
    """

    def __init__(
        self,
        max_rate: int = 25,
        interval: float = 60.0,
        burst: int = 5,
    ) -> None:
        self.max_rate = max_rate
        self.interval = interval
        self.burst = burst

        self._tokens: float = burst
        self._last_refill: float = time.monotonic()
        self._lock = asyncio.Lock()
        self._request_times: deque[float] = deque(maxlen=max_rate)
        self._total_blocked: int = 0

    @property
    def tokens(self) -> float:
        return self._tokens

    @property
    def total_blocked(self) -> int:
        return self._total_blocked

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        rate = self.max_rate / self.interval
        new_tokens = elapsed * rate
        if new_tokens > 0:
            self._tokens = min(self.burst, self._tokens + new_tokens)
            self._last_refill = now

    async def acquire(self) -> float:
        """Acquire a token. Returns wait time in seconds."""
        async with self._lock:
            self._refill()
            if self._tokens >= 1:
                self._tokens -= 1
                self._request_times.append(time.monotonic())
                return 0.0

            # Calculate wait time until next token
            wait = self.interval / self.max_rate
            self._total_blocked += 1
            log.warning(
                "rate_limited",
                wait_ms=round(wait * 1000),
                total_blocked=self._total_blocked,
            )
            await asyncio.sleep(wait)

            self._refill()
            self._tokens = max(0, self._tokens - 1)
            self._request_times.append(time.monotonic())
            return wait

    async def __aenter__(self) -> "TVRateLimiter":
        await self.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        pass
