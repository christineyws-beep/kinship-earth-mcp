"""
ERA5 climate reanalysis adapter for Kinship Earth.

ERA5 is ECMWF's fifth-generation global climate reanalysis dataset, providing
hourly estimates of atmospheric, land-surface, and ocean variables from 1940
to present at 0.25-degree (~25km) resolution.

This adapter uses the Open-Meteo Historical Weather API as a fast JSON gateway
to ERA5 data. Open-Meteo serves ERA5 (and ERA5-Land at 11km for land surfaces)
with sub-second response times, no authentication required.

We use the `models=era5` parameter to ensure strict ERA5 data rather than
Open-Meteo's blended default, for scientific consistency.

API base: https://archive-api.open-meteo.com/v1/archive
Auth: None required (free tier: 10,000 calls/day)
Format: JSON (flat arrays aligned by time index)

Note: Open-Meteo does not expose sea surface temperature (SST). If SST is
needed for a specific use case, a separate NOAA ERDDAP or CDS API adapter
would be required.

Citation: Hersbach et al. (2020). ERA5 hourly data on single levels.
Copernicus Climate Change Service (C3S) Climate Data Store (CDS).
DOI: 10.24381/cds.adbb2d47
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from kinship_shared import (
    AdapterCapabilities,
    EcologicalAdapter,
    EcologicalObservation,
    Location,
    Provenance,
    Quality,
    SearchParams,
    http_get_with_retry,
)

logger = logging.getLogger(__name__)

OPEN_METEO_API_BASE = "https://archive-api.open-meteo.com/v1/archive"

# Default hourly variables for ecological context
DEFAULT_HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "pressure_msl",
    "wind_speed_10m",
    "wind_direction_10m",
    "cloud_cover",
    "soil_temperature_0_to_7cm",
    "soil_moisture_0_to_7cm",
]

# Default daily variables for summary queries
DEFAULT_DAILY_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "wind_speed_10m_max",
    "wind_direction_10m_dominant",
    "shortwave_radiation_sum",
    "et0_fao_evapotranspiration",
]

# All available hourly variables (for documentation and validation)
ALL_HOURLY_VARS = [
    "temperature_2m", "dewpoint_2m", "apparent_temperature",
    "relative_humidity_2m", "vapour_pressure_deficit",
    "precipitation", "rain", "snowfall", "snow_depth",
    "pressure_msl", "surface_pressure",
    "wind_speed_10m", "wind_speed_100m",
    "wind_direction_10m", "wind_direction_100m", "wind_gusts_10m",
    "cloud_cover", "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high",
    "shortwave_radiation", "direct_radiation", "diffuse_radiation",
    "direct_normal_irradiance", "terrestrial_radiation",
    "soil_temperature_0_to_7cm", "soil_temperature_7_to_28cm",
    "soil_temperature_28_to_100cm", "soil_temperature_100_to_255cm",
    "soil_moisture_0_to_7cm", "soil_moisture_7_to_28cm",
    "soil_moisture_28_to_100cm", "soil_moisture_100_to_255cm",
    "weather_code", "et0_fao_evapotranspiration",
]

ERA5_DOI = "10.24381/cds.adbb2d47"
ERA5_CITATION = (
    "Hersbach, H., et al. (2020). The ERA5 global reanalysis. "
    "Quarterly Journal of the Royal Meteorological Society, 146(730), 1999-2049. "
    "https://doi.org/10.1002/qj.3803"
)


class ERA5Adapter(EcologicalAdapter):
    """Adapter for ERA5 climate reanalysis data via Open-Meteo."""

    @property
    def id(self) -> str:
        return "era5"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            adapter_id="era5",
            name="ERA5 — ECMWF Global Climate Reanalysis",
            description=(
                "ERA5 is ECMWF's fifth-generation global climate reanalysis, providing "
                "hourly estimates of atmospheric, land-surface, and ocean variables from "
                "1940 to present at ~25km resolution. Covers temperature, precipitation, "
                "wind, humidity, pressure, cloud cover, radiation, soil temperature and "
                "moisture. Research-grade data used as the global standard for climate "
                "context in ecological studies. Accessed via Open-Meteo for fast JSON "
                "point queries."
            ),
            modalities=["sensor"],
            supports_location_search=True,
            supports_taxon_search=False,
            supports_date_range=True,
            supports_site_search=False,
            geographic_coverage="Global",
            temporal_coverage_start="1940-01-01",
            update_frequency="daily (5-day lag behind real-time)",
            quality_tier=1,
            requires_auth=False,
            rate_limit_per_minute=600,
            license="CC-BY-4.0",
            homepage_url="https://www.ecmwf.int/en/forecasts/dataset/ecmwf-reanalysis-v5",
        )

    async def get_hourly(
        self,
        lat: float,
        lng: float,
        start_date: str,
        end_date: str,
        variables: list[str] | None = None,
    ) -> dict:
        """
        Fetch hourly ERA5 climate data for a point location and date range.

        Returns the raw Open-Meteo response dict with hourly time series.
        """
        vars_list = variables or DEFAULT_HOURLY_VARS
        query = {
            "latitude": lat,
            "longitude": lng,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": ",".join(vars_list),
            "models": "era5",
            "timezone": "UTC",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await http_get_with_retry(client, OPEN_METEO_API_BASE, params=query)
            resp.raise_for_status()
            return resp.json()

    async def get_daily(
        self,
        lat: float,
        lng: float,
        start_date: str,
        end_date: str,
        variables: list[str] | None = None,
    ) -> dict:
        """
        Fetch daily aggregated ERA5 climate data for a point location and date range.

        Returns the raw Open-Meteo response dict with daily time series.
        """
        logger.info("ERA5 get_daily: lat=%.4f, lng=%.4f, %s to %s", lat, lng, start_date, end_date)
        vars_list = variables or DEFAULT_DAILY_VARS
        query = {
            "latitude": lat,
            "longitude": lng,
            "start_date": start_date,
            "end_date": end_date,
            "daily": ",".join(vars_list),
            "models": "era5",
            "timezone": "UTC",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await http_get_with_retry(client, OPEN_METEO_API_BASE, params=query)
            logger.info("ERA5 HTTP response: status=%d", resp.status_code)
            resp.raise_for_status()
            return resp.json()

    async def search(self, params: SearchParams) -> list[EcologicalObservation]:
        """
        Search ERA5 data as EcologicalObservation records.

        For ERA5, "search" means: given a location and date range, return daily
        climate summaries as observation records. Each day becomes one observation.
        """
        logger.info("ERA5 search: lat=%s, lng=%s, dates=%s to %s", params.lat, params.lng, params.start_date, params.end_date)
        if params.lat is None or params.lng is None:
            return []
        if not params.start_date or not params.end_date:
            return []

        raw = await self.get_daily(
            lat=params.lat,
            lng=params.lng,
            start_date=params.start_date,
            end_date=params.end_date,
        )

        return _daily_response_to_observations(raw, params.lat, params.lng, params.limit)

    async def get_by_id(self, source_id: str) -> Optional[EcologicalObservation]:
        """
        ERA5 doesn't have individual record IDs.
        IDs are synthetic: 'era5:{lat},{lng}:{date}'.
        Parse the ID and fetch that day's data.
        """
        try:
            # Parse synthetic ID: "era5:52.52,13.41:2023-01-15"
            parts = source_id.split(":")
            if len(parts) < 2:
                return None
            coords = parts[0].split(",")
            date_str = parts[1] if len(parts) == 2 else parts[1]
            lat, lng = float(coords[0]), float(coords[1])

            raw = await self.get_daily(
                lat=lat, lng=lng,
                start_date=date_str, end_date=date_str,
            )
            observations = _daily_response_to_observations(raw, lat, lng, limit=1)
            return observations[0] if observations else None
        except (ValueError, IndexError, KeyError):
            return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _daily_response_to_observations(
    raw: dict, lat: float, lng: float, limit: int = 20
) -> list[EcologicalObservation]:
    """Convert an Open-Meteo daily response to EcologicalObservation records."""
    daily = raw.get("daily", {})
    times = daily.get("time", [])
    units = raw.get("daily_units", {})

    # Get the actual resolved coordinates (Open-Meteo snaps to grid)
    resolved_lat = raw.get("latitude", lat)
    resolved_lng = raw.get("longitude", lng)
    elevation = raw.get("elevation")

    results = []
    for i, date_str in enumerate(times):
        if len(results) >= limit:
            break

        # Build the value payload — one entry per variable
        value = {}
        for var_name in daily:
            if var_name == "time":
                continue
            values = daily[var_name]
            if i < len(values) and values[i] is not None:
                value[var_name] = values[i]

        # Include units in the value for self-documentation
        value["_units"] = {k: v for k, v in units.items() if k != "time"}

        # Parse the date
        try:
            observed_at = datetime.strptime(date_str, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue

        obs = EcologicalObservation(
            id=f"era5:{resolved_lat},{resolved_lng}:{date_str}",
            modality="sensor",
            taxon=None,  # Climate data has no taxonomic subject
            location=Location(
                lat=resolved_lat,
                lng=resolved_lng,
                elevation_m=elevation,
                uncertainty_m=25000.0,  # ERA5 grid resolution ~25km
            ),
            observed_at=observed_at,
            duration_seconds=86400.0,  # Daily summary = 24 hours
            value=value,
            unit="mixed (see value._units)",
            quality=Quality(
                tier=1,
                grade="research",
                validated=True,
                confidence=1.0,
                flags=["era5_reanalysis", "grid_resolution_25km"],
            ),
            provenance=Provenance(
                source_api="era5",
                source_id=f"{resolved_lat},{resolved_lng}:{date_str}",
                doi=ERA5_DOI,
                license="CC-BY-4.0",
                attribution=(
                    "ERA5 reanalysis data from Copernicus Climate Change Service (C3S). "
                    "Accessed via Open-Meteo Historical Weather API."
                ),
                citation_string=ERA5_CITATION,
                institution_code="ECMWF",
                original_url=(
                    f"https://open-meteo.com/en/docs/historical-weather-api"
                    f"#latitude={resolved_lat}&longitude={resolved_lng}"
                    f"&start_date={date_str}&end_date={date_str}"
                ),
            ),
            raw=raw,
        )
        results.append(obs)

    return results
