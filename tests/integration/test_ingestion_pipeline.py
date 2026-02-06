from __future__ import annotations

import pytest

from graphmind.ingestion.loaders import DocumentLoader
from graphmind.ingestion.chunker import SemanticChunker


@pytest.mark.integration
class TestIngestionPipelineIntegration:
    def test_load_and_chunk_markdown(self):
        loader = DocumentLoader()
        chunker = SemanticChunker()

        text = loader.load("# LangGraph\n\nLangGraph is a framework for building stateful apps.\n\n## Features\n\nIt supports cyclic graphs and state management.", "md")
        assert "LangGraph" in text

        chunks = chunker.chunk(text, "test-doc")
        assert len(chunks) >= 1
        assert all(c.document_id == "test-doc" for c in chunks)
        assert all(c.text for c in chunks)

    def test_load_and_chunk_long_document(self):
        loader = DocumentLoader()
        chunker = SemanticChunker()

        paragraphs = []
        for i in range(20):
            paragraphs.append(f"Section {i}: " + "This is a detailed paragraph with information. " * 10)
        long_text = "\n\n".join(paragraphs)

        text = loader.load(long_text, "txt")
        chunks = chunker.chunk(text, "long-doc")

        assert len(chunks) > 1
        reconstructed = " ".join(c.text for c in chunks)
        assert "Section 0" in reconstructed
        assert "Section 19" in reconstructed

    def test_code_loading_and_chunking(self):
        loader = DocumentLoader()
        chunker = SemanticChunker()

        code = "def hello():\n    return 'world'"
        text = loader.load(code, "py")
        assert "```python" in text

        chunks = chunker.chunk(text, "code-doc")
        assert len(chunks) >= 1
