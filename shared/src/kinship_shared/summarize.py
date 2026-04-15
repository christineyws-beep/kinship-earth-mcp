"""
Result summarization for conversation storage.

Condenses full tool results into storage-friendly summaries that
capture key metrics without storing multi-KB payloads.
"""

from __future__ import annotations


def summarize_search_result(tool_name: str, params: dict, result: dict) -> dict:
    """Condense a full tool result into a storage-friendly summary.

    Extracts key metrics without storing the full payload:
    - species_count, source_count, neon_sites_found
    - top 3 species by relevance
    - climate data available (bool)
    - result quality (avg relevance score)
    """
    if not isinstance(result, dict):
        return {"tool_name": tool_name, "raw_type": type(result).__name__}

    summary: dict = {"tool_name": tool_name}

    # Species observations
    occurrences = result.get("species_occurrences", [])
    summary["species_count"] = result.get("species_count", len(occurrences))

    # Top species by relevance
    top_species = []
    for occ in occurrences[:5]:
        name = occ.get("scientific_name")
        score = occ.get("relevance", {}).get("score", 0)
        if name:
            top_species.append({"name": name, "score": round(score, 3)})
    summary["top_species"] = top_species

    # NEON sites
    summary["neon_site_count"] = result.get("neon_site_count", len(result.get("neon_sites", [])))

    # Climate
    summary["climate_included"] = result.get("climate") is not None

    # Sources
    ctx = result.get("search_context", {})
    summary["sources_queried"] = ctx.get("sources_queried", [])

    # Average relevance
    scores = [occ.get("relevance", {}).get("score", 0) for occ in occurrences if occ.get("relevance")]
    if scores:
        summary["avg_relevance"] = round(sum(scores) / len(scores), 3)

    # Sparse results hint
    if ctx.get("sparse_results_hint"):
        summary["sparse_results_hint"] = ctx["sparse_results_hint"]

    # Error
    if result.get("error"):
        summary["error"] = result["error"]

    return summary


def summarize_environmental_context(result: dict) -> dict:
    """Summarize an environmental context result."""
    if not isinstance(result, dict):
        return {}

    summary = {
        "tool_name": "ecology_get_environmental_context",
        "neon_site_count": result.get("nearby_neon_count", 0),
        "climate_included": result.get("climate") is not None,
        "data_sources_used": result.get("data_sources_used", []),
    }

    # Climate stats
    climate = result.get("climate", {})
    daily = climate.get("daily", {})
    temps = daily.get("temperature_2m_mean", [])
    if temps:
        summary["temp_range"] = {"min": round(min(temps), 1), "max": round(max(temps), 1)}

    # NEON sites found
    sites = result.get("nearby_neon_sites", [])
    summary["neon_sites"] = [s.get("site_code") for s in sites[:5]]

    return summary


def make_human_summary(tool_name: str, params: dict, result: dict) -> str:
    """Generate a one-line human-readable summary of a tool call."""
    if tool_name == "ecology_search":
        taxon = params.get("scientificname", "")
        lat = params.get("lat")
        count = result.get("species_count", 0) if isinstance(result, dict) else 0
        if taxon and lat:
            return f"Searched for {taxon} near ({lat}, {params.get('lon')}) — {count} results"
        elif taxon:
            return f"Searched for {taxon} — {count} results"
        elif lat:
            return f"Searched near ({lat}, {params.get('lon')}) — {count} results"
        return f"Search — {count} results"

    elif tool_name == "ecology_get_environmental_context":
        lat = params.get("lat")
        date = params.get("date", "")
        neon_count = result.get("nearby_neon_count", 0) if isinstance(result, dict) else 0
        return f"Environmental context at ({lat}, {params.get('lon')}) on {date} — {neon_count} NEON sites"

    elif tool_name == "ecology_whats_around_me":
        lat = params.get("lat")
        count = 0
        if isinstance(result, dict):
            count = result.get("snapshot", {}).get("total_observations", 0)
        return f"What's around ({lat}, {params.get('lon')}) — {count} observations"

    return f"{tool_name} called"
