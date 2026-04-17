"""
Tests for the ecology_feedback tool and storage middleware.
"""

import pytest

from kinship_orchestrator.server import mcp


def test_feedback_tool_registered():
    """ecology_feedback should be registered as an MCP tool."""
    tool_names = list(mcp._tool_manager._tools.keys())
    assert "ecology_feedback" in tool_names


def test_tool_count_includes_feedback():
    """Tool count should include the new ecology_feedback tool."""
    tool_count = len(mcp._tool_manager._tools)
    # 4 original + 1 feedback = 5
    assert tool_count >= 5, f"Expected at least 5 tools, got {tool_count}"
