# D-16: Prometheus Metrics via prometheus-fastapi-instrumentator

**Date:** 2026-06-19
**Phase:** 06 — API Layer

## Context
The API layer needed HTTP request metrics (duration, counter, in-progress) for observability.

## Decision
Use `prometheus-fastapi-instrumentator` for automatic Prometheus metric exposition at `/metrics`. This provides Histogram (latency), Counter (per-method/status), and Gauge (in-progress) without manual instrumentation.

## Consequences
- `/metrics` endpoint auto-exposed by the instrumentator
- Custom metrics (WebSocket messages, errors) defined manually via `prometheus_client`
- Dependency added to core `pyproject.toml`
