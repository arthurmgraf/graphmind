"""Role-Based Access Control (RBAC) for GraphMind API."""

from __future__ import annotations

import enum
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)


class Role(enum.StrEnum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class Permission(enum.StrEnum):
    QUERY = "query"
    QUERY_STREAM = "query:stream"
    INGEST = "ingest"
    DELETE_DOCUMENT = "delete:document"
    VIEW_STATS = "view:stats"
    VIEW_METRICS = "view:metrics"
    MANAGE_WEBHOOKS = "manage:webhooks"
    MANAGE_EXPERIMENTS = "manage:experiments"
    VIEW_COSTS = "view:costs"
    MANAGE_TENANTS = "manage:tenants"


_ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: set(Permission),
    Role.EDITOR: {
        Permission.QUERY,
        Permission.QUERY_STREAM,
        Permission.INGEST,
        Permission.VIEW_STATS,
        Permission.VIEW_METRICS,
        Permission.VIEW_COSTS,
        Permission.MANAGE_WEBHOOKS,
    },
    Role.VIEWER: {
        Permission.QUERY,
        Permission.QUERY_STREAM,
        Permission.VIEW_STATS,
    },
}


@dataclass
class APIKeyRecord:
    key_hash: str
    tenant_id: str
    role: Role
    description: str = ""
    active: bool = True
    rate_limit_rpm: int | None = None


class RBACRegistry:
    """In-memory RBAC registry for API key -> role -> permissions resolution."""

    def __init__(self) -> None:
        self._keys: dict[str, APIKeyRecord] = {}

    def register_key(
        self,
        key_hash: str,
        tenant_id: str,
        role: Role,
        description: str = "",
        rate_limit_rpm: int | None = None,
    ) -> APIKeyRecord:
        record = APIKeyRecord(
            key_hash=key_hash,
            tenant_id=tenant_id,
            role=role,
            description=description,
            rate_limit_rpm=rate_limit_rpm,
        )
        self._keys[key_hash] = record
        logger.info("api_key_registered", tenant=tenant_id, role=role.value)
        return record

    def resolve(self, key_hash: str) -> APIKeyRecord | None:
        record = self._keys.get(key_hash)
        if record is None or not record.active:
            return None
        return record

    def has_permission(self, key_hash: str, permission: Permission) -> bool:
        record = self.resolve(key_hash)
        if record is None:
            return False
        role_perms = _ROLE_PERMISSIONS.get(record.role, set())
        return permission in role_perms

    def get_permissions(self, role: Role) -> set[Permission]:
        return _ROLE_PERMISSIONS.get(role, set())

    def deactivate_key(self, key_hash: str) -> bool:
        record = self._keys.get(key_hash)
        if record is None:
            return False
        record.active = False
        logger.info("api_key_deactivated", tenant=record.tenant_id)
        return True

    def list_keys(self, tenant_id: str | None = None) -> list[APIKeyRecord]:
        keys = list(self._keys.values())
        if tenant_id:
            keys = [k for k in keys if k.tenant_id == tenant_id]
        return keys
