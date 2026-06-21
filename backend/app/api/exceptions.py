"""API exception hierarchy and exception handler registration.

Provides standardized error responses in the format:
{error: {code, message, details, request_id}}
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from starlette.responses import JSONResponse

from backend.app.core.logging import correlation_id, get_logger

log = get_logger("conflu.api.exceptions")


class ApiError(Exception):
    """Base API error with structured error information."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


class NotFoundError(ApiError):
    """Resource not found (404)."""

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            status_code=404,
            code="NOT_FOUND",
            message=f"{resource} '{identifier}' not found",
        )


class ValidationError(ApiError):
    """Validation error (422)."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            status_code=422,
            code="VALIDATION_ERROR",
            message=message,
            details=details,
        )


class RateLimitError(ApiError):
    """Rate limit exceeded (429)."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            status_code=429,
            code="RATE_LIMIT_EXCEEDED",
            message=message or "Rate limit exceeded. Try again later.",
        )


class EngineError(ApiError):
    """Wraps an engine-level error into a 500 API error."""

    def __init__(self, engine: str, original_error: Exception) -> None:
        super().__init__(
            status_code=500,
            code=f"{engine.upper()}_ERROR",
            message=f"{engine} execution failed: {original_error}",
            details={"engine": engine},
        )


def _build_error_response(
    code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build a standardized JSON error response."""
    rid = correlation_id.get()
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": rid or None,
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app.

    Registers handlers for:
    - ApiException hierarchy → structured JSON errors
    - HTTPException (FastAPI built-in) → standardized envelope
    - Exception (catch-all) → sanitized internal error
    """

    @app.exception_handler(ApiError)
    async def api_exception_handler(request: Request, exc: ApiError) -> JSONResponse:  # noqa: ARG001
        """Handle all ApiError subclasses with structured error response."""
        log.warning(
            "api_exception",
            code=exc.code,
            status=exc.status_code,
            path=request.url.path,
        )
        return _build_error_response(
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:  # noqa: ARG001
        """Handle FastAPI built-in HTTP exceptions (422 validation, 401, etc.)."""
        return _build_error_response(
            code="HTTP_ERROR",
            message=exc.detail,
            status_code=exc.status_code,
            details={"headers": dict(exc.headers)} if exc.headers else None,
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: ARG001
        """Catch-all handler: log full traceback, return sanitized response."""
        log.exception(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
        )
        return _build_error_response(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred. Please try again.",
            status_code=500,
        )
