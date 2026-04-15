# Spec 009: Supabase Auth + FastAPI Proxy Service

> Phase 3.1 + 3.3 — Production Auth + Web App Migration
> Priority: P0
> Estimated effort: 1 session
> Dependency: Specs 001-003 (storage + auth) — DONE
> GitHub Issue: #7

## Decisions Locked In

- **Auth provider: Supabase** (existing project from web app)
- **Free tier: 50 queries/day**
- **Hosting: Railway** (existing deployment)
- **Web app: archive after migration**
- **Architecture: `service/` directory in this monorepo**

## Objective

Create a thin FastAPI service that wraps the MCP server with Supabase authentication, producing an authenticated MCP-over-HTTP proxy. This replaces kinship-earth-web's backend while dropping the duplicated orchestration logic and frontend.

## What to Build

### 1. Service Directory Structure

```
service/
  src/kinship_service/
    __init__.py
    app.py              # FastAPI app with CORS, lifespan
    auth.py             # Supabase auth middleware
    routes/
      __init__.py
      mcp_proxy.py      # SSE endpoint that proxies MCP protocol
      health.py         # Health check + readiness
    config.py           # Environment config (Supabase URL, keys, etc.)
  pyproject.toml
  Dockerfile
```

### 2. FastAPI App (`app.py`)

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize: MCP server, conversation store, graph
    await store.initialize()
    await graph.initialize()
    yield
    # Cleanup

app = FastAPI(
    title="Kinship Earth API",
    description="Authenticated ecological intelligence proxy",
    lifespan=lifespan,
)
```

### 3. Supabase Auth Middleware (`auth.py`)

```python
from supabase import create_client

class SupabaseAuth:
    def __init__(self, url: str, key: str):
        self.client = create_client(url, key)

    async def get_current_user(self, authorization: str) -> User:
        """Verify Supabase JWT and return User model."""
        # Extract bearer token
        # Verify with Supabase
        # Return User with id, email, name, tier
        # If invalid, raise HTTPException(401)

    async def get_or_create_anonymous(self) -> User:
        """For unauthenticated requests (free tier)."""
```

Dependencies: `supabase` Python client.

### 4. MCP-over-HTTP Proxy (`mcp_proxy.py`)

This is the key endpoint — it proxies MCP protocol over SSE so Claude Desktop and other clients can connect remotely with auth.

```python
@router.post("/mcp")
async def mcp_endpoint(
    request: Request,
    user: User = Depends(get_current_user_or_anonymous),
):
    """MCP protocol endpoint with auth."""
    # Check rate limit
    # Set KINSHIP_USER_ID in context
    # Forward to MCP server
    # Return response
```

Also expose a simpler REST-style endpoint for non-MCP clients:

```python
@router.post("/api/search")
async def search_endpoint(
    request: SearchRequest,
    user: User = Depends(get_current_user_or_anonymous),
):
    """Simple REST wrapper around ecology_search."""
```

### 5. Health Check (`health.py`)

```python
@router.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0", "tools": 17, "graph_entities": graph.entity_count()}
```

### 6. Configuration (`config.py`)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_key: str = ""  # For server-side operations
    free_tier_limit: int = 50
    cors_origins: list[str] = ["*"]
    db_path: str = "~/.kinship-earth/conversations.db"
    graph_db_path: str = "~/.kinship-earth/graph.db"

    class Config:
        env_prefix = "KINSHIP_"
```

### 7. Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install uv && uv sync --package kinship-service
CMD ["uv", "run", "--package", "kinship-service", "uvicorn", "kinship_service.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 8. pyproject.toml for service

```toml
[project]
name = "kinship-service"
version = "0.1.0"
dependencies = [
    "fastapi>=0.110",
    "uvicorn>=0.27",
    "supabase>=2.0",
    "kinship-orchestrator",
    "kinship-shared",
    "pydantic-settings>=2.0",
]
```

## What NOT to Build

- No frontend (no HTML, no Leaflet, no SSE badges)
- No marketing pages
- No email signup
- No admin endpoints (yet)
- No Supabase Postgres migration for conversations (keep SQLite for now, Postgres in a future spec)

## What to Port From kinship-earth-web

- Supabase project URL + keys (as env vars, not hardcoded)
- OAuth callback URL configuration
- CORS settings for Claude Desktop
- Nothing else — all orchestration logic is already in the MCP

## Tests to Write

Create `service/tests/test_app.py`:

1. `test_health_endpoint` — GET /health returns 200
2. `test_search_without_auth` — POST /api/search without token works (anonymous, free tier)
3. `test_cors_headers` — verify CORS headers present
4. `test_config_loads_defaults` — Settings loads with defaults when no env vars

Create `service/tests/test_auth.py`:

1. `test_anonymous_user_created` — unauthenticated request creates anonymous user
2. `test_rate_limit_enforced` — 51st request in a day returns 429
3. `test_invalid_token_returns_401` — bad bearer token returns 401

## Verification

```bash
uv run --package kinship-service pytest service/tests/ -v

# App starts
uv run --package kinship-service uvicorn kinship_service.app:app --host 0.0.0.0 --port 8000 &
curl http://localhost:8000/health
```

## Commit Message Template

```
Add FastAPI proxy service with Supabase auth

Implements Phase 3.1 + 3.3 (Issue #7):
- FastAPI service in service/ directory
- Supabase auth middleware (JWT verification)
- MCP-over-HTTP proxy endpoint
- REST wrapper for ecology_search
- Health check with graph stats
- Dockerfile for Railway deployment
- Rate limiting (50/day free tier)
- 7 new tests

Spec: specs/009-supabase-proxy.md
```

## Files to Create/Modify

| Action | File |
|--------|------|
| Create | `service/src/kinship_service/__init__.py` |
| Create | `service/src/kinship_service/app.py` |
| Create | `service/src/kinship_service/auth.py` |
| Create | `service/src/kinship_service/config.py` |
| Create | `service/src/kinship_service/routes/__init__.py` |
| Create | `service/src/kinship_service/routes/mcp_proxy.py` |
| Create | `service/src/kinship_service/routes/health.py` |
| Create | `service/pyproject.toml` |
| Create | `service/Dockerfile` |
| Create | `service/tests/test_app.py` |
| Create | `service/tests/test_auth.py` |
| Modify | `pyproject.toml` (add service to workspace members) |
| Modify | `specs/QUEUE.md` (mark this spec done) |
| Modify | `ROADMAP.md` (check off Milestone 3.1 + 3.3 items) |
