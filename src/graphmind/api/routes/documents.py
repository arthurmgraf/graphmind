"""Paginated document and job listing endpoints."""
from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1")


class PaginationMeta(BaseModel):
    page: int = 1
    per_page: int = 20
    total: int = 0
    total_pages: int = 0


class PaginatedResponse(BaseModel):
    data: list[dict] = Field(default_factory=list)
    meta: PaginationMeta = Field(default_factory=PaginationMeta)


def _paginate(items: list[Any], page: int, per_page: int) -> PaginatedResponse:
    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = items[start:end]

    return PaginatedResponse(
        data=[item if isinstance(item, dict) else item for item in page_items],
        meta=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
        ),
    )


@router.get("/documents", response_model=PaginatedResponse)
async def list_documents(
    request: Request,
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=20, ge=1, le=100, description="Items per page"),
    tenant_id: str | None = Query(default=None, description="Filter by tenant"),
) -> PaginatedResponse:
    """List ingested documents with pagination."""
    resources = request.app.state.resources
    driver = resources.neo4j_driver

    if driver is None:
        return PaginatedResponse()

    try:
        query = "MATCH (d:Document) "
        params: dict[str, Any] = {}
        if tenant_id:
            query += "WHERE d.tenant_id = $tenant_id "
            params["tenant_id"] = tenant_id
        query += "RETURN d ORDER BY d.ingested_at DESC"

        async with driver.session() as session:
            result = await session.run(query, **params)
            documents = []
            async for record in result:
                node = record["d"]
                documents.append(dict(node))

        return _paginate(documents, page, per_page)

    except Exception as exc:
        logger.error("list_documents_failed", error=str(exc))
        return PaginatedResponse()


@router.get("/jobs", response_model=PaginatedResponse)
async def list_jobs(
    request: Request,
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status: str | None = Query(default=None, description="Filter by status"),
) -> PaginatedResponse:
    """List ingestion jobs with pagination and status filter."""
    resources = request.app.state.resources
    cost_tracker = resources.cost_tracker

    jobs = [
        {
            "job_id": f"job-{i}",
            "status": q.provider,
            "cost_usd": q.cost_usd,
            "tokens": q.total_tokens,
        }
        for i, q in enumerate(cost_tracker.queries)
    ]

    if status:
        jobs = [j for j in jobs if j.get("status") == status]

    return _paginate(jobs, page, per_page)
