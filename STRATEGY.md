# STRATEGY.md — Kinship Earth MCP

## What This Is

Ecological intelligence middleware. A unified MCP server that makes ecological data queryable by AI agents. One query can combine data from NEON, OBIS, ERA5, eBird, iNaturalist, GBIF, USGS NWIS, Xeno-canto, and SoilGrids into a single coherent response.

Public repo: `christinebuilds/kinship-earth-mcp`

## Why It Matters

No single ecological API gives you a complete picture. A researcher asking "what were the conditions when dolphins were spotted near Woods Hole?" needs marine occurrence data (OBIS), climate context (ERA5), and monitoring site metadata (NEON) — three separate APIs with different schemas, auth models, and query patterns.

Kinship Earth normalizes all of this into a Darwin Core-aligned schema (`EcologicalObservation`) and exposes it through MCP tools that any AI agent can call. The orchestrator handles cross-source queries so the agent (or human) just asks a question.

## Vision Arc

The long-term vision is documented in [Voices of the Living World](../notes/projects/kinship-earth/concepts/voices-of-the-living-world.md). The short version:

1. **Query Layer** (now) — Make ecological data queryable by AI agents and curious humans
2. **Monitoring Agents** (2026 H2) — AI agents that continuously watch specific ecosystems and generate alerts
3. **Signal Translation** (2027) — Interpret raw ecological signals across modalities (acoustic, chemical, spectral, hydrological)
4. **Ecological Voice** (2028) — Ecosystems speak through sustained, data-grounded narratives
5. **Participatory Governance** (2029+) — Ecosystems participate in decisions through guardians informed by agents

We are in Phase 1. Phase 2 prep is underway.

## Architecture

```
┌─────────────────────────────────────────┐
│  AI Agent (Claude Desktop, CLI, Web)    │
└─────────────────┬───────────────────────┘
                  │ MCP (stdio or SSE)
┌─────────────────▼───────────────────────┐
│  Orchestrator                            │
│  ecology_get_environmental_context       │
│  ecology_search                          │
│  ecology_describe_sources                │
│  ecology_whats_around_me (DRAFT)         │
└──┬──────┬──────┬──────┬──────┬──────┬───┘
   │      │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼      ▼
 NEON   OBIS   ERA5  eBird  iNat   GBIF
                       │      │      │
                       ▼      ▼      ▼
                     USGS  Xeno-  Soil
                     NWIS  canto  Grids
```

### Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Schema | Darwin Core-aligned `EcologicalObservation` | Industry standard for biodiversity data; interop with GBIF, OBIS, iDigBio |
| Transport | MCP (stdio + SSE) | Native to Claude; composable with other MCP servers |
| Monorepo | One repo, many packages | Each adapter is independently installable but shares schema + utilities |
| Package manager | uv | Fast, deterministic, workspace support |
| No database (Phase 1) | Direct API pass-through | Keeps it simple; caching + persistence is Phase 2 (pgvector) |
| Quality tiers | Tier 1 (research-grade) / Tier 2 (community-validated) | Researchers need to know what they can cite |

### Shared Layer

- `shared/ecological_schema.py` — `EcologicalObservation`, `Location`, `Provenance`, `SignalModality`
- `shared/ranking.py` — Relevance scoring across heterogeneous results
- Each adapter normalizes its API's response into `EcologicalObservation`

### Data Sources (10 adapters)

| Adapter | Coverage | Records | Auth | Status |
|---------|----------|---------|------|--------|
| NEON | 81 US sites, 20 ecoclimatic domains | 180+ data products | None | Production |
| OBIS | Global oceans | 168M+ occurrences | None | Production |
| ERA5 | Global, hourly, 1940-present | ~25km resolution | None | Production |
| iNaturalist | Global community observations | 190M+ observations | None | Production |
| eBird | Global bird observations | 1.7B+ records | API key | Production |
| GBIF | Global biodiversity | 2.8B+ occurrences | None | Production |
| USGS NWIS | US water (stream gauges, groundwater) | Real-time + historical | None | Production |
| Xeno-canto | Bird/wildlife audio | 1M+ recordings | API key | Production |
| SoilGrids | Global soil properties | 250m resolution | None | Production |
| Orchestrator | Combines all above | Cross-source queries | None | Production |

## Differentiators

1. **Cross-source intelligence** — No other tool combines NEON + OBIS + ERA5 + eBird + iNat + GBIF + USGS + Xeno-canto + SoilGrids into unified queries
2. **Darwin Core alignment** — Results are interoperable with the broader biodiversity data ecosystem
3. **Full provenance** — Every result includes DOIs, citation strings, license info, and links to original source
4. **MCP-native** — Designed for AI agents, not just human-facing APIs
5. **Open source** — MIT license, open data, open methodology

## Competitive Landscape

- **Individual APIs** (GBIF, eBird, iNat) — Single-source, no cross-source intelligence
- **Google Earth Engine** — Powerful but not AI-agent-accessible, steep learning curve
- **Microsoft Planetary Computer** — Satellite-focused, no MCP interface
- **Map of Life** — Species-focused, no climate or hydrology integration

Kinship Earth's moat is the *combination* of sources under a unified schema with MCP access. No one else is building ecological middleware for AI agents.

## Audiences

1. **Researchers** — Ecologists, conservation biologists, environmental scientists who need cross-source data
2. **AI agent builders** — Developers building ecological reasoning into Claude, GPT, or custom agents
3. **Citizen scientists** — Curious humans who want to know "what's around me?"
4. **Conservation orgs** — Point Blue, Audubon chapters, land trusts needing data for decisions

## Key Risks

| Risk | Mitigation |
|------|-----------|
| API rate limits / downtime | Graceful degradation per-adapter; caching in Phase 2 |
| Schema drift in upstream APIs | Schema snapshot tool detects field changes automatically |
| Adoption chicken-and-egg | Free demo tier on web app; PyPI for frictionless install |
| Sustainability / funding | Open-source core; Researcher tier ($15/mo) for persistent features |
| Data sovereignty (Indigenous knowledge) | CARE Principles in schema from day one; never scrape/infer TEK |

## Principles

1. **Kinship, not dominion.** Relationship infrastructure, not monitoring tools.
2. **The AI doesn't speak for nature. It helps guardians listen.** Interpretation is human-accountable.
3. **Data sovereignty from day one.** CARE Principles built in, not bolted on.
4. **Open source, open data, open methodology.** Proprietary ecosystem agents are suspect.
5. **Separation of observation and advocacy.** The agent observes; guardians decide.
6. **Never scrape, infer, or reverse-engineer TEK.** Indigenous knowledge on Indigenous terms, or not at all.
