---
name: implementation-architect
description: 'Produces an Implementation Blueprint: architecture decisions, file responsibilities, data flows, interface contracts, and execution order. Design artifact for implementation execution skills. Use for Phase 2a of the engineering loop or any task requiring architectural planning before coding.'
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

### Step 8: Produce Blueprint

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
## Interface Contracts
```

## Quality Gates

- [ ] Every file has a responsibility definition
- [ ] Interface contracts defined for all cross-file dependencies
- [ ] Data flows traced for all user interactions
- [ ] Execution order respects all dependencies
- [ ] Integration points identified with risk assessment
- [ ] Error handling covers all failure modes
- [ ] Artifact does not exceed `max_artifact_size_lines` (from config.yaml)

## Anti-Patterns

- **Never skip interface contracts** — every cross-file dependency needs one
- **Never assume execution order** — explicitly define with rationale
- **Never ignore integration risk** — every existing code touchpoint needs assessment
- **Never produce vague responsibilities** — ownership must be unambiguous
- **Never skip error handling** — every layer needs a defined approach
