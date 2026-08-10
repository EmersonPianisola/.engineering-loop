---
stage: design.interaction
skill: bmad-interaction
min_complexity: large
---

# Design > Interaction
<!-- Min Complexity: large — deactivated for small/medium -->

Interaction design procedure (patterns, component behaviors, motion).

## Activation

- Sources: wireframes, IA, personas, journeys.
- Elicit: interaction patterns, component behaviors, motion principles, accessibility requirements.

## Discovery

1. Review wireframes, IA, personas, and journeys.
2. Define interaction patterns (named patterns with states, triggers, transitions).
3. Specify component behaviors (behavioral specs per component).
4. Define motion spec (transitions, easing, duration).

## Finalize

- Output: `interaction-patterns.md`, `component-behaviors.md`, `motion-spec.md`.
- Gate: every IA surface maps to ≥1 interaction pattern; states cover normal/error/empty/loading; accessibility floor defined.
- State: `done: true` when interaction artifacts are documented.

## State Update Contract

**MANDATORY.** Follow `{reference-root}/sub-agent-contract.md`. Before returning your response:

1. Write all artifacts to their designated paths in `{artifact-root}/`
2. Update `{loop-root}/state.json`:
   - `stages.design.interaction.done = true` (or `false` on failure)
   - `stages.design.interaction.attempts += 1`
   - `stages.design.interaction.artifact_path = "artifacts/..."` (your output path)
   - `stages.design.interaction.error = null` (or failure description)
3. Record AD-NNN decisions in `{loop-root}/STATE.md ## Decisions` (if applicable)
4. Your response MUST be a single JSON line:
   - Success: `{"stage":"design.interaction","status":"done","artifact":"artifacts/..."}`
   - Failure: `{"stage":"design.interaction","status":"failed","error":"reason"}`

DO NOT include artifact content, summaries, or "Next steps" in your response.
