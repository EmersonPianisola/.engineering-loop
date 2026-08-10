---
stage: design.visual-design
skill: bmad-visual-design
min_complexity: large
---

# Design > Visual Design
<!-- Min Complexity: large — deactivated for small/medium -->

Visual design procedure (typography, colors, layout, micro-animations).

## Activation

- Sources: design tokens, component library, brand assets.
- Elicit: visual identity, aesthetic direction, visual hierarchy, polish standards.

## Discovery

1. Review design tokens, component library, and brand assets.
2. Define visual identity and aesthetic direction.
3. Specify typography scale, color usage, layout system.
4. Define micro-animations and polish standards.
5. Establish accessibility contrast targets.

## Finalize

- Output: `visual-spec.md`, `visual-dos-donts.md`.
- Gate: token references resolve; visual decisions tied to business goals; accessibility contrast targets stated.
- State: `done: true` when visual design artifacts are documented.

## State Update Contract

**MANDATORY.** Follow `{reference-root}/sub-agent-contract.md`. Before returning your response:

1. Write all artifacts to their designated paths in `{artifact-root}/`
2. Update `{loop-root}/state.json`:
   - `stages.design.visual-design.done = true` (or `false` on failure)
   - `stages.design.visual-design.attempts += 1`
   - `stages.design.visual-design.artifact_path = "artifacts/..."` (your output path)
   - `stages.design.visual-design.error = null` (or failure description)
3. Record AD-NNN decisions in `{loop-root}/STATE.md ## Decisions` (if applicable)
4. Your response MUST be a single JSON line:
   - Success: `{"stage":"design.visual-design","status":"done","artifact":"artifacts/..."}`
   - Failure: `{"stage":"design.visual-design","status":"failed","error":"reason"}`

DO NOT include artifact content, summaries, or "Next steps" in your response.
