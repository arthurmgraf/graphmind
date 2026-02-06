from __future__ import annotations

from pathlib import Path
from functools import lru_cache
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config" / "settings.yaml"


def _load_yaml() -> dict[str, Any]:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


_yaml = _load_yaml()


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
    supported_formats: list[str] = Field(
        default=["pdf", "md", "html", "txt", "py", "ts", "js"]
    )


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
    agents: AgentSettings = Field(
        default_factory=lambda: AgentSettings(**_yaml.get("agents", {}))
    )
    ingestion: IngestionSettings = Field(
        default_factory=lambda: IngestionSettings(**_yaml.get("ingestion", {}))
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
