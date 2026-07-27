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
