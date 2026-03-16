"""
Kinship Earth Orchestrator — cross-source ecological intelligence tools.

This is the unique value of Kinship Earth. No individual data source can
answer cross-domain questions like "what was the climate when this species
was observed?" or "what ecological data exists for this location?"

The orchestrator coordinates across NEON, OBIS, and ERA5 (and future sources)
to answer higher-level ecological questions.

Tools are unprefixed with 'ecology_' per the architecture conventions:
- ecology_get_environmental_context — climate + sensors for a point/time
- ecology_search — unified search across all sources
- ecology_describe_sources — what data is available

Run locally:   uv run mcp dev src/kinship_orchestrator/server.py
Run via HTTP:  uv run python -m kinship_orchestrator.server
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)

from mcp.server.fastmcp import FastMCP

from neonscience_mcp.adapter import NeonAdapter
from obis_mcp.adapter import OBISAdapter
from era5_mcp.adapter import ERA5Adapter

from kinship_shared import SearchParams, score_observation

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "kinship-earth",
    instructions=(
        "This is the Kinship Earth orchestrator — the cross-source ecological intelligence "
        "layer. Use ecology_get_environmental_context to get climate, soil, and sensor data "
        "for any location and time period (combines ERA5 climate + nearest NEON sites). "
        "Use ecology_search to search for species observations AND their environmental "
        "context in a single call (combines OBIS marine data + NEON terrestrial data + ERA5 "
        "climate). Use ecology_describe_sources to learn what data sources are available "
        "and their capabilities. These tools answer questions that no single data source "
        "can answer alone."
    ),
)

# Initialize all adapters
_neon = NeonAdapter(api_token=os.environ.get("NEON_API_TOKEN"))
_obis = OBISAdapter()
_era5 = ERA5Adapter()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def ecology_get_environmental_context(
    lat: float,
    lon: float,
    date: str,
    days_before: int = 7,
    days_after: int = 0,
) -> dict:
    """
    Get the full environmental context for a location and time.

    This is the flagship cross-source tool. Given a point on Earth and a date,
    it pulls climate data from ERA5 and finds the nearest NEON monitoring sites.
    Use this to understand the environmental conditions when and where a species
    was observed, or to characterize a study site.

    Args:
        lat: Latitude in decimal degrees (e.g. 45.82 for Wind River).
        lon: Longitude in decimal degrees (e.g. -121.95). Negative = West.
        date: The focal date in ISO 8601 format (e.g. '2023-06-15').
        days_before: Number of days before the focal date to include in the
                     climate window (default 7). Useful for seeing conditions
                     leading up to an observation.
        days_after: Number of days after the focal date to include (default 0).

    Returns:
        - ERA5 daily climate summary for the time window
        - Nearest NEON field sites (within 200km)
        - Location metadata
    """
    logger.info("ecology_get_environmental_context called: lat=%.4f, lon=%.4f, date=%s", lat, lon, date)

    # Validate inputs
    if not (-90 <= lat <= 90):
        return {"error": f"lat must be between -90 and 90, got {lat}"}
    if not (-180 <= lon <= 180):
        return {"error": f"lon must be between -180 and 180, got {lon}"}
    try:
        focal = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return {"error": f"date must be in YYYY-MM-DD format, got {date!r}"}

    # Calculate date range
    start = (focal - timedelta(days=days_before)).strftime("%Y-%m-%d")
    end = (focal + timedelta(days=days_after)).strftime("%Y-%m-%d")

    # Run ERA5 climate and NEON site search in parallel
    era5_task = _era5.get_daily(
        lat=lat, lng=lon,
        start_date=start, end_date=end,
    )
    neon_task = _neon.search(SearchParams(
        lat=lat, lng=lon, radius_km=200, limit=10,
    ))

    era5_raw, neon_sites = await asyncio.gather(era5_task, neon_task)
    logger.info("environmental_context: %d NEON sites found, ERA5 keys=%s", len(neon_sites), list(era5_raw.get("daily", {}).keys())[:3])

    # Format NEON sites
    nearby_neon = [
        {
            "site_code": obs.location.site_id,
            "site_name": obs.location.site_name,
            "lat": obs.location.lat,
            "lng": obs.location.lng,
            "elevation_m": obs.location.elevation_m,
            "state": obs.location.state_province,
            "data_products": obs.value.get("data_products_available") if obs.value else None,
            "portal_url": obs.provenance.original_url,
        }
        for obs in neon_sites
    ]

    return {
        "query": {
            "lat": lat,
            "lon": lon,
            "focal_date": date,
            "climate_window": {"start": start, "end": end},
        },
        "climate": {
            "source": "ERA5 (ECMWF) via Open-Meteo",
            "resolution": "~25km grid, daily aggregation",
            "location_resolved": {
                "lat": era5_raw.get("latitude"),
                "lon": era5_raw.get("longitude"),
                "elevation_m": era5_raw.get("elevation"),
            },
            "daily": era5_raw.get("daily", {}),
            "units": era5_raw.get("daily_units", {}),
            "provenance": {
                "doi": "10.24381/cds.adbb2d47",
                "license": "CC-BY-4.0",
            },
        },
        "nearby_neon_sites": nearby_neon,
        "nearby_neon_count": len(nearby_neon),
        "data_sources_used": ["era5", "neonscience"],
    }


@mcp.tool()
async def ecology_search(
    scientificname: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    radius_km: Optional[float] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_climate: bool = True,
    limit: int = 20,
) -> dict:
    """
    Unified ecological search across all Kinship Earth data sources.

    Searches OBIS (marine species) and NEON (terrestrial sites) simultaneously,
    and optionally adds ERA5 climate context for the search area and time period.
    This is the single entry point for ecological data discovery.

    Args:
        scientificname: Scientific name to search for (e.g. 'Delphinus delphis').
                        Searches OBIS occurrence records.
        lat: Latitude for geographic search (decimal degrees).
        lon: Longitude for geographic search. Negative = West.
        radius_km: Search radius in kilometres.
        start_date: Start of date range (ISO 8601, e.g. '2020-01-01').
        end_date: End of date range (ISO 8601, e.g. '2023-12-31').
        include_climate: If true and lat/lon/dates are provided, include ERA5
                         daily climate summary for the search area (default true).
        limit: Max records per source (default 20).

    Returns species occurrences (OBIS), nearby monitoring sites (NEON),
    and climate context (ERA5) in a single response.
    """
    logger.info("ecology_search called: taxon=%s, lat=%s, lon=%s, radius_km=%s", scientificname, lat, lon, radius_km)

    # Validate coordinate bounds if provided
    if lat is not None and not (-90 <= lat <= 90):
        return {"error": f"lat must be between -90 and 90, got {lat}"}
    if lon is not None and not (-180 <= lon <= 180):
        return {"error": f"lon must be between -180 and 180, got {lon}"}

    tasks = {}

    # Always search OBIS if we have a species name or location
    if scientificname or (lat is not None and lon is not None):
        obis_params = SearchParams(
            taxon=scientificname,
            lat=lat, lng=lon, radius_km=radius_km,
            start_date=start_date, end_date=end_date,
            limit=limit,
        )
        tasks["obis"] = _obis.search(obis_params)

    # Search NEON if we have location
    if lat is not None and lon is not None:
        neon_params = SearchParams(
            lat=lat, lng=lon, radius_km=radius_km or 200,
            limit=10,
        )
        tasks["neon"] = _neon.search(neon_params)

    # Get climate context if we have location and dates
    if include_climate and lat is not None and lon is not None and start_date and end_date:
        tasks["era5"] = _era5.get_daily(
            lat=lat, lng=lon,
            start_date=start_date, end_date=end_date,
        )

    # Run all searches in parallel
    if not tasks:
        return {
            "error": "Please provide at least a species name or lat/lon coordinates.",
            "species_occurrences": [],
            "neon_sites": [],
            "climate": None,
        }

    results = {}
    task_keys = list(tasks.keys())
    task_coros = list(tasks.values())
    settled = await asyncio.gather(*task_coros, return_exceptions=True)

    for key, result in zip(task_keys, settled):
        if isinstance(result, Exception):
            logger.error("ecology_search: source %s failed: %s", key, result)
            results[key] = {"error": str(result)}
        else:
            results[key] = result

    # Build search params for scoring
    scoring_params = SearchParams(
        taxon=scientificname,
        lat=lat, lng=lon, radius_km=radius_km,
        start_date=start_date, end_date=end_date,
        limit=limit,
    )

    # Format OBIS results with relevance scores
    obis_occurrences = []
    if "obis" in results and isinstance(results["obis"], list):
        for obs in results["obis"]:
            relevance = score_observation(obs, scoring_params)
            obis_occurrences.append({
                "id": obs.id,
                "scientific_name": obs.taxon.scientific_name if obs.taxon else None,
                "common_name": obs.taxon.common_name if obs.taxon else None,
                "lat": obs.location.lat,
                "lng": obs.location.lng,
                "observed_at": obs.observed_at.isoformat(),
                "depth_m": obs.value.get("depth_m") if obs.value else None,
                "basis_of_record": obs.value.get("basis_of_record") if obs.value else None,
                "quality_tier": obs.quality.tier,
                "license": obs.provenance.license,
                "source_url": obs.provenance.original_url,
                "relevance": {
                    "score": relevance.score,
                    "geo_distance_km": relevance.geo_distance_km,
                    "taxon_match": relevance.taxon_match,
                    "quality_score": relevance.quality_score,
                    "explanation": relevance.explanation,
                },
            })
        # Sort by relevance score
        obis_occurrences.sort(key=lambda x: x["relevance"]["score"], reverse=True)

    # Format NEON results
    neon_sites = []
    if "neon" in results and isinstance(results["neon"], list):
        for obs in results["neon"]:
            neon_sites.append({
                "site_code": obs.location.site_id,
                "site_name": obs.location.site_name,
                "lat": obs.location.lat,
                "lng": obs.location.lng,
                "state": obs.location.state_province,
                "data_products": obs.value.get("data_products_available") if obs.value else None,
            })

    # Format climate
    climate = None
    if "era5" in results and isinstance(results["era5"], dict):
        era5_raw = results["era5"]
        climate = {
            "source": "ERA5 (ECMWF)",
            "location_resolved": {
                "lat": era5_raw.get("latitude"),
                "lon": era5_raw.get("longitude"),
            },
            "daily": era5_raw.get("daily", {}),
            "units": era5_raw.get("daily_units", {}),
        }

    # Build search_context — always show what was searched and what came back
    search_context = {
        "query": {
            "scientificname": scientificname,
            "lat": lat,
            "lon": lon,
            "radius_km": radius_km,
            "date_range": f"{start_date} to {end_date}" if start_date and end_date else None,
        },
        "sources_queried": task_keys,
        "obis_records_returned": len(obis_occurrences),
        "neon_sites_found": len(neon_sites),
        "climate_included": climate is not None,
    }

    if not obis_occurrences and not neon_sites:
        logger.warning("ecology_search: empty results for query taxon=%s, lat=%s, lon=%s", scientificname, lat, lon)

    # Add near-miss guidance when results are sparse
    if obis_occurrences and len(obis_occurrences) < 3 and (lat is not None and lon is not None):
        search_context["sparse_results_hint"] = (
            f"Only {len(obis_occurrences)} records found. To get more: "
            f"expand radius_km (currently {radius_km or 'not set'}), "
            f"widen date range, or search at genus/family level."
        )

    return {
        "species_occurrences": obis_occurrences,
        "species_count": len(obis_occurrences),
        "neon_sites": neon_sites,
        "neon_site_count": len(neon_sites),
        "climate": climate,
        "search_context": search_context,
    }


@mcp.tool()
async def ecology_describe_sources() -> dict:
    """
    Describe all available ecological data sources and their capabilities.

    Returns a summary of each data source including what types of data it
    provides, geographic and temporal coverage, quality tier, and access
    requirements. Use this to understand what data is available before
    searching.
    """
    sources = [_neon, _obis, _era5]
    descriptions = []

    for adapter in sources:
        caps = adapter.capabilities()
        descriptions.append({
            "id": caps.adapter_id,
            "name": caps.name,
            "description": caps.description,
            "modalities": caps.modalities,
            "geographic_coverage": caps.geographic_coverage,
            "temporal_coverage_start": caps.temporal_coverage_start,
            "update_frequency": caps.update_frequency,
            "quality_tier": caps.quality_tier,
            "requires_auth": caps.requires_auth,
            "license": caps.license,
            "homepage": caps.homepage_url,
            "search_capabilities": {
                "location": caps.supports_location_search,
                "taxon": caps.supports_taxon_search,
                "date_range": caps.supports_date_range,
                "site_code": caps.supports_site_search,
            },
        })

    return {
        "source_count": len(descriptions),
        "sources": descriptions,
        "cross_source_tools": [
            {
                "name": "ecology_get_environmental_context",
                "description": "Get climate + sensors for a point and time (ERA5 + NEON combined)",
            },
            {
                "name": "ecology_search",
                "description": "Unified search across all sources — species, sites, and climate",
            },
        ],
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    mcp.run(transport=transport)
