"""Neo4j graph retriever with DI support for shared driver."""

from __future__ import annotations

import neo4j
from neo4j import AsyncDriver, AsyncGraphDatabase

from graphmind.config import Settings, get_settings
from graphmind.schemas import RetrievalResult


class GraphRetriever:
    def __init__(
        self,
        settings: Settings | None = None,
        driver: AsyncDriver | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        if driver is not None:
            self._driver = driver
            self._owns_driver = False
        else:
            self._driver = AsyncGraphDatabase.driver(
                self._settings.graph_db.uri,
                auth=(self._settings.graph_db.username, self._settings.neo4j_password),
            )
            self._owns_driver = True
        self._database = self._settings.graph_db.database

    async def expand(
        self, entity_ids: list[str], hops: int = 2
    ) -> list[RetrievalResult]:
        query = (
            "MATCH path = (e:Entity)-[*1..$hops]-(related) "
            "WHERE e.id IN $ids "
            "UNWIND relationships(path) AS rel "
            "UNWIND [startNode(rel), endNode(rel)] AS node "
            "WITH DISTINCT node, rel "
            "RETURN node.id AS node_id, "
            "       node.name AS name, "
            "       node.description AS description, "
            "       type(rel) AS rel_type, "
            "       startNode(rel).name AS rel_source, "
            "       endNode(rel).name AS rel_target"
        )
        results: list[RetrievalResult] = []
        seen_ids: set[str] = set()
        async with self._driver.session(database=self._database) as session:
            records = await session.run(query, ids=entity_ids, hops=hops)
            async for record in records:
                node_id = record["node_id"]
                if node_id in seen_ids:
                    continue
                seen_ids.add(node_id)
                name = record["name"] or ""
                description = record["description"] or ""
                rel_type = record["rel_type"] or ""
                rel_source = record["rel_source"] or ""
                rel_target = record["rel_target"] or ""
                text = f"{name}: {description}" if description else name
                if rel_type:
                    text += f" [{rel_source} -{rel_type}-> {rel_target}]"
                results.append(
                    RetrievalResult(
                        id=node_id,
                        text=text,
                        score=0.0,
                        source="graph",
                        entity_id=node_id,
                        metadata={
                            "name": name,
                            "description": description,
                            "rel_type": rel_type,
                            "rel_source": rel_source,
                            "rel_target": rel_target,
                        },
                    )
                )
        return results

    async def search_by_name(
        self, query: str, limit: int = 10
    ) -> list[RetrievalResult]:
        cypher = (
            "MATCH (e:Entity) "
            "WHERE e.name CONTAINS $query "
            "RETURN e.id AS node_id, e.name AS name, e.description AS description "
            "LIMIT $limit"
        )
        results: list[RetrievalResult] = []
        async with self._driver.session(database=self._database) as session:
            records = await session.run(cypher, query=query, limit=limit)
            async for record in records:
                node_id = record["node_id"]
                name = record["name"] or ""
                description = record["description"] or ""
                text = f"{name}: {description}" if description else name
                results.append(
                    RetrievalResult(
                        id=node_id,
                        text=text,
                        score=0.0,
                        source="graph",
                        entity_id=node_id,
                        metadata={
                            "name": name,
                            "description": description,
                        },
                    )
                )
        return results

    async def close(self) -> None:
        if self._owns_driver:
            await self._driver.close()
