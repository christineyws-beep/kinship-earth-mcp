"""
Kinship Earth API — FastAPI application.

Authenticated proxy for the Kinship Earth MCP server. Provides:
- REST endpoints for non-MCP clients (web app demo)
- Remote MCP endpoint at /mcp (Streamable HTTP transport)
- Health check with graph stats
- Supabase auth (when configured) or anonymous access
- Rate limiting (50 queries/day free tier)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routes.api import router as api_router
from .routes.health import router as health_router

from kinship_orchestrator.server import mcp as mcp_server

logger = logging.getLogger(__name__)

# Build the MCP sub-app once at import time so session_manager is initialized
# before lifespan runs. The SDK registers its route at /mcp inside this sub-app,
# so we mount it at root and the final URL is /mcp.
mcp_app = mcp_server.streamable_http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize MCP components on startup."""
    logger.info("Kinship Earth API starting...")

    try:
        from kinship_orchestrator.server import _ensure_store, _ensure_graph
        await _ensure_store()
        await _ensure_graph()
        logger.info("Conversation store and graph initialized")
    except Exception as e:
        logger.warning("Failed to initialize storage/graph: %s", e)

    if settings.has_supabase:
        logger.info("Supabase auth configured")
    else:
        logger.info("Running in anonymous mode (no Supabase credentials)")

    # Mounted sub-app lifespans don't run automatically — drive the MCP
    # session manager from the parent lifespan so its task group is live.
    async with mcp_server.session_manager.run():
        yield
    logger.info("Kinship Earth API shutting down")


app = FastAPI(
    title="Kinship Earth API",
    description="Authenticated ecological intelligence proxy — 9 data sources, 17 tools, emergent knowledge graph",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(api_router)
app.mount("/", mcp_app)
