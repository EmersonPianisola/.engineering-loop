# ADR lifecycle: statuses, superseding, and reversals

## Statuses

- **proposed** — written, not yet ratified. Use when the team still needs to agree. The decision isn't binding yet.
- **accepted** — the decision is in force. Most ADRs an agent writes alongside shipping code are born `accepted`, because writing the code *is* the ratification.
- **rejected** — an option that a `proposed` ADR explicitly turned down, or a proposal the team declined. Rejected ADRs are kept, not deleted — knowing what was rejected and why is as valuable as knowing what was chosen.
- **deprecated** — the decision no longer applies but nothing specific replaced it (e.g. the component it governed was removed).
- **superseded by ADR-NNNN** — a newer decision replaces this one. Link forward to the replacement.

## The immutability principle

An accepted ADR is a historical record of what was decided and why, at a point in time. **Do not rewrite it to reflect a new decision.** If the reasoning changes, the correct move is always a *new* ADR that supersedes the old one. This keeps the chain of reasoning auditable: a reader can follow how thinking evolved rather than seeing only the current state with no history.

The only edits permitted to an accepted ADR are: fixing typos, fixing broken links, and updating its `status` line to `deprecated` or `superseded by …` when that happens.

## How to supersede

When a new decision reverses or replaces an earlier one:

1. Write the new ADR normally, with the next number. In its Context, reference what it changes and why the earlier decision no longer holds.
2. Edit the **old** ADR's status to `superseded by ADR-NNNN` (the new id) and add a link to it. Leave the rest of the old ADR untouched.
3. In the new ADR, link back: "Supersedes ADR-MMMM."

Both directions matter — someone landing on either record can navigate to the other.

## Reversals mid-flight

If a `proposed` ADR is discussed and the team picks a different option, you don't need a supersede chain — just update that ADR: mark the chosen option in Decision Outcome, or set the ADR `rejected` and write the one that won. Supersession is for decisions that were *accepted and acted upon*, then later changed.

## Confirmation / fitness functions

The strongest ADRs say how the decision will be *kept true* over time, not just asserted once. In the Confirmation section, point at whatever enforces it: an ArchUnit test, a dependency-cruiser rule, a lint rule, a CI gate, a `@security` BDD scenario, a schema check. A decision with an automated fitness function rarely rots; one without tends to erode silently. When the codebase already uses the paired testing/security skills, wire the ADR's confirmation to those artifacts.
