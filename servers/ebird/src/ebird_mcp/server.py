"""
eBird MCP Server — bird observation tools for AI agents.

Exposes eBird data through the Model Context Protocol, enabling
Claude and other AI agents to search for bird observations.

Requires EBIRD_API_KEY environment variable.
Get a free key at: https://ebird.org/api/keygen
"""

import os

from mcp.server.fastmcp import FastMCP

from ebird_mcp.adapter import EBirdAdapter

mcp = FastMCP(
    "ebird",
    instructions=(
        "eBird is the world's largest citizen science bird database, operated by "
        "the Cornell Lab of Ornithology. It contains over 1.5 billion bird "
        "observations from birders worldwide. Use this server to search for "
        "recent bird sightings near a location. Note: the API only returns "
        "recent observations (last 1-30 days), not historical data."
    ),
)

_adapter = EBirdAdapter(api_key=os.environ.get("EBIRD_API_KEY"))


def _obs_to_dict(obs) -> dict:
    """Serialize an EcologicalObservation to a clean dict for MCP output."""
    return {
        "id": obs.id,
        "scientific_name": obs.taxon.scientific_name if obs.taxon else None,
        "common_name": obs.taxon.common_name if obs.taxon else None,
        "lat": obs.location.lat,
        "lng": obs.location.lng,
        "location_name": obs.location.site_name,
        "observed_at": obs.observed_at.isoformat(),
        "count": obs.value.get("count") if obs.value else None,
        "quality_grade": obs.quality.grade,
        "checklist_url": obs.provenance.original_url,
    }


@mcp.tool()
async def ebird_recent_observations(
    lat: float,
    lng: float,
    radius_km: float = 25,
    species: str | None = None,
    days_back: int = 14,
    limit: int = 20,
) -> list[dict]:
    """
    Search for recent bird observations near a location.

    Args:
        lat: Latitude in decimal degrees
        lng: Longitude in decimal degrees (negative = West)
        radius_km: Search radius in km (max 50)
        species: Scientific name to filter by (optional)
        days_back: How many days back to search (1-30, default 14)
        limit: Max results to return (default 20)

    Returns a list of bird observations with species, location, date, and count.
    """
    from kinship_shared import SearchParams

    params = SearchParams(
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        taxon=species,
        limit=limit,
    )
    results = await _adapter.search(params)
    return [_obs_to_dict(obs) for obs in results]
