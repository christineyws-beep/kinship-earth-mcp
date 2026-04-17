"""
Tests for MCP Prompt Templates and Resources
=============================================

Verifies that prompts register correctly, accept their parameters,
and return structured content that agents can act on. These tests
call the prompt functions directly (not through MCP protocol) to
validate the data pipeline.

RUNNING:
  uv run --package kinship-orchestrator pytest servers/orchestrator/tests/test_prompts.py -v
"""

import json

import pytest

from kinship_orchestrator.server import (
    ecological_survey,
    species_report,
    site_comparison,
    data_export,
    mcp,
)


# ---------------------------------------------------------------------------
# Prompt registration
# ---------------------------------------------------------------------------


def test_prompts_are_registered():
    """All four prompts should be registered with the MCP server."""
    prompt_names = [p.name for p in mcp._prompt_manager._prompts.values()]
    assert "ecological_survey" in prompt_names
    assert "species_report" in prompt_names
    assert "site_comparison" in prompt_names
    assert "data_export" in prompt_names


def test_resource_is_registered():
    """The ecology://sources resource should be registered."""
    resource_names = list(mcp._resource_manager._resources.keys())
    assert "ecology://sources" in resource_names


# ---------------------------------------------------------------------------
# ecological_survey
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ecological_survey_returns_structured_prompt():
    """
    ecological_survey should return a string containing survey data
    and instructions for the agent.
    """
    result = await ecological_survey(
        lat=45.82, lon=-121.95, radius_km=25,
    )

    assert isinstance(result, str)
    assert "ecological survey" in result.lower()
    assert "Biodiversity Summary" in result
    assert "Climate Conditions" in result
    assert "Soil Properties" in result
    assert "survey_type" in result  # JSON data is embedded

    # Verify the embedded JSON is valid
    json_start = result.index("```json\n") + 8
    json_end = result.index("\n```", json_start)
    data = json.loads(result[json_start:json_end])
    assert data["survey_type"] == "ecological_survey"
    assert data["location"]["lat"] == 45.82
    assert "species_observations" in data
    assert "climate" in data
    assert "soil" in data


# ---------------------------------------------------------------------------
# species_report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_species_report_returns_structured_prompt():
    """
    species_report should return a string with species data and
    agent instructions.
    """
    result = await species_report(
        scientific_name="Delphinus delphis",
        lat=41.5, lon=-70.7, radius_km=200,
    )

    assert isinstance(result, str)
    assert "Delphinus delphis" in result
    assert "Distribution" in result
    assert "Audio/Media" in result

    # Verify embedded JSON
    json_start = result.index("```json\n") + 8
    json_end = result.index("\n```", json_start)
    data = json.loads(result[json_start:json_end])
    assert data["report_type"] == "species_report"
    assert data["species"] == "Delphinus delphis"
    assert "occurrences" in data
    assert "audio_recordings" in data


@pytest.mark.asyncio
async def test_species_report_global_search():
    """
    species_report with no location should search globally.
    """
    result = await species_report(scientific_name="Tursiops truncatus")

    assert isinstance(result, str)
    json_start = result.index("```json\n") + 8
    json_end = result.index("\n```", json_start)
    data = json.loads(result[json_start:json_end])
    assert data["search_area"] == "global"


# ---------------------------------------------------------------------------
# site_comparison
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_site_comparison_returns_two_sites():
    """
    site_comparison should return data for both sites.
    """
    result = await site_comparison(
        lat1=45.82, lon1=-121.95,
        lat2=42.54, lon2=-72.17,
        label1="Wind River", label2="Harvard Forest",
    )

    assert isinstance(result, str)
    assert "Wind River" in result
    assert "Harvard Forest" in result
    assert "Climate Comparison" in result

    json_start = result.index("```json\n") + 8
    json_end = result.index("\n```", json_start)
    data = json.loads(result[json_start:json_end])
    assert data["comparison_type"] == "site_comparison"
    assert "Wind River" in data["sites"]
    assert "Harvard Forest" in data["sites"]


# ---------------------------------------------------------------------------
# data_export
# ---------------------------------------------------------------------------


def test_data_export_csv():
    """data_export with csv format returns CSV instructions."""
    result = data_export(format="csv")
    assert isinstance(result, str)
    assert "CSV" in result or "csv" in result
    assert "id, scientific_name" in result


def test_data_export_geojson():
    """data_export with geojson format returns GeoJSON instructions."""
    result = data_export(format="geojson")
    assert "GeoJSON" in result
    assert "FeatureCollection" in result


def test_data_export_markdown():
    """data_export with markdown format returns Markdown instructions."""
    result = data_export(format="markdown")
    assert "Markdown" in result
    assert "Species Table" in result


def test_data_export_bibtex():
    """data_export with bibtex format returns BibTeX instructions."""
    result = data_export(format="bibtex")
    assert "BibTeX" in result
    assert "DOI" in result
