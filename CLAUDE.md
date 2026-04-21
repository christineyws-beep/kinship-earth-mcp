# CLAUDE.md — Kinship Earth MCP

## Project Overview

Ecological intelligence MCP server — a unified API that makes ecological data queryable by AI agents. One query can combine data from multiple scientific sources into a single coherent response.

Public repo: `christinebuilds/kinship-earth-mcp`

## Stack

- **Language:** Python 3.12+
- **Framework:** FastMCP
- **Package manager:** uv
- **Deploy:** Railway (prod + staging)
- **Tests:** pytest (hitting real APIs)

## Architecture

10 adapters (each in `servers/`):

| Adapter | Data |
|---------|------|
| NEON | 81 US ecological observatory sites |
| OBIS | 168M+ marine species records |
| ERA5 | Global climate data from 1940 |
| iNaturalist | Community species observations |
| eBird | Bird observations worldwide |
| USGS NWIS | US water data (streamflow, groundwater) |
| GBIF | Global biodiversity records |
| Xeno-canto | Bird/wildlife sound recordings |
| SoilGrids | Global soil property maps |
| Orchestrator | Combines adapters into unified queries |

Shared utilities live in `shared/`.

## Key Files

- `STRATEGY.md` — Vision, architecture, differentiators, principles
- `ROADMAP.md` — Phase plan with checkboxes
- `specs/QUEUE.md` — What's done, what's next
- `specs/001-*.md` through `specs/010-*.md` — Detailed build specs

## Commands

```bash
# Install dependencies
uv sync

# Run all tests
uv run pytest servers/ -v

# Run a specific adapter's tests
uv run pytest servers/usgs-nwis/tests/ -v

# Run a specific server locally
uv run --package kinship-orchestrator python -m kinship_orchestrator.server

# Run launcher
uv run --package kinship-earth-launcher python -m kinship_earth_launcher --list
```

## Deploy

Railway hosts both prod and staging environments. Always push to both `main` and `staging` branches when deploying.

## Data Export Formats

CSV, GeoJSON, Markdown, BibTeX

---

## Session Ritual

### On Session Start
1. Read this file + `specs/QUEUE.md` to understand current state
2. Check `git status` and `git log --oneline -5` for recent changes
3. Identify the next spec to execute from QUEUE.md
4. Confirm the plan with Christine before starting (unless autonomous protocol applies)

### On Session End
1. Run tests: `uv run pytest servers/ -v`
2. Update `specs/QUEUE.md` — mark completed specs, note blockers
3. Update `ROADMAP.md` checkboxes if milestones were hit
4. Commit with descriptive message
5. Note any decisions made or blockers found

### During Work
- One spec at a time. Complete it or explicitly pause it.
- Commit after each completed step within a spec.
- Run tests before and after every change.
- If a spec reveals unexpected complexity, stop and flag it.

---

## Decisions Needed

These require Christine's input before proceeding:

1. **eBird API key** — Need to register and get key to validate adapter end-to-end
2. **PyPI publication** — Ready to publish? Or just prep the metadata?
3. **Custom domain** — kinshipearth.org? kinship-earth.dev? Something else?
4. **Anthropic account funding** — Live demo needs funded API key
5. **TDWG 2026 abstract** — Submit? (Deadline TBD, conference Sep 21-25 in Oslo)
6. **First community partner** — Point Blue? Audubon chapter? Other?

---

## Autonomous Protocol

Work that can be done without asking:

### Always Safe (Do It)
- Fix failing tests
- Update documentation to match code
- Pin dependencies to SHA
- Fix linting / type errors
- Add test coverage for existing code
- Update QUEUE.md status
- Schema snapshot checks

### Ask First
- New adapter (even if researched)
- Schema changes (even backwards-compatible)
- New dependencies
- Anything that changes the public API surface
- Push to PyPI
- Send emails or post content
- Spend money (API keys, domains, hosting changes)

### Never
- Expose API keys in code or conversation
- Commit .env files
- Force push
- Delete adapters or tests
- Modify CARE/sovereignty-related code without explicit review
- Scrape, infer, or reverse-engineer Traditional Ecological Knowledge

---

## Safety Rules

- Never expose API keys in code or conversation
- Scan for secrets before every commit
- Pin dependencies to SHA where possible
- No `.env` files committed — use Railway environment variables
- Vet all new packages before adding

## Working With This Repo

Christine is a product manager learning to code. When making changes:
- Explain what you changed and why in plain English
- One step at a time — test between each change
- Update this file or README if architecture changes
- Use comprehension checkpoints: explain what was built so Christine understands, not just approves
