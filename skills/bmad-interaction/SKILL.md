---
name: bmad-interaction
id: bmad-interaction
version: 1.0.0
type: skill
stage: design.interaction
---

# Skill: BMAD Interaction Design

## Objective
Define how users interact with the product: interaction patterns, component behaviors, and motion specifications. Every interaction is a state machine with triggers, transitions, and outcomes. Accessibility is a floor, not a ceiling.

## Inputs
- Wireframes and IA artifacts
- Personas and journey maps
- Research findings
- Stage context: `state.stages.design.interaction`

## Permitted Tools
- `read`: Read wireframes, IA, personas, journeys
- `glob`: Find relevant project files
- `grep`: Search for existing interaction patterns, component definitions

## Interaction Design Framework

### 1. Interaction Patterns

Named, reusable patterns that solve common interaction problems:

```markdown
## Pattern: {Pattern Name}
**Category:** {Navigation / Data Entry / Feedback / Selection / Display}
**Trigger:** {User action or system event that initiates the pattern}

### States
| State | Condition | Visual |
|-------|-----------|--------|
| Default | Initial state | {Description} |
| Hover | Pointer over element | {Description} |
| Active | Element being interacted with | {Description} |
| Disabled | Interaction not available | {Description} |
| Error | Invalid state | {Description} |
| Loading | Async operation in progress | {Description} |
| Success | Operation completed | {Description} |

### Transitions
| From | Trigger | To | Animation |
|------|---------|-----|-----------|
| Default | Hover | Hover | {Fade, 150ms} |
| Hover | Click | Active | {Scale 0.95, 100ms} |
| Active | Release | Loading | {Spinner, 300ms} |
| Loading | Success | Success | {Fade in, 200ms} |
| Loading | Error | Error | {Shake, 400ms} |

### Accessibility
- **Keyboard:** {Keyboard interaction: Tab, Enter, Escape}
- **Screen reader:** {ARIA labels, live regions}
- **Touch:** {Minimum target size: 44x44px}
- **Motion:** {Respects prefers-reduced-motion}

### Examples
{Where this pattern is used in the product}
```

### Common Interaction Patterns

| Pattern | Category | Description |
|---------|----------|-------------|
| **Infinite Scroll** | Display | Load more content as user scrolls |
| **Modal Dialog** | Feedback | Overlay for critical decisions |
| **Inline Edit** | Data Entry | Edit content in place |
| **Drag & Drop** | Selection | Reorder items by dragging |
| **Swipe Actions** | Navigation | Swipe to reveal actions (mobile) |
| **Skeleton Loading** | Feedback | Placeholder while loading |
| **Toast Notification** | Feedback | Temporary status message |
| **Accordion** | Display | Expandable/collapsible sections |
| **Stepper** | Navigation | Multi-step process indicator |
| **Virtual Scroll** | Display | Render only visible list items |

### 2. Component Behaviors

Behavioral specifications for each UI component:

```markdown
## Component: {Component Name}
**Purpose:** {What this component does}

### Props / Configuration
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| {name} | {type} | {default} | {Description} |

### Events
| Event | Payload | When |
|-------|---------|------|
| onChange | {value} | When user modifies value |
| onSubmit | {formData} | When user submits |
| onError | {error} | When operation fails |

### States
| State | Trigger | Behavior |
|-------|---------|----------|
| Idle | Mount | Shows default content |
| Loading | Submit initiated | Shows skeleton/spinner, disables input |
| Success | Operation completes | Shows confirmation, resets |
| Error | Operation fails | Shows error message, preserves input |

### Edge Cases
| Case | Behavior |
|------|----------|
| Empty data | Shows empty state with CTA |
| Network error | Shows retry button |
| Concurrent edits | Shows conflict resolution |
| Large dataset | Paginates or virtual scrolls |
```

### 3. Motion Specification

Motion serves function, not decoration:

```markdown
# Motion Specification

## Principles
1. **Inform:** Motion communicates state changes
2. **Orient:** Motion maintains spatial context
3. **Delight:** Subtle motion adds polish (never at cost of performance)

## Easing Curves
| Name | Curve | Use |
|------|-------|-----|
| Standard | `cubic-bezier(0.2, 0, 0, 1)` | Default transitions |
| Decelerate | `cubic-bezier(0, 0, 0, 1)` | Elements entering |
| Accelerate | `cubic-bezier(0.4, 0, 1, 1)` | Elements exiting |
| Spring | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Playful interactions |

## Duration Scale
| Scale | Duration | Use |
|-------|----------|-----|
| Instant | 0ms | State changes that shouldn't animate |
| Fast | 100-150ms | Micro-interactions (hover, toggle) |
| Normal | 200-300ms | Default transitions |
| Slow | 400-500ms | Page transitions, modal open/close |

## Animation Rules
- Never animate more than 2 properties simultaneously
- Always respect `prefers-reduced-motion`
- Animation duration <= perceived operation duration
- No animation during user input (avoid input lag)
- Fallback to instant transition when GPU unavailable
```

## Accessibility Floor

Every interaction must meet WCAG 2.2 AA:

| Requirement | Standard |
|-------------|----------|
| **Keyboard accessible** | All interactions operable with keyboard alone |
| **Focus management** | Visible focus indicator, logical tab order |
| **Screen reader** | ARIA labels, roles, live regions for dynamic content |
| **Touch targets** | Minimum 44x44 CSS pixels |
| **Motion** | Respects `prefers-reduced-motion` |
| **Color** | Not the sole indicator of state (use icon + color) |
| **Timing** | All animations <= 5 seconds, pausable |

## Output Format
```json
{
  "stage": "design.interaction",
  "status": "done",
  "artifact": "artifacts/design/interaction/interaction-patterns.md",
  "patterns_count": 10,
  "components_specified": 15,
  "complete": true
}
```

## Output Artifacts

| File | Content |
|------|---------|
| `interaction-patterns.md` | Named patterns with states, triggers, transitions |
| `component-behaviors.md` | Behavioral specs per component |
| `motion-spec.md` | Easing curves, durations, animation rules |

## Quality Gates

| Gate | Criteria |
|------|----------|
| **Pattern coverage** | Every IA surface maps to >= 1 interaction pattern |
| **State coverage** | All patterns cover normal/error/empty/loading |
| **Accessibility** | WCAG 2.2 AA floor defined for all interactions |
| **Motion** | All animations have duration, easing, and reduced-motion fallback |

## Anti-Patterns
- **Never design interactions without states** — every interaction is a state machine
- **Never skip error states** — error handling is interaction design, not an afterthought
- **Never use motion for decoration** — motion must serve function (inform, orient, delight)
- **Never ignore keyboard** — if it doesn't work with keyboard, it doesn't work
- **Never hardcode animation values** — use design tokens for duration and easing
- **Never animate during input** — user input always takes priority over animation
