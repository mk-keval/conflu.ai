# ADR-008: Prometheus + Grafana Observability

**Status:** Accepted
**Date:** 2026-06-18

## Context
Need a production observability stack for metrics collection, visualization, log aggregation, and distributed tracing.

## Decision
Use Prometheus for metrics collection with prometheus-fastapi-instrumentator, Grafana for dashboards with provisioning, Loki for log aggregation, Tempo for distributed tracing, and OpenTelemetry for instrumentation.

## Consequences
- **Positive**: Industry-standard stack, auto-instrumentation for FastAPI, pre-provisioned dashboards
- **Negative**: Resource overhead from running multiple services
- **Mitigation**: Compose profiles for optional deployment, configurable resource limits
