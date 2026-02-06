# Running the Application

GraphMind provides three interfaces: a REST API, a Streamlit dashboard, and an MCP server for IDE integration.

## FastAPI Server

The main entry point. All other interfaces communicate through this API.

```bash
# Using Make
make run

# Using the CLI entry point
graphmind

# Using uvicorn directly (with hot reload for development)
uvicorn graphmind.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Once running, access:
- **API docs (Swagger)**: http://localhost:8000/docs
- **API docs (ReDoc)**: http://localhost:8000/redoc
- **Health check**: http://localhost:8000/api/v1/health

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/query` | Run a knowledge query (LangGraph or CrewAI) |
| POST | `/api/v1/ingest` | Ingest a document |
| GET | `/api/v1/health` | Check service health |
| GET | `/api/v1/stats` | Get knowledge graph statistics |

## Streamlit Dashboard

Visual interface for queries, ingestion, knowledge graph stats, and system health.

```bash
# Using Make
make dashboard

# Using the CLI entry point
graphmind-dashboard

# Using streamlit directly
streamlit run src/graphmind/dashboard/app.py --server.port 8501
```

Access at: **http://localhost:8501**

The dashboard has 4 pages:
- **Query** - Ask questions, select engine (LangGraph/CrewAI), view answers with citations
- **Ingest** - Upload or paste documents, choose format, ingest into knowledge base
- **Knowledge Graph** - View entity/relation counts and type distributions
- **System** - Monitor service health and version info

**Important**: The FastAPI server must be running for the dashboard to work. The dashboard calls the API at the URL configured in the sidebar (default: `http://localhost:8000`).

## MCP Server

For integration with AI-powered IDEs (Claude Code, Cursor, VS Code).

```bash
# Using Make
make mcp

# Using the CLI entry point
graphmind-mcp
```

### Configuring MCP in your IDE

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

| Tool | Description |
|------|-------------|
| `query` | Ask a knowledge question (supports `engine` param: `langgraph` or `crewai`) |
| `ingest` | Ingest a document into the knowledge base |
| `graph_stats` | Get knowledge graph statistics |
| `health` | Check backend service health |

## Running All Services Together

For a full development setup, run these in separate terminals:

```bash
# Terminal 1: Infrastructure
docker compose up -d

# Terminal 2: FastAPI server
make run

# Terminal 3: Dashboard
make dashboard
```

## Service URLs Summary

| Service | URL | Purpose |
|---------|-----|---------|
| FastAPI API | http://localhost:8000 | REST API |
| Swagger Docs | http://localhost:8000/docs | API documentation |
| Streamlit Dashboard | http://localhost:8501 | Web UI |
| Neo4j Browser | http://localhost:7474 | Graph database UI |
| Langfuse | http://localhost:3000 | Observability dashboard |
| Qdrant Dashboard | http://localhost:6333/dashboard | Vector database UI |
