# The Test Pyramid & Test Types

## The pyramid (proportions matter)
```
        /\        E2E / BDD        few   — slow, high-value, whole-system journeys
       /  \
      /----\      Integration      some  — real seams: DB, queue, HTTP, framework
     /      \
    /--------\    Unit            many   — fast, isolated logic; the base
```
Bugs are cheapest to catch at the bottom. Invert the pyramid (mostly e2e) and you get a
slow, flaky, expensive suite that nobody trusts — the "ice-cream cone" anti-pattern.

## Unit tests (the base — most numerous)
- Test one behavior of one unit (function/class) in isolation, no real I/O.
- Fast (milliseconds), deterministic, run on every save/PR.
- **Test behavior, not implementation** — assert outputs/effects, not internal calls, so
  refactors don't break tests that should still pass.
- Cover branches, boundaries, and error paths (mirror the non-happy-path categories from
  `bdd-comprehensive-testing`).

## Integration tests (the middle — fewer)
- Verify the seams: does the code work with the *real* database, cache, message broker, or
  the actual web framework wiring?
- Use real dependencies where feasible (e.g. **Testcontainers** to spin up a real DB in a
  container) rather than mocking the thing you're trying to verify.
- Slower than unit; run in CI, maybe not on every keystroke.

## End-to-end / BDD tests (the top — fewest)
- Exercise a full critical journey through the deployed system.
- These are the Gherkin scenarios owned by `bdd-comprehensive-testing` — don't duplicate
  them; just make sure the critical journeys exist and are stable.
- Keep them few and high-value; they're the slowest and most fragile. Reserve for
  revenue/safety-critical flows.

## Test doubles (use the right one)
- **Stub**: returns canned data. **Mock**: asserts interactions. **Fake**: a working
  lightweight implementation (in-memory DB). **Spy**: records calls.
- **Mock external dependencies, never the unit under test.** Mocking the thing you're
  testing proves nothing. Over-mocking couples tests to implementation and hides real
  integration bugs — prefer fakes/real deps as you go up the pyramid.

## Other useful types (place appropriately)
- **Snapshot tests** — for serialized output/UI; guard against unintended changes, but
  review diffs (blindly updating snapshots defeats them).
- **Smoke tests** — a tiny fast suite run right after deploy to confirm the system is
  basically alive (ties to `release-deployment-safety`).
- **Regression tests** — every fixed bug gets a test so it can't return (often a BDD
  non-happy-path scenario).
- **Golden/characterization tests** — capture existing behavior of legacy code before
  refactoring it.

## What to test where (heuristic)
- Complex business logic / algorithms → unit + property-based.
- Data access, transactions, migrations → integration (real DB).
- Service-to-service APIs → contract tests (see `contract-testing.md`).
- Critical user journeys → BDD/e2e.
- Performance-sensitive paths → load tests (see `load-and-performance-testing.md`).
- Failure handling → chaos/fault injection (see `chaos-engineering.md`).
