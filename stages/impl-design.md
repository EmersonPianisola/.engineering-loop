---
name: impl-design
id: impl.design
version: 1.0.0
type: stage
description: 'Implementation blueprint. File structure, contracts, data flows, execution order.'
---

# STAGE: Implementation Design
<!-- ID: impl.design -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting EXCLUSIVELY as the `implementation-architect` skill.
- DO NOT write implementation code. DO NOT transition to impl.code or test stages.
- The moment you produce the blueprint, your task is FINISHED.
- Generating implementation code is a CRITICAL VIOLATION.

## Procedure

1. **Prerequisite Check:** If `state.artifacts.consolidated_architecture` is null or missing → `status: blocked`, `blocking_condition: consolidated architecture not produced`. **EXIT.**
2. **Essence Gate:** Run Essence sidecar validation before proceeding. If Essence fails, adjust inputs and re-validate.
3. Proceed with the steps below.

# Implementation Design — Blueprint

**Skill:** `implementation-architect`
**Runs when:** `state.stages.impl.design.done == false`
**Prerequisite:** `state.artifacts.consolidated_architecture` not null

## Design

- Input: `state.artifacts.consolidated_architecture` as binding constraint.
- Output: `{artifact-root}/blueprints/blueprint-{slug}.md`
- Content: Architecture decisions, file responsibilities, data flows, interface contracts, execution order, error handling.
- Enforce `max_artifact_size_lines`. Store path in `state.artifacts.blueprint`.
- Essence: `references/essence-sidecar.md`
- **Decisions:** MUST include `## Decisions` section at end of blueprint. Record each implementation decision with rationale, alternatives considered, and consequences. Follow MADR template from `{reference-root}/decision-template.md`.

### Blueprint Structure

```
## File Structure
- Directory layout
- File responsibilities

## Interface Contracts
- Request/response schemas
- Function signatures
- Event payloads

## Data Flows
- User action → component → service → database
- Async flows (queues, webhooks)

## Execution Order
- Task 1: {description} → {files}
- Task 2: {description} → {files}

## Error Handling
- Error types
- Recovery strategies
- User-facing error messages

## Cross-Cutting Concerns
- Logging, caching, auth, i18n

## Decisions
| ID | Category | Decision | Rationale |
|----|----------|----------|-----------|
| ADR-XXX | code | {Decision} | {Rationale} |
```

## Execute — Validation

- Every architecture decision → reflected in blueprint
- Every component → file responsibility assigned
- Every API contract → request/response schema defined
- Execution order → dependencies resolved (no circular)
- Error handling → all failure paths covered
- **Decisions recorded:** `## Decisions` section present with rationale for each implementation decision

## Validate

- All pass → `done = true`. Gaps → `done = false` (loop re-runs).

## Expected Output

Your final response MUST strictly contain the implementation blueprint document. End your generation immediately after the blueprint block. Do not write "Next steps".
