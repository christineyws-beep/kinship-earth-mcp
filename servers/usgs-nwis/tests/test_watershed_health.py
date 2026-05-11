"""
Evaluative Tests: Watershed Ecologist Stream Monitoring
=======================================================

PERSONA: Dr. James Rivera — Watershed Restoration Ecologist
Research question: "Is the Russian River watershed recovering from
the 2021-2023 drought? Are stream conditions supporting salmon spawning?"

These tests exercise the USGS NWIS adapter through the lens of a
watershed ecologist monitoring stream health for fish habitat.

RUNNING THESE TESTS
-------------------
From the repo root:
  uv run --package usgs-nwis-mcp pytest servers/usgs-nwis/tests/ -v

NOTE: No API key required. Rate limited to ~50 req/hr without key.
Get a free key at: https://api.waterdata.usgs.gov/signup
"""

import pytest

from usgs_nwis_mcp.adapter import USGSNWISAdapter
from kinship_shared import SearchParams


@pytest.fixture
def adapter():
    return USGSNWISAdapter()


# Potomac River near DC — one of the most monitored gauges in the US
POTOMAC_PARAMS = SearchParams(lat=38.95, lng=-77.13, radius_km=10, limit=10)
POTOMAC_SITE_ID = "01646500"


# ===========================================================================
# Layer 1: Connectivity — can we reach the USGS API?
# ===========================================================================

class TestConnectivity:

    @pytest.mark.asyncio
    async def test_api_responds(self, adapter):
        """Canary test: USGS NWIS API is reachable and returns data."""
        result = await adapter.search(POTOMAC_PARAMS)
        assert isinstance(result, list)
        assert len(result) > 0, (
            "Potomac River near DC should always have monitoring data. "
            "If empty, the USGS API may be down or the adapter is broken."
        )

    @pytest.mark.asyncio
    async def test_capabilities_are_declared(self, adapter):
        """Adapter self-describes accurately."""
        caps = adapter.capabilities()
        assert caps.adapter_id == "usgs-nwis"
        assert caps.supports_location_search is True
        assert caps.supports_date_range is True
        assert caps.supports_taxon_search is False
        assert "hydrological" in caps.modalities
        assert caps.quality_tier == 1
        assert caps.requires_auth is False
        assert caps.license == "public-domain"


# ===========================================================================
# Layer 2: Contract — does the schema validate?
# ===========================================================================

class TestContract:

    @pytest.mark.asyncio
    async def test_observations_have_required_fields(self, adapter):
        """Every returned observation has the fields a researcher needs."""
        result = await adapter.search(POTOMAC_PARAMS)
        assert len(result) > 0, "Expected data from Potomac River"

        for obs in result:
            assert obs.id.startswith("usgs-nwis:"), f"ID should start with 'usgs-nwis:', got {obs.id!r}"
            assert obs.location.lat is not None
            assert obs.location.lng is not None
            assert obs.observed_at is not None
            assert obs.value is not None

    @pytest.mark.asyncio
    async def test_all_observations_have_modality_hydrological(self, adapter):
        """Every USGS NWIS observation should have modality 'hydrological'."""
        result = await adapter.search(POTOMAC_PARAMS)
        assert len(result) > 0

        for obs in result:
            assert obs.modality == "hydrological", (
                f"USGS data should have modality 'hydrological', got {obs.modality!r}"
            )

    @pytest.mark.asyncio
    async def test_provenance_fields_complete(self, adapter):
        """Provenance must identify source, license, and attribution."""
        result = await adapter.search(POTOMAC_PARAMS)
        assert len(result) > 0

        for obs in result:
            assert obs.provenance.source_api == "usgs-nwis", (
                f"source_api should be 'usgs-nwis', got {obs.provenance.source_api!r}"
            )
            assert obs.provenance.license == "public-domain", (
                f"USGS data is public domain, got {obs.provenance.license!r}"
            )
            assert obs.provenance.attribution is not None and len(obs.provenance.attribution) > 10, (
                "Attribution should identify USGS as the data source"
            )
            assert obs.provenance.original_url is not None, "Must link back to USGS"

    @pytest.mark.asyncio
    async def test_quality_tier_always_1(self, adapter):
        """USGS data comes from calibrated government instruments — always tier 1."""
        result = await adapter.search(POTOMAC_PARAMS)
        assert len(result) > 0

        for obs in result:
            assert obs.quality.tier == 1, (
                f"USGS data should be tier 1 (research-grade), got tier {obs.quality.tier}"
            )
            assert obs.quality.grade == "research", (
                f"Expected grade 'research', got {obs.quality.grade!r}"
            )

    @pytest.mark.asyncio
    async def test_watershed_id_populated(self, adapter):
        """USGS sites should have HUC watershed IDs."""
        result = await adapter.search(POTOMAC_PARAMS)
        assert len(result) > 0

        for obs in result:
            assert obs.location.watershed_id is not None, (
                "USGS sites should include HUC watershed ID"
            )

    @pytest.mark.asyncio
    async def test_temporal_resolution_present(self, adapter):
        """Each observation should report its temporal resolution."""
        result = await adapter.search(POTOMAC_PARAMS)
        assert len(result) > 0

        for obs in result:
            assert obs.temporal_resolution in ("15min", "daily"), (
                f"Expected temporal_resolution '15min' or 'daily', got {obs.temporal_resolution!r}"
            )

    @pytest.mark.asyncio
    async def test_value_has_parameter_info(self, adapter):
        """Value dict should include parameter name and measurement."""
        result = await adapter.search(POTOMAC_PARAMS)
        assert len(result) > 0

        for obs in result:
            assert "parameter_name" in obs.value, "value should include parameter_name"
            assert "measurement" in obs.value, "value should include measurement"
            assert isinstance(obs.value["measurement"], (int, float)), (
                f"measurement should be numeric, got {type(obs.value['measurement'])}"
            )


# ===========================================================================
# Layer 3: Semantic — is the data factually correct?
# ===========================================================================

class TestSemantic:

    @pytest.mark.asyncio
    async def test_potomac_has_data(self, adapter):
        """
        Known answer: The Potomac River near DC (site 01646500) is one of
        the most monitored stream gauges in the US. Should always have data.
        """
        result = await adapter.search(POTOMAC_PARAMS)
        assert len(result) > 0, (
            "No data found near the Potomac River — one of the most "
            "monitored gauges in the US."
        )

    @pytest.mark.asyncio
    async def test_potomac_discharge_realistic(self, adapter):
        """
        Known answer: Potomac River discharge at site 01646500 is typically
        1,000-100,000 ft3/s depending on season. Should always be > 0.
        """
        result = await adapter.search(SearchParams(
            site_id=POTOMAC_SITE_ID,
            limit=10,
        ))
        if len(result) == 0:
            pytest.skip("No data returned for Potomac site — API may be slow")

        discharge_obs = [
            obs for obs in result
            if obs.value.get("parameter_name") == "Discharge"
        ]
        if len(discharge_obs) == 0:
            pytest.skip("No discharge data in current response")

        for obs in discharge_obs:
            measurement = obs.value["measurement"]
            assert measurement > 0, (
                f"Potomac discharge should be > 0 ft3/s, got {measurement}"
            )

    @pytest.mark.asyncio
    async def test_parameter_codes_mapped(self, adapter):
        """
        Known answer: Parameter code 00060 = Discharge, 00010 = Water temperature.
        These should have human-readable names, not just codes.
        """
        result = await adapter.search(POTOMAC_PARAMS)
        assert len(result) > 0

        param_names = {obs.value.get("parameter_name") for obs in result}
        # At least one of the default parameters should be present
        known_names = {"Discharge", "Water temperature"}
        assert param_names & known_names, (
            f"Expected at least one of {known_names} in results, got {param_names}"
        )

    @pytest.mark.asyncio
    async def test_site_search_returns_correct_site(self, adapter):
        """Searching by site ID returns data from that specific site."""
        result = await adapter.search(SearchParams(
            site_id=POTOMAC_SITE_ID,
            limit=10,
        ))
        if len(result) == 0:
            pytest.skip("No data returned for Potomac site")

        for obs in result:
            assert POTOMAC_SITE_ID in obs.location.site_id, (
                f"Site search for {POTOMAC_SITE_ID} returned data from {obs.location.site_id}"
            )


# ===========================================================================
# Layer 4: Scientific fitness — does it solve the research question?
# ===========================================================================

class TestWatershedMonitoring:

    @pytest.mark.asyncio
    async def test_site_search_by_id(self, adapter):
        """The ecologist can query a specific site by USGS site number."""
        result = await adapter.search(SearchParams(
            site_id=POTOMAC_SITE_ID,
            limit=10,
        ))
        if len(result) > 0:
            assert POTOMAC_SITE_ID in result[0].location.site_id, (
                "Site search should return data from the requested site"
            )

    @pytest.mark.asyncio
    async def test_quality_is_research_grade(self, adapter):
        """All USGS data should be tier 1 (research grade)."""
        result = await adapter.search(POTOMAC_PARAMS)
        for obs in result:
            assert obs.quality.tier == 1, (
                f"USGS data should be tier 1, got tier {obs.quality.tier}"
            )
            assert obs.quality.grade == "research"

    @pytest.mark.asyncio
    async def test_provenance_supports_citation(self, adapter):
        """A researcher must be able to cite every observation back to USGS."""
        result = await adapter.search(POTOMAC_PARAMS)
        assert len(result) > 0

        for obs in result:
            assert "usgs.gov" in obs.provenance.original_url, (
                f"original_url should link to USGS, got {obs.provenance.original_url!r}"
            )
            assert obs.provenance.institution_code == "USGS", (
                f"institution_code should be 'USGS', got {obs.provenance.institution_code!r}"
            )


# ===========================================================================
# Edge cases — graceful failure under bad input
# ===========================================================================

class TestEdgeCases:

    @pytest.mark.asyncio
    async def test_ocean_coordinates_return_empty(self, adapter):
        """Searching in the middle of the ocean should return empty, not error."""
        result = await adapter.search(SearchParams(
            lat=0.0, lng=0.0, radius_km=10, limit=10,
        ))
        assert isinstance(result, list)
        assert len(result) == 0, (
            f"No USGS sites should exist near 0°N, 0°E. Got {len(result)} results."
        )

    @pytest.mark.asyncio
    async def test_invalid_site_id_returns_empty(self, adapter):
        """A fake site ID should return empty, not crash."""
        result = await adapter.search(SearchParams(
            site_id="99999999",
            limit=10,
        ))
        assert isinstance(result, list)
        assert len(result) == 0, "Fake site ID should return empty results"

    @pytest.mark.asyncio
    async def test_large_radius_does_not_crash(self, adapter):
        """Very large radius should be clamped, not crash."""
        result = await adapter.search(SearchParams(
            lat=38.95, lng=-77.13,
            radius_km=500,  # exceeds the 200km clamp in the adapter
            limit=5,
        ))
        assert isinstance(result, list)
        # Should work but may return fewer results due to clamping
