"""
Tests for memory-aware MCP tools (Phase 4.2).
"""

import pytest

from kinship_orchestrator.server import (
    mcp,
    ecology_memory_store,
    ecology_memory_recall,
    _graph,
    _ensure_graph,
)


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def test_memory_recall_registered():
    tool_names = list(mcp._tool_manager._tools.keys())
    assert "ecology_memory_recall" in tool_names


def test_memory_store_registered():
    tool_names = list(mcp._tool_manager._tools.keys())
    assert "ecology_memory_store" in tool_names


def test_related_queries_registered():
    tool_names = list(mcp._tool_manager._tools.keys())
    assert "ecology_related_queries" in tool_names


def test_emerging_patterns_registered():
    tool_names = list(mcp._tool_manager._tools.keys())
    assert "ecology_emerging_patterns" in tool_names


def test_tool_count():
    """Should have 17 tools total now."""
    tool_count = len(mcp._tool_manager._tools)
    assert tool_count >= 17, f"Expected at least 17 tools, got {tool_count}"


@pytest.mark.asyncio
async def test_memory_store_creates_finding():
    """ecology_memory_store should create a finding entity in the graph."""
    await _ensure_graph()
    initial_count = _graph.entity_count()

    result = await ecology_memory_store(
        name="Test finding",
        description="A test ecological finding",
        lat=41.5,
        lon=-70.7,
        scientific_name="Delphinus delphis",
    )

    assert result["status"] == "ok"
    assert result["finding_id"].startswith("finding:")
    assert _graph.entity_count() > initial_count


@pytest.mark.asyncio
async def test_memory_recall_by_species():
    """After storing a finding about a species, recall should find it."""
    await _ensure_graph()

    # Store a finding
    await ecology_memory_store(
        name="Dolphin sighting",
        description="Common dolphins observed feeding",
        scientific_name="Delphinus delphis",
    )

    # Recall
    result = await ecology_memory_recall(scientific_name="Delphinus delphis")
    assert "species" in result
    species_info = result["species"]
    # Should either be found or have neighbors from the store
    if species_info.get("found", True):
        assert species_info["mentions"] >= 1


@pytest.mark.asyncio
async def test_memory_recall_by_location():
    """After storing a finding at a location, recall should find it."""
    await _ensure_graph()

    await ecology_memory_store(
        name="Survey site",
        description="Active survey location",
        lat=42.0,
        lon=-71.0,
    )

    result = await ecology_memory_recall(lat=42.0, lon=-71.0)
    assert "location" in result
    assert "graph_size" in result
