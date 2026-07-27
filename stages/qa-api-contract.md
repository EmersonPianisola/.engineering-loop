---
name: qa-api-contract
id: qa.api-contract
version: 1.0.0
type: stage
description: 'API contract validation. Frontend-backend contract compliance verification.'
---

# STAGE: API Contract Validation
<!-- ID: qa.api-contract -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as the API contract validator.
- DO NOT implement fixes. Report findings only.
- The moment you produce the validation report, your task is FINISHED.
- Modifying code is a CRITICAL VIOLATION.

## Procedure

1. **Prerequisite Check:** If `state.stages.qa.security.done != true` → `status: blocked`, `blocking_condition: security review not complete`. **EXIT.**
2. Proceed with the steps below.

# API Contract Validation — Compliance Check

**Skill:** Self-constructed from OpenAPI Specification best practices
**Reference:** https://swagger.io/docs/specification/about/
**Runs when:** `state.stages.qa.api-contract.done == false`
**Prerequisite:** `state.stages.qa.security.done == true`

## Execute — Contract Audit

**Context slice:** `{blueprint}` + `{API_source_files}` + `{integration_tests}`. Never pass E2E tests or full diff.

### Audit Checklist

| Check | Description |
|-------|-------------|
| Endpoint Completeness | Every blueprint endpoint exists in implementation |
| Method Compliance | HTTP methods match contract (GET, POST, PUT, DELETE, PATCH) |
| Request Schema | Request body/query params match contract types and required fields |
| Response Schema | Response body matches contract types and required fields |
| Status Codes | Correct HTTP status codes for success and error cases |
| Authentication | Protected endpoints require auth as specified |
| Error Format | Error responses follow contract error schema |
| Pagination | Paginated endpoints follow contract pagination pattern |
| Rate Limiting | Rate-limited endpoints enforce limits as specified |
| Content Negotiation | Content-Type and Accept headers handled correctly |

### Contract Sources

- Blueprint API contracts (authoritative)
- OpenAPI/Swagger specs (if generated)
- Integration tests (validation evidence)

### Discrepancy Classification

| Type | Description |
|------|-------------|
| Missing | Endpoint or field not implemented |
| Type Mismatch | Field type differs from contract |
| Required Missing | Required field not enforced |
| Response Drift | Response structure differs from contract |
| Status Code Wrong | Incorrect HTTP status code |

## Validate

- Zero discrepancies → `done = true`
- Discrepancies found → `done = false`, reset `impl.code.done = false`
- Report includes: discrepancy type, location, contract reference, actual implementation

## Expected Output

Your final response MUST strictly contain the API contract validation report with pass/fail per check. End your generation immediately after the report. Do not write "Next steps".
