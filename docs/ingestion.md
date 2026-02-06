# Document Ingestion

GraphMind ingests documents through a multi-step pipeline: load, chunk, extract entities/relations, embed, and store.

## Supported Formats

| Format | Extension | Description |
|--------|-----------|-------------|
| PDF | `.pdf` | Extracted via PyMuPDF (text per page) |
| Markdown | `.md` | Plain text or file path |
| HTML | `.html` | Plain text or file path |
| Plain text | `.txt` | Plain text or file path |
| Python | `.py` | Wrapped in fenced code block |
| TypeScript | `.ts` | Wrapped in fenced code block |
| JavaScript | `.js` | Wrapped in fenced code block |

## Via REST API

```bash
# Ingest markdown content
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "content": "# LangGraph\n\nLangGraph is a framework for building stateful multi-actor applications with LLMs.",
    "filename": "langgraph.md",
    "doc_type": "md"
  }'

# Ingest Python code
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "content": "def hello():\n    return \"world\"",
    "filename": "example.py",
    "doc_type": "py"
  }'
```

### Response

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "chunks_created": 3,
  "entities_extracted": 5,
  "relations_extracted": 2
}
```

## Via CLI

```bash
# Ingest a local file
graphmind-ingest path/to/document.md --type md

# Ingest a PDF
graphmind-ingest path/to/paper.pdf --type pdf
```

## Via Dashboard

1. Open http://localhost:8501
2. Select **Ingest** from the sidebar
3. Either:
   - Upload a file using the file uploader (auto-fills content and filename)
   - Paste content directly into the text area
4. Select the document type
5. Set the filename
6. Click **Ingest**

## Via MCP (IDE)

```
Use graphmind ingest tool with content="# My Document\n\nContent here." filename="doc.md" doc_type="md"
```

## Pipeline Details

### 1. Loading
`DocumentLoader` reads the content based on format:
- **PDF**: Extracts text from each page using PyMuPDF
- **Text formats** (md, html, txt): Reads file or treats input as raw content
- **Code** (py, ts, js): Wraps in markdown fenced code block with language tag

### 2. Chunking
`SemanticChunker` splits text into chunks:
- **Chunk size**: 512 characters (configurable)
- **Overlap**: 50 characters between chunks (configurable)
- Splits on paragraph boundaries (`\n\n`) first
- Falls back to sentence boundaries (`.!?`) for long paragraphs
- Force-splits at chunk_size for text without boundaries
- Each chunk gets a UUID, index, and char offset metadata

### 3. Entity Extraction (if configured)
LLM extracts entities typed as: concept, technology, person, organization, framework, pattern, or other.

### 4. Relation Extraction (if configured)
LLM extracts relations between entities: uses, depends_on, extends, implements, part_of, related_to.

### 5. Vector Storage
Chunks are embedded via Ollama (nomic-embed-text, 768 dimensions) and stored in Qdrant.

### 6. Graph Storage
Entities and relations are upserted into Neo4j using MERGE operations (idempotent).

## Checking What's Ingested

```bash
# Via API - get knowledge graph stats
curl http://localhost:8000/api/v1/stats

# Via Neo4j Browser
# Open http://localhost:7474 and run:
# MATCH (n:Entity) RETURN n LIMIT 25

# Via Qdrant Dashboard
# Open http://localhost:6333/dashboard
```

## Configuration

In `config/settings.yaml`:

```yaml
ingestion:
  chunk_size: 512      # Characters per chunk
  chunk_overlap: 50    # Overlap between chunks
  supported_formats:
    - pdf
    - md
    - html
    - txt
    - py
    - ts
    - js
```
