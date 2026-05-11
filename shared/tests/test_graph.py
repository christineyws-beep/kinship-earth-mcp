"""
Tests for the ecological knowledge graph.
"""

from datetime import datetime, timezone

import pytest

from kinship_shared.graph_schema import (
    GraphEntity,
    GraphRelationship,
    TemporalFact,
    make_species_id,
    make_location_id,
)
from kinship_shared.graph_store import EcologicalGraph


@pytest.fixture
async def graph(tmp_path):
    db_path = str(tmp_path / "test_graph.db")
    g = EcologicalGraph(db_path=db_path)
    await g.initialize()
    return g


def _now():
    return datetime.now(tz=timezone.utc)


@pytest.mark.asyncio
async def test_add_and_get_entity(graph):
    entity = GraphEntity(
        id="species:delphinus_delphis",
        entity_type="species",
        name="Delphinus delphis",
        properties={"common_name": "Common Dolphin"},
    )
    await graph.add_entity(entity)

    retrieved = await graph.get_entity("species:delphinus_delphis")
    assert retrieved is not None
    assert retrieved.name == "Delphinus delphis"
    assert retrieved.properties["common_name"] == "Common Dolphin"


@pytest.mark.asyncio
async def test_add_relationship(graph):
    sp = GraphEntity(id="species:sp1", entity_type="species", name="Species 1")
    loc = GraphEntity(id="location:41.50_-70.70", entity_type="location", name="Woods Hole")
    await graph.add_entity(sp)
    await graph.add_entity(loc)

    rel = GraphRelationship(
        source_id="species:sp1",
        target_id="location:41.50_-70.70",
        relationship_type="OBSERVED_AT",
    )
    await graph.add_relationship(rel)

    rels = await graph.get_relationships("species:sp1")
    assert len(rels) >= 1
    assert any(r.target_id == "location:41.50_-70.70" for r in rels)


@pytest.mark.asyncio
async def test_get_neighbors(graph):
    sp = GraphEntity(id="species:sp1", entity_type="species", name="Species 1")
    loc = GraphEntity(id="location:loc1", entity_type="location", name="Location 1")
    site = GraphEntity(id="neon:HARV", entity_type="neon_site", name="Harvard Forest")
    await graph.add_entity(sp)
    await graph.add_entity(loc)
    await graph.add_entity(site)

    await graph.add_relationship(GraphRelationship(
        source_id="species:sp1", target_id="location:loc1", relationship_type="OBSERVED_AT",
    ))
    await graph.add_relationship(GraphRelationship(
        source_id="location:loc1", target_id="neon:HARV", relationship_type="MONITORED_BY",
    ))

    # Depth 1 from species — should find location
    result = await graph.get_neighbors("species:sp1", depth=1)
    neighbor_ids = {n["id"] for n in result["neighbors"]}
    assert "location:loc1" in neighbor_ids

    # Depth 2 from species — should also find NEON site
    result = await graph.get_neighbors("species:sp1", depth=2)
    neighbor_ids = {n["id"] for n in result["neighbors"]}
    assert "neon:HARV" in neighbor_ids


@pytest.mark.asyncio
async def test_find_co_occurring_species(graph):
    sp1 = GraphEntity(id="species:sp1", entity_type="species", name="Species 1")
    sp2 = GraphEntity(id="species:sp2", entity_type="species", name="Species 2")
    loc = GraphEntity(id="location:loc1", entity_type="location", name="Location 1")
    await graph.add_entity(sp1)
    await graph.add_entity(sp2)
    await graph.add_entity(loc)

    await graph.add_relationship(GraphRelationship(
        source_id="species:sp1", target_id="location:loc1", relationship_type="OBSERVED_AT",
    ))
    await graph.add_relationship(GraphRelationship(
        source_id="species:sp2", target_id="location:loc1", relationship_type="OBSERVED_AT",
    ))

    co = await graph.find_co_occurring_species("species:sp1", min_evidence=1)
    assert len(co) == 1
    assert co[0]["species_id"] == "species:sp2"


@pytest.mark.asyncio
async def test_temporal_fact_current(graph):
    fact = TemporalFact(
        id="fact-1",
        entity_id="location:41.50_-70.70",
        fact_type="temperature_normal",
        value={"mean_june": 18.5},
        valid_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
        source="era5",
    )
    await graph.add_fact(fact)

    current = await graph.get_current_facts("location:41.50_-70.70")
    assert len(current) == 1
    assert current[0].value["mean_june"] == 18.5


@pytest.mark.asyncio
async def test_temporal_fact_superseded(graph):
    fact1 = TemporalFact(
        id="fact-1",
        entity_id="location:loc1",
        fact_type="temperature_normal",
        value={"mean_june": 18.5},
        valid_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
        source="era5",
    )
    fact2 = TemporalFact(
        id="fact-2",
        entity_id="location:loc1",
        fact_type="temperature_normal",
        value={"mean_june": 19.2},
        valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        source="era5",
    )
    await graph.add_fact(fact1)
    await graph.add_fact(fact2)

    # Only fact2 should be current
    current = await graph.get_current_facts("location:loc1")
    assert len(current) == 1
    assert current[0].id == "fact-2"

    # fact1 should be superseded
    old = await graph.get_facts_at_time(
        "location:loc1", datetime(2022, 6, 1, tzinfo=timezone.utc)
    )
    assert len(old) == 1
    assert old[0].id == "fact-1"


@pytest.mark.asyncio
async def test_save_and_load(tmp_path):
    db_path = str(tmp_path / "test_persist.db")

    # Create and populate
    g1 = EcologicalGraph(db_path=db_path)
    await g1.initialize()
    await g1.add_entity(GraphEntity(id="species:sp1", entity_type="species", name="Species 1"))
    await g1.add_entity(GraphEntity(id="location:loc1", entity_type="location", name="Loc 1"))
    await g1.add_relationship(GraphRelationship(
        source_id="species:sp1", target_id="location:loc1", relationship_type="OBSERVED_AT",
    ))
    await g1.add_fact(TemporalFact(
        id="fact-1", entity_id="location:loc1", fact_type="temp",
        value={"mean": 20}, valid_from=_now(), source="test",
    ))
    await g1.save()

    # Load into a new instance
    g2 = EcologicalGraph(db_path=db_path)
    await g2.initialize()  # This calls load()

    assert g2.entity_count() == 2
    assert g2.relationship_count() == 1
    assert g2.fact_count() == 1

    entity = await g2.get_entity("species:sp1")
    assert entity is not None
    assert entity.name == "Species 1"


@pytest.mark.asyncio
async def test_entity_mention_count_increments(graph):
    entity1 = GraphEntity(id="species:sp1", entity_type="species", name="Species 1")
    entity2 = GraphEntity(id="species:sp1", entity_type="species", name="Species 1")

    await graph.add_entity(entity1)
    await graph.add_entity(entity2)

    result = await graph.get_entity("species:sp1")
    assert result.mention_count == 2


def test_make_species_id():
    assert make_species_id("Delphinus delphis") == "species:delphinus_delphis"


def test_make_location_id():
    assert make_location_id(41.5, -70.7) == "location:41.50_-70.70"
