# Writing faithful, discriminating check-tests

A check-test runs the **real check** against controlled inputs and asserts its result. This file
collects the patterns that keep such tests faithful (they reproduce the check's real detection)
and creditable (a coverage gate can confirm they actually exec the check).

## The shape

```
const CHECK = resolve(REPO, "path/to/your-check")      // a LOCAL constant naming the real check

function run(cwd, env = {}) {                           // spawn the real check; return its exit code
  try { execFileSync(runtime, [CHECK], { cwd, env, stdio: "pipe" }); return 0 }
  catch (e) { return e.status ?? 1 }
}

test("passes clean input",        () => expect(run(fixtureWith(GOOD))).toBe(0))
test("FLAGS the real violation",  () => expect(run(fixtureWith(BAD))).toBe(1))   // discriminating
test("fails closed on no input",  () => expect(run(emptyFixture)).toBe(1))
test("real project passes",       () => expect(run(REPO)).toBe(0))
```

Two things make this creditable by a coverage gate: the check is named by a **local constant
resolved to its real path**, and the test **spawns that path**. A coverage gate looks for exactly
that — a test that hands the real check's path to an exec. Keep the spawn in the test file; if you
factor it into a shared helper, keep the *path constant and the exec call* in the test so crediting
still sees them.

## Faithful fixtures — reproduce the REAL violation

The violation fixture must trip the check's *actual* detection, so that removing the check's
detection flips the test from fail to pass (that's what makes it discriminate). Anti-patterns:

- ❌ A fixture that fails for an incidental reason (a syntax error, a missing file) rather than the
  pattern the check hunts — it stays red even against a no-op-adjacent change, so it doesn't
  discriminate on the *real* logic.
- ❌ Asserting only the happy path (`→ 0`). That is the textbook vacuous test: it passes against a
  no-op check. Every check-test needs at least one **non-zero** case tied to real detection.
- ✅ A fixture that contains exactly the shape the check forbids (the real regex match, the real
  duplicate key, the real forbidden import), minimal but genuine.

Cover the distinct violation classes the check recognizes, plus the fail-closed exits (missing
input, zero-scan), plus any escape hatch (a suppression comment, an allowed exception) → passes.

## Rooting: cwd-relative vs. self-located checks

How a check finds *what it scans* determines how you point a fixture at it.

- **cwd-relative checks** resolve their targets against the current working directory (e.g. they
  read `./config` or walk `./src`). Steer them by running the real check with `cwd` set to a
  throwaway fixture directory you populated. Simple and preferred.

- **self-located checks** resolve their targets relative to *their own file location* (the check
  computes paths from where the check file sits, so it always scans the real project no matter the
  cwd). A fixture cwd won't move them. Use **copy-into-fixture**: read the real check's source and
  write a copy into `<fixture>/path/to/check`, then run the *copy* so its self-relative paths land
  inside the fixture. Crucially, still run the **real** check (via the local path constant) for the
  "real project passes" case, so the coverage gate credits the real file — and so the mutation gate,
  which no-ops the real file, also neutralizes the copy your violation test makes (keeping that test
  discriminating).

## Test-only seams for checks gated on a database / API / network

Some checks can only detect against live infrastructure — a query against a real database, a call
to an external API, a fetch over the network. In CI without that infrastructure they *skip*, and a
skip-only test is vacuous (it passes against a no-op too). Don't leave such a check untestable, and
don't invent a monitor just to have something to test — instead give the check a **test-only input
seam**:

```
const FIXTURE = process.env.MY_CHECK_FIXTURE     // set ONLY by tests; never in prod/CI
const rows = FIXTURE
  ? JSON.parse(readFileSync(FIXTURE, "utf8"))     // injected inputs → real detection logic runs
  : await queryTheLiveSystem()                    // untouched production path
// ...the check's real diff/threshold/coverage logic runs on `rows` either way...
```

Rules that keep a seam honest:
- **Inert in production.** The seam activates only when its env var is set, which prod/CI never do.
  With it unset, the check's path is byte-for-byte the original — verify this in review.
- **Feed inputs, not verdicts.** The seam supplies the *data* the live system would have returned
  (the rows, the response); the check's real comparison/threshold/coverage logic still runs and is
  what the test exercises. A seam that injects the *answer* tests nothing.
- **Still fails closed.** An empty or malformed injected input must hit the same fail-closed exit as
  a broken live query would. A missing/garbled fixture file should throw and exit non-zero — loud,
  never a false green.
- **Name it consistently.** Use one recognizable prefix for all such seams so reviewers can grep
  them and confirm none are referenced by production config.

This is the right tool when the detection logic is genuinely valuable and the check is real but
merely infrastructure-gated. When the check is instead *redundant* with an invariant something else
already owns, prefer deleting it and proving the owner — see `owning-layer-and-ratchet.md`.

## Checklist for one check-test
- [ ] Names the real check via a local path constant and spawns it (creditable).
- [ ] At least one violation fixture reproduces the check's real pattern and asserts non-zero (discriminating).
- [ ] Covers each distinct violation class, fail-closed (missing input, zero-scan), and any escape hatch.
- [ ] For self-located checks: copy-into-fixture for violations, real check for the pass case.
- [ ] For infra-gated checks: a test-only seam that is inert in prod and feeds inputs, not verdicts.
