---
name: tester-unit
id: tester-unit
version: 2.0.0
type: skill
stage: qa.unit
---

# Skill: Unit Tester Agent

## Objective
Generate and execute unit tests for source code. Verify test coverage meets threshold. Validate test discrimination strength via mutation score. Use two-step prompting: scenario identification before code generation for higher assertion quality.

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

## Two-Step Test Generation

### Step 1: Scenario Identification
Before writing test code, identify test scenarios:

1. Read the source file
2. Enumerate all public functions/methods
3. For each, identify:
   - Happy path inputs and expected outputs
   - Boundary values (0, -1, max, empty, null, undefined)
   - Error conditions (invalid args, edge cases, type mismatches)
   - State transitions (if applicable)
4. Write scenarios in plain language before generating code

**Why:** Research shows two-step prompting (scenario → code) produces tests with stronger assertions than direct code generation. The intermediate scenario step forces the model to reason about behavior before committing to syntax.

### Step 2: Code Generation
Generate test code from scenarios:

```
FOR each scenario:
    Generate test function with:
    - Descriptive name matching scenario
    - Arrange: setup inputs, mocks, fixtures
    - Act: invoke target function
    - Assert: specific value assertions (not just truthiness)
    - Comment: // Scenario: {description}
```

**Assertion quality rules:**
- Assert specific values, not just truthiness: `assertEqual(result, 42)` not `assert(result)`
- Assert error types and messages: `assertRaises(ValueError, "empty input")`
- Assert boundary behavior: test `0`, `-1`, `max`, `empty`, `null`
- Assert side effects: mock calls, state changes, file writes
- Never assert `true` or `None` without context — these are weak assertions

## Boundary Value Analysis

For every function accepting numeric, string, or collection inputs:

| Boundary | Test |
|----------|------|
| Minimum valid | Lower bound of valid range |
| Minimum invalid | One below minimum valid |
| Maximum valid | Upper bound of valid range |
| Maximum invalid | One above maximum valid |
| Empty | Empty string, empty array, null |
| Single element | Minimal non-empty input |
| Large input | Performance boundary |

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
  "mutation_score": 82.0,
  "mutation_killed": 41,
  "mutation_survived": 9,
  "mutation_equivalent": 3,
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
- `mutation_score` present (0-100)
- `exit_code` from test runner

## Success Criteria
- All tests pass (failed == 0)
- Coverage >= threshold (default 70%)
- Mutation score >= threshold (default 80%)
- exit_code == 0

## Blocking Criteria
- Test framework not available
- Project not buildable
- Cannot execute test runner

## Failure Criteria
- Any test fails
- Coverage below threshold
- Mutation score below threshold
- exit_code != 0

## Anti-Patterns
- **Never skip scenario identification** — direct code generation produces weaker assertions
- **Never assert truthiness without context** — `assert(result)` tells you nothing about correctness
- **Never skip boundary values** — most bugs live at boundaries, not in the happy path
- **Never mock everything** — mock external dependencies, not the code under test
- **Never ignore mutation score** — 95% coverage with 50% mutation score means tests assert nothing meaningful
