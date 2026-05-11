# Spec 007: Conversation → Graph Extraction Pipeline

> Phase 4.1 — Graph Infrastructure (Part 2)
> Priority: P0
> Estimated effort: 1 session
> Dependency: Specs 001 (storage) + 006 (graph scaffold) must be done first
> GitHub Issue: #8

## Objective

Build the pipeline that converts stored conversations into knowledge graph entities and relationships. Every time a user queries species, locations, or climate data, the system should automatically extract entities and relationships and upsert them into the graph.

## What to Build

### 1. Entity Extractor

Create `shared/src/kinship_shared/graph_extract.py`:

```python
class EntityExtractor:
    """Extracts entities and relationships from tool calls and results."""
    
    def extract_from_turn(self, turn: ConversationTurn, result: dict) -> ExtractedGraph:
        """Extract entities and relationships from a single conversation turn.
        
        Returns an ExtractedGraph containing entities and relationships
        to be upserted into the knowledge graph.
        """

class ExtractedGraph(BaseModel):
    entities: list[GraphEntity]
    relationships: list[GraphRelationship]
    facts: list[TemporalFact]
```

Extraction rules per tool:

**ecology_search results:**
- For each observation:
  - Entity: species (from taxon info)
  - Entity: location (from lat/lng, with reverse-geocoded name if available)
  - Relationship: species OBSERVED_AT location (with observation date, count)
- For each NEON site:
  - Entity: neon_site
  - Relationship: location MONITORED_BY neon_site
- Entity: query (the search itself)
- Relationship: query QUERIED_ABOUT species (if taxon search)
- Relationship: query QUERIED_ABOUT location (if geo search)

**ecology_get_environmental_context results:**
- Entity: location
- Entities: nearby NEON sites
- Relationships: location MONITORED_BY neon_site
- Facts: climate normals as TemporalFacts (temperature, precip for the queried period)

**ecology_whats_around_me results:**
- Same as ecology_search

**ecology_biodiversity_assessment results (if spec 004 done):**
- Same as ecology_search + soil facts as TemporalFacts

### 2. Entity ID Generation

Consistent, deterministic IDs:
- Species: `species:{scientific_name}` (lowercased, spaces to underscores)
- Location: `location:{lat:.2f}_{lng:.2f}` (rounded to ~1km precision)
- NEON site: `neon:{site_code}`
- Query: `query:{uuid}` (from ConversationTurn.id)
- Researcher: `user:{user_id}`
- Data source: `source:{adapter_id}`

### 3. Graph Upsert Logic

When upserting, handle duplicates intelligently:
- **Entities**: If entity already exists, increment `mention_count` and update `updated_at`. Merge properties (don't overwrite, extend).
- **Relationships**: If relationship already exists, increment `evidence_count`, increase `weight`, update `last_seen`. Don't create duplicates.
- **Co-occurrence detection**: When two species are observed at the same location (within 10km), create/strengthen a CORRELATES_WITH relationship between them.

### 4. Wire Into Storage Middleware

Modify the storage middleware in `server.py` (from spec 001):

```python
async def _store_turn(tool_name: str, params: dict, result: dict) -> None:
    # ... existing storage logic ...
    
    # Extract and upsert to graph
    if _graph is not None:
        extracted = _extractor.extract_from_turn(turn, result)
        for entity in extracted.entities:
            await _graph.add_entity(entity)
        for rel in extracted.relationships:
            await _graph.add_relationship(rel)
        for fact in extracted.facts:
            await _graph.add_fact(fact)
        await _graph.save()
```

### 5. Graph Stats Tool

Add a simple tool to see graph growth:

```python
@mcp.tool()
async def ecology_graph_stats() -> dict:
    """Show knowledge graph statistics.
    
    Returns entity counts, relationship counts, and top entities
    by mention count. Useful for understanding how the ecological
    knowledge base is growing.
    """
```

Returns:
```json
{
  "entities": {"total": 234, "by_type": {"species": 89, "location": 102, "neon_site": 23, "query": 20}},
  "relationships": {"total": 567, "by_type": {"OBSERVED_AT": 312, "MONITORED_BY": 45, ...}},
  "facts": {"total": 78, "current": 72, "superseded": 6},
  "top_species": [{"id": "species:delphinus_delphis", "mentions": 12}],
  "top_locations": [{"id": "location:41.50_-70.70", "mentions": 8}],
  "graph_age": "3 days"
}
```

## What NOT to Build

- No LLM-based entity extraction (keep it deterministic and fast)
- No external NER or NLP services
- No memory-aware tools yet (that's spec 008)
- No cross-user graph queries yet (that's spec 008)

## Tests to Write

Create `shared/tests/test_graph_extract.py`:

1. `test_extract_species_from_search` — mock search result, verify species entity extracted
2. `test_extract_location_from_search` — verify location entity with correct ID format
3. `test_extract_observed_at_relationship` — verify species→location relationship
4. `test_extract_neon_site` — verify NEON site entity and MONITORED_BY relationship
5. `test_extract_query_entity` — verify query entity with QUERIED_ABOUT relationships
6. `test_co_occurrence_detection` — two species at same location create CORRELATES_WITH
7. `test_upsert_increments_mention_count` — same species extracted twice, count = 2
8. `test_upsert_strengthens_relationship` — same relationship extracted twice, weight increases
9. `test_climate_facts_extracted` — verify TemporalFacts from environmental context
10. `test_graph_stats_tool_registered` — ecology_graph_stats in mcp tools

## Verification

```bash
uv run --package kinship-orchestrator pytest shared/tests/test_graph_extract.py -v
uv run --package kinship-orchestrator pytest shared/tests/test_graph.py -v  # Still pass

# Server loads
uv run --package kinship-orchestrator python -c "from kinship_orchestrator.server import mcp; print(f'Tools: {len(mcp._tool_manager._tools)}')"
```

## Commit Message Template

```
Add conversation-to-graph extraction pipeline

Implements Phase 4.1 graph pipeline (Issue #8):
- EntityExtractor: deterministic extraction from tool results
- Entity ID generation (species, location, neon_site, query)
- Upsert logic with mention counting and relationship strengthening
- Co-occurrence detection for species at same locations
- Climate facts as TemporalFacts
- ecology_graph_stats tool for monitoring graph growth
- Wired into storage middleware (fire-and-forget)
- 10 new tests

Spec: specs/007-graph-pipeline.md
```

## Files to Create/Modify

| Action | File |
|--------|------|
| Create | `shared/src/kinship_shared/graph_extract.py` |
| Create | `shared/tests/test_graph_extract.py` |
| Modify | `shared/src/kinship_shared/__init__.py` (export extractor) |
| Modify | `servers/orchestrator/src/kinship_orchestrator/server.py` (wire pipeline + stats tool) |
| Modify | `specs/QUEUE.md` (mark this spec done) |
| Modify | `ROADMAP.md` (check off completed items) |
