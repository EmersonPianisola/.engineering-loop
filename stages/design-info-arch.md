---
stage: design.info-arch
skill: bmad-info-arch
min_complexity: large
---

# Design > Information Architecture
<!-- Min Complexity: large — deactivated for small/medium -->

Information architecture procedure (sitemaps, wireframes, navigation).

## Activation

- Sources: personas, journeys, PRD, research.
- Elicit: content inventory, information hierarchy, navigation patterns.

## Discovery

1. Review personas, journeys, PRD, and research.
2. Build content inventory and information hierarchy.
3. Design sitemaps (hierarchical structure).
4. Create wireframes (low-fidelity screen layouts with annotations).
5. Define navigation spec.

## Finalize

- Output: `sitemaps.md`, `wireframes.md`, `navigation-spec.md`.
- Gate: every persona has a named path through IA; all journeys land on covered surfaces; every surface has a wireframe.
- State: `done: true` when IA artifacts are documented.

## State Update Contract

**MANDATORY.** Follow `{reference-root}/sub-agent-contract.md`. Before returning your response:

1. Write all artifacts to their designated paths in `{artifact-root}/`
2. Update `{loop-root}/state.json`:
   - `stages.design.info-arch.done = true` (or `false` on failure)
   - `stages.design.info-arch.attempts += 1`
   - `stages.design.info-arch.artifact_path = "artifacts/..."` (your output path)
   - `stages.design.info-arch.error = null` (or failure description)
3. Record AD-NNN decisions in `{loop-root}/STATE.md ## Decisions` (if applicable)
4. Your response MUST be a single JSON line:
   - Success: `{"stage":"design.info-arch","status":"done","artifact":"artifacts/..."}`
   - Failure: `{"stage":"design.info-arch","status":"failed","error":"reason"}`

DO NOT include artifact content, summaries, or "Next steps" in your response.
