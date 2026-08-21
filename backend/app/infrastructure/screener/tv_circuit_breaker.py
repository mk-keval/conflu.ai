# TV Circuit Breaker — Sliding-window upstream call guard
"""
Protects against rate-limit spirals during discovery bursts.

Tracks TradingView API call timestamps in a trailing window. When the
call count exceeds `max_calls` within `window_seconds`, the breaker
"opens": consumers (e.g. the SNAPSHOT_MULTI_SCREEN flag in P1.2) must
fall back to cached/local paths instead of issuing more upstream calls.

This is a volume guard, not an error guard — it complements TVRateLimiter
(which paces calls) by deciding whether extra speculative calls are
allowed at all.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any

from backend.app.core.logging import get_logger

log = get_logger("conflu.screener.tv_circuit_breaker")


class TVCircuitBreaker:
    """Sliding-window circuit breaker on upstream TV call volume.

    Single-event-loop assumption: mutated only from async code running on
    the engine's loop, so a plain deque suffices (no lock).
    """

    def __init__(self, max_calls: int = 20, window_seconds: float = 60.0) -> None:
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._call_times: deque[float] = deque()
        self._opened_count: int = 0
        self._was_open: bool = False

    def record_call(self, *, now: float | None = None) -> None:
        """Record one upstream call at ``now`` (defaults to monotonic)."""
        self._call_times.append(now if now is not None else time.monotonic())

    def _prune(self, now: float) -> None:
        horizon = now - self.window_seconds
        while self._call_times and self._call_times[0] <= horizon:
            self._call_times.popleft()

    def calls_in_window(self, *, now: float | None = None) -> int:
        """Number of recorded calls inside the trailing window."""
        current = now if now is not None else time.monotonic()
        self._prune(current)
        return len(self._call_times)

    def is_open(self, *, now: float | None = None) -> bool:
        """True when call volume in the window exceeds max_calls.

        While open, consumers must not issue additional upstream calls;
        serve stale/cached data or defer to legacy single-screen paths.
        """
        current = now if now is not None else time.monotonic()
        count = self.calls_in_window(now=current)
        is_open = count > self.max_calls
        if is_open and not self._was_open:
            # Count each transition into "open" once per overflow episode.
            self._opened_count += 1
            log.warning(
                "circuit_breaker_open",
                calls_in_window=count,
                max_calls=self.max_calls,
                window_s=self.window_seconds,
            )
        self._was_open = is_open
        return is_open

    @property
    def opened_count(self) -> int:
        """How many times the breaker transitioned into the open state."""
        return self._opened_count

    def reset(self) -> None:
        """Clear all recorded calls (e.g. between test cases)."""
        self._call_times.clear()
        self._was_open = False

    def stats(self) -> dict[str, Any]:
        return {
            "max_calls": self.max_calls,
            "window_seconds": self.window_seconds,
            "calls_in_window": self.calls_in_window(),
            "open": self.is_open(),
            "opened_count": self._opened_count,
        }
