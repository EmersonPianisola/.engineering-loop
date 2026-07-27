---
name: anti-patterns
id: anti
version: 1.0.0
type: reference
description: 'Global anti-patterns that apply across all stages.'
---

# Anti-Patterns

## Loop Mechanics

- **Never treat stages as sequential** — the loop re-evaluates ALL stages every iteration
- **Never break the loop prematurely** — only exit via all stages done or constraint breach
- **Never reset attempt counters mid-loop** — counters persist across all iterations
- **Never advance without convergence** — the architecture gate is mandatory
- **Never skip stages on user request** — user requests for a specific step are focus directives, not skip directives. The full loop is mandatory.

## Skill Usage

- **Never use a generic sub-agent for implementation** — always route through a specialized skill
- **Never self-construct a generic skill** — skills must be domain-specific
- **Never skip skill improvement** — each run makes skills better

## Essence Gate

- **Always run Essence BEFORE every stage** — Essence validates stage inputs are sound before any work begins
- **Never run Essence after a stage** — it is a pre-stage gate, not a post-stage check
- **Never skip Essence** — every stage must pass the Four Lenses before invocation
- **Never increment attempts for Essence** — Essence loop is internal to the pre-stage gate

## Design → Execute → Validate

- **Never skip Design** — every stage produces a blueprint before execution
- **Never skip Validate** — every execution is verified against its design

## Context Management

- **Never pass full context to a sub-agent** — always use context slicing
- **Never exceed agent_context_limit** — each sub-agent has its own token budget
- **Never let findings buffer grow unbounded** — cap at `max_findings_buffer`
- **Never skip log compaction** — context overflow will crash the loop

## Testing & Review

- **Never skip review** — even for trivial changes
- **Never skip tests** — unit + E2E for user-facing features
- **Never skip E2E** — every user-facing flow needs E2E coverage
- **Never defer findings caused by this change** — defer is only pre-existing
- **Never over-classify as reject** — when in doubt, prefer defer
