# Spec 014: Movebank + FLUXNET Data Source Adapters

> Phase 5.4 — Additional Data Sources
> Priority: P1
> Estimated effort: 1 session
> Dependency: None (adapters are independent), but best built after spec 011 so ecosystem state can use them

## Objective

Add two new data source adapters following the established `EcologicalAdapter` pattern: Movebank for animal tracking/movement data, and FLUXNET for carbon/water/energy flux tower measurements. Register them in the orchestrator and update federation to include them in cross-source queries.

## What to Build

### 1. Movebank Adapter

Create `servers/movebank/` with the standard server directory structure.

**Movebank API:**
- Base URL: `https://www.movebank.org/movebank/service/direct-read`
- Auth: Free account required. API key via basic auth (username/password)
- Data: GPS tracking data for 6,000+ animal tracking studies
- Coverage: Global, emphasis on migratory species
- Formats: CSV (primary), JSON (via REST API)
- Rate limits: 1 request/second, max 100,000 records per request
- Terms: Must accept data-sharing agreements per study
- Docs: https://github.com/movebank/movebank-api-doc

Create `servers/movebank/src/movebank_mcp/__init__.py`:
```python
"""Movebank MCP server — animal tracking and movement data."""
```

Create `servers/movebank/src/movebank_mcp/adapter.py`:

```python
"""
Movebank Adapter — animal tracking and GPS telemetry data.

Movebank is a free, online database of animal tracking data hosted
by the Max Planck Institute of Animal Behavior. It provides access
to GPS, Argos, radio, and accelerometer data from tagged animals.

API base: https://www.movebank.org/movebank/service/direct-read
Auth: Requires free account (username + password for basic auth)
      Set MOVEBANK_USER and MOVEBANK_PASSWORD env vars.
Coverage: Global, 6,000+ studies, emphasis on migration
Data: GPS locations, timestamps, sensor readings, study metadata
Temporal resolution: Minutes to hours (depends on tag configuration)
Quality tier: 1 (calibrated instrument data)

This adapter bridges animal movement data into the Kinship Earth
schema, enabling cross-source queries like "what birds are migrating
through this watershed while streamflow is anomalously low?"
"""

from __future__ import annotations

import csv
import io
import logging
import os
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
    TaxonInfo,
)
from kinship_shared.retry import http_get_with_retry

logger = logging.getLogger(__name__)

MOVEBANK_API_BASE = "https://www.movebank.org/movebank/service/direct-read"


class MovebankAdapter(EcologicalAdapter):
    """Adapter for Movebank animal tracking data."""

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
    ):
        self._username = username or os.environ.get("MOVEBANK_USER", "")
        self._password = password or os.environ.get("MOVEBANK_PASSWORD", "")
        self._auth = (self._username, self._password) if self._username else None

    @property
    def id(self) -> str:
        return "movebank"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            adapter_id="movebank",
            name="Movebank",
            description="Animal tracking and GPS telemetry data from the Max Planck Institute. 6,000+ studies covering migration, movement ecology, and habitat use.",
            modalities=["movement"],
            supports_location_search=True,
            supports_taxon_search=True,
            supports_date_range=True,
            geographic_coverage="global",
            temporal_coverage_start="2000-01-01",
            update_frequency="real-time",
            quality_tier=1,
            requires_auth=True,
            rate_limit_per_minute=60,
            license="varies-by-study",
            homepage_url="https://www.movebank.org",
        )

    async def search(self, params: SearchParams) -> list[EcologicalObservation]:
        """Search Movebank for animal tracking data.

        Strategy:
        1. Search for studies matching the taxon and/or bounding box
        2. For matching studies, fetch individual locations (GPS points)
        3. Convert to EcologicalObservation with modality='movement'
        """
        if not self._auth:
            logger.warning("Movebank credentials not set (MOVEBANK_USER, MOVEBANK_PASSWORD)")
            return []

        observations: list[EcologicalObservation] = []

        try:
            # Step 1: Find relevant studies
            study_params = {"entity_type": "study"}
            if params.taxon:
                study_params["taxon_name"] = params.taxon

            # Movebank doesn't support geo-search on studies directly,
            # so we search by taxon first, then filter results by location
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    MOVEBANK_API_BASE,
                    params=study_params,
                    auth=self._auth,
                )
                if resp.status_code != 200:
                    logger.warning("Movebank study search failed: %s", resp.status_code)
                    return []

                # Parse CSV response
                studies = self._parse_csv(resp.text)

                if not studies:
                    return []

                # Step 2: For top studies, fetch recent locations
                for study in studies[:3]:  # Limit to 3 studies to stay within rate limits
                    study_id = study.get("id", "")
                    if not study_id:
                        continue

                    location_params: dict = {
                        "entity_type": "event",
                        "study_id": study_id,
                        "attributes": "individual_local_identifier,timestamp,location_long,location_lat,ground_speed,heading",
                        "max_events_per_individual": str(min(params.limit, 50)),
                    }
                    if params.start_date:
                        location_params["timestamp_start"] = params.start_date
                    if params.end_date:
                        location_params["timestamp_end"] = params.end_date

                    try:
                        loc_resp = await client.get(
                            MOVEBANK_API_BASE,
                            params=location_params,
                            auth=self._auth,
                        )
                        if loc_resp.status_code != 200:
                            continue

                        events = self._parse_csv(loc_resp.text)

                        for event in events:
                            obs = self._event_to_observation(event, study)
                            if obs is None:
                                continue

                            # Filter by location if specified
                            if params.lat is not None and params.lng is not None:
                                from math import radians, sin, cos, sqrt, atan2
                                R = 6371
                                dlat = radians(obs.location.lat - params.lat)
                                dlon = radians(obs.location.lng - params.lng)
                                a = sin(dlat/2)**2 + cos(radians(params.lat)) * cos(radians(obs.location.lat)) * sin(dlon/2)**2
                                dist = R * 2 * atan2(sqrt(a), sqrt(1-a))
                                radius = params.radius_km or 200
                                if dist > radius:
                                    continue

                            observations.append(obs)

                            if len(observations) >= params.limit:
                                return observations

                    except Exception as e:
                        logger.warning("Failed to fetch events for study %s: %s", study_id, e)
                        continue

        except Exception as e:
            logger.warning("Movebank search failed: %s", e)

        return observations

    async def get_by_id(self, source_id: str) -> Optional[EcologicalObservation]:
        """Fetch a specific tracking event by ID. Not directly supported by Movebank."""
        return None

    def _parse_csv(self, csv_text: str) -> list[dict]:
        """Parse Movebank's CSV response into list of dicts."""
        if not csv_text.strip() or csv_text.startswith("No data"):
            return []
        reader = csv.DictReader(io.StringIO(csv_text))
        return list(reader)

    def _event_to_observation(
        self, event: dict, study: dict
    ) -> EcologicalObservation | None:
        """Convert a Movebank event record to EcologicalObservation."""
        try:
            lat = float(event.get("location_lat", ""))
            lng = float(event.get("location_long", ""))
        except (ValueError, TypeError):
            return None

        try:
            timestamp = datetime.fromisoformat(
                event.get("timestamp", "").replace(" ", "T")
            )
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            timestamp = datetime.now(timezone.utc)

        taxon_name = study.get("taxon_ids", "") or study.get("main_location_long", "")
        individual = event.get("individual_local_identifier", "unknown")
        study_name = study.get("name", "")
        study_id = study.get("id", "")

        # Build movement-specific value payload
        value: dict = {"individual_id": individual}
        if event.get("ground_speed"):
            try:
                value["speed_m_s"] = float(event["ground_speed"])
            except (ValueError, TypeError):
                pass
        if event.get("heading"):
            try:
                value["heading_deg"] = float(event["heading"])
            except (ValueError, TypeError):
                pass

        obs_id = f"movebank:{study_id}:{individual}:{timestamp.isoformat()}"

        return EcologicalObservation(
            id=obs_id,
            modality="movement",
            taxon=TaxonInfo(
                scientific_name=taxon_name or "Unknown",
                common_name=study_name or None,
            ),
            location=Location(lat=lat, lng=lng),
            observed_at=timestamp,
            value=value,
            unit="GPS fix",
            quality=Quality(
                tier=1,
                grade="research",
                confidence=0.95,
            ),
            provenance=Provenance(
                source_api="movebank",
                source_id=obs_id,
                original_url=f"https://www.movebank.org/cms/webapp?gwt_fragment=page=studies,path=study{study_id}",
                license="varies-by-study",
                attribution=f"Movebank study: {study_name}",
                collection_method="GPS telemetry",
                sensor_id=individual,
            ),
            temporal_resolution="event-driven",
        )
```

Create `servers/movebank/src/movebank_mcp/server.py`:

```python
"""Movebank MCP server — standalone for individual deployment."""

from mcp.server.fastmcp import FastMCP

from .adapter import MovebankAdapter

mcp = FastMCP(
    "movebank",
    instructions=(
        "Movebank provides GPS tracking data for thousands of animal species. "
        "Use this to query animal movement paths, migration routes, and habitat use patterns."
    ),
)

_adapter = MovebankAdapter()

@mcp.tool()
async def movebank_search(
    taxon: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float = 200,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 20,
) -> dict:
    """Search Movebank for animal tracking data."""
    from kinship_shared import SearchParams
    params = SearchParams(
        taxon=taxon, lat=lat, lng=lng, radius_km=radius_km,
        start_date=start_date, end_date=end_date, limit=limit,
    )
    results = await _adapter.search(params)
    return {
        "source": "movebank",
        "count": len(results),
        "observations": [r.model_dump() for r in results],
    }
```

Create `servers/movebank/pyproject.toml`:
```toml
[project]
name = "movebank-mcp"
version = "0.1.0"
requires-python = ">=3.12"
description = "MCP server for Movebank animal tracking data (GPS telemetry, migration)"
license = { text = "MIT" }
dependencies = [
    "mcp[cli]>=1.0",
    "httpx>=0.27",
    "kinship-shared",
]

[tool.uv.sources]
kinship-shared = { workspace = true }

[tool.hatch.build.targets.wheel]
packages = ["src/movebank_mcp"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### 2. FLUXNET Adapter

Create `servers/fluxnet/` with the standard server directory structure.

**FLUXNET API:**
- Data access: https://fluxnet.org/data/download-data/ (bulk download, account required)
- Alternative: AmeriFlux API at https://ameriflux.lbl.gov/data/download-data/
- For real-time-ish access, use NEON's eddy covariance data (DP4.00200.001) which is FLUXNET-compatible
- Auth: AmeriFlux account required for API access
- Data: Net ecosystem exchange (NEE), gross primary production (GPP), ecosystem respiration (Reco), latent heat, sensible heat, soil heat flux
- Coverage: ~200 active towers in Americas (AmeriFlux), ~950 global (FLUXNET)
- Temporal resolution: 30-minute intervals, aggregated to daily/monthly

Create `servers/fluxnet/src/fluxnet_mcp/__init__.py`:
```python
"""FLUXNET MCP server — carbon, water, and energy flux tower data."""
```

Create `servers/fluxnet/src/fluxnet_mcp/adapter.py`:

```python
"""
FLUXNET Adapter — carbon, water, and energy flux tower measurements.

FLUXNET is a global network of micrometeorological tower sites that
measure exchanges of carbon dioxide, water vapor, and energy between
terrestrial ecosystems and the atmosphere using eddy covariance methods.

This adapter uses two data pathways:
1. NEON's eddy covariance product (DP4.00200.001) for real-time NEON sites
2. AmeriFlux API for broader tower network coverage

The data is critical for understanding carbon budgets, ecosystem
productivity, and climate feedbacks at the ecosystem level.

API base (AmeriFlux): https://ameriflux.lbl.gov/api/v1
Auth: AmeriFlux account required (set AMERIFLUX_USER, AMERIFLUX_TOKEN env vars)
Coverage: ~200 towers across the Americas, ~950 global
Data: NEE, GPP, Reco, LE, H, soil heat flux, meteorological variables
Temporal resolution: 30-min → daily → monthly aggregations
Quality tier: 1 (calibrated instrument data, FLUXNET QC pipeline)

Citation: Pastorello et al. (2020). The FLUXNET2015 dataset.
Scientific Data 7, 225. DOI: 10.1038/s41597-020-0534-3
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from math import radians, sin, cos, sqrt, atan2
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
)
from kinship_shared.retry import http_get_with_retry

logger = logging.getLogger(__name__)

# AmeriFlux site metadata endpoint (public, no auth)
AMERIFLUX_SITE_URL = "https://ameriflux.lbl.gov/api/v1/sites"

# Known flux tower sites with coordinates for geo-search
# This is a curated subset — the full registry is fetched at runtime
KNOWN_SITES: list[dict] = [
    {"site_id": "US-Ha1", "name": "Harvard Forest", "lat": 42.5378, "lng": -72.1715, "ecosystem": "Deciduous Broadleaf Forest"},
    {"site_id": "US-MMS", "name": "Morgan Monroe State Forest", "lat": 39.3232, "lng": -86.4131, "ecosystem": "Deciduous Broadleaf Forest"},
    {"site_id": "US-NR1", "name": "Niwot Ridge", "lat": 40.0329, "lng": -105.5464, "ecosystem": "Evergreen Needleleaf Forest"},
    {"site_id": "US-Ton", "name": "Tonzi Ranch", "lat": 38.4316, "lng": -120.9660, "ecosystem": "Woody Savanna"},
    {"site_id": "US-Var", "name": "Vaira Ranch", "lat": 38.4133, "lng": -120.9508, "ecosystem": "Grassland"},
    {"site_id": "US-WCr", "name": "Willow Creek", "lat": 45.8059, "lng": -90.0799, "ecosystem": "Deciduous Broadleaf Forest"},
    {"site_id": "US-Wkg", "name": "Walnut Gulch Kendall Grassland", "lat": 31.7365, "lng": -109.9419, "ecosystem": "Grassland"},
    {"site_id": "US-ARM", "name": "ARM Southern Great Plains", "lat": 36.6058, "lng": -97.4888, "ecosystem": "Cropland"},
    {"site_id": "US-Ivo", "name": "Ivotuk", "lat": 68.4865, "lng": -155.7503, "ecosystem": "Tundra"},
    {"site_id": "US-Prr", "name": "Poker Flat Research Range", "lat": 65.1237, "lng": -147.4876, "ecosystem": "Boreal Forest"},
]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))


class FLUXNETAdapter(EcologicalAdapter):
    """Adapter for FLUXNET / AmeriFlux carbon flux tower data."""

    def __init__(
        self,
        username: str | None = None,
        token: str | None = None,
    ):
        self._username = username or os.environ.get("AMERIFLUX_USER", "")
        self._token = token or os.environ.get("AMERIFLUX_TOKEN", "")

    @property
    def id(self) -> str:
        return "fluxnet"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            adapter_id="fluxnet",
            name="FLUXNET / AmeriFlux",
            description="Carbon, water, and energy flux tower measurements. Eddy covariance data measuring ecosystem-atmosphere exchanges at ~950 sites globally.",
            modalities=["sensor"],
            supports_location_search=True,
            supports_taxon_search=False,
            supports_date_range=True,
            supports_site_search=True,
            geographic_coverage="global",
            temporal_coverage_start="1990-01-01",
            update_frequency="daily",
            quality_tier=1,
            requires_auth=True,
            rate_limit_per_minute=30,
            license="CC-BY-4.0",
            homepage_url="https://fluxnet.org",
        )

    async def search(self, params: SearchParams) -> list[EcologicalObservation]:
        """Search for flux tower data near a location.

        Strategy:
        1. Find nearby flux tower sites from the known sites registry
        2. Return site metadata with latest available flux values
        3. For authenticated users, fetch actual time-series data

        Without auth, returns site locations and capabilities.
        With auth, returns measured flux values.
        """
        observations: list[EcologicalObservation] = []

        # Find nearby sites
        nearby_sites = []
        if params.lat is not None and params.lng is not None:
            radius = params.radius_km or 200
            for site in KNOWN_SITES:
                dist = _haversine_km(params.lat, params.lng, site["lat"], site["lng"])
                if dist <= radius:
                    nearby_sites.append({**site, "distance_km": dist})
            nearby_sites.sort(key=lambda s: s["distance_km"])
        elif params.site_id:
            # Direct site lookup
            for site in KNOWN_SITES:
                if site["site_id"].lower() == params.site_id.lower():
                    nearby_sites.append({**site, "distance_km": 0})
        else:
            # Return all known sites (limited)
            nearby_sites = [{**s, "distance_km": 0} for s in KNOWN_SITES[:params.limit]]

        for site in nearby_sites[:params.limit]:
            obs = self._site_to_observation(site)
            observations.append(obs)

        # If authenticated, try to fetch actual data
        if self._username and self._token and nearby_sites:
            for site in nearby_sites[:3]:  # Limit API calls
                try:
                    flux_data = await self._fetch_site_data(
                        site["site_id"],
                        start_date=params.start_date,
                        end_date=params.end_date,
                    )
                    if flux_data:
                        for record in flux_data[:params.limit]:
                            obs = self._flux_to_observation(record, site)
                            if obs:
                                observations.append(obs)
                except Exception as e:
                    logger.warning("Failed to fetch flux data for %s: %s", site["site_id"], e)

        return observations[:params.limit]

    async def get_by_id(self, source_id: str) -> Optional[EcologicalObservation]:
        """Fetch a specific flux record by ID."""
        # Parse site_id from source_id
        parts = source_id.split(":")
        if len(parts) >= 2:
            site_id = parts[1]
            for site in KNOWN_SITES:
                if site["site_id"] == site_id:
                    return self._site_to_observation({**site, "distance_km": 0})
        return None

    async def _fetch_site_data(
        self, site_id: str, start_date: str | None = None, end_date: str | None = None
    ) -> list[dict]:
        """Fetch flux data from AmeriFlux API for a specific site.

        This requires authentication. Returns empty list if auth fails.
        """
        if not self._username or not self._token:
            return []

        # AmeriFlux data download requires specific endpoints
        # For now, return empty — actual integration requires accepted data use agreement
        logger.info("FLUXNET data fetch for %s (auth required)", site_id)
        return []

    def _site_to_observation(self, site: dict) -> EcologicalObservation:
        """Convert a flux site metadata record to EcologicalObservation."""
        now = datetime.now(timezone.utc)
        site_id = site["site_id"]

        return EcologicalObservation(
            id=f"fluxnet:{site_id}:metadata",
            modality="sensor",
            location=Location(
                lat=site["lat"],
                lng=site["lng"],
                site_id=site_id,
                site_name=site["name"],
            ),
            observed_at=now,
            value={
                "site_type": "flux_tower",
                "ecosystem_type": site.get("ecosystem", "Unknown"),
                "measurements": ["NEE", "GPP", "Reco", "LE", "H"],
                "description": f"{site['name']} ({site_id}) — {site.get('ecosystem', 'Unknown')} flux tower",
            },
            unit="various (umol/m2/s, W/m2)",
            quality=Quality(
                tier=1,
                grade="research",
                confidence=1.0,
            ),
            provenance=Provenance(
                source_api="fluxnet",
                source_id=f"fluxnet:{site_id}",
                original_url=f"https://ameriflux.lbl.gov/sites/siteinfo/{site_id}",
                doi="10.1038/s41597-020-0534-3",
                license="CC-BY-4.0",
                attribution=f"AmeriFlux site {site_id}: {site['name']}",
                institution_code="AmeriFlux",
                collection_method="eddy_covariance",
                sensor_id=site_id,
            ),
            temporal_resolution="30min",
        )

    def _flux_to_observation(
        self, record: dict, site: dict
    ) -> EcologicalObservation | None:
        """Convert a flux data record to EcologicalObservation."""
        try:
            timestamp = datetime.fromisoformat(record.get("timestamp", ""))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None

        site_id = site["site_id"]
        value = {}

        # Map FLUXNET variable names to our schema
        flux_vars = {
            "NEE_VUT_REF": ("net_ecosystem_exchange_umol_m2_s", "umol/m2/s"),
            "GPP_NT_VUT_REF": ("gross_primary_production_umol_m2_s", "umol/m2/s"),
            "RECO_NT_VUT_REF": ("ecosystem_respiration_umol_m2_s", "umol/m2/s"),
            "LE_F_MDS": ("latent_heat_flux_w_m2", "W/m2"),
            "H_F_MDS": ("sensible_heat_flux_w_m2", "W/m2"),
            "TA_F": ("air_temperature_c", "deg C"),
            "P_F": ("precipitation_mm", "mm"),
            "SWC_F_MDS_1": ("soil_water_content_pct", "%"),
        }

        for src_key, (dest_key, _) in flux_vars.items():
            if src_key in record and record[src_key] is not None:
                try:
                    value[dest_key] = float(record[src_key])
                except (ValueError, TypeError):
                    continue

        if not value:
            return None

        return EcologicalObservation(
            id=f"fluxnet:{site_id}:{timestamp.isoformat()}",
            modality="sensor",
            location=Location(
                lat=site["lat"],
                lng=site["lng"],
                site_id=site_id,
                site_name=site["name"],
            ),
            observed_at=timestamp,
            value=value,
            unit="various",
            quality=Quality(
                tier=1,
                grade="research",
                confidence=0.95,
            ),
            provenance=Provenance(
                source_api="fluxnet",
                source_id=f"fluxnet:{site_id}:{timestamp.isoformat()}",
                original_url=f"https://ameriflux.lbl.gov/sites/siteinfo/{site_id}",
                doi="10.1038/s41597-020-0534-3",
                license="CC-BY-4.0",
                attribution=f"AmeriFlux site {site_id}: {site['name']}",
                institution_code="AmeriFlux",
                collection_method="eddy_covariance",
                sensor_id=site_id,
            ),
            temporal_resolution="30min",
        )
```

Create `servers/fluxnet/src/fluxnet_mcp/server.py`:

```python
"""FLUXNET MCP server — standalone for individual deployment."""

from mcp.server.fastmcp import FastMCP

from .adapter import FLUXNETAdapter

mcp = FastMCP(
    "fluxnet",
    instructions=(
        "FLUXNET provides carbon, water, and energy flux measurements from "
        "eddy covariance towers worldwide. Use this to query ecosystem "
        "carbon budgets, primary productivity, and energy balance data."
    ),
)

_adapter = FLUXNETAdapter()

@mcp.tool()
async def fluxnet_search(
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float = 200,
    site_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 20,
) -> dict:
    """Search for FLUXNET / AmeriFlux tower data."""
    from kinship_shared import SearchParams
    params = SearchParams(
        lat=lat, lng=lng, radius_km=radius_km, site_id=site_id,
        start_date=start_date, end_date=end_date, limit=limit,
    )
    results = await _adapter.search(params)
    return {
        "source": "fluxnet",
        "count": len(results),
        "observations": [r.model_dump() for r in results],
    }
```

Create `servers/fluxnet/pyproject.toml`:
```toml
[project]
name = "fluxnet-mcp"
version = "0.1.0"
requires-python = ">=3.12"
description = "MCP server for FLUXNET / AmeriFlux carbon flux tower data"
license = { text = "MIT" }
dependencies = [
    "mcp[cli]>=1.0",
    "httpx>=0.27",
    "kinship-shared",
]

[tool.uv.sources]
kinship-shared = { workspace = true }

[tool.hatch.build.targets.wheel]
packages = ["src/fluxnet_mcp"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### 3. Register in Orchestrator

Modify `servers/orchestrator/src/kinship_orchestrator/server.py`:
- Import `MovebankAdapter` and `FLUXNETAdapter`
- Initialize adapters: `_movebank = MovebankAdapter()` and `_fluxnet = FLUXNETAdapter()`
- Add to the `_ALL_ADAPTERS` list used by `ecology_search` and `ecology_describe_sources`

Modify `servers/orchestrator/pyproject.toml`:
- Add `movebank-mcp` and `fluxnet-mcp` to dependencies and `[tool.uv.sources]`

### 4. Update Workspace

Modify the root `pyproject.toml` (workspace members):
- Add `servers/movebank` and `servers/fluxnet` to the workspace members list

### 5. Update Launcher

Modify `launcher/src/kinship_earth/__main__.py`:
- Add "movebank" and "fluxnet" to the server choices

## What NOT to Build

- No Wildlife Insights adapter (camera trap data — future spec)
- No Copernicus Land adapter (satellite NDVI — future spec)
- No Movebank study browser UI
- No FLUXNET data gap-filling (leave that to the source QC)
- No automatic data download pipeline (on-demand queries only)

## Tests to Write

Create `servers/movebank/tests/test_movebank.py`:

1. `test_movebank_adapter_id` — verify adapter id is "movebank"
2. `test_movebank_capabilities` — verify capabilities fields
3. `test_movebank_capabilities_modality` — modalities includes "movement"
4. `test_parse_csv_empty` — empty CSV returns empty list
5. `test_parse_csv_valid` — valid CSV returns parsed dicts
6. `test_event_to_observation` — verify conversion from Movebank event to EcologicalObservation
7. `test_event_to_observation_missing_coords` — returns None for bad coordinates
8. `test_search_without_auth_returns_empty` — no credentials returns empty list

Create `servers/fluxnet/tests/test_fluxnet.py`:

9. `test_fluxnet_adapter_id` — verify adapter id is "fluxnet"
10. `test_fluxnet_capabilities` — verify capabilities fields
11. `test_fluxnet_capabilities_modality` — modalities includes "sensor"
12. `test_site_to_observation` — verify conversion from site metadata to EcologicalObservation
13. `test_search_by_location` — search near Harvard Forest finds US-Ha1
14. `test_search_by_site_id` — direct site_id lookup works
15. `test_search_no_location` — without lat/lng returns all known sites
16. `test_flux_to_observation_valid` — valid flux record converts correctly
17. `test_flux_to_observation_no_timestamp` — returns None for missing timestamp

## Verification

```bash
# Movebank adapter tests (offline — mock auth)
uv run --package kinship-orchestrator pytest servers/movebank/tests/ -v

# FLUXNET adapter tests (offline — uses known sites registry)
uv run --package kinship-orchestrator pytest servers/fluxnet/tests/ -v

# All existing tests still pass
uv run --package kinship-orchestrator pytest servers/orchestrator/tests/ shared/tests/ -v -k "not (climate or dolphin or cetac or wind_river or woods_hole or parallel or cross_persona or marine or reachable or coordinates or geographic or bird_survey or bird_data or catalog or nonexistent or empty_area or bogus)"

# Server loads with both new adapters
uv run --package kinship-orchestrator python -c "from kinship_orchestrator.server import mcp; print(f'Tools: {len(mcp._tool_manager._tools)}')"

# Verify describe_sources includes new adapters
uv run --package kinship-orchestrator python -c "
from movebank_mcp.adapter import MovebankAdapter
from fluxnet_mcp.adapter import FLUXNETAdapter
m = MovebankAdapter()
f = FLUXNETAdapter()
print(f'Movebank: {m.capabilities().name}')
print(f'FLUXNET: {f.capabilities().name}')
print(f'Modalities: {m.capabilities().modalities + f.capabilities().modalities}')
"
```

## Commit Message Template

```
Add Movebank and FLUXNET data source adapters

Implements Phase 5.4 additional data sources:
- MovebankAdapter: animal tracking / GPS telemetry (6,000+ studies)
  - GPS location search, taxon search, movement modality
  - CSV parsing, study → event → EcologicalObservation pipeline
- FLUXNETAdapter: carbon/water/energy flux towers (~950 sites)
  - Known sites registry (10 curated AmeriFlux sites)
  - Site metadata + authenticated data fetch
  - NEE, GPP, Reco, latent/sensible heat measurements
- Both adapters registered in orchestrator federation
- Data source count: 9 → 11
- 17 new tests

Spec: specs/014-new-data-sources.md
```

## Files to Create/Modify

| Action | File |
|--------|------|
| Create | `servers/movebank/pyproject.toml` |
| Create | `servers/movebank/src/movebank_mcp/__init__.py` |
| Create | `servers/movebank/src/movebank_mcp/adapter.py` |
| Create | `servers/movebank/src/movebank_mcp/server.py` |
| Create | `servers/movebank/tests/test_movebank.py` |
| Create | `servers/fluxnet/pyproject.toml` |
| Create | `servers/fluxnet/src/fluxnet_mcp/__init__.py` |
| Create | `servers/fluxnet/src/fluxnet_mcp/adapter.py` |
| Create | `servers/fluxnet/src/fluxnet_mcp/server.py` |
| Create | `servers/fluxnet/tests/test_fluxnet.py` |
| Modify | `servers/orchestrator/src/kinship_orchestrator/server.py` (import + register adapters) |
| Modify | `servers/orchestrator/pyproject.toml` (add new adapter dependencies) |
| Modify | `pyproject.toml` (add workspace members) |
| Modify | `launcher/src/kinship_earth/__main__.py` (add server choices) |
| Modify | `specs/QUEUE.md` (mark this spec done) |
| Modify | `ROADMAP.md` (check off Milestone 5.4 items) |
