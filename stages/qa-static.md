---
name: qa-static
id: qa.static
version: 1.0.0
type: stage
description: 'Static analysis: lint, type-check, cyclomatic complexity. Base of QA pyramid.'
---

# STAGE: Static Analysis
<!-- ID: qa.static -->
<!-- Min Complexity: small -->
<!-- QA Type: deterministic -->
<!-- Cost Class: low -->

## Execution Boundary
- You are the static analysis agent.
- DO NOT fix any issues. Report findings only.
- Produce verifiable evidence: commands executed, exit codes, file counts.

## Procedure

1. **Prerequisite Check:** If `state.stages.verify.done != true` → `status: blocked`. **EXIT.**
2. Detect the project's linting and type-checking tools.
3. Execute tools and capture output.
4. Analyze cyclomatic complexity.
5. Produce structured output.

## Analysis Categories

| Category | Tool | Focus |
|----------|------|-------|
| Linting | ESLint, Pylint, Ruff, RuboCop, etc. | Code style, anti-patterns, bugs |
| Type Checking | TypeScript, mypy, Sorbet, etc. | Type safety, interface compliance |
| Complexity | Custom analysis | Cyclomatic complexity per function |

## Execution Strategy

1. Detect project type and available tools
2. Run lint tool: capture exit code, errors, warnings
3. Run type checker: capture errors
4. Analyze cyclomatic complexity for top functions
5. Compile results into structured output

## Evidence Contract

**REQUIRED fields:**
- `files_analyzed` (> 0)
- `lint_errors` (list, may be empty)
- `type_errors` (list, may be empty)
- `execution_command` (command that was run)
- `exit_code` (from tool execution)

## Output Schema

```json
{
  "verdict": "PASS|FAIL|BLOCKED",
  "qa_type": "deterministic",
  "confidence": 1.0,
  "severity": "info|low|medium|high|critical",
  "lint_errors": ["error messages"],
  "type_errors": ["error messages"],
  "cyclomatic_score": 0,
  "hotspots": ["function names with high complexity"],
  "files_analyzed": 10,
  "execution_command": "npx eslint .",
  "exit_code": 0,
  "findings": [],
  "complete": true
}
```

## Verdict Rules

- `PASS`: Zero lint errors, zero type errors
- `FAIL`: Any lint or type errors found
- `BLOCKED`: Tool not found, project not buildable

## State Update Contract

Update `state.json`:
- `stages.qa.static.done = true/false`
- `stages.qa.static.verdict = PASS/FAIL/BLOCKED`
- `stages.qa.static.attempts += 1`
- `stages.qa.static.output = <JSON result>`
