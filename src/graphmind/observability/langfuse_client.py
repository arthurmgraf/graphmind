from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator

from graphmind.config import get_settings

logger = logging.getLogger(__name__)

_langfuse = None


def get_langfuse():
    global _langfuse
    if _langfuse is not None:
        return _langfuse

    settings = get_settings()
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.info("Langfuse keys not configured, observability disabled")
        return None

    try:
        from langfuse import Langfuse

        _langfuse = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        logger.info("Langfuse connected to %s", settings.langfuse_host)
        return _langfuse
    except Exception as exc:
        logger.warning("Failed to initialize Langfuse: %s", exc)
        return None


@contextmanager
def trace_query(
    question: str, metadata: dict[str, Any] | None = None
) -> Generator[dict, None, None]:
    lf = get_langfuse()
    trace_data: dict[str, Any] = {"trace": None, "spans": []}

    if lf is None:
        yield trace_data
        return

    try:
        trace = lf.trace(
            name="graphmind-query",
            input={"question": question},
            metadata=metadata or {},
        )
        trace_data["trace"] = trace
        yield trace_data

        output = trace_data.get("output", {})
        trace.update(output=output)
    except Exception as exc:
        logger.error("Langfuse trace error: %s", exc)
        yield trace_data


def log_span(
    trace_data: dict,
    name: str,
    input_data: Any = None,
    output_data: Any = None,
    metadata: dict | None = None,
) -> None:
    trace = trace_data.get("trace")
    if trace is None:
        return

    try:
        span = trace.span(
            name=name,
            input=input_data,
            output=output_data,
            metadata=metadata or {},
        )
        trace_data["spans"].append(span)
    except Exception as exc:
        logger.error("Langfuse span error: %s", exc)


def log_generation(
    trace_data: dict,
    name: str,
    model: str,
    input_text: str,
    output_text: str,
    usage: dict | None = None,
) -> None:
    trace = trace_data.get("trace")
    if trace is None:
        return

    try:
        trace.generation(
            name=name,
            model=model,
            input=input_text,
            output=output_text,
            usage=usage or {},
        )
    except Exception as exc:
        logger.error("Langfuse generation error: %s", exc)


def flush() -> None:
    lf = get_langfuse()
    if lf is not None:
        lf.flush()
