# The discrimination (mutation) gate

The discrimination gate is the mechanical heart of this skill. It answers one question for every
check at once: *"if this check silently stopped detecting anything, would any test notice?"* If
the answer is no for even one check, the build is blocked.

## The idea

Mutation testing, applied to your checks instead of your product code. The simplest, most
general mutation of any check is to **replace it entirely with a no-op that always passes**
(exit 0). A faithful test for that check asserts something that depends on the check actually
detecting a violation — so against the no-op, that assertion must **fail**. If the test still
passes against a check that does nothing, the test proves nothing about detection: it is
**vacuous**, and a genuinely broken check would ship green behind it.

So the gate requires: **for every check, its test must fail when the check is a no-op.** A test
that stays green is the defect.

## The algorithm

```
for each check that is expected to have a test (i.e. not on the shrink-only allowlist):
    save the check's real source
    overwrite the check with a no-op stub that exits 0
run the whole check-test suite ONCE
restore every check from its saved source        # always, even on error (finally)
for each check:
    if its test(s) PASSED against the no-op:      # vacuous — the failure it should catch didn't happen
        report it and fail the gate
if any vacuous test was found: exit non-zero
else: exit 0 with evidence ("N checks, each test fails when its check is a no-op")
```

Key properties, each of which matters:

- **Run the suite once, not per-mutant.** No-opping *all* checks together and running the suite a
  single time is dramatically cheaper than mutating one check at a time, and it's sufficient: a
  test is mapped to the check(s) it exercises, so a test that stays green is vacuous regardless of
  what the other stubs did. (You can escalate to per-check mutation later if a check's test
  touches several checks; for the no-op mutant it's rarely needed.)

- **Restore in a `finally`.** The gate mutates real files on disk. It **must** restore them even
  if the runner throws, is killed, or a test hangs. Save original contents first; restore in a
  `finally`. In CI this runs on an ephemeral checkout so a crash is harmless anyway, but a local
  run must never leave a developer's checks stubbed. Document the one-line repair
  (re-checkout the checks directory) in case a hard kill still slips through.

- **Fail closed.** If the gate can't find the checks directory, the test directory, the
  allowlist, or a check it expected a test for, it exits non-zero — never a silent pass. A gate
  that guards quality must itself refuse to pass when it can't do its job.

- **Map tests to checks honestly.** Decide which test file corresponds to which check by a stable
  convention: the test references the check's path (e.g. it spawns `path/to/check`), and the gate
  reads that reference. A test that passes a *no-op*'s path is still mapped to that check — that's
  the point. Don't credit a check whose "test" never actually runs it.

- **This gate is itself a check.** It's code that can rot, so it needs its own test — but it is a
  *mutation-testing job*, not a scanning check, so it's exempt from the coverage gate's
  "must-exec-a-check" rule and instead proven by (a) unit tests of its fail-closed paths against
  throwaway fixtures, and (b) its own required run on the real repository. Note this exemption
  explicitly so no one "fixes" it by adding a circular test.

## Wiring it in

- Make it a **blocking** CI check (in the required set that must be green to merge). Its cost is
  one extra run of the check-test suite — put it in its own job so it parallelizes.
- Run it **after** the coverage gate, or alongside it: coverage proves a test *exists and execs
  the check*; discrimination proves that test *asserts detection*. You need both — one without the
  other is half a guarantee.

## Proving it yourself in one line
You don't need the whole gate to sanity-check a single check: break its detection by hand (change
its core pattern to match nothing, or invert its condition) and run its committed test. It must go
**red**. If it stays green, the test is fake — fix the test. Restore the check. This is the same
proof the gate automates for everyone, forever.

## What it deliberately does not do
- It does not prove the check's fixture is *complete* (that it covers every violation shape) — only
  that the test depends on the check detecting *something*. Faithful-fixture discipline (see
  `check-test-patterns.md`) covers breadth; the mutation gate covers non-vacuity.
- It does not replace human/adversarial review of whether a check guards the *right* thing. It
  guarantees the check you wrote can fail; it can't tell you that you wrote the check you needed.
