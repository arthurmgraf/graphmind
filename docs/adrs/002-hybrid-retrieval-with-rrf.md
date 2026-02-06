# ADR-002: Hybrid Retrieval with Reciprocal Rank Fusion

## Status
Accepted

## Context
Pure vector search retrieves semantically similar documents but misses explicit relationships between entities. Pure graph traversal follows structured relationships but cannot discover new relevant documents by semantic similarity. A hybrid approach is needed.

## Decision
Implement a `HybridRetriever` that:
1. Embeds the query via Ollama (nomic-embed-text, 768 dimensions).
2. Performs vector similarity search in Qdrant (top-k=20).
3. Extracts entity IDs from vector results and expands through Neo4j (2 hops).
4. Fuses both ranked lists using Reciprocal Rank Fusion: `score(d) = sum(1/(k + rank))` with `k=60`.

## Consequences
- **Quality**: Combines semantic relevance with structural knowledge for better recall.
- **Complexity**: Two retrieval systems to maintain (Qdrant + Neo4j).
- **Performance**: Two parallel queries add latency, mitigated by async execution.
- **RRF k=60**: Standard value from the original RRF paper; tunable via config.
