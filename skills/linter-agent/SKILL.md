---
name: linter-agent
id: linter-agent
version: 2.0.0
type: skill
stage: qa.static
---

# Skill: Linter Agent

## Objective
Perform comprehensive static analysis on source code: linting, type checking, security analysis, maintainability assessment, and cyclomatic complexity measurement. Distinguish real issues from false positives.

## Inputs
- Source code files from the project
- Project configuration (eslint, tsconfig, pyproject.toml, etc.)
- Stage context: `state.stages.qa.static`

## Permitted Tools
- `bash`: Run lint/type-check/security commands
- `read`: Read source files
- `glob`: Find source files
- `grep`: Search for patterns

## Analysis Dimensions

### 1. Lint Errors
Standard linting rules from project configuration.

### 2. Type Errors
Type checking from TypeScript, mypy, or equivalent.

### 3. Security Analysis
Security-focused static analysis:

| Tool | Language | Purpose |
|------|----------|---------|
| `bandit` | Python | Detect security hotspots (SQL injection, hardcoded secrets, unsafe deserialization) |
| `eslint-plugin-security` | JavaScript | Detect security issues (eval, innerHTML, unsafe redirects) |
| `npm audit` | JavaScript | Known vulnerable dependencies |
| `pip audit` | Python | Known vulnerable dependencies |

**Security severity levels:**
- `CRITICAL`: Direct exploit vector (SQL injection, RCE, XSS)
- `HIGH`: Potential data exposure (hardcoded secrets, weak crypto)
- `MEDIUM`: Security best practice violation (missing input validation)
- `LOW`: Hardening opportunity (verbose error messages)

### 4. Maintainability Assessment

| Metric | Tool | Threshold |
|--------|------|-----------|
| Maintainability Index | Pylint / CodeClimate | >= 80 (good), 60-79 (acceptable), < 60 (needs work) |
| Cyclomatic Complexity | ESLint / Radon | <= 10 (good), 11-20 (moderate), > 20 (high) |
| Halstead Volume | ESLint / XCop | Context-dependent |
| Technical Debt Ratio | Sonar / ESLint | < 1% (good), 1-5% (acceptable), > 5% (high) |

### 5. False Positive Handling

Not all reported issues are real problems:

| Category | Example | Action |
|----------|---------|--------|
| **False Positive** | Linter flags safe pattern as insecure | Verify manually, add suppression comment with rationale |
| **Intentional Violation** | Deliberate `any` type for dynamic data | Add suppression comment with rationale |
| **Legacy Code** | Old code pending refactor | Flag as technical debt, not blocking |
| **Real Issue** | Actual security vulnerability or type error | Report as finding, must fix |

**Suppression protocol:**
1. Verify the issue is genuinely a false positive or intentional
2. Add inline suppression with rationale: `// eslint-disable-next-line security/detect-eval-with-expression — required for dynamic config parsing`
3. Never suppress without a comment explaining why
4. Track suppressions in findings for review

## Output Format
```json
{
  "verdict": "PASS|FAIL|BLOCKED",
  "qa_type": "deterministic",
  "confidence": 1.0,
  "severity": "info|low|medium|high|critical",
  "lint_errors": ["error messages"],
  "type_errors": ["error messages"],
  "security_findings": [
    {
      "severity": "high",
      "rule": "hardcoded-password",
      "file": "src/auth.py",
      "line": 42,
      "detail": "Hardcoded password in database connection string"
    }
  ],
  "cyclomatic_score": 10,
  "hotspots": ["function names with complexity > 15"],
  "maintainability_index": 78,
  "technical_debt_ratio": 2.3,
  "false_positives_filtered": 4,
  "files_analyzed": 25,
  "execution_command": "npx eslint . && bandit -r src/",
  "exit_code": 0,
  "findings": [],
  "complete": true
}
```

## Mandatory Evidence
- `files_analyzed` > 0
- `lint_errors` present (may be empty)
- `type_errors` present (may be empty)
- `security_findings` present (may be empty)
- `maintainability_index` present (0-100)
- `execution_command` recorded
- `exit_code` from tool execution

## Success Criteria
- Zero lint errors (excluding documented suppressions)
- Zero type errors (excluding documented suppressions)
- Zero security findings at CRITICAL or HIGH severity
- Cyclomatic complexity within threshold (default 15)
- Maintainability index >= 60

## Blocking Criteria
- Lint/type-check tool not found
- Project not buildable
- Cannot access source files

## Failure Criteria
- Any lint error found (un-suppressed)
- Any type error found (un-suppressed)
- Any CRITICAL or HIGH security finding
- Cyclomatic complexity exceeds threshold
- Maintainability index < 60

## Anti-Patterns
- **Never suppress without rationale** — every suppression needs an inline comment
- **Never ignore security findings** — even LOW severity should be tracked
- **Never trust raw linter output blindly** — verify false positives before reporting
- **Never skip dependency audit** — vulnerable dependencies are as critical as code issues
- **Never treat all warnings equally** — prioritize by severity and exploitability
