from __future__ import annotations

import re
import uuid

from graphmind.config import get_settings
from graphmind.schemas import DocumentChunk

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


class SemanticChunker:
    def __init__(self) -> None:
        settings = get_settings()
        self._chunk_size: int = settings.ingestion.chunk_size
        self._chunk_overlap: int = settings.ingestion.chunk_overlap

    def chunk(self, text: str, doc_id: str) -> list[DocumentChunk]:
        paragraphs = self._split_paragraphs(text)
        raw_chunks = self._merge_into_chunks(paragraphs)
        return self._build_document_chunks(raw_chunks, doc_id)

    def _split_paragraphs(self, text: str) -> list[str]:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        result: list[str] = []
        for paragraph in paragraphs:
            if len(paragraph) <= self._chunk_size:
                result.append(paragraph)
            else:
                result.extend(self._split_into_sentences(paragraph))
        return result

    def _split_into_sentences(self, text: str) -> list[str]:
        sentences = _SENTENCE_BOUNDARY.split(text)
        merged: list[str] = []
        current = ""

        for sentence in sentences:
            candidate = f"{current} {sentence}".strip() if current else sentence
            if len(candidate) <= self._chunk_size:
                current = candidate
            else:
                if current:
                    merged.append(current)
                if len(sentence) > self._chunk_size:
                    merged.extend(self._force_split(sentence))
                    current = ""
                else:
                    current = sentence

        if current:
            merged.append(current)

        return merged

    def _force_split(self, text: str) -> list[str]:
        parts: list[str] = []
        start = 0
        while start < len(text):
            end = start + self._chunk_size
            parts.append(text[start:end])
            start = end - self._chunk_overlap
        return parts

    def _merge_into_chunks(self, segments: list[str]) -> list[str]:
        chunks: list[str] = []
        current = ""

        for segment in segments:
            candidate = f"{current}\n\n{segment}".strip() if current else segment
            if len(candidate) <= self._chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = segment

        if current:
            chunks.append(current)

        if self._chunk_overlap > 0 and len(chunks) > 1:
            chunks = self._apply_overlap(chunks)

        return chunks

    def _apply_overlap(self, chunks: list[str]) -> list[str]:
        result: list[str] = [chunks[0]]
        for i in range(1, len(chunks)):
            previous = chunks[i - 1]
            overlap_text = previous[-self._chunk_overlap :]
            boundary = overlap_text.rfind(" ")
            if boundary > 0:
                overlap_text = overlap_text[boundary + 1 :]
            merged = f"{overlap_text} {chunks[i]}".strip()
            result.append(merged)
        return result

    def _build_document_chunks(self, raw_chunks: list[str], doc_id: str) -> list[DocumentChunk]:
        total = len(raw_chunks)
        result: list[DocumentChunk] = []
        char_offset = 0

        for idx, text in enumerate(raw_chunks):
            chunk = DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                text=text,
                index=idx,
                metadata={
                    "char_start": char_offset,
                    "char_end": char_offset + len(text),
                    "chunk_index": idx,
                    "total_chunks": total,
                },
            )
            result.append(chunk)
            char_offset += len(text)

        return result
