from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ["GRAPHMIND_ENV"] = "test"  # Prevents loading dev/staging/prod profile overlays


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from graphmind.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings():
    from graphmind.config import get_settings

    return get_settings()


@pytest.fixture
def mock_llm_response():
    msg = MagicMock()
    msg.content = "Test LLM response"
    return msg


@pytest.fixture
def mock_router(mock_llm_response):
    router = MagicMock()
    router.ainvoke = AsyncMock(return_value=mock_llm_response)
    router.invoke = MagicMock(return_value=mock_llm_response)
    router.get_primary = MagicMock()
    return router


@pytest.fixture
def sample_chunks():
    from graphmind.schemas import DocumentChunk

    return [
        DocumentChunk(
            id="chunk-1",
            document_id="doc-1",
            text="LangGraph is a framework for building stateful, multi-actor applications.",
            index=0,
        ),
        DocumentChunk(
            id="chunk-2",
            document_id="doc-1",
            text="Neo4j is a native graph database that stores data as nodes and relationships.",
            index=1,
        ),
    ]


@pytest.fixture
def sample_entities():
    from graphmind.schemas import Entity, EntityType

    return [
        Entity(id="ent-1", name="LangGraph", type=EntityType.FRAMEWORK, description="Multi-actor framework"),
        Entity(id="ent-2", name="Neo4j", type=EntityType.TECHNOLOGY, description="Graph database"),
        Entity(id="ent-3", name="LangChain", type=EntityType.FRAMEWORK, description="LLM framework"),
    ]


@pytest.fixture
def sample_relations():
    from graphmind.schemas import Relation

    return [
        Relation(id="rel-1", source_id="ent-1", target_id="ent-3", type="extends", description="LangGraph extends LangChain"),
    ]


@pytest.fixture
def sample_retrieval_results():
    from graphmind.schemas import RetrievalResult

    return [
        RetrievalResult(id="r1", text="LangGraph doc", score=0.9, source="vector", entity_id="ent-1"),
        RetrievalResult(id="r2", text="Neo4j doc", score=0.8, source="vector", entity_id="ent-2"),
        RetrievalResult(id="r3", text="Graph expansion", score=0.7, source="graph", entity_id="ent-1"),
    ]
