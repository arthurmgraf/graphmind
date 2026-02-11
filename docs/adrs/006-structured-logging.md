# ADR-006: Structured Logging with structlog + OTEL Correlation

## Status
Accepted

## Context
GraphMind uses multiple logging approaches across its codebase: Python's standard `logging` module in API routes, middleware, LLM routing, and health checks, and `structlog` in the ingestion pipeline. As the system grows across multiple services and potentially multiple processes, several challenges emerge:

1. **Correlation**: When a single user request triggers multiple LLM calls, retrieval operations, and graph queries, it is difficult to trace all log entries belonging to that request. The `RequestLoggingMiddleware` generates an `X-Request-ID` (8-character UUID) but this is only attached to the HTTP-level request/response log line, not to downstream component logs.

2. **Structured output**: Standard `logging` produces free-form text messages (`"Provider %s failed after %.0f ms: %s"`). These are human-readable but difficult to parse, filter, and aggregate in log management systems (ELK, Loki, Datadog).

3. **Context propagation**: The ingestion pipeline already uses structlog with bound context (`document_id`, `filename`, `content_hash`), demonstrating the value of structured context. But query-path components do not benefit from the same approach.

4. **Observability integration**: The system uses Langfuse for LLM tracing but lacks integration with OpenTelemetry (OTEL) for distributed tracing. OTEL trace IDs and span IDs should appear in logs for correlation between logs and traces.

## Decision
Adopt `structlog` as the standard logging library across all GraphMind modules, configured with the following strategy:

1. **Unified structlog configuration**: Configure structlog at application startup in `create_app()` with processors for:
   - Timestamping (ISO 8601 format)
   - Log level enrichment
   - JSON rendering for production, console rendering for development
   - Exception formatting with traceback

2. **Request context binding**: Extend `RequestLoggingMiddleware` to bind `request_id` into a structlog context variable (via `contextvars`). All downstream log calls within that request automatically include `request_id` without explicit passing.

3. **OTEL correlation**: Add an OTEL processor to structlog that extracts the current `trace_id` and `span_id` from the OTEL context (if present) and injects them as fields in every log entry. This enables joining logs with Langfuse traces and future OTEL-based tracing.

4. **Bound loggers for components**: Each module creates a bound logger with `structlog.get_logger(__name__)` (already the pattern in `pipeline.py`). Components bind additional context as needed:
   - Query route: `question`, `engine`, `request_id`
   - LLM router: `provider`, `circuit_state`
   - Embedder: `model`, `batch_size`
   - Health check: `service_name`

5. **Migration path**: Migrate modules incrementally from `logging.getLogger` to `structlog.get_logger`. Both can coexist during the transition because structlog can be configured to wrap the standard library.

## Consequences
- **Queryability**: All log entries are structured JSON in production, enabling efficient filtering by `request_id`, `provider`, `document_id`, or any other bound field in log aggregation tools.
- **Correlation**: Every log entry within a request includes `request_id` and, when OTEL is active, `trace_id` and `span_id`. This connects logs to Langfuse traces.
- **Consistency**: One logging library and pattern across the entire codebase, replacing the current split between `logging` and `structlog`.
- **Development experience**: Console renderer in development mode preserves human-readable output with color coding.
- **Migration effort**: Existing modules using `logging.getLogger` need to be updated. The migration is mechanical (replace logger creation and convert format-string calls to keyword arguments) but touches many files.
- **Dependency**: structlog is already a dependency (used in `pipeline.py`). No new dependency is introduced. OTEL integration requires `opentelemetry-api` as an optional dependency.
- **Performance**: structlog adds minimal overhead. The JSON renderer is slightly slower than plain text but acceptable for the expected request volume.
