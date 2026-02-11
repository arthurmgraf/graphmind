#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="${BACKUP_DIR}/${TIMESTAMP}"

mkdir -p "${BACKUP_PATH}"

echo "=== GraphMind Backup — ${TIMESTAMP} ==="

# Neo4j backup
echo "[1/3] Backing up Neo4j..."
docker compose exec -T neo4j neo4j-admin database dump neo4j --to-path=/tmp/neo4j-backup 2>/dev/null || echo "Neo4j backup requires enterprise edition, skipping dump"
docker compose cp neo4j:/tmp/neo4j-backup "${BACKUP_PATH}/neo4j/" 2>/dev/null || true

# Qdrant snapshot
echo "[2/3] Backing up Qdrant..."
curl -s -X POST "http://localhost:6333/collections/graphmind_docs/snapshots" \
  -o "${BACKUP_PATH}/qdrant_snapshot.json" || echo "Qdrant snapshot failed"

# PostgreSQL backup
echo "[3/3] Backing up PostgreSQL..."
docker compose exec -T postgres pg_dump -U graphmind graphmind \
  > "${BACKUP_PATH}/postgres.sql" 2>/dev/null || echo "PostgreSQL backup failed"

echo "=== Backup completed: ${BACKUP_PATH} ==="
ls -la "${BACKUP_PATH}/"

# Cleanup old backups (keep last 7 daily)
find "${BACKUP_DIR}" -maxdepth 1 -type d -mtime +7 -exec rm -rf {} \; 2>/dev/null || true
