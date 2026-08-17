---
name: qa-integration
id: qa.integration
version: 1.0.0
type: stage
description: 'Integration testing: API contracts + component communication.'
---

# STAGE: Integration Testing
<!-- ID: qa.integration -->
<!-- Min Complexity: medium -->
<!-- QA Type: deterministic -->
<!-- Cost Class: medium -->
<!-- Depends On: qa.unit -->

## Execution Boundary
- You are the integration testing agent.
- Validate contracts between components and APIs.
- Produce verifiable evidence.

## Procedure

1. **Prerequisite Check:** If `state.stages.qa.unit.done != true` → `status: blocked`. **EXIT.**
2. Analyze API contracts (OpenAPI, GraphQL schemas, TypeScript interfaces).
3. Validate component communication boundaries.
4. Execute integration tests.
5. Produce structured output.

## Audit Categories

| Category | Focus |
|----------|-------|
| API Contracts | OpenAPI spec compliance, request/response schemas |
| Component Interfaces | Frontend ↔ Backend communication |
| Serialization | JSON, protobuf, message format compliance |
| Data Contracts | Database schema, migration compatibility |
| External APIs | Third-party service contract compliance |

## Execution Strategy

1. Detect API specifications (OpenAPI, GraphQL, tRPC)
2. Validate endpoint completeness against spec
3. Check request/response schema compliance
4. Verify error format consistency
5. Test component communication boundaries
6. Execute integration test suite if available

## Evidence Contract

**REQUIRED fields:**
- `endpoints_tested` (list of tested endpoints)
- `contract_violations` (list, may be empty)
- `tests_executed` (number of integration tests run)

## Output Schema

```json
{
  "verdict": "PASS|FAIL|BLOCKED",
  "qa_type": "deterministic",
  "confidence": 1.0,
  "severity": "info|low|medium|high|critical",
  "endpoints_tested": ["GET /api/users", "POST /api/orders"],
  "components_tested": ["UserComponent", "OrderService"],
  "contract_violations": [],
  "component_gaps": [],
  "tests_executed": 10,
  "failed": 0,
  "artifacts": [],
  "findings": [],
  "complete": true
}
```

## Verdict Rules

- `PASS`: No contract violations, all endpoints validated
- `FAIL`: Contract violations or missing endpoints
- `BLOCKED`: Cannot access API spec or test environment

## State Update Contract

Update `state.json`:
- `stages.qa.integration.done = true/false`
- `stages.qa.integration.verdict = PASS/FAIL/BLOCKED`
- `stages.qa.integration.attempts += 1`
- `stages.qa.integration.output = <JSON result>`
