"""
REST API endpoints wrapping MCP tools.

These are simple REST wrappers so non-MCP clients (like the web app demo)
can call ecological tools via HTTP. The real MCP protocol endpoint is
separate (mcp_proxy.py).
"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..auth import UserContext, get_current_user, rate_limiter
from ..config import settings

router = APIRouter(prefix="/api", tags=["api"])


class SearchRequest(BaseModel):
    scientificname: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    radius_km: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    include_climate: bool = True
    limit: int = 20
    output_format: Literal["json", "geojson"] = "json"


class FeedbackRequest(BaseModel):
    turn_id: str
    feedback: str


@router.post("/search")
async def search(
    req: SearchRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
):
    """Unified ecological search (REST wrapper for ecology_search)."""
    if not rate_limiter.check(user.user_id, settings.free_tier_limit):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({settings.free_tier_limit} queries/day). "
                   "Upgrade to pro or use BYOK API keys.",
        )

    rate_limiter.increment(user.user_id)

    from kinship_orchestrator.server import ecology_search
    result = await ecology_search(
        scientificname=req.scientificname,
        lat=req.lat, lon=req.lon,
        radius_km=req.radius_km,
        start_date=req.start_date, end_date=req.end_date,
        include_climate=req.include_climate,
        limit=req.limit,
        output_format=req.output_format,
    )

    return {"user_id": user.user_id, "tier": user.tier, **result}


@router.post("/environmental-context")
async def environmental_context(
    lat: float,
    lon: float,
    date: str,
    days_before: int = 7,
    days_after: int = 0,
    request: Request = None,
    user: UserContext = Depends(get_current_user),
):
    """Environmental context (REST wrapper for ecology_get_environmental_context)."""
    if not rate_limiter.check(user.user_id, settings.free_tier_limit):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    rate_limiter.increment(user.user_id)

    from kinship_orchestrator.server import ecology_get_environmental_context
    return await ecology_get_environmental_context(
        lat=lat, lon=lon, date=date,
        days_before=days_before, days_after=days_after,
    )


@router.get("/sources")
async def sources():
    """List available data sources."""
    from kinship_orchestrator.server import ecology_describe_sources
    return await ecology_describe_sources()


@router.post("/feedback")
async def feedback(
    req: FeedbackRequest,
    user: UserContext = Depends(get_current_user),
):
    """Submit feedback on a query result."""
    from kinship_orchestrator.server import ecology_feedback
    return await ecology_feedback(turn_id=req.turn_id, feedback=req.feedback)


@router.get("/usage")
async def usage(user: UserContext = Depends(get_current_user)):
    """Check current usage and rate limit status."""
    return {
        "user_id": user.user_id,
        "authenticated": user.authenticated,
        "tier": user.tier,
        "queries_today": rate_limiter.get_usage(user.user_id),
        "queries_limit": settings.free_tier_limit,
    }
