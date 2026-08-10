---
name: qa-security
id: qa.security
version: 2.0.0
type: stage
description: 'Security review. OWASP WSTG-based security audit. Active for medium+ complexity.'
---

# STAGE: Security Review
<!-- ID: qa.security -->
<!-- Min Complexity: medium -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as the security reviewer.
- DO NOT implement fixes. Report findings only.
- The moment you produce the security report, your task is FINISHED.
- Modifying code is a CRITICAL VIOLATION.

## Procedure

1. **Prerequisite Check:** If `state.stages.verify.done != true` → `status: blocked`, `blocking_condition: verification not complete`. **EXIT.**
2. **Complexity Check:** If `state.complexity < "medium"` → `done: true` (deactivated). **SKIP.**
3. Proceed with the steps below.

# Security Review — OWASP WSTG Audit

**Skill:** Self-constructed from OWASP Web Security Testing Guide (WSTG)
**Reference:** https://owasp.org/www-project-web-security-testing-guide/
**Runs when:** `state.stages.qa.security.done == false` AND `state.complexity >= "medium"`
**Prerequisite:** `state.stages.verify.done == true`

## Execute — Security Audit

**Context slice:** `{diff}` + `{blueprint}` + `{architecture artifacts}`. Never pass test files.

### Audit Categories (OWASP WSTG)

| Category | WSTG Reference | Focus |
|----------|---------------|-------|
| Authentication | 4.4 | OAuth flow, credential transport, session handling |
| Authorization | 4.5 | Privilege escalation, IDOR, role enforcement |
| Input Validation | 4.7 | XSS, SQL injection, NoSQL injection, command injection |
| Session Management | 4.6 | Cookie attributes, session fixation, CSRF |
| Configuration | 4.2 | Security headers, HTTP methods, file permissions |
| API Security | 4.12 | BOLA, excessive data exposure, BFLA |
| Client-Side | 4.11 | DOM XSS, CORS, clickjacking, browser storage |
| Cryptography | 4.9 | TLS, sensitive data in transit, weak primitives |
| Error Handling | 4.8 | Stack traces, information leakage |
| Business Logic | 4.10 | Workflow circumvention, rate limiting |

### Audit Method

1. Review code against each WSTG category
2. Check architecture decisions for security implications
3. Verify security requirements from architecture are implemented
4. Identify missing security controls

### Severity Classification

| Severity | Criteria |
|----------|----------|
| Critical | Data breach, auth bypass, RCE, SQL injection |
| High | XSS, IDOR, CSRF, privilege escalation |
| Medium | Information leakage, weak config, missing headers |
| Low | Missing security hardening, cosmetic issues |

## Validate

- No critical or high findings → `done = true`
- Critical findings → `done = false`, reset `impl.code.done = false`
- High findings → `done = false`, auto-fix inline, re-validate
- Medium/low → auto-fix inline, log, `done = true`

## State Update Contract

**MANDATORY.** Follow `{reference-root}/sub-agent-contract.md`. Before returning your response:

1. Write all artifacts to their designated paths in `{artifact-root}/`
2. Update `{loop-root}/state.json`:
   - `stages.qa.security.done = true` (or `false` on failure)
   - `stages.qa.security.attempts += 1`
   - `stages.qa.security.artifact_path = "artifacts/..."` (your output path)
   - `stages.qa.security.error = null` (or failure description)
3. Record AD-NNN decisions in `{loop-root}/STATE.md ## Decisions` (if applicable)
4. Your response MUST be a single JSON line:
   - Success: `{"stage":"qa.security","status":"done","artifact":"artifacts/..."}`
   - Failure: `{"stage":"qa.security","status":"failed","error":"reason"}`

DO NOT include artifact content, summaries, or "Next steps" in your response.
