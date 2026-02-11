from __future__ import annotations

from graphmind.security.rbac import (
    APIKeyRecord,
    Permission,
    RBACRegistry,
    Role,
)


class TestRoleEnum:
    def test_admin_value(self):
        assert Role.ADMIN.value == "admin"

    def test_editor_value(self):
        assert Role.EDITOR.value == "editor"

    def test_viewer_value(self):
        assert Role.VIEWER.value == "viewer"

    def test_role_is_string(self):
        assert isinstance(Role.ADMIN, str)
        assert Role.ADMIN == "admin"


class TestPermissionEnum:
    def test_query_value(self):
        assert Permission.QUERY.value == "query"

    def test_query_stream_value(self):
        assert Permission.QUERY_STREAM.value == "query:stream"

    def test_ingest_value(self):
        assert Permission.INGEST.value == "ingest"

    def test_delete_document_value(self):
        assert Permission.DELETE_DOCUMENT.value == "delete:document"

    def test_view_stats_value(self):
        assert Permission.VIEW_STATS.value == "view:stats"

    def test_view_metrics_value(self):
        assert Permission.VIEW_METRICS.value == "view:metrics"

    def test_manage_webhooks_value(self):
        assert Permission.MANAGE_WEBHOOKS.value == "manage:webhooks"

    def test_manage_experiments_value(self):
        assert Permission.MANAGE_EXPERIMENTS.value == "manage:experiments"

    def test_view_costs_value(self):
        assert Permission.VIEW_COSTS.value == "view:costs"

    def test_manage_tenants_value(self):
        assert Permission.MANAGE_TENANTS.value == "manage:tenants"


class TestAPIKeyRecord:
    def test_default_fields(self):
        record = APIKeyRecord(key_hash="abc123", tenant_id="t1", role=Role.VIEWER)
        assert record.active is True
        assert record.description == ""
        assert record.rate_limit_rpm is None


class TestRBACRegistryRegisterAndResolve:
    def test_register_key_returns_record(self):
        registry = RBACRegistry()
        record = registry.register_key("key1", "tenant-a", Role.ADMIN, description="Main key")
        assert isinstance(record, APIKeyRecord)
        assert record.key_hash == "key1"
        assert record.tenant_id == "tenant-a"
        assert record.role == Role.ADMIN
        assert record.description == "Main key"

    def test_resolve_returns_registered_key(self):
        registry = RBACRegistry()
        registry.register_key("key1", "tenant-a", Role.EDITOR)
        record = registry.resolve("key1")
        assert record is not None
        assert record.key_hash == "key1"
        assert record.role == Role.EDITOR

    def test_resolve_returns_none_for_unknown_key(self):
        registry = RBACRegistry()
        assert registry.resolve("nonexistent") is None

    def test_register_with_rate_limit(self):
        registry = RBACRegistry()
        record = registry.register_key("key1", "t1", Role.VIEWER, rate_limit_rpm=60)
        assert record.rate_limit_rpm == 60


class TestHasPermissionAdmin:
    def test_admin_has_all_permissions(self):
        registry = RBACRegistry()
        registry.register_key("admin-key", "t1", Role.ADMIN)
        for perm in Permission:
            assert registry.has_permission("admin-key", perm) is True

    def test_admin_has_manage_tenants(self):
        registry = RBACRegistry()
        registry.register_key("admin-key", "t1", Role.ADMIN)
        assert registry.has_permission("admin-key", Permission.MANAGE_TENANTS) is True

    def test_admin_has_manage_experiments(self):
        registry = RBACRegistry()
        registry.register_key("admin-key", "t1", Role.ADMIN)
        assert registry.has_permission("admin-key", Permission.MANAGE_EXPERIMENTS) is True


class TestHasPermissionViewer:
    def test_viewer_can_query(self):
        registry = RBACRegistry()
        registry.register_key("viewer-key", "t1", Role.VIEWER)
        assert registry.has_permission("viewer-key", Permission.QUERY) is True

    def test_viewer_can_query_stream(self):
        registry = RBACRegistry()
        registry.register_key("viewer-key", "t1", Role.VIEWER)
        assert registry.has_permission("viewer-key", Permission.QUERY_STREAM) is True

    def test_viewer_can_view_stats(self):
        registry = RBACRegistry()
        registry.register_key("viewer-key", "t1", Role.VIEWER)
        assert registry.has_permission("viewer-key", Permission.VIEW_STATS) is True

    def test_viewer_cannot_ingest(self):
        registry = RBACRegistry()
        registry.register_key("viewer-key", "t1", Role.VIEWER)
        assert registry.has_permission("viewer-key", Permission.INGEST) is False

    def test_viewer_cannot_delete_document(self):
        registry = RBACRegistry()
        registry.register_key("viewer-key", "t1", Role.VIEWER)
        assert registry.has_permission("viewer-key", Permission.DELETE_DOCUMENT) is False

    def test_viewer_cannot_manage_tenants(self):
        registry = RBACRegistry()
        registry.register_key("viewer-key", "t1", Role.VIEWER)
        assert registry.has_permission("viewer-key", Permission.MANAGE_TENANTS) is False

    def test_viewer_cannot_manage_experiments(self):
        registry = RBACRegistry()
        registry.register_key("viewer-key", "t1", Role.VIEWER)
        assert registry.has_permission("viewer-key", Permission.MANAGE_EXPERIMENTS) is False

    def test_viewer_cannot_view_costs(self):
        registry = RBACRegistry()
        registry.register_key("viewer-key", "t1", Role.VIEWER)
        assert registry.has_permission("viewer-key", Permission.VIEW_COSTS) is False


class TestHasPermissionEditor:
    def test_editor_can_query(self):
        registry = RBACRegistry()
        registry.register_key("editor-key", "t1", Role.EDITOR)
        assert registry.has_permission("editor-key", Permission.QUERY) is True

    def test_editor_can_ingest(self):
        registry = RBACRegistry()
        registry.register_key("editor-key", "t1", Role.EDITOR)
        assert registry.has_permission("editor-key", Permission.INGEST) is True

    def test_editor_can_view_costs(self):
        registry = RBACRegistry()
        registry.register_key("editor-key", "t1", Role.EDITOR)
        assert registry.has_permission("editor-key", Permission.VIEW_COSTS) is True

    def test_editor_can_manage_webhooks(self):
        registry = RBACRegistry()
        registry.register_key("editor-key", "t1", Role.EDITOR)
        assert registry.has_permission("editor-key", Permission.MANAGE_WEBHOOKS) is True

    def test_editor_cannot_delete_document(self):
        registry = RBACRegistry()
        registry.register_key("editor-key", "t1", Role.EDITOR)
        assert registry.has_permission("editor-key", Permission.DELETE_DOCUMENT) is False

    def test_editor_cannot_manage_tenants(self):
        registry = RBACRegistry()
        registry.register_key("editor-key", "t1", Role.EDITOR)
        assert registry.has_permission("editor-key", Permission.MANAGE_TENANTS) is False

    def test_editor_cannot_manage_experiments(self):
        registry = RBACRegistry()
        registry.register_key("editor-key", "t1", Role.EDITOR)
        assert registry.has_permission("editor-key", Permission.MANAGE_EXPERIMENTS) is False


class TestDeactivateKey:
    def test_deactivate_makes_resolve_return_none(self):
        registry = RBACRegistry()
        registry.register_key("key1", "t1", Role.ADMIN)
        assert registry.resolve("key1") is not None

        result = registry.deactivate_key("key1")
        assert result is True
        assert registry.resolve("key1") is None

    def test_deactivate_makes_has_permission_false(self):
        registry = RBACRegistry()
        registry.register_key("key1", "t1", Role.ADMIN)
        registry.deactivate_key("key1")
        assert registry.has_permission("key1", Permission.QUERY) is False

    def test_deactivate_nonexistent_returns_false(self):
        registry = RBACRegistry()
        assert registry.deactivate_key("nonexistent") is False


class TestListKeys:
    def test_list_all_keys(self):
        registry = RBACRegistry()
        registry.register_key("k1", "t1", Role.ADMIN)
        registry.register_key("k2", "t2", Role.VIEWER)
        registry.register_key("k3", "t1", Role.EDITOR)
        keys = registry.list_keys()
        assert len(keys) == 3

    def test_list_keys_with_tenant_filter(self):
        registry = RBACRegistry()
        registry.register_key("k1", "t1", Role.ADMIN)
        registry.register_key("k2", "t2", Role.VIEWER)
        registry.register_key("k3", "t1", Role.EDITOR)
        keys = registry.list_keys(tenant_id="t1")
        assert len(keys) == 2
        assert all(k.tenant_id == "t1" for k in keys)

    def test_list_keys_empty_registry(self):
        registry = RBACRegistry()
        assert registry.list_keys() == []

    def test_list_keys_tenant_with_no_match(self):
        registry = RBACRegistry()
        registry.register_key("k1", "t1", Role.ADMIN)
        assert registry.list_keys(tenant_id="t99") == []


class TestGetPermissions:
    def test_get_admin_permissions_includes_all(self):
        registry = RBACRegistry()
        perms = registry.get_permissions(Role.ADMIN)
        assert perms == set(Permission)

    def test_get_viewer_permissions_is_subset(self):
        registry = RBACRegistry()
        viewer_perms = registry.get_permissions(Role.VIEWER)
        admin_perms = registry.get_permissions(Role.ADMIN)
        assert viewer_perms.issubset(admin_perms)
        assert len(viewer_perms) < len(admin_perms)
