# D-17: OpenTelemetry Optional (Console Exporter by Default)

**Date:** 2026-06-19
**Phase:** 06 — API Layer

## Context
The API layer needed distributed tracing capability, but OTel setup requires a collector endpoint.

## Decision
Make OpenTelemetry optional — if `OTEL_EXPORTER_OTLP_ENDPOINT` is configured, use OTLP exporter; otherwise fall back to `ConsoleSpanExporter`. This avoids hard dependency on an OTel collector at startup.

## Consequences
- OTel dependencies in `[project.optional-dependencies] observability`
- No OTel setup errors if exporter endpoint is missing
- Console exporter works for local development
