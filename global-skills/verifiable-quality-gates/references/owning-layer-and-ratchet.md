# Prove at the owning layer; delete dead monitors; ratchet to zero

Two disciplines that keep a check *corpus* honest, beyond any single check's test.

## Prove an invariant at the layer that owns it

Before you add a check, ask: **who already enforces this invariant?** Many invariants are already
owned by something closer to the data than a CI script:

- a **database constraint or trigger** makes a bad row impossible to write,
- a **type** makes a bad value impossible to construct,
- a **service boundary / API contract** makes a bad call impossible to issue.

When an owner like that exists, the invariant should be **proven at that owner** — a test sitting
next to the constraint/trigger/type/boundary that exercises it directly — and you should **not**
add a separate CI check that re-detects the same fact from further away. A second, weaker checker
of a guarantee something else owns is the classic *"two owners of one guarantee"* smell:

- it **drifts** — the owner and the monitor evolve apart, and now they disagree about the rule;
- it is often **unwired** — bolted on "for safety" but running in no pipeline, so it verifies
  nothing while *looking* like protection;
- it is often **untestable** — only the live system could trigger it, so its own detection is
  unproven (and a skip-only test for it is vacuous — see `check-test-patterns.md`).

### The move: delete the monitor, prove the owner

A worked example of the general pattern:

> A CI script scanned a production datastore for rows in a forbidden shape and failed the build if
> it found any. But a **database trigger already rejected those rows at write time**, the script
> **ran in no pipeline**, and it could only detect against a live populated datastore (so it was
> untestable in CI without one). It was a third, weaker, after-the-fact layer over an invariant the
> trigger already owned.
>
> **Fix:** delete the script; add a test **next to the trigger** (in the database test suite that
> runs on schema changes) that inserts a forbidden row and asserts the trigger drops it, and inserts
> a valid row and asserts it is kept (the *kept* assertion is what makes the test discriminate —
> neutralize the trigger and it flips red). The invariant ends up **more** verified than before —
> behaviorally, on every relevant change, at its owning layer — and one piece of dead, redundant,
> unprovable code is gone.

This is an architecturally-significant decision (you removed a control and relocated its proof) —
record it as an ADR (see `architectural-decision-records`), stating the owner, why the monitor was
redundant, and where the proof now lives.

### Delete dead code, don't keep it on life support
Do **not** invent a test-only seam (see `check-test-patterns.md`) *just* to make a redundant or
unwired monitor pass the coverage gate — that adds surface area to preserve code that guards
nothing. Seams are for checks that are **real and needed but merely infrastructure-gated**. When a
check is redundant or dead, the honest state is "there is no such check," not "there is an
untestable one behind an exception." A check that runs in no pipeline is not a safety net.

**Decision rule:**
- Real, needed, infra-gated → give it a **test-only seam** and a discriminating test.
- Redundant with an owning layer, and/or unwired/dead → **delete it**, prove the invariant at its
  owner, and record the ADR.

## The shrink-only ratchet (getting an existing corpus to zero)

Retrofitting tests onto an existing pile of checks can't be a flag day. Use a **shrink-only
allowlist** — a file listing the checks that predate the "every check has a discriminating test"
rule:

- The **coverage gate** treats any check **not** on the allowlist as required to have a test, so a
  brand-new untested check fails immediately — the corpus can't get *worse*.
- Each allowlisted check is burned down one at a time: write its faithful, discriminating test,
  prove it with the mutation gate, then **remove** its name from the allowlist.
- Enforce **shrink-only**: entries may be removed, never added. A code check on the allowlist file
  itself (or a review rule) rejects any diff that adds a name. This makes the system tighten
  **monotonically** — every merge leaves it the same or better, and "zero" is reached by attrition
  without ever blocking work on unrelated changes.

When the allowlist reaches empty, delete it (or keep it empty as a tripwire): every check now has a
committed test that provably discriminates, enforced on every future change.

## Why this is foundational, not bureaucratic
The combination — coverage gate + discrimination gate + prove-at-the-owning-layer + shrink-only
ratchet — makes a specific bad outcome **structurally impossible**: a check cannot silently rot to
a false green, because the moment its detection stops working, its committed test stops failing
against the no-op mutant, and the discrimination gate goes red. That guarantee holds for every
future change and every future author automatically, with no reliance on anyone remembering to
re-verify. That is the difference between a convention (which is skipped exactly when under
pressure) and a mechanical gate (which is not).
