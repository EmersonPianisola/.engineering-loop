---
name: impl-code
id: impl.code
version: 1.0.0
type: stage
description: 'Code implementation. Execute all blueprint tasks, produce working code.'
---

# STAGE: Implementation Code
<!-- ID: impl.code -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as the domain-specific execution skill.
- DO NOT transition to test or review stages.
- The moment you implement all blueprint tasks, your task is FINISHED.
- Implementing features beyond the blueprint spec is a CRITICAL VIOLATION.

## Procedure

1. **Prerequisite Check:** If `state.artifacts.blueprint` is null or missing → `status: blocked`, `blocking_condition: implementation blueprint not produced`. **EXIT.**
2. Proceed with the steps below.

# Implementation Code — Execute

**Skill:** Domain-specific (self-constructed from internet best practices)
**Runs when:** `state.stages.impl.code.done == false`
**Prerequisite:** `state.artifacts.blueprint` not null

## Execute

- Set work item status `in-progress`.
- Capture `state.baseline_revision` (if first entry).
- Invoke domain-specific execution skill with work item + blueprint.
- Execute ALL tasks in blueprint execution order. Mark `[x]`.
- Never implement beyond spec.
- **Decisions:** Record any implementation decisions that deviate from or extend the blueprint. Include rationale for each decision. These will be extracted by the `doc.decisions` stage.

### Execution Rules

1. Follow blueprint file structure exactly
2. Implement interface contracts as specified
3. Follow data flows as defined
4. Implement error handling as specified
5. Respect execution order — dependencies first
6. No speculative features

## Validate

- **Context slice:** `{diff}` + `{blueprint}` + `{work_item}`. Never pass behavior_map or review_plan.
- Launch sub-agent:
   > Compare code against blueprint and work item. Verify: (1) all blueprint files exist with correct responsibility, (2) interface contracts implemented, (3) data flows match, (4) error handling followed, (5) all acceptance criteria addressed, (6) no speculative features, (7) implementation decisions documented with rationale. Report: conformant | deviation(severity) | missing

- **Result:**
  - All conformant → `done = true`
  - `missing` or `deviation: high` → auto-fix, `done = false` (loop re-runs)
  - `deviation: medium/low` → auto-fix, `done = true`

## Expected Output

Your final response MUST strictly contain the implemented code files per the blueprint. End your generation immediately after the last file. Do not write "Next steps".
