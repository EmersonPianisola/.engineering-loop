---
name: bmad-bdd-mapper
description: 'Maps all testable behaviors into Gherkin-style BDD scenarios. Produces a Behavior Map artifact as the design blueprint for test execution. Use for Phase 3a of the engineering loop or any task requiring behavior-driven test planning.'
---

# BDD Behavior Mapper

**Role:** Design — produces the Behavior Map that test execution skills implement against.

**Output artifact:** `{artifact-root}/behavior-maps/behavior-{slug}.md`

## Input

- Work item (spec, ticket, or description)
- Implementation Blueprint (from Phase 2a)

## Workflow

### Step 1: Extract Behaviors

Read the work item and identify every testable behavior from:

1. **Acceptance Criteria** — each criterion produces one or more scenarios
2. **I/O & Edge-Case Matrix** — each row is one scenario
3. **Intent / Purpose** — implicit behaviors not explicitly listed
4. **Implementation Blueprint** — architectural decisions that introduce testable paths

### Step 2: Classify Scenarios

Tag each scenario with its test type:

| Tag | When to Use |
|-----|------------|
| `e2e` | User-facing flow: navigation, UI interaction, multi-step |
| `component` | Single UI component with props/state interactions |
| `integration` | Cross-module interactions |
| `unit` | Pure functions, utilities, data transformations, validators |

**Rules:**
- User interaction visible in browser → `e2e`
- Single component rendering with props → `component`
- Spans multiple modules → `integration`
- Pure function with defined I/O → `unit`
- One acceptance criterion may produce multiple scenarios with different tags

### Step 3: Write Scenarios

```gherkin
Scenario: {descriptive name}
  Tags: @{tag} @{acceptance-criterion-id}
  Given {precondition state}
  When {user action or system trigger}
  Then {expected observable outcome}
  And {additional assertions}
```

**Naming:** `{feature}-{short-description}`

**Tags:** `@e2e` `@unit` `@integration` `@component` `@AC-{n}` `@edge-case` `@error-path` `@happy-path`

### Step 4: Error Path Scenarios

For every happy-path scenario, derive error-path variants:

| Error Condition | Variant |
|----------------|---------|
| Network failure | Service call fails |
| Invalid input | Boundary/invalid values |
| Empty state | Collection/data is empty |
| Permission denied | User lacks permission |
| Concurrent modification | Data changed between read/write |

### Step 5: Coverage Verification

Cross-reference against the work item:

1. Every acceptance criterion → at least one scenario
2. Every I/O matrix row → a scenario
3. Every edge case → a scenario
4. Every user-facing flow → at least one `@e2e` scenario

**If any gap exists, add scenarios until 100% coverage.**

### Step 6: Produce Behavior Map

Write to `{artifact-root}/behavior-maps/behavior-{slug}.md`:

```markdown
---
slug: "{slug}"
work_item: "{work_item identifier}"
generated_at: "{ISO-8601}"
total_scenarios: {count}
e2e_scenarios: {count}
unit_scenarios: {count}
integration_scenarios: {count}
component_scenarios: {count}
coverage: {percentage}%
---

# Behavior Map: {work item title}

## Coverage Matrix
| Acceptance Criterion | Scenarios | Tags |

## Scenarios
## Error Paths
## Edge Cases
```

## Quality Gates

- [ ] 100% acceptance criteria covered
- [ ] 100% I/O matrix rows covered
- [ ] Every user-facing flow has @e2e scenario(s)
- [ ] Error paths derived for all happy paths
- [ ] Scenarios independent (no cross-scenario dependencies)
- [ ] Each scenario has exactly one When clause
- [ ] Then clauses are observable (not implementation-internal)
- [ ] Artifact does not exceed `max_artifact_size_lines` (from config.yaml)

## Anti-Patterns

- **Never write implementation-specific scenarios** — describe behavior, not code
- **Never combine multiple behaviors** — one behavior per scenario
- **Never skip error paths** — every happy path needs error variants
- **Never use ambiguous Then clauses** — outcomes must be observable
- **Never skip coverage verification** — incomplete until 100%
