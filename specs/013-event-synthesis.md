# Spec 013: Event Synthesis

> Phase 5.3 — Event Synthesis
> Priority: P1
> Estimated effort: 1 session
> Dependency: Spec 012 (anomaly detection) must be done first

## Objective

Implement the `EcologicalEvent` classification pipeline that synthesizes multiple anomalies into higher-level ecological events (drought cascades, die-offs, phenological shifts, etc.). Add historical analog matching to connect current events to past patterns. Create an `ecology_events` tool and a subscription mechanism for proactive location alerts.

## What to Build

### 1. Event Classifier

Create `shared/src/kinship_shared/event_classify.py`:

```python
"""
Event synthesis — correlates multiple anomalies into classified events.

A single anomaly is a signal. An event is a story: "low streamflow +
high temperature + species richness decline = drought cascade."

Each EventPattern defines a rule: which anomaly types must co-occur,
how close in space/time, and what event type to emit.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import BaseModel, Field

from .schema import (
    EcologicalAnomaly,
    EcologicalEvent,
    EcologicalEventType,
    Location,
)

logger = logging.getLogger(__name__)


class EventPattern(BaseModel):
    """A rule for synthesizing anomalies into an event.

    When all required anomaly types are present within the spatial and
    temporal windows, the event fires.
    """

    event_type: EcologicalEventType
    required_anomaly_types: list[str] = Field(
        description="Anomaly types that must all be present"
    )
    min_anomalies: int = Field(
        default=2,
        description="Minimum number of anomalies required to trigger"
    )
    time_window_days: int = Field(
        default=30,
        description="Anomalies must be within this many days of each other"
    )
    spatial_radius_km: float = Field(
        default=100.0,
        description="Anomalies must be within this radius to correlate"
    )
    title_template: str = Field(
        description="Template for event title, e.g. 'Drought cascade at {location}'"
    )
    narrative_template: str = Field(
        description="Template for event narrative"
    )
    min_severity: str = Field(
        default="warning",
        description="Minimum severity of contributing anomalies"
    )


# ---------------------------------------------------------------------------
# Built-in event patterns
# ---------------------------------------------------------------------------

DROUGHT_CASCADE = EventPattern(
    event_type="drought_cascade",
    required_anomaly_types=["flow", "temperature"],
    min_anomalies=2,
    time_window_days=30,
    spatial_radius_km=100.0,
    title_template="Drought cascade at {location}",
    narrative_template=(
        "Multiple drought signals detected: streamflow is {flow_dev}% below normal "
        "while temperature is {temp_dev}% above normal. This combination suggests "
        "compound drought stress on aquatic and riparian ecosystems."
    ),
    min_severity="warning",
)

DIE_OFF = EventPattern(
    event_type="die_off",
    required_anomaly_types=["composition"],
    min_anomalies=1,
    time_window_days=14,
    spatial_radius_km=50.0,
    title_template="Potential die-off event at {location}",
    narrative_template=(
        "Species richness has dropped {comp_dev}% from baseline levels. "
        "This rapid decline in biodiversity may indicate a die-off event. "
        "Immediate field verification recommended."
    ),
    min_severity="warning",
)

PHENOLOGICAL_SHIFT = EventPattern(
    event_type="phenological_shift",
    required_anomaly_types=["phenological"],
    min_anomalies=1,
    time_window_days=60,
    spatial_radius_km=200.0,
    title_template="Phenological shift detected at {location}",
    narrative_template=(
        "Species activity patterns are {phen_dev}% different from expected "
        "for this time of year. This may indicate shifting seasonal timing "
        "due to climate change or habitat alteration."
    ),
    min_severity="info",
)

BLOOM = EventPattern(
    event_type="bloom",
    required_anomaly_types=["composition", "temperature"],
    min_anomalies=2,
    time_window_days=14,
    spatial_radius_km=50.0,
    title_template="Possible bloom event at {location}",
    narrative_template=(
        "Species composition increase of {comp_dev}% combined with "
        "temperature anomaly of {temp_dev}% suggests a bloom event "
        "(algal, insect emergence, or similar rapid population increase)."
    ),
    min_severity="info",
)

DEFAULT_PATTERNS: list[EventPattern] = [
    DROUGHT_CASCADE,
    DIE_OFF,
    PHENOLOGICAL_SHIFT,
    BLOOM,
]


# ---------------------------------------------------------------------------
# Spatial helpers
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _anomalies_in_window(
    anomalies: list[EcologicalAnomaly],
    center: Location,
    radius_km: float,
    time_window_days: int,
    reference_time: datetime,
) -> list[EcologicalAnomaly]:
    """Filter anomalies to those within spatial and temporal window."""
    cutoff = reference_time - timedelta(days=time_window_days)
    return [
        a for a in anomalies
        if (
            a.detected_at >= cutoff
            and _haversine_km(center.lat, center.lng, a.location.lat, a.location.lng) <= radius_km
        )
    ]


# ---------------------------------------------------------------------------
# Event synthesis
# ---------------------------------------------------------------------------

def _format_narrative(template: str, anomalies: list[EcologicalAnomaly]) -> str:
    """Fill in narrative template with anomaly deviation values."""
    values = {}
    for a in anomalies:
        prefix = a.anomaly_type[:4]  # e.g. "temp", "flow", "comp", "phen"
        values[f"{prefix}_dev"] = f"{abs(a.deviation_pct):.0f}"
    try:
        return template.format(**values, location="the target area")
    except KeyError:
        # If template has placeholders we can't fill, return as-is with what we have
        result = template
        for k, v in values.items():
            result = result.replace(f"{{{k}}}", v)
        return result.replace("{location}", "the target area")


def synthesize_events(
    anomalies: list[EcologicalAnomaly],
    patterns: list[EventPattern] | None = None,
    location: Location | None = None,
) -> list[EcologicalEvent]:
    """Synthesize anomalies into classified ecological events.

    For each pattern, checks if the required anomaly types are present
    within the spatial/temporal window. If so, creates an EcologicalEvent.

    Args:
        anomalies: All detected anomalies (may span locations and times).
        patterns: Event patterns to check. Defaults to DEFAULT_PATTERNS.
        location: Optional center point for spatial filtering. If None, uses
                  the location of the first anomaly.

    Returns:
        List of synthesized events, sorted by severity.
    """
    if not anomalies:
        return []

    patterns = patterns or DEFAULT_PATTERNS
    center = location or anomalies[0].location
    now = datetime.now(timezone.utc)
    events: list[EcologicalEvent] = []
    used_anomaly_ids: set[str] = set()

    severity_order = {"info": 0, "warning": 1, "critical": 2}

    for pattern in patterns:
        # Filter anomalies to the pattern's window
        windowed = _anomalies_in_window(
            anomalies, center, pattern.spatial_radius_km,
            pattern.time_window_days, now,
        )

        # Filter by minimum severity
        min_sev = severity_order.get(pattern.min_severity, 0)
        windowed = [a for a in windowed if severity_order.get(a.severity, 0) >= min_sev]

        # Check if required anomaly types are present
        present_types = {a.anomaly_type for a in windowed}
        required = set(pattern.required_anomaly_types)
        if not required.issubset(present_types):
            continue

        # Check minimum anomaly count
        matching = [a for a in windowed if a.anomaly_type in required]
        if len(matching) < pattern.min_anomalies:
            continue

        # Avoid double-counting anomalies across patterns
        # (allow it — an anomaly can contribute to multiple events)

        # Determine event severity: max of contributing anomalies
        max_severity = max(
            (severity_order.get(a.severity, 0) for a in matching),
            default=0,
        )
        event_severity_map = {0: "info", 1: "warning", 2: "critical"}
        event_severity = event_severity_map.get(max_severity, "info")

        # Compute event duration
        timestamps = [a.detected_at for a in matching]
        duration_days = max(1, (max(timestamps) - min(timestamps)).days) if len(timestamps) > 1 else 1

        # Build narrative
        narrative = _format_narrative(pattern.narrative_template, matching)

        # Collect all sources
        all_sources = list(set(s for a in matching for s in a.sources))

        # Compute confidence as mean of contributing anomalies
        confidence = sum(a.confidence for a in matching) / len(matching)

        event_id = f"event:{pattern.event_type}:{center.lat:.2f}_{center.lng:.2f}:{now.strftime('%Y-%m-%d')}"

        location_name = center.site_name or f"{center.lat:.2f}, {center.lng:.2f}"
        title = pattern.title_template.replace("{location}", location_name)

        events.append(EcologicalEvent(
            id=event_id,
            event_type=pattern.event_type,
            location=center,
            detected_at=now,
            duration_days=duration_days,
            severity=event_severity,
            title=title,
            narrative=narrative,
            anomalies=[a.id for a in matching],
            sources=all_sources,
            confidence=round(confidence, 2),
        ))

    # Sort by severity (most severe first)
    sev_rank = {"emergency": 0, "critical": 1, "warning": 2, "info": 3}
    events.sort(key=lambda e: (sev_rank.get(e.severity, 4), -e.confidence))

    return events
```

### 2. Historical Analog Matcher

Create `shared/src/kinship_shared/analog_match.py`:

```python
"""
Historical analog matching — connects current events to past patterns.

Given a current EcologicalEvent, searches stored event history and the
knowledge graph for similar past events based on event type, location,
severity, and contributing anomaly patterns.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from .schema import EcologicalEvent, Location

logger = logging.getLogger(__name__)


class HistoricalAnalog(BaseModel):
    """A past event that resembles the current one."""

    event_id: str
    event_type: str
    title: str
    detected_at: datetime
    location_name: str
    similarity_score: float = Field(ge=0, le=1, description="How similar to the query event (0-1)")
    explanation: str = Field(description="Why this is considered analogous")


# ---------------------------------------------------------------------------
# Built-in historical knowledge base
# ---------------------------------------------------------------------------
# These are well-documented ecological events that serve as reference analogs.
# They are matched by event type, geography, and season.

KNOWN_ANALOGS: list[dict] = [
    {
        "event_type": "drought_cascade",
        "title": "2021 Klamath Basin drought cascade",
        "year": 2021,
        "lat": 42.0,
        "lng": -121.8,
        "region": "Klamath Basin, OR/CA",
        "description": (
            "Record low water levels in the Klamath Basin led to massive salmon die-offs, "
            "irrigation shutoffs, and cascading ecosystem collapse. Stream temperatures "
            "exceeded 25°C and flows dropped to 10% of normal."
        ),
    },
    {
        "event_type": "drought_cascade",
        "title": "2020 Colorado River low-flow crisis",
        "year": 2020,
        "lat": 36.0,
        "lng": -111.8,
        "region": "Colorado River, AZ/UT",
        "description": (
            "Lake Powell dropped to historically low levels. Riparian habitat loss, "
            "endangered fish species stress, and multi-state water conflict."
        ),
    },
    {
        "event_type": "die_off",
        "title": "2023 Pacific marine heatwave die-off",
        "year": 2023,
        "lat": 37.0,
        "lng": -122.5,
        "region": "Pacific Coast, CA",
        "description": (
            "Elevated sea surface temperatures triggered mass mortality in intertidal "
            "species including sea stars, mussels, and kelp. SST anomaly +3.5°C."
        ),
    },
    {
        "event_type": "phenological_shift",
        "title": "2019 Northeast spring advancement",
        "year": 2019,
        "lat": 42.5,
        "lng": -72.0,
        "region": "Northeast US",
        "description": (
            "Spring leaf-out and bloom dates advanced 2-3 weeks earlier than historical "
            "average. Migratory bird arrival fell out of sync with peak caterpillar emergence."
        ),
    },
    {
        "event_type": "bloom",
        "title": "2024 Lake Erie harmful algal bloom",
        "year": 2024,
        "lat": 41.6,
        "lng": -83.0,
        "region": "Western Lake Erie, OH",
        "description": (
            "Cyanobacteria bloom covered 800 square miles. Triggered by nutrient loading + "
            "warm temperatures + low flow. Drinking water advisories for 500,000+ residents."
        ),
    },
    {
        "event_type": "migration",
        "title": "2022 Arctic tern route shift",
        "year": 2022,
        "lat": 64.0,
        "lng": -20.0,
        "region": "North Atlantic",
        "description": (
            "Arctic terns shifted their Atlantic migratory route 200km eastward, "
            "correlating with changes in prey fish distribution linked to ocean warming."
        ),
    },
]


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_historical_analogs(
    event: EcologicalEvent,
    max_results: int = 3,
    max_distance_km: float = 2000.0,
) -> list[HistoricalAnalog]:
    """Find historical events analogous to the given event.

    Matching criteria (weighted):
    - Same event type (required)
    - Geographic proximity (closer = higher score)
    - Similar season (same month = higher score)

    Args:
        event: The current event to find analogs for.
        max_results: Maximum number of analogs to return.
        max_distance_km: Maximum distance for analog consideration.

    Returns:
        List of HistoricalAnalog objects, sorted by similarity score.
    """
    candidates: list[HistoricalAnalog] = []

    for analog_data in KNOWN_ANALOGS:
        # Must match event type
        if analog_data["event_type"] != event.event_type:
            continue

        # Geographic proximity score (0-1)
        dist = _haversine_km(
            event.location.lat, event.location.lng,
            analog_data["lat"], analog_data["lng"],
        )
        if dist > max_distance_km:
            continue
        geo_score = max(0.0, 1.0 - dist / max_distance_km)

        # Seasonal similarity (0-1)
        event_month = event.detected_at.month
        # Approximate: analogs don't have exact dates, use mid-year as proxy
        season_diff = 0  # Default: no seasonal penalty for known events
        season_score = 1.0 - (season_diff / 6.0)

        # Composite similarity
        similarity = 0.5 * geo_score + 0.3 * season_score + 0.2 * 1.0  # Type match = 1.0

        explanation = (
            f"Similar {analog_data['event_type'].replace('_', ' ')} event in "
            f"{analog_data['region']} ({analog_data['year']}). "
            f"{analog_data['description'][:150]}"
        )

        candidates.append(HistoricalAnalog(
            event_id=f"historical:{analog_data['event_type']}:{analog_data['year']}",
            event_type=analog_data["event_type"],
            title=analog_data["title"],
            detected_at=datetime(analog_data["year"], 6, 1, tzinfo=timezone.utc),
            location_name=analog_data["region"],
            similarity_score=round(similarity, 2),
            explanation=explanation,
        ))

    # Sort by similarity
    candidates.sort(key=lambda a: -a.similarity_score)
    return candidates[:max_results]


def attach_analog_to_event(event: EcologicalEvent, analogs: list[HistoricalAnalog]) -> EcologicalEvent:
    """Attach the best historical analog to an event.

    Modifies the event's historical_analog field with the top match.
    Returns the same event (mutated) for chaining convenience.
    """
    if analogs:
        best = analogs[0]
        event.historical_analog = f"{best.title} (similarity: {best.similarity_score:.0%})"
    return event
```

### 3. MCP Tool: `ecology_events`

Add to `servers/orchestrator/src/kinship_orchestrator/server.py`:

```python
@mcp.tool()
async def ecology_events(
    lat: float,
    lng: float,
    include_analogs: bool = True,
    severity_min: str = "info",
) -> dict:
    """Synthesize ecological events from detected anomalies at a location.

    Runs the full pipeline: ecosystem state → anomaly detection → event
    synthesis → historical analog matching. Returns classified events like
    'drought cascade', 'die-off', 'phenological shift' with data-grounded
    narratives and historical context.

    This is the highest-level ecological intelligence tool — it interprets
    raw signals into ecological stories.

    Args:
        lat: Latitude
        lng: Longitude
        include_analogs: Whether to search for historical analogs (default True)
        severity_min: Minimum event severity to return
    """
```

This tool should:
- Call `ecology_check_anomalies` logic internally to get anomalies
- Run `synthesize_events()` on the anomalies
- If `include_analogs`, run `find_historical_analogs()` and `attach_analog_to_event()`
- Return dict with `events`, `anomaly_count`, `historical_analogs`, and `visualization_hint: "timeline"`

### 4. MCP Tool: `ecology_subscribe`

Add to the orchestrator:

```python
@mcp.tool()
async def ecology_subscribe(
    action: Literal["subscribe", "unsubscribe", "list"],
    lat: float | None = None,
    lng: float | None = None,
    site_name: str | None = None,
    severity_min: str = "warning",
) -> dict:
    """Subscribe to ecological alerts for a location.

    - subscribe: Register for alerts when anomalies/events are detected
    - unsubscribe: Stop receiving alerts for a location
    - list: Show all active subscriptions

    Subscriptions are stored in the monitoring registry. When the
    ecology_check_anomalies or ecology_events tools detect signals above
    the severity threshold, subscribed locations are flagged.
    """
```

This tool adds a `subscriptions` table to the monitoring registry:
- `site_id`, `user_id`, `severity_min`, `created_at`, `last_notified`
- On subscribe: creates monitoring site (if not exists) + subscription
- On unsubscribe: removes subscription (keeps monitoring site)
- On list: returns all subscriptions with their latest event status

### 5. Subscription Storage

Add to `shared/src/kinship_shared/monitoring.py` (created in spec 011):

```python
class Subscription(BaseModel):
    site_id: str
    user_id: str = Field(default="anonymous")
    severity_min: str = Field(default="warning")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_notified: datetime | None = None
```

Add methods to `MonitoringRegistry`:
- `async def add_subscription(self, sub: Subscription) -> None`
- `async def remove_subscription(self, site_id: str, user_id: str) -> bool`
- `async def list_subscriptions(self, user_id: str = "anonymous") -> list[Subscription]`
- `async def get_pending_alerts(self, user_id: str) -> list[dict]`

Add a `subscriptions` table to the `_CREATE_TABLES` SQL:
```sql
CREATE TABLE IF NOT EXISTS subscriptions (
    site_id TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT 'anonymous',
    severity_min TEXT NOT NULL DEFAULT 'warning',
    created_at TEXT NOT NULL,
    last_notified TEXT,
    PRIMARY KEY (site_id, user_id)
);
```

### 6. Wire Into Orchestrator

Modify `servers/orchestrator/src/kinship_orchestrator/server.py`:
- Import `synthesize_events`, `find_historical_analogs`, `attach_analog_to_event`
- Import `Subscription` from monitoring
- Add `ecology_events` and `ecology_subscribe` tools
- Update tool count (20 → 22)

## What NOT to Build

- No real-time push notifications (no WebSocket/SSE yet)
- No ML event classification (rule-based patterns only)
- No cross-location event correlation ("same drought across 3 watersheds")
- No event lifecycle management (open/resolved/closed)

## Tests to Write

Create `shared/tests/test_event_classify.py`:

1. `test_drought_cascade_detected` — flow + temp anomalies → drought_cascade event
2. `test_die_off_detected` — severe composition anomaly → die_off event
3. `test_phenological_shift_detected` — phenological anomaly → phenological_shift event
4. `test_bloom_detected` — composition increase + temp → bloom event
5. `test_no_event_when_insufficient_anomalies` — single temp anomaly does not trigger drought
6. `test_events_sorted_by_severity` — critical events sort before warnings
7. `test_narrative_populated` — event narrative contains deviation data
8. `test_spatial_filtering` — anomalies outside radius are excluded
9. `test_temporal_filtering` — old anomalies are excluded

Create `shared/tests/test_analog_match.py`:

10. `test_find_analog_drought` — drought event finds Klamath analog
11. `test_find_analog_geographic_proximity` — closer analogs score higher
12. `test_find_analog_no_match` — migration event with no nearby analog returns empty
13. `test_attach_analog_to_event` — verify historical_analog field is set
14. `test_max_results_respected` — requesting 1 result returns at most 1

Create `servers/orchestrator/tests/test_event_tools.py`:

15. `test_ecology_events_tool_registered` — verify ecology_events is in mcp tools
16. `test_ecology_subscribe_tool_registered` — verify ecology_subscribe is in mcp tools

## Verification

```bash
# Event synthesis tests (offline, pure computation)
uv run --package kinship-orchestrator pytest shared/tests/test_event_classify.py -v

# Analog matching tests (offline)
uv run --package kinship-orchestrator pytest shared/tests/test_analog_match.py -v

# Tool registration
uv run --package kinship-orchestrator pytest servers/orchestrator/tests/test_event_tools.py -v

# All existing tests still pass
uv run --package kinship-orchestrator pytest servers/orchestrator/tests/ shared/tests/ -v -k "not (climate or dolphin or cetac or wind_river or woods_hole or parallel or cross_persona or marine or reachable or coordinates or geographic or bird_survey or bird_data or catalog or nonexistent or empty_area or bogus)"

# Server loads with correct tool count
uv run --package kinship-orchestrator python -c "from kinship_orchestrator.server import mcp; print(f'Tools: {len(mcp._tool_manager._tools)}')"
# Expected: Tools: 22 (20 from spec 012 + ecology_events + ecology_subscribe)
```

## Commit Message Template

```
Add event synthesis pipeline with historical analog matching

Implements Phase 5.3 event synthesis:
- EventPattern rule system for multi-anomaly correlation
- Built-in patterns: drought_cascade, die_off, phenological_shift, bloom
- synthesize_events pipeline: anomalies → classified events with narratives
- Historical analog matcher with 6 reference events (Klamath, Colorado, etc.)
- ecology_events tool: full pipeline from state → anomaly → event
- ecology_subscribe tool: location alert subscriptions
- Subscription storage in monitoring registry
- 16 new tests

Spec: specs/013-event-synthesis.md
```

## Files to Create/Modify

| Action | File |
|--------|------|
| Create | `shared/src/kinship_shared/event_classify.py` |
| Create | `shared/src/kinship_shared/analog_match.py` |
| Create | `shared/tests/test_event_classify.py` |
| Create | `shared/tests/test_analog_match.py` |
| Create | `servers/orchestrator/tests/test_event_tools.py` |
| Modify | `shared/src/kinship_shared/__init__.py` (export event + analog classes) |
| Modify | `shared/src/kinship_shared/monitoring.py` (add Subscription + subscription methods) |
| Modify | `servers/orchestrator/src/kinship_orchestrator/server.py` (add tools) |
| Modify | `specs/QUEUE.md` (mark this spec done) |
| Modify | `ROADMAP.md` (check off Milestone 5.3 items) |
