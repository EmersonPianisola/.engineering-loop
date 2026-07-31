---
name: impl-code
id: impl.code
version: 2.0.0
type: stage
description: 'TDD implementation. Per task: test first, then code, atomic commit. Gate decides done.'
---

# STAGE: Implementation Code (TDD)
<!-- ID: impl.code -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as the domain-specific execution skill.
- DO NOT transition to verify or other stages.
- The moment all blueprint tasks are implemented with passing tests and atomic commits, your task is FINISHED.
- Implementing features beyond the blueprint spec is a CRITICAL VIOLATION.

## Procedure

1. **Prerequisite Check:** If `state.artifacts.blueprint` is null or missing → `status: blocked`, `blocking_condition: implementation blueprint not produced`. **EXIT.**
2. Load confirmed lessons: `python3 scripts/lessons.py list --status confirmed` (if available).
3. Proceed with the steps below.

# Implementation Code — TDD Per Task

**Skill:** Domain-specific (self-constructed from internet best practices)
**Runs when:** `state.stages.impl.code.done == false`
**Prerequisite:** `state.artifacts.blueprint` not null

## Execute — TDD Per Task

- Set work item status `in-progress`.
- Capture `state.baseline_revision` (if first entry).
- For EACH task in the blueprint execution order:

### Per-Task TDD Cycle

```
FOR each task:
    1. WRITE TEST FIRST
       - Derive test from spec acceptance criteria — assert spec-defined outcomes
       - Never mirror implementation
       - Mock external dependencies (APIs, DB, FS)
       - Test happy path + error conditions

       IF task involves UI components:
       - WRITE UI CONTRACT TEST:
         a. Component renders without errors
         b. Required props are validated (missing prop → error/warning)
         c. Events fire correctly (click, submit, change → callback invoked)
         d. States render correctly (loading, error, empty, success)
         e. Form fields validate input (empty, invalid, valid)
         f. Accessibility: aria-labels, roles, keyboard navigation

    2. RED — Run gate
       - Test MUST fail (confirms test is not vacuous)
       - If test passes without code → test is wrong, rewrite

    3. IMPLEMENT CODE
       - Minimal code to satisfy test
       - Follow blueprint file structure, contracts, data flows
       - No speculative features
       - For UI: ensure all states (loading/error/empty) are handled

    4. GREEN — Run gate
       - ALL tests must pass
       - The test runner decides "done", not self-assessment
       - If tests fail → fix code, re-run

    5. ATOMIC COMMIT
       - One commit per task
       - Commit message references task ID
       - Never batch tasks

    6. NEXT TASK
```

### Execution Rules

1. Follow blueprint file structure exactly
2. Implement interface contracts as specified
3. Follow data flows as defined
4. Implement error handling as specified
5. Respect execution order — dependencies first
6. No speculative features
7. Tests derive from spec ACs — never weaken or skip tests to make them pass
8. One atomic commit per task — never batch
9. UI components MUST handle: loading state, error state, empty state, success state
10. UI forms MUST validate: required fields, type validation, error messages
11. Navigation MUST work: all routes accessible, no 404 on valid paths
12. Events MUST fire: onClick, onSubmit, onChange callbacks must be invoked

### Decisions

Record any implementation decisions that deviate from or extend the blueprint. Include rationale for each decision. These will be extracted as AD-NNN entries.

## Validate

- **Context slice:** `{diff}` + `{blueprint}` + `{work_item}`.
- Launch inline validator:
  > Compare code against blueprint and work item. Verify: (1) all blueprint files exist with correct responsibility, (2) interface contracts implemented, (3) data flows match, (4) error handling followed, (5) all acceptance criteria addressed, (6) no speculative features, (7) all tests pass, (8) decisions documented with rationale. Report: conformant | deviation(severity) | missing

- **Result:**
  - All conformant → `done = true`
  - `missing` or `deviation: high` → auto-fix, `done = false` (loop re-runs)
  - `deviation: medium/low` → auto-fix, `done = true`

## Expected Output

Your final response MUST strictly contain the implemented code files and test files per the blueprint. End your generation immediately after the last file. Do not write "Next steps".
