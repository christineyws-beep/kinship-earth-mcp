"""
Kinship Earth API — FastAPI application.

Authenticated proxy for the Kinship Earth MCP server. Provides:
- REST endpoints for non-MCP clients (web app demo)
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

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize MCP components on startup."""
    logger.info("Kinship Earth API starting...")

    # Initialize conversation store and graph
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
