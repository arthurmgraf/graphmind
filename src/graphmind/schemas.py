"""Pydantic v2 schemas for the GraphMind platform.

All API request/response models, domain entities, and shared types.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


def _uuid() -> str:
    return str(uuid.uuid4())


class EntityType(StrEnum):
    CONCEPT = "concept"
    TECHNOLOGY = "technology"
    PERSON = "person"
    ORGANIZATION = "organization"
    FRAMEWORK = "framework"
    PATTERN = "pattern"
    OTHER = "other"


class Entity(BaseModel):
    id: str = Field(default_factory=_uuid)
    name: str = Field(..., min_length=1, max_length=512)
    type: EntityType
    description: str = Field(default="", max_length=4096)
    source_chunk_id: str = ""


class Relation(BaseModel):
    id: str = Field(default_factory=_uuid)
    source_id: str = Field(..., min_length=1)
    target_id: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1, max_length=128)
    description: str = Field(default="", max_length=4096)


class DocumentChunk(BaseModel):
    id: str = Field(default_factory=_uuid)
    document_id: str
    text: str = Field(..., min_length=1)
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
    content_hash: str = ""
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


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


# ---------------------------------------------------------------------------
# API request / response models
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=100)
    engine: str = "langgraph"
    session_id: str | None = Field(default=None, description="Session ID for conversation memory")
    tenant_id: str | None = Field(default=None, description="Tenant ID for multi-tenancy")
    experiment_id: str | None = Field(default=None, description="Experiment ID for A/B testing")
    stream: bool = Field(default=False, description="Enable SSE streaming")

    @field_validator("engine")
    @classmethod
    def _validate_engine(cls, v: str) -> str:
        allowed = {"langgraph", "crewai"}
        if v not in allowed:
            raise ValueError(f"engine must be one of {allowed}")
        return v


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    eval_score: float = 0.0
    sources_used: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    session_id: str | None = None
    experiment_variant: str | None = None


class IngestRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10 * 1024 * 1024)
    filename: str = Field(..., min_length=1, max_length=512)
    doc_type: str = "markdown"
    tenant_id: str | None = Field(default=None, description="Tenant ID for multi-tenancy")

    @field_validator("doc_type")
    @classmethod
    def _validate_doc_type(cls, v: str) -> str:
        allowed = {"pdf", "md", "markdown", "html", "txt", "py", "ts", "js"}
        if v not in allowed:
            raise ValueError(f"doc_type must be one of {sorted(allowed)}")
        return v


class IngestResponse(BaseModel):
    document_id: str
    chunks_created: int = 0
    entities_extracted: int = 0
    relations_extracted: int = 0
    duplicate: bool = False
    job_id: str | None = None


class JobStatus(BaseModel):
    job_id: str
    status: str = "pending"  # pending | running | completed | failed
    result: IngestResponse | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GraphStats(BaseModel):
    total_entities: int = 0
    total_relations: int = 0
    total_documents: int = 0
    total_chunks: int = 0
    entity_types: dict[str, int] = Field(default_factory=dict)
    relation_types: dict[str, int] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.2.0"
    services: dict[str, str] = Field(default_factory=dict)
    circuits: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Error response (matches errors.py envelope)
# ---------------------------------------------------------------------------


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str = ""
    details: dict | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail
