---
name: architecture-reviewer
version: 1.0.0
role: design
domain: architecture-review-and-consolidation
stage: architecture > review
description: >
  Evaluates the requirements, cloud architecture, and solution design proposals.
  Identifies gaps, inconsistencies, and conflicts. Produces the consolidated,
  finalized architecture package that the implementation stage consumes as
  binding constraints.
---

# Architecture Reviewer

## Purpose

Evaluate the three architecture proposals (requirements, cloud, solution),
identify gaps and inconsistencies, drive adjustments, and produce the
**final consolidated architecture package** that implementation consumes
as binding constraints.

## Inputs

- `state.artifacts.requirements` — Refined requirements
- `state.artifacts.cloud_architecture` — Cloud architecture
- `state.artifacts.solution_architecture` — Solution design
- `state.work_item` — story/spec being implemented
- `{planning-root}/prd.md` — PRD

## Output

- `{artifact-root}/architectures/consolidated-{slug}.md` — Final architecture package
- Stored in `state.artifacts.consolidated_architecture`

## Document Structure

```markdown
## Consolidated Architecture

### Executive Summary
- Scope of architecture
- Key decisions
- Technology stack summary
- Cost estimate summary

### Requirements Traceability Matrix
| Requirement | Cloud Decision | Solution Decision | Status |
|-------------|---------------|-------------------|--------|
| [PRD section] | [cloud reference] | [solution reference] | covered |

### Architecture Decisions (AD)
- AD-001: [Title]
  - Context: [what problem does this solve]
  - Decision: [what was decided]
  - Consequences: [trade-offs accepted]
  - Source: [cloud | solution | requirements]

### Reconciled Component Map
- [Component] → [AWS Service] → [Technology]
- [Component] → [AWS Service] → [Technology]

### Data Flow Diagrams
(Mermaid diagrams of key user flows through the full stack)

### Open Questions
- [Question] — [blocking | non-blocking] — [resolution owner]

### Deferred Decisions
- [Decision] — [condition to resolve]
```

## Review Phase

### Step 1: Completeness Check

Verify each artifact independently:

**Requirements:**
- [ ] All PRD features covered
- [ ] Volumetry quantified
- [ ] Scalability targets defined
- [ ] Observability requirements specified
- [ ] Security requirements complete

**Cloud Architecture:**
- [ ] All volumetry targets addressed by services
- [ ] VPC design complete
- [ ] Every service has rationale and cost
- [ ] Database strategy complete
- [ ] Deployment pipeline specified
- [ ] Security infrastructure defined
- [ ] Observability infrastructure matches requirements

**Solution Design:**
- [ ] All UX flows have component coverage
- [ ] Data model complete with lifecycle
- [ ] API contracts defined
- [ ] Cross-cutting concerns addressed
- [ ] Performance targets quantified
- [ ] Technology stack justified

### Step 2: Cross-Artifact Consistency

Check for conflicts between artifacts:

| Check | Cloud ↔ Solution | Cloud ↔ Requirements | Solution ↔ Requirements |
|-------|-----------------|---------------------|----------------------|
| Data storage | Database service matches ORM | Database capacity matches volumetry | Data model fits database type |
| Compute | Service matches runtime | Instance size matches concurrency | Component fits compute model |
| Networking | API Gateway matches API contracts | VPC endpoints match service calls | — |
| Caching | ElastiCache matches cache strategy | Cache size matches data volume | Cache TTL matches data lifecycle |
| Security | IAM roles match auth model | Encryption matches data protection | RBAC matches service permissions |
| Observability | CloudWatch matches logging needs | Metrics match observability targets | Error format matches alerting |
| Deployment | Pipeline matches tech stack | Environment matches requirements | — |

### Step 3: Gap Analysis

For every inconsistency or missing coverage:

1. **Classify severity:**
   - `critical` — Blocks implementation (missing data model, no auth strategy)
   - `high` — Significant risk (cost estimate missing, no error handling)
   - `medium` — Should fix (incomplete API contract, missing log format)
   - `low` — Nice to have (missing cost optimization note)

2. **Determine resolution:**
   - `adjust` — One artifact needs correction
   - `rework` — Send back to originating skill for re-execution
   - `defer` — Document in deferred decisions with resolution condition

3. **Execute resolution:**
   - `adjust` → Fix inline, record in findings
   - `rework` → Reset originating sub-stage to `done: false`
   - `defer` → Add to deferred decisions section

### Step 4: Consolidation

Produce the final architecture package:

1. Merge cloud and solution architecture into a unified view
2. Create traceability matrix: every PRD requirement → cloud decision + solution decision
3. Extract Architecture Decisions (AD) with stable IDs
4. Build reconciled component map: component → AWS service → technology
5. Create data flow diagrams for key user flows
6. List open questions and deferred decisions
7. Enforce `max_artifact_size_lines`
8. Store in `state.artifacts.consolidated_architecture`

### Step 5: Final Gate

The architecture stage passes when:

- [ ] Traceability matrix has zero `uncovered` entries
- [ ] No `critical` or `high` findings remain unresolved
- [ ] Cloud and solution artifacts are consistent (no conflicts)
- [ ] Cost summary is complete
- [ ] Security model is complete across both artifacts
- [ ] All `[TBD]` and `[DECIDE LATER]` placeholders resolved or deferred with conditions
- [ ] Consolidated architecture document is produced

## Validation Criteria

- [ ] Every PRD requirement traced to cloud + solution decisions
- [ ] Zero critical/high findings unresolved
- [ ] Cloud and solution artifacts are mutually consistent
- [ ] Consolidated architecture document exists and is complete
- [ ] Architecture decisions have stable AD IDs

## Cross-Stage Reset Behavior

| Finding Severity | Effect |
|-----------------|--------|
| `critical` in requirements | `architecture.requirements.done = false`, `requirements = null` |
| `critical` in cloud | `architecture.cloud.done = false`, `cloud_architecture = null` |
| `critical` in solution | `architecture.solution.done = false`, `solution_architecture = null` |
| `high` in any | Auto-adjust inline, re-validate |
| `medium` in any | Auto-adjust inline, pass |
| `low` in any | Log, pass |
| All clear | `architecture.review.done = true`, `architecture.done = true` |

## High-Confidence Rules

1. **No silent conflicts** — If cloud and solution disagree on anything (database type, auth model, data format), it must be surfaced and resolved.
2. **Traceability is mandatory** — Every PRD requirement must have a cloud decision AND a solution decision. Gaps are critical findings.
3. **Consolidated is the source of truth** — After this stage, implementation reads the consolidated architecture, not the individual artifacts.
4. **AD IDs are stable** — Once assigned, AD IDs never change. This enables downstream traceability.
5. **Defer with conditions** — Every deferred decision must have a specific condition that triggers its resolution (e.g., "resolve when user count exceeds 10K MAU").
