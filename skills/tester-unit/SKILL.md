---
name: tester-unit
id: tester-unit
version: 1.0.0
type: skill
stage: qa.unit
---

# Skill: Unit Tester Agent

## Objective
Generate and execute unit tests for source code. Verify test coverage meets threshold.

## Inputs
- Source code files from the project
- Existing test files (if any)
- Test framework configuration (vitest, jest, pytest, etc.)
- Stage context: `state.stages.qa.unit`

## Permitted Tools
- `bash`: Run test commands, install test dependencies
- `read`: Read source files
- `write`: Create test files
- `edit`: Modify test files
- `glob`: Find source and test files
- `grep`: Search for test patterns

## Output Format
```json
{
  "verdict": "PASS|FAIL|BLOCKED",
  "qa_type": "deterministic",
  "confidence": 1.0,
  "severity": "info|low|medium|high|critical",
  "test_count": 30,
  "tests_executed": 30,
  "passed": 30,
  "failed": 0,
  "coverage": 85.5,
  "failed_tests": [],
  "test_files": ["test files created"],
  "execution_command": "npx vitest run --coverage",
  "exit_code": 0,
  "findings": [],
  "complete": true
}
```

## Mandatory Evidence
- `test_count` > 0
- `tests_executed` == `test_count`
- `passed` + `failed` == `tests_executed`
- `coverage` present (0-100)
- `exit_code` from test runner

## Success Criteria
- All tests pass (failed == 0)
- Coverage >= threshold (default 70%)
- exit_code == 0

## Blocking Criteria
- Test framework not available
- Project not buildable
- Cannot execute test runner

## Failure Criteria
- Any test fails
- Coverage below threshold
- exit_code != 0
