from __future__ import annotations

from graphmind.config import (
    AgentSettings,
    EmbeddingsSettings,
    GraphDBSettings,
    IngestionSettings,
    LLMProviderSettings,
    RetrievalSettings,
    Settings,
    VectorStoreSettings,
    get_settings,
)


class TestSettings:
    def test_get_settings_returns_settings_instance(self):
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_is_cached(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_default_llm_primary(self, settings):
        assert isinstance(settings.llm_primary, LLMProviderSettings)
        assert settings.llm_primary.provider == "groq"

    def test_default_embeddings(self, settings):
        assert isinstance(settings.embeddings, EmbeddingsSettings)
        assert settings.embeddings.provider == "ollama"
        assert settings.embeddings.dimensions == 768

    def test_default_vector_store(self, settings):
        assert isinstance(settings.vector_store, VectorStoreSettings)
        assert settings.vector_store.provider == "qdrant"
        assert settings.vector_store.port == 6333

    def test_default_graph_db(self, settings):
        assert isinstance(settings.graph_db, GraphDBSettings)
        assert settings.graph_db.provider == "neo4j"

    def test_default_retrieval(self, settings):
        assert isinstance(settings.retrieval, RetrievalSettings)
        assert settings.retrieval.vector_top_k == 20
        assert settings.retrieval.graph_hops == 2
        assert settings.retrieval.rrf_k == 60

    def test_default_agents(self, settings):
        assert isinstance(settings.agents, AgentSettings)
        assert settings.agents.max_retries == 2
        assert settings.agents.eval_threshold == 0.7

    def test_default_ingestion(self, settings):
        assert isinstance(settings.ingestion, IngestionSettings)
        assert settings.ingestion.chunk_size == 512
        assert settings.ingestion.chunk_overlap == 50
        assert "pdf" in settings.ingestion.supported_formats
        assert "md" in settings.ingestion.supported_formats
