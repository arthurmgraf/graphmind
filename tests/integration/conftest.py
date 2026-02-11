"""Integration test fixtures.

These tests require Docker services running:
    make infra
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ["GRAPHMIND_ENV"] = "test"


def _service_available(host: str, port: int) -> bool:
    import socket
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def qdrant_available():
    return _service_available("localhost", 6333)


@pytest.fixture(scope="session")
def neo4j_available():
    return _service_available("localhost", 7687)


@pytest.fixture(scope="session")
def ollama_available():
    return _service_available("localhost", 11434)
