---
name: engineering-loop-readme
type: entry-point
description: 'Comprehensive framework documentation.'
---

# Engineering Loop v7.5.0

Persistent while-loop engine for AI-assisted development. The orchestrator delegates every phase of work to specialized sub-agents via progressive disclosure. Essence Sidecar validates inputs before every stage. All stages follow **Design → Execute → Validate**.

**Entry point:** `CORE.md`
**Orchestrator:** `ORCHESTRATOR.md`
**Configuration:** `config.yaml`

---

## Table of Contents

- [Architecture](#architecture)
- [How It Works](#how-it-works)
- [Stage Catalog](#stage-catalog)
- [Essence Sidecar](#essence-sidecar)
- [BDD Journey](#bdd-journey)
- [Cross-Stage Resets](#cross-stage-resets)
- [Self-Constructed Skills](#self-constructed-skills)
- [Configuration Reference](#configuration-reference)
- [State Management](#state-management)
- [Context Management](#context-management)
- [Directory Structure](#directory-structure)
- [Exit Conditions](#exit-conditions)
- [Invoke](#invoke)
- [Anti-Patterns](#anti-patterns)
- [Troubleshooting](#troubleshooting)

---

## Architecture

```
USER REQUEST (work item)
        │
        ▼
   ┌─────────┐
   │  INIT    │  ← Phase 0: Validate input, discover skills
   │  (once)  │
   └────┬─────┘
        │
        ▼
   ┌─────────┐
   │  INIT    │  ← BDD Journey: Full user journeys + Gherkin scenarios
   │  .BDD    │     Used as test baseline for all test stages
   │  (once)  │
   └────┬─────┘
        │
        ▼
   ┌─────────┐
   │ THE LOOP│  ← WHILE any stage not done
   │  (repeat│      Re-checks ALL stages each iteration
   │  all)   │      Essence validates inputs BEFORE every stage
   └────┬────┘
        │
        ▼
  ┌───────────┐
  │ POST-LOOP  │  ← Phase 5: Skill improvement
  │  (once)    │  ← Phase 6: Finalize + commit
  └───────────┘
```

### Design Philosophy

- **Orchestrator is pure delegation** — never executes work directly (except deploy.prepare and post-loop finalize)
- **Progressive disclosure** — stages, references, and skills loaded by ID only when needed
- **Context slicing** — each sub-agent receives only its relevant context; full artifacts are never passed to one agent
- **Full loop enforcement** — every stage must execute; user requests are focus directives, not skip directives
- **Essence before every stage** — inputs are validated before any work begins, not after

---

## How It Works

The orchestrator maintains a state table and iterates through 18 stages until all converge:

```
FOR each stage:
    1. essence.validate(stage_inputs)     ← ALWAYS runs first
    2. IF essence fails → adjust inputs, re-validate (no attempt increment)
    3. IF essence passes → invoke stage sub-agent
    4. stage executes (Design → Execute → Validate)
```

### Iteration Flow

1. **Increment iteration counter**
2. **Identify first incomplete stage** — scan state table top-to-bottom for `done: false`
3. **Essence Gate** — validate stage inputs via Four Lenses (does NOT increment attempts)
4. **Check constraint** — compare `attempts` against `config.yaml` limits; exit if exceeded
5. **Load procedure** — fetch stage file from `stages/` by ID
6. **Slice context** — determine what context the sub-agent needs
7. **Increment attempts** and **invoke sub-agent**
8. **Stop generation** — wait for sub-agent response
9. **Post-iteration** — check constraints, compact log if needed, cap findings, write state

The loop does NOT advance sequentially. It re-evaluates every stage each iteration. A stage reset to `done: false` by a downstream finding is picked up naturally on the next iteration.

### Example: First Run Walkthrough

```
Iteration 1:  init          → bmad-integration validates work item
Iteration 2:  init.bdd      → BDD journey mapper produces user journeys
Iteration 3:  design.user-research → bmad-user-research conducts user research
Iteration 4:  design.personas → bmad-personas creates personas and journey maps
Iteration 5:  design.info-arch → bmad-info-arch designs information architecture
Iteration 6:  design.interaction → bmad-interaction defines interaction patterns
Iteration 7:  design.design-system → bmad-design-system builds design system
Iteration 8:  design.visual-design → bmad-visual-design creates visual design
Iteration 9:  arch.requirements → requirements-refiner quantifies requirements
Iteration 10: arch.cloud    → cloud-architect designs AWS topology
Iteration 11: arch.solution → solution-designer designs components + APIs
Iteration=12: arch.review   → architecture-reviewer cross-checks, produces consolidated
Iteration=13: impl.design   → implementation-architect produces blueprint
Iteration=14: impl.code     → domain skill writes code
Iteration=15: impl.review   → 3 parallel reviewers, triage findings
Iteration=16: test.unit     → unit tests from BDD journey
Iteration=17: test.integration → integration tests from BDD journey
Iteration=18: test.e2e      → Playwright E2E tests from BDD journey
Iteration=19: test.qa       → QA audit verifies 100% coverage
Iteration=20: qa.security   → OWASP WSTG security audit
Iteration=21: qa.api-contract → OpenAPI contract compliance check
Iteration=22: qa.performance → bundle size, response time verification
Iteration=23: deploy.prepare → build, lint, type check, env config
Iteration=24: review        → final comprehensive adversarial review
Iteration=25: post          → skill improvement, finalize, commit
```

In practice, iterations may be higher due to stage resets from downstream findings.

---

## Stage Catalog

### 0 — INIT

- **Skill:** `bmad-integration`
- **Procedure:** `stages/init.md`
- **Purpose:** Validate work item (title, acceptance criteria, scope, intent). Discover domain skills via scoring: exact(10), adjacent(5), generic(1). Self-construct skills with score < 5.
- **Artifact:** Validated work item stored in `state.work_item`
- **On failure:** `status: blocked`, `blocking_condition: input not ready`, EXIT

### 0.5 — INIT.BDD (BDD Journey Mapping)

- **Skill:** BDD journey mapper (self-constructed from Cucumber BDD)
- **Procedure:** `stages/init-bdd.md`
- **Constraint:** `max_init_bdd_attempts` (default: 2)
- **Purpose:** Produce comprehensive user journeys with Gherkin scenarios. Every PRD feature → user journey. Every UX flow → scenario coverage. Every scenario tagged: `e2e`, `unit`, `integration`, or `component`.
- **Artifact:** `{artifact-root}/bdd-journeys/journey-{slug}.md`
- **Journey structure per flow:**
  - Actor (primary, secondary, system triggers)
  - Pre-conditions
  - Happy path (Given/When/Then)
  - Alternative paths
  - Edge cases (empty state, errors, timeouts, concurrency)
  - Post-conditions
  - Test mapping table

### 1.1 — DESIGN.USER-RESEARCH

- **Skill:** `bmad-user-research`
- **Procedure:** `stages/design-user-research.md`
- **Constraint:** `max_design_user_research_attempts` (default: 2)
- **Purpose:** Conduct user research: interviews, contextual inquiry, surveys, usability testing, competitive analysis.
- **Artifact:** `{artifact-root}/design/research-findings.md`, `research-questions.md`

### 1.2 — DESIGN.PERONAS

- **Skill:** `bmad-personas`
- **Procedure:** `stages/design-personas.md`
- **Constraint:** `max_design_personas_attempts` (default: 2)
- **Purpose:** Create personas and journey maps from research findings.
- **Artifact:** `{artifact-root}/design/personas.md`, `journey-maps.md`

### 1.3 — DESIGN.INFO-ARCH

- **Skill:** `bmad-info-arch`
- **Procedure:** `stages/design-info-arch.md`
- **Constraint:** `max_design_info_arch_attempts` (default: 2)
- **Purpose:** Design information architecture: sitemaps, wireframes, navigation patterns.
- **Artifact:** `{artifact-root}/design/sitemaps.md`, `wireframes.md`, `navigation-spec.md`

### 1.4 — DESIGN.INTERACTION

- **Skill:** `bmad-interaction`
- **Procedure:** `stages/design-interaction.md`
- **Constraint:** `max_design_interaction_attempts` (default: 2)
- **Purpose:** Define interaction patterns, component behaviors, motion principles.
- **Artifact:** `{artifact-root}/design/interaction-patterns.md`, `component-behaviors.md`, `motion-spec.md`

### 1.5 — DESIGN.DESIGN-SYSTEM

- **Skill:** `bmad-design-system`
- **Procedure:** `stages/design-design-system.md`
- **Constraint:** `max_design_design_system_attempts` (default: 2)
- **Purpose:** Build design system: tokens, components, guidelines.
- **Artifact:** `{artifact-root}/design/design-tokens.md`, `component-library.md`, `design-guidelines.md`

### 1.6 — DESIGN.VISUAL-DESIGN

- **Skill:** `bmad-visual-design`
- **Procedure:** `stages/design-visual-design.md`
- **Constraint:** `max_design_visual_design_attempts` (default: 2)
- **Purpose:** Create visual design: typography, colors, layout, micro-animations.
- **Artifact:** `{artifact-root}/design/visual-spec.md`, `visual-dos-donts.md`

### 2 — ARCH.REQUIREMENTS

- **Skill:** `requirements-refiner`
- **Procedure:** `stages/architecture.md`
- **Constraint:** `max_arch_requirements_attempts` (default: 2)
- **Purpose:** Quantify functional requirements, volumetry (users, data, traffic, storage), scalability targets (horizontal, vertical, burst), observability (logging, metrics, tracing, alerting), security requirements.
- **Artifact:** `{artifact-root}/architectures/requirements-{slug}.md`
- **Validation:** Every PRD feature → detailed user journeys. Volumetry quantified. No vague language.

### 2 — ARCH.CLOUD

- **Skill:** `cloud-architect`
- **Procedure:** `stages/architecture.md`
- **Constraint:** `max_arch_cloud_attempts` (default: 2)
- **Prerequisite:** `arch.requirements.done == true`
- **Purpose:** AWS topology (VPC, CIDR, subnets, security groups), service mapping, data storage (backup, scaling, multi-AZ), deployment pipeline, cost estimates.
- **Artifact:** `{artifact-root}/architectures/cloud-{slug}.md`
- **Validation:** Every volumetry target → addressed by a service. Every AWS service: rationale, configuration, cost.

### 3 — ARCH.SOLUTION

- **Skill:** `solution-designer`
- **Procedure:** `stages/architecture.md`
- **Constraint:** `max_arch_solution_attempts` (default: 2)
- **Prerequisite:** `arch.requirements.done == true`
- **Purpose:** Component design, data model with entity lifecycle, API contracts (request/response schemas), cross-cutting concerns (error handling, caching, auth, i18n), performance targets, tech stack justification.
- **Artifact:** `{artifact-root}/architectures/solution-{slug}.md`
- **Validation:** Every UX flow → component and data path coverage.

### 4 — ARCH.REVIEW

- **Skill:** `architecture-reviewer`
- **Procedure:** `stages/architecture.md`
- **Constraint:** `max_arch_review_attempts` (default: 2)
- **Prerequisite:** requirements + cloud + solution all `done: true`
- **Purpose:** Cross-artifact consistency (cloud ↔ solution, cloud ↔ requirements, solution ↔ requirements). Gap analysis with severity classification.
- **Artifact:** `{artifact-root}/architectures/consolidated-{slug}.md`
- **On critical finding:** Reset originating sub-stage to `done: false`, clear artifact.
- **Final gate:** Traceability matrix zero uncovered entries. No unresolved critical/high findings. All `[TBD]` and `[DECIDE LATER]` resolved or deferred.

### 5 — IMPL.DESIGN (Implementation Blueprint)

- **Skill:** `implementation-architect`
- **Procedure:** `stages/impl-design.md`
- **Constraint:** `max_impl_design_attempts` (default: 2)
- **Prerequisite:** `state.artifacts.consolidated_architecture` not null
- **Purpose:** File structure, interface contracts (request/response schemas, function signatures, event payloads), data flows (user action → component → service → database), execution order with dependency resolution, error handling strategies.
- **Artifact:** `{artifact-root}/blueprints/blueprint-{slug}.md`
- **Validation:** Every architecture decision → reflected in blueprint. Execution order → no circular dependencies.

### 6 — IMPL.CODE (Code Implementation)

- **Skill:** Domain-specific (self-constructed from internet best practices)
- **Procedure:** `stages/impl-code.md`
- **Constraint:** `max_impl_code_attempts` (default: 3)
- **Prerequisite:** `state.artifacts.blueprint` not null
- **Purpose:** Execute ALL blueprint tasks in order. Follow file structure exactly. Implement interface contracts. Follow data flows. Implement error handling. No speculative features.
- **Validation:** Inline validator compares code against blueprint. Checks: files exist, contracts implemented, data flows match, error handling followed, ACs addressed, no speculative features.
- **Result:** conformant → `done: true`. missing/high deviation → auto-fix, `done: false`. medium/low deviation → auto-fix, `done: true`.

### 7 — IMPL.REVIEW (Code Review)

- **Skill:** 3 parallel inline reviewers
- **Procedure:** `stages/impl-review.md`
- **Constraint:** `max_impl_review_attempts` (default: 2)
- **Prerequisite:** `state.stages.impl.code.done == true`
- **Reviewers:**
  - **Blind Hunter:** Security, data integrity, error handling, spec deviations, architecture
  - **Edge Case Hunter:** Boundaries, null paths, race conditions, validation gaps, state management
  - **Test Coverage Auditor:** AC and BDD scenario coverage audit

### 8 — TEST.UNIT (Unit Tests)

- **Skill:** Domain-specific (self-constructed from project test patterns)
- **Procedure:** `stages/test-unit.md`
- **Constraint:** `max_test_unit_attempts` (default: 3)
- **Prerequisite:** `state.stages.impl.code.done == true`
- **Purpose:** Component-level isolation tests. Each BDD scenario tagged `unit` → corresponding test. Mock external dependencies (APIs, DB, file system). Test happy path and error conditions.
- **Artifact:** `{artifact-root}/test-plans/unit-{slug}.md`
- **Quality criteria:** One behavior per test. Isolated (no shared state). Specific assertions. Edge cases covered. Descriptive test names.

### 9 — TEST.INTEGRATION (Integration Tests)

- **Skill:** Domain-specific (self-constructed from project test patterns)
- **Procedure:** `stages/test-integration.md`
- **Constraint:** `max_test_integration_attempts` (default: 3)
- **Prerequisite:** `state.stages.test.unit.done == true`
- **Purpose:** Service and API interaction tests. Each BDD scenario tagged `integration` → corresponding test. Test actual component interactions (not mocked). Test database with test data. Validate API contracts (request/response, status codes, error responses).
- **Artifact:** `{artifact-root}/test-plans/integration-{slug}.md`

### 10 — TEST.E2E (E2E Tests)

- **Skill:** `e2e-playwright`
- **Procedure:** `stages/test-e2e.md`
- **Constraint:** `max_test_e2e_attempts` (default: 3)
- **Prerequisite:** `state.stages.test.integration.done == true`
- **Purpose:** User flow tests via Playwright. Each BDD scenario tagged `e2e` → corresponding Playwright test. Use resilient locators (`getByRole`, `getByLabel`, `getByTestId`). Test across browsers (Chromium minimum).
- **Artifact:** `{artifact-root}/test-plans/e2e-{slug}.md`
- **Playwright patterns:** Auto-waiting (no artificial timeouts). Fresh browser context per test. Parallel execution. Trace viewer for failures.

### 11 — TEST.QA (QA Audit)

- **Skill:** Inline auditor
- **Procedure:** `stages/test-qa.md`
- **Constraint:** `max_test_qa_attempts` (default: 2)
- **Prerequisite:** `state.stages.test.e2e.done == true`
- **Purpose:** Coverage verification against BDD Journey. For each scenario: verify test exists, asserts expected outcome, sets up preconditions, triggers correct action.
- **Result:** 100% covered → `done: true`. Gaps → reset originating test stage to `done: false`.

### 12 — QA.SECURITY (Security Review)

- **Skill:** Security reviewer (self-constructed from OWASP WSTG)
- **Procedure:** `stages/qa-security.md`
- **Constraint:** `max_qa_security_attempts` (default: 2)
- **Prerequisite:** `state.stages.test.qa.done == true`
- **Audit categories (OWASP WSTG):**
  - **Authentication (4.4):** OAuth flow, credential transport, session handling
  - **Authorization (4.5):** Privilege escalation, IDOR, role enforcement
  - **Input Validation (4.7):** XSS, SQL injection, NoSQL injection, command injection
  - **Session Management (4.6):** Cookie attributes, session fixation, CSRF
  - **Configuration (4.2):** Security headers, HTTP methods, file permissions
  - **API Security (4.12):** BOLA, excessive data exposure, BFLA
  - **Client-Side (4.11):** DOM XSS, CORS, clickjacking, browser storage
  - **Cryptography (4.9):** TLS, sensitive data in transit, weak primitives
  - **Error Handling (4.8):** Stack traces, information leakage
  - **Business Logic (4.10):** Workflow circumvention, rate limiting
- **Severity:** Critical → reset `impl.code.done = false`. High → auto-fix inline, re-validate.
- **Reference:** https://owasp.org/www-project-web-security-testing-guide/

### 13 — QA.API-CONTRACT (API Contract Validation)

- **Skill:** API contract validator (self-constructed from OpenAPI)
- **Procedure:** `stages/qa-api-contract.md`
- **Constraint:** `max_qa_api_contract_attempts` (default: 2)
- **Prerequisite:** `state.stages.qa.security.done == true`
- **Audit checklist:**
  - Endpoint completeness (every blueprint endpoint exists)
  - Method compliance (HTTP methods match contract)
  - Request schema (types, required fields)
  - Response schema (types, required fields)
  - Status codes (correct for success and error)
  - Authentication (protected endpoints require auth)
  - Error format (follows contract error schema)
  - Pagination, rate limiting, content negotiation
- **Discrepancy types:** Missing, type mismatch, required missing, response drift, wrong status code
- **On discrepancy:** Reset `impl.code.done = false`
- **Reference:** https://swagger.io/docs/specification/about/

### 14 — QA.PERFORMANCE (Performance Check)

- **Skill:** Performance checker (self-constructed from web performance best practices)
- **Procedure:** `stages/qa-performance.md`
- **Constraint:** `max_qa_performance_attempts` (default: 2)
- **Prerequisite:** `state.stages.qa.api-contract.done == true`
- **Metrics checklist:**
  - Bundle size < 500KB initial (gzip)
  - First Contentful Paint < 1.5s
  - Time to Interactive < 3.5s
  - API response time < 200ms (p95)
  - Database query time < 50ms (simple)
  - Image optimization (WebP/AVIF, lazy loading)
  - Code splitting (route-based), caching strategy, font loading, critical CSS
- **Architecture checks:** CDN configuration, database indexing, connection pooling, caching layers, async processing, pagination
- **Severity:** Critical (>2x target exceeded) → reset `impl.code.done = false`. High (>50% exceeded) → document for optimization sprint.

### 15 — DEPLOY.PREPARE (Deploy Preparation)

- **Skill:** Orchestrator executes directly
- **Procedure:** `stages/deploy-prepare.md`
- **Constraint:** `max_deploy_prepare_attempts` (default: 2)
- **Prerequisite:** `state.stages.qa.performance.done == true`
- **Checklist:**
  1. **Build:** Production build succeeds, zero errors, output size checked
  2. **Lint:** Zero lint errors, warnings logged
  3. **Type check:** Zero type errors
  4. **Environment config:** `.env.example` complete, no secrets committed
  5. **Database migrations:** Files exist, ordered, rollback capable
  6. **Deploy artifacts:** Dockerfile, CI/CD config, deployment scripts, health checks
  7. **Final verification:** Full test suite passes, build artifacts clean
- **On failure:** Reset `impl.code.done = false`

### 16 — REVIEW (Final Comprehensive Review)

- **Skill:** 3 parallel inline reviewers
- **Procedure:** `stages/review.md`
- **Constraint:** `max_review_attempts` (default: 2)
- **Prerequisite:** `state.stages.deploy.prepare.done == true`
- **Reviewers:** Blind Hunter, Edge Case Hunter, Test Coverage Auditor
- **Triage categories:** See [Cross-Stage Resets](#cross-stage-resets)

### 17 — POST-LOOP

- **Skill:** Orchestrator executes directly
- **Procedure:** `stages/post-loop.md`
- **Phase 5 (Skill Improvement):** Extract lessons (KEEP / IMPROVE / ADD). Update each skill's SKILL.md. Record in `skill-index.md`.
- **Phase 6 (Finalize):** All tasks `[x]`. Full test suite passes. Lint/build passes. Update work item: `status: done`, `final_revision`, `review_loop_iteration`. Commit (do not push). Finalize log. Report summary to user.

---

## Essence Sidecar

Runs BEFORE every stage. Validates that stage inputs are sound before any work begins.

### The Four Lenses

| Lens | Focus | Findings |
|------|-------|----------|
| 1 | Subjective terms | Ambiguous language, opinion-based statements |
| 2 | Hidden assumptions | Unstated dependencies, implicit requirements |
| 3 | Literal traps | Phrasing that invites wrong LLM interpretation |
| 4 | Conflicting priorities | Competing goals that need human resolution |

### Execution Flow

1. Gather inputs for the upcoming stage
2. Launch essence sub-agent with context slice: `{stage_inputs}` + `{work_item}`
3. **Lenses 1-3 findings:** Adjust inputs inline, re-run Essence (does NOT increment attempts)
4. **Lens 4 tension:** Escalate to user for resolution, await confirmation
5. **Clean:** Set `essence_checked = true`, proceed to stage

### Essence Input Per Stage

| Stage | Essence Validates |
|-------|-------------------|
| `init` | Work item completeness, clarity of intent |
| `init.bdd` | PRD features, UX flows, user stories sufficient for journey mapping |
| `init.refine` | Idea refinement inputs are clear and actionable |
| `design.user-research` | PRD, existing research, external sources available |
| `design.personas` | Research findings, PRD, external sources available |
| `design.info-arch` | Personas, journeys, PRD, research available |
| `design.interaction` | Wireframes, IA, personas, journeys available |
| `design.design-system` | Interaction patterns, wireframes, brand assets available |
| `design.visual-design` | Design tokens, component library, brand assets available |
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

---

## BDD Journey

The `init.bdd` stage produces a comprehensive BDD Journey document that serves as the **single source of truth for testing**.

### Structure

Each user journey follows the BDD three-practice model:

1. **Discovery** — What the system could do (user perspectives, real-world examples)
2. **Formulation** — What the system should do (Gherkin scenarios, structured documentation)
3. **Automation reference** — What the system actually does (test mappings)

### Journey Document Format

```markdown
## User Journey: {journey-name}

### Actor
- Primary actor, secondary actors, system triggers

### Pre-conditions
- System state before journey begins

### Happy Path
Given {context}
When {action}
Then {outcome}

### Alternative Paths
- Branch A: {scenario}
- Branch B: {scenario}

### Edge Cases
- Empty state
- Error conditions
- Timeout scenarios
- Concurrent actions

### Post-conditions
- System state after journey completion

### Test Mapping
| Scenario | Type | Priority |
|----------|------|----------|
| {name} | e2e/unit/integration | high/medium/low |
```

### Test Flow

The BDD Journey feeds all test stages:

```
BDD Journey (init.bdd)
    │
    ├── scenarios tagged "unit"        → test.unit
    ├── scenarios tagged "integration" → test.integration
    ├── scenarios tagged "e2e"         → test.e2e
    └── full journey                   → test.qa (100% coverage audit)
```

---

## Cross-Stage Resets

Downstream stages can reset upstream stages to `done: false`, triggering re-execution.

### Architecture Review Resets

| Finding Severity | Resets |
|-----------------|--------|
| `critical` in requirements | `arch.requirements.done = false`, `artifacts.requirements = null` |
| `critical` in cloud | `arch.cloud.done = false`, `artifacts.cloud_architecture = null` |
| `critical` in solution | `arch.solution.done = false`, `artifacts.solution_architecture = null` |
| `high` | Auto-adjust inline, re-validate |

### Review Triage Resets

| Finding Category | Effect on State |
|-----------------|----------------|
| `intent_gap` | `status: blocked`. **EXIT.** |
| `bad_spec` | Amend work item. `impl.design.done = false`, `blueprint = null`, `review.done = false` |
| `architecture_gap` | `arch.review.done = false`, `consolidated_architecture = null`, `impl.design.done = false`, `blueprint = null`, `review.done = false` |
| `patch` | Auto-fix. If tests fail: `impl.code.done = false`, `test.unit.done = false`, `review.done = false` |
| `defer` | Append to `deferred-work.md` |
| `reject` | Drop |

### QA Stage Resets

| Stage | Finding Severity | Resets |
|-------|---------------|--------|
| `qa.security` | critical | `impl.code.done = false`, `qa.security.done = false` |
| `qa.security` | high | Auto-fix inline, re-validate |
| `qa.api-contract` | any discrepancy | `impl.code.done = false`, `qa.api-contract.done = false` |
| `qa.performance` | critical | `impl.code.done = false`, `qa.performance.done = false` |
| `qa.performance` | high | Document for optimization sprint, `qa.performance.done = false` |
| `deploy.prepare` | build/lint error | `impl.code.done = false`, `deploy.prepare.done = false` |

### Reset Flow Diagram

```
qa.security (critical)  ──→  impl.code (done: false)  ──→  impl.review (done: false)
                                                                    │
qa.api-contract (any)    ──→  impl.code (done: false)  ────────────┘
                                                                    │
qa.performance (critical) ──→  impl.code (done: false)  ──→  test.unit (done: false)
                                                                    │
deploy.prepare (error)   ──→  impl.code (done: false)  ──→  test.integration (done: false)
                                                                    │
review (bad_spec)        ──→  impl.design (done: false) ──→  test.e2e (done: false)
                                                                    │
review (architecture_gap)──→  arch.review (done: false) ──→  test.qa (done: false)
                                                                       │
                                                                       ▼
                                                                    re-enter loop
```

---

## Self-Constructed Skills

Skills marked as "self-constructed" are discovered and created at runtime from internet best practices.

| Skill | Source | Stage |
|-------|--------|-------|
| BDD Journey Mapper | Cucumber BDD, Example Mapping | `init.bdd` |
| Domain Skill | Project tech stack, internet best practices | `impl.code` |
| Unit Test Author | Project test patterns, framework docs | `test.unit` |
| Integration Test Author | Project test patterns, framework docs | `test.integration` |
| Security Reviewer | OWASP Web Security Testing Guide (WSTG) | `qa.security` |
| API Contract Validator | OpenAPI Specification, Swagger | `qa.api-contract` |
| Performance Checker | Web performance best practices, Lighthouse | `qa.performance` |

### Self-Construction Process

1. Classify domain(s) from work item
2. Scan `{skill-root}/` + system skills. Score: exact(10), adjacent(5), generic(1)
3. If score < 5 → self-construct via `skill-creator` + `{reference-root}/skill-templates.md`
4. Search internet for best practices, patterns, and reference implementations
5. Register in `state.skills` and `skill-index.md`

---

## Configuration Reference

All settings in `config.yaml`. Nothing is hardcoded.

### Framework Paths

| Key | Default | Purpose |
|-----|---------|---------|
| `artifact_root` | `.engineering-loop/artifacts` | Runtime output directory |
| `log_root` | `_bmad-output/process-logs` | Process log files |
| `skill_root` | `.engineering-loop/skills` | Specialized skills |
| `reference_root` | `.engineering-loop/references` | Shared references |
| `stage_root` | `.engineering-loop/stages` | Stage procedures |
| `planning_artifacts_root` | `_bmad-output/implementation-artifacts` | BMad planning artifacts |

### Constraints

| Key | Default | Purpose |
|-----|---------|---------|
| `max_init_bdd_attempts` | 2 | BDD journey mapping max iterations |
| `max_init_refine_attempts` | 5 | Idea refinement max iterations |
| `max_design_user_research_attempts` | 2 | User research max iterations |
| `max_design_personas_attempts` | 2 | Personas max iterations |
| `max_design_info_arch_attempts` | 2 | Information architecture max iterations |
| `max_design_interaction_attempts` | 2 | Interaction design max iterations |
| `max_design_design_system_attempts` | 2 | Design system max iterations |
| `max_design_visual_design_attempts` | 2 | Visual design max iterations |
| `max_arch_requirements_attempts` | 2 | Requirements refinement max iterations |
| `max_arch_cloud_attempts` | 2 | Cloud architecture max iterations |
| `max_arch_solution_attempts` | 2 | Solution design max iterations |
| `max_arch_review_attempts` | 2 | Architecture review max iterations |
| `max_impl_design_attempts` | 2 | Implementation blueprint max iterations |
| `max_impl_code_attempts` | 3 | Code implementation max iterations |
| `max_impl_review_attempts` | 2 | Implementation review max iterations |
| `max_test_unit_attempts` | 3 | Unit test max iterations |
| `max_test_integration_attempts` | 3 | Integration test max iterations |
| `max_test_e2e_attempts` | 3 | E2E test max iterations |
| `max_test_qa_attempts` | 2 | QA audit max iterations |
| `max_qa_security_attempts` | 2 | Security review max iterations |
| `max_qa_api_contract_attempts` | 2 | API contract validation max iterations |
| `max_qa_performance_attempts` | 2 | Performance check max iterations |
| `max_deploy_prepare_attempts` | 2 | Deploy preparation max iterations |
| `max_review_attempts` | 2 | Final review max iterations |
| `require_design_phase` | true | Design phase mandatory before architecture |
| `require_e2e_user_facing` | true | E2E mandatory for user-facing features |
| `require_100_coverage` | true | BDD Journey 100% test coverage |

### Hardware Management

| Key | Default | Purpose |
|-----|---------|---------|
| `context_window` | 200000 | Total available context tokens |
| `context_safety_margin` | 0.15 | Reserve 15% (30K buffer) |
| `max_parallel_agents` | 3 | Max concurrent sub-agents |
| `agent_context_limit` | 66666 | Max tokens per sub-agent |
| `stage_timeout_seconds` | 300 | Max seconds per stage execution |
| `max_artifact_size_lines` | 300 | Cap artifact file size |
| `max_findings_buffer` | 50 | Cap accumulated findings |
| `compact_log_after_iteration` | 3 | Compact log after N iterations |

### Essence

| Key | Default | Purpose |
|-----|---------|---------|
| `essence.enabled` | true | Enable Essence Sidecar |
| `essence.skill` | `essence` | Skill name for Essence sub-agent |
| `essence.run_before_stage` | true | Always runs before stage invocation |

### Self-Construction

| Key | Default | Purpose |
|-----|---------|---------|
| `skill_creator` | `skill-creator` | Skill for self-constructing new skills |
| `template_path` | `.engineering-loop/references/skill-templates.md` | Templates for new skills |

---

## State Management

### State Table Variables

Each stage tracks three variables:

| Variable | Type | Purpose |
|----------|------|---------|
| `stages.{id}.done` | boolean | Whether stage is complete |
| `stages.{id}.attempts` | integer | Number of attempts (checked against constraints) |
| `stages.{id}.essence_checked` | boolean | Whether Essence Sidecar validated inputs |

Global variables:

| Variable | Type | Purpose |
|----------|------|---------|
| `iteration` | integer | Current loop iteration count |
| `status` | enum | `running` / `done` / `blocked` / `halted` |
| `blocking_condition` | string | Reason for blocked/halted status |

### Log File

Every iteration writes to `{log_root}/engineering/{run_id}-{slug}.md`:

- **Frontmatter:** run_id, workflow, trigger, timestamps, work item path
- **State table:** All stage variables (updated every iteration)
- **Iteration log:** Table of iteration number, stage, action, result, details
- **Details:** Phase-specific details appended each iteration

### Compaction

Trigger: `state.iteration >= compact_log_after_iteration AND state.iteration % compact_log_after_iteration == 0`

1. Keep: frontmatter, current state table, last 5 iteration log rows
2. Discard: phase details from iterations older than (current - 2)
3. Summarize: old findings into counts by category
4. Rewrite log file with compacted content

### Findings Buffer

`state.findings` capped at `max_findings_buffer`. When exceeded:

1. Sort by severity (high → medium → low)
2. Keep top N highest-severity
3. Summarize remaining: `summarized: {count} (high: N, medium: N, low: N)`

---

## Context Management

### Progressive Disclosure

The orchestrator loads only what's needed, when it's needed:

- **Stages** — loaded by ID from `stages/` only when that stage is selected
- **References** — loaded by ID from `references/` only when referenced
- **Skills** — loaded from `skills/` only when invoking a sub-agent
- **Index of all stages and references:** `CORE.md`

### Context Slicing

Each sub-agent receives only its relevant context slice. Total tokens across all agents must stay within `context_window - (context_window * context_safety_margin)`.

| Agent | Receives | Does NOT receive |
|-------|----------|-----------------|
| Blind Hunter | diff + work item + blueprint (relevant sections) | BDD journey, review plan |
| Edge Case Hunter | work item + I/O matrix + diff (edge-case areas) | full blueprint, BDD journey |
| Test Coverage Auditor | BDD journey + ACs + test file paths | full diff, blueprint |
| Impl Validate | diff + blueprint + work item | BDD journey, review plan |
| QA Validate | BDD journey + test files | diff, blueprint |
| Security Reviewer | diff + blueprint + architecture | test files |
| API Contract Validator | blueprint + API source + integration tests | E2E tests, full diff |
| Performance Checker | blueprint + architecture + build output | test files |

**Rule:** Never pass the full set of artifacts to any single sub-agent.

---

## Directory Structure

```
.engineering-loop/
├── ORCHESTRATOR.md          # Orchestrator role, loop algorithm, delegation rules
├── CORE.md                  # Stage + reference index (discovery map)
├── README.md                # This file
├── config.yaml              # Constraints, paths, hardware settings
├── skill-index.md           # Skill registry with improvement log
├── stages/                  # Stage procedures (loaded by ID)
│   ├── init.md              # Phase 0: validate input + discover skills
│   ├── init-bdd.md          # BDD Journey: user journeys + Gherkin scenarios
│   ├── architecture.md      # 4 sub-stages: requirements → cloud → solution → review
│   ├── impl-design.md       # Implementation blueprint
│   ├── impl-code.md         # Code implementation
│   ├── impl-review.md       # Code review (3 parallel reviewers)
│   ├── test-unit.md         # Unit tests
│   ├── test-integration.md  # Integration tests
│   ├── test-e2e.md          # E2E tests (Playwright)
│   ├── test-qa.md           # QA audit (coverage verification)
│   ├── qa-security.md       # Security review (OWASP WSTG)
│   ├── qa-api-contract.md   # API contract validation (OpenAPI)
│   ├── qa-performance.md    # Performance check
│   ├── deploy-prepare.md    # Build, lint, env config, migrations
│   ├── review.md            # Final comprehensive review
│   └── post-loop.md         # Phase 5+6: skill improvement + finalize
├── references/              # Shared references (loaded on demand)
│   ├── anti-patterns.md     # Global anti-patterns
│   ├── essence-sidecar.md   # Four Lenses validation (runs BEFORE every stage)
│   ├── exit-conditions.md   # Exit conditions + cross-stage resets
│   ├── hardware-management.md  # Context slicing, compaction, caps
│   ├── logging.md           # Log format + state table template
│   ├── skill-discovery-guide.md  # Skill discovery process
│   └── skill-templates.md   # Self-construction templates
├── skills/                  # Specialized skills
│   ├── requirements-refiner/
│   ├── cloud-architect/
│   ├── solution-designer/
│   ├── architecture-reviewer/
│   ├── implementation-architect/
│   ├── bmad-bdd-mapper/
│   ├── e2e-playwright/
│   └── bmad-integration/
└── artifacts/               # Runtime output (per run)
    ├── bdd-journeys/        # BDD journey documents
    ├── design/              # Design artifacts: research, personas, IA, interaction, design system, visual design
    ├── architectures/       # Requirements, cloud, solution, consolidated
    ├── blueprints/          # Implementation blueprints
    ├── test-plans/          # Unit, integration, E2E test plans
    └── review-plans/        # Review plans
```

---

## Exit Conditions

| Condition | Where | Status | blocking_condition |
|-----------|-------|--------|-------------------|
| All stages done | WHILE false | `done` | — |
| Input invalid | Phase 0 | `blocked` | `input not ready for engineering` |
| Skill creation fails | Phase 1 | `blocked` | `no suitable skill available` |
| `init.bdd.attempts >= max` | init BDD | `blocked` | `BDD journey mapping non-convergence` |
| `arch.*.attempts >= max` | arch sub-stage | `blocked` | `{sub-stage} non-convergence` |
| Architecture missing | impl.design | `blocked` | `architecture stage not complete` |
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
| `intent_gap` | review triage | `blocked` | `intent gap` |
| Stage timeout | Any stage | `halted` | `stage timeout exceeded` |
| User interrupt | Any | `halted` | `user interrupted` |

---

## Invoke

Load `CORE.md` and provide a work item (spec file, ticket, or description). The orchestrator will:

1. **Validate input** (INIT) — ensure work item has title, ACs, scope, intent
2. **Discover skills** (INIT) — scan existing skills, self-construct missing ones
3. **Map BDD journeys** (INIT.BDD) — produce user journeys with Gherkin scenarios
4. **Run the full loop** — through all 18 stages with Essence gates
5. **Finalize and commit** (POST-LOOP) — improve skills, commit changes

---

## Anti-Patterns

### Loop Mechanics

- **Never treat stages as sequential** — the loop re-evaluates ALL stages every iteration
- **Never break the loop prematurely** — only exit via all stages done or constraint breach
- **Never reset attempt counters mid-loop** — counters persist across all iterations
- **Never advance without convergence** — the architecture gate is mandatory
- **Never skip stages on user request** — user requests are focus directives, not skip directives

### Essence Gate

- **Always run Essence BEFORE every stage** — validates inputs before any work begins
- **Never run Essence after a stage** — it is a pre-stage gate, not a post-stage check
- **Never skip Essence** — every stage must pass the Four Lenses before invocation
- **Never increment attempts for Essence** — Essence loop is internal to the pre-stage gate

### Skill Usage

- **Never use a generic sub-agent for implementation** — always route through a specialized skill
- **Never self-construct a generic skill** — skills must be domain-specific
- **Never skip skill improvement** — each run makes skills better

### Design → Execute → Validate

- **Never skip Design** — every stage produces a blueprint before execution
- **Never skip Validate** — every execution is verified against its design

### Context Management

- **Never pass full context to a sub-agent** — always use context slicing
- **Never exceed agent_context_limit** — each sub-agent has its own token budget
- **Never let findings buffer grow unbounded** — cap at `max_findings_buffer`
- **Never skip log compaction** — context overflow will crash the loop

### Testing & Review

- **Never skip review** — even for trivial changes
- **Never skip tests** — unit + E2E for user-facing features
- **Never skip E2E** — every user-facing flow needs E2E coverage
- **Never defer findings caused by this change** — defer is only for pre-existing issues
- **Never over-classify as reject** — when in doubt, prefer defer

---

## Troubleshooting

### Stage Won't Converge (Attempts Exhausted)

**Symptom:** `status: blocked`, `blocking_condition: {stage} non-convergence`

**Diagnosis:**
1. Check process log: `{log_root}/engineering/{run_id}-{slug}.md`
2. Review iteration log for patterns — are the same gaps appearing each attempt?
3. Check Essence findings — are inputs ambiguous?

**Resolution:**
- Increase `max_{stage}_attempts` in `config.yaml`
- Improve work item clarity (more specific ACs, clearer scope)
- Review upstream stage artifacts for completeness

### Essence Keeps Failing

**Symptom:** Stage never invokes, Essence loops indefinitely

**Diagnosis:**
1. Lens 1-3: Inputs have ambiguous language or hidden assumptions
2. Lens 4: Conflicting priorities require human resolution

**Resolution:**
- For Lenses 1-3: Adjust inputs inline, clarify ambiguous terms
- For Lens 4: Resolve priority tension, provide explicit direction

### Context Overflow

**Symptom:** Sub-agent responses are truncated or loop crashes

**Diagnosis:**
1. Check `agent_context_limit` vs actual context size
2. Verify context slicing is applied (full artifacts should never pass to one agent)

**Resolution:**
- Increase `context_window` in `config.yaml`
- Reduce `agent_context_limit` and enforce stricter slicing
- Run log compaction manually

### Cross-Stage Reset Loop

**Symptom:** Same stages keep resetting (e.g., impl.code → qa.security → impl.code)

**Diagnosis:**
1. Check findings buffer for recurring critical findings
2. Review if the root cause is in the blueprint (impl.design) or architecture

**Resolution:**
- If blueprint is wrong: reset `impl.design.done = false` and fix blueprint
- If architecture is wrong: reset `arch.review.done = false` and fix architecture
- If it's a fundamental spec issue: consider `intent_gap` — may need human clarification

### Skill Self-Construction Fails

**Symptom:** `status: blocked`, `blocking_condition: no suitable skill available`

**Diagnosis:**
1. Domain is too novel for internet-based discovery
2. Skill templates are insufficient for the domain

**Resolution:**
- Manually create the skill in `{skill-root}/`
- Provide more domain context in the work item
- Use a generic skill as fallback and specialize later
