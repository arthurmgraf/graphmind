# Running the Application

GraphMind provides three interfaces: a **REST API** (FastAPI), a **Streamlit dashboard**, and an **MCP server** for IDE integration. All three rely on the Docker infrastructure services being up (see [Getting Started](./getting-started.md)).

## FastAPI Server

The main entry point. The dashboard and MCP server both communicate through this API.

```bash
# Using Make
make run

# Using the CLI entry point
graphmind

# Using uvicorn directly (with hot reload for development)
uvicorn graphmind.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Once running, access:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health check**: http://localhost:8000/api/v1/health

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/query` | Run a knowledge query (LangGraph or CrewAI engine) |
| POST | `/api/v1/ingest` | Ingest a document into the knowledge base |
| GET | `/api/v1/health` | Check service health (Neo4j, Qdrant, Ollama) |
| GET | `/api/v1/stats` | Get knowledge graph statistics (entities, relations, documents, chunks) |

All endpoints use Pydantic models for request/response validation. See [Querying](./querying.md) and [Ingestion](./ingestion.md) for detailed request/response schemas.

## Streamlit Dashboard

A visual interface with four pages for interacting with the knowledge base.

```bash
# Using Make
make dashboard

# Using the CLI entry point
graphmind-dashboard

# Using streamlit directly
streamlit run src/graphmind/dashboard/app.py --server.port 8501
```

Access at: **http://localhost:8501**

### Dashboard Pages

| Page | Description |
|------|-------------|
| **Query** | Ask questions, select engine (LangGraph/CrewAI), adjust top-k, view answers with eval score, latency, source count, and expandable citations |
| **Ingest** | Upload files or paste content directly, choose from 7 document formats (PDF, MD, HTML, TXT, PY, TS, JS), ingest into the knowledge base |
| **Knowledge Graph** | View total entity/relation/document/chunk counts, bar charts of entity type and relation type distributions |
| **System** | Monitor service health status (Neo4j, Qdrant, Ollama), view version info |

**Important**: The FastAPI server must be running for the dashboard to work. The dashboard calls the API at the URL configured in the sidebar (default: `http://localhost:8000`). You can change the API URL in the sidebar without restarting.

## MCP Server

For integration with AI-powered IDEs such as Claude Code, Cursor, and VS Code with MCP support.

```bash
# Using Make
make mcp

# Using the CLI entry point
graphmind-mcp
```

The MCP server communicates over stdio and provides 4 tools.

### Configuring MCP in Your IDE

Add to your MCP client configuration file:

**Claude Code** (`~/.claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "graphmind": {
      "command": "graphmind-mcp",
      "args": []
    }
  }
}
```

**Cursor** (`.cursor/mcp.json`):
```json
{
  "mcpServers": {
    "graphmind": {
      "command": "graphmind-mcp",
      "args": []
    }
  }
}
```

### Available MCP Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `query` | Ask a knowledge question via the agentic RAG pipeline | `question` (required), `top_k` (default 10), `engine` (`langgraph` or `crewai`) |
| `ingest` | Ingest a document into the knowledge base | `content` (required), `filename` (required), `doc_type` (default `md`) |
| `graph_stats` | Get knowledge graph statistics (entities, relations, documents, chunks) | None |
| `health` | Check backend service health (Neo4j, Qdrant, Ollama) | None |

### MCP Usage Examples

In your IDE with MCP configured:

```
Use the graphmind query tool to answer: What is Reciprocal Rank Fusion?
```

```
Use graphmind query with engine=crewai: Compare CrewAI and LangGraph architectures
```

```
Use graphmind ingest with content="# My Notes\n\nContent here" filename="notes.md" doc_type="md"
```

## Running All Services Together

For a full development setup, run these in separate terminals:

```bash
# Terminal 1: Infrastructure (5 Docker services, ~3.3 GB RAM)
docker compose up -d

# Terminal 2: FastAPI server (with hot reload)
make run

# Terminal 3: Dashboard
make dashboard
```

## CLI Entry Points Summary

All entry points are defined in `pyproject.toml` under `[project.scripts]`:

| Command | Module | Purpose |
|---------|--------|---------|
| `graphmind` | `graphmind.api.main:run` | Start FastAPI server on port 8000 |
| `graphmind-dashboard` | `graphmind.dashboard.app:main` | Start Streamlit dashboard on port 8501 |
| `graphmind-mcp` | `graphmind.mcp.server:main` | Start MCP server (stdio transport) |
| `graphmind-ingest` | `graphmind.ingestion.pipeline:cli` | CLI document ingestion |
| `graphmind-eval` | `graphmind.evaluation.benchmark:cli` | Run evaluation benchmark |

## Service URLs Summary

| Service | URL | Purpose |
|---------|-----|---------|
| FastAPI API | http://localhost:8000 | REST API for query, ingest, health, stats |
| Swagger Docs | http://localhost:8000/docs | Interactive API documentation |
| Streamlit Dashboard | http://localhost:8501 | Web UI (Query, Ingest, Knowledge Graph, System) |
| Neo4j Browser | http://localhost:7474 | Graph database UI (Cypher queries) |
| Langfuse | http://localhost:3000 | LLM observability, tracing, cost tracking |
| Qdrant Dashboard | http://localhost:6333/dashboard | Vector database UI |

## Related Documentation

- [Getting Started](./getting-started.md) -- Installation and setup
- [Querying](./querying.md) -- Detailed query pipeline documentation
- [Ingestion](./ingestion.md) -- Document ingestion pipeline
- [Architecture](./architecture.md) -- System design overview
