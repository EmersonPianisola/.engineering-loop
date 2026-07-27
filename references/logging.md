---
name: logging
id: logging
version: 3.0.0
type: reference
description: 'Log format, state table template, and compaction rules. Dual state: JSON (machine) + STATE.md (human).'
---

# Logging Specification

**MANDATORY.** Every iteration writes to `{process-logs}/engineering/{run_id}-{slug}.md`.

## Dual State

| File | Purpose | Updated By |
|------|---------|------------|
| `state.json` | Machine-readable state (iteration, done/attempts, constraints) | Orchestrator every iteration |
| `STATE.md` | Human-readable state + Decisions (AD-NNN) + Handoff | Orchestrator after each stage |

## STATE.md Format

```markdown
# STATE

## Decisions

### AD-001
- **Decision**: {What}
- **Reason**: {Why}
- **Trade-off**: {Cost}
- **Scope**: {Where}
- **Date**: {YYYY-MM-DD}
- **Status**: active
- **Origin**: {stage ID}

## Handoff

**Current stage:** {stage ID}
**Iteration:** {n}
**Status:** running | blocked | done
**Summary:** {What was accomplished in the last stage}

## Complexity

**Level:** small | medium | large | complex
**Heuristics:** {files: N, tasks: N, new_domains: Y/N, external_integrations: Y/N}
```

## Log File Template

```markdown
---
run_id: "eng-{YYYYMMDD}-{HHMMSS}"
workflow: "engineering"
trigger: "{user phrase}"
started_at: "{ISO-8601}"
completed_at: ""
status: "running"
work_item: "{path or description}"
skills_used: ""
complexity: "unset"
---

# Engineering Loop: {title}

## State

| Variable | Value |
|----------|-------|
| iteration | 0 |
| complexity | unset |
| max_loop_iterations | 50 |
| subagent_invocations | {} |
| essence_retries | {} |
| stages.init.done | false |
| stages.init.attempts | 0 |
| stages.init.essence_checked | false |
| stages.init.bdd.done | false |
| stages.init.bdd.attempts | 0 |
| stages.init.bdd.essence_checked | false |
| stages.init.refine.done | false |
| stages.init.refine.attempts | 0 |
| stages.init.refine.essence_checked | false |
| stages.architecture.requirements.done | false |
| stages.architecture.requirements.attempts | 0 |
| stages.architecture.requirements.essence_checked | false |
| stages.architecture.solution.done | false |
| stages.architecture.solution.attempts | 0 |
| stages.architecture.solution.essence_checked | false |
| stages.architecture.review.done | false |
| stages.architecture.review.attempts | 0 |
| stages.architecture.review.essence_checked | false |
| stages.impl.design.done | false |
| stages.impl.design.attempts | 0 |
| stages.impl.design.essence_checked | false |
| stages.impl.code.done | false |
| stages.impl.code.attempts | 0 |
| stages.impl.code.essence_checked | false |
| stages.verify.done | false |
| stages.verify.attempts | 0 |
| stages.verify.essence_checked | false |
| stages.qa.security.done | false |
| stages.qa.security.attempts | 0 |
| stages.qa.security.essence_checked | false |
| stages.qa.api-contract.done | false |
| stages.qa.api-contract.attempts | 0 |
| stages.qa.api-contract.essence_checked | false |
| stages.qa.performance.done | false |
| stages.qa.performance.attempts | 0 |
| stages.qa.performance.essence_checked | false |
| stages.deploy.prepare.done | false |
| stages.deploy.prepare.attempts | 0 |
| stages.deploy.prepare.essence_checked | false |
| stages.doc.decisions.done | false |
| stages.doc.decisions.attempts | 0 |
| stages.doc.decisions.essence_checked | false |
| stages.doc.project.done | false |
| stages.doc.project.attempts | 0 |
| stages.doc.project.essence_checked | false |
| stages.post.done | false |
| status | running |

## Iteration Log

| Iter | Stage | Action | Result | Details |
|------|-------|--------|--------|---------|

## Details
```

## Update Rules

- **Every iteration:** update State table, append row to Iteration Log, append details, overwrite file.
- **After each stage:** update STATE.md Decisions (new AD-NNN) and Handoff.
- **Compaction:** After `compact_log_after_iteration` iterations, run `compact_log()` per `references/hardware-management.md`.
- **Post-loop:** update `completed_at`, `status: done`, `skills_used`, `total_iterations`. Append to `{process-logs}/index.md`.
