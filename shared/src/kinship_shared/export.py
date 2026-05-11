"""
Data export in standard formats: CSV, GeoJSON, Markdown, BibTeX.

Converts ecological search results into portable formats for
use in GIS tools, spreadsheets, reports, and reference managers.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from .citations import get_bibtex, get_citations


def to_csv(observations: list[dict], params: dict | None = None) -> str:
    """Convert observations to CSV string with header."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header comment
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    output.write(f"# Kinship Earth MCP export — {today}\n")
    if params:
        output.write(f"# Query: {params}\n")

    # Column headers
    headers = [
        "id", "scientific_name", "common_name", "lat", "lng",
        "observed_at", "source", "quality_tier", "license",
        "source_url", "relevance_score",
    ]
    writer.writerow(headers)

    for obs in observations:
        writer.writerow([
            obs.get("id", ""),
            obs.get("scientific_name", ""),
            obs.get("common_name", ""),
            obs.get("lat", ""),
            obs.get("lng", ""),
            obs.get("observed_at", ""),
            obs.get("source", "obis"),
            obs.get("quality_tier", ""),
            obs.get("license", ""),
            obs.get("source_url", ""),
            obs.get("relevance", {}).get("score", ""),
        ])

    return output.getvalue()


def to_geojson(observations: list[dict], params: dict | None = None) -> dict:
    """Convert observations to GeoJSON FeatureCollection."""
    features = []
    for obs in observations:
        lat = obs.get("lat")
        lng = obs.get("lng")
        if lat is None or lng is None:
            continue

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lng, lat],
            },
            "properties": {
                "id": obs.get("id", ""),
                "scientific_name": obs.get("scientific_name", ""),
                "common_name": obs.get("common_name", ""),
                "observed_at": obs.get("observed_at", ""),
                "source": obs.get("source", "obis"),
                "quality_tier": obs.get("quality_tier", ""),
                "relevance_score": obs.get("relevance", {}).get("score"),
                "source_url": obs.get("source_url", ""),
            },
        }
        features.append(feature)

    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    return {
        "type": "FeatureCollection",
        "metadata": {
            "generated": today,
            "generator": "Kinship Earth MCP",
            "query": params or {},
            "feature_count": len(features),
        },
        "features": features,
    }


def to_markdown(
    observations: list[dict],
    climate: dict | None = None,
    sources_queried: list[str] | None = None,
    params: dict | None = None,
) -> str:
    """Convert results to a formatted Markdown report."""
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    lines = []

    lines.append("# Ecological Data Report")
    lines.append(f"\n*Generated: {today} via Kinship Earth MCP*\n")

    if params:
        lines.append("## Query Parameters\n")
        for k, v in params.items():
            if v is not None:
                lines.append(f"- **{k}**: {v}")
        lines.append("")

    # Summary
    species_names = {o.get("scientific_name") for o in observations if o.get("scientific_name")}
    lines.append("## Summary\n")
    lines.append(f"- **Total observations**: {len(observations)}")
    lines.append(f"- **Unique species**: {len(species_names)}")
    if sources_queried:
        lines.append(f"- **Sources queried**: {', '.join(sources_queried)}")
    lines.append("")

    # Species table
    if observations:
        lines.append("## Species Observations\n")
        lines.append("| Scientific Name | Common Name | Lat | Lng | Date | Source | Quality |")
        lines.append("|---|---|---|---|---|---|---|")
        for obs in observations[:50]:
            lines.append(
                f"| {obs.get('scientific_name', '')} "
                f"| {obs.get('common_name', '')} "
                f"| {obs.get('lat', '')} "
                f"| {obs.get('lng', '')} "
                f"| {obs.get('observed_at', '')[:10]} "
                f"| {obs.get('source', 'obis')} "
                f"| {obs.get('quality_tier', '')} |"
            )
        lines.append("")

    # Climate
    if climate:
        lines.append("## Climate Context\n")
        daily = climate.get("daily", {})
        units = climate.get("units", {})
        temps = daily.get("temperature_2m_mean", [])
        if temps:
            lines.append(f"- **Temperature range**: {min(temps):.1f} – {max(temps):.1f} {units.get('temperature_2m_mean', '°C')}")
        precip = daily.get("precipitation_sum", [])
        if precip:
            lines.append(f"- **Total precipitation**: {sum(precip):.1f} {units.get('precipitation_sum', 'mm')}")
        lines.append("")

    # Citations
    if sources_queried:
        lines.append("## Data Sources\n")
        citation_data = get_citations(sources_queried)
        for sid, cite in citation_data["citations"].items():
            lines.append(f"- **{cite['name']}**: {cite['apa']}")
            if cite.get("doi"):
                lines.append(f"  - DOI: https://doi.org/{cite['doi']}")
            lines.append(f"  - License: {cite['license']}")
        lines.append("")

    lines.append("---\n")
    lines.append("*Data federated via [Kinship Earth MCP](https://github.com/christinebuilds/kinship-earth-mcp)*")

    return "\n".join(lines)


def to_bibtex(sources_queried: list[str] | None = None) -> str:
    """Generate BibTeX entries for data sources."""
    return get_bibtex(sources_queried)
