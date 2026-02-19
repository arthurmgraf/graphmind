from __future__ import annotations

import asyncio
import hashlib
import uuid
from typing import Any

import structlog

from graphmind.config import get_settings
from graphmind.ingestion.chunker import SemanticChunker
from graphmind.ingestion.loaders import DocumentLoader
from graphmind.schemas import (
    DocumentChunk,
    DocumentMetadata,
    Entity,
    IngestResponse,
    Relation,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class IngestionPipeline:
    def __init__(
        self,
        loader: DocumentLoader | None = None,
        chunker: SemanticChunker | None = None,
        entity_extractor: Any = None,
        relation_extractor: Any = None,
        graph_builder: Any = None,
        embedder: Any = None,
        vector_retriever: Any = None,
    ) -> None:
        self._settings = get_settings()
        self._loader = loader or DocumentLoader()
        self._chunker = chunker or SemanticChunker()
        self._entity_extractor = entity_extractor
        self._relation_extractor = relation_extractor
        self._graph_builder = graph_builder
        self._embedder = embedder
        self._vector_retriever = vector_retriever
        self._semaphore = asyncio.Semaphore(self._settings.ingestion.max_concurrent_chunks)

    async def process(self, content: str, filename: str, doc_type: str) -> IngestResponse:
        content_size = len(content.encode("utf-8"))
        max_size = self._settings.ingestion.max_document_size_bytes
        if content_size > max_size:
            raise ValueError(f"Document exceeds maximum size ({content_size} > {max_size} bytes)")

        doc_hash = _content_hash(content)
        doc_id = str(uuid.uuid4())
        log = logger.bind(
            document_id=doc_id, filename=filename, doc_type=doc_type, content_hash=doc_hash
        )
        log.info("ingestion_started")

        text = self._load(content, doc_type, log)
        chunks = self._chunk(text, doc_id, log)

        # Chunk-level near-duplicate detection
        from graphmind.ingestion.dedup import ChunkDeduplicator

        deduplicator = ChunkDeduplicator()
        dedup_result = deduplicator.deduplicate([c.text for c in chunks])
        if dedup_result.duplicate_indices:
            dup_set = set(dedup_result.duplicate_indices)
            chunks = [c for i, c in enumerate(chunks) if i not in dup_set]
            log.info(
                "chunks_deduplicated",
                removed=dedup_result.duplicate_chunks,
                remaining=len(chunks),
            )

        all_entities: list[Entity] = []
        all_relations: list[Relation] = []

        # Bounded concurrency for chunk processing (LLM calls)
        async def _bounded_process(chunk: DocumentChunk):
            async with self._semaphore:
                return await self._process_chunk(chunk, log)

        results = await asyncio.gather(
            *[_bounded_process(c) for c in chunks], return_exceptions=True
        )

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                log.error(
                    "chunk_processing_failed",
                    chunk_index=i,
                    error=str(result),
                )
                continue
            entities, relations = result  # type: ignore[misc]
            all_entities.extend(entities)
            all_relations.extend(relations)
            chunks[i].entity_ids = [e.id for e in entities]

        await self._store_vectors(chunks, log)
        await self._store_graph(all_entities, all_relations, log)
        await self._store_metadata(
            doc_id, filename, doc_type, content, doc_hash, chunks, all_entities, all_relations, log
        )

        log.info(
            "ingestion_completed",
            chunks_created=len(chunks),
            entities_extracted=len(all_entities),
            relations_extracted=len(all_relations),
        )

        return IngestResponse(
            document_id=doc_id,
            chunks_created=len(chunks),
            entities_extracted=len(all_entities),
            relations_extracted=len(all_relations),
        )

    def _load(self, content: str, doc_type: str, log: structlog.stdlib.BoundLogger) -> str:
        log.info("loading_document")
        return self._loader.load(content, doc_type)

    def _chunk(
        self, text: str, doc_id: str, log: structlog.stdlib.BoundLogger
    ) -> list[DocumentChunk]:
        log.info("chunking_document")
        chunks = self._chunker.chunk(text, doc_id)
        log.info("chunking_completed", chunk_count=len(chunks))
        return chunks

    async def _process_chunk(
        self, chunk: DocumentChunk, log: structlog.stdlib.BoundLogger
    ) -> tuple[list[Entity], list[Relation]]:
        entities: list[Entity] = []
        relations: list[Relation] = []

        try:
            entities = await self._extract_entities(chunk, log)
        except Exception as exc:
            log.error(
                "entity_extraction_failed",
                chunk_id=chunk.id,
                chunk_index=chunk.index,
                error=str(exc),
            )

        try:
            relations = await self._extract_relations(chunk, entities, log)
        except Exception as exc:
            log.error(
                "relation_extraction_failed",
                chunk_id=chunk.id,
                chunk_index=chunk.index,
                error=str(exc),
            )

        return entities, relations

    async def _extract_entities(
        self, chunk: DocumentChunk, log: structlog.stdlib.BoundLogger
    ) -> list[Entity]:
        if self._entity_extractor is None:
            log.debug("entity_extractor_not_configured", chunk_id=chunk.id)
            return []
        return await self._entity_extractor.extract(chunk)

    async def _extract_relations(
        self,
        chunk: DocumentChunk,
        entities: list[Entity],
        log: structlog.stdlib.BoundLogger,
    ) -> list[Relation]:
        if self._relation_extractor is None:
            log.debug("relation_extractor_not_configured", chunk_id=chunk.id)
            return []
        return await self._relation_extractor.extract(chunk, entities)

    async def _store_vectors(
        self, chunks: list[DocumentChunk], log: structlog.stdlib.BoundLogger
    ) -> None:
        if self._embedder is None or self._vector_retriever is None:
            log.debug("vector_storage_not_configured")
            return

        try:
            embeddings = await self._embedder.embed_batch([c.text for c in chunks])
            await self._vector_retriever.upsert(chunks, embeddings)
            log.info("vectors_stored", count=len(chunks))
        except Exception as exc:
            log.error("vector_storage_failed", error=str(exc))

    async def _store_graph(
        self,
        entities: list[Entity],
        relations: list[Relation],
        log: structlog.stdlib.BoundLogger,
    ) -> None:
        if self._graph_builder is None:
            log.debug("graph_builder_not_configured")
            return

        try:
            await self._graph_builder.add_entities(entities)
            await self._graph_builder.add_relations(relations)
            log.info(
                "graph_stored",
                entity_count=len(entities),
                relation_count=len(relations),
            )
        except Exception as exc:
            log.error("graph_storage_failed", error=str(exc))

    async def _store_metadata(
        self,
        doc_id: str,
        filename: str,
        doc_type: str,
        content: str,
        content_hash: str,
        chunks: list[DocumentChunk],
        entities: list[Entity],
        relations: list[Relation],
        log: structlog.stdlib.BoundLogger,
    ) -> None:
        metadata = DocumentMetadata(
            id=doc_id,
            filename=filename,
            format=doc_type,
            size_bytes=len(content.encode("utf-8")),
            chunk_count=len(chunks),
            entity_count=len(entities),
            relation_count=len(relations),
            content_hash=content_hash,
        )
        log.info("metadata_stored", metadata_id=metadata.id)


async def _async_cli_entrypoint(file_path: str, doc_type: str) -> None:
    pipeline = IngestionPipeline()
    response = await pipeline.process(
        content=file_path,
        filename=file_path,
        doc_type=doc_type,
    )
    logger.info(
        "cli_ingestion_result",
        document_id=response.document_id,
        chunks=response.chunks_created,
        entities=response.entities_extracted,
        relations=response.relations_extracted,
    )


def cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="graphmind-ingest",
        description="Ingest a document into the GraphMind knowledge base",
    )
    parser.add_argument(
        "file",
        type=str,
        help="Path to the file to ingest",
    )
    parser.add_argument(
        "--type",
        type=str,
        default="md",
        dest="doc_type",
        choices=get_settings().ingestion.supported_formats,
        help="Document format (default: md)",
    )

    args = parser.parse_args()
    asyncio.run(_async_cli_entrypoint(args.file, args.doc_type))
