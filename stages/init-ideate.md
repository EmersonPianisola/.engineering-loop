---
name: init-ideate
id: init.ideate
version: 1.0.0
type: stage
description: 'Phase 0.25: BMAD-derived ideation. Party Mode analysis, Brainstorming, SDD extraction, impact-gated decomposition. Transforms raw work items into rich, executable flows.'
---

# STAGE: INIT.IDEATE (Phase 0.25)

## Execution Boundary

- You are acting EXCLUSIVELY as the `bmad-ideation` skill.
- DO NOT transition to any loop stage (architecture, impl, test, review).
- This stage exists ONLY to enrich and decompose raw work items.
- Generating implementation code or architecture artifacts is a CRITICAL VIOLATION.

## Procedure

# INIT.IDEATE — BMAD Ideation & Decomposition

## Purpose

Transform a raw, under-specified work item into a concrete, decomposed set of
atomic tasks with acceptance criteria, code maps, edge cases, and impact
classification. Uses BMAD-derived patterns: Party Mode, Brainstorming, and SDD
extraction.

## Early Exit

This stage is only needed for raw, ad-hoc work items. Exit immediately if:

1. `state.work_item_type == "bmad-spec"` — BMad specs are already structured. Set `done: true`. EXIT.
2. `state.work_item.acceptance_criteria` exists AND length ≥ 3 AND `state.work_item.code_map` is non-empty — item is already structured. Set `done: true`. EXIT.
3. `state.complexity == "small"` AND work item has clear `title`, `intent`, and ≥2 acceptance criteria — minimal ideation needed. Set `done: true`. EXIT.

## Path Resolution

- `{framework-root}` = directory containing ORCHESTRATOR.md
- `{loop-root}` = `{framework-root}`
- `{artifact-root}` = `{loop-root}/<config.artifact_root>`
- `{reference-root}` = `{framework-root}/<config.framework_reference_root>`

## Execution

### Step 1: Load Resources

1. Load `state.work_item` — the raw work item to enrich.
2. Load `{reference-root}/bmad-ideation-patterns.md` — embedded BMAD patterns.
3. Ensure directory exists: `{artifact-root}/ideation/`.

### Step 2: Generate Slug

Create a URL-safe slug from the work item title for artifact filenames:
- Lowercase, spaces → hyphens, remove special characters.
- Example: "User Authentication System" → `user-authentication-system`

### Step 3: Invoke Ideation Skill

Load the `bmad-ideation` skill procedure. Provide context slice:

```
Context for bmad-ideation skill:
- Work item: {state.work_item}
- BMAD patterns: {reference-root}/bmad-ideation-patterns.md
- Project context: {loop-root}/context.md (if exists)
- Existing artifacts: list of files in {artifact-root}/
```

The skill executes four phases:
1. **Party Mode** — 9-role parallel analysis
2. **Brainstorming** — 2-3 technique application
3. **SDD Extraction** — structured design document
4. **Decomposition + Impact Gate** — atomic tasks with impact classification

### Step 4: Impact Gate Resolution

After the skill completes decomposition:

1. Check for **Critical** impact items.
2. IF critical items exist:
   - Present to user: "The following items require your confirmation:"
   - List each critical item with rationale
   - AWAIT user response
   - IF confirmed: record in `state.ideation.critical_confirmed`, proceed
   - IF rejected: set `status: blocked`, `blocking_condition: critical items rejected`, EXIT
3. IF no critical items: proceed automatically.

### Step 5: Update State

On successful completion:

1. Update `state.work_item` with enriched fields from the skill output.
2. Set `state.work_item_type = "ideated"`.
3. Set `state.ideation = { completed: true, artifacts: {...}, techniques_used: [...], role_conflicts: [...] }`.
4. Set `state.stages.init.ideate.done = true`.

## Success Criteria

- Three artifacts written: `ideation-{slug}.md`, `sdd-{slug}.md`, `flows-{slug}.md`
- `state.work_item` enriched with: `title`, `intent`, `acceptance_criteria`, `code_map`, `edge_cases`, `non_goals`, `success_metrics`
- All critical impact items confirmed by user (if any)
- Role conflicts documented (not resolved)

## Anti-Patterns

- **Never skip early exit checks** — structured items don't need ideation
- **Never resolve role conflicts** — they indicate real tensions for downstream stages
- **Never auto-execute Critical items** — human confirmation is mandatory
- **Never produce unstructured output** — follow the SDD template exactly
- **Never discard brainstorming ideas** — even rejected ideas inform edge cases

## State Update Contract

**MANDATORY.** Follow `{reference-root}/sub-agent-contract.md`. Before returning your response:

1. Write all artifacts to their designated paths in `{artifact-root}/`
2. Update `{loop-root}/state.json`:
   - `stages.init.ideate.done = true` (or `false` on failure)
   - `stages.init.ideate.attempts += 1`
   - `stages.init.ideate.artifact_path = "artifacts/..."` (your output path)
   - `stages.init.ideate.error = null` (or failure description)
3. Record AD-NNN decisions in `{loop-root}/STATE.md ## Decisions` (if applicable)
4. Your response MUST be a single JSON line:
   - Success: `{"stage":"init.ideate","status":"done","artifact":"artifacts/..."}`
   - Failure: `{"stage":"init.ideate","status":"failed","error":"reason"}`

DO NOT include artifact content, summaries, or "Next steps" in your response.
