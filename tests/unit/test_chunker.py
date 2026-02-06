from __future__ import annotations

from graphmind.ingestion.chunker import SemanticChunker


class TestSemanticChunker:
    def test_single_short_text(self):
        chunker = SemanticChunker()
        chunks = chunker.chunk("Hello world.", "doc-1")
        assert len(chunks) == 1
        assert chunks[0].text == "Hello world."
        assert chunks[0].document_id == "doc-1"
        assert chunks[0].index == 0

    def test_multiple_paragraphs(self):
        chunker = SemanticChunker()
        text = "Paragraph one. " * 20 + "\n\n" + "Paragraph two. " * 20
        chunks = chunker.chunk(text, "doc-2")
        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.document_id == "doc-2"
            assert chunk.text

    def test_empty_text_returns_empty(self):
        chunker = SemanticChunker()
        chunks = chunker.chunk("", "doc-3")
        assert chunks == []

    def test_long_text_is_split(self):
        chunker = SemanticChunker()
        text = "A" * 2000
        chunks = chunker.chunk(text, "doc-4")
        assert len(chunks) >= 2

    def test_chunk_metadata_has_required_fields(self):
        chunker = SemanticChunker()
        chunks = chunker.chunk("Some text for chunking.", "doc-5")
        assert len(chunks) == 1
        meta = chunks[0].metadata
        assert "char_start" in meta
        assert "char_end" in meta
        assert "chunk_index" in meta
        assert "total_chunks" in meta

    def test_chunks_have_sequential_indices(self):
        chunker = SemanticChunker()
        text = ("Sentence. " * 100 + "\n\n") * 5
        chunks = chunker.chunk(text, "doc-6")
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_chunk_ids_are_unique(self):
        chunker = SemanticChunker()
        text = ("Paragraph content. " * 50 + "\n\n") * 3
        chunks = chunker.chunk(text, "doc-7")
        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids))
