from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from graphmind.api.routes.health import router as health_router
from graphmind.api.routes.ingest import router as ingest_router
from graphmind.api.routes.query import router as query_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("GraphMind API starting up")
    yield
    logger.info("GraphMind API shutting down")


app = FastAPI(
    title="GraphMind API",
    description="Autonomous Knowledge Agent Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(query_router)


def run() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000)
