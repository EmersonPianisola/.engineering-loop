---
name: anti-patterns
id: anti
version: 2.0.0
type: reference
description: 'Global anti-patterns that apply across all stages. Updated for v9.'
---

# Anti-Patterns

## Loop Mechanics

- **Never treat stages as sequential** — the loop re-evaluates ALL active stages every iteration
- **Never break the loop prematurely** — only exit via all active stages done or constraint breach
- **Never reset attempt counters mid-loop** — counters persist across all iterations
- **Never skip stages on user request** — user requests for a specific step are focus directives, not skip directives. All active stages must run.
- **Always respect auto-sizing** — deactivated stages cannot be reactivated mid-loop

## LLM Orchestrator Drift (v11.1)

- **Never skip stages because complexity is "small"** — auto-sizing determines active stages, you execute all of them
- **Never skip the compliance gate** — `--check-compliance` must run before every stage transition
- **Never abandon the stage procedure to debug directly** — if debugging is needed, do it within the stage's sub-agent scope
- **Never modify project files outside your stage's allowed scope** — each stage has defined ALLOWED/FORBIDDEN actions
- **Never assume a stage is "not needed" based on your judgment** — the topology is authoritative
- **Never proceed past a compliance violation** — the gate exists to catch exactly these situations
- **Never edit config files during E2E execution** — `e2e.execute` can only modify files in `e2e/`
- **Never kill system processes from a stage** — report infrastructure issues as FAIL, don't self-repair

## Skill Usage

- **Never use a generic sub-agent for implementation** — always route through a specialized skill
- **Never self-construct a generic skill** — skills must be domain-specific
- **Never skip skill improvement** — each run makes skills better

## Essence Gate

- **Always run Essence BEFORE every stage** — Essence validates stage inputs are sound before any work begins
- **Never run Essence after a stage** — it is a pre-stage gate, not a post-stage check
- **Never skip Essence** — every stage must pass the Four Lenses before invocation
- **Never increment attempts for Essence** — Essence loop is internal to the pre-stage gate
- **Always capture Lens 4 in context.md** — user decisions must be recorded for traceability

## Design → Execute → Validate

- **Never skip Design for large/complex** — formal design stages are mandatory above complexity threshold
- **Never skip Validate** — every execution is verified against its design

## TDD

- **Never implement code before tests** — test first, always
- **Never skip the red phase** — test must fail before implementation
- **Never weaken tests to make them pass** — the gate decides done, not self-assessment
- **Never batch tasks in one commit** — one atomic commit per task

## Verification

- **Never let the author verify their own work** — Verifier must be a fresh agent
- **Never skip the discrimination sensor** — surviving mutations indicate weak tests
- **Never fabricate evidence** — evidence-or-zero: no file:line trace = gap

## Decisions

- **Never defer decision recording** — AD-NNN entries are recorded continuously, not at the end
- **Never reuse AD IDs** — sequential, never recycled
- **Never skip the Handoff update** — STATE.md Handoff must reflect current state

## Context Management

- **Never pass full context to a sub-agent** — always use context slicing
- **Never exceed agent_context_limit** — each sub-agent has its own token budget
- **Never let findings buffer grow unbounded** — cap at `max_findings_buffer`
- **Never skip log compaction** — context overflow will crash the loop

## Lessons

- **Never hand-edit lessons.json** — only the Verifier and lesson script modify it
- **Never load candidate lessons** — only confirmed lessons enter sub-agent context
- **Always distill from failures** — surviving mutants, spec gaps, uncovered ACs become lessons

## UI Testing

- **Never skip E2E for UI projects** — unit tests cannot catch integration-level UI bugs
- **Never use CSS/XPath selectors** — use role-based locators (`getByRole`, `getByLabel`, `getByText`)
- **Never rely on dev server for smoke tests** — test against production build
- **Never ignore console errors** — zero console errors is mandatory
- **Never ignore network errors** — zero 4xx/5xx is mandatory
- **Never skip auth bypass setup** — tests must bypass auth to reach protected routes
- **Never share state between E2E tests** — each test independently runnable
- **Never skip BDD→E2E coverage check** — every `@e2e` scenario must have a test
- **Never use `waitForTimeout()`** — use explicit assertions (`expect().toBeVisible()`)
- **Never test implementation details** — test observable user-facing behavior only
- **Always capture screenshots** — visual evidence for every test step
- **Always run serial execution for E2E** — deterministic state, no parallel flakiness
