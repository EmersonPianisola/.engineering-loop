# Quality Gates, Coverage, Mutation & Flaky-Test Management

Tests are only valuable if the suite is *trusted* and *meaningful*. These gates keep it so.

## Coverage (necessary, not sufficient)
- Enforce a coverage threshold, ideally on **changed lines** in a PR (diff coverage) rather
  than only a global number — global % barely moves and hides untested new code.
- Coverage proves code was *executed*, not that it was *asserted correctly*. High coverage
  with weak assertions is false confidence. Don't chase 100%; target meaningful coverage of
  logic and error paths, and don't write tests purely to hit a number.
- Exclude generated code and trivial getters from the metric so it reflects real logic.

## Mutation testing (checks that tests actually assert)
- A mutation tool makes small changes to your code (flip a `<` to `<=`, remove a line) and
  re-runs the tests. If tests still pass, they didn't really test that logic — a "surviving
  mutant."
- Run it on critical/complex modules (not the whole codebase every time — it's slow).
- Tools: Stryker (JS/.NET/Scala), PIT (JVM), mutmut/cosmic-ray (Python).
- Mutation score is a far better signal of test quality than line coverage.

## Property-based testing (finds edge cases you wouldn't pick)
- Instead of hand-picked examples, specify a **property** that must always hold, and the
  tool generates hundreds of random inputs trying to falsify it — then shrinks any failure
  to a minimal reproducer.
- Ideal for: parsers/serializers (round-trip), encoders, math, sorting/collections,
  invariants ("output is always sorted," "decode(encode(x)) == x").
- Tools: fast-check (JS), Hypothesis (Python), jqwik (JVM), FsCheck (.NET), PropEr/QuickCheck.

## Flaky-test management (a flaky suite is a liability)
A test that passes and fails without code changes destroys trust: people re-run until green
and stop reading failures — so real regressions ship. Treat flakiness as a defect.
- **Detect**: track pass/fail history; flag tests that fail intermittently.
- **Quarantine**: move a known-flaky test out of the blocking suite (so it doesn't gate
  merges) but keep it running and **file a ticket to fix or delete it** — quarantine is a
  hospital, not a graveyard.
- **Fix root causes**: usually timing/`sleep` races, test interdependence/shared state,
  real time/random without seeding, network/external calls, or order dependence.
- Make tests **deterministic**: inject clocks, seed randomness, isolate state, avoid real
  network (use fakes), and don't depend on execution order.
- Track a **flaky rate** and drive it toward zero; a green build must mean "good."

## CI gate summary (shared pipeline with bdd-comprehensive-testing)
Fail the build / block merge on:
- Any failing unit/integration/BDD/contract test.
- Diff coverage below threshold.
- (On critical modules) mutation score below threshold.
- (On perf-sensitive changes) load-test threshold breach.
Publish readable reports for each so failures are diagnosable from the CI UI.

## Test-suite health metrics worth tracking
- Total suite runtime (keep the fast feedback loop fast; parallelize/shard if it creeps up).
- Flaky rate. Diff-coverage trend. Mutation score on critical modules.
