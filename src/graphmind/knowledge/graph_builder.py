from __future__ import annotations

import logging

from neo4j import AsyncGraphDatabase, AsyncDriver

from graphmind.config import Settings, get_settings
from graphmind.schemas import Entity, GraphStats, Relation

logger = logging.getLogger(__name__)

UPSERT_ENTITY_QUERY = """
MERGE (e:Entity {name: $name, type: $type})
ON CREATE SET
    e.id = $id,
    e.description = $description,
    e.source_chunk_id = $source_chunk_id,
    e.created_at = datetime()
ON MATCH SET
    e.description = CASE
        WHEN size($description) > size(coalesce(e.description, ''))
        THEN $description ELSE e.description
    END,
    e.updated_at = datetime()
RETURN e.id AS entity_id
"""

UPSERT_RELATION_QUERY = """
MATCH (source:Entity {id: $source_id})
MATCH (target:Entity {id: $target_id})
MERGE (source)-[r:RELATES_TO {type: $type}]->(target)
ON CREATE SET
    r.id = $id,
    r.description = $description,
    r.created_at = datetime()
ON MATCH SET
    r.description = CASE
        WHEN size($description) > size(coalesce(r.description, ''))
        THEN $description ELSE r.description
    END,
    r.updated_at = datetime()
RETURN r.id AS relation_id
"""

SCHEMA_QUERY = """
CALL db.schema.visualization() YIELD nodes, relationships
RETURN nodes, relationships
"""

STATS_ENTITY_COUNT = "MATCH (e:Entity) RETURN count(e) AS total"

STATS_RELATION_COUNT = "MATCH ()-[r:RELATES_TO]->() RETURN count(r) AS total"

STATS_ENTITY_TYPES = """
MATCH (e:Entity)
RETURN e.type AS type, count(e) AS count
ORDER BY count DESC
"""

STATS_RELATION_TYPES = """
MATCH ()-[r:RELATES_TO]->()
RETURN r.type AS type, count(r) AS count
ORDER BY count DESC
"""

SCHEMA_DESCRIPTION_QUERY = """
CALL db.schema.visualization() YIELD nodes, relationships
WITH [n IN nodes | labels(n)[0] + ' (' + coalesce(n.name, '') + ')'] AS node_labels,
     [r IN relationships | type(r)] AS rel_types
RETURN node_labels, rel_types
"""


class GraphBuilder:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(
            self._settings.neo4j_uri,
            auth=(self._settings.neo4j_username, self._settings.neo4j_password),
            database=self._settings.graph_db.database,
        )

    async def close(self) -> None:
        await self._driver.close()

    async def upsert_entities(self, entities: list[Entity]) -> int:
        upserted = 0
        async with self._driver.session() as session:
            for entity in entities:
                try:
                    result = await session.run(
                        UPSERT_ENTITY_QUERY,
                        id=entity.id,
                        name=entity.name,
                        type=entity.type.value,
                        description=entity.description,
                        source_chunk_id=entity.source_chunk_id,
                    )
                    record = await result.single()
                    if record:
                        upserted += 1
                except Exception:
                    logger.exception(
                        "Failed to upsert entity %s (%s)",
                        entity.name,
                        entity.type.value,
                    )

        logger.info("Upserted %d / %d entities", upserted, len(entities))
        return upserted

    async def upsert_relations(self, relations: list[Relation]) -> int:
        upserted = 0
        async with self._driver.session() as session:
            for relation in relations:
                try:
                    result = await session.run(
                        UPSERT_RELATION_QUERY,
                        id=relation.id,
                        source_id=relation.source_id,
                        target_id=relation.target_id,
                        type=relation.type,
                        description=relation.description,
                    )
                    record = await result.single()
                    if record:
                        upserted += 1
                except Exception:
                    logger.exception(
                        "Failed to upsert relation %s -[%s]-> %s",
                        relation.source_id,
                        relation.type,
                        relation.target_id,
                    )

        logger.info("Upserted %d / %d relations", upserted, len(relations))
        return upserted

    async def get_schema(self) -> str:
        async with self._driver.session() as session:
            try:
                result = await session.run(SCHEMA_DESCRIPTION_QUERY)
                record = await result.single()
                if not record:
                    return "Empty graph - no schema available."

                node_labels: list[str] = record["node_labels"]
                rel_types: list[str] = record["rel_types"]

                lines: list[str] = ["Node labels:"]
                for label in node_labels:
                    lines.append(f"  - {label}")
                lines.append("Relationship types:")
                for rel in rel_types:
                    lines.append(f"  - {rel}")
                return "\n".join(lines)
            except Exception:
                logger.exception("Failed to retrieve graph schema")
                return "Schema unavailable."

    async def get_stats(self) -> GraphStats:
        async with self._driver.session() as session:
            entity_result = await session.run(STATS_ENTITY_COUNT)
            entity_record = await entity_result.single()
            total_entities = entity_record["total"] if entity_record else 0

            relation_result = await session.run(STATS_RELATION_COUNT)
            relation_record = await relation_result.single()
            total_relations = relation_record["total"] if relation_record else 0

            entity_type_result = await session.run(STATS_ENTITY_TYPES)
            entity_types: dict[str, int] = {}
            async for record in entity_type_result:
                entity_types[record["type"]] = record["count"]

            relation_type_result = await session.run(STATS_RELATION_TYPES)
            relation_types: dict[str, int] = {}
            async for record in relation_type_result:
                relation_types[record["type"]] = record["count"]

        return GraphStats(
            total_entities=total_entities,
            total_relations=total_relations,
            entity_types=entity_types,
            relation_types=relation_types,
        )

    async def __aenter__(self) -> GraphBuilder:
        return self

    async def __aexit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> None:
        await self.close()
