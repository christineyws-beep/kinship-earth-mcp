# 004: eBird Adapter End-to-End Validation

**Branch:** `sprint/ebird-validation`
**Est:** 1 hour
**Dependencies:** eBird API key (Christine needs to register at ebird.org)
**Status:** Blocked until API key is available

## Context

The eBird adapter was scaffolded and wired into the orchestrator, but hasn't been validated end-to-end with a real API key. eBird has 1.7B+ bird observations — it's the highest-volume community science dataset we connect to.

## What Exists

- `servers/ebird/` — adapter + server + tests
- Wired into orchestrator
- Tests exist but may be skipping/mocking due to missing API key

## Boundaries

**Always:** Test with real API, not mocks. Record actual response shapes.
**Ask first:** If the adapter needs structural changes based on real API responses.
**Never:** Commit the API key. Hard-code credentials.

## Steps

### 1. Get API key configured
- Christine registers at ebird.org/api/keygen (free)
- Add to Railway env vars: `EBIRD_API_KEY`
- Add to local `.env` (gitignored) for testing

### 2. Baseline test run
```bash
EBIRD_API_KEY=xxx uv run pytest servers/ebird/tests/ -v
```

### 3. Validate response mapping
- [ ] Query "recent observations near SF" — verify results map to EcologicalObservation
- [ ] Check species names are scientific + common
- [ ] Check location coordinates are present and valid
- [ ] Check timestamps parse correctly
- [ ] Check provenance has correct source_api, license, attribution

### 4. Test edge cases
- [ ] Location with no birds (mid-ocean) → empty, no error
- [ ] Very common species (American Robin) → results within days_back
- [ ] Rate limiting behavior — what happens at limit?

### 5. Orchestrator integration
- [ ] `ecology_search("birds near Golden Gate Park")` → includes eBird results
- [ ] `ecology_whats_around_me(37.77, -122.47)` → eBird data present
- [ ] Cross-source: eBird bird + ERA5 climate for same location/date

### 6. Update schema snapshot
Capture eBird response fields in the snapshot baseline.

## Success Criteria
- eBird adapter returns real data with valid API key
- All results map correctly to EcologicalObservation
- Orchestrator includes eBird in cross-source queries
- No API key in code or tests
- Schema snapshot updated
