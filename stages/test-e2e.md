---
name: test-e2e
id: test.e2e
version: 1.0.0
type: stage
description: 'End-to-end tests. User flow tests via Playwright across the full application stack.'
---

# STAGE: E2E Tests
<!-- ID: test.e2e -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as the E2E test author using Playwright.
- DO NOT write unit or integration tests. DO NOT transition to QA stage.
- The moment you produce E2E tests, your task is FINISHED.
- Modifying implementation code beyond test fixes is a CRITICAL VIOLATION.

## Procedure

1. **Prerequisite Check:** If `state.stages.test.integration.done != true` → `status: blocked`, `blocking_condition: integration tests not complete`. **EXIT.**
2. Proceed with the steps below.

# E2E Tests — User Flow Validation

**Skill:** `e2e-playwright`
**Runs when:** `state.stages.test.e2e.done == false`
**Prerequisite:** `state.stages.test.integration.done == true`

## Design — E2E Test Plan

- Input: BDD journey (e2e-tagged scenarios) + UX flows.
- Identify user-facing flows that need E2E coverage.
- Output: `{artifact-root}/test-plans/e2e-{slug}.md`
- Store path in `state.artifacts.e2e_test_plan`.

## Execute

- Infrastructure setup if needed (Playwright config, browsers).
- Implement E2E tests per test plan using Playwright.
- Each BDD scenario tagged `e2e` → corresponding Playwright test.
- Use resilient locators: `getByRole`, `getByLabel`, `getByTestId`.
- Test across configured browsers (Chromium minimum).
- Run full E2E suite. All must pass.

### Playwright Best Practices

- Auto-waiting: never use artificial timeouts
- Test isolation: fresh browser context per test
- Resilient locators: role-based selectors over CSS paths
- Parallel execution: tests run independently
- Trace viewer: enable tracing for failure investigation

### Test Quality Criteria

- Each test covers one user flow
- Tests are independent (no test dependencies)
- Assertions verify user-visible outcomes
- Happy path + critical error paths covered
- Tests run reliably in CI environment

## Validate

- All tests pass → `done = true`
- Tests fail → fix implementation, `done = false` (loop re-runs)

## Expected Output

Your final response MUST strictly contain the E2E test files. End your generation immediately after the last test file. Do not write "Next steps".
