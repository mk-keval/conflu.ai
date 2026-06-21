"""API middleware: logging, rate limiting, API key authentication.

Uses BaseHTTPMiddleware for clean request/response interception.
Order matters: CORSMiddleware (outermost) → RequestLog → RateLimit → APIKey (innermost).
"""

from __future__ import annotations

import threading
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.app.core.config import settings
from backend.app.core.logging import get_logger, set_correlation_id

log = get_logger("conflu.api.middleware")


class TokenBucket:
    """Simple in-memory token bucket for rate limiting.

    Thread-safe via threading.Lock().
    """

    def __init__(self, rate: int, window_s: int = 60) -> None:
        self._rate = rate
        self._window_s = window_s
        self._tokens = float(rate)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        """Consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume.

        Returns:
            True if tokens were consumed, False if rate limited.
        """
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        refill = (elapsed / self._window_s) * self._rate
        self._tokens = min(float(self._rate), self._tokens + refill)
        self._last_refill = now

    @property
    def remaining(self) -> int:
        """Current token count (rounded down)."""
        with self._lock:
            self._refill()
            return int(self._tokens)

    def reset_in(self) -> float:
        """Seconds until the bucket is fully refilled."""
        with self._lock:
            elapsed = time.monotonic() - self._last_refill
            fill_time = self._window_s * (1.0 - self._tokens / self._rate)
            return max(0.0, fill_time - elapsed)


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Log all HTTP requests with correlation ID, method, path, status, duration.

    Sets a correlation ID at the start of each request and adds
    X-Request-ID response header.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip logging for health and metrics endpoints to reduce noise
        if request.url.path in ("/health", "/health/ready", "/metrics"):
            return await call_next(request)

        request_id = set_correlation_id()
        start = time.monotonic()

        response = await call_next(request)

        duration_ms = (time.monotonic() - start) * 1000
        log.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
            content_length=response.headers.get("content-length"),
        )

        response.headers["X-Request-ID"] = request_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token bucket rate limiting per client.

    Rate limits are applied based on endpoint path prefix:
    - /api/v1/screen*     -> screener rate limit
    - /api/v1/backtest*   -> backtest rate limit
    - /api/v1/data*       -> data rate limit
    - /api/v1/risk*       -> default rate limit
    """

    PUBLIC_PATHS = frozenset({"/health", "/health/ready", "/docs", "/redoc"})

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self._buckets: dict[str, TokenBucket] = {}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip rate limiting for public/health paths
        if request.url.path in self.PUBLIC_PATHS or request.url.path.startswith("/metrics"):
            return await call_next(request)

        client_id = self._get_client_id(request)
        rate, window_s = self._get_rate_limit(request.url.path)

        bucket = self._get_or_create_bucket(client_id, rate, window_s)

        if not bucket.consume():
            reset_seconds = int(bucket.reset_in())
            return JSONResponse(
                status_code=429,
                headers={
                    "X-RateLimit-Limit": str(rate),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time() + reset_seconds)),
                    "Retry-After": str(reset_seconds),
                },
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit of {rate} requests per {window_s}s exceeded",
                    }
                },
            )

        response = await call_next(request)

        # Add rate limit headers to successful responses
        response.headers["X-RateLimit-Limit"] = str(rate)
        response.headers["X-RateLimit-Remaining"] = str(bucket.remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + bucket.reset_in()))

        return response

    def _get_client_id(self, request: Request) -> str:
        """Identify client by API key or IP."""
        api_key = request.headers.get("X-API-Key", "")
        if api_key:
            return f"key:{api_key}"
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"

    def _get_rate_limit(self, path: str) -> tuple[int, int]:
        """Get (rate, window_seconds) for a path."""
        if path.startswith("/api/v1/screen"):
            return settings.api.rate_limit_screener, 60
        elif path.startswith("/api/v1/backtest"):
            return settings.api.rate_limit_backtest, 60
        elif path.startswith("/api/v1/data") or path.startswith("/api/v1/indicators"):
            return settings.api.rate_limit_data, 60
        else:
            return settings.api.rate_limit, 60

    def _get_or_create_bucket(self, client_id: str, rate: int, window_s: int) -> TokenBucket:
        """Get existing bucket or create a new one."""
        if client_id not in self._buckets:
            self._buckets[client_id] = TokenBucket(rate, window_s)
        return self._buckets[client_id]


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Authenticate requests using X-API-Key header.

    If no API keys are configured in settings, authentication is disabled
    (development mode). When keys are configured, all non-public requests
    must include a valid X-API-Key header.
    """

    PUBLIC_PATHS = frozenset({
        "/health",
        "/health/ready",
        "/docs",
        "/redoc",
        "/api/v1/openapi.json",
        "/metrics",
    })

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip auth for public paths and WebSocket endpoints
        if request.url.path in self.PUBLIC_PATHS or request.url.path.startswith("/ws/"):
            return await call_next(request)

        # If no API keys configured, auth is disabled (dev mode)
        if not settings.api.api_keys:
            return await call_next(request)

        # Check API key
        api_key = request.headers.get("X-API-Key")
        if api_key not in settings.api.api_keys:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Valid X-API-Key header required",
                    }
                },
            )

        return await call_next(request)
