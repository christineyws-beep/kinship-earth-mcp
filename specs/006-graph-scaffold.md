# Spec 006: Knowledge Graph Scaffold

> Phase 4.1 — Graph Infrastructure (Part 1)
> Priority: P0 (core moat)
> Estimated effort: 1 session
> Dependency: Spec 001 (conversation storage) should be done first
> GitHub Issue: #8

## Objective

Stand up the knowledge graph infrastructure: entity ontology, relationship types, and a lightweight graph engine. This is the foundation for the emergent ecological memory system.

## Key Decision: Graph Engine

**Use `networkx` + SQLite for Phase 4.1, not Neo4j/Graphiti.**

Rationale:
- Zero infrastructure dependency (no database server to run)
- Ships with the MCP server (just a Python dependency)
- Sufficient for 10K-100K entities (our Phase 4 target)
- Can migrate to Neo4j/Graphiti later if we outgrow it
- Graphiti is excellent but adds complexity we don't need yet

We persist the graph to SQLite (same DB as conversations) and load it into networkx at server startup.

## What to Build

### 1. Entity & Relationship Models

Create `shared/src/kinship_shared/graph_schema.py`:

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Literal

EntityType = Literal[
    "species",       # A biological species (taxon)
    "location",      # A geographic point or named place
    "watershed",     # A hydrological unit
    "neon_site",     # A NEON monitoring site
    "researcher",    # A user of the system
    "query",         # A search query (what was asked)
    "finding",       # A discovered fact or pattern
    "data_source",   # An ecological data source (OBIS, ERA5, etc.)
]

RelationshipType = Literal[
    "OBSERVED_AT",       # species → location
    "INHABITS",          # species → ecosystem/watershed
    "DRAINS_TO",         # location → watershed
    "QUERIED_BY",        # query → researcher
    "QUERIED_ABOUT",     # query → species or location
    "FOUND_IN",          # finding → query (provenance)
    "CORRELATES_WITH",   # species ↔ species (co-occurrence)
    "MONITORED_BY",      # location → neon_site
    "SOURCED_FROM",      # finding → data_source
    "SIMILAR_TO",        # location ↔ location (ecological similarity)
]

class GraphEntity(BaseModel):
    id: str                     # e.g. "species:Delphinus_delphis" or "location:41.5_-70.7"
    entity_type: EntityType
    name: str                   # Display name
    properties: dict            # Type-specific attributes
    created_at: datetime
    updated_at: datetime
    mention_count: int = 1      # How many times this entity has appeared

class GraphRelationship(BaseModel):
    source_id: str              # Entity ID
    target_id: str              # Entity ID
    relationship_type: RelationshipType
    properties: dict            # Relationship-specific data (e.g., observation count, date range)
    weight: float = 1.0         # Strength of relationship (increases with evidence)
    first_seen: datetime
    last_seen: datetime
    evidence_count: int = 1     # Number of observations supporting this relationship

class TemporalFact(BaseModel):
    """A fact with a validity window — can be superseded but not deleted."""
    id: str
    entity_id: str
    fact_type: str              # e.g., "temperature_normal", "species_range", "population_estimate"
    value: dict                 # The fact data
    valid_from: datetime
    valid_until: datetime | None  # None = still current
    source: str                 # Where this fact came from
    superseded_by: str | None   # ID of the fact that replaced this one
```

### 2. Graph Store

Create `shared/src/kinship_shared/graph_store.py`:

```python
class EcologicalGraph:
    """In-memory knowledge graph backed by SQLite for persistence."""
    
    def __init__(self, db_path: str | None = None):
        # db_path defaults to ~/.kinship-earth/graph.db
        self._graph = networkx.DiGraph()
        ...
    
    async def initialize(self) -> None:
        """Create tables and load existing graph from SQLite."""
    
    # Entity operations
    async def add_entity(self, entity: GraphEntity) -> None: ...
    async def get_entity(self, entity_id: str) -> GraphEntity | None: ...
    async def find_entities(self, entity_type: EntityType, name_pattern: str) -> list[GraphEntity]: ...
    
    # Relationship operations
    async def add_relationship(self, rel: GraphRelationship) -> None: ...
    async def get_relationships(self, entity_id: str, rel_type: RelationshipType | None = None) -> list[GraphRelationship]: ...
    
    # Query operations
    async def get_neighbors(self, entity_id: str, depth: int = 1) -> dict:
        """Get connected entities up to N hops away."""
    
    async def find_co_occurring_species(self, species_id: str, min_evidence: int = 2) -> list[dict]:
        """Find species frequently observed at the same locations."""
    
    async def get_location_interest(self, lat: float, lng: float, radius_km: float) -> dict:
        """Get research interest metrics for a location (query count, researchers, species queried)."""
    
    # Temporal facts
    async def add_fact(self, fact: TemporalFact) -> None: ...
    async def get_current_facts(self, entity_id: str) -> list[TemporalFact]: ...
    async def get_facts_at_time(self, entity_id: str, at: datetime) -> list[TemporalFact]: ...
    
    # Persistence
    async def save(self) -> None:
        """Persist current graph state to SQLite."""
    
    async def load(self) -> None:
        """Load graph state from SQLite into networkx."""
    
    # Stats
    def entity_count(self) -> int: ...
    def relationship_count(self) -> int: ...
    def fact_count(self) -> int: ...
```

### 3. SQLite Schema for Graph Persistence

Tables in `~/.kinship-earth/graph.db`:
- `entities`: id, entity_type, name, properties (JSON), created_at, updated_at, mention_count
- `relationships`: source_id, target_id, relationship_type, properties (JSON), weight, first_seen, last_seen, evidence_count
- `temporal_facts`: id, entity_id, fact_type, value (JSON), valid_from, valid_until, source, superseded_by
- Indexes: entity_type, relationship (source_id, target_id), temporal_facts (entity_id, valid_until)

### 4. Initialize Graph in Orchestrator

Modify `servers/orchestrator/src/kinship_orchestrator/server.py`:
- Import and initialize `EcologicalGraph`
- Call `graph.initialize()` at startup (load from SQLite)
- Make `_graph` available to tools (but don't wire into tools yet — that's spec 008)

## What NOT to Build

- No entity extraction pipeline yet (that's spec 007)
- No memory-aware MCP tools yet (that's spec 008)
- No memory-informed ranking yet (that's spec 009)
- No Neo4j/Graphiti integration (future scale-up)

## Tests to Write

Create `shared/tests/test_graph.py`:

1. `test_add_and_get_entity` — round-trip entity storage
2. `test_add_relationship` — link two entities, verify edge exists
3. `test_get_neighbors` — verify depth-1 and depth-2 traversal
4. `test_find_co_occurring_species` — add species at same location, verify co-occurrence
5. `test_location_interest` — add queries for a location, verify interest metrics
6. `test_temporal_fact_current` — add fact, verify it's current
7. `test_temporal_fact_superseded` — add new fact, verify old one is superseded
8. `test_get_facts_at_time` — verify historical fact retrieval
9. `test_save_and_load` — persist to SQLite, create new instance, verify data
10. `test_entity_mention_count_increments` — add same entity twice, count = 2

## Verification

```bash
uv run --package kinship-orchestrator pytest shared/tests/test_graph.py -v

# Server still loads
uv run --package kinship-orchestrator python -c "from kinship_orchestrator.server import mcp; print('OK')"
```

## Commit Message Template

```
Add ecological knowledge graph scaffold with SQLite persistence

Implements Phase 4.1 graph infrastructure (Issue #8):
- Entity ontology: species, location, watershed, neon_site, researcher, query, finding
- Relationship types: OBSERVED_AT, INHABITS, CORRELATES_WITH, QUERIED_BY, etc.
- TemporalFact model with validity windows
- EcologicalGraph with networkx in-memory + SQLite persistence
- Co-occurrence, location interest, and temporal fact queries
- 10 new tests

Spec: specs/006-graph-scaffold.md
```

## Files to Create/Modify

| Action | File |
|--------|------|
| Create | `shared/src/kinship_shared/graph_schema.py` |
| Create | `shared/src/kinship_shared/graph_store.py` |
| Create | `shared/tests/test_graph.py` |
| Modify | `shared/src/kinship_shared/__init__.py` (export graph classes) |
| Modify | `shared/pyproject.toml` (add networkx, aiosqlite if not already) |
| Modify | `servers/orchestrator/src/kinship_orchestrator/server.py` (initialize graph) |
| Modify | `specs/QUEUE.md` (mark this spec done) |
| Modify | `ROADMAP.md` (check off completed items) |
