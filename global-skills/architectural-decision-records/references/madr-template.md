# MADR long-form template (default)

> Adapted from the ADR community's templates — https://adr.github.io/ (MADR / Nygard).

Copy the block below into `NNNN-title.md`. Replace every `{…}` placeholder with real content and delete the guidance comments. Sections marked *(optional)* may be removed if they add nothing — but Context, Decision Drivers, Considered Options, and Decision Outcome are load-bearing and should always be filled.

```markdown
---
status: "{proposed | accepted | rejected | deprecated | superseded by ADR-NNNN}"
date: {YYYY-MM-DD when the decision was last updated}
decision-makers: {everyone involved in the decision}
consulted: {subject-matter experts consulted (two-way communication)} # optional
informed: {people kept up to date (one-way communication)} # optional
---

# {short title representing the problem and the chosen solution}

## Context and Problem Statement

{Two to three sentences, or a short story, describing the context and the problem.
Make the scope explicit — name the components/connectors affected. Articulating
the problem as a question often helps. Link to the issue/board/design doc.}

## Decision Drivers

* {driver 1 — a desired quality, constraint, or force, e.g. "must sustain 5k writes/sec"}
* {driver 2 — e.g. "team has deep Postgres experience, none with Cassandra"}
* {driver 3 — e.g. "must not add a new operational component this quarter"}

## Considered Options

* {option 1}
* {option 2}
* {option 3}

## Decision Outcome

Chosen option: "{option N}", because {justification — meets the k.o. driver / resolves
the dominant force / best trade-off overall}.

### Consequences

* Good, because {positive consequence — a quality improved, a risk removed}
* Bad, because {negative consequence you are knowingly accepting}
* Neutral, because {a follow-on effect worth recording}

### Confirmation

{How will you confirm the implementation actually follows this decision? An automated
fitness function (ArchUnit, a lint rule, a CI check), a design/code review, a BDD
scenario? Point at it. — optional but strongly encouraged}

## Pros and Cons of the Options

### {option 1}

{short description or pointer}

* Good, because {argument}
* Neutral, because {argument}
* Bad, because {argument}

### {option 2}

* Good, because {argument}
* Bad, because {argument}

## More Information

{Evidence/confidence for the outcome, team agreement, when/how to realize it, and
when it should be revisited. Links to related ADRs and resources. — optional}
```
