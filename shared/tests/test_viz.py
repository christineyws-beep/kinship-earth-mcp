"""
Tests for visualization hints.
"""

import pytest

from kinship_shared.viz import (
    make_climate_chart_hint,
    make_map_hint,
    make_species_gallery_hint,
    make_visualization_hint,
)


def _sample_observations():
    return [
        {"id": "obis:1", "scientific_name": "Delphinus delphis", "lat": 41.5, "lng": -70.7,
         "observed_at": "2023-06-15", "source": "obis", "quality_tier": 2,
         "relevance": {"score": 0.85}},
        {"id": "inat:2", "scientific_name": "Carcharodon carcharias", "lat": 41.6, "lng": -70.5,
         "observed_at": "2023-07-01", "source": "inat", "quality_tier": 3,
         "relevance": {"score": 0.72}},
    ]


def _sample_neon_sites():
    return [
        {"site_code": "HARV", "site_name": "Harvard Forest", "lat": 42.54, "lng": -72.17},
    ]


def _sample_climate():
    return {
        "daily": {
            "time": ["2023-06-12", "2023-06-13", "2023-06-14"],
            "temperature_2m_mean": [18.5, 20.1, 19.3],
            "precipitation_sum": [0.0, 2.1, 0.5],
        },
        "units": {"temperature_2m_mean": "°C", "precipitation_sum": "mm"},
    }


def test_make_map_hint_from_observations():
    """Map hint should have valid GeoJSON and bounds."""
    hint = make_map_hint(_sample_observations())
    assert hint["primary"] == "map"
    assert hint["map_data"]["geojson"]["type"] == "FeatureCollection"
    assert len(hint["map_data"]["geojson"]["features"]) == 2
    bounds = hint["map_data"]["bounds"]
    assert bounds["sw"][0] <= bounds["ne"][0]  # min_lat <= max_lat


def test_make_map_hint_groups_by_source():
    """Layers should correspond to data sources."""
    hint = make_map_hint(_sample_observations())
    layer_names = {l["name"] for l in hint["map_data"]["layers"]}
    assert "obis" in layer_names
    assert "inat" in layer_names


def test_make_map_hint_includes_neon():
    """NEON sites should appear as a separate layer."""
    hint = make_map_hint(_sample_observations(), _sample_neon_sites())
    layer_names = {l["name"] for l in hint["map_data"]["layers"]}
    assert "neon" in layer_names


def test_make_climate_chart_hint():
    """Climate chart should have timeseries structure with correct axes."""
    hint = make_climate_chart_hint(_sample_climate())
    assert hint["primary"] == "timeseries"
    chart = hint["chart_data"]
    assert chart["chart_type"] == "timeseries"
    assert len(chart["x_values"]) == 3
    assert len(chart["series"]) >= 1
    # Temperature series should be present
    temp_series = [s for s in chart["series"] if "Temperature" in s["name"]]
    assert len(temp_series) >= 1


def test_make_species_gallery_hint():
    """Gallery hint should include observations with media URLs."""
    obs = [
        {"scientific_name": "Parus major", "media_url": "https://example.com/photo.jpg",
         "source": "inat", "observed_at": "2023-06-15"},
    ]
    hint = make_species_gallery_hint(obs)
    assert hint["primary"] == "species_gallery"
    assert len(hint["gallery_data"]) == 1


def test_empty_observations_returns_text_hint():
    """Empty observations should fall back to text_report."""
    hint = make_map_hint([])
    assert hint["primary"] == "text_report"


def test_make_visualization_hint_auto_selects():
    """Auto-select should pick map when geo data is available."""
    hint = make_visualization_hint(
        observations=_sample_observations(),
        neon_sites=_sample_neon_sites(),
        climate=_sample_climate(),
    )
    assert hint["primary"] == "map"
    # Should also include chart data
    assert "chart_data" in hint
