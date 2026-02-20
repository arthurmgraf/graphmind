"""Tests for route-level permission enforcement."""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock

from starlette.testclient import TestClient

from graphmind.api.main import create_app
from graphmind.config import Settings
from graphmind.security.rbac import Role


def _make_app_with_role(role: Role, api_key: str = "admin-key"):
    """Create a test app and register a key with the given role."""
    s = Settings()
    s.api_key = api_key

    app = create_app(settings=s)

    resources = MagicMock()
    resources.settings = s
    resources.startup = AsyncMock()
    resources.shutdown = AsyncMock()
    resources.llm_router = None
    resources.neo4j_driver = None
    resources.qdrant_client = None
    resources.hybrid_retriever = None
    resources.embedder = None
    resources.vector_retriever = None
    resources.cost_tracker = MagicMock()
    resources.metrics = MagicMock()
    app.state.resources = resources

    # Register a key with the requested role
    test_key = f"test-{role.value}-key"
    key_hash = hashlib.sha256(test_key.encode()).hexdigest()
    app.state.rbac_registry.register_key(
        key_hash=key_hash,
        tenant_id="test-tenant",
        role=role,
    )

    client = TestClient(app, raise_server_exceptions=False)
    return client, test_key


class TestViewerPermissions:
    def test_viewer_can_query(self):
        """Viewer role should be able to POST /query."""
        client, key = _make_app_with_role(Role.VIEWER)
        resp = client.post(
            "/api/v1/query",
            json={"question": "What is LangGraph?"},
            headers={"Authorization": f"Bearer {key}"},
        )
        # Should not be 403 — viewers can query (may be 500 due to missing pipeline)
        assert resp.status_code != 403

    def test_viewer_cannot_ingest(self):
        """Viewer role should NOT be able to POST /ingest."""
        client, key = _make_app_with_role(Role.VIEWER)
        resp = client.post(
            "/api/v1/ingest",
            json={"content": "test content", "filename": "test.md"},
            headers={"Authorization": f"Bearer {key}"},
        )
        assert resp.status_code == 403

    def test_viewer_cannot_view_metrics(self):
        """Viewer role should NOT be able to GET /metrics."""
        client, key = _make_app_with_role(Role.VIEWER)
        resp = client.get(
            "/metrics",
            headers={"Authorization": f"Bearer {key}"},
        )
        assert resp.status_code == 403


class TestEditorPermissions:
    def test_editor_can_ingest(self):
        """Editor role should be able to POST /ingest."""
        client, key = _make_app_with_role(Role.EDITOR)
        resp = client.post(
            "/api/v1/ingest",
            json={"content": "test content", "filename": "test.md"},
            headers={"Authorization": f"Bearer {key}"},
        )
        # Should not be 403 — editors can ingest
        assert resp.status_code != 403


class TestAdminPermissions:
    def test_admin_can_view_metrics(self):
        """Admin role should be able to GET /metrics."""
        client, key = _make_app_with_role(Role.ADMIN)
        resp = client.get(
            "/metrics",
            headers={"Authorization": f"Bearer {key}"},
        )
        assert resp.status_code != 403


class TestInputValidation:
    def test_invalid_doc_type_rejected(self):
        """Unsupported doc_type should be rejected with 400."""
        client, key = _make_app_with_role(Role.ADMIN)
        resp = client.post(
            "/api/v1/ingest",
            json={"content": "test content", "filename": "test.exe", "doc_type": "exe"},
            headers={"Authorization": f"Bearer {key}"},
        )
        assert resp.status_code in (400, 422)  # Pydantic validation returns 422


class TestHealthSanitization:
    def test_health_no_exception_details(self):
        """Health endpoint should never include exception details."""
        client, key = _make_app_with_role(Role.ADMIN)
        resp = client.get("/api/v1/health")
        body = resp.json()
        for service_status in body.get("services", {}).values():
            assert "Error" not in service_status
            assert "Traceback" not in service_status
            assert "error:" not in service_status
