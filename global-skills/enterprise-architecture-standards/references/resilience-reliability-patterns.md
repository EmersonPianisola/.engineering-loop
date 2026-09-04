# Resilience & Reliability Patterns

Covers: Circuit breaker, retry with backoff/jitter, bulkhead, timeouts, rate limiting, graceful degradation, idempotency, disaster recovery (RTO/RPO), chaos engineering.

## Core principle
In any system with more than one component (which is any system calling a database, another service, or a third-party API), assume every call can fail, be slow, or hang — and design explicitly for that, rather than treating failure as an unhandled exceptional case. Reliability is a design property, not something patched in after the first outage.

## Timeouts
- Every network call (HTTP, database, queue, cache) must have an explicit timeout — a call with no timeout can hang indefinitely, and under load, hung calls exhaust thread pools/connection pools and take down the whole service, not just the one slow dependency.
- Set timeouts based on the actual expected latency of the dependency plus a reasonable margin, not an arbitrarily large "safe" number — an overly generous timeout still lets one slow dependency degrade the whole system, just more slowly.

## Retry with backoff and jitter
- Retry transient failures (network blips, momentary 503s) but never retry blindly and immediately — use exponential backoff (each retry waits longer than the last) with jitter (randomized variance) to avoid a "thundering herd" where every failed client retries at the exact same moment and overwhelms the recovering service again.
- Only retry idempotent operations safely by default (see idempotency below) — retrying a non-idempotent operation (e.g., "charge the card") without an idempotency mechanism can cause duplicate side effects.
- Cap the total number of retries and the total time spent retrying; a request that ultimately fails should fail within a bounded time, not retry indefinitely while the caller waits.

## Circuit breaker
- Track failure rate for calls to a given dependency; when failures exceed a threshold, "open" the circuit and fail fast (without even attempting the call) for a cooldown period, instead of letting every request pile up waiting on a timeout against a dependency that's already down.
- After the cooldown, allow a small number of "trial" requests through (half-open state) to check if the dependency has recovered before fully closing the circuit again.
- This protects the calling service's own resources (threads, connections) from being exhausted by a dependency that's failing, and gives the failing dependency room to recover instead of being hammered by retries from every caller.

## Bulkhead
- Isolate resource pools (thread pools, connection pools) per dependency so that one slow/failing dependency can't exhaust resources needed to serve requests that don't depend on it — named after ship bulkheads that contain flooding to one compartment.
- Example: if a service calls both a fast internal cache and a slow third-party API, give them separate connection pools so the slow third-party dependency backing up doesn't starve the cache calls of available connections too.

## Rate limiting & load shedding
- Rate-limit both inbound requests (protect the service from being overwhelmed by a caller, malicious or accidental) and outbound calls to dependencies with known capacity limits (protect a downstream dependency from being overwhelmed by you).
- Under genuine overload, shed load deliberately (reject the least important requests, e.g., non-critical background reports) rather than letting every request degrade equally into failure — decide in advance what's most critical to keep serving.

## Graceful degradation
- Identify, per feature, what the acceptable degraded behavior is if a non-critical dependency is unavailable (e.g., render the page without the recommendations widget rather than failing the whole page load; show cached/stale data with an indicator rather than an error). Design this explicitly rather than letting a non-critical dependency's failure become an all-or-nothing outage for the whole user-facing feature.
- Distinguish critical dependencies (the request genuinely cannot succeed without them — e.g., payment processing for a checkout) from non-critical ones (recommendations, "recently viewed," analytics tracking) and treat their failure differently in code.

## Idempotency
- Design any operation that could plausibly be retried (client retry, network retry, at-least-once message delivery) to be safe to execute more than once with the same effect as executing it once.
- Common mechanism: an idempotency key supplied by the caller (or derived from the request), checked against a store of recently processed keys before executing the operation — if the key's already been processed, return the prior result instead of re-executing the side effect.
- This matters most for anything with an external side effect: payments, sending an email/SMS, creating a resource that shouldn't be duplicated.

## Disaster recovery: RTO & RPO
- Define, per system, the **Recovery Time Objective** (how long can this be down before it's unacceptable) and **Recovery Point Objective** (how much data loss, measured in time, is acceptable — "we can lose up to 5 minutes of writes" vs. "we can lose up to 24 hours") — these numbers should come from an actual business conversation about impact, not be assumed.
- Back these numbers with real mechanisms: RPO is achieved through backup frequency/replication strategy; RTO is achieved through failover automation and tested runbooks, not just a hope that someone will figure it out during an actual incident.
- Actually test disaster recovery procedures periodically (restore a backup, fail over to a secondary region) rather than trusting an untested runbook — an unexercised DR plan commonly fails at the exact moment it's needed, for reasons a live test would have caught (an expired credential in the backup process, a runbook step that references a system that no longer exists, etc.).

## Chaos engineering
- For systems where reliability is genuinely business-critical, deliberately and safely inject failure (kill a service instance, add latency, simulate a dependency outage) in a controlled way (starting in non-production, graduating to production with safeguards) to verify that the resilience patterns above actually work as designed, rather than assuming they do because the code looks right.
- Treat findings from chaos experiments the same as any other discovered reliability gap — fix and add regression coverage (a BDD scenario simulating the failure mode, see `bdd-comprehensive-testing`), don't just note it and move on.

## BDD scenario patterns

```gherkin
Scenario: Circuit breaker opens after repeated failures and fails fast
  Given the payment gateway has failed the last 10 consecutive requests
  When another request is made
  Then the circuit breaker rejects it immediately without calling the gateway
  And the response indicates a temporary unavailability rather than hanging

Scenario: Retry uses exponential backoff and does not exceed the retry limit
  Given a downstream call fails transiently
  When the client retries
  Then each retry waits longer than the previous one
  And the client stops retrying after the configured maximum attempts

Scenario: Duplicate payment request with the same idempotency key is not double-charged
  Given a payment request with idempotency key "abc123" has already succeeded
  When the same request is submitted again with the same key
  Then no second charge occurs
  And the original result is returned

Scenario: Non-critical dependency failure degrades gracefully
  Given the recommendations service is unavailable
  When a user loads the product page
  Then the page loads successfully without the recommendations section
```
