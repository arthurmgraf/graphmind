# Backup and Restore Procedures

This document covers backup and restore procedures for all stateful services in the GraphMind platform. Follow these procedures to protect against data loss and to recover from failures.

---

## Table of Contents

1. [Recovery Targets](#recovery-targets)
2. [Neo4j Backup and Restore](#neo4j-backup-and-restore)
3. [Qdrant Backup and Restore](#qdrant-backup-and-restore)
4. [PostgreSQL Backup and Restore](#postgresql-backup-and-restore)
5. [Verification Steps After Restore](#verification-steps-after-restore)
6. [Backup Schedule Recommendations](#backup-schedule-recommendations)

---

## Recovery Targets

| Target | Value | Notes |
|--------|-------|-------|
| **RTO (Recovery Time Objective)** | < 30 minutes | Time from declaring a restore is needed to having the system operational. |
| **RPO (Recovery Point Objective)** | < 24 hours | Maximum acceptable data loss. Backups should run at least once per day. |

These targets assume backups are stored on the same host or in readily accessible storage. Remote storage (S3, GCS) may add transfer time to the RTO.

---

## Neo4j Backup and Restore

Neo4j stores the knowledge graph: entities (7 types), relations (6 types), and their properties. Data is stored in the `neo4j_data` Docker volume.

### Backup

**Option A: neo4j-admin dump (offline, full consistency)**

```bash
# Stop Neo4j to ensure a consistent dump
docker compose stop neo4j

# Run the dump command inside a temporary container with the same volume
docker run --rm \
  -v graphmind_neo4j_data:/data \
  -v $(pwd)/backups:/backups \
  neo4j:5.26-community \
  neo4j-admin database dump neo4j --to-path=/backups

# Restart Neo4j
docker compose start neo4j

# Verify the backup file was created
ls -la backups/neo4j.dump
```

**Option B: APOC export (online, no downtime)**

```bash
# Connect to Neo4j and export to JSON (requires APOC plugin, which is enabled)
docker exec <neo4j-container> cypher-shell -u neo4j -p "${NEO4J_PASSWORD}" \
  "CALL apoc.export.json.all('/data/export.json', {useTypes: true})"

# Copy the export file out of the container
docker cp <neo4j-container>:/data/export.json ./backups/neo4j-export.json
```

### Restore

**From neo4j-admin dump:**

```bash
# Stop Neo4j
docker compose stop neo4j

# Remove existing data (destructive)
docker volume rm graphmind_neo4j_data
docker volume create graphmind_neo4j_data

# Restore the dump
docker run --rm \
  -v graphmind_neo4j_data:/data \
  -v $(pwd)/backups:/backups \
  neo4j:5.26-community \
  neo4j-admin database load neo4j --from-path=/backups --overwrite-destination=true

# Start Neo4j
docker compose start neo4j
```

**From APOC export:**

```bash
# Copy the export file into the container
docker cp ./backups/neo4j-export.json <neo4j-container>:/data/export.json

# Import (this adds to existing data; clear the database first if needed)
docker exec <neo4j-container> cypher-shell -u neo4j -p "${NEO4J_PASSWORD}" \
  "CALL apoc.import.json('/data/export.json')"
```

---

## Qdrant Backup and Restore

Qdrant stores vector embeddings and collection metadata in the `qdrant_data` Docker volume. The primary collection is `graphmind_docs` with 768-dimensional cosine similarity vectors.

### Backup

**Option A: Qdrant Snapshots API (online, no downtime)**

```bash
# Create a snapshot of the graphmind_docs collection
curl -X POST "http://localhost:6333/collections/graphmind_docs/snapshots"

# List available snapshots
curl "http://localhost:6333/collections/graphmind_docs/snapshots"

# Download the snapshot file
# The snapshot name is returned from the create call (e.g., "graphmind_docs-123456.snapshot")
curl "http://localhost:6333/collections/graphmind_docs/snapshots/<snapshot-name>" \
  --output ./backups/qdrant-graphmind_docs.snapshot
```

**Option B: Full storage snapshot (online)**

```bash
# Create a full storage snapshot (all collections)
curl -X POST "http://localhost:6333/snapshots"

# List full snapshots
curl "http://localhost:6333/snapshots"

# Download
curl "http://localhost:6333/snapshots/<snapshot-name>" \
  --output ./backups/qdrant-full.snapshot
```

**Option C: Docker volume copy (offline)**

```bash
# Stop Qdrant
docker compose stop qdrant

# Copy the volume data
docker run --rm \
  -v graphmind_qdrant_data:/source:ro \
  -v $(pwd)/backups:/backups \
  alpine tar czf /backups/qdrant-volume.tar.gz -C /source .

# Restart Qdrant
docker compose start qdrant
```

### Restore

**From Qdrant Snapshot:**

```bash
# Upload and restore the collection snapshot
# First, delete the existing collection if it exists
curl -X DELETE "http://localhost:6333/collections/graphmind_docs"

# Restore from snapshot file
curl -X POST "http://localhost:6333/collections/graphmind_docs/snapshots/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "snapshot=@./backups/qdrant-graphmind_docs.snapshot"
```

**From full storage snapshot:**

```bash
# Stop Qdrant
docker compose stop qdrant

# Remove existing data
docker volume rm graphmind_qdrant_data
docker volume create graphmind_qdrant_data

# Restore the snapshot into the volume
docker run --rm \
  -v graphmind_qdrant_data:/qdrant/storage \
  -v $(pwd)/backups:/backups \
  qdrant/qdrant:v1.12.1 \
  ./qdrant --storage-snapshot /backups/qdrant-full.snapshot

# Start Qdrant
docker compose start qdrant
```

**From Docker volume copy:**

```bash
# Stop Qdrant
docker compose stop qdrant

# Remove and recreate the volume
docker volume rm graphmind_qdrant_data
docker volume create graphmind_qdrant_data

# Restore from tar
docker run --rm \
  -v graphmind_qdrant_data:/target \
  -v $(pwd)/backups:/backups \
  alpine tar xzf /backups/qdrant-volume.tar.gz -C /target

# Start Qdrant
docker compose start qdrant
```

---

## PostgreSQL Backup and Restore

PostgreSQL stores Langfuse data: LLM call traces, evaluation scores, token usage, cost tracking, and user/session metadata. Data is in the `postgres_data` Docker volume. The database name is `graphmind` (or `langfuse` depending on Langfuse configuration).

### Backup

**Option A: pg_dump (online, no downtime)**

```bash
# Dump the graphmind database
docker exec <postgres-container> pg_dump \
  -U ${POSTGRES_USER:-graphmind} \
  -d graphmind \
  --format=custom \
  --file=/tmp/graphmind.dump

# Copy the dump out of the container
docker cp <postgres-container>:/tmp/graphmind.dump ./backups/postgres-graphmind.dump

# Also dump the langfuse database if it exists separately
docker exec <postgres-container> pg_dump \
  -U ${POSTGRES_USER:-graphmind} \
  -d langfuse \
  --format=custom \
  --file=/tmp/langfuse.dump 2>/dev/null

docker cp <postgres-container>:/tmp/langfuse.dump ./backups/postgres-langfuse.dump 2>/dev/null
```

**Option B: pg_dumpall (all databases)**

```bash
docker exec <postgres-container> pg_dumpall \
  -U ${POSTGRES_USER:-graphmind} \
  > ./backups/postgres-all.sql
```

**Option C: Docker volume copy (offline)**

```bash
# Stop PostgreSQL (and Langfuse which depends on it)
docker compose stop langfuse postgres

# Copy the volume
docker run --rm \
  -v graphmind_postgres_data:/source:ro \
  -v $(pwd)/backups:/backups \
  alpine tar czf /backups/postgres-volume.tar.gz -C /source .

# Restart
docker compose start postgres langfuse
```

### Restore

**From pg_dump (custom format):**

```bash
# Stop Langfuse (it depends on PostgreSQL)
docker compose stop langfuse

# Drop and recreate the database
docker exec <postgres-container> psql -U ${POSTGRES_USER:-graphmind} -c \
  "DROP DATABASE IF EXISTS graphmind;"
docker exec <postgres-container> psql -U ${POSTGRES_USER:-graphmind} -c \
  "CREATE DATABASE graphmind;"

# Restore from dump
docker cp ./backups/postgres-graphmind.dump <postgres-container>:/tmp/graphmind.dump
docker exec <postgres-container> pg_restore \
  -U ${POSTGRES_USER:-graphmind} \
  -d graphmind \
  /tmp/graphmind.dump

# Restart Langfuse
docker compose start langfuse
```

**From pg_dumpall (SQL format):**

```bash
docker compose stop langfuse

docker exec -i <postgres-container> psql \
  -U ${POSTGRES_USER:-graphmind} < ./backups/postgres-all.sql

docker compose start langfuse
```

**From Docker volume copy:**

```bash
docker compose stop langfuse postgres

docker volume rm graphmind_postgres_data
docker volume create graphmind_postgres_data

docker run --rm \
  -v graphmind_postgres_data:/target \
  -v $(pwd)/backups:/backups \
  alpine tar xzf /backups/postgres-volume.tar.gz -C /target

docker compose start postgres langfuse
```

---

## Verification Steps After Restore

After restoring any service, run the following verification steps to confirm data integrity and service health.

### 1. Health Check

```bash
# Wait for services to start (30 seconds for Neo4j start period)
sleep 30

# Check overall system health
curl -s http://localhost:8000/api/v1/health | python -m json.tool
```

Expected output:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "services": {
    "neo4j": "healthy",
    "qdrant": "healthy",
    "ollama": "healthy"
  }
}
```

### 2. Graph Statistics

```bash
# Verify graph data was restored
curl -s http://localhost:8000/api/v1/stats | python -m json.tool
```

Check that `total_entities`, `total_relations`, `total_documents`, and `total_chunks` match pre-backup values.

### 3. Neo4j Verification

```bash
# Count entities and relations directly
docker exec <neo4j-container> cypher-shell -u neo4j -p "${NEO4J_PASSWORD}" \
  "MATCH (n) RETURN count(n) AS nodes"

docker exec <neo4j-container> cypher-shell -u neo4j -p "${NEO4J_PASSWORD}" \
  "MATCH ()-[r]->() RETURN count(r) AS relationships"
```

### 4. Qdrant Verification

```bash
# Check collection info (vector count, configuration)
curl -s "http://localhost:6333/collections/graphmind_docs" | python -m json.tool
```

Verify `points_count` matches the expected number of chunks and `vector_size` is 768.

### 5. PostgreSQL Verification

```bash
# Check Langfuse database tables exist
docker exec <postgres-container> psql -U ${POSTGRES_USER:-graphmind} -d graphmind -c \
  "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
```

### 6. End-to-End Query Test

```bash
# Send a test query to verify the full pipeline works
curl -s -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is GraphMind?", "top_k": 5}' | python -m json.tool
```

Verify that the response includes an answer, citations, and a non-zero eval_score.

### 7. Langfuse Verification

Open `http://localhost:3000` in a browser and verify:
- You can log in.
- Previous traces are visible (if restoring from a backup that included traces).
- New queries create traces.

---

## Backup Schedule Recommendations

| Service | Method | Frequency | Retention | Storage |
|---------|--------|-----------|-----------|---------|
| Neo4j | APOC export (online) | Daily at 02:00 UTC | 7 daily + 4 weekly | Local `./backups/` + offsite |
| Neo4j | neo4j-admin dump (offline) | Weekly (Sunday 03:00 UTC) | 4 weekly | Offsite (S3/GCS) |
| Qdrant | Snapshots API | Daily at 02:30 UTC | 7 daily | Local `./backups/` + offsite |
| PostgreSQL | pg_dump | Daily at 01:30 UTC | 7 daily + 4 weekly | Local `./backups/` + offsite |

**Automation example (cron):**

```cron
# Daily PostgreSQL backup at 01:30 UTC
30 1 * * * /path/to/graphmind/scripts/backup-postgres.sh >> /var/log/graphmind-backup.log 2>&1

# Daily Neo4j APOC export at 02:00 UTC
0 2 * * * /path/to/graphmind/scripts/backup-neo4j.sh >> /var/log/graphmind-backup.log 2>&1

# Daily Qdrant snapshot at 02:30 UTC
30 2 * * * /path/to/graphmind/scripts/backup-qdrant.sh >> /var/log/graphmind-backup.log 2>&1
```

**Important:** Test your restore procedures regularly (at least quarterly) to verify that backups are usable and that the RTO target of < 30 minutes is achievable.

---

## Related Documentation

- [Operations Runbook](./runbook.md) -- Day-to-day operational procedures
- [Incident Playbook](./incident-playbook.md) -- Incident response procedures
- [Deployment](../deployment.md) -- Infrastructure and data persistence details
