"""Integration tests for the ingestion pipeline.

Tests the pipeline with mocked external services.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.integration


class TestIngestionPipeline:
    @pytest.mark.asyncio
    async def test_pipeline_processes_markdown(self):
        """Test that the pipeline can process a markdown document."""
        from graphmind.ingestion.pipeline import IngestionPipeline

        mock_embedder = MagicMock()
        mock_embedder.embed_batch = AsyncMock(return_value=[[0.1] * 768])
        mock_embedder.close = AsyncMock()

        mock_vector = MagicMock()
        mock_vector.upsert_chunks = AsyncMock()

        pipeline = IngestionPipeline(
            embedder=mock_embedder,
            vector_retriever=mock_vector,
        )

        content = (
            "# Test Document\n\nThis is a test paragraph with enough content to be meaningful."
        )
        response = await pipeline.process(
            content=content,
            filename="test.md",
            doc_type="markdown",
        )

        assert response.chunks_created >= 1
        assert response.document_id != ""
