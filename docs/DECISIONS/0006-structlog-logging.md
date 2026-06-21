# ADR-006: structlog for Structured Logging

**Status:** Accepted
**Date:** 2026-06-18

## Context
Need structured JSON logging with correlation IDs, context propagation, and integration with observability tools like Loki.

## Decision
Use structlog as the logging framework with JSON output, correlation ID propagation via context variables, and Loki integration.

## Consequences
- **Positive**: Structured JSON logs, correlation ID propagation, easy Loki integration
- **Negative**: Slightly more verbose than stdlib logging
- **Mitigation**: Factory function pattern for consistent logger creation across modules
