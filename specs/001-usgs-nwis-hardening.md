# 001: USGS NWIS Test Hardening + Orchestrator Integration

**Branch:** `sprint/usgs-nwis-hardening`
**Est:** 1-2 hours
**Dependencies:** None

## Context

The USGS NWIS adapter is functional but undertested. The adapter (`adapter.py`, ~327 lines) and server (`server.py`, ~113 lines) work. Tests exist (`test_watershed_health.py`, ~164 lines) with the four-layer structure but many assertions are shallow or conditional.

Uses the new OGC API (`api.waterdata.usgs.gov`), not the legacy API (decommissioned 2027).

## What Exists

- `servers/usgs-nwis/src/usgs_nwis_mcp/adapter.py` — OGC API, haversine filtering, param codes, schema mapping
- `servers/usgs-nwis/src/usgs_nwis_mcp/server.py` — Two tools: `usgs_stream_conditions()`, `usgs_site_data()`
- `servers/usgs-nwis/tests/test_watershed_health.py` — Four layers, partially stubbed

## Boundaries

**Always:** Run tests before changes. One commit per step. Use NEON tests as gold standard pattern.
**Never:** Change the adapter's public API. Break existing passing tests. Add dependencies.

## Steps

### 1. Baseline test run
```bash
uv run pytest servers/usgs-nwis/tests/ -v
```
Record pass/fail counts.

### 2. Complete Layer 2 (Contract) tests
- [ ] `test_all_observations_have_modality_hydrological` — every result `modality == "hydrological"`
- [ ] `test_provenance_fields_complete` — `source_api == "usgs-nwis"`, license "Public Domain", attribution present
- [ ] `test_quality_tier_always_1` — government instruments = tier 1
- [ ] `test_temporal_resolution_present` — "15min" or "daily"
- [ ] `test_location_has_watershed_id` — USGS sites should populate `watershed_id`

### 3. Complete Layer 3 (Semantic) tests
- [ ] `test_potomac_discharge_realistic` — site 01646500, discharge > 0 ft3/s
- [ ] `test_date_range_filtering` — queries with start/end return only results in range
- [ ] `test_parameter_codes_mapped` — 00060=Discharge, 00010=Temperature have readable names

### 4. Edge case tests
- [ ] `test_ocean_coordinates_return_empty` — (0, 0) → empty, no error
- [ ] `test_invalid_site_id_returns_empty` — fake site → empty, no error
- [ ] `test_radius_clamped_to_max` — radius > 200km doesn't crash
- [ ] `test_sentinel_values_filtered` — -999999 values excluded

### 5. Wire into orchestrator
- Check if USGS NWIS is in orchestrator's adapter registry
- If not: add it, verify `ecology_search()` includes NWIS results near rivers
- Add one orchestrator integration test

### 6. Full suite
```bash
uv run pytest -v
```

## Success Criteria
- All 4 test layers have substantive assertions
- Edge cases covered
- USGS NWIS in orchestrator cross-source results
- Zero regressions
