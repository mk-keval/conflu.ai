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
    """Initialize Prometheus metrics (called once on first use).

    All metrics use registry-guarded creation (mirrors ws/handler.py's pattern):
    if a collector name already exists (e.g. the app was created twice in the
    same process — tests, uvicorn reload), reuse the existing collector instead
    of raising ``DuplicateTimeseries``.
    """
    global ws_connections_gauge, ws_messages_total, ws_errors_total, rate_limit_exceeded_total

    try:
        from prometheus_client import REGISTRY, Counter, Gauge

        def _get_or_create_metric(metric_type: Any, name: str, desc: str, labelnames: tuple[str, ...] = ()) -> Any:
            """Return the existing collector for ``name`` or create a new one."""
            if name in REGISTRY._names_to_collectors:
                for collector in REGISTRY._collector_to_names:
                    if name in REGISTRY._collector_to_names[collector]:
                        return collector
            return metric_type(name, desc, labelnames=labelnames)

        ws_connections_gauge = _get_or_create_metric(
            Gauge, "ws_connections_active", "Current number of active WebSocket connections"
        )
        ws_messages_total = _get_or_create_metric(
            Counter, "ws_messages_total", "Total number of WebSocket messages processed", ("channel_type",)
        )
        ws_errors_total = _get_or_create_metric(
            Counter, "ws_errors_total", "Total number of WebSocket errors", ("error_type",)
        )
        rate_limit_exceeded_total = _get_or_create_metric(
            Counter, "rate_limit_exceeded_total", "Total number of rate limit exceeded responses", ("endpoint_group",)
        )
        log.info("prometheus_metrics_initialized")
    except ImportError:
        log.warning("prometheus_client not available — metrics disabled")


def _patch_instrumentator_routing() -> None:
    """Make prometheus-fastapi-instrumentator tolerate FastAPI >= 0.138.

    FastAPI 0.138+ stores included routers in ``app.routes`` as
    ``_IncludedRouter`` objects that have no ``.path`` attribute, which crashes
    the instrumentator's route-name resolver (``AttributeError``). Flatten them
    via ``effective_route_contexts()`` (duck-typed, so older FastAPI versions
    are unaffected). Idempotent.
    """
    try:
        from prometheus_fastapi_instrumentator import routing
        from starlette.routing import Match, Mount

        def _safe_get_route_name(scope: Any, routes: list[Any], route_name: str | None = None) -> str | None:
            for route in routes:
                effective = getattr(route, "effective_route_contexts", None)
                if effective is not None:
                    for ctx in effective():
                        match, child_scope = ctx.matches(scope)
                        if match == Match.FULL:
                            return ctx.path or getattr(ctx.starlette_route, "path", "")
                        if match == Match.PARTIAL and route_name is None:
                            route_name = ctx.path or getattr(ctx.starlette_route, "path", "")
                    continue
                match, child_scope = route.matches(scope)
                if match == Match.FULL:
                    route_name = route.path
                    child_scope = {**scope, **child_scope}
                    if isinstance(route, Mount) and route.routes:
                        child_route_name = _safe_get_route_name(child_scope, route.routes, route_name)
                        if child_route_name is None:
                            route_name = None
                        else:
                            route_name = f"{route_name}{child_route_name}"
                    return route_name
                elif match == Match.PARTIAL and route_name is None:
                    route_name = route.path
            return None

        routing._get_route_name = _safe_get_route_name
    except ImportError:
        pass


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
        _patch_instrumentator_routing()

        instrumentator = Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
        )
        # Enable the middleware so http_requests_total / http_request_duration_seconds
        # are actually collected. The route-name resolver is patched above to handle
        # FastAPI >= 0.138 _IncludedRouter objects (see _patch_instrumentator_routing).
        instrumentator.instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
        log.info("prometheus_instrumentation_ready")
    except ImportError:
        log.warning("prometheus-fastapi-instrumentator not available — prometheus metrics disabled")


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
