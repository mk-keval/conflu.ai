"""Observability setup — Prometheus metrics and OpenTelemetry tracing.

Provides factory functions called from the FastAPI lifespan:
- setup_prometheus(app): FastAPI request metrics, custom WS/rate-limit metrics
- setup_opentelemetry(app): Distributed tracing with OTLP export or console
"""

from __future__ import annotations

from typing import Any

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

log = get_logger("conflu.api.observability")

# ── Global Prometheus Metrics ──

ws_connections_gauge: Any = None
ws_messages_total: Any = None
ws_errors_total: Any = None
rate_limit_exceeded_total: Any = None


def _init_metrics() -> None:
    """Initialize Prometheus metrics (called once on first use)."""
    global ws_connections_gauge, ws_messages_total, ws_errors_total, rate_limit_exceeded_total

    try:
        from prometheus_client import Counter, Gauge

        ws_connections_gauge = Gauge(
            "ws_connections_active",
            "Current number of active WebSocket connections",
        )
        ws_messages_total = Counter(
            "ws_messages_total",
            "Total number of WebSocket messages processed",
            labelnames=("channel_type",),
        )
        ws_errors_total = Counter(
            "ws_errors_total",
            "Total number of WebSocket errors",
            labelnames=("error_type",),
        )
        rate_limit_exceeded_total = Counter(
            "rate_limit_exceeded_total",
            "Total number of rate limit exceeded responses",
            labelnames=("endpoint_group",),
        )
        log.info("prometheus_metrics_initialized")
    except ImportError:
        log.warning("prometheus_client not available — metrics disabled")


def setup_prometheus(app: Any) -> None:
    """Configure Prometheus FastAPI instrumentation and custom metrics.

    Uses prometheus-fastapi-instrumentator to auto-collect:
    - http_request_duration_seconds (histogram)
    - http_requests_total (counter)

    Also initializes custom application metrics.

    Args:
        app: FastAPI application instance.
    """
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        _init_metrics()

        instrumentator = Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
        )
        # Don't add middleware - just expose the /metrics endpoint
        # The middleware causes issues with _IncludedRouter objects
        instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)
        log.info("prometheus_instrumentation_ready (metrics endpoint only)")
    except ImportError:
        log.warning(
            "prometheus-fastapi-instrumentator not available — "
            "prometheus metrics disabled"
        )


def setup_opentelemetry(app: Any) -> None:
    """Configure OpenTelemetry tracing for the FastAPI application.

    Uses OTLP exporter if endpoint is configured, otherwise console exporter.
    Wraps in try/except for optional packages.

    Args:
        app: FastAPI application instance.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        resource = Resource.create(
            attributes={
                "service.name": settings.api.otel_service_name,
            }
        )
        provider = TracerProvider(resource=resource)

        if settings.api.otel_exporter_otlp_endpoint:
            exporter = OTLPSpanExporter(
                endpoint=settings.api.otel_exporter_otlp_endpoint,
            )
            log.info(
                "otel_using_otlp_exporter",
                endpoint=settings.api.otel_exporter_otlp_endpoint,
            )
        else:
            exporter = ConsoleSpanExporter()
            log.info("otel_using_console_exporter")

        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app)
        log.info("opentelemetry_instrumentation_ready")
    except ImportError as e:
        log.warning(
            "opentelemetry_packages_not_available",
            error=str(e),
        )
