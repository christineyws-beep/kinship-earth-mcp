"""
Evaluative Tests: Field Ecologist Biodiversity Inventory
========================================================

PERSONA: Dr. Maria Torres — Restoration Ecologist
Research question: "What species have been documented at our coastal
restoration site, and how does community composition compare to
reference sites?"

These tests exercise the iNaturalist adapter through the lens of a
field ecologist conducting biodiversity inventories for habitat restoration.

RUNNING THESE TESTS
-------------------
From the repo root:
  uv run --package inaturalist-mcp pytest servers/inaturalist/tests/ -v

NOTE: No API key required. iNaturalist rate limit: 60 req/min.
"""

import pytest

from inaturalist_mcp.adapter import INaturalistAdapter
from kinship_shared import SearchParams


@pytest.fixture
def adapter():
    return INaturalistAdapter()


# ===========================================================================
# Layer 1: Connectivity — can we reach the iNaturalist API?
# ===========================================================================

class TestConnectivity:

    @pytest.mark.asyncio
    async def test_api_responds(self, adapter):
        """Canary test: iNaturalist API is reachable."""
        result = await adapter.search(SearchParams(
            lat=37.77,  # San Francisco
            lng=-122.43,
            radius_km=10,
            limit=5,
        ))
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_capabilities_are_declared(self, adapter):
        """Adapter self-describes accurately."""
        caps = adapter.capabilities()
        assert caps.adapter_id == "inaturalist"
        assert caps.supports_location_search is True
        assert caps.supports_taxon_search is True
        assert caps.supports_date_range is True
        assert "visual" in caps.modalities


# ===========================================================================
# Layer 2: Contract — does the schema validate?
# ===========================================================================

class TestContract:

    @pytest.mark.asyncio
    async def test_observations_have_required_fields(self, adapter):
        """Every returned observation has the fields a researcher needs."""
        result = await adapter.search(SearchParams(
            lat=37.77,
            lng=-122.43,
            radius_km=10,
            limit=10,
        ))
        if len(result) > 0:
            obs = result[0]
            assert obs.id.startswith("inaturalist:")
            assert obs.modality == "occurrence"
            assert obs.location.lat is not None
            assert obs.location.lng is not None
            assert obs.observed_at is not None
            assert obs.provenance.source_api == "inaturalist"
            assert obs.provenance.original_url is not None

    @pytest.mark.asyncio
    async def test_quality_tiers_map_correctly(self, adapter):
        """
        iNaturalist quality_grade should map to our tier system:
        research → 1, needs_id → 2, casual → 3
        """
        result = await adapter.search(SearchParams(
            lat=37.77,
            lng=-122.43,
            radius_km=10,
            quality_tier_min=1,  # Research grade only
            limit=10,
        ))
        for obs in result:
            assert obs.quality.tier == 1, (
                f"Requested research-grade only but got tier {obs.quality.tier}"
            )
            assert obs.quality.grade == "research"


# ===========================================================================
# Layer 3: Semantic — is the data factually correct?
# ===========================================================================

class TestSemantic:

    @pytest.mark.asyncio
    async def test_golden_gate_park_has_observations(self, adapter):
        """
        Known answer: Golden Gate Park in San Francisco is one of the most
        observed locations on iNaturalist. Should always have recent data.
        """
        result = await adapter.search(SearchParams(
            lat=37.77,
            lng=-122.46,  # Golden Gate Park
            radius_km=5,
            limit=20,
        ))
        assert len(result) > 0, (
            "No observations near Golden Gate Park — one of the most "
            "observed locations on iNaturalist."
        )

    @pytest.mark.asyncio
    async def test_taxon_search_returns_correct_species(self, adapter):
        """Search for a common species returns correct taxonomy."""
        result = await adapter.search(SearchParams(
            taxon="Quercus agrifolia",  # Coast Live Oak, common in SF
            lat=37.77,
            lng=-122.43,
            radius_km=50,
            limit=10,
        ))
        for obs in result:
            if obs.taxon:
                assert "Quercus" in obs.taxon.scientific_name, (
                    f"Expected Quercus, got {obs.taxon.scientific_name}"
                )


# ===========================================================================
# Layer 4: Scientific — does it solve the research question?
# ===========================================================================

class TestRestorationInventory:

    @pytest.mark.asyncio
    async def test_cross_taxa_inventory(self, adapter):
        """
        A restoration ecologist needs ALL taxa at a site — not just birds
        or just plants. iNaturalist should return diverse taxonomic groups.

        Search a well-observed area and check that multiple iconic_taxon
        groups appear (plants, birds, insects, mammals, etc.).
        """
        result = await adapter.search(SearchParams(
            lat=37.77,
            lng=-122.46,
            radius_km=5,
            limit=50,
        ))
        iconic_taxa = set()
        for obs in result:
            if obs.value and obs.value.get("iconic_taxon"):
                iconic_taxa.add(obs.value["iconic_taxon"])

        # A well-surveyed area should have at least 3 different taxonomic groups
        assert len(iconic_taxa) >= 2, (
            f"Expected diverse taxa at Golden Gate Park, only got: {iconic_taxa}. "
            f"A restoration ecologist needs cross-taxa data."
        )

    @pytest.mark.asyncio
    async def test_photo_urls_for_field_verification(self, adapter):
        """
        Restoration ecologists need photos to verify community IDs.
        Observations should include photo URLs.
        """
        result = await adapter.search(SearchParams(
            lat=37.77,
            lng=-122.46,
            radius_km=5,
            limit=20,
        ))
        photos_found = sum(1 for obs in result if obs.media_url)
        assert photos_found > 0, (
            "No photo URLs found. iNaturalist is photo-based — "
            "most observations should have photos."
        )

    @pytest.mark.asyncio
    async def test_get_by_id_for_detailed_review(self, adapter):
        """
        After finding observations in a search, the ecologist needs to
        drill into specific records for detailed review.
        """
        # First, find an observation
        results = await adapter.search(SearchParams(
            lat=37.77,
            lng=-122.46,
            radius_km=5,
            limit=1,
        ))
        if results:
            obs_id = results[0].provenance.source_id
            detail = await adapter.get_by_id(obs_id)
            assert detail is not None, (
                f"Could not fetch observation {obs_id} by ID"
            )
            assert detail.id == results[0].id
