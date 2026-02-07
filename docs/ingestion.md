# Document Ingestion

GraphMind ingests documents through a multi-step pipeline: load, chunk, extract entities/relations, embed, and store. The pipeline produces vector embeddings in Qdrant and a knowledge graph in Neo4j from each ingested document.

## Supported Formats

GraphMind supports **7 document formats**:

| Format | Extension | How It Is Processed |
|--------|-----------|---------------------|
| PDF | `.pdf` | Text extracted page-by-page via PyMuPDF |
| Markdown | `.md` | Plain text or file path, processed as-is |
| HTML | `.html` | Plain text or file path, processed as-is |
| Plain text | `.txt` | Plain text or file path, processed as-is |
| Python | `.py` | Wrapped in markdown fenced code block (` ```python `) |
| TypeScript | `.ts` | Wrapped in markdown fenced code block (` ```typescript `) |
| JavaScript | `.js` | Wrapped in markdown fenced code block (` ```javascript `) |

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

# Ingest HTML
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<h1>Title</h1><p>Some content about knowledge graphs.</p>",
    "filename": "page.html",
    "doc_type": "html"
  }'
```

### Request Schema

```json
{
  "content": "Full text content of the document",
  "filename": "document.md",
  "doc_type": "md"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `content` | string | required | Full text content of the document |
| `filename` | string | required | Original filename (used as metadata) |
| `doc_type` | string | `"markdown"` | Document format: `pdf`, `md`, `html`, `txt`, `py`, `ts`, `js` |

### Response Schema

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "chunks_created": 3,
  "entities_extracted": 5,
  "relations_extracted": 2
}
```

| Field | Type | Description |
|-------|------|-------------|
| `document_id` | string | UUID assigned to the ingested document |
| `chunks_created` | integer | Number of text chunks produced |
| `entities_extracted` | integer | Number of entities identified and stored in Neo4j |
| `relations_extracted` | integer | Number of relations identified and stored in Neo4j |

## Via CLI

```bash
# Ingest a local file
graphmind-ingest path/to/document.md --type md

# Ingest a PDF
graphmind-ingest path/to/paper.pdf --type pdf

# Ingest Python source code
graphmind-ingest path/to/module.py --type py
```

## Via Dashboard

1. Open http://localhost:8501
2. Select **Ingest** from the sidebar
3. Either:
   - **Upload a file** using the file uploader (supports all 7 formats; auto-fills content and filename)
   - **Paste content** directly into the text area
4. Select the document type from the dropdown
5. Set or confirm the filename
6. Click **Ingest**

The dashboard shows success metrics after ingestion: document ID (truncated), chunk count, entity count, and relation count.

## Via MCP (IDE)

In your IDE with MCP configured (see [Running](./running.md#mcp-server)):

```
Use graphmind ingest tool with content="# My Document\n\nContent here." filename="doc.md" doc_type="md"
```

## Pipeline Details

### 1. Loading

`DocumentLoader` reads the content based on format:
- **PDF**: Extracts text from each page using PyMuPDF (`fitz`), concatenating page text
- **Text formats** (md, html, txt): Reads file from disk or treats input as raw content string
- **Code** (py, ts, js): Wraps content in a markdown fenced code block with the appropriate language tag (e.g., ` ```python\n<code>\n``` `)

### 2. Chunking

`SemanticChunker` splits text into overlapping chunks for embedding:

| Parameter | Default | Description |
|-----------|---------|-------------|
| Chunk size | 512 characters | Maximum characters per chunk |
| Chunk overlap | 50 characters | Overlap between consecutive chunks |

Splitting strategy (in priority order):
1. **Paragraph boundaries** (`\n\n`) -- preferred split points
2. **Sentence boundaries** (`.`, `!`, `?`) -- for long paragraphs exceeding chunk size
3. **Force split** at chunk_size -- for text without natural boundaries

Each chunk receives:
- A unique UUID
- A sequential index (0, 1, 2, ...)
- Character offset metadata for source traceability

### 3. Entity Extraction (if configured)

An LLM extracts named entities from each chunk, typed as one of:
- `concept`, `technology`, `person`, `organization`, `framework`, `pattern`, `other`

Each entity gets a UUID, name, type, description, and reference back to its source chunk ID.

### 4. Relation Extraction (if configured)

An LLM extracts relationships between entities. Supported relation types:
- `uses`, `depends_on`, `extends`, `implements`, `part_of`, `related_to`

Each relation connects a source entity ID to a target entity ID with a type and description.

### 5. Vector Storage

Chunks are embedded using Ollama's `nomic-embed-text` model (768 dimensions) and stored in Qdrant. The Qdrant collection (`graphmind_docs`) uses cosine similarity for search.

### 6. Graph Storage

Entities and relations are upserted into Neo4j using `MERGE` operations, making ingestion idempotent. The graph schema includes:
- Uniqueness constraints on entity IDs
- Indexes for efficient traversal
- Full-text search index for text-based entity lookup

## Checking What Is Ingested

```bash
# Via API -- get knowledge graph statistics
curl http://localhost:8000/api/v1/stats
# Returns: total_entities, total_relations, total_documents, total_chunks,
#          entity_types distribution, relation_types distribution

# Via Neo4j Browser
# Open http://localhost:7474 and run Cypher queries:
# MATCH (n:Entity) RETURN n LIMIT 25
# MATCH ()-[r]->() RETURN type(r), count(r)

# Via Qdrant Dashboard
# Open http://localhost:6333/dashboard
# Browse the graphmind_docs collection
```

## Configuration

Ingestion parameters can be set in `config/settings.yaml`:

```yaml
ingestion:
  chunk_size: 512       # Characters per chunk
  chunk_overlap: 50     # Overlap between consecutive chunks
  supported_formats:
    - pdf
    - md
    - html
    - txt
    - py
    - ts
    - js
```

Embedding parameters:

```yaml
embeddings:
  provider: ollama
  model: nomic-embed-text
  base_url: http://localhost:11434
  dimensions: 768
```

## Related Documentation

- [Getting Started](./getting-started.md) -- Installation and pulling the embedding model
- [Querying](./querying.md) -- How the ingested data is retrieved and used
- [Architecture](./architecture.md) -- How ingestion fits into the overall system
- [Running](./running.md) -- Starting the API server for ingestion
