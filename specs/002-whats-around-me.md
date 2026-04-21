# 002: ecology_whats_around_me Finalization

**Branch:** `sprint/whats-around-me`
**Est:** 1-2 hours
**Dependencies:** None

## Context

The tool exists in the orchestrator (`servers/orchestrator/src/kinship_orchestrator/server.py`) marked as DRAFT. It queries eBird, iNaturalist, OBIS, NEON, and ERA5 in parallel and returns a citizen-friendly snapshot.

This spec: remove DRAFT, write tests, optionally add USGS NWIS, verify performance.

## What Exists

```python
@mcp.tool()  # DRAFT
async def ecology_whats_around_me(
    lat: float, lon: float, radius_km: float = 25, days_back: int = 7
) -> dict:
    """Discover what's been observed near a location recently."""
```

Returns: recent species sightings, nearby monitoring sites, current climate, observation counts and unique species tally.

## Boundaries

**Always:** Write tests first. Don't change the function signature. Handle missing data gracefully.
**Ask first:** Whether to add USGS NWIS. Whether to change default `radius_km`.
**Never:** Require auth for this tool. Return more than 50 results. Break existing interface.

## Steps

### 1. Write tests first
```python
# Layer 1: Connectivity
test_whats_around_me_returns_results     # SF Bay → non-empty dict
test_whats_around_me_handles_ocean       # (0, 0) → graceful empty

# Layer 2: Contract
test_response_has_required_keys          # species_count, sources, observations
test_observations_are_schema_compliant   # each is valid EcologicalObservation
test_multiple_sources_queried            # 2+ source_api values

# Layer 3: Semantic
test_sf_bay_includes_birds               # Golden Gate Park → bird observations
test_coastal_includes_marine             # Monterey Bay → OBIS marine data
test_results_are_recent                  # all within days_back window

# Layer 4: Scientific Fitness
test_provenance_chain_complete           # every result has citation
test_quality_tiers_reported              # tier metadata on all results
```

### 2. Remove DRAFT status
- Remove DRAFT comment from tool decorator
- Verify tool appears in orchestrator tool listing

### 3. Add USGS NWIS (if confirmed)
- Add to parallel adapter query
- Only include near waterways
- Test with Russian River, Guerneville CA

### 4. Edge case testing
- [ ] Middle of Pacific Ocean → graceful empty
- [ ] Arctic coordinates → handles sparse data
- [ ] Very small radius (0.5km) → works but may be empty
- [ ] Very large radius (200km) → no crash or timeout

### 5. Performance verification
- Time full query across all adapters
- Confirm parallel execution (not sequential)
- Target: < 10s for any location

## Success Criteria
- DRAFT removed, tool is production
- 10+ tests covering all 4 layers
- Graceful empty responses for sparse locations
- Response time < 10s
- All existing orchestrator tests pass
