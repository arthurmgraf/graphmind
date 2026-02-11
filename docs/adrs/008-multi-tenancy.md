# ADR-008: Multi-Tenancy Isolation Model

## Status
Accepted

## Context
GraphMind is designed as a knowledge agent platform that may serve multiple users, teams, or organizations. As the platform moves toward production, a multi-tenancy model is needed to ensure that:

1. **Data isolation**: One tenant's ingested documents, knowledge graph entities, and vector embeddings are not visible to other tenants during queries.
2. **Cost attribution**: LLM token usage and costs can be tracked per tenant via the existing `CostTracker`.
3. **Rate limiting**: Per-tenant rate limits can be enforced independently of per-IP limits.
4. **Scalability**: The isolation model should not require separate infrastructure per tenant, as this would be prohibitively expensive for small to medium deployments.

Three isolation models were considered:

**Separate infrastructure per tenant**: Each tenant gets their own Qdrant collection, Neo4j database, and PostgreSQL schema. Maximum isolation but high operational cost and complexity. Does not scale to many tenants.

**Shared schema with tenant_id filter**: All tenants share the same database tables, collections, and graphs, but every record includes a `tenant_id` field. All queries filter by `tenant_id`. Simple to implement, scales to many tenants, but relies on correct application-level filtering.

**Schema-per-tenant**: Each tenant gets their own schema within shared database instances (e.g., separate Qdrant collections per tenant, separate Neo4j databases per tenant). Moderate isolation and complexity.

## Decision
Adopt the **shared schema with `tenant_id` filter** model for the following reasons:

1. **Simplicity**: Adding a `tenant_id` field to existing models and filtering all queries is straightforward. No infrastructure changes are required.

2. **Scalability**: Supports hundreds of tenants without additional infrastructure. A single Qdrant collection with payload filtering on `tenant_id` is efficient (Qdrant supports indexed payload filtering). A single Neo4j database with `tenant_id` property on all nodes works with indexed lookups.

3. **Cost**: No per-tenant infrastructure provisioning. One set of services serves all tenants.

4. **Alignment with existing architecture**: The application already uses filter-based retrieval (Qdrant payload filters, Neo4j Cypher WHERE clauses). Adding `tenant_id` to these filters is a natural extension.

### Implementation details

**Schema changes:**

- `DocumentChunk.metadata` gains a `tenant_id` field.
- `Entity` and `Relation` gain a `tenant_id` field.
- Qdrant points include `tenant_id` in the payload for filtering.
- Neo4j nodes include a `tenant_id` property with an index.

**Query filtering:**

- `VectorRetriever.search()` adds `must: [{"key": "tenant_id", "match": {"value": tenant_id}}]` to the Qdrant filter.
- `GraphRetriever.expand()` adds `WHERE n.tenant_id = $tenant_id` to Cypher queries.
- `HybridRetriever` passes `tenant_id` through to both sub-retrievers.

**Tenant identification:**

- API requests include `tenant_id` in the request body or derive it from the API key (via a tenant-to-key mapping).
- The `APIKeyMiddleware` can be extended to resolve `tenant_id` from the Bearer token and attach it to `request.state`.

**Ingestion:**

- `IngestRequest` gains an optional `tenant_id` field.
- `IngestionPipeline.process()` propagates `tenant_id` to all created chunks, entities, and relations.

**Cost tracking:**

- `CostTracker.record()` accepts an optional `tenant_id` parameter.
- `CostTracker.summary()` supports filtering by tenant.

## Consequences
- **Low implementation cost**: No new infrastructure. Changes are limited to adding a field and filter to existing code paths.
- **Scales well**: Hundreds of tenants can share the same infrastructure without performance issues, assuming proper indexing.
- **No hard isolation**: A bug in the application code (missing `tenant_id` filter) could leak data between tenants. This risk is mitigated by centralizing the filter logic in the retriever layer and adding integration tests that verify cross-tenant isolation.
- **Performance**: Qdrant payload filtering on an indexed field adds negligible overhead. Neo4j property filtering with an index is similarly efficient. The overhead is proportional to the total data volume, not the number of tenants.
- **Noisy neighbor risk**: A single tenant with heavy ingestion or query load can impact other tenants. This is mitigated by per-tenant rate limiting (extending the existing `RateLimitMiddleware` to key by `tenant_id` instead of or in addition to client IP).
- **Migration path**: If stronger isolation is later needed for specific high-value tenants, individual tenants can be migrated to dedicated Qdrant collections or Neo4j databases without changing the API contract (the `tenant_id` field remains; routing logic changes internally).
