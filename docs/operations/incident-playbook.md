# Incident Response Playbook

This playbook provides structured procedures for responding to incidents affecting the GraphMind platform. Follow the appropriate decision tree based on the observed symptoms.

---

## Table of Contents

1. [Severity Levels](#severity-levels)
2. [Decision Trees](#decision-trees)
   - [High Latency](#high-latency)
   - [Low Evaluation Scores](#low-evaluation-scores)
   - [Provider Outages](#provider-outages)
   - [Data Inconsistency](#data-inconsistency)
   - [Rate Limiting Issues](#rate-limiting-issues)
3. [Escalation Paths](#escalation-paths)
4. [Post-Incident Review Template](#post-incident-review-template)

---

## Severity Levels

| Severity | Definition | Response Time | Update Cadence | Examples |
|----------|-----------|---------------|----------------|----------|
| **P1 -- Critical** | Complete service outage. No queries can be processed. Data loss risk. | **15 minutes** | Every 30 minutes | All LLM providers exhausted, Neo4j data corruption, API unresponsive |
| **P2 -- High** | Significant degradation. Core functionality impaired but partially available. | **1 hour** | Every 2 hours | Primary provider down (operating on fallback), health check degraded, elevated error rate (>10%) |
| **P3 -- Medium** | Minor degradation. Non-critical functionality affected. Workarounds exist. | **4 hours** | Daily | Slow queries (p95 > 10s), Langfuse tracing unavailable, dashboard errors, single eval score drop |
| **P4 -- Low** | Cosmetic or minor issue. No user-facing impact. | **Next business day** | As needed | Log noise, non-critical deprecation warnings, documentation gaps |

---

## Decision Trees

### High Latency

**Trigger:** p95 latency exceeds 10 seconds, or individual queries consistently take > 15 seconds.

```
Query latency > 10s?
|
+-- Check /api/v1/health
|   |
|   +-- status: "degraded"?
|   |   |
|   |   +-- Which service is unhealthy?
|   |       |
|   |       +-- neo4j: unhealthy
|   |       |   --> Graph retrieval is slow or failing.
|   |       |   --> Check: docker compose logs neo4j --tail=50
|   |       |   --> Fix: Restart neo4j, check heap/pagecache settings.
|   |       |   --> Temporary: Reduce retrieval.graph_hops to 1.
|   |       |
|   |       +-- qdrant: unhealthy
|   |       |   --> Vector search is failing, falling back to graph-only.
|   |       |   --> Check: docker compose logs qdrant --tail=50
|   |       |   --> Fix: Restart qdrant, check memory limit.
|   |       |
|   |       +-- ollama: unhealthy
|   |           --> Embedding calls are failing/retrying with backoff.
|   |           --> Check: docker compose logs ollama --tail=50
|   |           --> Fix: Restart ollama, verify model is pulled.
|   |
|   +-- status: "ok" (all services healthy)
|       |
|       +-- Check which LLM provider is being used (grep logs)
|           |
|           +-- Using "ollama" (local fallback)?
|           |   --> Cloud providers are failing; Ollama is 2-10x slower.
|           |   --> Severity: P2. Investigate Groq/Gemini API keys and quotas.
|           |
|           +-- Using "groq" or "gemini" but still slow?
|           |   --> Check retry count in response (retry_count > 0?)
|           |   |
|           |   +-- Retries happening?
|           |   |   --> Eval scores are below 0.7, triggering rewrites.
|           |   |   --> Check knowledge base coverage for query topics.
|           |   |   --> Consider lowering agents.eval_threshold temporarily.
|           |   |
|           |   +-- No retries, still slow?
|           |       --> Provider-side latency spike.
|           |       --> Check provider status pages (status.groq.com).
|           |       --> Severity: P3. Monitor and wait for provider recovery.
|           |
|           +-- Check embedding batch size and concurrency
|               --> Large ingestion jobs can saturate Ollama.
|               --> Reduce ingestion.max_concurrent_chunks.
```

### Low Evaluation Scores

**Trigger:** Average eval score drops below 0.5, or > 50% of queries have eval_score < 0.7.

```
Low eval scores detected?
|
+-- Is the knowledge base empty or nearly empty?
|   |
|   +-- Check: GET /api/v1/stats (total_entities, total_chunks)
|   |
|   +-- Few or zero chunks?
|       --> Ingest relevant documents first.
|       --> Not an incident; operational gap.
|
+-- Knowledge base has content?
    |
    +-- Are queries relevant to ingested content?
    |   |
    |   +-- No --> Queries are outside the knowledge domain.
    |   |       --> Expected behavior; not an incident.
    |   |
    |   +-- Yes --> Retrieval or synthesis problem.
    |       |
    |       +-- Check retrieval quality (are relevant chunks being retrieved?)
    |       |   |
    |       |   +-- Chunks are relevant but answer is poor?
    |       |   |   --> LLM synthesis issue.
    |       |   |   --> Check which provider is being used.
    |       |   |   --> If using Ollama fallback, quality is expected to be lower.
    |       |   |   --> Severity: P3. Ensure cloud providers are available.
    |       |   |
    |       |   +-- Chunks are NOT relevant?
    |       |       --> Embedding quality or vector search issue.
    |       |       --> Verify embedding model is loaded: docker exec ollama ollama list
    |       |       --> Check if Qdrant collection exists and has vectors.
    |       |       --> Re-ingest documents if embedding model was changed.
    |       |       --> Severity: P2.
    |       |
    |       +-- Is the evaluator itself malfunctioning?
    |           --> Check evaluator logs for JSON parse failures.
    |           --> The evaluator falls back to heuristic scoring on parse failure.
    |           --> Heuristic scores may differ from LLM-as-judge scores.
    |           --> Severity: P3. Check LLM provider availability.
```

### Provider Outages

**Trigger:** Logs show "Provider X failed" warnings. Circuit breaker is open for one or more providers.

```
Provider outage detected?
|
+-- Which provider(s) are affected?
|
+-- Only Groq (primary) is down?
|   --> System falls back to Gemini automatically.
|   --> Severity: P3 (if Gemini is working).
|   --> Action: Monitor. Check Groq status page. Circuit breaker will
|       auto-recover via half-open probe when Groq returns.
|
+-- Groq AND Gemini are down?
|   --> System falls back to Ollama (local).
|   --> Severity: P2 (degraded quality and speed).
|   --> Action: Verify API keys. Check provider status pages.
|       Consider temporarily increasing Ollama resources.
|
+-- All three providers are down?
|   --> Severity: P1 (complete query failure).
|   --> "All LLM providers exhausted" errors.
|   --> Action:
|       1. Check Ollama container: docker compose ps ollama
|       2. Check Ollama model: docker exec ollama ollama list
|       3. Restart Ollama: docker compose restart ollama
|       4. Restart API server to reset circuit breaker state.
|       5. Verify API keys for Groq and Gemini.
|
+-- Recovery steps:
    --> Circuit breakers auto-recover after backoff period (2-60s exponential).
    --> Half-open probes test the provider on the next request.
    --> On success, circuit closes and normal routing resumes.
    --> To force-reset all circuits: restart the API server process.
```

### Data Inconsistency

**Trigger:** Query results reference non-existent entities. Graph stats show unexpected counts. Chunks exist in Qdrant but not in Neo4j (or vice versa).

```
Data inconsistency detected?
|
+-- Chunks in Qdrant but missing from Neo4j?
|   --> Ingestion partially failed (graph storage step failed).
|   --> Check ingestion logs for "graph_storage_failed" events.
|   --> Fix: Re-ingest the affected documents.
|   --> Severity: P3.
|
+-- Entities in Neo4j but no vectors in Qdrant?
|   --> Ingestion partially failed (vector storage step failed).
|   --> Check ingestion logs for "vector_storage_failed" events.
|   --> Fix: Re-ingest the affected documents.
|   --> Severity: P3.
|
+-- Graph stats show zero counts but data was ingested?
|   --> Neo4j connection issue or database reset.
|   --> Check: docker compose logs neo4j --tail=50
|   --> Verify neo4j_data volume exists: docker volume ls | grep neo4j
|   --> If volume was lost, restore from backup (see restore.md).
|   --> Severity: P2.
|
+-- Duplicate entities or relations?
|   --> Graph builder uses MERGE operations which should prevent duplicates.
|   --> If duplicates exist, check for entity name normalization issues.
|   --> Fix: Run deduplication Cypher query in Neo4j browser (port 7474).
|   --> Severity: P4.
```

### Rate Limiting Issues

**Trigger:** Clients report HTTP 429 errors. Legitimate traffic is being blocked.

```
Rate limiting issues?
|
+-- Single client hitting limits?
|   --> Default: 60 requests per minute per client IP.
|   --> Is the client making > 60 req/min?
|   |
|   +-- Yes --> Client needs to implement backoff.
|   |       --> Or increase RATE_LIMIT_RPM in .env.
|   |       --> Severity: P4.
|   |
|   +-- No --> Multiple clients sharing an IP (NAT/proxy)?
|       --> The rate limiter tracks by client IP.
|       --> Behind a reverse proxy, all clients may share one IP.
|       --> Fix: Configure the proxy to pass X-Forwarded-For.
|       --> Or increase RATE_LIMIT_RPM.
|       --> Severity: P3.
|
+-- Many clients hitting limits simultaneously?
|   --> Possible traffic spike or DDoS.
|   --> Check: How many unique IPs are in the rate limiter?
|   --> The rate limiter is bounded to 10,000 client entries (evicts oldest).
|   --> If legitimate traffic spike: increase RATE_LIMIT_RPM.
|   --> If attack: add IP blocking at the reverse proxy layer.
|   --> Severity: P2 (if legitimate users are affected).
|
+-- Rate limiter consuming too much memory?
    --> Bounded to _RATE_LIMIT_MAX_CLIENTS = 10,000 entries.
    --> Each entry stores a list of timestamps (max 60 per window).
    --> Memory is bounded and predictable.
    --> Not expected to be an issue.
    --> Severity: P4.
```

---

## Escalation Paths

| Level | Role | When to Escalate | Contact Method |
|-------|------|-----------------|----------------|
| **L1** | On-call engineer | First responder for all alerts. Follows decision trees above. | Pager / Slack alert channel |
| **L2** | Backend engineer | Escalate if L1 cannot resolve within the severity response time. Code-level debugging required. | Slack direct message + incident channel |
| **L3** | Platform / infra lead | Escalate for data loss, infrastructure failures, or issues requiring architectural changes. | Phone call + incident channel |
| **External** | Provider support | Escalate to Groq/Google/Ollama support if the issue is confirmed to be provider-side. | Provider support channels |

**Escalation rules:**

- **P1**: Immediately notify L2. If not resolved in 30 minutes, escalate to L3.
- **P2**: Attempt L1 resolution for 1 hour. If unresolved, escalate to L2.
- **P3**: L1 handles during business hours. Escalate to L2 if unresolved after 1 business day.
- **P4**: Track in backlog. No escalation required.

---

## Post-Incident Review Template

Complete this template within 3 business days of incident resolution for P1/P2 incidents, and within 1 week for P3 incidents. P4 incidents do not require a post-incident review.

```markdown
# Post-Incident Review: [INCIDENT-ID]

## Summary
- **Date/Time:** [When the incident started and ended, in UTC]
- **Duration:** [Total time from detection to resolution]
- **Severity:** [P1/P2/P3]
- **Impact:** [What users/functionality were affected, and to what extent]
- **On-call:** [Who responded]

## Timeline
| Time (UTC) | Event |
|-----------|-------|
| HH:MM | [First alert or detection] |
| HH:MM | [First responder acknowledged] |
| HH:MM | [Key diagnostic step] |
| HH:MM | [Mitigation applied] |
| HH:MM | [Resolution confirmed] |

## Root Cause
[Detailed technical explanation of why the incident occurred.
Include the chain of events that led to the failure.]

## Detection
- **How was it detected?** [Alert / user report / health check / manual observation]
- **Detection delay:** [Time between incident start and detection]
- **Could detection have been faster?** [Yes/No, and how]

## Response
- **What worked well?** [Effective steps taken during the response]
- **What could be improved?** [Steps that were slow, confusing, or missing]
- **Were runbooks/playbooks followed?** [Yes/No, and which ones]
- **Were runbooks/playbooks adequate?** [Yes/No, and what was missing]

## Mitigation and Resolution
- **Immediate mitigation:** [What was done to stop the bleeding]
- **Root cause fix:** [What was done to permanently resolve the issue]
- **Rollback required?** [Yes/No, and what was rolled back]

## Action Items
| ID | Action | Owner | Priority | Due Date | Status |
|----|--------|-------|----------|----------|--------|
| 1 | [Action description] | [Name] | [P1-P4] | [Date] | [Open/Done] |
| 2 | [Action description] | [Name] | [P1-P4] | [Date] | [Open/Done] |

## Metrics
- **Time to detect (TTD):** [minutes]
- **Time to mitigate (TTM):** [minutes]
- **Time to resolve (TTR):** [minutes]
- **Queries affected:** [count or estimate]
- **Error rate during incident:** [percentage]

## Lessons Learned
[Key takeaways. What should the team remember from this incident?
Include both technical and process lessons.]
```

**Required sections for all reviews:** Summary, Timeline, Root Cause, Action Items.

**Additional sections for P1 reviews:** Detection, Response, Metrics, Lessons Learned.

---

## Related Documentation

- [Operations Runbook](./runbook.md) -- Day-to-day operational procedures
- [Backup and Restore](./restore.md) -- Data recovery procedures
- [Architecture](../architecture.md) -- System design reference
- [Deployment](../deployment.md) -- Configuration and environment details
