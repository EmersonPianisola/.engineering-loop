---
name: exit-conditions
id: exit
version: 2.0.0
type: reference
description: 'All possible loop exit conditions, status codes, and blocking conditions.'
---

# Exit Conditions

| Condition | Where | Status | blocking_condition |
|-----------|-------|--------|-------------------|
| All stages done | WHILE false | `done` | — |
| Input invalid | Phase 0 | `blocked` | `input not ready for engineering` |
| Skill creation fails | Phase 1 | `blocked` | `no suitable skill available` |
| `init.bdd.attempts >= max` | init BDD | `blocked` | `BDD journey mapping non-convergence` |
| `init.refine.attempts >= max` | init refinement | `blocked` | `idea refinement non-convergence` |
| `arch.requirements.attempts >= max` | arch requirements | `blocked` | `requirements refinement non-convergence` |
| `arch.cloud.attempts >= max` | arch cloud | `blocked` | `cloud architecture non-convergence` |
| `arch.solution.attempts >= max` | arch solution | `blocked` | `solution design non-convergence` |
| `arch.review.attempts >= max` | arch review | `blocked` | `architecture review non-convergence` |
| Architecture missing | impl.design Design | `blocked` | `architecture stage not complete` |
| `impl.design.attempts >= max` | impl design | `blocked` | `implementation blueprint non-convergence` |
| `impl.code.attempts >= max` | impl code | `blocked` | `implementation non-convergence` |
| `impl.review.attempts >= max` | impl review | `blocked` | `implementation review non-convergence` |
| `test.unit.attempts >= max` | test unit | `blocked` | `unit tests cannot pass` |
| `test.integration.attempts >= max` | test integration | `blocked` | `integration tests cannot pass` |
| `test.e2e.attempts >= max` | test e2e | `blocked` | `E2E tests cannot pass` |
| `test.qa.attempts >= max` | test QA | `blocked` | `test coverage non-convergence` |
| `qa.security.attempts >= max` | qa security | `blocked` | `security review non-convergence` |
| `qa.api-contract.attempts >= max` | qa api-contract | `blocked` | `API contract validation non-convergence` |
| `qa.performance.attempts >= max` | qa performance | `blocked` | `performance check non-convergence` |
| `deploy.prepare.attempts >= max` | deploy prepare | `blocked` | `deploy preparation non-convergence` |
| `review.attempts >= max` | review | `blocked` | `review non-convergence` |
| `doc.decisions.attempts >= max` | doc decisions | `blocked` | `decision log non-convergence` |
| `doc.project.attempts >= max` | doc project | `blocked` | `project docs non-convergence` |
| `intent_gap` | review triage | `blocked` | `intent gap` |
| Stage timeout | Any stage | `halted` | `stage timeout exceeded` |
| User interrupt | Any | `halted` | `user interrupted` |

## Cross-Stage Reset (Review Triage)

| Finding Category | Effect on State |
|-----------------|----------------|
| `intent_gap` | `status: blocked`. **EXIT.** |
| `bad_spec` | Amend work item. `impl.design.done = false`, `blueprint = null`, `review.done = false` |
| `architecture_gap` | `arch.review.done = false`, `consolidated_architecture = null`, `impl.design.done = false`, `blueprint = null`, `review.done = false` |
| `patch` | Auto-fix. If tests fail: `impl.code.done = false`, `test.unit.done = false`, `review.done = false` |
| `patch` → tests pass | `review.done = true` |
| `defer` | Append to `deferred-work.md` |
| `reject` | Drop |

## Architecture Review Resets

| Finding Severity | Resets |
|-----------------|--------|
| `critical` in requirements | `arch.requirements.done = false`, `artifacts.requirements = null` |
| `critical` in cloud | `arch.cloud.done = false`, `artifacts.cloud_architecture = null` |
| `critical` in solution | `arch.solution.done = false`, `artifacts.solution_architecture = null` |
| `high` | Auto-adjust inline, re-validate |
| All clear | `arch.review.done = true` → architecture stage complete |

## QA Stage Resets

| Stage | Finding Severity | Resets |
|-------|---------------|--------|
| `qa.security` | critical | `impl.code.done = false`, `qa.security.done = false` |
| `qa.security` | high | Auto-fix inline, re-validate |
| `qa.api-contract` | any discrepancy | `impl.code.done = false`, `qa.api-contract.done = false` |
| `qa.performance` | critical | `impl.code.done = false`, `qa.performance.done = false` |
| `qa.performance` | high | Document for optimization sprint, `qa.performance.done = false` |
| `deploy.prepare` | build/lint error | `impl.code.done = false`, `deploy.prepare.done = false` |
