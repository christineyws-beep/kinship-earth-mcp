# Spec 004: Workflow Composition Tools

> Phase 2.2 — Higher-Level Research Workflows
> Priority: P1
> Estimated effort: 1 session
> Dependency: None (can run in parallel with auth specs)
> GitHub Issue: #6

## Objective

Add higher-level tools that chain existing tools into research workflows. These let agents (and users) get comprehensive answers in a single call instead of manually orchestrating multiple tool calls.

## What to Build

### 1. Biodiversity Assessment Tool

Add to orchestrator:

```python
@mcp.tool()
async def ecology_biodiversity_assessment(
    lat: float,
    lon: float,
    radius_km: float = 25,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Comprehensive biodiversity assessment for a location.
    
    Chains species search + climate + soil into a structured assessment.
    Returns species richness, taxonomic diversity, environmental context,
    and data quality metrics — everything needed for a baseline survey.
    """
```

Implementation:
- Call `run_search()` with all sources enabled
- Call `_soil.search()` for soil context
- Compute derived metrics:
  - `species_richness`: count of unique species
  - `taxonomic_diversity`: dict of {kingdom: count, class: count, order: count}
  - `source_coverage`: which sources contributed data
  - `quality_distribution`: count of observations per quality tier
  - `temporal_coverage`: earliest and latest observation dates
- Return structured assessment with all raw data + derived metrics

### 2. Temporal Comparison Tool

```python
@mcp.tool()
async def ecology_temporal_comparison(
    lat: float,
    lon: float,
    radius_km: float = 50,
    period_a_start: str,
    period_a_end: str,
    period_b_start: str,
    period_b_end: str,
    scientificname: str | None = None,
) -> dict:
    """Compare ecological conditions between two time periods.
    
    Answers "what changed here?" by running parallel queries for both
    periods and computing differences in species composition, climate,
    and observation patterns.
    """
```

Implementation:
- Run `run_search()` for both periods in parallel via `asyncio.gather()`
- Compute deltas:
  - `species_gained`: species in period B not in period A
  - `species_lost`: species in period A not in period B  
  - `species_persistent`: in both periods
  - `climate_delta`: temperature/precipitation differences
  - `observation_count_change`: more or fewer observations
- Return both raw data and computed deltas

### 3. Export Tool

```python
@mcp.tool()
async def ecology_export(
    data_source: Literal["last_search", "location", "species"] = "last_search",
    format: Literal["csv", "geojson", "markdown", "bibtex"] = "geojson",
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float | None = None,
    scientificname: str | None = None,
) -> dict:
    """Export ecological data in a standard format.
    
    Runs a search (or uses recent results) and formats the output as
    CSV, GeoJSON, Markdown report, or BibTeX citations.
    """
```

Implementation:
- If `data_source == "location"` or `"species"`, run a fresh search
- Format results according to `format`:
  - `csv`: Return a CSV string with header row
  - `geojson`: Return GeoJSON FeatureCollection
  - `markdown`: Return formatted Markdown report with citations
  - `bibtex`: Return BibTeX entries for all data sources used
- Include provenance and DOIs in all formats

### 4. Citation Tool

```python
@mcp.tool()
async def ecology_cite(
    sources: list[str] | None = None,
) -> dict:
    """Generate citations for ecological data sources.
    
    Returns properly formatted citations for OBIS, NEON, ERA5, and all
    other data sources. Includes DOIs, access dates, and license info.
    If no sources specified, returns citations for all available sources.
    """
```

Implementation:
- Maintain a citation registry (hardcoded dict) with:
  - BibTeX entry
  - APA formatted string
  - DOI
  - License
- Return citations for requested sources (or all)

## Tests to Write

Create `servers/orchestrator/tests/test_workflow_tools.py`:

1. `test_biodiversity_assessment_registered` — tool in mcp
2. `test_biodiversity_assessment_returns_metrics` — verify derived metrics present
3. `test_temporal_comparison_registered` — tool in mcp
4. `test_temporal_comparison_computes_deltas` — verify species gained/lost/persistent
5. `test_export_geojson_format` — verify valid GeoJSON output
6. `test_export_csv_has_headers` — verify CSV has proper header row
7. `test_export_bibtex_has_dois` — verify DOIs present
8. `test_cite_all_sources` — verify all 9 sources have citations
9. `test_cite_specific_source` — verify single source citation

## Verification

```bash
uv run --package kinship-orchestrator pytest servers/orchestrator/tests/test_workflow_tools.py -v

# Server loads with new tool count
uv run --package kinship-orchestrator python -c "from kinship_orchestrator.server import mcp; print(f'Tools: {len(mcp._tool_manager._tools)}')"
# Expected: Tools: N+4 (+ biodiversity_assessment + temporal_comparison + export + cite)
```

## Commit Message Template

```
Add workflow composition tools for research workflows

Implements Phase 2.2 (Milestone 2.2, Issue #6):
- ecology_biodiversity_assessment: species + climate + soil in one call
- ecology_temporal_comparison: "what changed here between X and Y?"
- ecology_export: CSV, GeoJSON, Markdown, BibTeX output
- ecology_cite: formatted citations with DOIs for all sources
- 9 new tests

Spec: specs/004-workflow-tools.md
```

## Files to Create/Modify

| Action | File |
|--------|------|
| Create | `shared/src/kinship_shared/citations.py` (citation registry) |
| Create | `shared/src/kinship_shared/export.py` (format conversion logic) |
| Create | `servers/orchestrator/tests/test_workflow_tools.py` |
| Modify | `shared/src/kinship_shared/__init__.py` (export new modules) |
| Modify | `servers/orchestrator/src/kinship_orchestrator/server.py` (add 4 tools) |
| Modify | `specs/QUEUE.md` (mark this spec done) |
| Modify | `ROADMAP.md` (check off Milestone 2.2 items) |
