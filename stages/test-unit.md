---
name: test-unit
id: test.unit
version: 1.0.0
type: stage
description: 'Unit tests. Component-level isolation tests for individual functions and classes.'
---

# STAGE: Unit Tests
<!-- ID: test.unit -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as the unit test author.
- DO NOT write integration or E2E tests. DO NOT transition to other test stages.
- The moment you produce unit tests, your task is FINISHED.
- Modifying implementation code beyond test fixes is a CRITICAL VIOLATION.

## Procedure

1. **Prerequisite Check:** If `state.stages.impl.code.done != true` → `status: blocked`, `blocking_condition: implementation not complete`. **EXIT.**
2. Proceed with the steps below.

# Unit Tests — Component Isolation

**Skill:** Domain-specific (self-constructed from project test patterns)
**Runs when:** `state.stages.test.unit.done == false`
**Prerequisite:** `state.stages.impl.code.done == true`

## Design — Test Plan

- Input: BDD journey (unit-tagged scenarios) + blueprint + source code.
- Identify testable units: functions, classes, utilities, pure logic.
- Output: `{artifact-root}/test-plans/unit-{slug}.md`
- Store path in `state.artifacts.unit_test_plan`.

## Execute

- Implement unit tests per test plan.
- Each BDD scenario tagged `unit` → corresponding test.
- Mock external dependencies (APIs, DB, file system).
- Test both happy path and error conditions.
- Run unit test suite. All must pass.

### Test Quality Criteria

- Each test tests one behavior
- Tests are isolated (no shared state)
- Assertions are specific (not truthy/falsy)
- Edge cases covered
- Test names describe behavior, not implementation

## Validate

- All tests pass → `done = true`
- Tests fail → fix implementation, `done = false` (loop re-runs)

## Expected Output

Your final response MUST strictly contain the unit test files. End your generation immediately after the last test file. Do not write "Next steps".
