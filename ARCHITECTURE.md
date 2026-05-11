# Kinship Earth — Architecture

## System Overview

Kinship Earth is an ecological intelligence platform that federates 9 scientific data APIs into a unified interface for AI agents and web clients.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Consumers                                 │
├──────────────┬──────────────────┬───────────────────────────────┤
│ Claude Chat  │  Web App         │  Any MCP Client               │
│ (claude.ai / │  (kinship-earth  │  (Cursor, Windsurf,           │
│  Desktop)    │  -web, Next.js)  │   custom agents)              │
└──────┬───────┴────────┬─────────┴──────────────┬────────────────┘
       │                │                        │
       │ MCP protocol   │ REST API               │ MCP protocol
       │ (Streamable    │ (JSON over HTTP)       │ (stdio local)
       │  HTTP)         │                        │
       ▼                ▼                        ▼
┌─────────────────────────────────────────────────────────────────┐
│              service/ — FastAPI Application                       │
│                                                                  │
│  /mcp          Streamable HTTP MCP endpoint (remote access)      │
│  /api/search   REST wrapper for ecology_search                   │
│  /api/sources  Data source registry                              │
│  /api/usage    Rate limit status                                 │
│  /health       Service health + graph stats                      │
│  /docs         Swagger UI (interactive API explorer)             │
│                                                                  │
│  Auth: Supabase (when configured) or anonymous                   │
│  Rate limiting: 50 queries/day free tier, unlimited BYOK         │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               │ imports
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│         servers/orchestrator — MCP Server (FastMCP)               │
│                                                                  │
│  17 tools:                                                       │
│    Core:     ecology_search, ecology_get_environmental_context,  │
│              ecology_describe_sources, ecology_whats_around_me    │
│    Memory:   ecology_memory_recall, ecology_memory_store,        │
│              ecology_related_queries, ecology_emerging_patterns   │
│    Workflow: ecology_biodiversity_assessment,                     │
│              ecology_temporal_comparison, ecology_export,         │
│              ecology_cite                                         │
│    User:    ecology_my_history, ecology_my_usage,                │
│              ecology_set_api_key, ecology_feedback               │
│    Graph:   ecology_graph_stats                                  │
│                                                                  │
│  4 prompts: ecological_survey, species_report,                   │
│             habitat_assessment, temporal_analysis                 │
│  1 resource: ecology://sources                                   │
│                                                                  │
│  Knowledge graph: entity extraction → networkx + SQLite          │
│  Conversation storage: SQLite (every tool call persisted)        │
│  Memory-informed ranking: boosts results for active research     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               │ calls adapters
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                  shared/ — Core Libraries                         │
│                                                                  │
│  Adapters (9):                                                   │
│    NEON, OBIS, ERA5, iNaturalist, eBird, GBIF,                  │
│    Xeno-canto, USGS NWIS, SoilGrids                             │
│                                                                  │
│  Schema:     EcologicalObservation (Darwin Core-aligned)         │
│  Ranking:    Federated scoring + memory-informed boosting        │
│  Graph:      graph_schema.py, graph_store.py, graph_extract.py   │
│  Storage:    storage.py, storage_sqlite.py                       │
│  Viz:        Auto-detection (map, timeseries, gallery)           │
│  Export:     CSV, GeoJSON, Markdown, BibTeX                      │
│  Citations:  Auto-generated from source metadata                 │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               │ HTTP requests
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   External Data APIs                              │
│                                                                  │
│  NEON API    │ OBIS API   │ ERA5/CDS    │ iNaturalist API        │
│  eBird API   │ GBIF API   │ Xeno-canto  │ USGS NWIS             │
│  SoilGrids (ISRIC)                                              │
└─────────────────────────────────────────────────────────────────┘
```

## Access Methods

| Method | URL / Command | Auth | Who it's for |
|--------|---------------|------|--------------|
| Remote MCP (Streamable HTTP) | `https://kinship-api-staging-40ec.up.railway.app/mcp` | None (free tier) | Claude Desktop, claude.ai, any MCP client |
| REST API | `https://kinship-api-staging-40ec.up.railway.app/api/search` | None (free tier) | Web apps, scripts, non-MCP clients |
| Swagger UI | `https://kinship-api-staging-40ec.up.railway.app/docs` | None | Demos, testing |
| Local MCP (stdio) | `uvx --from git+https://github.com/christinebuilds/kinship-earth-mcp kinship-orchestrator` | N/A | Power users, offline use |

## Claude Desktop Configuration (Remote — no install needed)

```json
{
  "mcpServers": {
    "kinship-earth": {
      "url": "https://kinship-api-staging-40ec.up.railway.app/mcp"
    }
  }
}
```

## Deployment

- **Railway project**: kinship-earth-web
- **Services**:
  - `motivated-light` — kinship-earth-web (Next.js frontend)
  - `kinship-api` — this service (FastAPI + MCP, staging)
- **Branch**: `claude/mcp-chat-integration-8Tpu4`
- **Env vars**: `KINSHIP_FREE_TIER_LIMIT=50`, `KINSHIP_CORS_ORIGINS=*`

## Data Flow

1. User asks Claude: "What birds are near Golden Gate Park?"
2. Claude connects to Kinship Earth MCP at `/mcp`
3. MCP server calls `ecology_search(lat=37.77, lon=-122.49, radius_km=5)`
4. Orchestrator fans out to eBird + iNaturalist + OBIS adapters in parallel
5. Results ranked, deduplicated, and enriched with visualization hints
6. Knowledge graph extracts entities (species, location) and stores them
7. Response returned with observations, GeoJSON map data, and citations

## Key Design Decisions

- **MCP-first**: The MCP server IS the product. REST and web are thin wrappers.
- **Federation**: No data is stored/cached from sources — always live queries.
- **Knowledge graph is per-user**: Opt-in shared memory (not yet implemented).
- **SQLite for now**: Scales to ~100K entities. Neo4j migration path exists.
- **Monorepo**: All adapters, shared libs, orchestrator, and service in one repo.
