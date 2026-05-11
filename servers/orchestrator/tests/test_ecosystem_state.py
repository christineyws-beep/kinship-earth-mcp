"""Tests for ecosystem state tools."""

from kinship_orchestrator.server import mcp


def test_ecosystem_state_tool_registered():
    tool_names = list(mcp._tool_manager._tools.keys())
    assert "ecology_ecosystem_state" in tool_names


def test_monitor_site_tool_registered():
    tool_names = list(mcp._tool_manager._tools.keys())
    assert "ecology_monitor_site" in tool_names


def test_tool_count():
    """Should have 19 tools total now."""
    tool_count = len(mcp._tool_manager._tools)
    assert tool_count >= 19, f"Expected at least 19 tools, got {tool_count}"
