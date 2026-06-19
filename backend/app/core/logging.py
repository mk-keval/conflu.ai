"""Structured logging configuration using structlog."""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from uuid import uuid4

import structlog
from structlog.processors import CallsiteParameter, CallsiteParameterAdder

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def configure_logging(*, log_level: str = "INFO", log_json: bool = True) -> None:
    """Configure structlog with JSON output and correlation ID support.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        log_json: If True, output JSON-formatted logs. If False, use console-friendly format.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        CallsiteParameterAdder(
            [
                CallsiteParameter.FILENAME,
                CallsiteParameter.FUNC_NAME,
                CallsiteParameter.LINENO,
            ]
        ),
    ]

    if log_json:
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        shared_processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )


def set_correlation_id(cid: str | None = None) -> str:
    """Set and return a correlation ID for the current async context.

    Args:
        cid: Optional pre-existing correlation ID. If None, generates a new UUID.

    Returns:
        The correlation ID string.
    """
    cid = cid or str(uuid4())
    correlation_id.set(cid)
    structlog.contextvars.bind_contextvars(correlation_id=cid)
    return cid


def get_logger(name: str = "conflu") -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically module path).

    Returns:
        A structlog BoundLogger instance.
    """
    log: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return log
