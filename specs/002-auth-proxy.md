# Spec 002: Authenticated MCP Proxy

> Phase 3.1 — Auth & Identity
> Priority: P0 (prerequisite for per-user memory)
> Estimated effort: 1 session
> Dependency: Spec 001 (conversation storage) should be done first

## Objective

Wrap the MCP server with an authenticated proxy layer so users have persistent identity. This enables per-user conversation history, metering, and eventually per-user memory graphs.

## What to Build

### 1. Auth Service Module

Create `servers/orchestrator/src/kinship_orchestrator/auth.py`:

```python
class User(BaseModel):
    id: str                    # UUID or provider ID
    email: str
    name: str | None
    provider: str              # "github" | "google"
    created_at: datetime
    api_keys: dict[str, str]   # BYOK: {"ebird": "key...", "xc": "key..."}
    tier: str                  # "free" | "pro"
    queries_today: int
    queries_limit: int         # 50 for free, unlimited for pro

class AuthManager:
    """Manages user authentication and session tokens."""
    
    def __init__(self, supabase_url: str | None, supabase_key: str | None):
        # If Supabase creds provided, use Supabase auth
        # Otherwise, fall back to local SQLite user store (dev mode)
        ...
    
    async def verify_token(self, token: str) -> User | None:
        """Verify a bearer token and return the user."""
        ...
    
    async def create_anonymous_user(self) -> User:
        """Create an anonymous user for unauthenticated access (free tier)."""
        ...
    
    async def check_rate_limit(self, user: User) -> bool:
        """Returns True if user has queries remaining today."""
        ...
    
    async def increment_usage(self, user: User) -> None:
        """Increment the user's daily query count."""
        ...
```

### 2. Local User Store (Dev Mode)

Create `servers/orchestrator/src/kinship_orchestrator/auth_sqlite.py`:

- SQLite-backed user store for local development
- Table: `users` (id, email, name, provider, created_at, api_keys JSON, tier, queries_today, queries_limit, last_query_date)
- Auto-reset `queries_today` when `last_query_date` != today
- Database at `~/.kinship-earth/users.db` (configurable via `KINSHIP_USERS_DB_PATH`)

### 3. Auth Middleware for MCP Tools

Modify `servers/orchestrator/src/kinship_orchestrator/server.py`:

- Add optional auth context to tool calls
- Create a helper `_get_current_user()` that:
  - Checks for `KINSHIP_AUTH_TOKEN` in environment (set by proxy)
  - Returns User or None (anonymous)
  - Checks rate limit, returns error if exceeded
- Modify `_store_turn()` (from spec 001) to include `user_id` from current user
- Use user's BYOK API keys when available (override default adapter keys)

### 4. BYOK API Key Tool

Add to the orchestrator:

```python
@mcp.tool()
async def ecology_set_api_key(
    service: Literal["ebird", "xeno-canto", "neon"],
    api_key: str,
) -> dict:
    """Store your own API key for a data source (BYOK).
    
    Some data sources (eBird, Xeno-canto) require API keys for full access.
    Use this to provide your own key, which will be stored securely and
    used for your queries only.
    """
```

### 5. Auth Configuration

Environment variables:
- `KINSHIP_AUTH_ENABLED` — "true" to require auth, "false" for open access (default)
- `KINSHIP_SUPABASE_URL` — Supabase project URL (optional, for prod)
- `KINSHIP_SUPABASE_KEY` — Supabase anon key (optional, for prod)
- `KINSHIP_FREE_TIER_LIMIT` — queries per day for free tier (default: 50)
- `KINSHIP_AUTH_TOKEN` — bearer token for current session (set by proxy/client)

## What NOT to Build

- No OAuth login flow (that's a client concern — Claude Desktop, web, etc.)
- No Supabase integration yet (just the interface + SQLite dev backend)
- No JWT token generation (tokens come from the OAuth provider)
- No admin endpoints
- No password-based auth

## Tests to Write

Create `servers/orchestrator/tests/test_auth.py`:

1. `test_create_anonymous_user` — creates user, gets valid ID
2. `test_rate_limit_allows_within_limit` — user with 49/50 queries passes check
3. `test_rate_limit_blocks_over_limit` — user with 50/50 queries fails check
4. `test_rate_limit_resets_daily` — user with 50/50 from yesterday passes check today
5. `test_byok_key_storage` — store and retrieve a BYOK key
6. `test_auth_disabled_by_default` — with no env vars, all tools work without auth
7. `test_ecology_set_api_key_registered` — tool is in mcp tools list

## Verification

```bash
# Existing tests still pass
uv run --package kinship-orchestrator pytest servers/orchestrator/tests/test_prompts.py -v

# Auth tests pass
uv run --package kinship-orchestrator pytest servers/orchestrator/tests/test_auth.py -v

# Server loads with new tool count
uv run --package kinship-orchestrator python -c "from kinship_orchestrator.server import mcp; print(f'Tools: {len(mcp._tool_manager._tools)}')"
# Expected: Tools: 6 (was 5 + ecology_set_api_key)
```

## Commit Message Template

```
Add auth layer with local user store and rate limiting

Implements Phase 3.1 auth infrastructure:
- User model and AuthManager interface
- SQLite-backed local user store (dev mode)
- Rate limiting (daily query cap for free tier)
- BYOK API key storage via ecology_set_api_key tool
- Auth disabled by default (opt-in via KINSHIP_AUTH_ENABLED)
- 7 new tests

Spec: specs/002-auth-proxy.md
```

## Files to Create/Modify

| Action | File |
|--------|------|
| Create | `servers/orchestrator/src/kinship_orchestrator/auth.py` |
| Create | `servers/orchestrator/src/kinship_orchestrator/auth_sqlite.py` |
| Create | `servers/orchestrator/tests/test_auth.py` |
| Modify | `servers/orchestrator/src/kinship_orchestrator/server.py` (auth middleware + BYOK tool) |
| Modify | `servers/orchestrator/pyproject.toml` (add aiosqlite if not already from spec 001) |
| Modify | `specs/QUEUE.md` (mark this spec done) |
| Modify | `ROADMAP.md` (check off completed items) |
