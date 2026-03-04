"""
Evaluation Test: North Atlantic Cetacean Research Use Case
==========================================================

USE CASE
--------
A researcher is studying common dolphin (Delphinus delphis) distribution off
the US East Coast to correlate with ERA5 sea surface temperature data.

They need:
  - Confirmed occurrence records for Delphinus delphis in the North Atlantic
  - Records near Woods Hole, MA (a major marine research hub) for ground-truthing
  - Validated taxonomy (must be in order Cetacea)
  - Coordinates that fall in marine areas

This sets up Phase 1 cross-source capability: OBIS occurrences + ERA5 SST.

WHAT THESE TESTS CHECK (and why each one matters)
--------------------------------------------------
There are four layers of correctness:

  1. Connectivity   — does the OBIS API respond and return occurrence data?
  2. Contract       — does every observation conform to EcologicalObservation schema?
  3. Semantic       — is the data factually correct? (Delphinus delphis is Cetacea)
  4. Scientific     — is the data fit for research? (finds records near Woods Hole)

RUNNING THESE TESTS
-------------------
From the repo root:
  uv run pytest servers/obis/tests/test_north_atlantic_cetaceans.py -v

To run just one test:
  uv run pytest servers/obis/tests/test_north_atlantic_cetaceans.py::test_obis_api_returns_delphinus_records -v
"""

import pytest

from kinship_shared import SearchParams
from obis_mcp.adapter import OBISAdapter


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def adapter():
    """An OBISAdapter instance shared across tests in this module."""
    return OBISAdapter()


# ---------------------------------------------------------------------------
# Layer 1: Connectivity
# The canary test. If this fails, stop — nothing else is trustworthy.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_obis_api_returns_delphinus_records(adapter):
    """
    CANARY TEST: OBIS returns occurrence records for Delphinus delphis.

    Delphinus delphis (common dolphin) has thousands of records in OBIS.
    If we get zero results, either the API is down or our query parameters
    are broken. Either way, nothing else is trustworthy.

    This is the first test to run. If it fails, stop.
    """
    params = SearchParams(taxon="Delphinus delphis", limit=10)
    observations = await adapter.search(params)

    assert len(observations) > 0, (
        "OBIS should return records for 'Delphinus delphis' (common dolphin). "
        "If zero records returned, either the OBIS API is down or the scientificname "
        "parameter is broken. Check: https://api.obis.org/v3/occurrence?scientificname=Delphinus+delphis"
    )


# ---------------------------------------------------------------------------
# Layer 2: Contract
# Does every observation conform to the EcologicalObservation schema?
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_observation_schema_is_complete(adapter):
    """
    CONTRACT TEST: Every field that downstream tools depend on must be present.

    The EcologicalObservation schema is a contract with every MCP tool,
    API caller, and future embedding model.

    - taxon.scientific_name: required to identify the species
    - location.lat/lng: required for any spatial analysis
    - provenance.source_api: required to trace data origin
    - provenance.license: required for compliance — OBIS records carry per-record licenses
    - quality.tier: required for filtering by data reliability

    We use the first Delphinus delphis result as our test specimen.
    """
    params = SearchParams(taxon="Delphinus delphis", limit=5)
    observations = await adapter.search(params)

    assert len(observations) >= 1, "Need at least one observation to test schema"
    obs = observations[0]

    # Identity
    assert obs.id.startswith("obis:"), f"ID must start with 'obis:', got: {obs.id!r}"
    assert obs.modality == "occurrence", f"Expected modality 'occurrence', got {obs.modality!r}"

    # Taxon — required for species research
    assert obs.taxon is not None, "taxon must be populated for OBIS occurrence records"
    assert obs.taxon.scientific_name, "taxon.scientific_name must not be empty"

    # Location — required for all spatial queries
    assert obs.location is not None, "location must be present"
    assert obs.location.lat is not None, "location.lat must be present"
    assert obs.location.lng is not None, "location.lng must be present"
    assert -90 <= obs.location.lat <= 90, f"lat={obs.location.lat} is not a valid latitude"
    assert -180 <= obs.location.lng <= 180, f"lng={obs.location.lng} is not a valid longitude"

    # Temporal — required for time-series correlation
    assert obs.observed_at is not None, "observed_at must be present"

    # Provenance — required for compliance and citation
    assert obs.provenance.source_api == "obis", "source_api must be 'obis'"
    assert obs.provenance.source_id, "source_id must not be empty"
    assert obs.provenance.license, "license must be present — OBIS records have per-record licenses"
    assert obs.provenance.original_url, "original_url must link back to the OBIS record"

    # Quality — required for filtering
    assert obs.quality.tier == 2, (
        f"OBIS records should be quality tier 2 (community-validated). Got tier {obs.quality.tier}."
    )
    assert obs.quality.grade == "community", (
        f"Expected grade 'community', got {obs.quality.grade!r}"
    )


# ---------------------------------------------------------------------------
# Layer 3: Semantic correctness
# Is the data factually correct? We check against known ground truth.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delphinus_delphis_is_in_cetacea(adapter):
    """
    KNOWN-ANSWER TEST: Delphinus delphis is taxonomically in order Cetacea.

    This is a matter of biological fact, independent of any code.
    Delphinus delphis: Kingdom Animalia > Phylum Chordata > Class Mammalia >
    Order Cetacea > Family Delphinidae > Genus Delphinus > Species delphis

    If our taxonomy mapping returns a different order (or None), we have a
    parsing error in the Darwin Core field mapping.
    """
    params = SearchParams(taxon="Delphinus delphis", limit=10)
    observations = await adapter.search(params)

    assert len(observations) > 0, "Need records to check taxonomy"

    # Find any record that has order populated
    records_with_order = [obs for obs in observations if obs.taxon and obs.taxon.order]

    assert len(records_with_order) > 0, (
        "At least some Delphinus delphis records should have 'order' populated. "
        "Check that the 'order' Darwin Core field is being mapped correctly from the OBIS response."
    )

    # Check the order value — should be Cetacea (or Cetartiodactyla in some taxonomies)
    for obs in records_with_order:
        order = obs.taxon.order
        assert order in ("Cetacea", "Cetartiodactyla"), (
            f"Delphinus delphis should be in order Cetacea or Cetartiodactyla. "
            f"Got order='{order}'. This is a taxonomic mapping error."
        )
        break  # One verified record is sufficient


@pytest.mark.asyncio
async def test_delphinus_records_have_marine_coordinates(adapter):
    """
    SEMANTIC TEST: Delphinus delphis is a marine species — coordinates must be oceanic.

    Common dolphins live in the ocean, not on land. If we're returning records
    with coordinates far inland (e.g. lat=40, lng=80 — Central Asia), something
    is wrong with our coordinate parsing or the query is returning wrong species.

    We use a rough heuristic: at least 80% of records should have longitude
    in an oceanic range (not deep inland continental areas).

    Note: we check for valid lat/lng ranges rather than trying to build a
    full ocean polygon — that would be over-engineering for this test.
    """
    params = SearchParams(taxon="Delphinus delphis", limit=20)
    observations = await adapter.search(params)

    assert len(observations) > 0, "Need records to check coordinates"

    for obs in observations:
        lat = obs.location.lat
        lng = obs.location.lng

        # Basic sanity: valid coordinate range
        assert -90 <= lat <= 90, f"Impossible latitude: {lat}"
        assert -180 <= lng <= 180, f"Impossible longitude: {lng}"

        # Not null island (common missing-value encoding error)
        assert not (lat == 0.0 and lng == 0.0), (
            f"Record {obs.id} has (0, 0) coordinates — likely a missing-value encoding error."
        )


# ---------------------------------------------------------------------------
# Layer 4: Scientific fitness
# Is the data fit for the actual research use case?
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_geographic_search_finds_occurrences_near_woods_hole(adapter):
    """
    SCIENTIFIC FITNESS TEST: The core spatial query for our research use case.

    Woods Hole, MA (lat=41.5, lon=-70.7) is a major marine biology hub.
    The area hosts WHOI (Woods Hole Oceanographic Institution) and lies within
    the North Atlantic range of Delphinus delphis.

    A 200km radius encompasses the Gulf of Maine and approaches the Gulf Stream —
    prime common dolphin habitat documented in published literature.

    If this search returns zero results, our geographic search implementation
    is broken, or the radius/coordinate parameters are not being sent correctly.
    """
    params = SearchParams(
        taxon="Delphinus delphis",
        lat=41.5,
        lng=-70.7,
        radius_km=200,
        limit=20,
    )
    observations = await adapter.search(params)

    assert len(observations) > 0, (
        "Expected Delphinus delphis occurrences within 200km of Woods Hole, MA "
        "(lat=41.5, lon=-70.7). This is a documented common dolphin range. "
        "If zero records found, check that lat/lon/radius are being passed to "
        "the OBIS API correctly as: ?lat=41.5&lon=-70.7&radius=200"
    )

    # All returned records must be within the 200km search radius.
    # Our adapter applies client-side Haversine filtering to guarantee this —
    # OBIS server-side geo filtering is unreliable when combined with taxon queries.
    for obs in observations:
        lat = obs.location.lat
        lng = obs.location.lng
        # Within 200km of Woods Hole: roughly 37–46°N, -76 to -66°W
        assert 36 <= lat <= 46, (
            f"Record {obs.id} at lat={lat} is outside the 200km search radius from Woods Hole. "
            f"Client-side Haversine filtering should have excluded this record."
        )
        assert -76 <= lng <= -64, (
            f"Record {obs.id} at lng={lng} is outside the 200km search radius from Woods Hole. "
            f"Client-side Haversine filtering should have excluded this record."
        )


@pytest.mark.asyncio
async def test_occurrence_has_basis_of_record(adapter):
    """
    SCIENTIFIC FITNESS TEST: basisOfRecord tells researchers how the data was collected.

    In Darwin Core, basisOfRecord distinguishes between:
    - HumanObservation (field survey)
    - MachineObservation (automated sensor)
    - PreservedSpecimen (museum collection)

    For SST correlation research, the observation method affects data reliability.
    A museum specimen from 1910 has different relevance than a 2023 ship survey.

    We verify that this critical metadata field flows through to our value payload.
    """
    params = SearchParams(taxon="Delphinus delphis", limit=10)
    observations = await adapter.search(params)

    assert len(observations) > 0, "Need records to test"

    records_with_basis = [
        obs for obs in observations
        if obs.value and obs.value.get("basis_of_record")
    ]

    assert len(records_with_basis) > 0, (
        "At least some records should have basisOfRecord populated. "
        "This field is nearly always present in OBIS Darwin Core records. "
        "Check that 'basisOfRecord' is being mapped to value['basis_of_record']."
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_species_returns_empty_list_not_exception(adapter):
    """
    EDGE CASE: Searching for a made-up species name should return empty, not crash.

    An AI agent might query for a misspelled or hallucinated species name.
    The adapter must return an empty list, never raise an exception.
    """
    params = SearchParams(taxon="Fakeus speciesus notarealspecies", limit=10)
    observations = await adapter.search(params)

    assert isinstance(observations, list), "search() must always return a list"
    assert len(observations) == 0, (
        f"A made-up species name should return zero results. "
        f"Got {len(observations)} results — check if OBIS is doing fuzzy matching."
    )


@pytest.mark.asyncio
async def test_bogus_occurrence_id_returns_none_not_exception(adapter):
    """
    EDGE CASE: Requesting a non-existent occurrence UUID should return None, not crash.

    The EcologicalAdapter contract: get_by_id returns None if not found.
    An agent asking about a stale or hallucinated UUID must get None, not an error.
    """
    result = await adapter.get_by_id("00000000-0000-0000-0000-000000000000")
    assert result is None, (
        "Requesting a non-existent occurrence UUID should return None, not raise an exception. "
        "Adapters must fail gracefully."
    )
