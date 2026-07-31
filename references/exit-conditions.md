---
name: exit-conditions
id: exit
version: 3.0.0
type: reference
description: 'All possible loop exit conditions, status codes, and blocking conditions. Updated for v9 stages.'
---

# Exit Conditions

| Condition | Where | Status | blocking_condition |
|-----------|-------|--------|-------------------|
| All active stages done | WHILE false | `done` | — |
| Input invalid | Phase 0 | `blocked` | `input not ready for engineering` |
| Skill creation fails | Phase 1 | `blocked` | `no suitable skill available` |
| `init.bdd.attempts >= max` | init BDD | `blocked` | `BDD journey mapping non-convergence` |
| `init.refine.attempts >= max` | init refinement | `blocked` | `idea refinement non-convergence` |
| `arch.requirements.attempts >= max` | arch requirements | `blocked` | `requirements refinement non-convergence` |
| `arch.solution.attempts >= max` | arch solution | `blocked` | `solution design non-convergence` |
| `arch.review.attempts >= max` | arch review | `blocked` | `architecture review non-convergence` |
| Architecture missing | impl.design Design | `blocked` | `architecture stage not complete` |
| `impl.design.attempts >= max` | impl design | `blocked` | `implementation blueprint non-convergence` |
| `impl.code.attempts >= max` | impl code | `blocked` | `implementation non-convergence` |
| `verify.attempts >= max` | verify | `blocked` | `verification non-convergence` |
| `e2e.execute.attempts >= max` | e2e execute | `blocked` | `E2E browser testing non-convergence` |
| `smoke.test.attempts >= max` | smoke test | `blocked` | `smoke test non-convergence` |
| `qa.security.attempts >= max` | qa security | `blocked` | `security review non-convergence` |
| `qa.api-contract.attempts >= max` | qa api-contract | `blocked` | `API contract validation non-convergence` |
| `qa.performance.attempts >= max` | qa performance | `blocked` | `performance check non-convergence` |
| `deploy.prepare.attempts >= max` | deploy prepare | `blocked` | `deploy preparation non-convergence` |
| `doc.decisions.attempts >= max` | doc decisions | `blocked` | `decision log non-convergence` |
| `doc.project.attempts >= max` | doc project | `blocked` | `project docs non-convergence` |
| Stage timeout | Any stage | `halted` | `stage timeout exceeded` |
| User interrupt | Any | `halted` | `user interrupted` |

## Verify Resets

| Finding | Effect on State |
|---------|----------------|
| Surviving mutation | `impl.code.done = false`, `verify.done = false` — fix iteration |
| Uncovered AC | `impl.code.done = false`, `verify.done = false` — fix iteration |
| Spec-precision gap | Document, `verify.done = false` if blocking |
| Runtime evidence failure | `impl.code.done = false`, `verify.done = false` — fix iteration |
| 3 iterations still FAIL | `status: blocked`, `blocking_condition: verification non-convergence` |

## E2E Execute Resets

| Finding | Effect on State |
|---------|----------------|
| Test failure | `impl.code.done = false`, `e2e.execute.done = false` — fix iteration |
| Console error | `impl.code.done = false`, `e2e.execute.done = false` — fix iteration |
| Network 4xx/5xx | `impl.code.done = false`, `e2e.execute.done = false` — fix iteration |
| Orphaned BDD scenario | `impl.code.done = false`, `e2e.execute.done = false` — generate test |
| 3 iterations still FAIL | `status: blocked`, `blocking_condition: E2E browser testing non-convergence` |

## Smoke Test Resets

| Finding | Effect on State |
|---------|----------------|
| Journey step failure | `impl.code.done = false`, `smoke.test.done = false` — fix iteration |
| Network error | `impl.code.done = false`, `smoke.test.done = false` — fix iteration |
| Route 404 | `impl.code.done = false`, `smoke.test.done = false` — fix routing |
| 3 iterations still FAIL | `status: blocked`, `blocking_condition: smoke test non-convergence` |

## QA Stage Resets

| Stage | Finding Severity | Resets |
|-------|---------------|--------|
| `qa.security` | critical | `impl.code.done = false`, `qa.security.done = false` |
| `qa.security` | high | Auto-fix inline, re-validate |
| `qa.api-contract` | any discrepancy | `impl.code.done = false`, `qa.api-contract.done = false` |
| `qa.performance` | critical | `impl.code.done = false`, `qa.performance.done = false` |
| `qa.performance` | high | Document for optimization sprint, `qa.performance.done = false` |
| `deploy.prepare` | build/lint error | `impl.code.done = false`, `deploy.prepare.done = false` |

## Architecture Review Resets

| Finding Severity | Resets |
|-----------------|--------|
| `critical` in requirements | `arch.requirements.done = false`, `artifacts.requirements = null` |
| `critical` in solution | `arch.solution.done = false`, `artifacts.solution_architecture = null` |
| `high` | Auto-adjust inline, re-validate |
| All clear | `arch.review.done = true` → architecture stage complete |
