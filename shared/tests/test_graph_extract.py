"""
Tests for conversation-to-graph extraction pipeline.
"""

import uuid

import pytest

from kinship_shared.graph_extract import EntityExtractor, ExtractedGraph
from kinship_shared.graph_schema import make_species_id, make_location_id
from kinship_shared.storage import ConversationTurn


def _make_turn(**kwargs) -> ConversationTurn:
    defaults = {
        "id": str(uuid.uuid4()),
        "conversation_id": "conv-1",
        "user_id": "researcher-1",
        "tool_name": "ecology_search",
        "tool_params": {"scientificname": "Delphinus delphis", "lat": 41.5, "lon": -70.7},
        "tool_result_summary": {},
        "lat": 41.5,
        "lng": -70.7,
        "taxa_mentioned": ["Delphinus delphis"],
    }
    defaults.update(kwargs)
    return ConversationTurn(**defaults)


def _sample_search_result():
    return {
        "species_occurrences": [
            {
                "scientific_name": "Delphinus delphis",
                "common_name": "Common Dolphin",
                "lat": 41.5,
                "lng": -70.7,
                "observed_at": "2023-06-15",
                "source": "obis",
                "quality_tier": 2,
            },
            {
                "scientific_name": "Tursiops truncatus",
                "common_name": "Bottlenose Dolphin",
                "lat": 41.6,
                "lng": -70.5,
                "observed_at": "2023-07-01",
                "source": "obis",
                "quality_tier": 2,
            },
        ],
        "species_count": 2,
        "neon_sites": [
            {"site_code": "HARV", "site_name": "Harvard Forest", "lat": 42.54, "lng": -72.17, "state": "MA"},
        ],
        "neon_site_count": 1,
        "climate": None,
        "search_context": {"sources_queried": ["obis", "neon"]},
    }


def _sample_env_context_result():
    return {
        "query": {"lat": 45.82, "lon": -121.95, "focal_date": "2023-06-15",
                  "climate_window": {"start": "2023-06-08", "end": "2023-06-15"}},
        "climate": {
            "daily": {
                "time": ["2023-06-12", "2023-06-13", "2023-06-14"],
                "temperature_2m_mean": [18.5, 20.1, 19.3],
            },
        },
        "nearby_neon_sites": [
            {"site_code": "WREF", "site_name": "Wind River", "lat": 45.82, "lng": -121.95},
        ],
    }


extractor = EntityExtractor()


def test_extract_species_from_search():
    """Should extract species entities from search results."""
    turn = _make_turn()
    result = _sample_search_result()
    extracted = extractor.extract_from_turn(turn, result)

    species_entities = [e for e in extracted.entities if e.entity_type == "species"]
    species_ids = {e.id for e in species_entities}
    assert make_species_id("Delphinus delphis") in species_ids
    assert make_species_id("Tursiops truncatus") in species_ids


def test_extract_location_from_search():
    """Should extract location entity with correct ID format."""
    turn = _make_turn()
    result = _sample_search_result()
    extracted = extractor.extract_from_turn(turn, result)

    location_entities = [e for e in extracted.entities if e.entity_type == "location"]
    location_ids = {e.id for e in location_entities}
    assert make_location_id(41.5, -70.7) in location_ids


def test_extract_observed_at_relationship():
    """Should create species→location OBSERVED_AT relationships."""
    turn = _make_turn()
    result = _sample_search_result()
    extracted = extractor.extract_from_turn(turn, result)

    observed_rels = [r for r in extracted.relationships if r.relationship_type == "OBSERVED_AT"]
    assert len(observed_rels) >= 2  # At least one per species


def test_extract_neon_site():
    """Should extract NEON site entity and MONITORED_BY relationship."""
    turn = _make_turn()
    result = _sample_search_result()
    extracted = extractor.extract_from_turn(turn, result)

    neon_entities = [e for e in extracted.entities if e.entity_type == "neon_site"]
    assert len(neon_entities) >= 1
    assert neon_entities[0].id == "neon:HARV"

    monitored_rels = [r for r in extracted.relationships if r.relationship_type == "MONITORED_BY"]
    assert len(monitored_rels) >= 1


def test_extract_query_entity():
    """Should create query entity with QUERIED_ABOUT relationships."""
    turn = _make_turn()
    result = _sample_search_result()
    extracted = extractor.extract_from_turn(turn, result)

    query_entities = [e for e in extracted.entities if e.entity_type == "query"]
    assert len(query_entities) == 1

    queried_about = [r for r in extracted.relationships if r.relationship_type == "QUERIED_ABOUT"]
    # Should link to location and species
    assert len(queried_about) >= 2


def test_co_occurrence_detection():
    """Two species at same location should create CORRELATES_WITH."""
    # Both species at the same location (rounded to same ~1km)
    result = {
        "species_occurrences": [
            {"scientific_name": "Species A", "lat": 41.50, "lng": -70.70, "observed_at": "2023-06-15", "source": "obis"},
            {"scientific_name": "Species B", "lat": 41.50, "lng": -70.70, "observed_at": "2023-06-15", "source": "obis"},
        ],
        "species_count": 2,
        "neon_sites": [],
        "search_context": {"sources_queried": ["obis"]},
    }
    turn = _make_turn()
    extracted = extractor.extract_from_turn(turn, result)

    correlates = [r for r in extracted.relationships if r.relationship_type == "CORRELATES_WITH"]
    assert len(correlates) >= 1


def test_climate_facts_extracted():
    """Environmental context should produce TemporalFacts for climate."""
    turn = _make_turn(
        tool_name="ecology_get_environmental_context",
        tool_params={"lat": 45.82, "lon": -121.95, "date": "2023-06-15"},
        lat=45.82,
        lng=-121.95,
    )
    result = _sample_env_context_result()
    extracted = extractor.extract_from_turn(turn, result)

    assert len(extracted.facts) >= 1
    fact = extracted.facts[0]
    assert fact.fact_type == "climate_observation"
    assert "temp_mean" in fact.value
    assert fact.source == "era5"


def test_researcher_entity_extracted():
    """If user_id is present, should create researcher entity."""
    turn = _make_turn(user_id="researcher-42")
    result = _sample_search_result()
    extracted = extractor.extract_from_turn(turn, result)

    researcher_entities = [e for e in extracted.entities if e.entity_type == "researcher"]
    assert len(researcher_entities) == 1
    assert researcher_entities[0].id == "user:researcher-42"


def test_graph_stats_tool_registered():
    """ecology_graph_stats should be registered as an MCP tool."""
    from kinship_orchestrator.server import mcp
    tool_names = list(mcp._tool_manager._tools.keys())
    assert "ecology_graph_stats" in tool_names
