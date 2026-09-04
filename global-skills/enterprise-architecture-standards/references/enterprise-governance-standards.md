# Enterprise Governance & Engineering Standards

Covers: Architecture Decision Records, non-functional requirements, technical debt tracking, documentation standards, definition of done.

## Architecture Decision Records (ADRs)
- For any decision with real long-term consequences (a new service boundary, a database technology choice, a major library/framework adoption, an API contract other teams will build against, a significant pattern change), write a short ADR rather than letting the reasoning live only in chat history, a Slack thread, or one person's memory.
- Minimal ADR format — keep it short enough that it actually gets written and read:

  ```markdown
  # ADR-00X: <short title>

  ## Status
  Proposed / Accepted / Superseded by ADR-00Y

  ## Context
  What problem are we solving, and what constraints apply (team size, timeline, existing systems)?

  ## Decision
  What we're doing.

  ## Alternatives considered
  What else we looked at, and why we didn't choose it.

  ## Consequences
  What this makes easier, what it makes harder, and what we're explicitly accepting as a tradeoff.
  ```

- Store ADRs in version control alongside the code they affect (commonly `docs/adr/` or `architecture/decisions/`), numbered sequentially, never deleted — a superseded decision is marked superseded and linked to its replacement, not removed, since the history of *why* something changed has real value later.
- Revisit an ADR's stated consequences honestly when circumstances change significantly (major scale change, a new regulatory requirement) rather than treating the original decision as permanently settled regardless of context — write a new ADR that supersedes the old one rather than silently drifting away from a documented decision without saying so.

## Non-functional requirements (NFRs)
- Make non-functional requirements explicit and specific before or during design, not implicit assumptions discovered after the fact: expected load (requests/sec, data volume, concurrent users), latency targets (tie to SLOs, see `observability-operations.md`), availability target, data retention/compliance requirements, expected growth over a defined horizon (e.g., 12-24 months, not "eventually").
- Treat NFRs as real requirements with the same weight as functional ones when making architecture decisions — "it should scale" and "it should be secure" are not actionable NFRs; "supports 10,000 concurrent users at p95 < 200ms" and "meets the relevant OWASP checklist for this attack surface" are.

## Technical debt tracking
- Distinguish deliberate, documented technical debt (a known shortcut taken consciously to meet a deadline, with a plan to address it) from accidental debt (a design that just turned out to be wrong, or a shortcut nobody flagged) — the deliberate kind is a legitimate engineering tool when it's tracked and paid down; both kinds are a problem when they're invisible.
- Track technical debt as real backlog items (not just a "TODO" comment buried in code that nobody sees again), with enough context that someone other than the original author can understand and prioritize it later: what was skipped, why, and what the risk/cost of leaving it unaddressed is.
- Revisit tracked debt on a regular cadence (not only when it causes an incident) — debt that's tracked but never actually revisited provides the appearance of governance without the substance of it.

## Documentation standards
- Every service/component should have a discoverable README covering: what it does, how to run it locally, how to deploy it, its key dependencies, and where to find its ADRs/architecture docs, its BDD feature index (see `bdd-comprehensive-testing`), and its runbooks for common operational tasks.
- Keep architecture diagrams (system context, container/component diagrams — C4 model is a reasonable default) up to date as the system evolves; an architecture diagram that no longer matches reality is worse than no diagram, since it actively misleads whoever relies on it next.
- Document the "why" for non-obvious decisions at the point of use (a comment near a workaround explaining the constraint that forced it, linking to the relevant ADR) rather than only in a separate document nobody reads while working in that part of the code.

## Definition of done
For a feature/change to be considered complete at an enterprise standard, it should satisfy all of:
- [ ] Meets the functional requirement as specified
- [ ] Has full happy-path and non-happy-path BDD coverage, stored permanently and indexed (`bdd-comprehensive-testing`)
- [ ] Has passed a threat-modeling pass for its actual attack surface, with `@security` scenarios covering the relevant risks (`owasp-secure-coding-bdd`), including the lockout-prevention check if it touches permissions/access/deletion
- [ ] Fits the system's established architecture (or the deviation is a deliberate, documented decision — an ADR, not a silent workaround)
- [ ] Meets its stated non-functional requirements (performance, scalability, reliability) or has an explicit, accepted tradeoff documented if it doesn't yet
- [ ] Is observable in production (relevant logs/metrics/traces exist, and a meaningful health/readiness signal reflects its actual dependency state)
- [ ] Is documented sufficiently for someone other than the author to operate and extend it
- [ ] Runs in CI/CD with all of the above enforced as automated gates, not manual checklist items trusted to memory

This definition of done is the practical synthesis of everything in this skill and its two companions (`bdd-comprehensive-testing`, `owasp-secure-coding-bdd`) — treat "done" as meaning all of this, not just "the happy path works on my machine."
