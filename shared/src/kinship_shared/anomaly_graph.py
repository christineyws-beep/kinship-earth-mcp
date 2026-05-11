"""
Wire anomalies into the knowledge graph as first-class entities.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .graph_schema import GraphEntity, GraphRelationship, make_location_id
from .schema import EcologicalAnomaly


def anomaly_to_graph_entities(anomaly: EcologicalAnomaly) -> tuple[list[GraphEntity], list[GraphRelationship]]:
    """Convert an EcologicalAnomaly into graph entities and relationships."""
    now = datetime.now(timezone.utc)
    anomaly_entity_id = f"anomaly:{anomaly.id}"
    location_id = make_location_id(anomaly.location.lat, anomaly.location.lng)

    entities = [
        GraphEntity(
            id=anomaly_entity_id,
            entity_type="finding",
            name=anomaly.description[:100],
            properties={
                "anomaly_type": anomaly.anomaly_type,
                "severity": anomaly.severity,
                "deviation_pct": anomaly.deviation_pct,
                "signal_value": anomaly.signal_value,
                "baseline_value": anomaly.baseline_value,
                "confidence": anomaly.confidence,
                "detected_at": anomaly.detected_at.isoformat(),
            },
        ),
        GraphEntity(
            id=location_id,
            entity_type="location",
            name=f"{anomaly.location.lat:.2f}, {anomaly.location.lng:.2f}",
            properties={"lat": anomaly.location.lat, "lng": anomaly.location.lng},
        ),
    ]

    relationships = [
        GraphRelationship(
            source_id=anomaly_entity_id,
            target_id=location_id,
            relationship_type="FOUND_IN",
            properties={"anomaly_type": anomaly.anomaly_type},
        ),
    ]

    for source in anomaly.sources:
        source_id = f"source:{source}"
        entities.append(GraphEntity(id=source_id, entity_type="data_source", name=source))
        relationships.append(GraphRelationship(
            source_id=anomaly_entity_id, target_id=source_id,
            relationship_type="SOURCED_FROM",
        ))

    return entities, relationships
