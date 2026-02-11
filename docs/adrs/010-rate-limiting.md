# ADR-010: Rate Limiting Architecture

## Status
Accepted

## Context
GraphMind exposes a public API that processes queries involving multiple LLM calls (planning, retrieval, synthesis, evaluation) and ingestion operations that consume embedding and LLM resources. Without rate limiting, a single client or a traffic spike could:

1. Exhaust LLM provider rate limits (Groq free tier has per-minute token limits), triggering circuit breaker activations and degrading service for all users.
2. Saturate the Ollama embedding service, causing backpressure and timeouts for concurrent users.
3. Overload Neo4j and Qdrant with excessive queries, degrading retrieval performance.
4. Generate unbounded costs if using paid LLM tiers.

A rate limiting solution is needed that:
- Limits requests per client to protect shared resources.
- Has bounded and predictable memory usage (no unbounded growth under traffic from many unique IPs).
- Adds minimal latency to the request path.
- Works in the current single-process deployment.
- Has a clear upgrade path for multi-process/multi-instance deployments.

## Decision
Implement a **sliding-window, per-client-IP rate limiter** as FastAPI middleware using an in-memory `OrderedDict`, with a defined migration path to Redis for multi-process deployments.

### Current implementation: In-memory `RateLimitMiddleware`

The `RateLimitMiddleware` in `api/main.py` implements:

1. **Sliding window**: Each client IP has a list of request timestamps. On each request, timestamps older than 60 seconds are pruned. If the remaining count exceeds `rate_limit_rpm` (default: 60), the request is rejected with HTTP 429.

2. **Bounded memory via `OrderedDict`**: The window storage is an `OrderedDict` bounded to `_RATE_LIMIT_MAX_CLIENTS = 10,000` entries. When a new client IP arrives and the map is full, the oldest (least recently seen) client is evicted. This ensures memory usage is bounded regardless of how many unique IPs send traffic.

3. **Configurable**: The `rate_limit_rpm` setting (default: 60) is configurable via environment variable `RATE_LIMIT_RPM`. Setting it to 0 disables rate limiting entirely.

4. **Zero dependencies**: No external service (Redis, memcached) is required. The rate limiter runs entirely in-process.

5. **Public path exemption**: The middleware does not exempt specific paths from rate limiting (unlike `APIKeyMiddleware` which exempts `/api/v1/health`, `/docs`, etc.). Rate limiting applies to all endpoints uniformly. If health check probes are frequent, the 15-second cache on the health endpoint mitigates the impact.

### Memory analysis

```
Per client: 1 IP string (~40 bytes) + up to 60 float timestamps (~480 bytes) = ~520 bytes
Max clients: 10,000
Worst case: 10,000 * 520 bytes = ~5.2 MB
```

This is well within acceptable bounds for a single-process application.

### Redis migration path (multi-process)

When GraphMind scales to multiple API workers (via gunicorn with multiple uvicorn workers, or multiple container instances behind a load balancer), the in-memory rate limiter becomes per-process. Each process tracks its own counts, effectively multiplying the actual rate limit by the number of workers.

The migration path to consistent cross-process rate limiting:

1. **Add Redis** as an infrastructure service (already planned for arq job queue, see ADR-007).

2. **Replace `OrderedDict` with Redis sorted sets**:
   ```python
   # Key: rate_limit:{client_ip}
   # Members: request timestamps (score = timestamp)
   # ZRANGEBYSCORE to prune old entries
   # ZCARD to count current window
   # ZADD to record new request
   # EXPIRE to auto-clean inactive clients
   ```

3. **Use Redis pipeline** for atomic check-and-increment to avoid race conditions between workers.

4. **Backward compatibility**: The `RateLimitMiddleware` class can detect whether Redis is configured and fall back to in-memory if not:
   ```python
   class RateLimitMiddleware(BaseHTTPMiddleware):
       def __init__(self, app, rpm, redis_url=None):
           if redis_url:
               self._backend = RedisRateLimitBackend(redis_url, rpm)
           else:
               self._backend = InMemoryRateLimitBackend(rpm)
   ```

### Configuration

| Setting | Default | Environment Variable | Description |
|---------|---------|---------------------|-------------|
| `rate_limit_rpm` | 60 | `RATE_LIMIT_RPM` | Max requests per minute per client IP. Set to 0 to disable. |

## Consequences
- **Immediate protection**: The in-memory rate limiter is already deployed and protecting the API from traffic spikes, with zero additional infrastructure.
- **Bounded memory**: The `OrderedDict` with `_RATE_LIMIT_MAX_CLIENTS = 10,000` cap ensures memory usage stays under ~5.2 MB worst case, regardless of traffic patterns.
- **Low latency**: In-memory list operations (prune, count, append) add microseconds to request processing. No network round-trip to an external service.
- **Per-process limitation**: In a multi-worker deployment, each worker has its own rate limit state. A client sending requests to 4 workers effectively gets 4x the configured limit. This is acceptable for the current single-process deployment but must be addressed when scaling horizontally.
- **No distributed state**: Without Redis, rate limits cannot be shared across multiple API instances. The Redis migration path addresses this but adds infrastructure complexity and a network hop per request.
- **IP-based limitation**: Rate limiting by client IP can be circumvented by distributing requests across IPs. Behind a NAT or reverse proxy, multiple legitimate clients may share a single IP. The reverse proxy should be configured to pass `X-Forwarded-For` for accurate client identification.
- **No per-tenant limiting**: The current implementation limits by IP, not by tenant. When multi-tenancy is implemented (ADR-008), the rate limiter should be extended to support per-tenant limits using the `tenant_id` from the authenticated request context.
