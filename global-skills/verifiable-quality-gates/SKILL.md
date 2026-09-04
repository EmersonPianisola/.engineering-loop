---
name: verifiable-quality-gates
description: "When you write, review, or rely on an automated check — a CI guard, custom lint rule, schema/config validator, or architecture fitness function: make it provably detect what it claims. Every check gets a committed test that FAILS when the check is neutralized (proven mechanically by a mutation gate), fails closed, and proves each invariant at the layer that owns it. Triggers on: adding/changing a CI check or guard, a check that 'passes' but might not be catching anything, a green build you don't fully trust, making quality gates self-proving."
---

# Verifiable Quality Gates — prove your checks actually detect

## Why this exists

A quality gate is only worth the failures it catches. But a gate is *code* — a regex, a
threshold, a query, a walk over files — and code silently stops working. Someone tightens a
pattern and it now matches nothing; a refactor inverts a condition; a data source moves and the
check quietly reads empty. The gate keeps exiting `0`. The build stays green. And the exact
violation it was built to stop sails through — invisibly, because *nothing announces that a
check went blind*.

This is the most dangerous failure in a CI system, because it inverts the signal you trust
most: a green check now means "the check ran," not "the thing it guards is true." Test suites
have a name for a test that asserts nothing — **vacuous** — and a whole discipline (mutation
testing) for catching them. This skill applies that same discipline to the checks *themselves*.

The rule is simple and absolute: **a check you have never proven can detect a violation is not
protection — it is theater.** Every automated check must be provably able to fail for the right
reason, and that proof must be mechanical, so it holds for every future change and every future
author — not a one-time manual demo that rots.

## The core rule

> Every automated check has a committed test that runs the **real** check end-to-end and
> **discriminates**: the test must **fail** when the check is replaced by a no-op. A test that
> still passes against a do-nothing check asserts nothing about detection — it is vacuous, and
> it means a *broken* check would ship green.

Two mechanical gates enforce this, and they are themselves ordinary checks (yes — they guard
each other):

1. **Coverage gate** — every check has a committed test that execs it. (See
   `scripts/check-has-test.mjs`.)
2. **Discrimination gate** — a mutation test: replace each check with a no-op and require its
   test to fail. (See `scripts/verify-check-discrimination.mjs`.)

## The workflow — for every check you add, change, or inherit

### 1. Write the check to fail closed and emit evidence
Before worrying about its test, make the check honest:
- **Fail closed.** A missing input, an internal error, an empty scan, or a zero-file match must
  exit **non-zero** — never a silent `exit 0`. "I found nothing to check" and "I checked and
  everything passed" are different outcomes and must have different exit codes. The most common
  false-green bug is a check that skips itself into a pass.
- **Emit evidence on success.** Print *what* was inspected and *how much* (counts, paths), so a
  passing run is auditable — "OK — 214 files scanned, 0 violations" not just "OK."
- **No error-swallowing.** No `exit 0` inside a `catch`, no returning a pass on a thrown
  exception. A check that can't run must say so and fail, not shrug and go green.

### 2. Write a committed test that runs the REAL check end-to-end
Not a unit test of an extracted helper — **execute the actual check** (spawn it, or invoke its
entrypoint) against fixtures, and assert its **exit code / reported result**. Testing an
extracted predicate in isolation proves the predicate, not the check that ships; the wiring
between them is exactly where checks go blind. Keep the real invocation in the test. See
`references/check-test-patterns.md` for faithful-fixture patterns (including checks rooted at
their own file location, which need a copy-into-fixture approach, and checks gated on a live
database/API/network, which need a test-only input seam).

Cover, at minimum:
- **the happy path** → passes (exit 0),
- **each distinct real violation** → fails (non-zero), with a fixture that reproduces the check's
  *actual* pattern — not a contrived trigger,
- **fail-closed paths** → missing input and zero-scan both fail,
- **any escape hatch** the check honors → passes.

### 3. Prove the test DISCRIMINATES (do not skip — this is the whole point)
A test that execs the check but asserts nothing tied to detection would let a broken check ship
green. Prove it can't, mechanically:

> Replace the check with a no-op that always passes. Run its test. **The test must fail.** If it
> still passes, the test is vacuous — fix the test, not the check.

Do this for *every* check at once with a mutation gate (`scripts/verify-check-discrimination.mjs`):
it stubs each check to a no-op, runs the check-test suite, and requires every check's test to go
red. Any test that stays green is reported and blocks the merge. This converts "we think our
checks work" into a deterministic, every-PR guarantee. See `references/mutation-gate.md`.

### 4. Prove each invariant at the layer that OWNS it — don't stack blind monitors
Before adding a check, ask **who already enforces this?** If a database constraint or trigger, a
type, or a service boundary already makes the bad state impossible, prove the invariant *there*
(a test next to that owner), and do **not** add a separate after-the-fact monitor that re-checks
the same fact from further away. A second, weaker checker of a guarantee something else owns is
the "two owners of one guarantee" smell — it drifts, and worse, it's often **unwired** (runs
nowhere) or **untestable** (only a live system could trigger it), so it provides confidence
without protection. Delete dead and redundant checks; a check that runs in no pipeline is not a
safety net, it's a comment that lies. See `references/owning-layer-and-ratchet.md`.

### 5. Ratchet, don't big-bang
Retrofitting existing checks with tests takes time. Use a **shrink-only allowlist** of checks
that predate the requirement: the coverage gate blocks any *new* untested check immediately,
while the backlog is burned down entry by entry. Names may only be **removed** from the
allowlist (once a real, discriminating test exists), never added. This makes the system tighten
monotonically without demanding a flag day. See `references/owning-layer-and-ratchet.md`.

## Definition of done for a check
- [ ] Fails closed (missing input / internal error / zero-scan → non-zero) and prints evidence on success.
- [ ] Has a committed test that execs the real check and asserts its exit code.
- [ ] That test reproduces the check's real violation (faithful fixture) and covers fail-closed paths.
- [ ] The test **discriminates** — proven by the mutation gate (no-op the check → its test fails).
- [ ] The invariant isn't already owned elsewhere (else it's proven there and this check is deleted).
- [ ] The coverage + discrimination gates are wired into CI as **blocking** checks.

## How this pairs with the other skills
- **`comprehensive-test-strategy`** owns mutation testing of your *application* code; this skill
  applies the same idea one level up — to the *checks and gates* that guard the code. They're
  complementary: one proves the product works, the other proves the guards that prove the product.
- **`judge-arch` / `arch-encode`** turn caught mistakes into mechanical gate rules; this skill is
  how you keep *those* gates honest — an `arch-encode` rule you never proved can detect is the
  same theater as any other unproven check.
- **`architectural-decision-records`** — deleting a redundant monitor in favor of proving an
  invariant at its owning layer is an architecturally-significant decision; record it as an ADR
  (see the worked example in `references/owning-layer-and-ratchet.md`).

## Bundled resources
- `references/mutation-gate.md` — how to build the discrimination (mutation) gate: the no-op
  mutant, running the check-test suite, requiring failure, restoring safely, failing closed.
- `references/check-test-patterns.md` — writing faithful, discriminating check-tests: fixtures,
  checks rooted at their own location (copy-into-fixture), test-only seams for
  database/API/network-gated checks, and how a coverage gate "credits" a test.
- `references/owning-layer-and-ratchet.md` — prove-at-the-owning-layer, deleting dead/redundant
  monitors, and the shrink-only allowlist ratchet.
- `scripts/check-has-test.mjs` — dependency-free reference coverage gate (every check has a
  committed test that execs it; shrink-only allowlist).
- `scripts/verify-check-discrimination.mjs` — dependency-free reference mutation gate (no-op each
  check, require its test to fail).
- `assets/verifiable-gates.config.example.json` — example configuration for both engines.
