---
name: decision-log
id: decisions
version: 1.0.0
type: reference
description: 'Continuous decision recording (AD-NNN). Decisions captured during stages, consolidated in doc.decisions.'
---

# Decision Log — Continuous Recording (AD-NNN)

Decisions are recorded **continuously** as they are made during each stage, not deferred to a documentation phase.

## Format

Every decision follows this compact format in `STATE.md`:

```markdown
### AD-NNN
- **Decision**: {What was decided}
- **Reason**: {Why this decision}
- **Trade-off**: {What was sacrificed}
- **Scope**: {What it affects}
- **Date**: {YYYY-MM-DD}
- **Status**: active | superseded | amended
- **Origin**: {stage ID that made this decision}
```

## Recording Protocol

After each stage completes, the orchestrator extracts decisions:

1. Scan stage output for `## Decisions` section or any decision-like statements
2. For each decision:
   - Assign next AD-NNN ID (sequential, project-wide)
   - Fill format above
   - Append to `STATE.md ## Decisions`
3. Update `STATE.md ## Handoff` with decision summary

## When to Record

| Trigger | Example |
|---------|---------|
| Architecture choice | "Use SQLite over Postgres for MVP" |
| API design decision | "REST over GraphQL for public API" |
| Library/framework choice | "Three.js over Babylon.js" |
| Trade-off acceptance | "Defer geodata to post-MVP" |
| Constraint relaxation | "Supersede AD-005 procedural-only rule" |
| Implementation pattern | "TDD per task, not stage" |

## When NOT to Record

| Skip | Reason |
|------|--------|
| Obvious defaults | "Use TypeScript" (already in stack) |
| Temporary workarounds | Will be reverted |
| Style preferences | Indentation, naming conventions |
| Tooling configuration | Linter rules, CI config |

## Consolidation (doc.decisions stage)

The `doc.decisions` stage reads `STATE.md ## Decisions` and produces a formal MADR-formatted decision log. It does NOT discover new decisions — it only consolidates what was already recorded.

## ID Convention

- `AD-001` through `AD-999`
- Sequential, never reused
- Superseded decisions keep their ID, status changes to `superseded`
- Amended decisions keep their ID, status changes to `amended`, amendment noted
