# Summary

<!-- One paragraph on what this PR does and why. -->

## Changes

<!-- Bulleted list of the substantive changes. -->

-
-

## Tests

<!-- Required: at least one box checked. If you skip tests, justify why. -->

- [ ] Unit test added or updated for affected MCP server
- [ ] Adapter integration test added or updated
- [ ] N/A — docs/config only (no behavior change)
- [ ] N/A — see justification below

**If tests were skipped, why:**
<!-- e.g. "this is a hotfix for a prod incident; follow-up issue #N tracks the test" -->

## Affected MCP servers

<!-- Which servers are touched? Helps reviewers focus. -->

- [ ] orchestrator
- [ ] neonscience
- [ ] obis
- [ ] era5
- [ ] inaturalist
- [ ] usgs-nwis
- [ ] ebird
- [ ] gbif
- [ ] xeno-canto
- [ ] soilgrids
- [ ] shared (touches all)

## Manual verification

<!-- What did you click through / curl / call to confirm this works? -->

- [ ]

## Risk

- [ ] Low — small, isolated, well-tested change
- [ ] Medium — affects multiple servers or shared module; covered by tests
- [ ] High — breaking API change, auth change, or affects orchestrator routing

## Deploy notes

<!-- KE-mcp is consumed by KE-web as a git dependency. Breaking changes propagate. -->

- [ ] No breaking changes to MCP server interfaces (or KE-web pin updated)
- [ ] CHANGELOG updated if user-visible
- [ ] Version bumped if API surface changed (per package's pyproject.toml)

🤖 Drafted from boraboard PR template via Butler
