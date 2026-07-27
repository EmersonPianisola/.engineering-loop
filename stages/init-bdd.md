---
name: init-bdd
id: init.bdd
version: 1.0.0
type: stage
description: 'Full BDD journey mapping. Produces detailed user journeys with Gherkin scenarios used as test baseline.'
---

# STAGE: INIT BDD Journey
<!-- ID: init.bdd -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting EXCLUSIVELY as the BDD journey mapper.
- DO NOT transition to architecture or implementation stages.
- The moment you produce the BDD journey document, your task is FINISHED.
- Generating code or architecture artifacts is a CRITICAL VIOLATION.

## Procedure

1. **Prerequisite Check:** If `state.work_item` is null or missing → `status: blocked`, `blocking_condition: work item not validated`. **EXIT.**
2. **Essence Gate:** Run Essence sidecar validation before proceeding. If Essence fails, adjust inputs and re-validate.
3. Proceed with the steps below.

# BDD Journey — Discovery + Formulation

**Skill:** Self-constructed from BDD best practices (Cucumber, Example Mapping)
**Runs when:** `state.stages.init.bdd.done == false`
**Prerequisite:** `init` stage complete (validated work item)

## Design — Journey Discovery

- Input: validated work item + PRD + UX designs + user stories.
- Output: `{artifact-root}/bdd-journeys/journey-{slug}.md`
- Enforce `max_artifact_size_lines`. Store path in `state.artifacts.bdd_journey`.

### Journey Structure

Each user journey follows the BDD three-practice model:

1. **Discovery** — What the system could do (user perspectives, real-world examples)
2. **Formulation** — What the system should do (Gherkin scenarios, structured documentation)
3. **Automation reference** — What the system actually does (test mappings)

### Journey Document Contents

```
## User Journey: {journey-name}

### Actor
- Primary actor, secondary actors, system triggers

### Pre-conditions
- System state before journey begins

### Happy Path
Given {context}
When {action}
Then {outcome}

### Alternative Paths
- Branch A: {scenario}
- Branch B: {scenario}

### Edge Cases
- Empty state
- Error conditions
- Timeout scenarios
- Concurrent actions

### Post-conditions
- System state after journey completion

### Test Mapping
| Scenario | Type | Priority |
|----------|------|----------|
| {name} | e2e/unit/integration | high/medium/low |
```

## Execute — Validation

- Every PRD feature → at least one user journey
- Every UX flow → Gherkin scenario coverage
- Every user story → acceptance criteria mapped to scenarios
- Edge cases identified for each journey
- Test types assigned (e2e, unit, integration, component)
- No vague language — all scenarios are testable

## Validate

- All pass → `done = true`. Gaps → `done = false` (loop re-runs).

## Expected Output

Your final response MUST strictly contain the BDD journey document with all user journeys, Gherkin scenarios, and test mappings. End your generation immediately after the document block. Do not write "Next steps".
