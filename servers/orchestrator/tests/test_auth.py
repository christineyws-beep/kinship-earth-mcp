"""
Tests for auth layer and BYOK API key management.
"""

from datetime import datetime, timezone

import pytest

from kinship_orchestrator.auth import User
from kinship_orchestrator.auth_sqlite import SQLiteAuthManager
from kinship_orchestrator.server import mcp


@pytest.fixture
async def auth(tmp_path):
    """Create a fresh SQLiteAuthManager with a temp database."""
    db_path = str(tmp_path / "test_users.db")
    am = SQLiteAuthManager(db_path=db_path)
    await am.initialize()
    return am


@pytest.mark.asyncio
async def test_create_anonymous_user(auth):
    """Creating an anonymous user should return a valid user."""
    user = await auth.create_anonymous_user()
    assert user.id
    assert user.provider == "anonymous"
    assert user.tier == "free"
    assert user.queries_today == 0


@pytest.mark.asyncio
async def test_get_user(auth):
    """Should be able to retrieve a user by ID."""
    user = await auth.create_anonymous_user()
    retrieved = await auth.get_user(user.id)
    assert retrieved is not None
    assert retrieved.id == user.id


@pytest.mark.asyncio
async def test_get_nonexistent_user(auth):
    """Getting a nonexistent user returns None."""
    user = await auth.get_user("nonexistent")
    assert user is None


@pytest.mark.asyncio
async def test_rate_limit_allows_within_limit(auth):
    """User with queries below limit should pass rate check."""
    user = await auth.create_anonymous_user()
    # Set queries to 49/50
    user.queries_today = 49
    user.last_query_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    allowed = await auth.check_rate_limit(user)
    assert allowed is True


@pytest.mark.asyncio
async def test_rate_limit_blocks_over_limit(auth):
    """User at query limit should fail rate check."""
    user = await auth.create_anonymous_user()
    user.queries_today = 50
    user.last_query_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    allowed = await auth.check_rate_limit(user)
    assert allowed is False


@pytest.mark.asyncio
async def test_rate_limit_resets_daily(auth):
    """User with queries from yesterday should have count reset."""
    user = await auth.create_anonymous_user()
    user.queries_today = 50
    user.last_query_date = "2020-01-01"  # A past date
    allowed = await auth.check_rate_limit(user)
    assert allowed is True
    assert user.queries_today == 0  # Reset


@pytest.mark.asyncio
async def test_increment_usage(auth):
    """Incrementing usage should increase query count."""
    user = await auth.create_anonymous_user()
    await auth.increment_usage(user)
    assert user.queries_today == 1
    await auth.increment_usage(user)
    assert user.queries_today == 2


@pytest.mark.asyncio
async def test_byok_key_storage(auth):
    """Should store and retrieve BYOK API keys."""
    user = await auth.create_anonymous_user()
    await auth.set_api_key(user.id, "ebird", "test-key-123")

    keys = await auth.get_api_keys(user.id)
    assert keys["ebird"] == "test-key-123"


@pytest.mark.asyncio
async def test_byok_multiple_keys(auth):
    """Should store multiple service keys for one user."""
    user = await auth.create_anonymous_user()
    await auth.set_api_key(user.id, "ebird", "ebird-key")
    await auth.set_api_key(user.id, "xeno-canto", "xc-key")

    keys = await auth.get_api_keys(user.id)
    assert keys["ebird"] == "ebird-key"
    assert keys["xeno-canto"] == "xc-key"


def test_ecology_set_api_key_registered():
    """ecology_set_api_key should be registered as an MCP tool."""
    tool_names = list(mcp._tool_manager._tools.keys())
    assert "ecology_set_api_key" in tool_names


def test_auth_disabled_by_default():
    """Auth should be disabled by default (tools work without it)."""
    from kinship_orchestrator.server import _auth_enabled
    # In test environment, KINSHIP_AUTH_ENABLED is not set
    assert _auth_enabled is False
