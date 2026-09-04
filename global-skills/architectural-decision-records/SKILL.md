---
name: architectural-decision-records
description: The single source of truth for capturing architectural decisions. Use for EVERY feature, service, endpoint, schema change, framework/library choice, integration, infrastructure change, or refactor an agent builds or modifies — no such change is "done" until an Architectural Decision Record (ADR) is written and committed alongside the code. Produces MADR-format records by default (Nygard lightweight for trivial decisions), auto-detecting or establishing the repo's ADR directory and sequential numbering. Trigger PROACTIVELY whenever the user asks to build, add, implement, design, choose, adopt, migrate, refactor, or change anything architectural — a new service, "which database should we use," "let's switch to gRPC," "add caching," "split this into microservices," a new API contract, an auth model — even when they never say the words "ADR," "decision record," "documentation," or "why." If a change would make a future engineer ask "why was it built this way?", it needs an ADR, and this skill governs how.
---

# Architectural Decision Records (ADRs)

## Why this skill exists

Code shows *what* the system does. It almost never shows *why* it was built that way — why Postgres over DynamoDB, why events instead of synchronous calls, why this auth model, why the retry budget is 3. That "why" is the single most expensive thing to reconstruct later. When it's lost, teams re-litigate settled questions, quietly violate constraints they don't know exist, and rip out load-bearing decisions because nobody recorded the forces behind them.

An ADR captures one architecturally-significant decision: the context and forces at play, the options considered, the option chosen, and the consequences accepted. Written at the moment of decision — when the reasoning is fresh and cheap to record — it becomes the durable source of truth that survives re-orgs, rewrites, and the departure of everyone who was in the room.

This skill treats ADRs as non-optional, the same way `enterprise-architecture-standards` treats sound architecture and `owasp-secure-coding-bdd` treats security. A feature without its decision record is unfinished work, not finished work missing a nicety. Hold that line — but hold it by *doing the ADR as part of the task*, quietly and well, not by lecturing the user about process.

## The core rule

Every architecturally-significant change ships with an ADR in the same unit of work (same PR / same commit series) as the code. "Architecturally-significant" is broad on purpose — see the significance test below — but it is not *everything*. Fixing a typo, tuning a log line, or renaming a local variable does not need an ADR. The judgment call is: **would a competent engineer arriving in six months ask "why was this done this way?" and be materially helped by a recorded answer?** If yes, write the ADR. If genuinely no, skip it silently.

When in doubt, lean toward writing one. A three-minute Nygard-format record is cheap; a lost decision is not.

## Significance test — does this change need an ADR?

Write an ADR when the change involves any of:

- **Structure**: a new service/module/component, splitting or merging services, a new bounded context, a significant layering or dependency-direction choice.
- **Data**: choosing or changing a datastore, a schema design with real trade-offs, a data-ownership or consistency model (strong vs eventual), a partitioning/sharding strategy, a migration approach.
- **Integration & contracts**: a new or changed API contract, sync vs async communication, a messaging/eventing pattern, a public interface other teams depend on, a versioning strategy.
- **Cross-cutting choices**: auth/authz model, caching strategy, concurrency/locking model, error-handling and retry policy, idempotency approach, multi-tenancy model.
- **Technology selection**: adopting or replacing a framework, library, protocol, runtime, or major dependency — especially anything hard to reverse later.
- **Operational shape**: deployment topology, rollout/rollback strategy that constrains the design, SLO-driven design choices, significant build-vs-buy decisions.

You can skip the ADR for reversible, low-stakes, mechanical work: cosmetic refactors, formatting, dependency patch bumps with no behavior change, copy edits, purely local implementation details that impose no constraint on anyone else.

If a task bundles several significant decisions (e.g. "build the notifications service" → datastore choice + delivery model + retry policy), prefer **one ADR per decision** over one giant ADR. Small, focused, individually-supersedable records are the whole point of the format.

## Workflow for every qualifying change

Fold these steps into how the feature gets built — the ADR is part of the deliverable, not a separate ceremony afterward.

1. **Locate or establish the decision log.** Detect the repo's existing ADR home before inventing one. Check, in order: `docs/adr/`, `docs/decisions/`, `doc/adr/`, `adr/`, `architecture/decisions/`, and any `.adr-dir` marker file. If one exists, match its exact location, filename pattern, numbering width, and template style — consistency with what's there beats your personal default. If none exists, create `docs/adr/` and add a short `README.md` explaining the convention (there's a ready-made one in `assets/adr-readme.md`). See `references/workflow.md` for the full detection and setup procedure.

2. **Assign the next number.** ADRs are sequentially numbered with zero-padded four-digit ids: `0001`, `0002`, …. The next number is one above the highest existing id in the log (not the file count — deleted/superseded records still consumed their number). The helper script `scripts/new_adr.sh` computes this and scaffolds the file for you; use it rather than counting by hand.

3. **Pick the template.** Default to **MADR** (`references/madr-template.md`) — it forces you to record decision drivers, the options you *didn't* pick, and the consequences of the one you did, which is exactly the reasoning that's expensive to reconstruct. Drop to the **Nygard lightweight** format (`references/nygard-template.md`) only for decisions that are real but small, where the full options analysis would be ceremony. When unsure, use MADR. Read the template file before writing so the section structure is exact.

4. **Write the record.** Fill every section with specifics, not placeholders. The bar is set in `references/writing-guide.md` — read it; the difference between a useful ADR and a useless one is entirely in the quality of Context, Decision Drivers, and Consequences. Name at least two genuinely considered options (an ADR with one option is a decision with no visible alternatives, which reads as unconsidered). State the consequences you're *accepting*, including the bad ones — an ADR that lists only upsides is not trusted.

5. **Set status and links.** New records are usually `accepted` (or `proposed` if the team still needs to ratify). If this decision reverses or replaces an earlier one, set the old ADR's status to `superseded by ADR-NNNN` and link both directions — the log's value is that the chain of reasoning stays traceable. Never silently edit or delete a past ADR to reflect a new decision; supersede it. ADRs are immutable once accepted, correctable only by a new ADR.

6. **Commit with the code.** The ADR lands in the same commit or PR as the change it explains, so the record and the reality can never drift apart. Reference the ADR id in the PR description and, where natural, in code comments at the point the decision shows up (`// datastore choice: see ADR-0007`).

7. **Verify before calling it done.** Part of finishing the feature is confirming the ADR exists, is numbered correctly, has no unfilled `{placeholders}`, names ≥2 options (if MADR), records real consequences, and is staged alongside the code. `scripts/check_adr.sh` runs these checks; treat a failure as a blocker exactly like a failing test.

## How this pairs with the other skills

This skill answers **"why did we decide this?"**. It sits naturally alongside:

- `enterprise-architecture-standards` — designs the *what* and *how*; its significant choices are precisely what you record here.
- `owasp-secure-coding-bdd` — a security-model decision (auth approach, trust boundary, crypto choice) is an architectural decision; capture it as an ADR *and* as `@security` scenarios.
- `bdd-comprehensive-testing` — the ADR's "Confirmation" section can point at the Gherkin scenarios or ArchUnit-style fitness functions that keep the code honest to the decision.
- `release-deployment-safety` / `sre-operational-readiness` — rollout, migration, and SLO-driven design choices are ADR-worthy; link the ADR from the runbook.

When several of these apply to one feature, produce all their artifacts together. The ADR is the connective tissue: it references the tests that confirm it, the security scenarios it implies, and the operational plan it constrains.

## Quick reference

- **Default format**: MADR. **Fallback**: Nygard, for small-but-real decisions.
- **Location**: match the repo's existing ADR dir; else create `docs/adr/`.
- **Filename**: `NNNN-kebab-case-title.md`, e.g. `0007-use-postgres-for-billing.md`.
- **Numbering**: zero-padded, sequential, monotonic, never reused.
- **Statuses**: `proposed` → `accepted` → (`deprecated` | `superseded by ADR-NNNN`). `rejected` for options a `proposed` ADR turned down.
- **Immutable**: never rewrite an accepted ADR to change its decision — supersede it with a new one.
- **One decision per ADR**: split bundled decisions into separate records.

## Bundled resources

- `references/workflow.md` — full log-detection, numbering, and setup procedure; edge cases (monorepos, existing non-standard logs, retrofitting a repo with none).
- `references/writing-guide.md` — what makes each section good vs useless, with a worked before/after example.
- `references/madr-template.md` — the MADR long-form template (default).
- `references/nygard-template.md` — the Nygard lightweight template (fallback).
- `references/lifecycle.md` — statuses, superseding, deprecation, and how to handle reversals.
- `scripts/new_adr.sh` — scaffold the next-numbered ADR from a template.
- `scripts/check_adr.sh` — verify an ADR is complete and well-formed before commit.
- `assets/adr-readme.md` — drop-in README for a freshly created `docs/adr/` directory.

## Credits and attribution

This skill is built on the Architectural Decision Record practice stewarded by
the ADR community at https://adr.github.io/. Specifically:

- The ADR concept originates with Michael Nygard, "Documenting Architecture
  Decisions" (2011).
- The default long-form format is MADR (Markdown Any Decision Records) —
  https://adr.github.io/madr/.
- The lightweight format follows Nygard's original template.

The templates and lifecycle guidance here are adapted from that community's
work. Credit to the ADR GitHub organization and its contributors.
