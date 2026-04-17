"""Health check and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Health check with service metadata."""
    try:
        from kinship_orchestrator.server import mcp, _graph, _graph_initialized
        tool_count = len(mcp._tool_manager._tools)
        prompt_count = len(mcp._prompt_manager._prompts)
        graph_entities = _graph.entity_count() if _graph_initialized else 0
    except Exception:
        tool_count = 0
        prompt_count = 0
        graph_entities = 0

    return {
        "status": "ok",
        "version": "0.1.0",
        "service": "kinship-earth",
        "tools": tool_count,
        "prompts": prompt_count,
        "graph_entities": graph_entities,
    }
