# Spec 003: Auth + Storage Integration

> Phase 3.1 + 3.2 — Wire Auth Into Conversations
> Priority: P0
> Estimated effort: 1 session
> Dependency: Specs 001 + 002 must be done first

## Objective

Wire the auth layer (spec 002) into the conversation storage layer (spec 001) so that every stored conversation turn is associated with a user identity. Add a conversation history tool so users can see their past queries.

## What to Build

### 1. Wire User Identity Into Storage

Modify `servers/orchestrator/src/kinship_orchestrator/server.py`:

- Update `_store_turn()` to pull `user_id` from `_get_current_user()`
- If no auth, use `"anonymous"` as user_id (still store the turn)
- Pass user's BYOK keys to adapters when available

### 2. Conversation History Tool

Add to orchestrator:

```python
@mcp.tool()
async def ecology_my_history(
    limit: int = 20,
    taxon_filter: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float | None = None,
) -> dict:
    """View your past ecological queries.
    
    Returns your recent query history, optionally filtered by species
    or location. Useful for picking up where you left off or seeing
    what you've explored.
    """
```

Returns:
```json
{
  "turns": [
    {
      "id": "uuid",
      "timestamp": "2026-04-18T...",
      "tool_name": "ecology_search",
      "summary": "Searched for Delphinus delphis near Woods Hole (3 results)",
      "location": {"lat": 41.5, "lon": -70.7},
      "taxa": ["Delphinus delphis"],
      "feedback": "helpful"
    }
  ],
  "total_queries": 47,
  "unique_species_queried": 12,
  "unique_locations_queried": 8
}
```

### 3. Conversation Summary Generator

Create `shared/src/kinship_shared/summarize.py`:

```python
def summarize_search_result(tool_name: str, params: dict, result: dict) -> dict:
    """Condense a full tool result into a storage-friendly summary.
    
    Extracts key metrics without storing the full payload:
    - species_count, source_count, neon_sites_found
    - top 3 species by relevance
    - climate data available (bool)
    - result quality (avg relevance score)
    """
```

This replaces the ad-hoc summary logic and ensures consistent, useful summaries across all tools.

### 4. Usage Dashboard Tool

Add to orchestrator:

```python
@mcp.tool()
async def ecology_my_usage() -> dict:
    """Check your usage and rate limit status.
    
    Returns your current query count, daily limit, tier, and
    stored API keys (names only, not values).
    """
```

Returns:
```json
{
  "user": {
    "email": "researcher@university.edu",
    "tier": "free",
    "queries_today": 12,
    "queries_limit": 50,
    "api_keys_configured": ["ebird"]
  },
  "history_summary": {
    "total_queries": 47,
    "first_query": "2026-04-16",
    "unique_species": 12,
    "unique_locations": 8
  }
}
```

## What NOT to Build

- No Supabase migration yet (still SQLite for dev)
- No conversation export (handled by data_export prompt)
- No admin analytics
- No conversation deletion (that's a future privacy spec)

## Tests to Write

Create `servers/orchestrator/tests/test_history.py`:

1. `test_ecology_my_history_registered` — tool is in mcp tools
2. `test_history_returns_empty_for_new_user` — no turns yet, returns empty list
3. `test_history_after_search` — run ecology_search, verify it appears in history
4. `test_history_taxon_filter` — filter by species name
5. `test_history_location_filter` — filter by lat/lon/radius
6. `test_usage_tool_registered` — ecology_my_usage is in mcp tools
7. `test_summarize_search_result` — verify summary extraction from full result

## Verification

```bash
# All tests pass
uv run --package kinship-orchestrator pytest servers/orchestrator/tests/ -v -k "not (climate or dolphin or cetac or wind_river or woods_hole or parallel or cross_persona or marine)"

# Server loads with new tool count
uv run --package kinship-orchestrator python -c "from kinship_orchestrator.server import mcp; print(f'Tools: {len(mcp._tool_manager._tools)}')"
# Expected: Tools: 8 (was 6 + ecology_my_history + ecology_my_usage)
```

## Commit Message Template

```
Wire auth into conversation storage, add history and usage tools

Integrates Phase 3.1 auth with Phase 3.2 conversation storage:
- User identity attached to every stored conversation turn
- ecology_my_history tool for viewing past queries (with filters)
- ecology_my_usage tool for checking rate limits and tier
- Result summarization for storage-friendly conversation logs
- 7 new tests

Spec: specs/003-auth-integration.md
```

## Files to Create/Modify

| Action | File |
|--------|------|
| Create | `shared/src/kinship_shared/summarize.py` |
| Create | `servers/orchestrator/tests/test_history.py` |
| Modify | `shared/src/kinship_shared/__init__.py` (export summarize) |
| Modify | `servers/orchestrator/src/kinship_orchestrator/server.py` (wire auth + add tools) |
| Modify | `specs/QUEUE.md` (mark this spec done) |
| Modify | `ROADMAP.md` (check off completed items) |
