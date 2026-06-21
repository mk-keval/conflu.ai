# D-19: Error Response Envelope

**Date:** 2026-06-19
**Phase:** 06 — API Layer

## Context
The API needed a consistent error response format across all endpoints for client-side error handling.

## Decision
Use `{error: {code, message, details, request_id}}` envelope for all error responses:
- `code`: Machine-readable error code (`NOT_FOUND`, `VALIDATION_ERROR`, `RATE_LIMIT_EXCEEDED`)
- `message`: Human-readable description
- `details`: Optional structured error details (field-level validation, engine error info)
- `request_id`: Correlation ID from `RequestLogMiddleware`

## Consequences
- Consistent error handling across all exception types
- Clients can programmatically handle errors by code
- `request_id` enables log correlation for debugging
