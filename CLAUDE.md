# Kinship Earth MCP — Development Notes

## Session Ritual (TPM / Chief of Staff)
- **Start of session:** Review progress against ROADMAP.md. Report: what phase/milestone we're in, what's on track, what's at risk, what's blocked. Keep us accountable against the timeline.
- **During session:** Track deliverables against milestone checklists. Flag scope creep or distractions.
- **End of session:** Summarize what was completed, update ROADMAP.md checkboxes, note blockers, state next priorities.

## Architecture
- Monorepo: `shared/` (schema, ranking, adapters), `servers/` (one per data source + orchestrator), `launcher/`
- Framework: FastMCP (Python)
- Schema: `EcologicalObservation` in `shared/src/kinship_shared/schema.py` — Darwin Core-aligned
- All adapters implement `EcologicalAdapter` interface from `shared/src/kinship_shared/adapter.py`
- Orchestrator tools live in `shared/src/kinship_shared/ecology_tools.py`, server in `servers/orchestrator/`

## Key Docs
- `STRATEGY.md` — Vision, architecture, competitive moat, key decisions
- `ROADMAP.md` — 5-phase plan with milestones and checklists

## Testing
```bash
uv run --package kinship-orchestrator pytest servers/ -v
```

## Current Focus
- Phase 2: MCP Maturity (prompt templates, workflow tools, structured output)
- Tracking issues: #5 (prompts), #6 (workflow tools), #10 (structured output)
