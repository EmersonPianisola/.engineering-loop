---
name: lessons
id: lessons
version: 2.0.0
type: reference
description: 'Self-improving lessons lifecycle. Failures become reusable guidance. Candidate → Confirmed → Applied. Shared across projects via framework.'
---

# Lessons Lifecycle

Self-improving mechanism that turns verification failures into reusable guidance. Lessons are **shared across all projects** using the framework.

## Sources

Lessons are distilled from:

| Source | What to Extract |
|--------|----------------|
| Surviving mutants (discrimination sensor) | Test design gaps, assertion weaknesses |
| Spec-precision gaps | Ambiguous AC patterns |
| Uncovered ACs | Coverage blind spots |
| SPEC_DEVIATIONs | Implementation vs spec drift patterns |
| Fix iterations | Recurring error patterns |

## Format

Each lesson follows this structure:

```json
{
  "id": "L-001",
  "title": "Short description of the lesson",
  "context": "What was being done when this occurred",
  "error": "What went wrong",
  "correction": "How it was fixed",
  "prevention": "How to avoid this in the future",
  "status": "candidate",
  "occurrences": 1,
  "confirmed_at": null,
  "origin_feature": "feature-slug",
  "origin_project": "project-name",
  "origin_stage": "verify",
  "created_at": "2026-07-26"
}
```

## Lifecycle

```
Candidate → Confirmed → Applied → Shared
   ↓           ↓           ↓         ↓
  1st         2nd         Loaded    Pushed to
 occurrence  occurrence  into loop   framework
```

### Candidate

- Created when a failure is first detected
- `occurrences: 1`
- Stored in `{artifact-root}/lessons.json` (project-local)
- Not yet loaded into future feature context

### Confirmed

- When `occurrences >= config.lessons.confirm_threshold` (default: 2)
- Same pattern detected in 2+ features
- `status: confirmed`
- Automatically loaded at Specify/Design phase for all future features

### Applied

- Confirmed lessons are loaded into sub-agent context at:
  - `init` — skill discovery phase
  - `impl.design` — blueprint creation
  - `impl.code` — implementation
- Only confirmed lessons are loaded — never candidates

### Shared (NEW)

- Confirmed lessons are promoted to the framework for all projects to benefit
- At POST-LOOP Phase 5.5:
  1. Identify new confirmed lessons not yet in shared store
  2. Copy to `{artifact-root}/lessons-pending.json`
  3. Report: "N lessons ready to share with framework"
  4. User commits to framework repo: `git -C .eng add artifacts/lessons-shared.json && git commit`
- Other projects load shared lessons on initialization

## Storage

| File | Location | Purpose | Git-tracked |
|------|----------|---------|-------------|
| `lessons.json` | `{artifact-root}/lessons.json` | Project-local lessons (all statuses) | No |
| `LESSONS.md` | `{artifact-root}/LESSONS.md` | Rendered view (human-readable) | No |
| `lessons-pending.json` | `{artifact-root}/lessons-pending.json` | Lessons ready for framework commit | No |
| `lessons-shared.json` | `{artifact-root}/lessons-shared.json` | Shared lessons (committed to framework) | Yes |

## Distillation (Verifier)

The Verifier distills lessons automatically after each verification:

1. For each surviving mutant:
   - Extract pattern (what kind of mutation survived)
   - Check if similar lesson exists in `lessons.json` (local + shared)
   - If exists: increment `occurrences`, check for confirmation
   - If new: create as candidate in local `lessons.json`

2. For each spec-precision gap:
   - Extract pattern (what kind of ambiguity)
   - Same check/create logic

3. For each SPEC_DEVIATION:
   - Extract pattern (what kind of drift)
   - Same check/create logic

4. Clean PASS records nothing

## Loading

At initialization, the orchestrator loads lessons:

```
1. Load shared lessons: {artifact-root}/lessons-shared.json (framework, git-tracked)
2. Load local lessons: {artifact-root}/lessons.json (project, gitignored)
3. Merge: shared lessons take precedence for same ID
4. Filter: only confirmed lessons enter sub-agent context
5. Render: append to sub-agent context as "## Confirmed Lessons"
```

At `impl.design` and `impl.code`:

```
confirmed_lessons = merge(shared.confirmed, local.confirmed)
IF confirmed_lessons:
    append to sub-agent context:
    "## Confirmed Lessons
    {lessons rendered as bullet points}"
```

## Sharing (POST-LOOP)

At POST-LOOP Phase 5.5:

```
1. Read local lessons: {artifact-root}/lessons.json
2. Read shared lessons: {artifact-root}/lessons-shared.json (if exists)
3. Find local confirmed lessons NOT in shared store
4. Write to {artifact-root}/lessons-pending.json
5. Report to user:
   "N lessons ready to share with framework.
    To commit: git -C .eng add artifacts/lessons-shared.json && git commit -m 'Add N new lessons'"
6. User reviews and commits (manual step)
```

## Rules

- **Never hand-edit** `lessons.json` — only the Verifier and lesson script modify it
- **Never load candidate lessons** — only confirmed lessons enter sub-agent context
- **Always distill from failures** — a clean PASS records nothing
- **Confirm threshold is configurable** — `config.yaml → lessons.confirm_threshold`
- **Lessons are shared across projects** — confirmed lessons benefit all framework users
- **User commits shared lessons** — orchestrator prepares, user reviews and commits
