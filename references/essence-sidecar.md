---
name: essence-sidecar
id: essence
version: 2.0.0
type: reference
description: 'Four Lenses validation protocol. Runs BEFORE every stage, validates inputs are sound.'
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
   - Apply resolution, set `essence_checked = true`.
6. If clean: set `state.stages.{stage}.essence_checked = true`. Proceed to stage.

## Essence Input Per Stage

| Stage | Essence Validates |
|-------|-------------------|
| `init` | Work item completeness, clarity of intent |
| `init.bdd` | PRD features, UX flows, user stories sufficient for journey mapping |
| `init.refine` | Raw user request: clarity, scope, and intent are well-defined |
| `arch.requirements` | Work item + planning artifacts provide sufficient context |
| `arch.cloud` | Requirements artifact is complete and unambiguous |
| `arch.solution` | Requirements artifact + UX designs are sufficient |
| `arch.review` | All 3 architecture artifacts exist and are internally consistent |
| `impl.design` | Consolidated architecture is complete |
| `impl.code` | Blueprint is complete, contracts are defined |
| `impl.review` | Code implementation is complete |
| `test.unit` | Code + BDD journey (unit scenarios) available |
| `test.integration` | Code + BDD journey (integration scenarios) + API contracts available |
| `test.e2e` | Code + BDD journey (e2e scenarios) + UX flows available |
| `test.qa` | All test files + BDD journey available |
| `qa.security` | Code diff + architecture artifacts available |
| `qa.api-contract` | Blueprint + API source files available |
| `qa.performance` | Blueprint + architecture + build output available |
| `deploy.prepare` | All QA stages complete, code is ready |
| `review` | All implementation and test artifacts available |

## Rules

- **Never skip** — every stage must pass the Four Lenses before invocation.
- **Never increment attempts** — essence loop is internal to the pre-stage gate.
- **Never escalate Lenses 1-3** — auto-adjust inline.
- **Always escalate Lens 4** — human resolution required for priority tensions.
- **Always run BEFORE stage** — Essence validates inputs, not outputs.
