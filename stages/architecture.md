---
name: architecture
id: architecture
version: 1.0.0
type: stage
description: 'Mandatory gate. Sub-stages: requirements → cloud → solution → review.'
---

# STAGE: Architecture (Requirements → Cloud → Solution → Review)
<!-- ID: architecture -->

## Procedure
# Architecture Stage — Mandatory Gate

Sub-stages execute sequentially. Loop does not advance to `impl.design` until all are `done: true`.

## Sub-Stage: Requirements

1. **Prerequisite Check:** If `state.artifacts.requirements` is null or missing → `status: blocked`, `blocking_condition: requirements artifact not produced`. **EXIT.**
2. **Essence Gate:** Run Essence sidecar validation before proceeding. If Essence fails, adjust inputs and re-validate.
3. Proceed with the steps below.

**Skill:** `requirements-refiner`
**Runs when:** `state.stages.architecture.requirements.done == false`
**Constraint:** `max_arch_requirements_attempts` (default: 2)

### 🚨 BOUNDARY
- Act EXCLUSIVELY as `requirements-refiner`. Do not produce cloud, solution, or implementation artifacts.
- Generating implementation code (`yaml`, `json`, `python`, `go`) is a CRITICAL VIOLATION.

### Design
- Input: work item + BMad planning artifacts (PRD, brief, UX, architecture spine).
- Output: `{artifact-root}/architectures/requirements-{slug}.md`
- Content: Functional requirements, volumetry, scalability targets, observability, security.
- Enforce `max_artifact_size_lines`. Store path in `state.artifacts.requirements`.
- Essence: `references/essence-sidecar.md`
- **Decisions:** MUST include `## Decisions` section at end of artifact. Record each architectural decision with rationale, alternatives considered, and consequences. Follow MADR template from `{reference-root}/decision-template.md`.

### Execute — Validation
- Every PRD feature → detailed user journeys
- Volumetry quantified (users, data, traffic, storage)
- Scalability targets (horizontal, vertical, burst)
- Observability (logging, metrics, tracing, alerting, health checks)
- Security requirements complete
- No vague language
- **Decisions recorded:** `## Decisions` section present with rationale for each decision

### Validate
- All pass → `done = true`. Gaps → `done = false` (loop re-runs).

## Sub-Stage: Cloud

1. **Prerequisite Check:** If `state.artifacts.cloud_architecture` is null or missing → `status: blocked`, `blocking_condition: cloud architecture artifact not produced`. **EXIT.**
2. **Essence Gate:** Run Essence sidecar validation before proceeding. If Essence fails, adjust inputs and re-validate.
3. Proceed with the steps below.

**Skill:** `cloud-architect`
**Runs when:** `state.stages.architecture.cloud.done == false` AND `state.artifacts.requirements` not null
**Constraint:** `max_arch_cloud_attempts` (default: 2)

### 🚨 BOUNDARY
- Act EXCLUSIVELY as `cloud-architect`. Do not produce solution design or implementation artifacts.

### Design
- Input: `state.artifacts.requirements` + work item + PRD.
- Output: `{artifact-root}/architectures/cloud-{slug}.md`
- Content: AWS topology, service mapping, data storage, deployment, security, observability, cost.
- Enforce `max_artifact_size_lines`. Store path in `state.artifacts.cloud_architecture`.
- Essence: `references/essence-sidecar.md`
- **Decisions:** MUST include `## Decisions` section at end of artifact. Record each infrastructure decision with rationale, alternatives considered, and consequences. Follow MADR template from `{reference-root}/decision-template.md`.

### Execute — Validation
- Every volumetry target → addressed by a service
- VPC design (CIDR, subnets, security groups)
- Every AWS service: rationale, configuration, cost estimate
- Database (backup, scaling, multi-AZ)
- Deployment pipeline, security, observability, cost summary
- **Decisions recorded:** `## Decisions` section present with rationale for each infrastructure decision

### Validate
- All pass → `done = true`. Gaps → `done = false`.

## Sub-Stage: Solution

1. **Prerequisite Check:** If `state.artifacts.solution_architecture` is null or missing → `status: blocked`, `blocking_condition: solution architecture artifact not produced`. **EXIT.**
2. **Essence Gate:** Run Essence sidecar validation before proceeding. If Essence fails, adjust inputs and re-validate.
3. Proceed with the steps below.

**Skill:** `solution-designer`
**Runs when:** `state.stages.architecture.solution.done == false` AND `state.artifacts.requirements` not null
**Constraint:** `max_arch_solution_attempts` (default: 2)

### 🚨 BOUNDARY
- Act EXCLUSIVELY as `solution-designer`. Do not produce implementation blueprints or code.

### Design
- Input: `state.artifacts.requirements` + work item + UX designs + PRD.
- Output: `{artifact-root}/architectures/solution-{slug}.md`
- Content: Component design, data architecture, API contracts, cross-cutting concerns, performance, tech stack.
- Enforce `max_artifact_size_lines`. Store path in `state.artifacts.solution_architecture`.
- Essence: `references/essence-sidecar.md`
- **Decisions:** MUST include `## Decisions` section at end of artifact. Record each design decision with rationale, alternatives considered, and consequences. Follow MADR template from `{reference-root}/decision-template.md`.

### Execute — Validation
- Every UX flow → component and data path coverage
- Data model with entity lifecycle
- API contracts (request/response schemas)
- Error handling, caching, auth, i18n
- Performance targets quantified, tech stack justified
- **Decisions recorded:** `## Decisions` section present with rationale for each design decision

### Validate
- All pass → `done = true`. Gaps → `done = false`.

## Sub-Stage: Review

1. **Prerequisite Check:** If `state.artifacts.consolidated_architecture` is null or missing → `status: blocked`, `blocking_condition: consolidated architecture not produced`. **EXIT.**
2. **Essence Gate:** Run Essence sidecar validation before proceeding. If Essence fails, adjust inputs and re-validate.
3. Proceed with the steps below.

**Skill:** `architecture-reviewer`
**Runs when:** `state.stages.architecture.review.done == false` AND all three prior sub-stages done
**Constraint:** `max_arch_review_attempts` (default: 2)

### 🚨 BOUNDARY
- Act EXCLUSIVELY as `architecture-reviewer`. Review and consolidate only — do not implement.

### Design — Cross-Artifact Review
- Input: all three architecture artifacts + work item + PRD.
- Completeness check per artifact.
- Cross-artifact consistency (cloud ↔ solution, cloud ↔ requirements, solution ↔ requirements).
- Gap analysis with severity classification.
- Essence: `references/essence-sidecar.md`
- **Decisions:** Consolidate all decisions from requirements, cloud, and solution artifacts. Resolve conflicts. Record review decisions with rationale. Follow MADR template from `{reference-root}/decision-template.md`.

### Execute — Resolution
- `critical` → reset originating sub-stage to `done: false`, clear artifact.
- `high` → auto-adjust inline, re-validate.
- `medium/low` → auto-adjust inline, log.
- Produce: `{artifact-root}/architectures/consolidated-{slug}.md`
- Store path in `state.artifacts.consolidated_architecture`.

### Validate — Final Gate
- Traceability matrix: zero `uncovered` entries
- No `critical` or `high` findings unresolved
- Cloud and solution mutually consistent
- Consolidated architecture complete
- All `[TBD]` and `[DECIDE LATER]` resolved or deferred with conditions
- **Decisions consolidated:** All decisions from sub-stages merged, conflicts resolved, rationale documented
- All pass → `done = true`. Failures → `done = false`.

## Cross-Stage Resets

See `references/exit-conditions.md` → Architecture Review Resets.


## Expected Output
Your final response MUST strictly contain the architecture artifact for the current sub-stage (requirements document, cloud architecture, solution design, or consolidated architecture with findings). End your generation immediately after the artifact block. Do not write "Next steps".
