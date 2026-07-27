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
