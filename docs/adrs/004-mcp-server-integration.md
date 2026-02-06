# ADR-004: MCP Server for IDE and Tool Integration

## Status
Accepted

## Context
GraphMind should be usable not only via its API/dashboard but also directly from AI-powered IDEs (Claude Code, Cursor, VS Code) and other tools that support the Model Context Protocol.

## Decision
Expose GraphMind capabilities as an MCP server using the `mcp` Python library (v1.x) over stdio transport. Tools exposed:
- `query` - Run the agentic RAG pipeline.
- `ingest` - Ingest documents into the knowledge base.
- `graph_stats` - Get knowledge graph statistics.
- `health` - Check service health.

Entry point: `graphmind-mcp` CLI command.

## Consequences
- **Accessibility**: Any MCP-compatible client can use GraphMind as a knowledge tool.
- **Simplicity**: stdio transport requires no HTTP server, reducing deployment complexity.
- **Limitation**: stdio means one client at a time; HTTP/SSE transport can be added later.
