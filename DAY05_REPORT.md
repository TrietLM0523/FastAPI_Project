# Day 05 — Platform Reliability

## Goal

Hoàn thành Platform Reliability với structured logging, request tracing, xử lý lỗi tập trung, health checks và cấu hình vận hành an toàn.

## Implemented features

- JSON application and access logs with configurable severity.
- Request ID propagation and monotonic request-duration measurement.
- Central handlers for service, HTTP, validation, and unexpected errors.
- Backward-compatible health check plus dedicated liveness and readiness checks.
- Environment-controlled trusted hosts and CORS policy.
- Startup protection against the known development JWT secret in non-debug or production operation.

## Request lifecycle

1. The request-context middleware preserves an inbound `X-Request-ID` or creates a UUID.
2. Trusted-host and CORS policies run before routing.
3. Dependencies, routes, services, and repositories perform the request work.
4. Central handlers turn known failures into a consistent, safe response.
5. The middleware adds `X-Request-ID` to the response and emits one structured access record with status and duration.

## Error-response example

```json
{
  "detail": "Task not found",
  "error_code": "not_found",
  "request_id": "98c2be70-c36c-458a-8b25-b5ff93d567fb"
}
```

Unexpected failures are logged with traceback details internally, while clients receive only `Internal server error`.

## Health endpoints

- `GET /api/v1/health`: original application health response.
- `GET /api/v1/health/live`: process-only liveness; never queries the database.
- `GET /api/v1/health/ready`: database readiness using asynchronous `SELECT 1`; returns `503` with a safe response when unavailable.

## Tests executed

- `ruff format .`
- `ruff check .`
- `pytest -v`
- `python -m alembic check`

Coverage includes request IDs, structured formatting, duplicate-handler prevention, error mappings, safe unexpected errors, health endpoints, database failure, list parsing, and production secret validation.

## Remaining limitations

- Logs are written to the process stream; collection, retention, and alerting belong to the deployment platform.
- Readiness currently checks only the database because it is the application's only required external runtime dependency.
