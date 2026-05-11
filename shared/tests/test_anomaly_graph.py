"""Tests for anomaly-to-graph integration."""

from datetime import datetime, timezone

from kinship_shared.anomaly_graph import anomaly_to_graph_entities
from kinship_shared.schema import EcologicalAnomaly, Location


def _make_anomaly():
    return EcologicalAnomaly(
        id="anomaly:41.50_-70.70:2023-07-15:temperature",
        anomaly_type="temperature",
        location=Location(lat=41.5, lng=-70.7),
        detected_at=datetime(2023, 7, 15, tzinfo=timezone.utc),
        signal_value=28.0,
        baseline_value=20.0,
        deviation_pct=40.0,
        severity="warning",
        description="Temperature 4.0 sigma above normal",
        sources=["era5", "neon"],
        confidence=0.85,
    )


def test_anomaly_to_graph_entities_creates_nodes():
    anomaly = _make_anomaly()
    entities, rels = anomaly_to_graph_entities(anomaly)
    entity_types = {e.entity_type for e in entities}
    assert "finding" in entity_types
    assert "location" in entity_types


def test_anomaly_to_graph_relationships():
    anomaly = _make_anomaly()
    entities, rels = anomaly_to_graph_entities(anomaly)
    rel_types = {r.relationship_type for r in rels}
    assert "FOUND_IN" in rel_types
    assert "SOURCED_FROM" in rel_types


def test_anomaly_graph_source_nodes():
    anomaly = _make_anomaly()
    entities, rels = anomaly_to_graph_entities(anomaly)
    source_entities = [e for e in entities if e.entity_type == "data_source"]
    assert len(source_entities) == 2
    source_names = {e.name for e in source_entities}
    assert "era5" in source_names
    assert "neon" in source_names
