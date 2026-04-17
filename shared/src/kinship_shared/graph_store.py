"""
In-memory knowledge graph backed by SQLite for persistence.

Uses networkx for graph operations and aiosqlite for durable storage.
Designed for 10K-100K entities (Phase 4 scale). Can migrate to
Neo4j/Graphiti if we outgrow it.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite

try:
    import networkx as nx
except ImportError:
    nx = None  # type: ignore[assignment]

from .graph_schema import (
    EntityType,
    GraphEntity,
    GraphRelationship,
    RelationshipType,
    TemporalFact,
)

logger = logging.getLogger(__name__)

_DEFAULT_DB_DIR = Path.home() / ".kinship-earth"
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "graph.db"

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    properties TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    mention_count INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS relationships (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    properties TEXT NOT NULL DEFAULT '{}',
    weight REAL NOT NULL DEFAULT 1.0,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    evidence_count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (source_id, target_id, relationship_type)
);

CREATE TABLE IF NOT EXISTS temporal_facts (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    fact_type TEXT NOT NULL,
    value TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_until TEXT,
    source TEXT NOT NULL,
    superseded_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_id);
CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_id);
CREATE INDEX IF NOT EXISTS idx_facts_entity ON temporal_facts(entity_id);
CREATE INDEX IF NOT EXISTS idx_facts_current ON temporal_facts(entity_id, valid_until);
"""


class EcologicalGraph:
    """In-memory knowledge graph backed by SQLite for persistence."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or os.environ.get(
            "KINSHIP_GRAPH_DB_PATH", str(_DEFAULT_DB_PATH)
        )
        if nx is not None:
            self._graph: nx.DiGraph = nx.DiGraph()
        else:
            self._graph = None  # type: ignore[assignment]
        self._entities: dict[str, GraphEntity] = {}
        self._facts: dict[str, TemporalFact] = {}

    async def initialize(self) -> None:
        """Create tables and load existing graph from SQLite."""
        db_dir = Path(self._db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(_CREATE_TABLES)
            await db.commit()

        await self.load()

    # ----- Entity operations -----

    async def add_entity(self, entity: GraphEntity) -> None:
        """Add or update an entity. Increments mention_count on duplicates."""
        existing = self._entities.get(entity.id)
        if existing:
            existing.mention_count += 1
            existing.updated_at = datetime.now(tz=timezone.utc)
            # Merge properties (don't overwrite, extend)
            for k, v in entity.properties.items():
                if k not in existing.properties:
                    existing.properties[k] = v
            entity = existing

        self._entities[entity.id] = entity
        if self._graph is not None:
            self._graph.add_node(entity.id, **entity.model_dump(mode="json"))

    async def get_entity(self, entity_id: str) -> Optional[GraphEntity]:
        return self._entities.get(entity_id)

    async def find_entities(
        self, entity_type: EntityType, name_pattern: str = ""
    ) -> list[GraphEntity]:
        results = []
        pattern = name_pattern.lower()
        for entity in self._entities.values():
            if entity.entity_type == entity_type:
                if not pattern or pattern in entity.name.lower():
                    results.append(entity)
        return results

    # ----- Relationship operations -----

    async def add_relationship(self, rel: GraphRelationship) -> None:
        """Add or strengthen a relationship. Increments evidence_count on duplicates."""
        key = (rel.source_id, rel.target_id, rel.relationship_type)

        if self._graph is not None:
            existing_data = None
            if self._graph.has_edge(rel.source_id, rel.target_id):
                edge_data = self._graph.edges[rel.source_id, rel.target_id]
                if edge_data.get("relationship_type") == rel.relationship_type:
                    existing_data = edge_data

            if existing_data:
                existing_data["evidence_count"] = existing_data.get("evidence_count", 1) + 1
                existing_data["weight"] = existing_data.get("weight", 1.0) + 0.5
                existing_data["last_seen"] = datetime.now(tz=timezone.utc).isoformat()
            else:
                self._graph.add_edge(
                    rel.source_id, rel.target_id,
                    **rel.model_dump(mode="json"),
                )
        # Ensure both entities exist as nodes
        if self._graph is not None:
            if not self._graph.has_node(rel.source_id):
                self._graph.add_node(rel.source_id)
            if not self._graph.has_node(rel.target_id):
                self._graph.add_node(rel.target_id)

    async def get_relationships(
        self, entity_id: str, rel_type: Optional[RelationshipType] = None
    ) -> list[GraphRelationship]:
        results = []
        if self._graph is None:
            return results

        # Outgoing edges
        for _, target, data in self._graph.out_edges(entity_id, data=True):
            if rel_type and data.get("relationship_type") != rel_type:
                continue
            results.append(GraphRelationship(
                source_id=entity_id,
                target_id=target,
                relationship_type=data.get("relationship_type", "OBSERVED_AT"),
                properties=data.get("properties", {}),
                weight=data.get("weight", 1.0),
                evidence_count=data.get("evidence_count", 1),
            ))

        # Incoming edges
        for source, _, data in self._graph.in_edges(entity_id, data=True):
            if rel_type and data.get("relationship_type") != rel_type:
                continue
            results.append(GraphRelationship(
                source_id=source,
                target_id=entity_id,
                relationship_type=data.get("relationship_type", "OBSERVED_AT"),
                properties=data.get("properties", {}),
                weight=data.get("weight", 1.0),
                evidence_count=data.get("evidence_count", 1),
            ))

        return results

    # ----- Query operations -----

    async def get_neighbors(self, entity_id: str, depth: int = 1) -> dict:
        """Get connected entities up to N hops away."""
        if self._graph is None or entity_id not in self._graph:
            return {"entity_id": entity_id, "neighbors": [], "depth": depth}

        visited = set()
        current_level = {entity_id}
        all_neighbors = []

        for d in range(depth):
            next_level = set()
            for node in current_level:
                if node in visited:
                    continue
                visited.add(node)
                for neighbor in self._graph.successors(node):
                    if neighbor not in visited:
                        next_level.add(neighbor)
                        entity = self._entities.get(neighbor)
                        if entity:
                            all_neighbors.append({
                                "id": neighbor,
                                "name": entity.name,
                                "type": entity.entity_type,
                                "depth": d + 1,
                            })
                for neighbor in self._graph.predecessors(node):
                    if neighbor not in visited:
                        next_level.add(neighbor)
                        entity = self._entities.get(neighbor)
                        if entity:
                            all_neighbors.append({
                                "id": neighbor,
                                "name": entity.name,
                                "type": entity.entity_type,
                                "depth": d + 1,
                            })
            current_level = next_level

        return {"entity_id": entity_id, "neighbors": all_neighbors, "depth": depth}

    async def find_co_occurring_species(
        self, species_id: str, min_evidence: int = 2
    ) -> list[dict]:
        """Find species frequently observed at the same locations."""
        if self._graph is None:
            return []

        # Find all locations this species is observed at
        locations = set()
        for _, target, data in self._graph.out_edges(species_id, data=True):
            if data.get("relationship_type") == "OBSERVED_AT":
                locations.add(target)

        # Find other species at those locations
        co_occurring: dict[str, int] = {}
        for loc in locations:
            for source, _, data in self._graph.in_edges(loc, data=True):
                if data.get("relationship_type") == "OBSERVED_AT" and source != species_id:
                    entity = self._entities.get(source)
                    if entity and entity.entity_type == "species":
                        co_occurring[source] = co_occurring.get(source, 0) + 1

        results = []
        for sp_id, count in sorted(co_occurring.items(), key=lambda x: -x[1]):
            if count >= min_evidence:
                entity = self._entities.get(sp_id)
                results.append({
                    "species_id": sp_id,
                    "name": entity.name if entity else sp_id,
                    "co_occurrence_count": count,
                    "shared_locations": count,
                })

        return results

    async def get_location_interest(
        self, lat: float, lng: float, radius_km: float
    ) -> dict:
        """Get research interest metrics for a location."""
        from .graph_schema import make_location_id
        loc_id = make_location_id(lat, lng)

        entity = self._entities.get(loc_id)
        if not entity:
            return {
                "location_id": loc_id,
                "query_count": 0,
                "researchers": 0,
                "species_queried": 0,
            }

        rels = await self.get_relationships(loc_id)
        researchers = set()
        species = set()
        queries = 0

        for rel in rels:
            if rel.relationship_type == "QUERIED_ABOUT":
                queries += 1
            source_entity = self._entities.get(rel.source_id)
            target_entity = self._entities.get(rel.target_id)
            if source_entity and source_entity.entity_type == "researcher":
                researchers.add(rel.source_id)
            if target_entity and target_entity.entity_type == "species":
                species.add(rel.target_id)
            if source_entity and source_entity.entity_type == "species":
                species.add(rel.source_id)

        return {
            "location_id": loc_id,
            "mention_count": entity.mention_count,
            "query_count": queries,
            "researchers": len(researchers),
            "species_queried": len(species),
        }

    # ----- Temporal facts -----

    async def add_fact(self, fact: TemporalFact) -> None:
        """Add a temporal fact."""
        # Check for existing current facts of the same type
        for existing in list(self._facts.values()):
            if (
                existing.entity_id == fact.entity_id
                and existing.fact_type == fact.fact_type
                and existing.valid_until is None
            ):
                # Supersede old fact
                existing.valid_until = fact.valid_from
                existing.superseded_by = fact.id

        self._facts[fact.id] = fact

    async def get_current_facts(self, entity_id: str) -> list[TemporalFact]:
        return [
            f for f in self._facts.values()
            if f.entity_id == entity_id and f.valid_until is None
        ]

    async def get_facts_at_time(
        self, entity_id: str, at: datetime
    ) -> list[TemporalFact]:
        return [
            f for f in self._facts.values()
            if f.entity_id == entity_id
            and f.valid_from <= at
            and (f.valid_until is None or f.valid_until > at)
        ]

    # ----- Persistence -----

    async def save(self) -> None:
        """Persist current graph state to SQLite."""
        async with aiosqlite.connect(self._db_path) as db:
            # Save entities
            for entity in self._entities.values():
                await db.execute(
                    """INSERT OR REPLACE INTO entities
                    (id, entity_type, name, properties, created_at, updated_at, mention_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        entity.id, entity.entity_type, entity.name,
                        json.dumps(entity.properties), entity.created_at.isoformat(),
                        entity.updated_at.isoformat(), entity.mention_count,
                    ),
                )

            # Save relationships
            if self._graph is not None:
                for source, target, data in self._graph.edges(data=True):
                    await db.execute(
                        """INSERT OR REPLACE INTO relationships
                        (source_id, target_id, relationship_type, properties, weight,
                         first_seen, last_seen, evidence_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            source, target, data.get("relationship_type", ""),
                            json.dumps(data.get("properties", {})),
                            data.get("weight", 1.0),
                            data.get("first_seen", datetime.now(tz=timezone.utc).isoformat()),
                            data.get("last_seen", datetime.now(tz=timezone.utc).isoformat()),
                            data.get("evidence_count", 1),
                        ),
                    )

            # Save temporal facts
            for fact in self._facts.values():
                await db.execute(
                    """INSERT OR REPLACE INTO temporal_facts
                    (id, entity_id, fact_type, value, valid_from, valid_until, source, superseded_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        fact.id, fact.entity_id, fact.fact_type,
                        json.dumps(fact.value), fact.valid_from.isoformat(),
                        fact.valid_until.isoformat() if fact.valid_until else None,
                        fact.source, fact.superseded_by,
                    ),
                )

            await db.commit()

    async def load(self) -> None:
        """Load graph state from SQLite into memory."""
        async with aiosqlite.connect(self._db_path) as db:
            # Load entities
            cursor = await db.execute("SELECT * FROM entities")
            rows = await cursor.fetchall()
            for row in rows:
                entity = GraphEntity(
                    id=row[0], entity_type=row[1], name=row[2],
                    properties=json.loads(row[3]),
                    created_at=datetime.fromisoformat(row[4]),
                    updated_at=datetime.fromisoformat(row[5]),
                    mention_count=row[6],
                )
                self._entities[entity.id] = entity
                if self._graph is not None:
                    self._graph.add_node(entity.id, **entity.model_dump(mode="json"))

            # Load relationships
            cursor = await db.execute("SELECT * FROM relationships")
            rows = await cursor.fetchall()
            for row in rows:
                if self._graph is not None:
                    self._graph.add_edge(
                        row[0], row[1],
                        relationship_type=row[2],
                        properties=json.loads(row[3]),
                        weight=row[4],
                        first_seen=row[5],
                        last_seen=row[6],
                        evidence_count=row[7],
                    )

            # Load temporal facts
            cursor = await db.execute("SELECT * FROM temporal_facts")
            rows = await cursor.fetchall()
            for row in rows:
                fact = TemporalFact(
                    id=row[0], entity_id=row[1], fact_type=row[2],
                    value=json.loads(row[3]),
                    valid_from=datetime.fromisoformat(row[4]),
                    valid_until=datetime.fromisoformat(row[5]) if row[5] else None,
                    source=row[6], superseded_by=row[7],
                )
                self._facts[fact.id] = fact

        logger.info(
            "Loaded graph: %d entities, %d edges, %d facts",
            len(self._entities),
            self._graph.number_of_edges() if self._graph else 0,
            len(self._facts),
        )

    # ----- Stats -----

    def entity_count(self) -> int:
        return len(self._entities)

    def relationship_count(self) -> int:
        return self._graph.number_of_edges() if self._graph else 0

    def fact_count(self) -> int:
        return len(self._facts)
