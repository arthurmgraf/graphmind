"""OpenTelemetry setup for distributed tracing."""

from __future__ import annotations

import structlog
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = structlog.get_logger(__name__)


def setup_otel(
    app: FastAPI,
    service_name: str = "graphmind-api",
    endpoint: str | None = None,
) -> None:
    """Configure OpenTelemetry tracing for the FastAPI application.

    Args:
        app: The FastAPI application instance to instrument.
        service_name: Logical service name reported in traces.
        endpoint: Optional OTLP gRPC collector endpoint. When provided,
            a :class:`BatchSpanProcessor` with an
            :class:`OTLPSpanExporter` is registered so spans are
            exported to the collector.
    """
    resource = Resource(attributes={"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if endpoint is not None:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    logger.info(
        "OpenTelemetry configured: service_name=%s, endpoint=%s",
        service_name,
        endpoint,
    )


def get_tracer(name: str = "graphmind") -> trace.Tracer:
    """Return a named tracer from the global provider.

    Args:
        name: Tracer instrumentation name.

    Returns:
        An OpenTelemetry :class:`~opentelemetry.trace.Tracer`.
    """
    return trace.get_tracer(name)
