# API & Integration Design

Covers: REST/GraphQL/gRPC design standards, versioning, contract-first design, pub/sub and event streaming, ESB vs. point-to-point integration, idempotency keys.

## REST API design standards
- Model resources as nouns, use HTTP methods for actions (`GET /orders/123`, `POST /orders`, `PATCH /orders/123`, `DELETE /orders/123`) — avoid verb-in-URL patterns (`/getOrder`, `/createOrder`) which fight the grain of HTTP semantics and caching.
- Use HTTP status codes meaningfully and consistently: 2xx for success, 4xx for client errors (400 validation, 401 unauthenticated, 403 unauthorized, 404 not found, 409 conflict, 429 rate limited), 5xx for server errors — don't return 200 with an error payload buried in the body, which breaks standard tooling (monitoring, retries, client libraries) that relies on status codes.
- Return consistent, structured error responses with a machine-readable error code, a human-readable message, and (in non-production or for known-safe fields) enough detail to act on — never a raw stack trace or internal exception message (see `owasp-secure-coding-bdd` error-handling guidance).
- Design for pagination, filtering, and sorting on any list endpoint from the start, using consistent query parameter conventions across the API (`?page=`/`?cursor=`, `?limit=`, `?sort=`) rather than ad hoc per-endpoint conventions.
- Prefer cursor-based pagination over offset-based for large or frequently-changing datasets — offset pagination degrades in both performance (the database still scans/skips prior rows) and correctness (items can shift between pages if the underlying data changes between requests).

## API versioning
- Version explicitly (URL path `/v1/orders`, a header, or content negotiation) rather than silently changing a contract that existing clients depend on — a breaking change to a live API without versioning breaks every consumer simultaneously with no migration window.
- Distinguish backward-compatible changes (adding an optional field, a new endpoint) from breaking ones (removing/renaming a field, changing a field's type or meaning, changing required parameters) — only breaking changes need a new version; don't version-bump for additive changes, which just fragments the API unnecessarily.
- Deprecate old versions on a defined, communicated timeline rather than supporting every version indefinitely (accumulating unmaintainable surface area) or removing a version abruptly without notice.

## Contract-first design
- For APIs with multiple consumers (other teams, external partners), define the contract (OpenAPI/Swagger for REST, a `.proto` file for gRPC, a schema for GraphQL) before or alongside implementation, and treat it as the source of truth both teams build against — this lets consumer teams build against a mock/stub of the contract in parallel rather than waiting for the full implementation, and catches contract mismatches early via schema validation rather than in production integration testing.
- Run contract tests (e.g., Pact, or schema validation in CI) that verify the actual implementation matches the published contract, and that a provider's changes don't silently break a documented consumer expectation — wire this into the same CI/CD pipeline as the BDD suite from `bdd-comprehensive-testing`.

## GraphQL
- See `owasp-secure-coding-bdd`'s `api-tokens-graphql-microservices.md` for GraphQL-specific security (depth/complexity limits, introspection, field-level authorization) — apply those alongside the design guidance here.
- Design the schema around consumer needs (what shapes of data do clients actually need to query in one round trip) rather than mechanically mirroring the database schema — GraphQL's value is letting clients fetch precisely what they need, which requires actual schema design effort, not a 1:1 auto-generated mapping from tables.

## gRPC
- Strong fit for internal service-to-service communication needing low latency and strict typed contracts (via Protocol Buffers) — less suited to public-facing APIs consumed by arbitrary web/mobile clients where REST/JSON's ubiquity and human-readability matter more.
- Design `.proto` messages with forward/backward compatibility in mind from the start (never reuse a field number, add new fields as optional, don't repurpose an existing field's meaning) since Protobuf's wire format depends on consistent field numbering across versions.

## Pub/sub and event streaming (Kafka, SNS/SQS, etc.)
- Design event schemas deliberately and version them (like any other contract) — an event schema change that breaks existing consumers is exactly as disruptive as a breaking REST API change, just less visible until a consumer actually fails.
- Distinguish **event notification** (a small message saying "something happened, go fetch details if you need them") from **event-carried state transfer** (the event itself carries the full relevant data) — the latter avoids extra round trips but increases event size and duplicates data across services; choose deliberately based on consumer needs, not by default.
- Design consumers to be idempotent (see `resilience-reliability-patterns.md`) since most streaming platforms provide at-least-once delivery, not exactly-once, by default.
- Use a schema registry (Confluent Schema Registry, AWS Glue Schema Registry, or equivalent) for event contracts in any non-trivial event-driven system, enforcing compatibility checks on schema evolution in CI, the same discipline as contract tests for REST/gRPC.

## ESB vs. point-to-point integration
- A point-to-point integration (service A calls service B directly) is simpler and has fewer moving parts — prefer it for a small number of well-understood integrations.
- An Enterprise Service Bus or integration platform earns its complexity when there are many services needing mediated routing, transformation, and protocol translation between heterogeneous systems (common in large enterprises integrating legacy and modern systems) — don't introduce an ESB for a handful of services that could integrate directly; that's unjustified complexity for the actual current need (see the over-engineering caution in the main SKILL.md).

## Idempotency keys for APIs
- For any API operation with a side effect that shouldn't be duplicated on retry (payments, resource creation, sending a notification), support a client-supplied idempotency key header; the server stores the key with the result of the first successful execution and returns that same result for subsequent requests with the same key, rather than re-executing the side effect (see `resilience-reliability-patterns.md` for the underlying pattern).

## BDD scenario patterns

```gherkin
Scenario: Breaking API change is served under a new version, old version still works
  Given API v1 clients depend on a field "total" being a string
  When v2 changes "total" to a number
  Then v1 clients calling /v1/orders still receive "total" as a string
  And v2 clients calling /v2/orders receive the new numeric type

Scenario: API returns structured, consistent error response
  When a request is missing a required field
  Then the response is 400 with a machine-readable error code and field name
  And no internal exception detail is included

Scenario: Idempotency key prevents duplicate resource creation
  Given a "create order" request with idempotency key "xyz" has already succeeded
  When the same request is retried with the same key
  Then no second order is created and the original order is returned

Scenario: Consumer handles an event schema evolution without breaking
  Given an event schema adds a new optional field
  When an older consumer that doesn't know about the field processes the event
  Then processing succeeds, ignoring the unknown field
```
