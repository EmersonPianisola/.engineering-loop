---
name: logging
id: logging
version: 2.0.0
type: reference
description: 'Log format, state table template, and compaction rules.'
---

# Logging Specification

**MANDATORY.** Every iteration writes to `{process-logs}/engineering/{run_id}-{slug}.md`.

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
---

# Engineering Loop: {title}

## State

| Variable | Value |
|----------|-------|
| iteration | 0 |
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
| stages.architecture.cloud.done | false |
| stages.architecture.cloud.attempts | 0 |
| stages.architecture.cloud.essence_checked | false |
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
| stages.impl.review.done | false |
| stages.impl.review.attempts | 0 |
| stages.impl.review.essence_checked | false |
| stages.test.unit.done | false |
| stages.test.unit.attempts | 0 |
| stages.test.unit.essence_checked | false |
| stages.test.integration.done | false |
| stages.test.integration.attempts | 0 |
| stages.test.integration.essence_checked | false |
| stages.test.e2e.done | false |
| stages.test.e2e.attempts | 0 |
| stages.test.e2e.essence_checked | false |
| stages.test.qa.done | false |
| stages.test.qa.attempts | 0 |
| stages.test.qa.essence_checked | false |
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
| stages.review.done | false |
| stages.review.attempts | 0 |
| stages.review.essence_checked | false |
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
- **Compaction:** After `compact_log_after_iteration` iterations, run `compact_log()` per `references/hardware-management.md`.
- **Post-loop:** update `completed_at`, `status: done`, `skills_used`, `total_iterations`. Append to `{process-logs}/index.md`.
