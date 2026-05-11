# Spec 012: Anomaly Detection Pipeline

> Phase 5.2 — Anomaly Detection
> Priority: P0 (core intelligence capability)
> Estimated effort: 1 session
> Dependency: Spec 011 (ecosystem state + baselines) must be done first

## Objective

Build the anomaly detection pipeline that identifies deviations from ecological baselines and exposes them through an `ecology_check_anomalies` tool. Implement detectors for temperature, streamflow, phenological, and composition anomalies. Wire detected anomalies into the knowledge graph as first-class entities.

## What to Build

### 1. Anomaly Detector Framework

Create `shared/src/kinship_shared/anomaly_detect.py`:

```python
"""
Anomaly detection pipeline for ecological signals.

Each detector takes current data and baselines, and emits zero or more
EcologicalAnomaly objects. Detectors are composable — the pipeline runs
all relevant detectors for a location and aggregates results.
"""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from .baselines import BaselineValues, compute_deviation
from .schema import AnomalyType, EcologicalAnomaly, EcologicalObservation, EcosystemState, Location

logger = logging.getLogger(__name__)


class AnomalyDetector(ABC):
    """Base class for ecological anomaly detectors."""

    @property
    @abstractmethod
    def anomaly_type(self) -> AnomalyType:
        """The type of anomaly this detector identifies."""

    @abstractmethod
    def detect(
        self,
        *,
        location: Location,
        observations: list[EcologicalObservation],
        baseline: BaselineValues | None = None,
        state: EcosystemState | None = None,
    ) -> list[EcologicalAnomaly]:
        """Analyze data and return any detected anomalies."""


def _make_anomaly_id(anomaly_type: str, lat: float, lng: float, dt: datetime) -> str:
    date_str = dt.strftime("%Y-%m-%d")
    return f"anomaly:{lat:.2f}_{lng:.2f}:{date_str}:{anomaly_type}"


def _classify_severity(deviation_pct: float) -> str:
    """Classify severity from deviation percentage.

    <50% = info, 50-100% = warning, >100% = critical.
    """
    abs_dev = abs(deviation_pct)
    if abs_dev > 100:
        return "critical"
    elif abs_dev > 50:
        return "warning"
    return "info"


class TemperatureDetector(AnomalyDetector):
    """Detects temperature anomalies by comparing current to baseline.

    Flags when temperature deviates >2 sigma from seasonal normal.
    """

    @property
    def anomaly_type(self) -> AnomalyType:
        return "temperature"

    def detect(
        self,
        *,
        location: Location,
        observations: list[EcologicalObservation],
        baseline: BaselineValues | None = None,
        state: EcosystemState | None = None,
    ) -> list[EcologicalAnomaly]:
        if state is None or state.temp_mean_c is None:
            return []
        if baseline is None or baseline.temp_mean_c is None:
            return []

        std = baseline.temp_std_c or 2.0  # Default std if not computed
        z = compute_deviation(state.temp_mean_c, baseline.temp_mean_c, std)

        if abs(z) < 2.0:
            return []  # Within normal range

        deviation_pct = ((state.temp_mean_c - baseline.temp_mean_c) / max(abs(baseline.temp_mean_c), 0.1)) * 100
        direction = "above" if z > 0 else "below"

        return [EcologicalAnomaly(
            id=_make_anomaly_id("temperature", location.lat, location.lng, state.timestamp),
            anomaly_type="temperature",
            location=location,
            detected_at=state.timestamp,
            signal_value=state.temp_mean_c,
            baseline_value=baseline.temp_mean_c,
            deviation_pct=round(deviation_pct, 1),
            severity=_classify_severity(deviation_pct),
            description=f"Temperature {abs(z):.1f} sigma {direction} normal: {state.temp_mean_c:.1f}°C vs baseline {baseline.temp_mean_c:.1f}°C",
            sources=state.sources_contributing,
            confidence=min(1.0, abs(z) / 4.0),
        )]


class FlowDetector(AnomalyDetector):
    """Detects streamflow anomalies (drought or flood signals)."""

    @property
    def anomaly_type(self) -> AnomalyType:
        return "flow"

    def detect(
        self,
        *,
        location: Location,
        observations: list[EcologicalObservation],
        baseline: BaselineValues | None = None,
        state: EcosystemState | None = None,
    ) -> list[EcologicalAnomaly]:
        if state is None or state.streamflow_cfs is None or state.streamflow_baseline is None:
            return []

        baseline_val = state.streamflow_baseline
        if baseline_val < 1.0:
            return []  # Can't compute meaningful deviation from near-zero flow

        deviation_pct = ((state.streamflow_cfs - baseline_val) / baseline_val) * 100

        # Flag if >50% deviation from baseline
        if abs(deviation_pct) < 50:
            return []

        direction = "above" if deviation_pct > 0 else "below"
        signal = "flood risk" if deviation_pct > 0 else "drought signal"

        return [EcologicalAnomaly(
            id=_make_anomaly_id("flow", location.lat, location.lng, state.timestamp),
            anomaly_type="flow",
            location=location,
            detected_at=state.timestamp,
            signal_value=state.streamflow_cfs,
            baseline_value=baseline_val,
            deviation_pct=round(deviation_pct, 1),
            severity=_classify_severity(deviation_pct),
            description=f"Streamflow {abs(deviation_pct):.0f}% {direction} normal ({signal}): {state.streamflow_cfs:.0f} cfs vs baseline {baseline_val:.0f} cfs",
            sources=["usgs-nwis"],
            confidence=min(1.0, abs(deviation_pct) / 200.0),
        )]


class CompositionDetector(AnomalyDetector):
    """Detects species composition anomalies (unusual richness changes)."""

    @property
    def anomaly_type(self) -> AnomalyType:
        return "composition"

    def detect(
        self,
        *,
        location: Location,
        observations: list[EcologicalObservation],
        baseline: BaselineValues | None = None,
        state: EcosystemState | None = None,
    ) -> list[EcologicalAnomaly]:
        if state is None or state.species_richness is None or state.species_baseline is None:
            return []
        if state.species_baseline < 1:
            return []

        deviation_pct = ((state.species_richness - state.species_baseline) / state.species_baseline) * 100

        # Flag if >40% change in species richness
        if abs(deviation_pct) < 40:
            return []

        direction = "increase" if deviation_pct > 0 else "decrease"

        return [EcologicalAnomaly(
            id=_make_anomaly_id("composition", location.lat, location.lng, state.timestamp),
            anomaly_type="composition",
            location=location,
            detected_at=state.timestamp,
            signal_value=float(state.species_richness),
            baseline_value=float(state.species_baseline),
            deviation_pct=round(deviation_pct, 1),
            severity=_classify_severity(deviation_pct),
            description=f"Species richness {direction}: {state.species_richness} species vs baseline {state.species_baseline} ({abs(deviation_pct):.0f}% change)",
            sources=state.sources_contributing,
            confidence=min(1.0, abs(deviation_pct) / 150.0),
        )]


class PhenologicalDetector(AnomalyDetector):
    """Detects phenological anomalies (timing shifts in seasonal events).

    Compares observation dates of seasonal species against expected
    arrival/departure windows.
    """

    @property
    def anomaly_type(self) -> AnomalyType:
        return "phenological"

    def detect(
        self,
        *,
        location: Location,
        observations: list[EcologicalObservation],
        baseline: BaselineValues | None = None,
        state: EcosystemState | None = None,
    ) -> list[EcologicalAnomaly]:
        if not observations:
            return []

        # Look for migratory species observed unusually early or late
        # Heuristic: if >30% of observations are from a different month
        # than the baseline DOY window, flag it
        now = datetime.now(timezone.utc)
        anomalies = []

        # Group observations by month
        month_counts: dict[int, int] = {}
        species_seen: set[str] = set()
        for obs in observations:
            month_counts[obs.observed_at.month] = month_counts.get(obs.observed_at.month, 0) + 1
            if obs.taxon and obs.taxon.scientific_name:
                species_seen.add(obs.taxon.scientific_name)

        if not month_counts or len(species_seen) < 3:
            return []  # Not enough data for phenological analysis

        # Check if current month has unusually high activity compared to baseline DOY
        current_month = now.month
        total_obs = sum(month_counts.values())
        current_month_pct = month_counts.get(current_month, 0) / total_obs * 100

        # Simple heuristic: if a species is observed outside its expected month range
        # this is a placeholder — real phenological detection requires species-specific calendars
        if baseline and baseline.species_richness_mean:
            if state and state.species_richness:
                early_late_ratio = state.species_richness / max(baseline.species_richness_mean, 1)
                if early_late_ratio > 1.5 or early_late_ratio < 0.5:
                    deviation_pct = (early_late_ratio - 1.0) * 100
                    anomalies.append(EcologicalAnomaly(
                        id=_make_anomaly_id("phenological", location.lat, location.lng, now),
                        anomaly_type="phenological",
                        location=location,
                        detected_at=now,
                        signal_value=float(state.species_richness),
                        baseline_value=float(baseline.species_richness_mean),
                        deviation_pct=round(deviation_pct, 1),
                        severity=_classify_severity(deviation_pct),
                        description=f"Unusual species activity for this time of year: {state.species_richness} species vs expected {baseline.species_richness_mean}",
                        sources=state.sources_contributing if state else [],
                        confidence=0.5,  # Phenological detection has moderate confidence
                    ))

        return anomalies


# ---------------------------------------------------------------------------
# Anomaly pipeline
# ---------------------------------------------------------------------------

# Default detector registry
DEFAULT_DETECTORS: list[AnomalyDetector] = [
    TemperatureDetector(),
    FlowDetector(),
    CompositionDetector(),
    PhenologicalDetector(),
]


def run_anomaly_detection(
    *,
    location: Location,
    observations: list[EcologicalObservation] | None = None,
    baseline: BaselineValues | None = None,
    state: EcosystemState | None = None,
    detectors: list[AnomalyDetector] | None = None,
) -> list[EcologicalAnomaly]:
    """Run all anomaly detectors and return aggregated results.

    This is a synchronous function — detectors are lightweight computation,
    not I/O-bound. Data fetching happens upstream.
    """
    detectors = detectors or DEFAULT_DETECTORS
    all_anomalies: list[EcologicalAnomaly] = []

    for detector in detectors:
        try:
            found = detector.detect(
                location=location,
                observations=observations or [],
                baseline=baseline,
                state=state,
            )
            all_anomalies.extend(found)
        except Exception as e:
            logger.warning("Detector %s failed: %s", detector.anomaly_type, e)

    # Sort by severity (critical first), then confidence
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    all_anomalies.sort(key=lambda a: (severity_order.get(a.severity, 3), -a.confidence))

    return all_anomalies
```

### 2. Anomaly-to-Graph Integration

Create `shared/src/kinship_shared/anomaly_graph.py`:

```python
"""
Wire anomalies into the knowledge graph as first-class entities.

When an anomaly is detected, it becomes a node in the graph connected
to its location, data sources, and any related species. This enables
cross-location and temporal pattern detection.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .graph_schema import (
    GraphEntity,
    GraphRelationship,
    make_location_id,
)
from .schema import EcologicalAnomaly


def anomaly_to_graph_entities(anomaly: EcologicalAnomaly) -> tuple[list[GraphEntity], list[GraphRelationship]]:
    """Convert an EcologicalAnomaly into graph entities and relationships.

    Creates:
    - An anomaly entity node
    - A location entity node (if not already present — upsert handled by graph store)
    - DETECTED_AT relationship: anomaly → location
    - SOURCED_FROM relationships: anomaly → each data source
    """
    now = datetime.now(timezone.utc)
    anomaly_entity_id = f"anomaly:{anomaly.id}"
    location_id = make_location_id(anomaly.location.lat, anomaly.location.lng)

    entities = [
        GraphEntity(
            id=anomaly_entity_id,
            entity_type="finding",  # Anomalies are findings in our ontology
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
            created_at=now,
            updated_at=now,
        ),
        GraphEntity(
            id=location_id,
            entity_type="location",
            name=anomaly.location.site_name or f"{anomaly.location.lat:.2f}, {anomaly.location.lng:.2f}",
            properties={
                "lat": anomaly.location.lat,
                "lng": anomaly.location.lng,
            },
            created_at=now,
            updated_at=now,
        ),
    ]

    relationships = [
        GraphRelationship(
            source_id=anomaly_entity_id,
            target_id=location_id,
            relationship_type="FOUND_IN",
            properties={"anomaly_type": anomaly.anomaly_type},
            first_seen=now,
            last_seen=now,
        ),
    ]

    # Add SOURCED_FROM for each contributing source
    for source in anomaly.sources:
        source_id = f"data_source:{source}"
        entities.append(GraphEntity(
            id=source_id,
            entity_type="data_source",
            name=source,
            properties={},
            created_at=now,
            updated_at=now,
        ))
        relationships.append(GraphRelationship(
            source_id=anomaly_entity_id,
            target_id=source_id,
            relationship_type="SOURCED_FROM",
            properties={},
            first_seen=now,
            last_seen=now,
        ))

    return entities, relationships
```

### 3. MCP Tool: `ecology_check_anomalies`

Add to `servers/orchestrator/src/kinship_orchestrator/server.py`:

```python
@mcp.tool()
async def ecology_check_anomalies(
    lat: float,
    lng: float,
    include_types: list[str] | None = None,
    severity_min: str = "info",
) -> dict:
    """Check for ecological anomalies at a location.

    Runs the anomaly detection pipeline: fetches current ecosystem state,
    computes baselines, and identifies deviations in temperature, streamflow,
    species composition, and phenology.

    Args:
        lat: Latitude
        lng: Longitude
        include_types: Filter to specific anomaly types (temperature, flow, composition, phenological). None = all.
        severity_min: Minimum severity to return: 'info', 'warning', or 'critical'.

    Returns anomalies sorted by severity, with links to baseline data and
    suggested follow-up queries.
    """
```

This tool should:
- Build or retrieve `EcosystemState` using `build_ecosystem_state()` from spec 011
- Compute baselines using `compute_baselines_from_era5()` / `compute_baselines_from_usgs()`
- Run `run_anomaly_detection()` with all detectors
- Filter by `include_types` and `severity_min` if provided
- Wire anomalies into graph via `anomaly_to_graph_entities()`
- Return dict with `anomalies`, `ecosystem_state_summary`, and `visualization_hint: "dashboard"`

### 4. Wire Into Orchestrator

Modify `servers/orchestrator/src/kinship_orchestrator/server.py`:
- Import `run_anomaly_detection`, `anomaly_to_graph_entities`, `BaselineValues`
- Import `compute_baselines_from_era5`, `compute_baselines_from_usgs`
- Add `ecology_check_anomalies` tool
- Update tool count expectation (19 → 20 if built after spec 011, or 17 → 18 if standalone)

## What NOT to Build

- No acoustic anomaly detector (needs Xeno-canto time series — future enhancement)
- No spectral/NDVI detector (needs Copernicus adapter — spec 014+)
- No scheduled anomaly scanning (on-demand only for now)
- No ML-based anomaly detection (all detectors are threshold-based)
- No anomaly notifications/subscriptions (that's spec 013)

## Tests to Write

Create `shared/tests/test_anomaly_detect.py`:

1. `test_temperature_detector_normal` — temp within 2 sigma returns no anomalies
2. `test_temperature_detector_extreme_hot` — temp 3 sigma above returns critical anomaly
3. `test_temperature_detector_extreme_cold` — temp 3 sigma below returns warning/critical
4. `test_flow_detector_normal` — flow within 50% of baseline returns nothing
5. `test_flow_detector_drought` — flow 70% below baseline returns flow anomaly
6. `test_flow_detector_flood` — flow 150% above baseline returns flow anomaly
7. `test_composition_detector_normal` — richness within 40% returns nothing
8. `test_composition_detector_decline` — 60% richness drop returns composition anomaly
9. `test_run_anomaly_detection_aggregates` — pipeline runs all detectors and sorts by severity
10. `test_run_anomaly_detection_handles_detector_failure` — one detector throws, others still run
11. `test_classify_severity_thresholds` — verify info/warning/critical thresholds
12. `test_anomaly_id_format` — verify anomaly IDs follow expected pattern

Create `shared/tests/test_anomaly_graph.py`:

13. `test_anomaly_to_graph_entities_creates_nodes` — verify entity creation
14. `test_anomaly_to_graph_relationships` — verify FOUND_IN and SOURCED_FROM edges
15. `test_anomaly_graph_source_nodes` — each source gets its own data_source entity

Create `servers/orchestrator/tests/test_anomaly_tool.py`:

16. `test_check_anomalies_tool_registered` — verify ecology_check_anomalies is in mcp tools

## Verification

```bash
# Anomaly detection tests (offline, pure computation)
uv run --package kinship-orchestrator pytest shared/tests/test_anomaly_detect.py -v

# Graph integration tests (offline)
uv run --package kinship-orchestrator pytest shared/tests/test_anomaly_graph.py -v

# Tool registration
uv run --package kinship-orchestrator pytest servers/orchestrator/tests/test_anomaly_tool.py -v

# All existing tests still pass
uv run --package kinship-orchestrator pytest servers/orchestrator/tests/ shared/tests/ -v -k "not (climate or dolphin or cetac or wind_river or woods_hole or parallel or cross_persona or marine or reachable or coordinates or geographic or bird_survey or bird_data or catalog or nonexistent or empty_area or bogus)"

# Server loads with correct tool count
uv run --package kinship-orchestrator python -c "from kinship_orchestrator.server import mcp; print(f'Tools: {len(mcp._tool_manager._tools)}')"
# Expected: Tools: 20 (19 from spec 011 + ecology_check_anomalies)
```

## Commit Message Template

```
Add anomaly detection pipeline with ecology_check_anomalies tool

Implements Phase 5.2 anomaly detection:
- AnomalyDetector ABC and detector registry
- TemperatureDetector: flags >2 sigma temperature deviations
- FlowDetector: flags >50% streamflow deviations (drought/flood)
- CompositionDetector: flags >40% species richness changes
- PhenologicalDetector: flags unusual seasonal species activity
- run_anomaly_detection pipeline: runs all detectors, sorts by severity
- anomaly_to_graph_entities: wires anomalies into knowledge graph
- ecology_check_anomalies MCP tool
- 16 new tests

Spec: specs/012-anomaly-detection.md
```

## Files to Create/Modify

| Action | File |
|--------|------|
| Create | `shared/src/kinship_shared/anomaly_detect.py` |
| Create | `shared/src/kinship_shared/anomaly_graph.py` |
| Create | `shared/tests/test_anomaly_detect.py` |
| Create | `shared/tests/test_anomaly_graph.py` |
| Create | `servers/orchestrator/tests/test_anomaly_tool.py` |
| Modify | `shared/src/kinship_shared/__init__.py` (export anomaly classes) |
| Modify | `servers/orchestrator/src/kinship_orchestrator/server.py` (add tool + imports) |
| Modify | `specs/QUEUE.md` (mark this spec done) |
| Modify | `ROADMAP.md` (check off Milestone 5.2 items) |
