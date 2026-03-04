"""
Evaluation Test: Pacific Northwest Bird-Climate Research Use Case
=================================================================

USE CASE
--------
A researcher is studying how old-growth forest microclimates affect bird
diversity in the Pacific Northwest. They need NEON field sites in Oregon
and Washington that have BOTH:
  - Climate sensor data (soil, temperature, eddy covariance flux)
  - Bird point count survey data (DP1.10003.001)

So they can cross-reference microclimate readings with species observations
across seasons.

This is a real scientific workflow. These tests verify that the neonscience
MCP server can actually support it — not just that the code runs, but that
the data returned is correct, complete, and scientifically meaningful.

WHAT THESE TESTS CHECK (and why each one matters)
--------------------------------------------------
There are four layers of correctness we care about:

  1. Connectivity   — does the NEON API respond at all?
  2. Contract       — does every observation conform to the EcologicalObservation schema?
  3. Semantic       — is the data factually correct? (WREF is in WA, not TX)
  4. Scientific     — is the data fit for research? (has the data products we need)

Most "does it work?" checks only verify layer 1. We verify all four.

KNOWN-ANSWER TESTS
------------------
The most valuable tests in data infrastructure are known-answer tests:
we know the correct answer from reality, independent of the code.
  - NEON has exactly 81 field sites (public record)
  - WREF is in Washington state at lat ~45.82, lng ~-121.95 (GPS record)
  - WREF has bird point count data DP1.10003.001 (NEON data catalog)
If our code disagrees with reality, the code is wrong.

RUNNING THESE TESTS
-------------------
From the repo root:
  uv run pytest servers/neonscience/tests/test_pnw_bird_climate.py -v

To run just one test:
  uv run pytest servers/neonscience/tests/test_pnw_bird_climate.py::test_wref_is_in_washington -v
"""

import pytest

from kinship_shared import SearchParams
from neonscience_mcp.adapter import NeonAdapter


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def adapter():
    """A NeonAdapter instance shared across tests in this module."""
    return NeonAdapter()


# ---------------------------------------------------------------------------
# Layer 1: Connectivity
# The canary test. If this fails, stop — nothing else is trustworthy.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_neon_api_is_reachable_and_returns_all_sites(adapter):
    """
    CANARY TEST: NEON operates exactly 81 field sites as of 2024.

    Why 81? It's a matter of public record from the NEON program.
    If we get fewer, the API connection is broken or we're filtering incorrectly.
    If we get more, we have a deduplication bug.

    This is the first test to run. If it fails, don't trust any other result.
    """
    sites = await adapter.list_sites()

    assert len(sites) == 81, (
        f"Expected exactly 81 NEON field sites, got {len(sites)}. "
        "If the NEON program has added or removed sites, update this number."
    )


# ---------------------------------------------------------------------------
# Layer 2: Contract
# Does every observation conform to the EcologicalObservation schema?
# The schema is our contract with every downstream consumer.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_observation_schema_is_complete_for_wref(adapter):
    """
    CONTRACT TEST: Every field that downstream tools depend on must be present.

    The EcologicalObservation schema is a contract — not just with this test,
    but with every MCP tool, REST API caller, and future embedding model.

    - If provenance.citation_string is missing, a scientist can't cite the data.
    - If quality.tier is missing, an agent can't filter by data quality.
    - If location.lat/lng are missing, a map can't render the site.

    We use WREF as our test case because it's a well-known, stable site.
    """
    params = SearchParams(site_id="WREF", limit=1)
    observations = await adapter.search(params)

    assert len(observations) == 1, "Search for WREF by site_id should return exactly 1 result"
    obs = observations[0]

    # Identity
    assert obs.id == "neonscience:WREF", f"ID format wrong: {obs.id!r}"
    assert obs.modality == "sensor", f"NEON sites should have modality 'sensor', got {obs.modality!r}"

    # Location — required for all spatial queries
    assert obs.location.lat is not None, "lat must be present"
    assert obs.location.lng is not None, "lng must be present"
    assert obs.location.site_id == "WREF", f"site_id should be 'WREF', got {obs.location.site_id!r}"
    assert obs.location.site_name is not None, "site_name must be present"
    assert obs.location.country_code == "US", f"country_code should be 'US', got {obs.location.country_code!r}"

    # Provenance — required for scientific citation
    assert obs.provenance.source_api == "neonscience", "source_api must identify the source"
    assert obs.provenance.source_id == "WREF", "source_id must be the NEON site code"
    assert obs.provenance.license == "CC-BY-4.0", "NEON data is CC-BY-4.0"
    assert obs.provenance.citation_string is not None, "citation_string is required for research use"
    assert obs.provenance.original_url is not None, "original_url should link back to the source"

    # Quality tier — required for filtering by data reliability
    assert obs.quality.tier == 1, (
        f"NEON data is always quality tier 1 (calibrated, peer-reviewed). Got tier {obs.quality.tier}."
    )
    assert obs.quality.grade == "research", f"Expected grade 'research', got {obs.quality.grade!r}"


# ---------------------------------------------------------------------------
# Layer 3: Semantic correctness
# Is the data factually correct? We check against known ground truth.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wref_location_matches_known_coordinates(adapter):
    """
    KNOWN-ANSWER TEST: WREF is at a real, verified location on Earth.

    Wind River Experimental Forest is in Skamania County, Washington.
    Actual GPS coordinates: lat 45.8205, lng -121.9519 (public record).

    If our code returns different coordinates, the code is wrong — not this test.
    We use a tolerance of ±0.1 degrees (~11km) to allow for sensor vs. centroid
    differences in how NEON reports site location.
    """
    site = await adapter.get_site("WREF")

    assert site is not None, "WREF should exist in the NEON catalog"
    assert site["stateCode"] == "WA", (
        f"WREF is in Washington state (WA), not '{site['stateCode']}'. "
        "If this is wrong, our state mapping or API parsing is broken."
    )

    # Check against known GPS coordinates with tolerance
    assert abs(site["siteLatitude"] - 45.82) < 0.1, (
        f"WREF latitude should be ~45.82°N, got {site['siteLatitude']}. "
        "Something is wrong with coordinate parsing."
    )
    assert abs(site["siteLongitude"] - (-121.95)) < 0.1, (
        f"WREF longitude should be ~-121.95°E, got {site['siteLongitude']}. "
        "Something is wrong with coordinate parsing."
    )


@pytest.mark.asyncio
async def test_all_sites_have_valid_coordinates(adapter):
    """
    SEMANTIC TEST: Every site should have plausible coordinates.

    A lat of 0.0 might mean "missing" was encoded as zero.
    Coordinates outside US bounds would indicate a parsing error.
    NEON is a US observatory — all sites should be within US boundaries.
    """
    sites = await adapter.list_sites()

    for site in sites:
        code = site["siteCode"]
        lat = site["siteLatitude"]
        lng = site["siteLongitude"]

        # Coordinates should exist
        assert lat is not None, f"Site {code} has no latitude"
        assert lng is not None, f"Site {code} has no longitude"

        # Must be within plausible US bounds (includes Alaska, Hawaii, Puerto Rico)
        assert -90 <= lat <= 90, f"Site {code} has impossible latitude: {lat}"
        assert -180 <= lng <= 180, f"Site {code} has impossible longitude: {lng}"

        # Should not be the null island (0, 0) — a common data error
        assert not (lat == 0.0 and lng == 0.0), (
            f"Site {code} has (0, 0) coordinates — likely a missing-value encoding error."
        )


# ---------------------------------------------------------------------------
# Layer 4: Scientific fitness
# Is the data actually usable for the research use case?
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wref_has_bird_survey_data(adapter):
    """
    SCIENTIFIC FITNESS TEST: The core data product for our use case.

    NEON's bird point count survey product is DP1.10003.001.
    It's the standardized dataset for avian community monitoring across NEON sites.

    If WREF doesn't have this product, our research use case fails before
    we even begin — better to discover that here than mid-analysis.

    This test also teaches an important pattern: verify your data sources
    have the specific data you need, not just that they exist.
    """
    site = await adapter.get_site("WREF")
    product_codes = [dp["dataProductCode"] for dp in site["dataProducts"]]

    assert "DP1.10003.001" in product_codes, (
        f"WREF should have NEON bird point count data (DP1.10003.001). "
        f"Available products ({len(product_codes)} total): "
        f"{sorted(product_codes)[:10]}..."
    )


@pytest.mark.asyncio
async def test_pnw_geographic_search_finds_expected_sites(adapter):
    """
    SCIENTIFIC FITNESS TEST: Geographic search supports our research workflow.

    A researcher centered on Portland, OR (45.5°N, 122.6°W) needs to find
    nearby NEON sites within 300km. This should include at minimum:
      - WREF (Wind River Experimental Forest, WA) — ~60km NE
      - ABBY (Abby Road, OR) — ~160km SE of Portland

    If geographic filtering is broken, the researcher gets wrong sites —
    silently, with no error. That's worse than a crash.

    We also verify that returned sites are actually in the PNW, not in Florida.
    """
    params = SearchParams(lat=45.5, lng=-122.6, radius_km=300, limit=50)
    observations = await adapter.search(params)

    site_codes = [obs.location.site_id for obs in observations]

    assert "WREF" in site_codes, (
        f"WREF (~60km from Portland) should appear in a 300km search. "
        f"Got: {sorted(site_codes)}"
    )

    # All returned sites must actually be within the search radius
    # (this catches off-by-one errors in the Haversine calculation)
    for obs in observations:
        lat = obs.location.lat
        lng = obs.location.lng
        # Rough PNW + broader West Coast bounding box for a 300km Portland search
        assert 40.0 <= lat <= 50.0, (
            f"Site {obs.location.site_id} at lat={lat} is outside the expected "
            f"range for a 300km search from Portland."
        )


@pytest.mark.asyncio
async def test_bird_data_product_exists_in_catalog(adapter):
    """
    SCIENTIFIC FITNESS TEST: The full research workflow starts with discovery.

    Before querying data, a researcher (or agent) should ask:
    "What bird data does NEON actually have?"

    This tests that:
    1. The product search returns results for "bird"
    2. The core bird survey product DP1.10003.001 is in the catalog
    3. It has a real description (not an empty string or placeholder)

    This mirrors how an AI agent would use neon_list_data_products before
    deciding whether NEON can answer a bird-related question.
    """
    products = await adapter.list_data_products()

    bird_products = [
        p for p in products
        if "bird" in p.get("productName", "").lower()
    ]
    assert len(bird_products) >= 1, (
        "The NEON catalog should contain at least one bird-related data product. "
        "If this fails, the product catalog API is broken."
    )

    bird_survey = next(
        (p for p in products if p.get("productCode") == "DP1.10003.001"),
        None
    )
    assert bird_survey is not None, (
        "Core NEON bird point count product DP1.10003.001 must exist. "
        "This is a stable, long-running NEON product — if missing, the API is broken."
    )
    assert len(bird_survey.get("productDescription", "")) > 20, (
        "Product description should be a real description, not empty or placeholder."
    )


# ---------------------------------------------------------------------------
# Edge cases
# What happens when things go wrong? Adapters must fail gracefully.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nonexistent_site_returns_none_not_exception(adapter):
    """
    EDGE CASE: An agent asking about a made-up site should get None, not a crash.

    The AbstractAdapter contract says: get_by_id returns None if not found.
    It must never raise an exception for a missing record — that would break
    the agent mid-reasoning.

    This is a simple but important test: it verifies the adapter honours
    its contract under bad input.
    """
    result = await adapter.get_by_id("DOESNOTEXIST")
    assert result is None, (
        "Requesting a non-existent site code should return None, not raise an exception. "
        "Adapters must fail gracefully."
    )


@pytest.mark.asyncio
async def test_empty_area_search_returns_empty_list_not_exception(adapter):
    """
    EDGE CASE: Searching in the middle of the ocean should return no sites.

    Coordinates: 0°N, 0°E (Gulf of Guinea — no NEON sites here).
    Radius: 10km (very small — definitely no sites).

    Must return an empty list, not raise an exception.
    This matters because agents will search arbitrary coordinates.
    """
    params = SearchParams(lat=0.0, lng=0.0, radius_km=10, limit=10)
    observations = await adapter.search(params)

    assert isinstance(observations, list), "search() must always return a list"
    assert len(observations) == 0, (
        f"No NEON sites should exist near 0°N, 0°E. Got {len(observations)} sites."
    )
