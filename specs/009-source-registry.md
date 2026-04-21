# 009: Source Registry + ecology_describe_sources Refresh

**Branch:** `sprint/source-registry`
**Est:** 1-2 hours
**Dependencies:** None

## Context

`ecology_describe_sources` is one of the orchestrator's three main tools. It tells the AI agent what data sources are available and their capabilities. With 10 adapters now (up from the original 3), this tool's output needs to be accurate and comprehensive.

Additionally, a formal source registry would let the orchestrator make smarter decisions about which adapters to query for a given question.

## Goals

1. Verify `ecology_describe_sources` lists all 10 adapters with accurate info
2. Add structured metadata per adapter (coverage area, modalities, record counts, auth requirements)
3. Create a source registry that the orchestrator can use for smart routing

## Steps

### 1. Audit current describe_sources output
Call `ecology_describe_sources()` and capture the output. Check:
- [ ] All 10 adapters listed?
- [ ] Descriptions accurate?
- [ ] Coverage areas correct?
- [ ] Record counts current?

### 2. Create source registry
```python
# shared/source_registry.py
SOURCE_REGISTRY = {
    "neonscience": {
        "name": "NEON",
        "description": "National Ecological Observatory Network — 81 US field sites",
        "coverage": "North America (US)",
        "modalities": ["sensor", "occurrence"],
        "record_estimate": "180+ data products",
        "auth_required": False,
        "quality_tier": 1,
        "temporal_range": "2014-present",
        "spatial_resolution": "site-level",
    },
    # ... all 10 adapters
}
```

### 3. Update ecology_describe_sources
- Pull from registry instead of hard-coded strings
- Return structured data (not just prose)
- Include: name, coverage, modalities, record estimate, auth, quality tier

### 4. Add smart routing hints
Add to registry:
- `best_for: list[str]` — query types this adapter excels at
  - e.g., OBIS: `["marine species", "ocean biodiversity"]`
  - e.g., ERA5: `["climate", "weather", "temperature", "precipitation"]`
  - e.g., USGS NWIS: `["stream flow", "water quality", "watershed"]`

### 5. Write tests
- [ ] `test_describe_sources_lists_all_adapters` — count == 10
- [ ] `test_registry_has_required_fields` — every entry has name, coverage, modalities
- [ ] `test_describe_sources_output_is_structured` — returns dict, not free text

### 6. Full test suite

## Success Criteria
- All 10 adapters in describe_sources output
- Source registry with structured metadata
- Smart routing hints for future orchestrator improvements
- Tests pass
