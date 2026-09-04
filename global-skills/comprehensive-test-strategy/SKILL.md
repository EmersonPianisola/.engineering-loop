---
name: comprehensive-test-strategy
description: Use for EVERY feature, service, or system to decide and implement the FULL testing strategy beyond behavioral BDD — the test pyramid (unit, integration, end-to-end), consumer-driven contract testing between services, load/performance/stress testing, chaos/resilience testing, coverage and mutation-testing quality gates, property-based testing, and flaky-test management. Complements bdd-comprehensive-testing (which owns Gherkin behavioral scenarios) by covering the other ~70% of a real test strategy. Trigger proactively on "tests," "testing," "coverage," "load test," "performance test," "contract test," "integration test," "e2e," "chaos," "flaky," "test strategy," or any code that other code or services depend on — even without those words.
---

# Comprehensive Test Strategy

## Why this exists

BDD scenarios prove a feature *behaves* correctly, but that's roughly a third of what
elite teams test. They also verify the units in isolation, that services don't break each
other's contracts, that the system holds up under load, that it degrades gracefully when
infrastructure fails, and that the test suite itself is trustworthy (fast, deterministic,
meaningfully covering the code). This skill owns that broader strategy so "we have tests"
means "we have the *right* tests at the right levels," not just a pile of end-to-end
checks.

This skill is the companion to `bdd-comprehensive-testing`. That skill owns the
Gherkin/behavioral layer and wires the suite into CI; this skill decides the *full mix* of
test types and adds the ones BDD doesn't cover. Use them together — don't duplicate the
behavioral scenarios here.

## The core principle

**Test at the lowest level that can catch the bug, and match the test type to the risk.**
Fast, isolated tests for logic; a smaller number of integration tests for the seams;
fewer, high-value end-to-end/BDD tests for critical journeys; plus specialized tests
(contract, load, chaos) for the risks that unit tests can't see. A suite that's all
end-to-end is slow, flaky, and expensive; a suite that's all unit misses integration and
scale failures.

## The workflow

### Step 1: Design the test mix for the change (the pyramid)

Read `references/test-pyramid-and-types.md`. Decide the right proportion:

- **Unit tests** (most numerous) — pure logic, fast, no I/O, one behavior each.
- **Integration tests** (fewer) — real seams: DB, cache, queue, the actual framework wiring.
- **End-to-end / BDD tests** (fewest) — critical user journeys through the whole system.
  These are the Gherkin scenarios from `bdd-comprehensive-testing`; don't rewrite them here.

Add the specialized layers below based on what the change touches. Not every change needs
every layer — but actively decide, don't default to "a couple of unit tests."

### Step 2: If the change crosses a service boundary → contract testing

Read `references/contract-testing.md`. When a service calls another service (or a frontend
calls an API), add **consumer-driven contract tests** (e.g. Pact) so a provider can't ship
a breaking change without a failing test — without the two teams having to run a full
integrated environment. This is how big orgs keep hundreds of services from breaking each
other. Ties to `release-deployment-safety` backward-compatibility.

### Step 3: If the change is on a hot path or has scale requirements → performance testing

Read `references/load-and-performance-testing.md`. Add:
- **Load test** — expected traffic; confirm SLO latency/throughput hold.
- **Stress test** — beyond expected, to find the breaking point and confirm it fails
  gracefully.
- **Soak test** — sustained load over hours to catch leaks/degradation.
- **Spike test** — sudden surge, to validate autoscaling/backpressure.
Establish a baseline and run performance tests in CI (or nightly) to catch regressions.
Feed results into capacity planning (`sre-operational-readiness` if present).

### Step 4: If the system has real availability requirements → chaos / resilience testing

Read `references/chaos-engineering.md`. Deliberately inject failure (kill an instance, add
latency, sever a dependency, exhaust a resource) and verify the system degrades gracefully
and recovers — validating the resilience patterns (timeouts, retries, circuit breakers,
fallbacks) from `enterprise-architecture-standards`. Start small, in staging, with a
hypothesis and a blast-radius limit.

### Step 5: Enforce quality gates so the suite stays trustworthy

Read `references/quality-gates-and-flaky-tests.md`. Configure CI to:
- Enforce a **coverage threshold** on changed code (and don't game it — coverage is
  necessary, not sufficient).
- Consider **mutation testing** on critical modules to check tests actually *assert*, not
  just execute.
- Use **property-based testing** for logic with large input spaces (parsers, serializers,
  math, invariants) to find edge cases you wouldn't hand-pick.
- **Quarantine and fix flaky tests** — a flaky suite that people re-run until green is
  worse than no suite, because it trains the team to ignore failures.

### Step 6: Wire everything into CI/CD (shared with bdd-comprehensive-testing)

The pipeline runs the pyramid on every PR (fast tests first, fail fast), contract tests on
change, and heavier load/chaos suites on a schedule or pre-release gate. Reuse the CI setup
from `bdd-comprehensive-testing`'s `ci-cd-wiring` rather than building a parallel one. Every
test type publishes a readable report; the build fails on real failures and blocks merge.

### Step 7: Confirm the strategy before calling it done

- [ ] Logic covered by unit tests at the lowest useful level
- [ ] Seams (DB/queue/external) covered by integration tests
- [ ] Critical journeys covered by BDD/e2e (from the BDD skill)
- [ ] Cross-service boundaries covered by contract tests (if applicable)
- [ ] Performance validated against SLOs (if hot path / scale requirement)
- [ ] Resilience validated by fault injection (if availability matters)
- [ ] Coverage gate passes; no known flaky tests left unquarantined
- [ ] All of it runs in CI and blocks merge on failure

## What the big engineering orgs do that this encodes

- A deliberate **test pyramid**, not an ice-cream-cone of slow e2e tests.
- **Consumer-driven contracts** so independent teams deploy without integrated staging
  gridlock.
- **Continuous performance testing** with baselines, so regressions are caught before users.
- **Chaos engineering** in production-like environments to prove resilience instead of
  assuming it.
- Ruthless **flaky-test hygiene** — a trusted green build is a prerequisite for continuous
  delivery.

## Reference files

| Topic | File |
|---|---|
| Test pyramid, unit/integration/e2e, test doubles, what to test where | `references/test-pyramid-and-types.md` |
| Consumer-driven contract testing (Pact), provider verification, versioning | `references/contract-testing.md` |
| Load / stress / soak / spike testing, baselines, tooling, CI perf gates | `references/load-and-performance-testing.md` |
| Chaos engineering, fault injection, game days, resilience validation | `references/chaos-engineering.md` |
| Coverage + mutation + property-based testing, flaky-test management, CI gates | `references/quality-gates-and-flaky-tests.md` |
