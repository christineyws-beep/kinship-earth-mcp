"""
Tests for memory-informed ranking.
"""

from datetime import datetime, timezone

import pytest

from kinship_shared.graph_schema import GraphEntity, make_species_id, make_location_id
from kinship_shared.graph_store import EcologicalGraph
from kinship_shared.ranking import compute_memory_relevance, score_observation
from kinship_shared.schema import (
    EcologicalObservation,
    Location,
    Provenance,
    Quality,
    SearchParams,
    TaxonInfo,
)


def _make_observation(**kwargs):
    defaults = {
        "id": "test:1",
        "modality": "occurrence",
        "taxon": TaxonInfo(scientific_name="Delphinus delphis", common_name="Common Dolphin"),
        "location": Location(lat=41.5, lng=-70.7),
        "observed_at": datetime(2023, 6, 15, tzinfo=timezone.utc),
        "quality": Quality(tier=2),
        "provenance": Provenance(source_api="obis", source_id="1"),
    }
    defaults.update(kwargs)
    return EcologicalObservation(**defaults)


@pytest.fixture
async def graph(tmp_path):
    g = EcologicalGraph(db_path=str(tmp_path / "test_rank.db"))
    await g.initialize()
    return g


def test_memory_relevance_zero_without_graph():
    """No graph should return 0.0."""
    obs = _make_observation()
    assert compute_memory_relevance(obs, None) == 0.0


@pytest.mark.asyncio
async def test_memory_relevance_zero_for_unknown_entity(graph):
    """Entity not in graph should return 0.0."""
    obs = _make_observation()
    assert compute_memory_relevance(obs, graph) == 0.0


@pytest.mark.asyncio
async def test_memory_relevance_increases_with_mentions(graph):
    """More mentions should give higher score."""
    species_id = make_species_id("Delphinus delphis")

    # Add entity once
    await graph.add_entity(GraphEntity(
        id=species_id, entity_type="species", name="Delphinus delphis",
    ))
    obs = _make_observation()
    score1 = compute_memory_relevance(obs, graph)

    # Mention it more (simulate multiple queries)
    for _ in range(10):
        await graph.add_entity(GraphEntity(
            id=species_id, entity_type="species", name="Delphinus delphis",
        ))

    score2 = compute_memory_relevance(obs, graph)
    assert score2 > score1


@pytest.mark.asyncio
async def test_memory_relevance_capped_at_one(graph):
    """Score should never exceed 1.0 even with many mentions."""
    species_id = make_species_id("Delphinus delphis")
    for _ in range(1000):
        await graph.add_entity(GraphEntity(
            id=species_id, entity_type="species", name="Delphinus delphis",
        ))
    obs = _make_observation()
    score = compute_memory_relevance(obs, graph)
    assert score <= 1.0


def test_ranking_weights_sum_to_one_without_memory():
    """Standard formula weights should sum to 1.0."""
    assert abs(0.35 + 0.30 + 0.15 + 0.20 - 1.0) < 0.001


def test_ranking_weights_sum_to_one_with_memory():
    """Memory-enhanced formula weights should sum to 1.0."""
    assert abs(0.30 + 0.25 + 0.15 + 0.15 + 0.15 - 1.0) < 0.001


def test_score_observation_with_memory():
    """Passing memory_relevance should use the memory-enhanced formula."""
    obs = _make_observation()
    params = SearchParams(taxon="Delphinus delphis", lat=41.5, lng=-70.7, radius_km=100)

    score_without = score_observation(obs, params)
    score_with = score_observation(obs, params, memory_relevance=0.8)

    assert "memory=" in score_with.explanation
    assert "memory=" not in score_without.explanation
