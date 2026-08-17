---
name: bmad-bdd-mapper
description: 'Maps all testable behaviors into Gherkin-style BDD scenarios. Produces a Behavior Map artifact as the design blueprint for test execution. Supports Scenario Outlines, hooks, data-driven testing, and traceability. Use for Phase 3a of the engineering loop or any task requiring behavior-driven test planning.'
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

#### Standard Scenarios

```gherkin
Scenario: {descriptive name}
  Tags: @{tag} @{acceptance-criterion-id}
  Given {precondition state}
  When {user action or system trigger}
  Then {expected observable outcome}
  And {additional assertions}
```

#### Scenario Outlines (Data-Driven)

When a behavior varies across multiple data combinations, use Scenario Outline instead of duplicating scenarios:

```gherkin
Scenario Outline: Login with varying credentials
  Tags: @e2e @AC-03 @data-driven
  Given the user is on the login page
  When the user enters username "<username>" and password "<password>"
  Then the system should "<outcome>"

  Examples: Valid credentials
    | username | password | outcome |
    | alice    | pass123  | redirect to dashboard |
    | bob      | secret   | redirect to dashboard |

  Examples: Invalid credentials
    | username | password | outcome |
    | alice    | wrong    | show error message |
    |          | pass123  | show error message |
    | unknown  | pass123  | show error message |
```

**When to use Scenario Outline:**
- Same flow, different input data
- Boundary value testing (min, max, empty, null)
- Parameterized validation rules
- Multiple user roles with same action

**When NOT to use Scenario Outline:**
- Different preconditions per example
- Different expected outcomes requiring different assertions
- More than 10 examples (split into multiple outlines)

### Step 4: Error Path Scenarios

For every happy-path scenario, derive error-path variants:

| Error Condition | Variant |
|----------------|---------|
| Network failure | Service call fails |
| Invalid input | Boundary/invalid values |
| Empty state | Collection/data is empty |
| Permission denied | User lacks permission |
| Concurrent modification | Data changed between read/write |
| Rate limiting | Too many requests in time window |
| Timeout | Service exceeds response time |
| Malformed data | Invalid JSON, unexpected schema |

### Step 5: Hook Strategy

Define hooks for test setup and teardown:

| Hook | Purpose |
|------|---------|
| `BeforeSuite` | One-time setup: database seed, service start |
| `AfterSuite` | One-time teardown: cleanup, reports |
| `BeforeScenario` | Per-scenario setup: authentication, navigation |
| `AfterScenario` | Per-scenario teardown: logout, state reset |
| `BeforeStep` | Per-step setup: rarely needed, use sparingly |
| `AfterStep` | Per-step teardown: screenshot on failure |

**Hook rules:**
- Keep hooks fast — they run before/after every test
- Use `BeforeScenario` for auth bypass, not `BeforeStep`
- Never share state between scenarios — each scenario must be independently runnable
- Tag-based hooks (`@requires-db`, `@skip-ci`) for selective execution

### Step 6: Coverage Verification

Cross-reference against the work item:

1. Every acceptance criterion → at least one scenario
2. Every I/O matrix row → a scenario
3. Every edge case → a scenario
4. Every user-facing flow → at least one `@e2e` scenario

**If any gap exists, add scenarios until 100% coverage.**

### Step 7: Produce Behavior Map

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
scenario_outlines: {count}
examples_tables: {count}
coverage: {percentage}%
---

# Behavior Map: {work item title}

## Coverage Matrix

| Acceptance Criterion | Scenarios | Tags |
|---------------------|-----------|------|
| AC-01 | Scenario: X, Scenario Outline: Y | @e2e @AC-01 |

## Scenarios
## Error Paths
## Edge Cases
## Hook Configuration
```

## Quality Gates

- [ ] 100% acceptance criteria covered
- [ ] 100% I/O matrix rows covered
- [ ] Every user-facing flow has @e2e scenario(s)
- [ ] Error paths derived for all happy paths
- [ ] Scenarios independent (no cross-scenario dependencies)
- [ ] Each scenario has exactly one When clause
- [ ] Then clauses are observable (not implementation-internal)
- [ ] Scenario Outlines used for data-driven patterns (not duplicated scenarios)
- [ ] Hooks defined for setup/teardown
- [ ] Artifact does not exceed `max_artifact_size_lines` (from config.yaml)
- [ ] **Every @e2e scenario has a unique, testable identifier** for 1:1 mapping to Playwright tests

## BDD→E2E Enforcement

Every `@e2e` scenario in this Behavior Map **MUST** have a corresponding Playwright test. The `e2e.execute` stage enforces this:

```
FOR each @e2e scenario:
    IF no test exists → ORPHANED (FAIL)
    IF test fails → FAILED (becomes fix task)
    IF test passes → COVERED (PASS)
```

**Rules:**
- Each `@e2e` scenario name becomes the test title
- Scenario tags include `@{scenario-id}` for traceability
- Then clauses must be browser-observable (visible element, URL change, text presence)
- If a scenario cannot be tested in a browser, re-tag as `@component` or `@integration`

## Tag Strategy

| Tag | Purpose | CI Usage |
|-----|---------|----------|
| `@smoke` | Critical path only | Run on every PR |
| `@regression` | Full coverage | Run nightly |
| `@e2e` | Browser tests | Run in CI browser pool |
| `@unit` | Unit tests | Run on every commit |
| `@integration` | Cross-module | Run on merge |
| `@component` | Component tests | Run on every commit |
| `@edge-case` | Edge conditions | Run nightly |
| `@error-path` | Error scenarios | Run nightly |
| `@happy-path` | Primary flows | Run on every PR |
| `@slow` | > 5s execution | Skip in fast CI |
| `@skip-ci` | Manual-only | Never run in CI |
| `@AC-{n}` | Acceptance criterion traceability | Filter by feature |

## Anti-Patterns

- **Never write implementation-specific scenarios** — describe behavior, not code
- **Never combine multiple behaviors** — one behavior per scenario
- **Never skip error paths** — every happy path needs error variants
- **Never use ambiguous Then clauses** — outcomes must be observable
- **Never skip coverage verification** — incomplete until 100%
- **Never duplicate scenarios for data variation** — use Scenario Outline
- **Never put setup logic in scenarios** — use hooks
- **Never share state between scenarios** — each scenario is independently runnable
