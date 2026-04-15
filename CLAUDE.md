# Kinship Earth MCP — Development Notes

## Session Ritual (TPM / Chief of Staff)
- **Start of session:** Review progress against ROADMAP.md and specs/QUEUE.md. Report: what phase/milestone we're in, what's on track, what's at risk, what's blocked. Keep us accountable against the timeline.
- **During session:** Track deliverables against milestone checklists. Flag scope creep or distractions.
- **End of session:** Summarize what was completed, update ROADMAP.md checkboxes and specs/QUEUE.md status, note blockers, state next priorities. Report spec buffer ("X specs ready, Y nights of runway").

## Autonomous Session Protocol

When starting an autonomous session (no human present):

1. Read `specs/QUEUE.md` — find the first spec with status `ready`
2. Read the spec file — it contains everything: what to build, what to test, what to commit
3. **Execute the spec exactly as written** — create files, modify files, write tests
4. **Run all tests** — both new tests from the spec AND existing tests (validation/offline only)
5. **Commit with the template** from the spec, push to the working branch
6. **Update specs/QUEUE.md** — mark the spec as `done`, add completion date
7. **Update ROADMAP.md** — check off completed items
8. **Check spec buffer** — if 2 or fewer specs remain `ready`, note this in commit message so the next interactive session knows to write more specs

### If a spec is blocked:
- Mark it as `blocked` in QUEUE.md with a note explaining why
- Move to the next `ready` spec
- Do NOT skip queued (unwritten) specs — stop and flag

### Branch strategy:
- Work on branch `claude/mcp-chat-integration-8Tpu4`
- Push after each spec completion
- Do not create PRs autonomously — the human will review and merge

## Architecture
- Monorepo: `shared/` (schema, ranking, adapters), `servers/` (one per data source + orchestrator), `launcher/`
- Framework: FastMCP (Python)
- Schema: `EcologicalObservation` in `shared/src/kinship_shared/schema.py` — Darwin Core-aligned
- All adapters implement `EcologicalAdapter` interface from `shared/src/kinship_shared/adapter.py`
- Orchestrator tools live in `shared/src/kinship_shared/ecology_tools.py`, server in `servers/orchestrator/`

## Key Docs
- `STRATEGY.md` — Vision, architecture, competitive moat, key decisions
- `ROADMAP.md` — 5-phase plan with milestones and checklists
- `specs/QUEUE.md` — Ordered spec queue for autonomous sessions
- `specs/001-*.md` through `specs/007-*.md` — Detailed build specs

## Testing
```bash
# Full test suite (requires network for API tests)
uv run --package kinship-orchestrator pytest servers/ -v

# Offline-only tests (always runnable)
uv run --package kinship-orchestrator pytest servers/orchestrator/tests/ -v -k "not (climate or dolphin or cetac or wind_river or woods_hole or parallel or cross_persona or marine or reachable or coordinates or geographic or bird_survey or bird_data or catalog or nonexistent or empty_area or bogus)"
```

## Current Focus
- Phase 2.1: DONE (prompt templates, ecology://sources resource)
- Phase 2.2: Next (workflow tools) — spec 004
- Phase 2.3: Next (visualization hints) — spec 005
- Phase 3.1-3.2: Next (auth + storage) — specs 001-003
- Phase 4.1: Next (graph scaffold + pipeline) — specs 006-007
- Tracking issues: #5 (prompts, done), #6 (workflow tools), #7 (auth), #8 (graph), #10 (viz hints)
