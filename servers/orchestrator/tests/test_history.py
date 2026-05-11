"""
Tests for conversation history and usage tools.
"""

import pytest

from kinship_orchestrator.server import mcp
from kinship_shared.summarize import summarize_search_result, make_human_summary


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def test_ecology_my_history_registered():
    """ecology_my_history should be registered as an MCP tool."""
    tool_names = list(mcp._tool_manager._tools.keys())
    assert "ecology_my_history" in tool_names


def test_ecology_my_usage_registered():
    """ecology_my_usage should be registered as an MCP tool."""
    tool_names = list(mcp._tool_manager._tools.keys())
    assert "ecology_my_usage" in tool_names


def test_tool_count():
    """Tool count should include history, usage, set_api_key, and feedback."""
    tool_count = len(mcp._tool_manager._tools)
    # 4 original + feedback + set_api_key + my_history + my_usage = 8
    assert tool_count >= 8, f"Expected at least 8 tools, got {tool_count}"


# ---------------------------------------------------------------------------
# Summarization
# ---------------------------------------------------------------------------


def test_summarize_search_result():
    """summarize_search_result should extract key metrics."""
    result = {
        "species_occurrences": [
            {"scientific_name": "Delphinus delphis", "relevance": {"score": 0.85}},
            {"scientific_name": "Tursiops truncatus", "relevance": {"score": 0.72}},
        ],
        "species_count": 2,
        "neon_sites": [{"site_code": "WREF"}],
        "neon_site_count": 1,
        "climate": {"daily": {}},
        "search_context": {"sources_queried": ["obis", "neon", "era5"]},
    }

    summary = summarize_search_result("ecology_search", {}, result)
    assert summary["species_count"] == 2
    assert summary["neon_site_count"] == 1
    assert summary["climate_included"] is True
    assert len(summary["top_species"]) == 2
    assert summary["sources_queried"] == ["obis", "neon", "era5"]
    assert 0 < summary["avg_relevance"] < 1


def test_summarize_empty_result():
    """Summarize should handle empty results gracefully."""
    summary = summarize_search_result("ecology_search", {}, {})
    assert summary["species_count"] == 0
    assert summary["climate_included"] is False


def test_make_human_summary_search():
    """Human summary for ecology_search should include species and count."""
    params = {"scientificname": "Delphinus delphis", "lat": 41.5, "lon": -70.7}
    result = {"species_count": 5}
    text = make_human_summary("ecology_search", params, result)
    assert "Delphinus delphis" in text
    assert "5 results" in text


def test_make_human_summary_env_context():
    """Human summary for env context should include location."""
    params = {"lat": 45.82, "lon": -121.95, "date": "2023-06-15"}
    result = {"nearby_neon_count": 3}
    text = make_human_summary("ecology_get_environmental_context", params, result)
    assert "45.82" in text
    assert "3 NEON sites" in text
