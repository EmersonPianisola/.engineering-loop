# Microservices Patterns

Covers: Service decomposition via DDD, API Gateway, Service Discovery, sync/async communication, Saga pattern, Event Sourcing, CQRS, Strangler Fig, database-per-service.

## Service decomposition
- Decompose along **Domain-Driven Design bounded contexts** — a service should map to a coherent business capability with its own ubiquitous language (e.g., "Order Management," "Inventory," "Billing"), not a technical concern ("the validation service," "the database service").
- A good boundary test: could this service's team make most changes without needing a coordinated release with another team? If two "services" almost always change together, they're probably one bounded context split in two — a common accidental-coupling mistake.
- Each service should be independently deployable and independently scalable — if deploying service A always requires redeploying service B in lockstep, the boundary is wrong or the contract between them is too tightly coupled.

## Database per service
- Each microservice owns its data exclusively; no other service queries that database directly, ever — all cross-service data access goes through the owning service's API or published events.
- This is what actually enables independent deployability: if service B can be broken by service A silently changing its schema (because B was querying A's tables directly), you don't have independent services, you have a distributed monolith with the failure modes of both.
- Consequence: no cross-service joins or cross-service ACID transactions — see Saga pattern below for how to handle multi-service consistency.

## Inter-service communication

### Synchronous (REST, gRPC)
- Use when the caller needs an immediate response to proceed (e.g., "is this payment authorized").
- Always apply timeouts, retries with backoff, and circuit breakers on synchronous calls (see `resilience-reliability-patterns.md`) — a synchronous call chain across several services multiplies latency and failure probability with every hop; a hard dependency chain of 5 synchronous services each with 99.9% availability yields under 99.5% for the whole chain.
- Minimize synchronous call depth/fan-out; a request that synchronously calls 6 other services to render one page is fragile and slow. Prefer async/event-driven for anything that doesn't need an immediate response, or aggregate data ahead of time (see CQRS below).

### Asynchronous (message queues, event streaming — Kafka, RabbitMQ, SQS/SNS, etc.)
- Use for anything that doesn't need an immediate synchronous answer: notifications, analytics, cross-service side effects, workflows that can tolerate eventual consistency.
- Decouples availability: if the consumer is down, messages queue up rather than the whole request chain failing.
- Requires its own discipline: idempotent consumers (a message can be delivered more than once — "at least once" delivery is the common guarantee, so consumers must handle duplicate processing safely), dead-letter queues for messages that repeatedly fail processing, and monitoring queue depth/consumer lag as a first-class operational metric.

## API Gateway
- A single entry point for external clients that handles cross-cutting concerns (authentication, rate limiting, request routing, response aggregation) so individual services don't each reimplement them.
- Don't let the gateway accumulate business logic — it routes and enforces cross-cutting policy, it doesn't make domain decisions; business logic creeping into the gateway recreates a monolith at the edge.

## Service discovery
- In dynamic environments (containers, auto-scaling), services need a way to find each other's current network location rather than hardcoded addresses — a service registry (Consul, Eureka, or the orchestration platform's built-in discovery like Kubernetes DNS/Services) tracks healthy instances so callers/gateways can route correctly as instances come and go.

## Saga pattern (distributed transactions)
- Since there's no cross-service ACID transaction, a business process spanning multiple services (e.g., "place order" touching Inventory, Payment, and Shipping) is implemented as a Saga: a sequence of local transactions, each publishing an event that triggers the next step, with explicit **compensating transactions** to undo prior steps if a later step fails.
- Two coordination styles: **choreography** (each service reacts to events from others, no central coordinator — simpler but harder to see the overall flow) and **orchestration** (a central saga orchestrator explicitly calls each step and handles failures — easier to reason about and monitor, adds a coordinating component).
- Design compensating actions deliberately as part of the feature, not as an afterthought — "how do we undo this step if a later step fails" is a required design question for every saga step, and should be captured in BDD scenarios (see `bdd-comprehensive-testing`) as explicit non-happy-path cases.

## Event Sourcing
- Instead of storing only current state, store the sequence of events that led to it; current state is derived by replaying events. Gives a full audit trail and the ability to reconstruct state at any point in time, at the cost of query complexity (you generally pair it with CQRS, below, to get efficient reads) and a real learning curve for the team.
- Strong fit for domains where the history of changes has intrinsic business value (financial ledgers, order lifecycles, audit-heavy domains) — a poor fit as a default for simple CRUD data with no real need for historical replay.

## CQRS (Command Query Responsibility Segregation)
- Separate the model used to write data (commands, enforcing business rules and invariants) from the model used to read data (queries, optimized for the actual read patterns — often a denormalized, pre-joined view).
- Often paired with event sourcing (the write side produces events, the read side is a projection built by consuming them), but usable independently — even a single-database system can benefit from separate write and read models if read and write access patterns are very different.
- Overkill for simple CRUD services with no meaningful difference between the read and write shape of the data — don't apply this reflexively; the complexity (eventual consistency between write and read models, more moving parts) needs to be justified by an actual read/write pattern mismatch.

## Strangler Fig pattern (incremental migration)
- When migrating a monolith to microservices (or any large system rewrite), route traffic for one capability at a time to the new implementation via a facade/gateway, while the rest continues to be served by the old system — incrementally "strangling" the legacy system's responsibilities rather than a risky big-bang cutover.
- Prefer this over a full rewrite for any system with real production traffic and business criticality; big-bang rewrites have a well-documented history of running over budget, over time, and often being abandoned partway.

## BDD scenario patterns for microservices-specific behavior

```gherkin
Scenario: Saga compensates a failed downstream step
  Given an order-placement saga has completed the "reserve inventory" step
  When the "charge payment" step fails
  Then the "release inventory" compensating action is triggered
  And the order is marked as failed, not left in an inconsistent partial state

Scenario: Consumer handles a duplicate message idempotently
  Given a message has already been processed successfully
  When the same message is delivered again (at-least-once redelivery)
  Then processing it again produces no duplicate side effect (e.g., no double charge)

Scenario: Service degrades gracefully when a synchronous dependency times out
  Given the recommendation service is unavailable
  When a user loads the product page
  Then the page renders without recommendations rather than failing entirely
```
