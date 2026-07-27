---
name: architecture
id: architecture
version: 2.0.0
type: stage
description: 'Architecture stages. Requirements (medium+), Solution (medium+), Review (complex). Auto-sized by complexity.'
---

# STAGE: Architecture
<!-- ID: architecture (sub-stages: requirements, solution, review) -->

## Auto-Sizing

| Sub-stage | Min Complexity | Prerequisite |
|-----------|---------------|--------------|
| `arch.requirements` | `medium` | `init` complete |
| `arch.solution` | `medium` | `arch.requirements` complete (if active) |
| `arch.review` | `complex` | requirements + solution complete |

## 🚨 MANDATORY EXECUTION BOUNDARY

Each sub-stage has its own boundary. The orchestrator dispatches them independently.

---

## arch.requirements — Requirements Refinement

**Skill:** `requirements-refiner`
**Runs when:** `state.stages.architecture.requirements.done == false` AND `state.complexity >= "medium"`

### Procedure

1. **Prerequisite Check:** If `state.work_item` is null → `status: blocked`. **EXIT.**
2. **Essence Gate:** Run Essence sidecar validation.
3. **Design:**
   - Input: work item + PRD + brief + UX + architecture spine.
   - Output: `{artifact-root}/architectures/requirements-{slug}.md`
   - Content: Volumetry, scalability, observability, security requirements.
   - Enforce `max_artifact_size_lines`. Store path in `state.artifacts.requirements`.
4. **Decisions:** Record architectural decisions as AD-NNN in STATE.md.
5. **Validate:** All requirements quantified → `done = true`.

---

## arch.solution — Solution Design

**Skill:** `solution-designer`
**Runs when:** `state.stages.architecture.solution.done == false` AND `state.complexity >= "medium"`
**Prerequisite:** `arch.requirements.done == true` (if active)

### Procedure

1. **Prerequisite Check:** If requirements artifact missing (and active) → `status: blocked`. **EXIT.**
2. **Essence Gate:** Run Essence sidecar validation.
3. **Design:**
   - Input: requirements artifact (if exists) + work item + UX + PRD.
   - Output: `{artifact-root}/architectures/solution-{slug}.md`
   - Content: Components, data architecture, API design, cross-cutting concerns.
   - Enforce `max_artifact_size_lines`. Store path in `state.artifacts.solution_architecture`.
4. **Decisions:** Record architectural decisions as AD-NNN in STATE.md.
5. **Validate:** All components designed → `done = true`.

---

## arch.review — Architecture Review

**Skill:** `architecture-reviewer`
**Runs when:** `state.stages.architecture.review.done == false` AND `state.complexity == "complex"`
**Prerequisite:** requirements + solution both `done: true`

### Procedure

1. **Prerequisite Check:** If architecture artifacts missing → `status: blocked`. **EXIT.**
2. **Essence Gate:** Run Essence sidecar validation.
3. **Execute — Cross-Artifact Review:**
   - Input: all architecture artifacts + work item + PRD.
   - Check: internal consistency, gap analysis, dependency conflicts.
   - Output: `{artifact-root}/architectures/consolidated-{slug}.md`
4. **Validate — Triage:**

| Finding Severity | Resets |
|-----------------|--------|
| `critical` in requirements | `arch.requirements.done = false`, `artifacts.requirements = null` |
| `critical` in solution | `arch.solution.done = false`, `artifacts.solution_architecture = null` |
| `high` | Auto-adjust inline, re-validate |
| All clear | `arch.review.done = true` |

5. **Decisions:** Record any review decisions as AD-NNN in STATE.md.

## Expected Output

Your final response MUST strictly contain the architecture artifact for the active sub-stage. End your generation immediately after the artifact block. Do not write "Next steps".
