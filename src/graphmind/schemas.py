from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


def _uuid() -> str:
    return str(uuid.uuid4())


class EntityType(str, Enum):
    CONCEPT = "concept"
    TECHNOLOGY = "technology"
    PERSON = "person"
    ORGANIZATION = "organization"
    FRAMEWORK = "framework"
    PATTERN = "pattern"
    OTHER = "other"


class Entity(BaseModel):
    id: str = Field(default_factory=_uuid)
    name: str
    type: EntityType
    description: str = ""
    source_chunk_id: str = ""


class Relation(BaseModel):
    id: str = Field(default_factory=_uuid)
    source_id: str
    target_id: str
    type: str
    description: str = ""


class DocumentChunk(BaseModel):
    id: str = Field(default_factory=_uuid)
    document_id: str
    text: str
    index: int = 0
    metadata: dict = Field(default_factory=dict)
    entity_ids: list[str] = Field(default_factory=list)


class DocumentMetadata(BaseModel):
    id: str = Field(default_factory=_uuid)
    filename: str
    format: str
    size_bytes: int = 0
    chunk_count: int = 0
    entity_count: int = 0
    relation_count: int = 0
    ingested_at: datetime = Field(default_factory=datetime.utcnow)


class RetrievalResult(BaseModel):
    id: str
    text: str
    score: float = 0.0
    source: str = ""
    entity_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class Citation(BaseModel):
    document_id: str
    chunk_id: str
    text_snippet: str
    source: str = ""


class QueryRequest(BaseModel):
    question: str
    top_k: int = 10


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    eval_score: float = 0.0
    sources_used: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0


class IngestRequest(BaseModel):
    content: str
    filename: str
    doc_type: str = "markdown"


class IngestResponse(BaseModel):
    document_id: str
    chunks_created: int = 0
    entities_extracted: int = 0
    relations_extracted: int = 0


class GraphStats(BaseModel):
    total_entities: int = 0
    total_relations: int = 0
    total_documents: int = 0
    total_chunks: int = 0
    entity_types: dict[str, int] = Field(default_factory=dict)
    relation_types: dict[str, int] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    services: dict[str, str] = Field(default_factory=dict)
