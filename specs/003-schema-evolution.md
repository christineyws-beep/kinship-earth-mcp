# 003: Schema Evolution — Phase 1C Fields

**Branch:** `sprint/schema-evolution`
**Est:** 1 hour
**Dependencies:** None (all changes are backwards-compatible)

## Context

The roadmap and schema evolution spec call for adding fields to prepare for Phase 2 monitoring. All additions are `Optional` with defaults — no existing adapter breaks.

Full analysis: `~/Coding/notes/projects/kinship-earth/specs/schema-evolution-spec.md`

## Changes

### Add to `Location` (in `shared/ecological_schema.py`)
```python
watershed_id: Optional[str] = Field(
    default=None,
    description="Watershed identifier (e.g., HUC-12 code)."
)
ecosystem_id: Optional[str] = Field(
    default=None,
    description="Ecosystem identifier from a recognized classification."
)
```

### Add to `Provenance`
```python
care_status: Optional[Literal["public", "research", "restricted", "sovereign"]] = Field(
    default=None,
    description="CARE Principles data governance status. 'sovereign' = Indigenous data requiring community consent."
)
sensor_id: Optional[str] = Field(
    default=None,
    description="Identifier of the specific sensor or instrument."
)
collection_method: Optional[str] = Field(
    default=None,
    description="Method of data collection. E.g., 'autonomous_recorder', 'visual_survey', 'satellite_remote_sensing'."
)
```

### Add to `EcologicalObservation`
```python
temporal_resolution: Optional[str] = Field(
    default=None,
    description="Reporting frequency of source. E.g., '15min', 'daily', '5-day', 'event-driven'."
)
```

### Extend `SignalModality`
Add to the Literal type:
- `"hydrological"` — water flow, chemistry, eDNA
- `"movement"` — GPS telemetry, migration tracking
- `"spectral"` — hyperspectral, multispectral remote sensing

Keep existing values (`sensor`, `geospatial`, etc.) — no renames.

## Boundaries

**Always:** Run all tests before and after. Every field is Optional with default None.
**Ask first:** Before removing or renaming any existing field or modality value.
**Never:** Make breaking changes to existing schema. Change field types on existing fields.

## Steps

### 1. Baseline test run
```bash
uv run pytest -v
```

### 2. Add Location fields
- Add `watershed_id` and `ecosystem_id` to Location model
- Run tests — should all pass (new fields default to None)

### 3. Add Provenance fields
- Add `care_status`, `sensor_id`, `collection_method`
- Run tests

### 4. Add EcologicalObservation field
- Add `temporal_resolution`
- Run tests

### 5. Extend SignalModality
- Add `hydrological`, `movement`, `spectral` to the Literal union
- Run tests

### 6. Update USGS NWIS adapter to populate new fields
- Set `watershed_id` from USGS HUC codes (if available in API response)
- Set `temporal_resolution` to "15min" or "daily" based on data type
- Set `sensor_id` from monitoring location ID
- Set `care_status` to "public" (government data)
- Set `collection_method` appropriately per parameter

### 7. Update schema snapshot
Run the schema snapshot tool to capture the new baseline.

### 8. Full test suite
```bash
uv run pytest -v
```

## Success Criteria
- All new fields added with correct types and defaults
- All existing tests pass unchanged
- USGS NWIS adapter populates new fields where data available
- Schema snapshot updated
- Zero regressions
