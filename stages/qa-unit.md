---
name: qa-unit
id: qa.unit
version: 1.0.0
type: stage
description: 'Unit test generation and execution. Second layer of QA pyramid.'
---

# STAGE: Unit Testing
<!-- ID: qa.unit -->
<!-- Min Complexity: small -->
<!-- QA Type: deterministic -->
<!-- Cost Class: low -->
<!-- Depends On: qa.static -->

## Execution Boundary
- You are the unit testing agent.
- Generate AND execute tests.
- Produce verifiable evidence: test count, exit codes, coverage.

## Procedure

1. **Prerequisite Check:** If `state.stages.qa.static.done != true` → `status: blocked`. **EXIT.**
2. Analyze source code for testable units.
3. Generate unit tests for functions, classes, and business logic.
4. Execute test suite.
5. Measure coverage.
6. Produce structured output.

## Test Generation Strategy

1. Identify testable units (functions, classes, modules)
2. For each unit, generate tests covering:
   - Happy path
   - Edge cases
   - Error conditions
   - Boundary values
3. Use project's test framework (Vitest, Jest, pytest, etc.)
4. Write tests to standard test directory

## Execution Strategy

1. Detect test framework and runner
2. Execute test suite: capture output, exit code
3. Measure code coverage
4. Record results

## Evidence Contract

**REQUIRED fields:**
- `test_count` (> 0)
- `tests_executed` (== test_count)
- `passed` (>= 0)
- `failed` (>= 0)
- `coverage` (0-100)
- `exit_code` (from test runner)

**CONSISTENCY:**
- `tests_executed <= test_count`
- `passed + failed == tests_executed`

## Output Schema

```json
{
  "verdict": "PASS|FAIL|BLOCKED",
  "qa_type": "deterministic",
  "confidence": 1.0,
  "severity": "info|low|medium|high|critical",
  "test_count": 20,
  "tests_executed": 20,
  "passed": 20,
  "failed": 0,
  "coverage": 85.5,
  "failed_tests": [],
  "test_files": ["test files created"],
  "execution_command": "npx vitest run",
  "exit_code": 0,
  "findings": [],
  "complete": true
}
```

## Verdict Rules

- `PASS`: All tests pass, coverage >= threshold (default 70%)
- `FAIL`: Any test fails OR coverage below threshold
- `BLOCKED`: Test runner not available, project not buildable

## State Update Contract

Update `state.json`:
- `stages.qa.unit.done = true/false`
- `stages.qa.unit.verdict = PASS/FAIL/BLOCKED`
- `stages.qa.unit.attempts += 1`
- `stages.qa.unit.output = <JSON result>`
