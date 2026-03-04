"""
ERA5 MCP server — exposes ERA5 climate reanalysis data to AI agents via the
Model Context Protocol.

ERA5 is the global standard for historical climate context in ecological
research. This server provides fast point-based climate queries for any
location on Earth, from 1940 to present.

Tools follow MCP naming conventions:
- snake_case, prefixed with 'era5_'
- Descriptions written for LLM understanding (intention-focused)

Run locally:   uv run mcp dev src/era5_mcp/server.py
Run via HTTP:  uv run python -m era5_mcp.server
"""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from era5_mcp.adapter import ERA5Adapter, ALL_HOURLY_VARS, DEFAULT_DAILY_VARS

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "era5",
    instructions=(
        "This server provides access to ERA5 climate reanalysis data — the global "
        "standard for historical climate context. ERA5 provides hourly estimates of "
        "atmospheric, land-surface, and ocean variables from 1940 to present at ~25km "
        "resolution. Use era5_get_climate to fetch hourly climate data for any point "
        "on Earth. Use era5_get_daily_summary for daily aggregated data (min/max/mean "
        "temperature, total precipitation, etc.). Use era5_list_variables to see all "
        "available climate variables. Common ecological use cases: correlating species "
        "observations with local climate, understanding seasonal patterns, comparing "
        "climate conditions across sites."
    ),
)

_adapter = ERA5Adapter()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def era5_get_climate(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    variables: Optional[str] = None,
) -> dict:
    """
    Get hourly ERA5 climate data for a specific location and date range.

    ERA5 is ECMWF's global climate reanalysis — the gold standard for
    historical climate context. Returns hourly time series data.

    Args:
        lat: Latitude in decimal degrees (e.g. 47.37 for NEON Wind River site).
        lon: Longitude in decimal degrees (e.g. -121.95). Negative = West.
        start_date: Start date in ISO 8601 format (e.g. '2023-06-01').
                    ERA5 data available from 1940-01-01 to ~5 days ago.
        end_date: End date in ISO 8601 format (e.g. '2023-06-07').
                  Keep ranges short (1-7 days) for fast responses.
        variables: Comma-separated list of ERA5 variable names to include.
                   Defaults to a core ecological set: temperature_2m,
                   relative_humidity_2m, precipitation, pressure_msl,
                   wind_speed_10m, wind_direction_10m, cloud_cover,
                   soil_temperature_0_to_7cm, soil_moisture_0_to_7cm.
                   Use era5_list_variables to see all available variables.

    Returns hourly time series with timestamps aligned to variable arrays.
    Each variable array has one value per hour in the date range.
    """
    var_list = None
    if variables:
        var_list = [v.strip() for v in variables.split(",")]

    raw = await _adapter.get_hourly(
        lat=lat, lng=lon,
        start_date=start_date, end_date=end_date,
        variables=var_list,
    )

    return {
        "location": {
            "requested": {"lat": lat, "lon": lon},
            "resolved": {
                "lat": raw.get("latitude"),
                "lon": raw.get("longitude"),
                "elevation_m": raw.get("elevation"),
            },
            "note": "ERA5 grid resolution is ~25km. Resolved coordinates are the nearest grid point.",
        },
        "period": {"start": start_date, "end": end_date},
        "model": "ERA5",
        "hourly": raw.get("hourly", {}),
        "units": raw.get("hourly_units", {}),
        "provenance": {
            "source": "ERA5 (ECMWF) via Open-Meteo",
            "doi": "10.24381/cds.adbb2d47",
            "license": "CC-BY-4.0",
        },
    }


@mcp.tool()
async def era5_get_daily_summary(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    variables: Optional[str] = None,
) -> dict:
    """
    Get daily aggregated ERA5 climate data for a location and date range.

    Returns one data point per day with min/max/mean temperature, total
    precipitation, max wind speed, radiation, and evapotranspiration.
    Better than hourly data for trend analysis and longer time periods.

    Args:
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees. Negative = West.
        start_date: Start date (ISO 8601). ERA5 available from 1940-01-01.
        end_date: End date (ISO 8601). Ranges of weeks to months work well.
        variables: Comma-separated daily variable names. Defaults to:
                   temperature_2m_max, temperature_2m_min, temperature_2m_mean,
                   precipitation_sum, wind_speed_10m_max,
                   wind_direction_10m_dominant, shortwave_radiation_sum,
                   et0_fao_evapotranspiration.

    Returns daily time series — one value per day per variable.
    """
    var_list = None
    if variables:
        var_list = [v.strip() for v in variables.split(",")]

    raw = await _adapter.get_daily(
        lat=lat, lng=lon,
        start_date=start_date, end_date=end_date,
        variables=var_list,
    )

    return {
        "location": {
            "requested": {"lat": lat, "lon": lon},
            "resolved": {
                "lat": raw.get("latitude"),
                "lon": raw.get("longitude"),
                "elevation_m": raw.get("elevation"),
            },
        },
        "period": {"start": start_date, "end": end_date},
        "model": "ERA5",
        "daily": raw.get("daily", {}),
        "units": raw.get("daily_units", {}),
        "provenance": {
            "source": "ERA5 (ECMWF) via Open-Meteo",
            "doi": "10.24381/cds.adbb2d47",
            "license": "CC-BY-4.0",
        },
    }


@mcp.tool()
async def era5_list_variables() -> dict:
    """
    List all available ERA5 climate variables.

    Returns the complete list of hourly and daily variables that can be
    requested from ERA5 via this server. Use these variable names with
    the 'variables' parameter in era5_get_climate and era5_get_daily_summary.
    """
    return {
        "hourly_variables": ALL_HOURLY_VARS,
        "daily_variables": DEFAULT_DAILY_VARS,
        "notes": {
            "soil_variables": (
                "Soil temperature and moisture available at 4 depths: "
                "0-7cm, 7-28cm, 28-100cm, 100-255cm. "
                "Example: soil_temperature_0_to_7cm, soil_moisture_28_to_100cm"
            ),
            "wind_variables": (
                "Wind speed available at 10m and 100m heights. "
                "Wind direction and gusts at 10m only."
            ),
            "radiation_variables": (
                "shortwave_radiation (total incoming solar), "
                "direct_radiation, diffuse_radiation, "
                "direct_normal_irradiance, terrestrial_radiation (outgoing longwave)"
            ),
            "not_available": (
                "Sea surface temperature (SST) is not available via this API. "
                "For SST data, use NOAA ERDDAP or the Copernicus CDS API directly."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Serialisation helper (for search results as EcologicalObservation)
# ---------------------------------------------------------------------------

def _obs_to_dict(obs: Any) -> dict:
    """Convert an EcologicalObservation to a clean dict for MCP output."""
    loc = obs.location
    prov = obs.provenance
    qual = obs.quality

    return {
        "id": obs.id,
        "modality": obs.modality,
        "location": {
            "lat": loc.lat,
            "lng": loc.lng,
            "elevation_m": loc.elevation_m,
            "uncertainty_m": loc.uncertainty_m,
        },
        "observed_at": obs.observed_at.isoformat(),
        "duration_seconds": obs.duration_seconds,
        "value": obs.value,
        "unit": obs.unit,
        "quality": {
            "tier": qual.tier,
            "grade": qual.grade,
            "validated": qual.validated,
            "confidence": qual.confidence,
            "flags": qual.flags,
        },
        "provenance": {
            "source_api": prov.source_api,
            "source_id": prov.source_id,
            "doi": prov.doi,
            "license": prov.license,
            "institution_code": prov.institution_code,
            "citation_string": prov.citation_string,
        },
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    mcp.run(transport=transport)
