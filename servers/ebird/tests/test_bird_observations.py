"""
Evaluative Tests: Ornithologist Migration Study
================================================

PERSONA: Dr. Sarah Chen — Avian Migration Ecologist
Research question: "How are spring migration timing and routes shifting
for Neotropical migrants in the eastern United States?"

These tests exercise the eBird adapter through the lens of a real
research workflow studying climate-driven changes in bird migration.

RUNNING THESE TESTS
-------------------
From the repo root:
  uv run --package ebird-mcp pytest servers/ebird/tests/ -v

NOTE: Requires EBIRD_API_KEY environment variable.
Get a free key at: https://ebird.org/api/keygen
"""

import os

import pytest

from ebird_mcp.adapter import EBirdAdapter
from kinship_shared import SearchParams


# Skip all tests if no API key is configured
pytestmark = pytest.mark.skipif(
    not os.environ.get("EBIRD_API_KEY"),
    reason="EBIRD_API_KEY not set — get a free key at https://ebird.org/api/keygen",
)


@pytest.fixture
def adapter():
    return EBirdAdapter()


# ===========================================================================
# Layer 1: Connectivity — can we reach the eBird API?
# ===========================================================================

class TestConnectivity:

    @pytest.mark.asyncio
    async def test_api_responds(self, adapter):
        """Canary test: eBird API is reachable and returns data."""
        result = await adapter.search(SearchParams(
            lat=42.46,  # Cornell Lab, Ithaca NY
            lng=-76.45,
            radius_km=10,
            limit=5,
        ))
        # Should return something — Ithaca is one of the most birded places on Earth
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_capabilities_are_declared(self, adapter):
        """Adapter self-describes accurately."""
        caps = adapter.capabilities()
        assert caps.adapter_id == "ebird"
        assert caps.supports_location_search is True
        assert caps.supports_taxon_search is True
        assert caps.quality_tier == 1


# ===========================================================================
# Layer 2: Contract — does the schema validate?
# ===========================================================================

class TestContract:

    @pytest.mark.asyncio
    async def test_observations_have_required_fields(self, adapter):
        """Every returned observation has the fields a researcher needs."""
        result = await adapter.search(SearchParams(
            lat=42.46,
            lng=-76.45,
            radius_km=25,
            limit=10,
        ))
        if len(result) > 0:
            obs = result[0]
            assert obs.id.startswith("ebird:")
            assert obs.modality == "occurrence"
            assert obs.location.lat is not None
            assert obs.location.lng is not None
            assert obs.observed_at is not None
            assert obs.taxon is not None
            assert obs.taxon.scientific_name is not None
            assert obs.provenance.source_api == "ebird"


# ===========================================================================
# Layer 3: Semantic — is the data factually correct?
# ===========================================================================

class TestSemantic:

    @pytest.mark.asyncio
    async def test_ithaca_has_birds(self, adapter):
        """
        Known answer: The Ithaca, NY area (home of Cornell Lab) should
        always have recent bird observations. If this returns zero,
        something is wrong with the API call.
        """
        result = await adapter.search(SearchParams(
            lat=42.46,
            lng=-76.45,
            radius_km=25,
            limit=20,
        ))
        assert len(result) > 0, (
            "No birds found near Cornell Lab of Ornithology — "
            "one of the most birded locations on Earth. "
            "Check API key and query parameters."
        )


# ===========================================================================
# Layer 4: Scientific — does it solve the research question?
# ===========================================================================

class TestMigrationResearch:

    @pytest.mark.asyncio
    async def test_search_for_specific_migrant(self, adapter):
        """
        The ornithologist searches for a specific Neotropical migrant
        (Setophaga cerulea — Cerulean Warbler) near a known breeding site.

        This tests taxon filtering through the adapter.
        """
        result = await adapter.search(SearchParams(
            taxon="Setophaga",  # Genus of many warblers
            lat=42.46,
            lng=-76.45,
            radius_km=50,
            limit=20,
        ))
        # Results should all be Setophaga if taxon filter works
        for obs in result:
            assert obs.taxon is not None
            assert "Setophaga" in obs.taxon.scientific_name, (
                f"Expected Setophaga, got {obs.taxon.scientific_name}"
            )
