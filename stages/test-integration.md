---
name: test-integration
id: test.integration
version: 1.0.0
type: stage
description: 'Integration tests. Service and API interaction tests between components.'
---

# STAGE: Integration Tests
<!-- ID: test.integration -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as the integration test author.
- DO NOT write unit or E2E tests. DO NOT transition to other test stages.
- The moment you produce integration tests, your task is FINISHED.
- Modifying implementation code beyond test fixes is a CRITICAL VIOLATION.

## Procedure

1. **Prerequisite Check:** If `state.stages.test.unit.done != true` → `status: blocked`, `blocking_condition: unit tests not complete`. **EXIT.**
2. Proceed with the steps below.

# Integration Tests — Component Interaction

**Skill:** Domain-specific (self-constructed from project test patterns)
**Runs when:** `state.stages.test.integration.done == false`
**Prerequisite:** `state.stages.test.unit.done == true`

## Design — Integration Test Plan

- Input: BDD journey (integration-tagged scenarios) + API contracts from blueprint.
- Identify integration points: service-to-service, API endpoints, database interactions.
- Output: `{artifact-root}/test-plans/integration-{slug}.md`
- Store path in `state.artifacts.integration_test_plan`.

## Execute

- Implement integration tests per test plan.
- Each BDD scenario tagged `integration` → corresponding test.
- Test actual component interactions (not mocked).
- Use test database or in-memory alternatives.
- Test API contracts: request/response schemas, status codes, error responses.
- Run integration test suite. All must pass.

### Test Quality Criteria

- Tests verify component interactions, not individual behavior
- Database operations tested with test data
- API contracts validated (request/response)
- Error handling between components verified
- Test data setup and teardown is clean

## Validate

- All tests pass → `done = true`
- Tests fail → fix implementation, `done = false` (loop re-runs)

## Expected Output

Your final response MUST strictly contain the integration test files. End your generation immediately after the last test file. Do not write "Next steps".
