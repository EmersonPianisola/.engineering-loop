# Consumer-Driven Contract Testing

## The problem it solves
In a system of many services (or a frontend + API), a provider can ship a change that
silently breaks a consumer. Full integrated end-to-end environments to catch this are slow,
flaky, and don't scale to hundreds of services. **Contract tests** let each side verify the
integration *independently*, in fast unit-test-speed runs.

## How it works (Pact-style, consumer-driven)
1. **Consumer** writes a test describing exactly the requests it makes and the responses it
   expects. Running it produces a **contract** (a "pact" file) — the consumer's real
   expectations, not a hand-written doc.
2. The contract is shared with the provider (via a **Pact Broker** or a shared artifact).
3. **Provider** runs **provider verification**: replays the contract against the real
   provider and confirms it can satisfy every consumer expectation.
4. If a provider change would break a consumer, provider verification fails *in the
   provider's own CI* — before deploy, without an integrated environment.

## Why "consumer-driven"
The contract reflects what consumers *actually use*, so providers know exactly what they
can and can't change. A provider can freely change anything no consumer depends on.

## Where it fits
- REST/HTTP APIs between services, and frontend ↔ backend.
- Message/event contracts (async) — Pact and others support message pacts: the producer
  guarantees the message shape the consumer expects.
- Complements, doesn't replace, the provider's own functional tests.

## Versioning & safe deploys
- Tag contracts with consumer/provider versions and environments in the broker.
- Use **can-i-deploy** checks: before deploying a provider, verify it's compatible with all
  consumer versions currently in the target environment. This directly enforces the
  backward-compatibility rule in `release-deployment-safety`.

## Tooling
Pact (multi-language: JS, JVM, .NET, Python, Go, Ruby), Spring Cloud Contract (JVM). Wire
provider verification and can-i-deploy into the CI pipeline shared with
`bdd-comprehensive-testing`.

## Good practices
- Keep contracts focused on structure and semantics the consumer relies on — not exhaustive
  data values (that's the provider's functional tests).
- Don't let contracts become a second copy of the API spec maintained by hand — they should
  be generated from real consumer tests.
- Contract tests verify *compatibility*, not correctness of business logic — keep both.

## Example flow in CI
```
Consumer CI:  run consumer tests → publish pact to broker (tagged with branch/version)
Provider CI:  fetch pacts → run provider verification → publish results
Deploy gate:  can-i-deploy --pacticipant provider --version <sha> --to-environment prod
```
