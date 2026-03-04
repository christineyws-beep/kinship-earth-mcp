"""
Evaluation Test: Pacific Northwest Climate Context Use Case
============================================================

USE CASE
--------
A researcher studying old-growth forest ecology at the NEON Wind River site
(WREF, lat=45.82, lon=-121.95) needs historical climate context for their
bird and soil observations from summer 2023.

They need:
  - Daily temperature, precipitation, and soil conditions for the study period
  - Hourly resolution data to correlate with dawn chorus timing
  - Valid ERA5 reanalysis data (not forecast or interpolated garbage)
  - Proper provenance and citation for publication

This is the core cross-source use case: NEON sites + OBIS occurrences
get their climate context from ERA5.

WHAT THESE TESTS CHECK (and why each one matters)
--------------------------------------------------
  1. Connectivity   — does the Open-Meteo ERA5 API respond with data?
  2. Contract       — does every observation conform to EcologicalObservation schema?
  3. Semantic       — is the data physically plausible? (PNW summer temps, not Arctic)
  4. Scientific     — is the data fit for research? (hourly resolution, soil data)

RUNNING THESE TESTS
-------------------
From the repo root:
  uv run pytest servers/era5/tests/test_pnw_climate_context.py -v
"""

import pytest

from kinship_shared import SearchParams
from era5_mcp.adapter import ERA5Adapter


# ---------------------------------------------------------------------------
# Test constants — NEON Wind River Experimental Forest (WREF)
# ---------------------------------------------------------------------------

WREF_LAT = 45.82
WREF_LNG = -121.95
STUDY_START = "2023-06-15"
STUDY_END = "2023-06-21"  # One week in summer


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def adapter():
    """An ERA5Adapter instance shared across tests in this module."""
    return ERA5Adapter()


# ---------------------------------------------------------------------------
# Layer 1: Connectivity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_era5_api_returns_hourly_data(adapter):
    """
    CANARY TEST: Open-Meteo returns ERA5 hourly climate data.

    If this fails, either the Open-Meteo API is down or our request
    parameters are malformed. Nothing else is trustworthy.
    """
    raw = await adapter.get_hourly(
        lat=WREF_LAT, lng=WREF_LNG,
        start_date=STUDY_START, end_date=STUDY_END,
    )

    assert "hourly" in raw, (
        "Expected 'hourly' key in Open-Meteo response. "
        "Check: https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={WREF_LAT}&longitude={WREF_LNG}"
        f"&start_date={STUDY_START}&end_date={STUDY_END}"
        "&hourly=temperature_2m&models=era5"
    )

    times = raw["hourly"].get("time", [])
    assert len(times) > 0, "ERA5 should return hourly timestamps for the date range"

    # One week = 7 days × 24 hours = 168 hours
    assert len(times) >= 100, (
        f"Expected ~168 hourly timestamps for one week. Got {len(times)}."
    )


@pytest.mark.asyncio
async def test_era5_api_returns_daily_data(adapter):
    """
    CANARY TEST: Open-Meteo returns ERA5 daily aggregated data.
    """
    raw = await adapter.get_daily(
        lat=WREF_LAT, lng=WREF_LNG,
        start_date=STUDY_START, end_date=STUDY_END,
    )

    assert "daily" in raw, "Expected 'daily' key in Open-Meteo response"
    times = raw["daily"].get("time", [])
    assert len(times) == 7, f"Expected 7 days for one week. Got {len(times)}."


# ---------------------------------------------------------------------------
# Layer 2: Contract
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_observation_schema_via_search(adapter):
    """
    CONTRACT TEST: ERA5 search results conform to EcologicalObservation schema.

    The search method returns daily summaries as observations. Each observation
    must have valid location, timestamp, provenance, and quality metadata.
    """
    params = SearchParams(
        lat=WREF_LAT, lng=WREF_LNG,
        start_date=STUDY_START, end_date=STUDY_END,
        limit=7,
    )
    observations = await adapter.search(params)

    assert len(observations) > 0, "search() should return daily observations"
    obs = observations[0]

    # Identity
    assert obs.id.startswith("era5:"), f"ID must start with 'era5:', got: {obs.id!r}"
    assert obs.modality == "sensor", f"Expected modality 'sensor', got {obs.modality!r}"

    # No taxon for climate data
    assert obs.taxon is None, "ERA5 climate data should have no taxon"

    # Location
    assert obs.location is not None, "location must be present"
    assert obs.location.lat is not None, "location.lat must be present"
    assert obs.location.lng is not None, "location.lng must be present"
    assert -90 <= obs.location.lat <= 90, f"lat={obs.location.lat} is invalid"
    assert -180 <= obs.location.lng <= 180, f"lng={obs.location.lng} is invalid"

    # Temporal
    assert obs.observed_at is not None, "observed_at must be present"
    assert obs.duration_seconds == 86400.0, "Daily observations should span 24 hours"

    # Value payload
    assert obs.value is not None, "value must contain climate data"
    assert isinstance(obs.value, dict), "value must be a dict"

    # Provenance
    assert obs.provenance.source_api == "era5", "source_api must be 'era5'"
    assert obs.provenance.doi == "10.24381/cds.adbb2d47", "Must include ERA5 DOI"
    assert obs.provenance.license == "CC-BY-4.0", "ERA5 license is CC-BY-4.0"
    assert obs.provenance.institution_code == "ECMWF", "Institution is ECMWF"
    assert obs.provenance.citation_string, "Must include citation string"

    # Quality
    assert obs.quality.tier == 1, "ERA5 is quality tier 1 (calibrated reanalysis)"
    assert obs.quality.grade == "research", "ERA5 is research-grade"


# ---------------------------------------------------------------------------
# Layer 3: Semantic correctness
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pnw_summer_temperature_is_plausible(adapter):
    """
    KNOWN-ANSWER TEST: Summer temperatures at Wind River should be 10-35°C.

    Wind River Experimental Forest is in the Cascade Range of Washington state.
    June daily highs are typically 18-30°C, lows 5-15°C. If we're getting
    -40°C or +50°C, something is wrong with coordinate mapping or unit conversion.
    """
    raw = await adapter.get_hourly(
        lat=WREF_LAT, lng=WREF_LNG,
        start_date=STUDY_START, end_date=STUDY_END,
        variables=["temperature_2m"],
    )

    temps = raw["hourly"]["temperature_2m"]
    valid_temps = [t for t in temps if t is not None]

    assert len(valid_temps) > 0, "Should have temperature readings"

    min_temp = min(valid_temps)
    max_temp = max(valid_temps)

    # PNW summer: absolute bounds -5°C to 45°C (generous for heat waves)
    assert min_temp > -5, (
        f"Minimum temp {min_temp}°C is implausibly cold for PNW in June. "
        "Check coordinate mapping — are we getting data from the right location?"
    )
    assert max_temp < 45, (
        f"Maximum temp {max_temp}°C is implausibly hot for PNW in June. "
        "Check unit conversion — should be Celsius."
    )

    # More refined: mean should be 10-30°C
    mean_temp = sum(valid_temps) / len(valid_temps)
    assert 5 < mean_temp < 35, (
        f"Mean temp {mean_temp:.1f}°C is outside plausible range for PNW June. "
        "Expected 10-25°C."
    )


@pytest.mark.asyncio
async def test_resolved_coordinates_are_near_requested(adapter):
    """
    SEMANTIC TEST: ERA5 grid-snapped coordinates should be near the requested point.

    ERA5 has ~25km resolution. The resolved coordinates (nearest grid point)
    should be within ~25km of what we asked for. If they're wildly different,
    something is wrong with coordinate handling.
    """
    raw = await adapter.get_hourly(
        lat=WREF_LAT, lng=WREF_LNG,
        start_date=STUDY_START, end_date=STUDY_END,
        variables=["temperature_2m"],
    )

    resolved_lat = raw.get("latitude")
    resolved_lng = raw.get("longitude")

    assert resolved_lat is not None, "Response should include resolved latitude"
    assert resolved_lng is not None, "Response should include resolved longitude"

    # Within ~0.5 degrees (~50km) of requested — generous for 25km grid
    assert abs(resolved_lat - WREF_LAT) < 0.5, (
        f"Resolved lat {resolved_lat} is too far from requested {WREF_LAT}"
    )
    assert abs(resolved_lng - WREF_LNG) < 0.5, (
        f"Resolved lng {resolved_lng} is too far from requested {WREF_LNG}"
    )


# ---------------------------------------------------------------------------
# Layer 4: Scientific fitness
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hourly_data_has_ecological_variables(adapter):
    """
    SCIENTIFIC FITNESS: ERA5 response includes the key variables for ecology.

    For correlating bird observations with climate, researchers need at minimum:
    temperature, precipitation, and wind. These should all be present in the
    default variable set.
    """
    raw = await adapter.get_hourly(
        lat=WREF_LAT, lng=WREF_LNG,
        start_date=STUDY_START, end_date=STUDY_END,
    )

    hourly = raw.get("hourly", {})
    required_vars = ["temperature_2m", "precipitation", "wind_speed_10m"]

    for var in required_vars:
        assert var in hourly, (
            f"Missing required ecological variable '{var}' in hourly response. "
            f"Available variables: {list(hourly.keys())}"
        )
        values = hourly[var]
        non_null = [v for v in values if v is not None]
        assert len(non_null) > 0, f"Variable '{var}' has all null values"


@pytest.mark.asyncio
async def test_soil_data_available_for_forest_site(adapter):
    """
    SCIENTIFIC FITNESS: ERA5 soil variables are available for forest ecology.

    Soil temperature and moisture are critical for understanding forest
    phenology, root activity, and decomposition. ERA5 provides these at
    four depth layers.
    """
    raw = await adapter.get_hourly(
        lat=WREF_LAT, lng=WREF_LNG,
        start_date=STUDY_START, end_date=STUDY_END,
        variables=["soil_temperature_0_to_7cm", "soil_moisture_0_to_7cm"],
    )

    hourly = raw.get("hourly", {})
    assert "soil_temperature_0_to_7cm" in hourly, "Soil temperature should be available"
    assert "soil_moisture_0_to_7cm" in hourly, "Soil moisture should be available"

    # Soil temps should be plausible (5-25°C in PNW summer topsoil)
    soil_temps = [t for t in hourly["soil_temperature_0_to_7cm"] if t is not None]
    assert len(soil_temps) > 0, "Should have soil temperature readings"

    mean_soil_temp = sum(soil_temps) / len(soil_temps)
    assert 0 < mean_soil_temp < 35, (
        f"Mean soil temperature {mean_soil_temp:.1f}°C is outside plausible range "
        "for PNW June topsoil (expected 8-20°C)."
    )


@pytest.mark.asyncio
async def test_daily_summary_has_min_max_mean(adapter):
    """
    SCIENTIFIC FITNESS: Daily summary includes min/max/mean temperature.

    For ecological analysis, daily temperature range (max - min) is often
    more informative than mean alone. This tests that we get all three.
    """
    raw = await adapter.get_daily(
        lat=WREF_LAT, lng=WREF_LNG,
        start_date=STUDY_START, end_date=STUDY_END,
    )

    daily = raw.get("daily", {})
    for var in ["temperature_2m_max", "temperature_2m_min", "temperature_2m_mean"]:
        assert var in daily, f"Missing daily variable '{var}'"
        values = daily[var]
        non_null = [v for v in values if v is not None]
        assert len(non_null) > 0, f"Daily '{var}' has all null values"

    # Verify max > min (basic sanity)
    maxes = daily["temperature_2m_max"]
    mins = daily["temperature_2m_min"]
    for i in range(min(len(maxes), len(mins))):
        if maxes[i] is not None and mins[i] is not None:
            assert maxes[i] >= mins[i], (
                f"Day {i}: max temp ({maxes[i]}°C) < min temp ({mins[i]}°C)"
            )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_location_returns_empty(adapter):
    """
    EDGE CASE: Search without lat/lng should return empty, not crash.
    """
    params = SearchParams(
        start_date=STUDY_START, end_date=STUDY_END, limit=10,
    )
    observations = await adapter.search(params)
    assert isinstance(observations, list), "search() must always return a list"
    assert len(observations) == 0, "Search without location should return empty"


@pytest.mark.asyncio
async def test_missing_dates_returns_empty(adapter):
    """
    EDGE CASE: Search without date range should return empty, not crash.
    """
    params = SearchParams(lat=WREF_LAT, lng=WREF_LNG, limit=10)
    observations = await adapter.search(params)
    assert isinstance(observations, list), "search() must always return a list"
    assert len(observations) == 0, "Search without dates should return empty"
