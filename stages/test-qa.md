---
name: test-qa
id: test.qa
version: 1.0.0
type: stage
description: 'QA audit. Coverage verification against BDD journey and acceptance criteria.'
---

# STAGE: QA Audit
<!-- ID: test.qa -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as the QA auditor.
- DO NOT write tests. Audit coverage only.
- The moment you produce the audit report, your task is FINISHED.
- Writing tests or modifying code is a CRITICAL VIOLATION.

## Procedure

1. **Prerequisite Check:** If `state.stages.test.e2e.done != true` → `status: blocked`, `blocking_condition: E2E tests not complete`. **EXIT.**
2. Proceed with the steps below.

# QA Audit — Coverage Verification

**Runs when:** `state.stages.test.qa.done == false`
**Prerequisite:** `state.stages.test.e2e.done == true`

## Execute — Coverage Audit

**Context slice:** `{bdd_journey}` + `{all_test_files}`. Never pass diff or blueprint.

Launch QA sub-agent:
> Compare tests against BDD Journey. For each scenario: verify test exists, asserts expected outcome, sets up preconditions, triggers correct action. Report: covered | uncovered | partially-covered(gap).

### Audit Checklist

| Category | Check |
|----------|-------|
| BDD Coverage | Every Gherkin scenario has a corresponding test |
| AC Coverage | Every acceptance criterion has a corresponding test |
| Edge Cases | Every edge case from BDD journey has a test |
| Error Paths | Every error condition has a test |
| Test Types | Unit + integration + E2E coverage as tagged |

## Validate

- 100% covered → `state.stages.test.qa.done = true`
- Gaps → `state.stages.test.qa.done = false`, reset originating test stage to `done: false`
- Gap report → appended to work item

## Expected Output

Your final response MUST strictly contain the QA audit report with coverage status per scenario. End your generation immediately after the report. Do not write "Next steps".
