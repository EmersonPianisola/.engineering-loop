---
stage: design.personas
skill: bmad-personas
min_complexity: large
---

# Design > Personas & Journey Maps
<!-- Min Complexity: large — deactivated for small/medium -->

Personas & journey maps procedure.

## Activation

- Sources: research findings, PRD, `{workflow.external_sources}`.
- Elicit: user segments, motivations, goals, pain points, context of use.

## Discovery

1. Review research findings and PRD.
2. Identify user segments, motivations, goals, pain points.
3. Create personas per segment: bio, goals, frustrations, behaviors, quote.
4. Build named-protagonist journey maps with climax beat.

## Finalize

- Output: `personas.md`, `journey-maps.md`.
- Gate: each major user segment from research has a persona; journeys cover all key flows.
- State: `done: true` when personas and journey maps are documented.

## State Update Contract

**MANDATORY.** Follow `{reference-root}/sub-agent-contract.md`. Before returning your response:

1. Write all artifacts to their designated paths in `{artifact-root}/`
2. Update `{loop-root}/state.json`:
   - `stages.design.personas.done = true` (or `false` on failure)
   - `stages.design.personas.attempts += 1`
   - `stages.design.personas.artifact_path = "artifacts/..."` (your output path)
   - `stages.design.personas.error = null` (or failure description)
3. Record AD-NNN decisions in `{loop-root}/STATE.md ## Decisions` (if applicable)
4. Your response MUST be a single JSON line:
   - Success: `{"stage":"design.personas","status":"done","artifact":"artifacts/..."}`
   - Failure: `{"stage":"design.personas","status":"failed","error":"reason"}`

DO NOT include artifact content, summaries, or "Next steps" in your response.
