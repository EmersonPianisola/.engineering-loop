---
name: implementation-architect
description: 'Produces an Implementation Blueprint: architecture decisions, file responsibilities, data flows, interface contracts, execution order, testing strategy, CI/CD pipeline, and rollback plan. Design artifact for implementation execution skills. Use for Phase 2a of the engineering loop or any task requiring architectural planning before coding.'
---

# Implementation Architect

**Role:** Design — produces the Implementation Blueprint that execution skills implement against.

**Output artifact:** `{artifact-root}/blueprints/blueprint-{slug}.md`

## Input

- Work item (spec, ticket, or description)

## Workflow

### Step 1: Analyze Work Item

Read the work item thoroughly. Extract:
- All tasks and acceptance criteria
- All file paths or scope of changes
- Dependencies between tasks
- Edge cases and error conditions

### Step 2: Architecture Decisions

For each significant technical choice, document:

| Decision | Options Considered | Selected | Rationale |
|----------|-------------------|----------|-----------|

**Decision areas to consider:**
- State management strategy
- Data fetching pattern
- Error handling approach
- Component composition strategy
- Styling organization
- External service interaction patterns
- Navigation/routing approach

### Step 3: File Responsibilities

For each file in scope, define:

```markdown
#### `{file_path}`
- **Responsibility:** What this file owns
- **Exports:** Functions, components, constants exported
- **Imports:** Dependencies
- **Interface Contract:** Public API signature
- **Error Handling:** How errors originate and propagate
```

### Step 4: Data Flow

Produce text-based data flow diagrams:

```
User Action → Component → Hook → Lib Function → External Service
     ↑                                          ↓
     └── Response/Error ────────────────────────┘
```

Trace the complete data path for each major user flow.

### Step 5: Execution Order

Determine implementation order based on dependencies:

```markdown
1. `{file}` — no dependencies, static data
2. `{file}` — depends on: {file}
3. `{file}` — depends on: {file}
```

### Step 6: Integration Points

Identify where new code touches existing code:

```markdown
#### Integration: `{existing_file}`
- **Change:** What changes
- **Risk:** Low / Medium / High
- **Test impact:** What tests may need updates
```

### Step 7: Error Handling Strategy

Define the error handling approach per layer:

```markdown
| Layer | Strategy | User-facing? |
|-------|----------|-------------|
```

### Step 8: Testing Strategy

Define how each component will be tested:

```markdown
## Testing Strategy

### Unit Tests
| Module | Test File | Coverage Target | Key Scenarios |
|--------|-----------|----------------|---------------|
| `utils/validate.ts` | `utils/validate.test.ts` | 100% | Boundary values, invalid inputs |

### Integration Tests
| Flow | Test File | Mock Strategy |
|------|-----------|---------------|
| User registration | `integration/register.test.ts` | Mock email service |

### E2E Tests
| User Flow | Test File | Priority |
|-----------|-----------|----------|
| Complete checkout | `e2e/checkout.spec.js` | @smoke |

### Test Data
- Fixtures: [describe shared test data]
- Factories: [describe data generation]
- Seed data: [describe database seeding]
```

### Step 9: CI/CD Pipeline

Define the automation pipeline:

```markdown
## CI/CD Pipeline

### Pre-commit
- Linting: [tool, scope]
- Type checking: [tool, scope]
- Pre-commit hooks: [list]

### PR Checks
- Unit tests: [command, coverage threshold]
- Integration tests: [command]
- Build: [command]
- Security scan: [tool]

### Post-Merge
- E2E tests: [command, browser targets]
- Deployment: [environment, strategy]
- Smoke tests: [command]

### Artifacts
- Build output: [location]
- Test reports: [format, location]
- Coverage reports: [format, location]
```

### Step 10: Rollback Plan

Define how to undo this implementation if needed:

```markdown
## Rollback Plan

### Rollback Triggers
- [Condition that warrants rollback, e.g., error rate > 5%]
- [Condition, e.g., critical bug in core flow]

### Rollback Steps
1. [Step 1, e.g., Revert deployment to previous version]
2. [Step 2, e.g., Run database migration rollback]
3. [Step 3, e.g., Verify health checks]

### Data Migration Rollback
- [If data migrations are involved, describe rollback strategy]
- [If irreversible, describe compensating actions]

### Communication
- [Who to notify]
- [Status update template]
```

### Step 11: Produce Blueprint

Write to `{artifact-root}/blueprints/blueprint-{slug}.md`:

```markdown
---
slug: "{slug}"
work_item: "{work_item identifier}"
generated_at: "{ISO-8601}"
total_files: {count}
new_files: {count}
modified_files: {count}
---

# Implementation Blueprint: {work item title}

## Architecture Decisions
## File Responsibilities
## Data Flows
## Execution Order
## Integration Points
## Error Handling Strategy
## Testing Strategy
## CI/CD Pipeline
## Rollback Plan
## Interface Contracts
```

## Quality Gates

- [ ] Every file has a responsibility definition
- [ ] Interface contracts defined for all cross-file dependencies
- [ ] Data flows traced for all user interactions
- [ ] Execution order respects all dependencies
- [ ] Integration points identified with risk assessment
- [ ] Error handling covers all failure modes
- [ ] Testing strategy covers unit, integration, and E2E
- [ ] CI/CD pipeline defined for all stages
- [ ] Rollback plan includes triggers, steps, and communication
- [ ] Artifact does not exceed `max_artifact_size_lines` (from config.yaml)

## Anti-Patterns

- **Never skip interface contracts** — every cross-file dependency needs one
- **Never assume execution order** — explicitly define with rationale
- **Never ignore integration risk** — every existing code touchpoint needs assessment
- **Never produce vague responsibilities** — ownership must be unambiguous
- **Never skip error handling** — every layer needs a defined approach
- **Never skip testing strategy** — untested code is a rollback risk
- **Never skip rollback plan** — every deployment needs an undo path
