---
name: skill-templates
id: templates
version: 1.0.0
type: reference
description: 'Templates for self-constructing Design and Execution skills.'
---

# Skill Templates for Self-Construction

When the Engineering Loop encounters a domain with no matching skill, it uses these templates.

---

## Design Skill Template

```markdown
---
name: {domain}-designer
description: 'Produces a {artifact_type} for {domain} work. Use when the engineering loop needs to design {what} before execution.'
---

# {Domain} Designer

**Role:** Design

**Output artifact:** `{artifact-root}/{artifact_directory}/{artifact_name}-{{slug}}.md`

## Input
- Work item
- Implementation Blueprint (if applicable)

## Workflow
1. Analyze work item for {domain-specific elements}
2. Produce {artifact}: {element 1}, {element 2}, interface contracts
3. Verify 100% coverage of relevant work item elements
4. Write artifact to designated path

## Quality Gates
- [ ] 100% coverage
- [ ] Interface contracts defined
- [ ] No ambiguity

## Anti-Patterns
- Never produce vague specifications
- Never skip coverage verification
```

---

## Execution Skill Template

```markdown
---
name: {domain}-executor
description: 'Implements {domain} work following a {design_artifact}. Use when the engineering loop needs to execute {what}.'
---

# {Domain} Executor

**Role:** Execute

**Output:** {output_description}

## Input
- {Design_artifact} (from {design_skill})
- Project conventions

## Workflow
1. Read design artifact
2. Setup infrastructure (dependencies, config)
3. Implement following contracts and patterns
4. Run verification (tests, build, lint)
5. Report completion status

## Quality Gates
- [ ] All design specifications implemented
- [ ] All verification passes
- [ ] No deviations from design

## Anti-Patterns
- Never deviate from design artifact — report gaps
- Never skip verification
- Never implement speculative features
```

---

## Decision Tree

```
What stage needs the skill?
│
├─ impl stage — Design
│  └─ Has implementation-architect? → Yes: use it.
│
├─ impl stage — Execute
│  ├─ Frontend UI? → Domain-specific or self-construct
│  ├─ Backend API? → Self-construct from template
│  ├─ Data/Storage? → Self-construct from template
│  └─ Other? → Self-construct + research
│
├─ test stage — Design
│  └─ Has bmad-bdd-mapper? → Yes: use it.
│
├─ test stage — Execute
│  ├─ E2E? → e2e-playwright
│  └─ Unit/Component? → Project test patterns
│
└─ review stage — Execute
   └─ Inline prompts in CORE.md (or BMad review skills if available)
```

## Rules

1. **Prefer existing skills** — only create when no match
2. **Design skills produce artifacts** — artifact is the contract
3. **Execution skills consume artifacts** — never deviate from design
4. **Domain-specific** — never create generic skills
5. **Record immediately** — update `skill-index.md`
6. **Use templates** — customize for domain and project
