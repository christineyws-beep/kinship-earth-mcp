"""
Tests for conversation storage layer.

Uses a temporary SQLite database for each test to ensure isolation.
"""

import asyncio
import uuid
from datetime import datetime

import pytest

from kinship_shared.storage import ConversationTurn
from kinship_shared.storage_sqlite import SQLiteConversationStore


@pytest.fixture
async def store(tmp_path):
    """Create a fresh SQLiteConversationStore with a temp database."""
    db_path = str(tmp_path / "test_conversations.db")
    s = SQLiteConversationStore(db_path=db_path)
    await s.initialize()
    return s


def _make_turn(**kwargs) -> ConversationTurn:
    """Create a ConversationTurn with sensible defaults."""
    defaults = {
        "id": str(uuid.uuid4()),
        "conversation_id": "conv-1",
        "tool_name": "ecology_search",
        "tool_params": {"scientificname": "Delphinus delphis", "lat": 41.5, "lon": -70.7},
        "tool_result_summary": {"species_count": 5, "sources_queried": ["obis", "inat"]},
        "lat": 41.5,
        "lng": -70.7,
        "taxa_mentioned": ["Delphinus delphis"],
    }
    defaults.update(kwargs)
    return ConversationTurn(**defaults)


@pytest.mark.asyncio
async def test_store_and_retrieve_turn(store):
    """Round-trip a turn to SQLite and read it back."""
    turn = _make_turn()
    await store.store_turn(turn)

    turns = await store.get_conversation("conv-1")
    assert len(turns) == 1
    assert turns[0].id == turn.id
    assert turns[0].tool_name == "ecology_search"
    assert turns[0].taxa_mentioned == ["Delphinus delphis"]
    assert turns[0].lat == 41.5
    assert turns[0].lng == -70.7


@pytest.mark.asyncio
async def test_get_turns_by_location(store):
    """Store turns at different locations, query by proximity."""
    # Woods Hole, MA
    turn1 = _make_turn(id="t1", lat=41.5, lng=-70.7)
    # San Francisco, CA (far away)
    turn2 = _make_turn(id="t2", lat=37.7, lng=-122.4, taxa_mentioned=["Enhydra lutris"])
    # Near Woods Hole
    turn3 = _make_turn(id="t3", lat=41.6, lng=-70.5, taxa_mentioned=["Balaenoptera musculus"])

    await store.store_turn(turn1)
    await store.store_turn(turn2)
    await store.store_turn(turn3)

    # Query near Woods Hole — should find t1 and t3, not t2
    nearby = await store.get_turns_by_location(lat=41.5, lng=-70.7, radius_km=50)
    turn_ids = {t.id for t in nearby}
    assert "t1" in turn_ids
    assert "t3" in turn_ids
    assert "t2" not in turn_ids


@pytest.mark.asyncio
async def test_get_turns_by_taxon(store):
    """Store turns mentioning different species, query by name."""
    turn1 = _make_turn(id="t1", taxa_mentioned=["Delphinus delphis"])
    turn2 = _make_turn(id="t2", taxa_mentioned=["Tursiops truncatus"])
    turn3 = _make_turn(id="t3", taxa_mentioned=["Delphinus delphis", "Balaenoptera musculus"])

    await store.store_turn(turn1)
    await store.store_turn(turn2)
    await store.store_turn(turn3)

    # Query for Delphinus — should find t1 and t3
    results = await store.get_turns_by_taxon("Delphinus delphis")
    turn_ids = {t.id for t in results}
    assert "t1" in turn_ids
    assert "t3" in turn_ids
    assert "t2" not in turn_ids


@pytest.mark.asyncio
async def test_add_feedback(store):
    """Store a turn, add feedback, verify it's persisted."""
    turn = _make_turn(id="t-feedback")
    await store.store_turn(turn)

    found = await store.add_feedback("t-feedback", "helpful")
    assert found is True

    turns = await store.get_conversation("conv-1")
    assert turns[0].feedback == "helpful"
    assert turns[0].feedback_at is not None


@pytest.mark.asyncio
async def test_add_feedback_missing_turn(store):
    """Feedback on nonexistent turn returns False."""
    found = await store.add_feedback("nonexistent", "helpful")
    assert found is False


@pytest.mark.asyncio
async def test_concurrent_writes(store):
    """Write 10 turns concurrently, verify all stored."""
    turns = [_make_turn(id=f"concurrent-{i}", conversation_id="conv-concurrent") for i in range(10)]
    await asyncio.gather(*(store.store_turn(t) for t in turns))

    stored = await store.get_conversation("conv-concurrent")
    assert len(stored) == 10
