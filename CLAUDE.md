# CLAUDE.md — Kinship Earth MCP

## Project Overview

Ecological intelligence MCP server — a unified API that makes ecological data queryable by AI agents. One query can combine data from multiple scientific sources into a single coherent response.

Public repo: `christinebuilds/kinship-earth-mcp`

## Stack

- **Language:** Python 3.12+
- **Framework:** FastMCP
- **Package manager:** uv
- **Deploy:** Railway (prod + staging)

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

## Data Export Formats

CSV, GeoJSON, Markdown, BibTeX

## Commands

```bash
# Install dependencies
uv sync

# Run tests
pytest

# Run a specific server locally
uv run --package kinship-orchestrator python -m kinship_orchestrator.server
```

## Deploy

Railway hosts both prod and staging environments. Always push to both `main` and `staging` branches when deploying.

## Safety Rules

- Never expose API keys in code or conversation
- Scan for secrets before every commit
- Pin dependencies to SHA where possible
- No `.env` files committed — use Railway environment variables

## Working With This Repo

Christine is a product manager learning to code. When making changes:
- Explain what you changed and why in plain English
- One step at a time — test between each change
- Update this file or README if architecture changes
