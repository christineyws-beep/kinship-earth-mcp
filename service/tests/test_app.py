"""
Tests for the Kinship Earth API service.
"""

import pytest
from fastapi.testclient import TestClient

from kinship_service.app import app
from kinship_service.config import Settings


client = TestClient(app)


def test_health_endpoint():
    """GET /health should return 200 with service metadata."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "kinship-earth"
    assert "tools" in data
    assert "prompts" in data


def test_sources_endpoint():
    """GET /api/sources should return available data sources."""
    response = client.get("/api/sources")
    assert response.status_code == 200
    data = response.json()
    assert "source_count" in data
    assert data["source_count"] >= 3


def test_usage_endpoint():
    """GET /api/usage should return usage stats for anonymous user."""
    response = client.get("/api/usage")
    assert response.status_code == 200
    data = response.json()
    assert "user_id" in data
    assert "queries_today" in data
    assert "queries_limit" in data
    assert data["queries_limit"] == 50


def test_cors_headers():
    """Preflight requests should include CORS headers."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200


def test_config_loads_defaults():
    """Settings should load with sensible defaults when no env vars set."""
    s = Settings()
    assert s.free_tier_limit == 50
    assert s.auth_enabled is False
    assert s.has_supabase is False
