"""Integration tests for the GraphMind API.

Uses FastAPI TestClient with create_app() factory.
Requires: Docker services running (make infra)
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.integration


class TestHealthEndpoint:
    """Health endpoint integration tests (run even without real services)."""

    def test_health_returns_200(self):
        """Test that the health endpoint returns 200 with mocked services."""
        from graphmind.api.main import create_app
        from graphmind.config import Settings
        from fastapi.testclient import TestClient

        settings = Settings(
            groq_api_key="test",
            gemini_api_key="test",
            neo4j_password="test",
        )
        app = create_app(settings=settings)

        # Mock startup to avoid real connections
        with patch.object(app.state.resources, "startup", new_callable=AsyncMock):
            with patch.object(app.state.resources, "shutdown", new_callable=AsyncMock):
                with TestClient(app) as client:
                    response = client.get("/api/v1/health")
                    assert response.status_code == 200
                    data = response.json()
                    assert "status" in data
                    assert "version" in data


class TestMetricsEndpoint:
    """Prometheus metrics endpoint tests."""

    def test_metrics_returns_200(self):
        from graphmind.api.main import create_app
        from graphmind.config import Settings
        from fastapi.testclient import TestClient

        settings = Settings(
            groq_api_key="test",
            gemini_api_key="test",
            neo4j_password="test",
        )
        app = create_app(settings=settings)

        with patch.object(app.state.resources, "startup", new_callable=AsyncMock):
            with patch.object(app.state.resources, "shutdown", new_callable=AsyncMock):
                with TestClient(app) as client:
                    response = client.get("/metrics")
                    assert response.status_code == 200
                    assert "graphmind_" in response.text


class TestErrorHandling:
    """Test structured error responses."""

    def test_invalid_query_returns_validation_error(self):
        from graphmind.api.main import create_app
        from graphmind.config import Settings
        from fastapi.testclient import TestClient

        settings = Settings(
            groq_api_key="test",
            gemini_api_key="test",
            neo4j_password="test",
        )
        app = create_app(settings=settings)

        with patch.object(app.state.resources, "startup", new_callable=AsyncMock):
            with patch.object(app.state.resources, "shutdown", new_callable=AsyncMock):
                with TestClient(app) as client:
                    # Empty question should fail validation (min_length=3)
                    response = client.post("/api/v1/query", json={"question": "ab"})
                    assert response.status_code == 422  # Pydantic validation

    def test_invalid_engine_returns_error(self):
        from graphmind.api.main import create_app
        from graphmind.config import Settings
        from fastapi.testclient import TestClient

        settings = Settings(
            groq_api_key="test",
            gemini_api_key="test",
            neo4j_password="test",
        )
        app = create_app(settings=settings)

        with patch.object(app.state.resources, "startup", new_callable=AsyncMock):
            with patch.object(app.state.resources, "shutdown", new_callable=AsyncMock):
                with TestClient(app) as client:
                    response = client.post("/api/v1/query", json={
                        "question": "What is LangGraph?",
                        "engine": "invalid_engine",
                    })
                    assert response.status_code == 422


class TestAPIKeyAuth:
    """Test API key authentication middleware."""

    def test_protected_endpoint_requires_auth(self):
        from graphmind.api.main import create_app
        from graphmind.config import Settings
        from fastapi.testclient import TestClient

        settings = Settings(
            groq_api_key="test",
            gemini_api_key="test",
            neo4j_password="test",
            api_key="secret-key-123",
        )
        app = create_app(settings=settings)

        with patch.object(app.state.resources, "startup", new_callable=AsyncMock):
            with patch.object(app.state.resources, "shutdown", new_callable=AsyncMock):
                with TestClient(app) as client:
                    # No auth header - should be rejected
                    response = client.post("/api/v1/query", json={
                        "question": "What is LangGraph?",
                    })
                    assert response.status_code == 401

    def test_health_is_public(self):
        from graphmind.api.main import create_app
        from graphmind.config import Settings
        from fastapi.testclient import TestClient

        settings = Settings(
            groq_api_key="test",
            gemini_api_key="test",
            neo4j_password="test",
            api_key="secret-key-123",
        )
        app = create_app(settings=settings)

        with patch.object(app.state.resources, "startup", new_callable=AsyncMock):
            with patch.object(app.state.resources, "shutdown", new_callable=AsyncMock):
                with TestClient(app) as client:
                    response = client.get("/api/v1/health")
                    assert response.status_code == 200
