"""Tests for ecology_check_anomalies tool."""

from kinship_orchestrator.server import mcp


def test_check_anomalies_tool_registered():
    tool_names = list(mcp._tool_manager._tools.keys())
    assert "ecology_check_anomalies" in tool_names


def test_tool_count_with_anomalies():
    tool_count = len(mcp._tool_manager._tools)
    assert tool_count >= 20, f"Expected at least 20 tools, got {tool_count}"
