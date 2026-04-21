# Spec Queue — Kinship Earth MCP

*Pick the next spec. Complete it or explicitly pause it. One at a time.*

## Done
(none yet)

## Ready (in priority order)

| # | Spec | Repo | Est | Status |
|---|------|------|-----|--------|
| 001 | [USGS NWIS test hardening + orchestrator integration](001-usgs-nwis-hardening.md) | mcp | 1-2h | Ready |
| 002 | [ecology_whats_around_me finalization](002-whats-around-me.md) | mcp | 1-2h | Ready |
| 003 | [Schema evolution: Phase 1C fields](003-schema-evolution.md) | mcp | 1h | Ready |
| 004 | [eBird adapter validation](004-ebird-validation.md) | mcp | 1h | Ready (needs API key) |
| 005 | [Orchestrator reliability: timeouts + retry](005-orchestrator-reliability.md) | mcp | 1-2h | Ready |
| 006 | [Community launch prep](006-community-launch.md) | mcp | 2h | Ready |
| 007 | [Test coverage gap audit](007-test-coverage-audit.md) | mcp | 1-2h | Ready |
| 008 | [Adapter response normalization audit](008-normalization-audit.md) | mcp | 1-2h | Ready |
| 009 | [Source registry + ecology_describe_sources refresh](009-source-registry.md) | mcp | 1-2h | Ready |
| 010 | [Phase 2 prep: subscribe() + streaming types](010-phase2-streaming-prep.md) | mcp | 2-3h | Ready (after 003) |

## Blocked

| # | Spec | Blocker |
|---|------|---------|
| 004 | eBird validation | Christine needs to register for eBird API key |

## Notes

- Specs 001-005 are Phase 1C (hardening). Do these first.
- Spec 006 is Phase 1D (community launch). Can overlap with 001-005.
- Specs 007-009 are quality/consistency work. Good for burndowns.
- Spec 010 is Phase 2 prep. Do after 003 (schema evolution).
- Web app specs (RCL Sessions 2-4) live in the kinship-earth-web repo, not here.
