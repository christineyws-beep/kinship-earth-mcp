# 006: Community Launch Prep

**Branch:** `sprint/community-launch`
**Est:** 2 hours
**Dependencies:** None

## Context

The MCP is technically solid (10 adapters, 36+ tests, CI/CD) but missing packaging and community artifacts for public launch. Roadmap targets Phase 1D (May-June 2026). These are no-regret tasks.

### Current State (verified 2026-03-28)
- **pyproject.toml**: `name = "kinship-earth"`, `version = "0.1.0"` — minimal metadata
- **CONTRIBUTING.md**: Exists, excellent
- **CITATION.cff**: Exists, excellent (version 0.2.0)
- **LICENSE**: DOES NOT EXIST (mentioned as MIT in CITATION.cff and README)
- **README.md**: Exists, excellent
- **Version mismatch**: CITATION.cff says 0.2.0, pyproject.toml files say 0.1.0

## Boundaries

**Always:** Run tests before and after. Commit per step. Follow existing conventions.
**Ask first:** Author email for pyproject.toml. Whether to register on PyPI now.
**Never:** Change adapter code or tests. Modify the shared schema. Push to PyPI without approval.

## Steps

### 1. Add LICENSE file
MIT license, `Copyright 2026 Christine Su`

### 2. Align versions to 0.2.0
Bump to match CITATION.cff:
- Root `pyproject.toml`
- `launcher/pyproject.toml`
- All `servers/*/pyproject.toml`
- `shared/pyproject.toml`

### 3. Enrich root pyproject.toml
Add: description, readme, license, requires-python, authors, keywords, classifiers, project.urls

### 4. Add CODE_OF_CONDUCT.md
Contributor Covenant v2.1 — standard for open-source science projects.

### 5. Verify launcher works
```bash
uv run --package kinship-earth-launcher python -m kinship_earth_launcher --list
```
Test that all 10 adapters + orchestrator are launchable.

### 6. Create `.well-known/ecological-data.json` stub
Machine-readable spec listing adapters, coverage, modalities, schema alignment.

### 7. TDWG 2026 abstract (stretch)
If time: draft 250-word abstract for TDWG 2026 Oslo (Sep 21-25).
Theme: MCP as a bridge between ecological databases and AI agents.
Save to `docs/tdwg-2026-abstract.md`.

## Success Criteria
- LICENSE file exists (MIT)
- All versions aligned at 0.2.0
- pyproject.toml has full PyPI-ready metadata
- CODE_OF_CONDUCT.md exists
- Launcher works for all servers
- `.well-known/ecological-data.json` exists
- All existing tests pass
