---
stage: design.design-system
skill: bmad-design-system
min_complexity: large
---

# Design > Design System
<!-- Min Complexity: large — deactivated for small/medium -->

Design system procedure (tokens, components, guidelines).

## Activation

- Sources: interaction patterns, wireframes, brand assets (if any).
- Elicit: token system, component library, brand guidelines, governance model.

## Discovery

1. Review interaction patterns, wireframes, and brand assets.
2. Define design tokens (color, typography, spacing, elevation, motion tokens in YAML).
3. Build component library (visual + behavioral specs per component).
4. Document design guidelines.
5. Define governance model.

## Finalize

- Output: `design-tokens.md`, `component-library.md`, `design-guidelines.md`.
- Gate: all tokens defined with values + usage rules; every component in wireframes has a library entry; governance model clear.
- State: `done: true` when design system artifacts are documented.

## State Update Contract

**MANDATORY.** Follow `{reference-root}/sub-agent-contract.md`. Before returning your response:

1. Write all artifacts to their designated paths in `{artifact-root}/`
2. Update `{loop-root}/state.json`:
   - `stages.design.design-system.done = true` (or `false` on failure)
   - `stages.design.design-system.attempts += 1`
   - `stages.design.design-system.artifact_path = "artifacts/..."` (your output path)
   - `stages.design.design-system.error = null` (or failure description)
3. Record AD-NNN decisions in `{loop-root}/STATE.md ## Decisions` (if applicable)
4. Your response MUST be a single JSON line:
   - Success: `{"stage":"design.design-system","status":"done","artifact":"artifacts/..."}`
   - Failure: `{"stage":"design.design-system","status":"failed","error":"reason"}`

DO NOT include artifact content, summaries, or "Next steps" in your response.
