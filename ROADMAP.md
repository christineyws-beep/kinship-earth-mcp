# ROADMAP.md — Kinship Earth MCP

*Last updated: 2026-04-20*

---

## Phase 1: The Query Layer (Now → June 2026)

Make ecological data queryable by AI agents and curious humans.

### 1A: Foundation (Done)
- [x] NEON adapter + MCP server
- [x] OBIS adapter + MCP server
- [x] ERA5 adapter + MCP server
- [x] Cross-source orchestrator
- [x] Shared schema (EcologicalObservation, Darwin Core-aligned)
- [x] Relevance scoring + ranking layer
- [x] Railway deployment (prod + staging)
- [x] CI + branch protection
- [x] Scientist persona eval tests (16 tests, 4 personas)

### 1B: Expand Sources (Done)
- [x] iNaturalist adapter (9/9 tests passing)
- [x] eBird adapter (wired into orchestrator)
- [x] GBIF adapter (2.8B+ records)
- [x] USGS NWIS adapter (stream gauges, OGC API)
- [x] Xeno-canto adapter (1M+ bird audio recordings)
- [x] SoilGrids adapter (global soil properties)
- [x] All 7 new adapters wired into orchestrator
- [x] Schema snapshot tool (detects upstream API drift)

### 1C: Hardening & Polish (In Progress → May 2026)
- [ ] USGS NWIS test hardening (spec 001)
- [ ] `ecology_whats_around_me` finalization — remove DRAFT (spec 002)
- [ ] Schema evolution: `watershed_id`, `ecosystem_id`, `care_status` (spec 003)
- [ ] eBird API key validation end-to-end (spec 004)
- [ ] Orchestrator timeout/retry improvements (spec 005)

### 1D: Community Launch (May–June 2026)
- [ ] LICENSE file (MIT) at root (spec 006)
- [ ] Version alignment — all packages to 0.2.0 (spec 006)
- [ ] PyPI-ready pyproject.toml metadata (spec 006)
- [ ] CODE_OF_CONDUCT.md (spec 006)
- [ ] `.well-known/ecological-data.json` spec (spec 006)
- [ ] PyPI publication (`uvx kinship-earth <server>`)
- [ ] Send scientist outreach emails (8 drafts ready)
- [ ] Custom domain (kinshipearth.org or similar)
- [ ] TDWG 2026 Oslo abstract submission (conference Sep 21–25)
- [ ] First community data partner

---

## Phase 2: Monitoring Agents (July–December 2026)

AI agents that continuously watch specific ecosystems and generate alerts.

### MVP Watershed Listener
Target: **Russian River, Sonoma County** (biodiversity, tribal presence, community engagement culture)

- [ ] Monitoring agent that runs daily
- [ ] Connect USGS stream gauge (real-time flow, 15-min intervals)
- [ ] Connect Sentinel-2 vegetation indices (5-day repeat)
- [ ] Connect eBird observations (daily community science)
- [ ] Historical baselines (30-year normals for current date)
- [ ] Daily "watershed whisper" — one paragraph, natural language
- [ ] `subscribe()` method on adapter base class (async generator)
- [ ] Public page or newsletter for output

### Streaming Architecture
- [ ] Ingestion endpoint (HTTP webhook / MQTT / adapter poll)
- [ ] Message queue (Redis Pub/Sub → Kafka at scale)
- [ ] `EcologicalSignal` type for streaming data
- [ ] `Anomaly` type — deviation from baseline
- [ ] `EcologicalEvent` type — classified event (drought cascade, phenological shift)

### New Adapters
- [ ] Sentinel-2 / satellite health (Prithvi-EO-2.0 foundation model)
- [ ] BirdNET / acoustic monitoring pipeline
- [ ] NOAA weather forecasts (forward-looking, complements ERA5 historical)

### Persistence
- [ ] PostgreSQL + pgvector for local caching
- [ ] Knowledge graph for ecological reasoning
- [ ] Cross-modal embeddings

### Governance
- [ ] Alert recipient framework
- [ ] Interpretation transparency (every alert traceable to data)
- [ ] Community advisory input on monitoring priorities

---

## Phase 3: Signal Translation (2027)

Interpret raw ecological signals across modalities. The beginning of "listening."

- [ ] `CrossModalCorrelation` type — patterns across signal types
- [ ] `EcologicalNarrative` type — sustained natural language ecosystem state
- [ ] Phenology tracker (current vs historical seasonal patterns)
- [ ] Cross-modal anomaly detection (acoustic + spectral + hydrological = cascade)
- [ ] Plant electrophysiology adapter (Vivent PhytlSigns)
- [ ] VOC pattern recognition (e-nose arrays)
- [ ] eDNA biodiversity pipelines
- [ ] Soundscape ecology metrics (ecosystem-level acoustic health)
- [ ] Ecological signal ontology (formal vocabulary)
- [ ] First peer-reviewed publication on methodology

---

## Phase 4: Ecological Voice (2028)

Ecosystems speak through sustained, data-grounded narratives.

- [ ] Annual "State of the Watershed" reports
- [ ] Long-term narrative memory (agent remembers last year, last decade)
- [ ] Regulatory testimony generation (data-supported impact assessments)
- [ ] Scenario modeling ("if project X proceeds, likely outcomes")
- [ ] Pilot guardian/trustee model with one willing community

---

## Phase 5: Participatory Governance (2029+)

Ecosystems participate in decisions that affect them, through guardians informed by agents.

- [ ] Automated environmental review participation
- [ ] Cumulative impact assessment across permit applications
- [ ] Federated ecosystem network (agents sharing patterns across regions)
- [ ] Legal personhood exploration for monitored ecosystems
- [ ] Democratic accountability framework for ecosystem guardians

*This phase is speculative. The point is to build Phases 1–4 so Phase 5 is possible.*

---

## Key Dates

| Date | Milestone |
|------|-----------|
| 2026-04 | Phase 1C hardening sprints |
| 2026-05 | Community launch prep, PyPI, outreach |
| 2026-06 | TDWG abstract deadline (TBD), first community partner |
| 2026-07 | Phase 2 kickoff: Russian River watershed listener |
| 2026-09-21 | TDWG 2026 Oslo conference |
| 2026-12 | Phase 2 complete: first production monitoring agent |
| ~2026-05-04 | Knowledge graph foundation (per high-level timelines) |
