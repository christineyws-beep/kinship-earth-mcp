# Spec 010: Memory-Informed Ranking + Integration Test

> Phase 4.3 — Memory-Informed Ranking
> Priority: P1
> Estimated effort: 1 session
> Dependency: Specs 006-008 (graph + pipeline + memory tools) — DONE or in progress
> GitHub Issue: #8

## Objective

Enhance the existing federated ranking system to incorporate knowledge graph signals. Observations about species/locations with active research interest should score higher. Add an end-to-end integration test that validates the full pipeline: query → store → extract → graph → recall.

## What to Build

### 1. Memory-Informed Ranking Component

Modify `shared/src/kinship_shared/ranking.py`:

Add a new optional `memory_relevance` component to the scoring formula:

**Current formula:**
```
score = 0.35 × geo_distance + 0.30 × taxon_match + 0.15 × temporal + 0.20 × quality
```

**New formula (when graph available):**
```
score = 0.30 × geo_distance + 0.25 × taxon_match + 0.15 × temporal + 0.15 × quality + 0.15 × memory_relevance
```

`memory_relevance` (0-1) is computed from:
- Entity mention count (normalized to 0-1 by dividing by max mention count in graph)
- Co-occurrence network size (species with more co-occurring species score higher)
- Location research interest (locations queried more often score higher)
- Recency of last mention (entities mentioned recently score higher than stale ones)

```python
def compute_memory_relevance(
    observation: EcologicalObservation,
    graph: EcologicalGraph | None,
) -> float:
    """Compute memory relevance score (0-1) from knowledge graph."""
    if graph is None or graph.entity_count() == 0:
        return 0.0  # No memory available, neutral score

    score = 0.0
    components = 0

    # Species mention count
    if observation.taxon and observation.taxon.scientific_name:
        species_id = make_species_id(observation.taxon.scientific_name)
        entity = graph._entities.get(species_id)
        if entity:
            # Normalize: log scale, cap at 1.0
            import math
            score += min(1.0, math.log1p(entity.mention_count) / 5.0)
            components += 1

    # Location research interest
    if observation.location.lat and observation.location.lng:
        loc_id = make_location_id(observation.location.lat, observation.location.lng)
        entity = graph._entities.get(loc_id)
        if entity:
            score += min(1.0, math.log1p(entity.mention_count) / 5.0)
            components += 1

    return score / max(components, 1)
```

### 2. Wire Memory Ranking Into Search

Modify `shared/src/kinship_shared/ecology_tools.py` `run_search()`:
- Accept optional `graph` parameter
- After scoring with `score_observation()`, if graph is provided, compute `memory_relevance` and add to the relevance dict
- Re-weight the composite score to include memory component

Modify `servers/orchestrator/src/kinship_orchestrator/server.py`:
- Pass `_graph` to `run_search()` calls (if initialized)

### 3. "You Might Also Want to Know" Suggestions

Add to the search result:
```python
# After scoring, if graph is available:
suggestions = []
for occ in top_3_species:
    co = await graph.find_co_occurring_species(species_id, min_evidence=2)
    for sp in co[:3]:
        suggestions.append({
            "type": "co_occurring_species",
            "species": sp["name"],
            "reason": f"Frequently observed at the same locations ({sp['co_occurrence_count']} shared locations)",
        })

result["suggestions"] = suggestions
```

### 4. End-to-End Integration Test

Create `servers/orchestrator/tests/test_integration.py`:

A single test that validates the full pipeline:

```python
async def test_full_pipeline():
    """End-to-end: search → store → extract → graph → recall → enhanced ranking."""
    # 1. Run ecology_search (with real or mock data)
    # 2. Verify conversation turn was stored
    # 3. Verify graph entities were extracted
    # 4. Run ecology_memory_recall for the same location
    # 5. Verify memory contains the species from step 1
    # 6. Run ecology_search again — verify memory_relevance > 0
    # 7. Run ecology_graph_stats — verify entity counts
```

## What NOT to Build

- No A/B testing infrastructure (just the scoring change)
- No ML-based ranking (keep it deterministic)
- No cross-user ranking signals yet (per-user graph only for now)

## Tests to Write

Create `shared/tests/test_memory_ranking.py`:

1. `test_memory_relevance_zero_without_graph` — no graph returns 0.0
2. `test_memory_relevance_increases_with_mentions` — more mentions = higher score
3. `test_memory_relevance_capped_at_one` — score never exceeds 1.0
4. `test_ranking_weights_sum_to_one` — verify new formula weights add up

Create `servers/orchestrator/tests/test_integration.py`:

5. `test_full_pipeline_search_to_recall` — end-to-end pipeline test

## Verification

```bash
uv run --package kinship-orchestrator pytest shared/tests/test_memory_ranking.py -v
uv run --package kinship-orchestrator pytest servers/orchestrator/tests/test_integration.py -v

# All existing tests still pass
uv run --package kinship-orchestrator pytest servers/orchestrator/tests/test_prompts.py shared/tests/ -v
```

## Commit Message Template

```
Add memory-informed ranking and end-to-end integration test

Implements Phase 4.3 (Issue #8):
- memory_relevance scoring component (mention count + research interest)
- Re-weighted ranking formula: geo 0.30 + taxon 0.25 + temporal 0.15 + quality 0.15 + memory 0.15
- "You might also want to know" suggestions from co-occurrence graph
- End-to-end integration test: search → store → extract → recall
- 5 new tests

Spec: specs/010-memory-ranking.md
```

## Files to Create/Modify

| Action | File |
|--------|------|
| Create | `shared/tests/test_memory_ranking.py` |
| Create | `servers/orchestrator/tests/test_integration.py` |
| Modify | `shared/src/kinship_shared/ranking.py` (add memory_relevance) |
| Modify | `shared/src/kinship_shared/ecology_tools.py` (pass graph, add suggestions) |
| Modify | `servers/orchestrator/src/kinship_orchestrator/server.py` (pass graph to search) |
| Modify | `specs/QUEUE.md` (mark this spec done) |
| Modify | `ROADMAP.md` (check off Milestone 4.3 items) |
