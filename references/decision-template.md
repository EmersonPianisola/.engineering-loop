---
name: decision-template
id: decision-template
version: 1.0.0
type: reference
description: 'ADR template based on MADR (Markdown Architectural Decision Records) v4.0. Categories align with C4 Model levels.'
---

# Decision Template (MADR-based)

Every stage that produces architectural or implementation decisions MUST record them using this template. The template follows the [MADR v4.0](https://adr.github.io/madr/) standard, adapted for Engineering Loop artifacts.

## Category Structure

Decisions are organized by C4 Model level:

| Category | C4 Level | Examples |
|----------|----------|----------|
| `context` | C1 — System Context | Tech stack, deployment model, external integrations |
| `container` | C2 — Container | Service boundaries, data stores, communication protocols |
| `component` | C3 — Component | Module boundaries, API contracts, data models |
| `code` | C4 — Code | Framework choices, library selections, coding patterns |
| `process` | Cross-cutting | CI/CD, testing strategy, security, observability |

## ADR Template

Each decision record follows this structure:

```markdown
---
status: "{proposed | accepted | deprecated | superseded by ADR-NNNN}"
date: "{YYYY-MM-DD}"
category: "{context | container | component | code | process}"
decision_makers: "{role or name}"
consulted: "{roles consulted, if any}"
informed: "{roles informed, if any}"
---

# {Short title — representative of solved problem and found solution}

## Context and Problem Statement

{Describe the context and problem in 2-3 sentences. What requirement or constraint
drove this decision? What was the trade-off space?}

## Decision Drivers

* {driver 1 — e.g., performance requirement, team skill set, cost constraint}
* {driver 2}
* ...

## Considered Options

* {Option 1 name}
* {Option 2 name}
* {Option 3 name}
* ...

## Decision Outcome

Chosen option: "{Option 1}", because {justification — e.g., only option meeting
k.o. criterion | resolves force {X} | came out best in evaluation}.

### Consequences

* Good, because {positive consequence}
* Bad, because {negative consequence or trade-off accepted}
* ...

## Pros and Cons of the Options

### {Option 1 name}

* Good, because {argument}
* Bad, because {argument}

### {Option 2 name}

* Good, because {argument}
* Bad, because {argument}
```

## Recording Decisions in Stage Artifacts

Each stage artifact (architecture, blueprint, etc.) MUST include a `## Decisions`
section at the end. This section lists the decisions made during that stage using
the condensed format:

```markdown
## Decisions

| ID | Category | Decision | Rationale |
|----|----------|----------|-----------|
| ADR-001 | context | Use Firebase over AWS | Team familiarity, faster time-to-market, real-time sync native |
| ADR-002 | container | Firestore over PostgreSQL | Schemaless for flexible vehicle profiles, real-time listeners |
```

Full ADR records go into the decision log produced by the `doc.decisions` stage.

## Decision Log File

The `doc.decisions` stage produces `{artifact-root}/decision-log-{slug}.md` with:

```markdown
# Decision Log

**Project:** {project name}
**Generated:** {date}
**Source:** Engineering Loop run {run_id}

## Index

| ID | Category | Title | Status | Stage |
|----|----------|-------|--------|-------|
| ADR-001 | context | Use Firebase over AWS | accepted | arch.cloud |
| ADR-002 | container | Firestore over PostgreSQL | accepted | arch.solution |
| ... | ... | ... | ... | ... |

---

## ADR-001: Use Firebase over AWS

{Full MADR record}

---

## ADR-002: Firestore over PostgreSQL

{Full MADR record}
```

## Guidelines

1. **One decision per ADR** — each record captures a single, atomic decision.
2. **Rationale over description** — focus on "why", not "what".
3. **Immutable** — never edit an accepted ADR. Create a new ADR to supersede.
4. **Categorize by C4 level** — use the category that matches the architectural level.
5. **Cross-reference** — link related ADRs using `superseded by ADR-NNNN`.
6. **Keep it lean** — an ADR should be readable in under 2 minutes.
