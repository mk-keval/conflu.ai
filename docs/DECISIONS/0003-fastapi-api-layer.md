# ADR-003: FastAPI for API Layer

**Status:** Accepted
**Date:** 2026-06-18

## Context
Need a Python web framework for REST API and WebSocket endpoints with automatic OpenAPI documentation, dependency injection, and async support.

## Decision
Use FastAPI as the API framework with Pydantic models for request/response validation, automatic OpenAPI docs, and WebSocket support.

## Consequences
- **Positive**: Automatic OpenAPI docs, async native, type-safe with Pydantic, excellent performance
- **Negative**: Requires async/await throughout, ASGI debugging can be tricky
- **Mitigation**: Use uvicorn with --reload for development, structured error handling
