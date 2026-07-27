---
name: bmad-integration
description: 'Integrates the Engineering Loop with BMad planning artifacts. Consumes BMad specs, stories, and epics as work items. Validates BMad-specific frontmatter and structure. Use when the planning framework is BMad and you need to load, validate, or update BMad artifacts.'
---

# BMad Integration Skill

**Role:** Bridge — connects the Engineering Loop with BMad planning outputs.

**Optional:** This skill is only needed when the planning framework is BMad. The Engineering Loop operates independently of any planning framework.

## BMad Spec Validation

When consuming a BMad spec, validate:

| Field | Required | Location |
|-------|----------|----------|
| `status` | Yes | Frontmatter (`done` or `ready-for-dev`) |
| `title` | Yes | Frontmatter or H1 |
| `<intent-contract>` | Yes | XML block in spec body |
| `## Tasks & Acceptance` | Yes | Section with numbered tasks |
| `## Code Map` | Yes | Section with file paths |
| I/O Matrix | If present | Section with edge cases |

### Validation Logic

```
IF status NOT IN (done, ready-for-dev) → HALT: spec not ready
IF intent-contract missing or empty → HALT: spec incomplete
IF Tasks & Acceptance missing or empty → HALT: spec incomplete
IF Code Map missing → HALT: spec incomplete
IF [TBD] or placeholder text found → HALT: spec incomplete
```

## BMad Status Updates

| Engineering Phase | BMad Status |
|------------------|-------------|
| Phase 2b begins | `in-progress` |
| Phase 4b begins | `in-review` |
| Phase 6 complete | `done` |

Update the spec's frontmatter `status` field at each transition.

## BMad Artifact Paths

| Artifact | Path |
|----------|------|
| Specs | `_bmad-output/implementation-artifacts/spec-*.md` |
| Epics | `_bmad-output/implementation-artifacts/epics/` |
| Stories | `_bmad-output/implementation-artifacts/stories/` |
| Sprint Plan | `_bmad-output/implementation-artifacts/sprint-plan.md` |
| Process Logs | `_bmad-output/process-logs/` |

## BMad Review Skills

BMad provides review skills that the Engineering Loop can invoke:

| BMad Skill | Loop Phase | Purpose |
|-----------|-----------|---------|
| `bmad-review-adversarial-general` | Phase 4b (Blind Hunter) | Adversarial code review |
| `bmad-review-edge-case-hunter` | Phase 4b (Edge Case Hunter) | Edge case analysis |

These are system-installed skills available through the normal skill discovery process.

## BMad Skill Improvement Integration

When the Engineering Loop improves skills (Phase 5), also update BMad's deferred work:

```markdown
## {date} — Engineering Loop Run {run_id}
- **Spec:** {spec_file basename}
- **Deferred:** {deferred items}
- **Lessons:** {lessons for future BMad planning}
```

## Workflow

### Step 1: Locate Spec

1. Read `{loop-root}/config.yaml` → `planning_artifacts_root`
2. If user provided explicit path → load that file
3. Otherwise → find first `spec-*.md` with `status: ready-for-dev` or `status: done`

### Step 2: Validate

Run BMad spec validation (table above). If fails, HALT.

### Step 3: Extract Work Item

Transform BMad spec into the universal work item format:

| BMad Field | Work Item Field |
|-----------|-----------------|
| `title` (frontmatter) | `title` |
| `<intent-contract>` | `intent` |
| `## Tasks & Acceptance` | `acceptance_criteria` |
| `## Code Map` | `code_map` |
| I/O Matrix | `edge_cases` |

### Step 4: Pass to Loop

Provide the extracted work item to the Engineering Loop for Phase 1+.

## Anti-Patterns

- **Never modify BMad planning artifacts** — only update `status` and `review_loop_iteration`
- **Never skip BMad validation** — incomplete specs produce incomplete implementations
- **Never assume BMad conventions** — always read the spec structure before parsing
