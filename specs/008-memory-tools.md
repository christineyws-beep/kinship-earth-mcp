# Spec 008: Memory-Aware MCP Tools

> Phase 4.2 — Memory Tools
> Priority: P0 (core moat)
> Estimated effort: 1 session
> Dependency: Specs 006 + 007 (graph scaffold + pipeline) — DONE
> GitHub Issue: #8

## Objective

Add MCP tools that query the knowledge graph so agents and users can tap into the emergent ecological memory. These are the tools that make the system "get smarter" — surfacing connections, history, and patterns that no single query could reveal.

## Decisions Locked In

- Shared memory: **opt-in shared, per-user by default**
- CARE-flagged data: **never shared**
- Graph engine: **networkx + SQLite** (current)

## What to Build

### 1. Memory Recall Tool

```python
@mcp.tool()
async def ecology_memory_recall(
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float = 50,
    scientific_name: str | None = None,
    depth: int = 2,
) -> dict:
    """Recall what the knowledge graph knows about a location or species.

    Searches the ecological memory for entities, relationships, and
    temporal facts related to a location or species. Returns connected
    entities up to N hops away, co-occurring species, and historical
    facts.
    """
```

Implementation:
- If `scientific_name`: find species entity, get neighbors at `depth`, get co-occurring species, get current facts
- If `lat/lon`: find location entity, get neighbors, get location interest metrics, get current facts
- If both: do both and merge
- Return structured memory with entity counts, relationships, and facts

### 2. Memory Store Tool

```python
@mcp.tool()
async def ecology_memory_store(
    entity_type: Literal["finding", "species", "location"],
    name: str,
    description: str,
    lat: float | None = None,
    lon: float | None = None,
    scientific_name: str | None = None,
    share: bool = False,
) -> dict:
    """Explicitly save an insight to the ecological knowledge graph.

    Use this when an agent or researcher discovers something worth
    remembering — a confirmed spawning site, an unusual species
    observation, a climate correlation. The insight becomes a graph
    entity that enriches future queries.

    Args:
        entity_type: Type of entity to store ('finding', 'species', 'location').
        name: Short name for the entity (e.g. 'Coho spawning confirmed at Russian River tributary').
        description: Detailed description of the finding.
        lat: Latitude (required for location entities).
        lon: Longitude (required for location entities).
        scientific_name: Scientific name (required for species entities).
        share: If True, this finding is visible to other users (opt-in shared memory).
    """
```

Implementation:
- Create a `finding` entity with the description in properties
- Link to location and/or species if provided
- If `share=False`, tag with `user_id` in properties (only visible to that user)
- If `share=True`, tag as `shared=True` in properties

### 3. Related Queries Tool

```python
@mcp.tool()
async def ecology_related_queries(
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float = 50,
    scientific_name: str | None = None,
    limit: int = 10,
) -> dict:
    """Find related past queries from the knowledge graph.

    Shows what other queries have been made about this location or species.
    Surfaces patterns like "3 researchers queried this watershed last month"
    or "this species was also searched near 5 other locations."
    """
```

Implementation:
- Find the species or location entity in the graph
- Get all QUERIED_ABOUT relationships pointing to it
- Get the query entities, then follow QUERIED_BY to find researchers
- Return: related queries with timestamps, researcher count, other species/locations queried together

### 4. Emerging Patterns Tool

```python
@mcp.tool()
async def ecology_emerging_patterns(
    min_mentions: int = 3,
    limit: int = 10,
) -> dict:
    """Surface emerging patterns from the ecological knowledge graph.

    Finds entities and relationships that are growing in mention count,
    species with expanding co-occurrence networks, and locations with
    increasing research interest. These are signals of ecological
    change or research momentum.
    """
```

Implementation:
- Find entities with highest mention_count (growing interest)
- Find relationships with highest evidence_count (confirmed patterns)
- Find species with most co-occurring species (ecological hubs)
- Find locations with most queries (research hotspots)
- Return structured patterns with trends

## What NOT to Build

- No cross-user shared memory yet (just the `share` flag plumbing)
- No LLM-based pattern detection (keep it deterministic)
- No anomaly detection (that's Phase 5)

## Tests to Write

Create `servers/orchestrator/tests/test_memory_tools.py`:

1. `test_memory_recall_registered` — tool in mcp
2. `test_memory_store_registered` — tool in mcp
3. `test_related_queries_registered` — tool in mcp
4. `test_emerging_patterns_registered` — tool in mcp
5. `test_memory_store_creates_finding` — store a finding, verify it's in the graph
6. `test_memory_recall_by_species` — add species to graph, recall it
7. `test_memory_recall_by_location` — add location to graph, recall it
8. `test_emerging_patterns_finds_top_entities` — populate graph, verify top entities returned

## Verification

```bash
uv run --package kinship-orchestrator pytest servers/orchestrator/tests/test_memory_tools.py -v

# Server loads with new tool count
uv run --package kinship-orchestrator python -c "from kinship_orchestrator.server import mcp; print(f'Tools: {len(mcp._tool_manager._tools)}')"
# Expected: Tools: 17 (was 13 + 4 memory tools)
```

## Commit Message Template

```
Add memory-aware MCP tools for ecological knowledge graph

Implements Phase 4.2 memory tools (Issue #8):
- ecology_memory_recall: query the graph for a location or species
- ecology_memory_store: explicitly save findings to the graph
- ecology_related_queries: find past queries about the same entities
- ecology_emerging_patterns: surface growing trends and research hotspots
- Opt-in shared memory support (per-user by default)
- 8 new tests

Spec: specs/008-memory-tools.md
```

## Files to Create/Modify

| Action | File |
|--------|------|
| Create | `servers/orchestrator/tests/test_memory_tools.py` |
| Modify | `servers/orchestrator/src/kinship_orchestrator/server.py` (add 4 tools) |
| Modify | `specs/QUEUE.md` (mark this spec done) |
| Modify | `ROADMAP.md` (check off Milestone 4.2 items) |
