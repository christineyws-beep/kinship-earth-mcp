# 008: Adapter Response Normalization Audit

**Branch:** `sprint/normalization-audit`
**Est:** 1-2 hours
**Dependencies:** None

## Context

All 10 adapters should normalize their API responses into `EcologicalObservation` objects with consistent field population. In practice, adapters were built at different times and may have inconsistencies in how they populate provenance, location, modality, and quality fields.

This spec audits every adapter's normalization and fixes inconsistencies.

## What to Check Per Adapter

For each adapter, verify these fields are populated correctly:

### Location
- [ ] `latitude` and `longitude` present and numeric
- [ ] `location_name` human-readable (not null or "Unknown")
- [ ] `elevation` populated when available from source
- [ ] `coordinate_uncertainty_meters` populated when available

### Provenance
- [ ] `source_api` matches adapter ID (e.g., `"neonscience"`, `"obis"`, `"era5"`)
- [ ] `license` is correct for the data source
- [ ] `attribution` is present and accurate
- [ ] `doi` populated when the source provides one
- [ ] `citation` is a usable citation string
- [ ] `url` links back to the original record

### Quality
- [ ] `tier` is correct (1 for research-grade, 2 for community-validated)
- [ ] `relevance_score` populated by ranking layer

### Modality
- [ ] `signal_modality` is appropriate (`occurrence` for species, `sensor` for instruments, etc.)

## Steps

### 1. Write a cross-adapter consistency test
```python
def test_all_adapters_produce_consistent_schema():
    """Query each adapter and verify field population consistency."""
    for adapter in ALL_ADAPTERS:
        results = adapter.search(known_good_params)
        for obs in results:
            assert obs.location.latitude is not None
            assert obs.provenance.source_api == adapter.id
            assert obs.provenance.license is not None
            # ... etc
```

### 2. Run the audit
Query each adapter with a known-good location/species and inspect the actual output.

### 3. Fix inconsistencies
For each adapter that's missing or incorrect:
- Fix the normalization in `adapter.py`
- Add/update the test to catch regressions

### 4. Verify ranking layer consistency
- Ensure `relevance_score` is populated on all results from all adapters
- Verify scores are comparable across adapters (not always 1.0 or 0.0)

### 5. Full test suite
```bash
uv run pytest -v
```

## Success Criteria
- All adapters populate the same core fields consistently
- Provenance is accurate for each data source
- Quality tiers are correct
- Cross-adapter consistency test exists and passes
- Zero regressions
