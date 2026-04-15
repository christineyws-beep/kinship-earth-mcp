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
import json
import os
from typing import Literal, Optional

from mcp.server.fastmcp import FastMCP

from neonscience_mcp.adapter import NeonAdapter
from obis_mcp.adapter import OBISAdapter
from era5_mcp.adapter import ERA5Adapter
from inaturalist_mcp.adapter import INaturalistAdapter
from ebird_mcp.adapter import EBirdAdapter
from gbif_mcp.adapter import GBIFAdapter
from usgs_nwis_mcp.adapter import USGSNWISAdapter
from xenocanto_mcp.adapter import XenoCantoAdapter
from soilgrids_mcp.adapter import SoilGridsAdapter

from kinship_shared import (
    ConversationTurn,
    SearchParams,
    SQLiteConversationStore,
    run_describe_sources,
    run_get_environmental_context,
    run_search,
)

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
_inat = INaturalistAdapter()
_ebird = EBirdAdapter(api_key=os.environ.get("EBIRD_API_KEY"))
_gbif = GBIFAdapter()
_nwis = USGSNWISAdapter()
_xc = XenoCantoAdapter(api_key=os.environ.get("XC_API_KEY"))
_soil = SoilGridsAdapter()

# Conversation storage (fire-and-forget, never blocks tools)
_store = SQLiteConversationStore()
_conversation_id = os.environ.get("KINSHIP_CONVERSATION_ID", "")

# Lazy-initialize storage on first use
_store_initialized = False


async def _ensure_store() -> None:
    global _store_initialized
    if not _store_initialized:
        try:
            await _store.initialize()
            _store_initialized = True
        except Exception as e:
            logger.warning("Failed to initialize conversation store: %s", e)


async def _store_turn(tool_name: str, params: dict, result: dict) -> None:
    """Persist a tool invocation. Fire-and-forget — never breaks tools."""
    try:
        await _ensure_store()
        if not _store_initialized:
            return

        import uuid

        # Extract location from params
        lat = params.get("lat")
        lon = params.get("lon") or params.get("lng")

        # Extract taxa from params and results
        taxa = []
        if params.get("scientificname"):
            taxa.append(params["scientificname"])
        if params.get("scientific_name"):
            taxa.append(params["scientific_name"])
        if isinstance(result, dict):
            for occ in result.get("species_occurrences", [])[:5]:
                name = occ.get("scientific_name")
                if name and name not in taxa:
                    taxa.append(name)

        # Condense result to summary
        summary = {}
        if isinstance(result, dict):
            summary["species_count"] = result.get("species_count", 0)
            summary["neon_site_count"] = result.get("neon_site_count", 0)
            summary["climate_included"] = result.get("climate") is not None
            sources = result.get("search_context", {}).get("sources_queried", [])
            summary["sources_queried"] = sources

        turn = ConversationTurn(
            id=str(uuid.uuid4()),
            conversation_id=_conversation_id or str(uuid.uuid4()),
            user_id=os.environ.get("KINSHIP_USER_ID"),
            tool_name=tool_name,
            tool_params=params,
            tool_result_summary=summary,
            lat=lat,
            lng=lon,
            taxa_mentioned=taxa,
        )
        await _store.store_turn(turn)
    except Exception as e:
        logger.warning("Failed to store turn for %s: %s", tool_name, e)


import logging
logger = logging.getLogger(__name__)


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
    result = await run_get_environmental_context(
        lat=lat, lon=lon, date=date,
        days_before=days_before, days_after=days_after,
        neon=_neon, era5=_era5,
    )
    asyncio.create_task(_store_turn(
        "ecology_get_environmental_context",
        {"lat": lat, "lon": lon, "date": date, "days_before": days_before, "days_after": days_after},
        result,
    ))
    return result


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
    offset: int = 0,
    output_format: Literal["json", "geojson"] = "json",
) -> dict:
    """
    Unified ecological search across all Kinship Earth data sources.

    Searches OBIS (marine species) and NEON (terrestrial sites) simultaneously,
    and optionally adds ERA5 climate context for the search area and time period.
    This is the single entry point for cross-source ecological data discovery.

    For source-specific queries with more control, use the individual servers:
    obis_search_occurrences (marine), inaturalist_search (all taxa),
    ebird_recent_observations (birds, real-time).

    Args:
        scientificname: Scientific name to search for (e.g. 'Delphinus delphis').
                        Searches OBIS occurrence records.
        lat: Latitude for geographic search (decimal degrees).
        lon: Longitude for geographic search (negative = West).
        radius_km: Search radius in kilometres.
        start_date: Start of date range (ISO 8601, e.g. '2020-01-01').
        end_date: End of date range (ISO 8601, e.g. '2023-12-31').
        include_climate: If true and lat/lon/dates are provided, include ERA5
                         daily climate summary for the search area (default true).
        limit: Max records per source (default 20).
        offset: Number of results to skip for pagination (default 0).
        output_format: "json" (default) returns structured dict with sections.
                       "geojson" returns species_occurrences as a GeoJSON
                       FeatureCollection (useful for QGIS and mapping tools).

    Example return (json): {"species_occurrences": [...], "neon_sites": [...],
    "climate": {"daily": [...]}, "search_context": {"relevance_scores": [...]}}
    """
    result = await run_search(
        scientificname=scientificname, lat=lat, lon=lon,
        radius_km=radius_km, start_date=start_date, end_date=end_date,
        include_climate=include_climate, limit=limit,
        obis=_obis, neon=_neon, era5=_era5,
        inat=_inat, ebird=_ebird,
    )

    if output_format == "geojson":
        from kinship_shared import observations_to_geojson
        occurrences = result.get("species_occurrences", [])
        result["species_occurrences_geojson"] = observations_to_geojson(occurrences)

    asyncio.create_task(_store_turn(
        "ecology_search",
        {"scientificname": scientificname, "lat": lat, "lon": lon, "radius_km": radius_km,
         "start_date": start_date, "end_date": end_date, "limit": limit},
        result,
    ))
    return result


@mcp.tool()
async def ecology_describe_sources() -> dict:
    """
    Describe all available ecological data sources and their capabilities.

    Returns a summary of each data source including what types of data it
    provides, geographic and temporal coverage, quality tier, and access
    requirements. Use this to understand what data is available before
    searching.
    """
    return await run_describe_sources(
        neon=_neon, obis=_obis, era5=_era5,
        inat=_inat, ebird=_ebird,
        gbif=_gbif, nwis=_nwis, xc=_xc,
    )


# DRAFT: citizen-facing discovery tool (pending full eBird + iNaturalist validation)
@mcp.tool()
async def ecology_whats_around_me(
    lat: float,
    lon: float,
    radius_km: float = 25,
    days_back: int = 7,
) -> dict:
    """
    Discover what's been observed near a location recently.

    A citizen-friendly entry point: "What's happening in the ecosystem around me?"
    Returns a snapshot combining recent species sightings, nearby monitoring sites,
    and current climate conditions from all available data sources.

    Args:
        lat: Your latitude in decimal degrees.
        lon: Your longitude in decimal degrees (negative = West).
        radius_km: How far to look (default 25 km).
        days_back: How many days of recent observations to include (default 7).

    Returns a combined ecological snapshot: recent species sightings (from eBird,
    iNaturalist, and OBIS), nearby monitoring sites (NEON), and current climate
    conditions (ERA5).
    """
    from datetime import datetime, timedelta

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    result = await run_search(
        lat=lat, lon=lon,
        radius_km=radius_km,
        start_date=start_date,
        end_date=end_date,
        include_climate=True,
        limit=30,
        obis=_obis, neon=_neon, era5=_era5,
        inat=_inat, ebird=_ebird,
    )

    # Summarize by source for the citizen
    by_source = {}
    for occ in result.get("species_occurrences", []):
        src = occ.get("source", "obis")
        if src not in by_source:
            by_source[src] = []
        by_source[src].append(occ)

    # Count unique species
    species_names = set()
    for occ in result.get("species_occurrences", []):
        name = occ.get("scientific_name")
        if name:
            species_names.add(name)

    return {
        "snapshot": {
            "location": {"lat": lat, "lon": lon, "radius_km": radius_km},
            "period": f"Last {days_back} days ({start_date} to {end_date})",
            "unique_species": len(species_names),
            "total_observations": len(result.get("species_occurrences", [])),
            "monitoring_sites_nearby": result.get("neon_site_count", 0),
            "climate_data_available": result.get("climate") is not None,
        },
        "recent_sightings": result.get("species_occurrences", [])[:20],
        "neon_sites": result.get("neon_sites", []),
        "climate": result.get("climate"),
        "sources_queried": result.get("search_context", {}).get("sources_queried", []),
    }


@mcp.tool()
async def ecology_feedback(
    turn_id: str,
    feedback: str,
) -> dict:
    """
    Provide feedback on a previous query result.

    Attaches feedback to a stored conversation turn. Use 'helpful',
    'not_helpful', or free-text feedback. This helps improve data
    quality and ranking over time.

    Args:
        turn_id: The ID of the conversation turn to provide feedback on.
        feedback: Feedback text — 'helpful', 'not_helpful', or free text.
    """
    await _ensure_store()
    if not _store_initialized:
        return {"error": "Conversation storage not available"}

    found = await _store.add_feedback(turn_id, feedback)
    if found:
        return {"status": "ok", "turn_id": turn_id, "feedback": feedback}
    else:
        return {"error": f"Turn {turn_id} not found"}


# ---------------------------------------------------------------------------
# Prompts — curated multi-step workflows for agents
# ---------------------------------------------------------------------------


@mcp.prompt()
async def ecological_survey(
    lat: float,
    lon: float,
    radius_km: float = 25,
    start_date: str = "",
    end_date: str = "",
) -> str:
    """
    Comprehensive biodiversity + climate + soil report for a location.

    Runs a multi-source survey: species observations (OBIS, iNaturalist,
    eBird), NEON monitoring sites, ERA5 climate, and SoilGrids soil
    properties. Returns a structured dataset the agent should synthesize
    into a narrative ecological survey report.
    """
    from datetime import datetime, timedelta

    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

    search_result = await run_search(
        lat=lat, lon=lon, radius_km=radius_km,
        start_date=start_date, end_date=end_date,
        include_climate=True, limit=30,
        obis=_obis, neon=_neon, era5=_era5,
        inat=_inat, ebird=_ebird,
    )

    soil_result = await _soil.search(SearchParams(lat=lat, lng=lon, radius_km=1, limit=1))
    soil_data = {}
    if soil_result:
        obs = soil_result[0]
        soil_data = obs.value if obs.value else {}

    survey_data = {
        "survey_type": "ecological_survey",
        "location": {"lat": lat, "lon": lon, "radius_km": radius_km},
        "period": {"start": start_date, "end": end_date},
        "species_observations": search_result.get("species_occurrences", []),
        "species_count": search_result.get("species_count", 0),
        "neon_sites": search_result.get("neon_sites", []),
        "climate": search_result.get("climate"),
        "soil": soil_data,
        "sources_queried": search_result.get("search_context", {}).get("sources_queried", []),
    }

    return (
        "You are conducting an ecological survey. Below is data from 9 ecological "
        "data sources for the requested location and time period. Synthesize this "
        "into a comprehensive ecological survey report with these sections:\n\n"
        "1. **Location Overview** — coordinates, nearest monitoring sites, ecosystem type\n"
        "2. **Biodiversity Summary** — species observed, taxonomic diversity, notable species\n"
        "3. **Climate Conditions** — temperature, precipitation, wind patterns for the period\n"
        "4. **Soil Properties** — composition, organic carbon, pH, moisture (if available)\n"
        "5. **Data Quality Assessment** — source mix, quality tiers, confidence levels\n"
        "6. **Gaps & Recommendations** — what data is missing, suggested follow-up queries\n\n"
        "Include specific numbers, dates, and scientific names. Cite data sources.\n\n"
        f"Survey data:\n```json\n{json.dumps(survey_data, indent=2, default=str)}\n```"
    )


@mcp.prompt()
async def species_report(
    scientific_name: str,
    lat: float = 0,
    lon: float = 0,
    radius_km: float = 100,
) -> str:
    """
    Deep dive on a single species: occurrences, climate correlation, audio, soil.

    Searches across all sources for a specific species, optionally scoped to
    a geographic area. Returns occurrence data, environmental context, and
    any available audio recordings.
    """
    import asyncio

    tasks = {
        "search": run_search(
            scientificname=scientific_name,
            lat=lat if lat else None, lon=lon if lon else None,
            radius_km=radius_km if lat else None,
            include_climate=True, limit=30,
            obis=_obis, neon=_neon, era5=_era5,
            inat=_inat, ebird=_ebird,
        ),
        "audio": _xc.search(SearchParams(taxon=scientific_name, limit=5)),
    }

    if lat and lon:
        tasks["soil"] = _soil.search(SearchParams(lat=lat, lng=lon, radius_km=1, limit=1))

    task_keys = list(tasks.keys())
    results_raw = await asyncio.gather(*tasks.values(), return_exceptions=True)
    results = {}
    for key, val in zip(task_keys, results_raw):
        if isinstance(val, Exception):
            results[key] = {"error": str(val)}
        else:
            results[key] = val

    search_data = results.get("search", {})

    audio_data = []
    if isinstance(results.get("audio"), list):
        for obs in results["audio"]:
            audio_data.append({
                "id": obs.id,
                "location": {"lat": obs.location.lat, "lng": obs.location.lng, "country": obs.location.country},
                "recorded_at": obs.observed_at.isoformat() if obs.observed_at else None,
                "audio_url": obs.media_url,
                "quality": obs.quality.grade,
            })

    soil_data = {}
    if isinstance(results.get("soil"), list) and results["soil"]:
        soil_data = results["soil"][0].value or {}

    report_data = {
        "report_type": "species_report",
        "species": scientific_name,
        "search_area": {"lat": lat, "lon": lon, "radius_km": radius_km} if lat else "global",
        "occurrences": search_data.get("species_occurrences", []) if isinstance(search_data, dict) else [],
        "occurrence_count": search_data.get("species_count", 0) if isinstance(search_data, dict) else 0,
        "climate_context": search_data.get("climate") if isinstance(search_data, dict) else None,
        "soil_context": soil_data,
        "audio_recordings": audio_data,
        "neon_sites": search_data.get("neon_sites", []) if isinstance(search_data, dict) else [],
    }

    return (
        f"You are writing a species report for **{scientific_name}**. Below is data "
        "from multiple ecological sources. Synthesize into a species report with:\n\n"
        "1. **Species Overview** — taxonomy, common name, conservation context\n"
        "2. **Distribution & Occurrences** — where observed, spatial patterns, habitat\n"
        "3. **Environmental Associations** — climate conditions at observation sites, "
        "soil properties, elevation range\n"
        "4. **Temporal Patterns** — when observed, seasonal trends, recent vs. historical\n"
        "5. **Audio/Media** — available recordings with links (if any)\n"
        "6. **Monitoring Infrastructure** — nearby NEON sites for long-term tracking\n"
        "7. **Data Sources & Citations** — list all contributing sources with provenance\n\n"
        "Use scientific names and specific data values. Note data quality tiers.\n\n"
        f"Report data:\n```json\n{json.dumps(report_data, indent=2, default=str)}\n```"
    )


@mcp.prompt()
async def site_comparison(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    label1: str = "Site A",
    label2: str = "Site B",
    start_date: str = "",
    end_date: str = "",
) -> str:
    """
    Structured comparison of two locations across all data sources.

    Runs parallel queries for both sites and returns side-by-side data
    on species, climate, soil, and monitoring infrastructure. The agent
    should present a comparative analysis.
    """
    import asyncio
    from datetime import datetime, timedelta

    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

    search1, search2, soil1, soil2 = await asyncio.gather(
        run_search(
            lat=lat1, lon=lon1, radius_km=50,
            start_date=start_date, end_date=end_date,
            include_climate=True, limit=20,
            obis=_obis, neon=_neon, era5=_era5,
            inat=_inat, ebird=_ebird,
        ),
        run_search(
            lat=lat2, lon=lon2, radius_km=50,
            start_date=start_date, end_date=end_date,
            include_climate=True, limit=20,
            obis=_obis, neon=_neon, era5=_era5,
            inat=_inat, ebird=_ebird,
        ),
        _soil.search(SearchParams(lat=lat1, lng=lon1, radius_km=1, limit=1)),
        _soil.search(SearchParams(lat=lat2, lng=lon2, radius_km=1, limit=1)),
    )

    comparison_data = {
        "comparison_type": "site_comparison",
        "period": {"start": start_date, "end": end_date},
        "sites": {
            label1: {
                "location": {"lat": lat1, "lon": lon1},
                "species_count": search1.get("species_count", 0),
                "species": search1.get("species_occurrences", []),
                "neon_sites": search1.get("neon_sites", []),
                "climate": search1.get("climate"),
                "soil": soil1[0].value if soil1 else {},
            },
            label2: {
                "location": {"lat": lat2, "lon": lon2},
                "species_count": search2.get("species_count", 0),
                "species": search2.get("species_occurrences", []),
                "neon_sites": search2.get("neon_sites", []),
                "climate": search2.get("climate"),
                "soil": soil2[0].value if soil2 else {},
            },
        },
    }

    return (
        f"You are comparing two ecological sites: **{label1}** vs **{label2}**. "
        "Below is parallel data from multiple sources. Create a structured comparison:\n\n"
        "1. **Location Context** — coordinates, nearest monitoring sites, ecosystem type for each\n"
        "2. **Biodiversity Comparison** — species richness, unique vs. shared species, taxonomic composition\n"
        "3. **Climate Comparison** — temperature, precipitation, seasonality side by side\n"
        "4. **Soil Comparison** — composition, organic carbon, pH differences\n"
        "5. **Monitoring Infrastructure** — NEON coverage, data product availability\n"
        "6. **Key Differences & Similarities** — what distinguishes these sites ecologically?\n"
        "7. **Research Potential** — what questions could a comparative study address here?\n\n"
        "Use tables where helpful. Cite data sources.\n\n"
        f"Comparison data:\n```json\n{json.dumps(comparison_data, indent=2, default=str)}\n```"
    )


@mcp.prompt()
def data_export(
    format: Literal["csv", "geojson", "markdown", "bibtex"] = "markdown",
) -> str:
    """
    Guide the agent through exporting ecological data in a specific format.

    This prompt instructs the agent how to format data from prior queries
    into the requested export format with proper citations and provenance.
    """
    format_instructions = {
        "csv": (
            "Export the ecological data as a CSV file. Include columns:\n"
            "id, scientific_name, common_name, lat, lng, observed_at, source, "
            "quality_tier, license, source_url, relevance_score\n\n"
            "Add a header comment row with the query parameters and date generated. "
            "Use the data from the most recent ecology_search or ecological_survey results "
            "in this conversation."
        ),
        "geojson": (
            "Export the ecological data as a GeoJSON FeatureCollection. Each observation "
            "becomes a Feature with:\n"
            "- geometry: Point with [lon, lat] coordinates\n"
            "- properties: scientific_name, common_name, observed_at, source, quality_tier, "
            "relevance_score, source_url\n\n"
            "Include a top-level 'metadata' property with query parameters and date generated. "
            "Use the data from the most recent ecology_search or ecological_survey results."
        ),
        "markdown": (
            "Export the ecological data as a formatted Markdown report with:\n"
            "1. **Header** — title, date generated, query parameters\n"
            "2. **Summary** — key findings, species count, location, time period\n"
            "3. **Species Table** — markdown table of all observations with key fields\n"
            "4. **Climate Summary** — key climate metrics if available\n"
            "5. **Data Sources** — list of all sources with DOIs and citation strings\n"
            "6. **Methodology** — note that data was federated via Kinship Earth MCP\n\n"
            "Use the data from the most recent ecology_search or ecological_survey results."
        ),
        "bibtex": (
            "Export citation information as BibTeX entries for all data sources used. "
            "Include entries for:\n"
            "- Each data source API (OBIS, NEON, ERA5, eBird, iNaturalist, etc.)\n"
            "- Any datasets with DOIs from the observation provenance\n"
            "- The Kinship Earth MCP server itself\n\n"
            "Use proper BibTeX formatting (@misc, @article, @dataset as appropriate). "
            "Include DOIs, URLs, access dates, and license information."
        ),
    }

    return (
        f"The user wants to export ecological data in **{format}** format.\n\n"
        f"{format_instructions[format]}\n\n"
        "If there is no recent search data in this conversation, first ask the user "
        "what data they want to export and run the appropriate search."
    )


# ---------------------------------------------------------------------------
# Resources — live data for agent discovery
# ---------------------------------------------------------------------------


@mcp.resource("ecology://sources")
async def ecology_sources_resource() -> str:
    """Live registry of all available ecological data sources and their status."""
    result = await run_describe_sources(
        neon=_neon, obis=_obis, era5=_era5,
        inat=_inat, ebird=_ebird,
        gbif=_gbif, nwis=_nwis, xc=_xc,
    )
    return json.dumps(result, indent=2, default=str)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    mcp.run(transport=transport)
