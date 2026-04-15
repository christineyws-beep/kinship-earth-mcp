# Spec 001: Conversation Storage Layer

> Phase 3.2 — Conversation Persistence
> Priority: P0 (prerequisite for memory graph)
> Estimated effort: 1 session

## Objective

Add a conversation storage layer so every MCP tool invocation and its results can be persisted. This is the raw material for the memory graph — without stored conversations, the graph has nothing to learn from.

## What to Build

### 1. Conversation Storage Schema

Create `shared/src/kinship_shared/storage.py` with Pydantic models:

```python
class ConversationTurn(BaseModel):
    id: str                          # UUID
    conversation_id: str             # Groups turns into a session
    user_id: str | None              # None until auth is added (spec 002)
    timestamp: datetime
    tool_name: str                   # e.g. "ecology_search"
    tool_params: dict                # The input parameters
    tool_result_summary: dict        # Condensed result (not full payload)
    location: Location | None        # Extracted from params if lat/lon present
    taxa_mentioned: list[str]        # Scientific names extracted from params/results
    feedback: str | None             # User feedback (thumbs up/down/text)
    feedback_at: datetime | None

class ConversationStore(ABC):
    """Abstract interface for conversation persistence."""
    async def store_turn(self, turn: ConversationTurn) -> None: ...
    async def get_conversation(self, conversation_id: str) -> list[ConversationTurn]: ...
    async def get_turns_by_location(self, lat: float, lng: float, radius_km: float, limit: int = 50) -> list[ConversationTurn]: ...
    async def get_turns_by_taxon(self, scientific_name: str, limit: int = 50) -> list[ConversationTurn]: ...
    async def add_feedback(self, turn_id: str, feedback: str) -> None: ...
```

### 2. SQLite Implementation

Create `shared/src/kinship_shared/storage_sqlite.py`:

- Implement `SQLiteConversationStore(ConversationStore)`
- Database file at `~/.kinship-earth/conversations.db` (configurable via env var `KINSHIP_DB_PATH`)
- Use `aiosqlite` for async SQLite access
- Auto-create tables on first use
- Schema:
  - `conversations` table: id, created_at
  - `turns` table: id, conversation_id, user_id, timestamp, tool_name, tool_params (JSON), tool_result_summary (JSON), lat, lng, taxa_mentioned (JSON array), feedback, feedback_at
  - Index on (lat, lng) for geo queries
  - Index on tool_name for analytics
  - Full-text search index on taxa_mentioned

### 3. Storage Middleware in Orchestrator

Modify `servers/orchestrator/src/kinship_orchestrator/server.py`:

- Import and initialize the SQLiteConversationStore
- Create a helper function `_store_turn(tool_name, params, result)` that:
  - Extracts lat/lon from params if present
  - Extracts scientific names from params and results
  - Condenses the result to a summary (species count, source list, etc. — not the full payload)
  - Stores asynchronously (fire-and-forget, don't slow down tool responses)
- Call `_store_turn()` at the end of each tool function
- Storage failures should log warnings but never break tool responses

### 4. Feedback MCP Tool

Add to the orchestrator:

```python
@mcp.tool()
async def ecology_feedback(
    turn_id: str,
    feedback: str,  # "helpful", "not_helpful", or free text
) -> dict:
    """Provide feedback on a previous query result."""
```

### 5. Add `aiosqlite` Dependency

Add `aiosqlite>=0.20` to `shared/pyproject.toml` dependencies.

## What NOT to Build

- No Supabase/Postgres yet (that's spec 003)
- No auth/user_id yet (that's spec 002)
- No UI for viewing conversations
- No conversation export (already handled by data_export prompt)

## Tests to Write

Create `shared/tests/test_storage.py`:

1. `test_store_and_retrieve_turn` — round-trip a turn to SQLite and read it back
2. `test_get_turns_by_location` — store turns with different locations, query by proximity
3. `test_get_turns_by_taxon` — store turns mentioning different species, query by name
4. `test_add_feedback` — store a turn, add feedback, verify it's persisted
5. `test_storage_failure_does_not_break_tool` — mock a storage error, verify tool still returns data
6. `test_concurrent_writes` — write 10 turns concurrently, verify all stored

Create `servers/orchestrator/tests/test_feedback_tool.py`:

1. `test_feedback_tool_registered` — verify ecology_feedback is in mcp tools
2. `test_feedback_stores_correctly` — call ecology_feedback and verify storage

## Verification

```bash
# All existing tests still pass
uv run --package kinship-orchestrator pytest servers/orchestrator/tests/test_cross_source.py -v -k "validation or bad_date or invalid"

# New storage tests pass
uv run --package kinship-orchestrator pytest shared/tests/test_storage.py -v

# New feedback tool tests pass
uv run --package kinship-orchestrator pytest servers/orchestrator/tests/test_feedback_tool.py -v

# Server still loads with correct counts
uv run --package kinship-orchestrator python -c "from kinship_orchestrator.server import mcp; print(f'Tools: {len(mcp._tool_manager._tools)}'); print(f'Prompts: {len(mcp._prompt_manager._prompts)}')"
# Expected: Tools: 5 (was 4 + ecology_feedback), Prompts: 4
```

## Commit Message Template

```
Add conversation storage layer with SQLite backend

Implements Phase 3.2 conversation persistence:
- ConversationTurn schema and ConversationStore interface
- SQLiteConversationStore with geo and taxon indexes
- Storage middleware in orchestrator (fire-and-forget)
- ecology_feedback tool for per-turn feedback
- 8 new tests

Spec: specs/001-conversation-storage.md
```

## Files to Create/Modify

| Action | File |
|--------|------|
| Create | `shared/src/kinship_shared/storage.py` |
| Create | `shared/src/kinship_shared/storage_sqlite.py` |
| Create | `shared/tests/test_storage.py` |
| Create | `servers/orchestrator/tests/test_feedback_tool.py` |
| Modify | `shared/src/kinship_shared/__init__.py` (export new classes) |
| Modify | `shared/pyproject.toml` (add aiosqlite) |
| Modify | `servers/orchestrator/src/kinship_orchestrator/server.py` (storage middleware + feedback tool) |
| Modify | `specs/QUEUE.md` (mark this spec done) |
| Modify | `ROADMAP.md` (check off completed items) |
