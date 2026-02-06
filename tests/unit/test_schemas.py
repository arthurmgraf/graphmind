from __future__ import annotations

from graphmind.schemas import (
    Citation,
    DocumentChunk,
    DocumentMetadata,
    Entity,
    EntityType,
    GraphStats,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    Relation,
    RetrievalResult,
)


class TestEntity:
    def test_creates_with_auto_id(self):
        entity = Entity(name="LangGraph", type=EntityType.FRAMEWORK)
        assert entity.id
        assert entity.name == "LangGraph"
        assert entity.type == EntityType.FRAMEWORK

    def test_entity_types_are_strings(self):
        assert EntityType.CONCEPT.value == "concept"
        assert EntityType.TECHNOLOGY.value == "technology"


class TestRelation:
    def test_creates_with_auto_id(self):
        rel = Relation(source_id="a", target_id="b", type="uses")
        assert rel.id
        assert rel.source_id == "a"
        assert rel.target_id == "b"


class TestDocumentChunk:
    def test_creates_with_defaults(self):
        chunk = DocumentChunk(document_id="doc-1", text="hello")
        assert chunk.id
        assert chunk.index == 0
        assert chunk.metadata == {}
        assert chunk.entity_ids == []


class TestDocumentMetadata:
    def test_creates_with_defaults(self):
        meta = DocumentMetadata(filename="test.md", format="md")
        assert meta.filename == "test.md"
        assert meta.chunk_count == 0


class TestRetrievalResult:
    def test_creates_with_required_fields(self):
        result = RetrievalResult(id="r1", text="some text")
        assert result.score == 0.0
        assert result.source == ""
        assert result.entity_id is None


class TestCitation:
    def test_creates(self):
        c = Citation(document_id="d1", chunk_id="c1", text_snippet="snippet")
        assert c.source == ""


class TestQueryRequestResponse:
    def test_query_request_defaults(self):
        req = QueryRequest(question="What is LangGraph?")
        assert req.top_k == 10

    def test_query_response_defaults(self):
        resp = QueryResponse(answer="It is a framework")
        assert resp.eval_score == 0.0
        assert resp.citations == []


class TestIngestRequestResponse:
    def test_ingest_request_defaults(self):
        req = IngestRequest(content="data", filename="test.md")
        assert req.doc_type == "markdown"

    def test_ingest_response_defaults(self):
        resp = IngestResponse(document_id="d1")
        assert resp.chunks_created == 0


class TestGraphStats:
    def test_defaults(self):
        stats = GraphStats()
        assert stats.total_entities == 0
        assert stats.entity_types == {}


class TestHealthResponse:
    def test_defaults(self):
        hr = HealthResponse()
        assert hr.status == "ok"
        assert hr.version == "0.1.0"
