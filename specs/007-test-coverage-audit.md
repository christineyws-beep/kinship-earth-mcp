# 007: Test Coverage Gap Audit

**Branch:** `sprint/test-coverage`
**Est:** 1-2 hours
**Dependencies:** None

## Context

The MCP has 36+ tests but coverage is uneven. NEON has the gold-standard 4-layer tests. Some newer adapters (GBIF, SoilGrids, Xeno-canto) may have thinner coverage. This spec audits every adapter's test quality and fills gaps.

## The 4-Layer Test Standard

From NEON (`servers/neonscience/tests/test_pnw_bird_climate.py`):

1. **Layer 1 — Connectivity:** Can we reach the API and get data back?
2. **Layer 2 — Contract:** Do results conform to EcologicalObservation schema?
3. **Layer 3 — Semantic:** Are the results correct? (known species in known locations)
4. **Layer 4 — Scientific Fitness:** Is provenance complete? Could a researcher cite this?

## Steps

### 1. Inventory current tests
```bash
uv run pytest --collect-only -q 2>/dev/null | grep "test_" | wc -l
```
List every test file and count tests per adapter.

### 2. Grade each adapter

| Adapter | L1 | L2 | L3 | L4 | Grade | Notes |
|---------|----|----|----|----|-------|-------|
| NEON | ? | ? | ? | ? | | Gold standard |
| OBIS | ? | ? | ? | ? | | |
| ERA5 | ? | ? | ? | ? | | |
| iNaturalist | ? | ? | ? | ? | | |
| eBird | ? | ? | ? | ? | | Blocked without API key? |
| GBIF | ? | ? | ? | ? | | |
| USGS NWIS | ? | ? | ? | ? | | See spec 001 |
| Xeno-canto | ? | ? | ? | ? | | |
| SoilGrids | ? | ? | ? | ? | | |
| Orchestrator | ? | ? | ? | ? | | |

### 3. Fill gaps for adapters with < 3 layers covered
For each adapter missing layers, add tests following the NEON pattern:
- Use real API calls (not mocks)
- Use known-good locations and species
- Assert specific field values, not just "result exists"

### 4. Add orchestrator cross-source tests
- [ ] Test that `ecology_search` returns results from 3+ adapters
- [ ] Test that `ecology_get_environmental_context` includes NEON + ERA5
- [ ] Test response includes quality tier metadata

### 5. Full suite
```bash
uv run pytest -v
```
Target: every adapter has at least L1 + L2 + L3 coverage.

## Success Criteria
- Every adapter has 3+ test layers with substantive assertions
- Orchestrator has cross-source integration tests
- All tests pass
- Coverage inventory documented in this spec (fill in the table)
