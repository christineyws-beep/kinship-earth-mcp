# 010: Phase 2 Prep — subscribe() + Streaming Types

**Branch:** `sprint/phase2-streaming-prep`
**Est:** 2-3 hours
**Dependencies:** Spec 003 (schema evolution) should be done first

## Context

Phase 2 (July-Dec 2026) introduces monitoring agents — AI that continuously watches ecosystems. This requires a streaming data path in addition to the existing query path.

This spec lays the groundwork without building the full streaming infrastructure. It adds the `subscribe()` method to the adapter base class and defines the interpretation layer types (`Anomaly`, `EcologicalEvent`). No adapter implements streaming yet — this is scaffolding.

Full design: `~/Coding/notes/projects/kinship-earth/specs/streaming-architecture.md`
Schema analysis: `~/Coding/notes/projects/kinship-earth/specs/schema-evolution-spec.md`

## What This Spec Does NOT Do

- Does not implement streaming for any adapter
- Does not set up message queues (Redis/Kafka)
- Does not build the monitoring agent
- Does not build the watershed listener

Those are Phase 2 proper. This is just the type system and interface.

## Steps

### 1. Add subscribe() to adapter base class
```python
# shared/adapter_base.py (or wherever the base class lives)
class EcologicalAdapter(ABC):
    # ... existing methods ...

    async def subscribe(
        self,
        params: SearchParams,
        interval_seconds: float = 900,  # 15 min default
    ) -> AsyncGenerator[EcologicalObservation, None]:
        """
        Subscribe to streaming observations. Phase 2+.
        Default raises NotImplementedError.
        """
        raise NotImplementedError(f"{self.id} does not support streaming yet")
```

### 2. Define Anomaly type
```python
# shared/interpretation_types.py (new file)
class Anomaly(BaseModel):
    """A detected deviation from baseline in an ecological signal."""
    id: str
    observation_id: str
    signal_modality: SignalModality
    location: Location
    detected_at: datetime
    metric: str
    expected_range: tuple[float, float]
    observed_value: float
    deviation_sigma: float
    severity: Literal["info", "warning", "alert", "critical"]
    interpretation: Optional[str] = None
```

### 3. Define EcologicalEvent type
```python
class EcologicalEvent(BaseModel):
    """A classified ecological event from one or more anomalies."""
    id: str
    event_type: Literal[
        "drought_cascade", "pest_outbreak", "fire_stress",
        "phenological_shift", "pollution_event", "population_decline",
        "habitat_change", "migration_anomaly",
    ]
    anomaly_ids: list[str]
    observation_ids: list[str]
    location: Location
    time_range: tuple[datetime, datetime]
    confidence: float
    narrative: str
    recommended_actions: Optional[list[str]] = None
    provenance: list[Provenance]
```

### 4. Write tests for new types
- [ ] `test_anomaly_serialization` — create, serialize, deserialize
- [ ] `test_ecological_event_serialization` — same
- [ ] `test_subscribe_raises_not_implemented` — default behavior
- [ ] `test_anomaly_severity_values` — only valid severities accepted
- [ ] `test_event_type_values` — only valid event types accepted

### 5. Update schema snapshot
Capture new types in the baseline.

### 6. Document in STRATEGY.md
Add a note about Phase 2 types being defined but not yet implemented.

## Boundaries

**Always:** Keep new types in a separate file from existing schema. Don't modify existing types.
**Ask first:** Before adding fields not in the schema evolution spec.
**Never:** Implement actual streaming. Change existing adapter behavior. Add infrastructure deps.

## Success Criteria
- `subscribe()` on base class raises NotImplementedError
- `Anomaly` and `EcologicalEvent` types defined and serializable
- All existing tests pass (new types don't affect anything)
- Types match the schema evolution spec
- New file: `shared/interpretation_types.py`
