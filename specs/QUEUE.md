# Spec Queue — Autonomous Nightly Sessions

> This file is the source of truth for what the nightly autonomous session should work on.
> Each session reads this file, picks the next `ready` spec, executes it, and marks it `done`.

## How It Works

1. Session starts, reads this file
2. Finds the first spec with status `ready`
3. Reads that spec file for detailed instructions
4. Executes the spec: build, test, commit, push
5. Updates this file: marks spec as `done`, adds completion notes
6. Opens a PR or pushes to the feature branch
7. Writes a burn-down summary as a commit message

## Queue Status

| # | Spec File | Status | Target Date | Completed | Notes |
|---|-----------|--------|-------------|-----------|-------|
| 1 | `001-conversation-storage.md` | done | 2026-04-16 | 2026-04-15 | Phase 3.2 |
| 2 | `002-auth-proxy.md` | done | 2026-04-17 | 2026-04-15 | Phase 3.1 |
| 3 | `003-auth-integration.md` | done | 2026-04-18 | 2026-04-15 | Phase 3.1 + 3.2 |
| 4 | `004-workflow-tools.md` | done | 2026-04-19 | 2026-04-15 | Phase 2.2 |
| 5 | `005-visualization-hints.md` | done | 2026-04-20 | 2026-04-15 | Phase 2.3 |
| 6 | `006-graph-scaffold.md` | done | 2026-04-21 | 2026-04-15 | Phase 4.1 |
| 7 | `007-graph-pipeline.md` | done | 2026-04-22 | 2026-04-15 | Phase 4.1 |
| 8 | `008-memory-tools.md` | queued | 2026-04-23 | — | Phase 4.2 (needs spec) |
| 9 | `009-memory-ranking.md` | queued | 2026-04-24 | — | Phase 4.3 (needs spec) |
| 10 | `010-integration-test.md` | queued | 2026-04-25 | — | End-to-end (needs spec) |

### Status Key
- `ready` — spec is written, detailed, and executable autonomously
- `queued` — placeholder, spec not yet written (session should skip and flag)
- `in_progress` — currently being worked on
- `done` — completed, committed, pushed
- `blocked` — cannot proceed, see notes

## Inventory

- **Specs ready:** 0
- **Specs queued (need writing):** 3
- **Specs done:** 7
- **Buffer:** 0 nights ahead — ALL SPECS EXECUTED. Write specs 008-010 next session.

> When buffer drops to 2 or fewer, the next interactive session should prioritize writing more specs.
