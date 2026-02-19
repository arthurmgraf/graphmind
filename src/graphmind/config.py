from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Self

import structlog
import yaml
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

logger = structlog.get_logger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_DIR = _PROJECT_ROOT / "config"
_CONFIG_PATH = _CONFIG_DIR / "settings.yaml"


def _load_yaml() -> dict[str, Any]:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


def _load_env_profile() -> dict[str, Any]:
    """Load environment-specific YAML profile (dev / staging / production).

    Set ``GRAPHMIND_ENV`` to one of ``dev``, ``staging``, ``production``
    (defaults to ``dev``).  The profile is deep-merged on top of the base
    settings YAML so that per-environment overrides take precedence.
    """
    env = os.getenv("GRAPHMIND_ENV", "dev").lower()
    profile_path = _CONFIG_DIR / "environments" / f"{env}.yaml"
    if profile_path.exists():
        with open(profile_path) as f:
            data = yaml.safe_load(f) or {}
        logger.info("Loaded environment profile: %s (%s)", env, profile_path)
        return data
    logger.debug("No environment profile found for '%s'", env)
    return {}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base* (mutates *base*)."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


_yaml = _deep_merge(_load_yaml(), _load_env_profile())


class LLMProviderSettings(BaseSettings):
    provider: str = "groq"
    model: str = "llama-3.3-70b-versatile"
    temperature: float = 0.1
    max_tokens: int = 4096
    base_url: str | None = None


class EmbeddingsSettings(BaseSettings):
    provider: str = "ollama"
    model: str = "nomic-embed-text"
    base_url: str = "http://localhost:11434"
    dimensions: int = 768


class VectorStoreSettings(BaseSettings):
    provider: str = "qdrant"
    host: str = "localhost"
    port: int = 6333
    collection: str = "graphmind_docs"


class GraphDBSettings(BaseSettings):
    provider: str = "neo4j"
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    database: str = "neo4j"


class RetrievalSettings(BaseSettings):
    vector_top_k: int = 20
    graph_hops: int = 2
    rrf_k: int = 60
    final_top_n: int = 10


class AgentSettings(BaseSettings):
    max_retries: int = 2
    eval_threshold: float = 0.7


class IngestionSettings(BaseSettings):
    chunk_size: int = 512
    chunk_overlap: int = 50
    max_document_size_bytes: int = 10 * 1024 * 1024  # 10 MB
    max_concurrent_chunks: int = 10
    supported_formats: list[str] = Field(default=["pdf", "md", "html", "txt", "py", "ts", "js"])


class Settings(BaseSettings):
    model_config = {"env_prefix": "", "env_nested_delimiter": "__", "extra": "ignore"}

    groq_api_key: str = ""
    gemini_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = ""
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "graphmind"
    postgres_user: str = "graphmind"
    postgres_password: str = ""
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    api_key: str = ""
    cors_origins: list[str] = Field(default=["http://localhost:8501", "http://localhost:3000"])
    rate_limit_rpm: int = 60

    llm_primary: LLMProviderSettings = Field(
        default_factory=lambda: LLMProviderSettings(**_yaml.get("llm", {}).get("primary", {}))
    )
    llm_secondary: LLMProviderSettings = Field(
        default_factory=lambda: LLMProviderSettings(**_yaml.get("llm", {}).get("secondary", {}))
    )
    llm_fallback: LLMProviderSettings = Field(
        default_factory=lambda: LLMProviderSettings(**_yaml.get("llm", {}).get("fallback", {}))
    )
    embeddings: EmbeddingsSettings = Field(
        default_factory=lambda: EmbeddingsSettings(**_yaml.get("embeddings", {}))
    )
    vector_store: VectorStoreSettings = Field(
        default_factory=lambda: VectorStoreSettings(**_yaml.get("vector_store", {}))
    )
    graph_db: GraphDBSettings = Field(
        default_factory=lambda: GraphDBSettings(**_yaml.get("graph_db", {}))
    )
    retrieval: RetrievalSettings = Field(
        default_factory=lambda: RetrievalSettings(**_yaml.get("retrieval", {}))
    )
    agents: AgentSettings = Field(default_factory=lambda: AgentSettings(**_yaml.get("agents", {})))
    ingestion: IngestionSettings = Field(
        default_factory=lambda: IngestionSettings(**_yaml.get("ingestion", {}))
    )

    @model_validator(mode="after")
    def _validate_required_secrets(self) -> Self:
        if not self.groq_api_key and not self.gemini_api_key:
            logger.warning(
                "Neither GROQ_API_KEY nor GEMINI_API_KEY is set; "
                "only local Ollama fallback will be available"
            )
        if not self.neo4j_password:
            logger.warning("NEO4J_PASSWORD is not set; graph operations will fail")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
