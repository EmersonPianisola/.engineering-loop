# Nygard lightweight template (fallback)

> Adapted from the ADR community's templates — https://adr.github.io/ (MADR / Nygard).

Use this for decisions that are real and worth recording but small enough that the full MADR options analysis would be ceremony. It's the original format from Michael Nygard's 2011 post. If the decision has genuine competing options with trade-offs worth weighing, use MADR instead.

Copy the block into `NNNN-title.md`, fill it in, delete the comments.

```markdown
# NNNN. {short title of the decision}

Date: {YYYY-MM-DD}

## Status

{Proposed | Accepted | Deprecated | Superseded by ADR-NNNN}

## Context

{What is the issue that motivates this decision? Describe the forces at play —
technical, business, team, political. State them value-neutrally, as facts, so the
reader can judge whether the same forces still hold later.}

## Decision

{State the decision in full sentences, in active voice: "We will …". One clear
choice, not a menu.}

## Consequences

{What becomes easier and what becomes harder as a result. List the good, the bad,
and the neutral outcomes. Describe the resulting context after the decision is
applied — future ADRs may need to reckon with it.}
```
