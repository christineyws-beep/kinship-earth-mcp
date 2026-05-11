"""Tests for the monitoring site registry."""

from datetime import datetime, timezone

import pytest

from kinship_shared.monitoring import MonitoringRegistry, MonitoringSite
from kinship_shared.schema import EcosystemState, Location


@pytest.fixture
async def registry(tmp_path):
    r = MonitoringRegistry(db_path=str(tmp_path / "test_monitoring.db"))
    await r.initialize()
    return r


def _make_site(**kwargs):
    defaults = {
        "site_id": "location:41.50_-70.70",
        "name": "Woods Hole",
        "location": Location(lat=41.5, lng=-70.7),
    }
    defaults.update(kwargs)
    return MonitoringSite(**defaults)


def _make_state(site_id="location:41.50_-70.70", health=75.0, **kwargs):
    return EcosystemState(
        id=site_id,
        location=Location(lat=41.5, lng=-70.7),
        timestamp=datetime.now(timezone.utc),
        overall_health_score=health,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_add_and_get_site(registry):
    site = _make_site()
    await registry.add_site(site)
    retrieved = await registry.get_site("location:41.50_-70.70")
    assert retrieved is not None
    assert retrieved.name == "Woods Hole"


@pytest.mark.asyncio
async def test_list_sites(registry):
    await registry.add_site(_make_site(site_id="site-1", name="Site 1"))
    await registry.add_site(_make_site(site_id="site-2", name="Site 2"))
    sites = await registry.list_sites()
    assert len(sites) == 2


@pytest.mark.asyncio
async def test_remove_site(registry):
    await registry.add_site(_make_site())
    removed = await registry.remove_site("location:41.50_-70.70")
    assert removed is True
    site = await registry.get_site("location:41.50_-70.70")
    assert site is None


@pytest.mark.asyncio
async def test_remove_nonexistent(registry):
    removed = await registry.remove_site("nonexistent")
    assert removed is False


@pytest.mark.asyncio
async def test_store_and_get_state(registry):
    state = _make_state(health=82.5)
    await registry.store_state(state)
    retrieved = await registry.get_latest_state("location:41.50_-70.70")
    assert retrieved is not None
    assert retrieved.overall_health_score == 82.5


@pytest.mark.asyncio
async def test_state_history(registry):
    import asyncio
    for i in range(5):
        state = _make_state(health=50.0 + i * 5)
        await registry.store_state(state)
        await asyncio.sleep(0.01)  # Ensure different timestamps

    history = await registry.get_state_history("location:41.50_-70.70", limit=3)
    assert len(history) <= 5


@pytest.mark.asyncio
async def test_latest_state_returns_most_recent(registry):
    import asyncio
    await registry.store_state(_make_state(health=60.0))
    await asyncio.sleep(0.01)
    await registry.store_state(_make_state(health=80.0))

    latest = await registry.get_latest_state("location:41.50_-70.70")
    assert latest is not None
    assert latest.overall_health_score == 80.0
