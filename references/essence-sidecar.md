---
name: essence-sidecar
id: essence
version: 4.0.0
type: reference
description: 'Four Lenses validation protocol. Runs BEFORE every stage. Lens 4 tensions captured to context.md.'
---

# Essence Sidecar — Four Lenses Protocol

Mandatory validation BEFORE every stage. Ensures stage inputs are sound before any work begins.

## Invocation

- **When:** Before every stage invocation — validates inputs, not outputs.
- **Who:** Essence sub-agent (skill: `essence`).
- **Context slice:** Inputs for the upcoming stage + work item. Never full context.
- **Loop behavior:** Internal to pre-stage gate — does NOT increment `attempts`.

## The Four Lenses

| Lens | Focus | Findings |
|------|-------|----------|
| 1 | Subjective terms | Ambiguous language, opinion-based statements |
| 2 | Hidden assumptions | Unstated dependencies, implicit requirements |
| 3 | Literal traps | Phrasing that invites wrong LLM interpretation |
| 4 | Conflicting priorities | Competing goals that need human resolution |

## Reflection Types (Andrew Ng Pattern)

Andrew Ng identifies reflection as a design pattern for agentic workflows. The Essence gate applies three distinct types of reflection, each with different verification requirements:

| Type | Mechanism | Example |
|------|-----------|---------|
| **Self-review** | A node critiques its own output before proceeding | `impl.code` reviews its own code against the blueprint |
| **Tool-backed evaluation** | External tools (tests, linters) verify output | `qa.static` runs lint/type-check to verify code quality |
| **Multi-agent collaboration** | A separate reviewer agent checks another agent's work | `verifier` checks `impl.code` output (author ≠ verifier) |

**Rule:** Every worker node must use at least one reflection type. The graph must not let an agent self-verify without a separate mechanism (tool-backed or multi-agent).

## Execution

1. Gather inputs for the upcoming stage (per ORCHESTRATOR.md essence input table).
2. Launch essence sub-agent with context slice: `{stage_inputs}` + `{work_item}`.
3. Prompt: "Apply the Four Lenses to these stage inputs. Are they sufficient and unambiguous for the upcoming stage? Report findings."
4. If findings (Lenses 1-3):
   - Adjust inputs inline (clarify ambiguity, state assumptions, fix phrasing).
   - Re-run Essence. Loop until clean.
   - Set `state.stages.{stage}.essence_checked = true`.
5. If Lens 4 tension (conflicting priorities):
   - Escalate to user for resolution. Await confirmation.
   - **Capture decision in `{loop-root}/context.md`** — record the tension, options, and user's resolution.
   - Set `essence_checked = true`.
6. If clean: set `state.stages.{stage}.essence_checked = true`. Proceed to stage.

## Context.md — Decision Capture

When Lens 4 tensions occur, the user's resolution is recorded in `{loop-root}/context.md`:

```markdown
# Context — {feature slug}

## Decisions

### {Decision Title}
- **Tension**: {What priorities conflict}
- **Options**: {Option A vs Option B}
- **Resolution**: {User's choice}
- **Date**: {YYYY-MM-DD}
- **Stage**: {stage that triggered the tension}
```

This file is loaded by:
- `impl.design` — blueprint creation considers user decisions
- `impl.code` — implementation follows user decisions
- `verify` — verification accounts for user decisions

## Essence Input Per Stage

| Stage | Essence Validates |
|-------|-------------------|
| `init` | Work item completeness, clarity of intent |
| `init.bdd` | PRD features, UX flows, user stories sufficient for journey mapping |
| `init.refine` | Raw user request: clarity, scope, intent |
| `arch.requirements` | Work item + planning artifacts provide sufficient context |
| `arch.solution` | Requirements artifact + UX designs are sufficient |
| `arch.review` | All architecture artifacts exist and are consistent |
| `impl.design` | Architecture (or work item for small/medium) is complete |
| `impl.code` | Blueprint is complete, contracts are defined |
| `verify` | Code implementation + tests are complete |
| `qa.security` | Code diff + architecture artifacts available |
| `qa.api-contract` | Blueprint + API source files available |
| `qa.performance` | Blueprint + architecture + build output available |
| `deploy.prepare` | All QA stages complete, code is ready |
| `doc.decisions` | STATE.md Decisions section has entries to consolidate |
| `doc.project` | Decision log exists, project structure is clear |

## Rules

- **Never skip** — every stage must pass the Four Lenses before invocation.
- **Never increment attempts** — essence loop is internal to the pre-stage gate.
- **Never escalate Lenses 1-3** — auto-adjust inline.
- **Always escalate Lens 4** — human resolution required for priority tensions.
- **Always capture Lens 4 in context.md** — user decisions are recorded for traceability.
- **Always run BEFORE stage** — Essence validates inputs, not outputs.
