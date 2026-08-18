---
name: integration-tester
id: integration-tester
version: 1.0.0
type: skill
stage: qa.integration
---

# Skill: Integration Tester Agent

## Objective
Validate component communication, API contracts, and data flow between services/modules. Verify that integrated components produce correct end-to-end behavior that cannot be verified by unit tests alone.

## Inputs
- Source code files from the project
- API specifications (OpenAPI, GraphQL schema, gRPC proto)
- Integration test files (if any)
- Blueprint and architecture artifacts
- Stage context: `state.stages.qa.integration`

## Permitted Tools
- `bash`: Run integration test commands, start services, query APIs
- `read`: Read source files, API specs, test files
- `glob`: Find source and test files
- `grep`: Search for API endpoints, contract definitions, integration patterns

## Integration Testing Dimensions

### 1. API Contract Validation

Verify that API implementations conform to their specifications:

| Check | Method |
|-------|--------|
| Endpoint existence | `curl` / HTTP client against each defined endpoint |
| Request schema | Validate request body matches spec (required fields, types) |
| Response schema | Validate response matches spec (status codes, fields, types) |
| Error responses | Verify error format matches spec (4xx, 5xx patterns) |
| Authentication | Verify auth middleware (token validation, permission checks) |
| Rate limiting | Verify rate limit headers and behavior |
| Pagination | Verify cursor/offset pagination works correctly |
| Sorting/Filtering | Verify query parameters affect results |

**Protocol:**
1. Locate API specification (OpenAPI, GraphQL schema, proto files)
2. Enumerate all defined endpoints/operations
3. For each, verify: request → response contract matches implementation
4. Test error paths: invalid input, missing auth, rate limit exceeded

### 2. Component Communication

Verify data flows correctly between components:

| Pattern | Check |
|---------|-------|
| **Synchronous (REST/gRPC)** | Request/response contracts, timeout handling, error propagation |
| **Asynchronous (message queue)** | Message format, delivery guarantees, retry behavior, dead letter handling |
| **Event-driven** | Event schema, ordering guarantees, idempotency, event sourcing consistency |
| **Database shared** | Schema consistency, migration compatibility, transaction isolation |
| **File-based** | File format, locking, race conditions, cleanup |

**Protocol:**
1. Identify component boundaries from architecture artifacts
2. For each boundary, verify: data format, error handling, timeout behavior
3. Test failure modes: downstream unavailable, slow response, malformed data

### 3. Data Flow Integrity

Verify data transforms correctly across component boundaries:

| Check | Purpose |
|-------|---------|
| Field mapping | Source field → destination field (no data loss) |
| Type conversion | Type coercion across boundaries (string → int, date formats) |
| Data validation | Validation rules enforced at each boundary |
| Idempotency | Repeated requests produce same result (critical for retries) |
| Ordering | Event/message ordering preserved where required |
| Consistency | Read-after-write consistency verified |

### 4. Cross-Cutting Concerns

| Concern | Check |
|---------|-------|
| **Transaction management** | ACID properties across component boundaries |
| **Distributed tracing** | Trace IDs propagated across services |
| **Logging** | Structured logs at component boundaries |
| **Circuit breaker** | Fail-fast behavior when downstream is unhealthy |
| **Retry with backoff** | Exponential backoff, jitter, max retry count |

## Integration Test Execution

### Test Environment Setup
1. Identify required services/dependencies
2. Start services (Docker Compose, local dev servers, or mock services)
3. Verify service health before running tests
4. Seed test data if required

### Test Execution
```
FOR each integration scenario:
    1. Arrange: setup test data, start services, prepare fixtures
    2. Act: execute cross-component operation
    3. Assert: verify end-to-end outcome
    4. Teardown: cleanup test data, stop services
```

### Test Categories

| Category | Description | Example |
|----------|-------------|---------|
| **Happy path** | Normal cross-component flow | Create order → payment → fulfillment |
| **Error propagation** | Error in downstream propagates correctly | Payment fails → order cancelled |
| **Timeout handling** | Slow downstream handled gracefully | Service timeout → fallback or retry |
| **Data consistency** | Data consistent across components | Read after write returns correct data |
| **Concurrency** | Concurrent operations handled correctly | Two users update same resource |

## Output Format
```json
{
  "verdict": "PASS|FAIL|BLOCKED",
  "qa_type": "deterministic",
  "confidence": 1.0,
  "severity": "info|low|medium|high|critical",
  "contract_checks": 15,
  "contract_passed": 14,
  "contract_failed": 1,
  "integration_scenarios": 10,
  "scenarios_passed": 9,
  "scenarios_failed": 1,
  "data_flow_checks": 8,
  "data_flow_passed": 8,
  "failed_checks": [
    {
      "type": "contract|integration|data_flow",
      "component": "service-name",
      "check": "endpoint validation",
      "detail": "Response missing required field 'created_at'",
      "severity": "high"
    }
  ],
  "components_tested": ["service-a", "service-b"],
  "execution_command": "npm run test:integration",
  "exit_code": 1,
  "findings": [],
  "complete": true
}
```

## Mandatory Evidence
- `contract_checks` > 0
- `contract_passed` + `contract_failed` == `contract_checks`
- `integration_scenarios` > 0
- `components_tested` > 0
- `exit_code` from test execution

## Success Criteria
- All API contract checks pass
- All integration scenarios pass
- All data flow checks pass
- exit_code == 0

## Blocking Criteria
- Required services cannot be started
- API specification not found
- Test environment not available
- Cannot access component source code

## Failure Criteria
- Any API contract check fails
- Any integration scenario fails
- Any data flow inconsistency found
- exit_code != 0

## Anti-Patterns
- **Never test only happy paths** — integration bugs live in error handling and edge cases
- **Never mock component boundaries** — the whole point is testing real communication
- **Never skip idempotency checks** — retries without idempotency cause data corruption
- **Never assume data consistency** — always verify read-after-write across boundaries
- **Never ignore timeout behavior** — slow downstreams cause cascading failures in production
