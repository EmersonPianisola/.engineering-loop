---
name: init-refine
id: init.refine
version: 1.0.0
type: stage
description: 'Phase 0.75: Iterative refinement of ad-hoc work items. Absorb → analyze → propose → iterate → lock.'
---

# STAGE: INIT.REFINE (Phase 0.75)

## 🚨 EXECUTION BOUNDARY
- You are acting EXCLUSIVELY as the idea refinement engine.
- DO NOT transition to any loop stage (architecture, impl, test, review).
- This stage exists ONLY to refine the work item until it is concrete enough for BDD mapping.
- Generating implementation code or architecture artifacts is a CRITICAL VIOLATION.

## Procedure

# INIT.REFINE — Iterative Refinement Loop

## Purpose

Transform a raw user idea into a concrete, actionable work item. This stage runs when `state.work_item_type == "ad-hoc"`.

## Early Exit

Refinement is now performed inline during the init stage (Phase 0.5: Ideation).
This stage exists for documentation only — mark done immediately and proceed.

- Set `state.stages.init.refine.done = true`.
- EXIT.

## Refinement Loop

1. **Load current work item** from `state.work_item`.
2. **Run essence validation** (Four Lenses) on the current work item:
   - Lens 1: Identify subjective/ambiguous terms
   - Lens 2: Surface hidden assumptions
   - Lens 3: Flag literal traps
   - Lens 4: Detect conflicting priorities
3. **Propose refinements**:
   - For each Lens 1-3 finding: rewrite the affected section with concrete language
   - For each Lens 4 finding: present options to the user
   - Add missing sections: `edge_cases`, `non_goals`, `success_metrics`
4. **Present to user**:
   - Show the refined work item
   - Ask: "Should we adjust X, or is this accurate?"
5. **User response**:
   - If adjustments requested → go to step 2 with updated work item
   - If confirmed → proceed to Phase 1 (Skill Discovery)
   - If 5 iterations reached → proceed with current state
6. **On confirmation**:
   - Set `state.work_item_type = "confirmed"`.
   - Set `state.stages.init.refine.done = true`.

## Success Criteria

- Work item has a clear `title`, `intent`, `acceptance_criteria`, and `scope`
- No ambiguous language remains (or ambiguities are documented with decisions)
- All edge cases relevant to the idea are captured
- Non-goals are explicitly stated

## Anti-Patterns

- **Never assume the user's intent** — always present refinements for confirmation
- **Never skip essence validation** — every refinement must be checked for clarity
- **Never proceed with a vague work item** — if the user's idea is too abstract, propose breaking it into smaller work items
