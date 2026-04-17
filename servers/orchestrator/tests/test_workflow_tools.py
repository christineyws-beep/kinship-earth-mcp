"""
Tests for workflow composition tools (Phase 2.2).
"""

import pytest

from kinship_orchestrator.server import mcp, ecology_cite, ecology_export
from kinship_shared.citations import get_citations, CITATIONS
from kinship_shared.export import to_csv, to_geojson


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def test_biodiversity_assessment_registered():
    tool_names = list(mcp._tool_manager._tools.keys())
    assert "ecology_biodiversity_assessment" in tool_names


def test_temporal_comparison_registered():
    tool_names = list(mcp._tool_manager._tools.keys())
    assert "ecology_temporal_comparison" in tool_names


def test_export_registered():
    tool_names = list(mcp._tool_manager._tools.keys())
    assert "ecology_export" in tool_names


def test_cite_registered():
    tool_names = list(mcp._tool_manager._tools.keys())
    assert "ecology_cite" in tool_names


# ---------------------------------------------------------------------------
# Citations
# ---------------------------------------------------------------------------


def test_cite_all_sources():
    """All 9 data sources should have citations."""
    result = get_citations()
    assert result["count"] == 9
    for source_id in ["obis", "neonscience", "era5", "ebird", "inaturalist", "gbif", "usgs-nwis", "xeno-canto", "soilgrids"]:
        assert source_id in result["citations"], f"Missing citation for {source_id}"
        cite = result["citations"][source_id]
        assert "bibtex" in cite
        assert "apa" in cite
        assert "license" in cite


def test_cite_specific_source():
    """Should return citation for a single requested source."""
    result = get_citations(["era5"])
    assert result["count"] == 1
    assert "era5" in result["citations"]
    assert result["citations"]["era5"]["doi"] == "10.1002/qj.3803"


@pytest.mark.asyncio
async def test_cite_tool_returns_all():
    """ecology_cite with no args should return all sources."""
    result = await ecology_cite()
    assert result["count"] == 9


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def test_export_csv_has_headers():
    """CSV output should have proper header row."""
    observations = [
        {"id": "obis:1", "scientific_name": "Delphinus delphis", "lat": 41.5, "lng": -70.7,
         "observed_at": "2023-06-15", "source": "obis", "quality_tier": 2, "license": "CC-BY",
         "source_url": "https://obis.org/1", "relevance": {"score": 0.85}},
    ]
    csv_str = to_csv(observations)
    lines = csv_str.strip().split("\n")
    # First lines are comments
    header_line = [l for l in lines if not l.startswith("#")][0]
    assert "id" in header_line
    assert "scientific_name" in header_line
    assert "relevance_score" in header_line
    # Data row
    data_line = [l for l in lines if not l.startswith("#")][1]
    assert "Delphinus delphis" in data_line


def test_export_geojson_format():
    """GeoJSON output should be a valid FeatureCollection."""
    observations = [
        {"id": "obis:1", "scientific_name": "Delphinus delphis", "lat": 41.5, "lng": -70.7,
         "observed_at": "2023-06-15", "source": "obis", "quality_tier": 2,
         "relevance": {"score": 0.85}},
    ]
    geojson = to_geojson(observations)
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 1
    feature = geojson["features"][0]
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "Point"
    assert feature["geometry"]["coordinates"] == [-70.7, 41.5]  # [lon, lat]
    assert feature["properties"]["scientific_name"] == "Delphinus delphis"


def test_export_bibtex_has_dois():
    """BibTeX output should include DOIs where available."""
    from kinship_shared.export import to_bibtex
    bibtex = to_bibtex(["era5", "soilgrids"])
    assert "10.1002/qj.3803" in bibtex
    assert "10.5194/soil-7-217-2021" in bibtex
