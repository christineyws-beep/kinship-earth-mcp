# Spec 005: Structured Output for Agent UI Generation

> Phase 2.3 — Visualization Hints
> Priority: P1
> Estimated effort: 1 session
> Dependency: None (can run in any order)
> GitHub Issue: #10

## Objective

Add structured visualization hints to all tool responses so AI agents can generate appropriate maps, charts, and tables on the fly — replacing the need for a custom web frontend.

## What to Build

### 1. Visualization Hint Models

Create `shared/src/kinship_shared/viz.py`:

```python
from pydantic import BaseModel
from typing import Literal

class MapData(BaseModel):
    """Pre-structured data for map rendering."""
    geojson: dict                           # GeoJSON FeatureCollection
    bounds: dict                            # {"sw": [lat, lon], "ne": [lat, lon]}
    center: dict                            # {"lat": float, "lon": float}
    zoom_level: int                         # Suggested zoom (1-18)
    layers: list[dict]                      # [{"name": "OBIS", "color": "#1f77b4", "features": [...]}]

class ChartData(BaseModel):
    """Pre-structured data for chart rendering."""
    chart_type: Literal["timeseries", "bar", "scatter", "histogram"]
    title: str
    x_label: str
    y_label: str
    series: list[dict]                      # [{"name": "Temperature", "values": [...], "units": "°C"}]
    x_values: list[str | float]             # Shared x-axis values (dates, categories, etc.)

class VisualizationHint(BaseModel):
    """Hint for how an agent should visualize this data."""
    primary: Literal["map", "timeseries", "bar_chart", "comparison_table", "species_gallery", "audio_player", "text_report"]
    map_data: MapData | None = None
    chart_data: ChartData | None = None
    description: str                        # Human-readable: "Map of 23 species observations across 4 sources"
```

### 2. Hint Generator Functions

Add to `shared/src/kinship_shared/viz.py`:

```python
def make_map_hint(observations: list[dict], neon_sites: list[dict]) -> VisualizationHint:
    """Generate map visualization hint from search results."""
    # Convert observations to GeoJSON features grouped by source
    # Calculate bounds from all coordinates
    # Set zoom level based on extent
    
def make_climate_chart_hint(climate: dict) -> VisualizationHint:
    """Generate timeseries chart hint from ERA5 climate data."""
    # Extract temperature, precipitation series
    # Use dates as x-axis
    
def make_comparison_hint(label1: str, label2: str, data: dict) -> VisualizationHint:
    """Generate comparison table hint from site comparison data."""

def make_species_gallery_hint(observations: list[dict]) -> VisualizationHint:
    """Generate species gallery hint for observations with media URLs."""
```

### 3. Add Hints to All Tool Responses

Modify each tool in `server.py` to include a `visualization` key in the response:

**ecology_search:**
- Primary: `"map"` (if lat/lon provided) or `"text_report"` (species-only search)
- Include `map_data` with observations as GeoJSON + source-colored layers
- If climate included, also add `chart_data` with timeseries

**ecology_get_environmental_context:**
- Primary: `"timeseries"` 
- `chart_data` with temperature, precipitation, soil moisture series

**ecology_whats_around_me:**
- Primary: `"map"`
- `map_data` centered on user location with recent sightings

**ecology_biodiversity_assessment** (from spec 004):
- Primary: `"map"` with species gallery secondary
- Both `map_data` and bar chart of taxonomic diversity

**ecology_temporal_comparison** (from spec 004):
- Primary: `"comparison_table"`
- Species gained/lost as comparison table

### 4. Add Hint to Shared Tool Logic

Modify `shared/src/kinship_shared/ecology_tools.py`:

- Import `make_map_hint`, `make_climate_chart_hint` from viz module
- Add `visualization` key to `run_search()` return dict
- Add `visualization` key to `run_get_environmental_context()` return dict
- Keep backward compatible — `visualization` is always an additional key, never replaces existing data

## What NOT to Build

- No rendering code (agents do that)
- No frontend components
- No image generation
- No changes to the MCP prompt templates (they already work)

## Tests to Write

Create `shared/tests/test_viz.py`:

1. `test_make_map_hint_from_observations` — verify valid GeoJSON, correct bounds
2. `test_make_map_hint_groups_by_source` — layers correspond to data sources
3. `test_make_climate_chart_hint` — verify timeseries structure with correct axes
4. `test_make_comparison_hint` — verify comparison table structure
5. `test_make_species_gallery_hint` — verify media URLs are included
6. `test_empty_observations_returns_text_hint` — graceful fallback
7. `test_search_result_has_visualization_key` — run ecology_search, verify `visualization` in response
8. `test_environmental_context_has_visualization_key` — verify `visualization` in response

## Verification

```bash
uv run --package kinship-orchestrator pytest shared/tests/test_viz.py -v
uv run --package kinship-orchestrator pytest servers/orchestrator/tests/test_prompts.py -v  # Still pass
```

## Commit Message Template

```
Add visualization hints to all tool responses

Implements Phase 2.3 (Milestone 2.3, Issue #10):
- VisualizationHint, MapData, ChartData models
- Hint generators for map, timeseries, comparison, gallery
- All tool responses now include visualization key
- Agents can render maps/charts without guessing format
- 8 new tests

Spec: specs/005-visualization-hints.md
```

## Files to Create/Modify

| Action | File |
|--------|------|
| Create | `shared/src/kinship_shared/viz.py` |
| Create | `shared/tests/test_viz.py` |
| Modify | `shared/src/kinship_shared/__init__.py` (export viz) |
| Modify | `shared/src/kinship_shared/ecology_tools.py` (add hints to responses) |
| Modify | `servers/orchestrator/src/kinship_orchestrator/server.py` (add hints to tools) |
| Modify | `specs/QUEUE.md` (mark this spec done) |
| Modify | `ROADMAP.md` (check off Milestone 2.3 items) |
