from __future__ import annotations

import pytest

from graphmind.ingestion.chunker import SemanticChunker
from graphmind.ingestion.loaders import DocumentLoader


@pytest.mark.integration
class TestIngestionPipelineIntegration:
    def test_load_and_chunk_markdown(self):
        loader = DocumentLoader()
        chunker = SemanticChunker()

        md_content = (
            "# LangGraph\n\n"
            "LangGraph is a framework for building"
            " stateful apps.\n\n"
            "## Features\n\n"
            "It supports cyclic graphs and"
            " state management."
        )
        text = loader.load(md_content, "md")
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
            detail = "This is a detailed paragraph with information. "
            paragraphs.append(f"Section {i}: " + detail * 10)
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
