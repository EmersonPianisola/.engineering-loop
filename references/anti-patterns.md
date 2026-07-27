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
