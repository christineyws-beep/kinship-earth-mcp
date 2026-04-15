"""
Visualization hints for agent UI generation.

Provides structured data that helps AI agents render appropriate
maps, charts, and tables without prescribing the UI. Agents can
use these hints to generate Leaflet maps, D3 charts, or simple
tables as appropriate for their client.
"""

from __future__ import annotations

import math
from typing import Literal


def make_map_hint(
    observations: list[dict],
    neon_sites: list[dict] | None = None,
) -> dict:
    """Generate a map visualization hint from search results.

    Groups observations by source and generates a GeoJSON-ready structure
    with bounds for auto-zoom.
    """
    features = []
    layers: dict[str, list] = {}
    lats = []
    lngs = []

    # Source colors
    source_colors = {
        "obis": "#1f77b4",
        "inat": "#2ca02c",
        "ebird": "#ff7f0e",
        "gbif": "#9467bd",
        "neon": "#d62728",
    }

    for obs in observations:
        lat = obs.get("lat")
        lng = obs.get("lng")
        if lat is None or lng is None:
            continue

        lats.append(lat)
        lngs.append(lng)

        source = obs.get("source", "obis")
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "scientific_name": obs.get("scientific_name", ""),
                "common_name": obs.get("common_name", ""),
                "observed_at": obs.get("observed_at", ""),
                "source": source,
                "quality_tier": obs.get("quality_tier"),
                "relevance_score": obs.get("relevance", {}).get("score"),
            },
        }
        features.append(feature)

        if source not in layers:
            layers[source] = []
        layers[source].append(feature)

    # Add NEON sites as a separate layer
    if neon_sites:
        for site in neon_sites:
            lat = site.get("lat")
            lng = site.get("lng")
            if lat is None or lng is None:
                continue
            lats.append(lat)
            lngs.append(lng)
            feature = {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
                "properties": {
                    "site_code": site.get("site_code", ""),
                    "site_name": site.get("site_name", ""),
                    "source": "neon",
                    "data_products": site.get("data_products"),
                },
            }
            features.append(feature)
            if "neon" not in layers:
                layers["neon"] = []
            layers["neon"].append(feature)

    if not lats:
        return {
            "primary": "text_report",
            "description": "No geographic data available for map rendering",
        }

    # Compute bounds and center
    min_lat, max_lat = min(lats), max(lats)
    min_lng, max_lng = min(lngs), max(lngs)
    center_lat = (min_lat + max_lat) / 2
    center_lng = (min_lng + max_lng) / 2

    # Estimate zoom level from extent
    lat_extent = max_lat - min_lat
    lng_extent = max_lng - min_lng
    extent = max(lat_extent, lng_extent)
    if extent < 0.01:
        zoom = 14
    elif extent < 0.1:
        zoom = 11
    elif extent < 1:
        zoom = 8
    elif extent < 5:
        zoom = 6
    elif extent < 20:
        zoom = 4
    else:
        zoom = 2

    layer_summaries = []
    for source, feats in layers.items():
        layer_summaries.append({
            "name": source,
            "color": source_colors.get(source, "#333333"),
            "feature_count": len(feats),
        })

    return {
        "primary": "map",
        "description": f"Map of {len(features)} features across {len(layers)} sources",
        "map_data": {
            "geojson": {"type": "FeatureCollection", "features": features},
            "bounds": {"sw": [min_lat, min_lng], "ne": [max_lat, max_lng]},
            "center": {"lat": center_lat, "lon": center_lng},
            "zoom_level": zoom,
            "layers": layer_summaries,
        },
    }


def make_climate_chart_hint(climate: dict) -> dict:
    """Generate a timeseries chart hint from ERA5 climate data."""
    daily = climate.get("daily", {})
    units = climate.get("units", {})
    dates = daily.get("time", [])

    if not dates:
        return {
            "primary": "text_report",
            "description": "No timeseries data available",
        }

    series = []

    # Temperature
    temp_key = None
    for k in ["temperature_2m_mean", "temperature_2m_max", "temperature_2m_min"]:
        if k in daily and daily[k]:
            temp_key = k
            series.append({
                "name": k.replace("temperature_2m_", "Temperature ").title(),
                "values": daily[k],
                "units": units.get(k, "°C"),
            })

    # Precipitation
    if "precipitation_sum" in daily and daily["precipitation_sum"]:
        series.append({
            "name": "Precipitation",
            "values": daily["precipitation_sum"],
            "units": units.get("precipitation_sum", "mm"),
        })

    return {
        "primary": "timeseries",
        "description": f"Climate timeseries with {len(series)} variables over {len(dates)} days",
        "chart_data": {
            "chart_type": "timeseries",
            "title": "Climate Conditions",
            "x_label": "Date",
            "y_label": "Value",
            "x_values": dates,
            "series": series,
        },
    }


def make_comparison_hint(label1: str, label2: str, data: dict) -> dict:
    """Generate a comparison table hint from site comparison or temporal data."""
    return {
        "primary": "comparison_table",
        "description": f"Comparison: {label1} vs {label2}",
        "table_data": data,
    }


def make_species_gallery_hint(observations: list[dict]) -> dict:
    """Generate a species gallery hint for observations with media URLs."""
    media_items = []
    for obs in observations:
        url = obs.get("media_url")
        if url:
            media_items.append({
                "url": url,
                "scientific_name": obs.get("scientific_name", ""),
                "common_name": obs.get("common_name", ""),
                "source": obs.get("source", ""),
                "observed_at": obs.get("observed_at", ""),
            })

    if not media_items:
        return {
            "primary": "text_report",
            "description": "No media available for gallery",
        }

    return {
        "primary": "species_gallery",
        "description": f"Gallery of {len(media_items)} species observations with media",
        "gallery_data": media_items,
    }


def make_visualization_hint(
    observations: list[dict] | None = None,
    neon_sites: list[dict] | None = None,
    climate: dict | None = None,
) -> dict:
    """Auto-select the best visualization for a result set.

    Returns a hint with `primary` indicating the recommended visualization
    type and structured data to render it.
    """
    hints = {}

    # Map hint if we have geo data
    if observations:
        map_hint = make_map_hint(observations, neon_sites)
        if map_hint.get("primary") == "map":
            hints["map"] = map_hint

    # Climate chart hint
    if climate:
        chart_hint = make_climate_chart_hint(climate)
        if chart_hint.get("primary") == "timeseries":
            hints["chart"] = chart_hint

    # Species gallery if media present
    if observations:
        gallery = make_species_gallery_hint(observations)
        if gallery.get("primary") == "species_gallery":
            hints["gallery"] = gallery

    if not hints:
        return {"primary": "text_report", "description": "Text-based results"}

    # Pick primary based on what's available
    if "map" in hints:
        result = hints["map"]
        if "chart" in hints:
            result["chart_data"] = hints["chart"].get("chart_data")
        return result
    elif "chart" in hints:
        return hints["chart"]
    elif "gallery" in hints:
        return hints["gallery"]

    return {"primary": "text_report", "description": "Text-based results"}
