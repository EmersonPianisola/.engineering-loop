---
name: linter-agent
id: linter-agent
version: 1.0.0
type: skill
stage: qa.static
---

# Skill: Linter Agent

## Objective
Perform static analysis on source code: linting, type checking, and cyclomatic complexity measurement.

## Inputs
- Source code files from the project
- Project configuration (eslint, tsconfig, pyproject.toml, etc.)
- Stage context: `state.stages.qa.static`

## Permitted Tools
- `bash`: Run lint/type-check commands
- `read`: Read source files
- `glob`: Find source files
- `grep`: Search for patterns

## Output Format
```json
{
  "verdict": "PASS|FAIL|BLOCKED",
  "qa_type": "deterministic",
  "confidence": 1.0,
  "severity": "info|low|medium|high|critical",
  "lint_errors": ["error messages"],
  "type_errors": ["error messages"],
  "cyclomatic_score": 10,
  "hotspots": ["function names"],
  "files_analyzed": 25,
  "execution_command": "npx eslint .",
  "exit_code": 0,
  "findings": [],
  "complete": true
}
```

## Mandatory Evidence
- `files_analyzed` > 0
- `lint_errors` present (may be empty)
- `type_errors` present (may be empty)
- `execution_command` recorded
- `exit_code` from tool execution

## Success Criteria
- Zero lint errors
- Zero type errors
- Cyclomatic complexity within threshold (default 15)

## Blocking Criteria
- Lint/type-check tool not found
- Project not buildable
- Cannot access source files

## Failure Criteria
- Any lint error found
- Any type error found
- Cyclomatic complexity exceeds threshold
