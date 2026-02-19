"""Prompt versioning registry with YAML-based configuration."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_PROMPTS_DIR = _PROJECT_ROOT / "config" / "prompts"


class PromptVersion:
    def __init__(self, version: str, system: str, active: bool = False) -> None:
        self.version = version
        self.system = system
        self.active = active


class PromptRegistry:
    def __init__(self, prompts_dir: Path | None = None) -> None:
        self._dir = prompts_dir or _PROMPTS_DIR
        self._prompts: dict[str, dict[str, PromptVersion]] = {}
        self._load_all()

    def _load_all(self) -> None:
        if not self._dir.exists():
            logger.info("Prompts directory %s not found, using defaults", self._dir)
            return
        for path in self._dir.glob("*.yaml"):
            name = path.stem
            try:
                with open(path) as f:
                    data = yaml.safe_load(f) or {}
                versions = data.get("versions", {})
                self._prompts[name] = {}
                for ver_name, ver_data in versions.items():
                    self._prompts[name][ver_name] = PromptVersion(
                        version=ver_name,
                        system=ver_data.get("system", ""),
                        active=ver_data.get("active", False),
                    )
            except Exception as exc:
                logger.error("Failed to load prompt %s: %s", name, exc)

    def get(self, name: str, version: str | None = None) -> str:
        if name not in self._prompts:
            logger.warning("Prompt %s not found in registry", name)
            return ""
        versions = self._prompts[name]
        if version and version in versions:
            return versions[version].system
        for v in versions.values():
            if v.active:
                return v.system
        if versions:
            return next(iter(versions.values())).system
        return ""

    def get_active_version(self, name: str) -> str:
        if name not in self._prompts:
            return "unknown"
        for v in self._prompts[name].values():
            if v.active:
                return v.version
        return "unknown"

    def list_prompts(self) -> dict[str, list[dict]]:
        result: dict[str, list[dict]] = {}
        for name, versions in self._prompts.items():
            result[name] = [
                {"version": v.version, "active": v.active, "preview": v.system[:100]}
                for v in versions.values()
            ]
        return result

    def activate(self, name: str, version: str) -> bool:
        if name not in self._prompts or version not in self._prompts[name]:
            return False
        for v in self._prompts[name].values():
            v.active = False
        self._prompts[name][version].active = True
        return True


_registry: PromptRegistry | None = None


def get_prompt_registry() -> PromptRegistry:
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry
