---
name: lessons
id: lessons
version: 1.0.0
type: reference
description: 'Self-improving lessons lifecycle. Failures become reusable guidance. Candidate → Confirmed → Applied.'
---

# Lessons Lifecycle

Self-improving mechanism that turns verification failures into reusable project-local guidance.

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
  "origin_stage": "verify",
  "created_at": "2026-07-26"
}
```

## Lifecycle

```
Candidate → Confirmed → Applied
   ↓           ↓           ↓
 1st         2nd         Loaded at Specify/Design
 occurrence  occurrence  for all future features
```

### Candidate

- Created when a failure is first detected
- `occurrences: 1`
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
- Loaded via `python3 scripts/lessons.py list --status confirmed`
- Only confirmed lessons are loaded — never candidates

## Storage

| File | Purpose |
|------|---------|
| `artifacts/lessons.json` | Canonical state (machine-owned) |
| `artifacts/LESSONS.md` | Rendered view (human-readable, auto-generated) |

## Distillation (Verifier)

The Verifier distills lessons automatically after each verification:

1. For each surviving mutant:
   - Extract pattern (what kind of mutation survived)
   - Check if similar lesson exists in `lessons.json`
   - If exists: increment `occurrences`, check for confirmation
   - If new: create as candidate

2. For each spec-precision gap:
   - Extract pattern (what kind of ambiguity)
   - Same check/create logic

3. For each SPEC_DEVIATION:
   - Extract pattern (what kind of drift)
   - Same check/create logic

4. Clean PASS records nothing

## Loading

At the start of `impl.design` and `impl.code`:

```
confirmed_lessons = load(lessons.json, status: "confirmed")
IF confirmed_lessons:
    append to sub-agent context:
    "## Confirmed Lessons
    {lessons rendered as bullet points}"
```

## Rules

- **Never hand-edit** `lessons.json` — only the Verifier and lesson script modify it
- **Never load candidate lessons** — only confirmed lessons enter sub-agent context
- **Always distill from failures** — a clean PASS records nothing
- **Confirm threshold is configurable** — `config.yaml → lessons.confirm_threshold`
- **Lessons are project-local** — not shared across projects
