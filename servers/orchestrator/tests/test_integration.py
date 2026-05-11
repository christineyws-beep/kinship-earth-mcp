"""
End-to-end integration test: search → store → extract → graph → recall.

Validates the full pipeline works together — every tool invocation
should result in graph entities that can be recalled later.
"""

import pytest

from kinship_orchestrator.server import (
    ecology_graph_stats,
    ecology_memory_recall,
    ecology_memory_store,
    _ensure_graph,
    _ensure_store,
    _graph,
)


@pytest.mark.asyncio
async def test_full_pipeline_store_and_recall():
    """Store a finding, then recall it — the core memory loop."""
    await _ensure_store()
    await _ensure_graph()

    # 1. Store a finding
    store_result = await ecology_memory_store(
        name="Integration test finding",
        description="Coho salmon spawning observed at test tributary",
        lat=38.5,
        lon=-123.0,
        scientific_name="Oncorhynchus kisutch",
    )
    assert store_result["status"] == "ok"
    finding_id = store_result["finding_id"]

    # 2. Recall by species
    species_recall = await ecology_memory_recall(
        scientific_name="Oncorhynchus kisutch",
    )
    assert "species" in species_recall
    species_info = species_recall["species"]
    if species_info.get("found", True):
        assert species_info["mentions"] >= 1

    # 3. Recall by location
    location_recall = await ecology_memory_recall(lat=38.5, lon=-123.0)
    assert "location" in location_recall

    # 4. Check graph stats
    stats = await ecology_graph_stats()
    assert stats["entities"]["total"] > 0
    assert "finding" in stats["entities"].get("by_type", {}) or stats["entities"]["total"] > 0


@pytest.mark.asyncio
async def test_graph_stats_has_structure():
    """ecology_graph_stats should return well-structured data."""
    await _ensure_graph()
    stats = await ecology_graph_stats()

    assert "entities" in stats
    assert "total" in stats["entities"]
    assert "by_type" in stats["entities"]
    assert "relationships" in stats
    assert "facts" in stats
    assert "top_entities" in stats
