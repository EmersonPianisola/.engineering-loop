---
name: init-bdd
id: init.bdd
version: 2.0.0
type: stage
description: 'Full BDD journey mapping. Active only for large+ complexity. Produces detailed user journeys with Gherkin scenarios.'
---

# STAGE: INIT BDD Journey
<!-- ID: init.bdd -->
<!-- Min Complexity: large -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting EXCLUSIVELY as the BDD journey mapper.
- DO NOT transition to architecture or implementation stages.
- The moment you produce the BDD journey document, your task is FINISHED.
- Generating code or architecture artifacts is a CRITICAL VIOLATION.

## Procedure

1. **Prerequisite Check:** If `state.work_item` is null or missing → `status: blocked`, `blocking_condition: work item not validated`. **EXIT.**
2. **Complexity Check:** If `state.complexity < "large"` → `done: true` (deactivated). **SKIP.**
3. **Essence Gate:** Run Essence sidecar validation before proceeding. If Essence fails, adjust inputs and re-validate.
4. Proceed with the steps below.

# BDD Journey — Discovery + Formulation

**Skill:** Self-constructed from BDD best practices (Cucumber, Example Mapping)
**Runs when:** `state.stages.init.bdd.done == false` AND `state.complexity >= "large"`
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
| {name} | unit/integration | high/medium/low |
```

## Execute — Validation

- Every PRD feature → at least one user journey
- Every UX flow → Gherkin scenario coverage
- Every user story → acceptance criteria mapped to scenarios
- Edge cases identified for each journey
- Test types assigned (unit, integration)
- No vague language — all scenarios are testable

## Validate

- All pass → `done = true`. Gaps → `done = false` (loop re-runs).

## State Update Contract

**MANDATORY.** Follow `{reference-root}/sub-agent-contract.md`. Before returning your response:

1. Write all artifacts to their designated paths in `{artifact-root}/`
2. Update `{loop-root}/state.json`:
   - `stages.init.bdd.done = true` (or `false` on failure)
   - `stages.init.bdd.attempts += 1`
   - `stages.init.bdd.artifact_path = "artifacts/..."` (your output path)
   - `stages.init.bdd.error = null` (or failure description)
3. Record AD-NNN decisions in `{loop-root}/STATE.md ## Decisions` (if applicable)
4. Your response MUST be a single JSON line:
   - Success: `{"stage":"init.bdd","status":"done","artifact":"artifacts/..."}`
   - Failure: `{"stage":"init.bdd","status":"failed","error":"reason"}`

DO NOT include artifact content, summaries, or "Next steps" in your response.
