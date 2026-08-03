---
name: engineering-loop-readme
type: entry-point
description: 'Comprehensive framework documentation.'
---

# Engineering Loop v10.2

Persistent **while-loop engine** for AI-assisted software development. Auto-sizes depth by complexity. Delegates every phase to specialized sub-agents via progressive disclosure. Validates all inputs with the Essence Sidecar before any work begins. Self-improves through lessons learned across projects.

| | |
|---|---|
| **Version** | 10.2.0 |
| **Architecture** | Multi-project via git submodule |
| **Stages** | 24 stages across 7 phases |
| **Skills** | 11 built-in + 7 self-constructed at runtime |
| **Entry point** | `CORE.md` |
| **Orchestrator** | `ORCHESTRATOR.md` |
| **Configuration** | `config-template.yaml` (framework) + `config.yaml` (project) |

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [The Loop](#the-loop)
- [Auto-Sizing](#auto-sizing)
- [Multi-Project](#multi-project)
- [Stage Catalog](#stage-catalog)
- [BMAD Ideation](#bmad-ideation)
- [Essence Sidecar](#essence-sidecar)
- [BDD Journey](#bdd-journey)
- [E2E & Smoke Testing](#e2e--smoke-testing)
- [Cross-Stage Resets](#cross-stage-resets)
- [Self-Constructed Skills](#self-constructed-skills)
- [Continuous Decisions](#continuous-decisions)
- [Lessons System](#lessons-system)
- [Knowledge Graph](#knowledge-graph)
- [Configuration Reference](#configuration-reference)
- [State Management](#state-management)
- [Context Management](#context-management)
- [Directory Structure](#directory-structure)
- [Exit Conditions](#exit-conditions)
- [Anti-Patterns](#anti-patterns)
- [Troubleshooting](#troubleshooting)
- [Version History](#version-history)

---

## Overview

Engineering Loop is a framework for orchestrating AI sub-agents through the complete software development lifecycle. Instead of a linear pipeline, it operates as a **persistent while-loop** that re-evaluates every stage on each iteration, allowing downstream findings to trigger upstream rework automatically.

### Core Principles

- **Orchestrator is pure delegation** — never executes work directly (except `deploy.prepare` and `post-loop` finalize)
- **Progressive disclosure** — stages, references, and skills loaded by ID only when needed
- **Context slicing** — each sub-agent receives only its relevant context; full artifacts are never passed to one agent
- **Full loop enforcement** — every active stage must execute; user requests are focus directives, not skip directives
- **Essence before every stage** — inputs validated through Four Lenses before any work begins
- **Auto-sizing** — complexity classification determines which stages are active (small → complex)
- **TDD per task** — test-first implementation with red-green-commit per atomic task
- **Independent verification** — author ≠ verifier; discrimination sensor confirms test quality
- **Multi-project isolation** — each project has its own config, state, and artifacts
- **Shared lessons** — confirmed lessons propagate across all projects via the framework
- **Continuous decisions** — every architectural decision recorded as `AD-NNN` immediately, not deferred

### Design vs. Execute vs. Validate

Every stage follows a three-phase pattern:

```
┌─────────────────────────────────────────────┐
│              STAGE PROCEDURE                 │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  DESIGN   │→│ EXECUTE   │→│ VALIDATE  │  │
│  │ Plan what │  │ Do the   │  │ Check if │  │
│  │ to do     │  │ work     │  │ it's right│  │
│  └──────────┘  └──────────┘  └──────────┘  │
│                                              │
│  Essence gate runs BEFORE the stage enters   │
│  this procedure.                             │
└─────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Add as Git Submodule

```bash
git submodule add <engineering-loop-url> .eng
git commit -m "Add engineering loop framework"
```

### 2. Run Setup

**Linux / Mac / WSL:**
```bash
bash .eng/setup/install.sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File .eng\setup\install.ps1
```

The setup script:
- Copies `config-template.yaml` → `config.yaml`
- Copies `state-template.json` → `state.json`
- Creates the `artifacts/` directory structure
- Generates project `.gitignore`

### 3. Customize Configuration

Review `.eng/config.yaml` and adjust constraints, hardware limits, and paths as needed.

### 4. Start Using

Load `ORCHESTRATOR.md` in your AI agent session and provide a work item (spec file, ticket, or description). The orchestrator auto-detects all paths and begins the loop.

---

## Architecture

```
USER REQUEST (work item)
        │
        ▼
   ┌─────────┐
   │  INIT    │  ← Phase 0: Validate input, discover skills, init paths, auto-size
   │  (once)  │     If raw/ad-hoc → init.ideate (Party Mode + Brainstorming + SDD)
   └────┬─────┘
        │
        ▼
   ┌─────────┐
   │ INIT.BDD │  ← BDD Journey: Full user journeys + Gherkin scenarios (large+)
   │  (once)  │     Serves as single source of truth for all test stages
   └────┬─────┘
        │
        ▼
   ┌─────────┐
   │  DESIGN  │  ← Phases 1-3: User research → Architecture (auto-sized, large+)
   │ (0-9     │     6 design stages, 3 architecture stages, optional review
   │  stages) │
   └────┬─────┘
        │
        ▼
   ┌─────────┐
   │  IMPL    │  ← Phase 4: Blueprint → TDD code implementation
   │          │     doc.update refreshes existing project files
   └────┬─────┘
        │
        ▼
   ┌─────────┐
   │THE LOOP │  ← WHILE any active stage not done
   │(repeat  │     Re-checks ALL stages each iteration
   │ all)    │     Essence validates inputs BEFORE every stage
   └────┬─────┘
        │
        ▼
   ┌───────────┐
   │    QA      │  ← Phase 4: Security, API contract, Performance (auto-sized)
   └────┬───────┘
        │
        ▼
   ┌───────────┐
   │ DEPLOY +  │  ← Phase 4: Build, lint, test, smoke test (UI projects)
   │   DOC     │  ← Phase 5: Decision log (MADR), project docs (arc42 + C4)
   └────┬───────┘
        │
        ▼
   ┌───────────┐
   │ POST-LOOP  │  ← Phase 6: Skill improvement + share lessons + finalize
   │  (once)    │
   └───────────┘
```

### Component Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                            │
│  Pure delegation — manages state, constraints, context slices   │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ State Engine  │  │ Constraint   │  │  Context Slicer       │ │
│  │ 24 stages,    │  │ Monitor per- │  │  Token budgets,       │ │
│  │ iteration,    │  │ stage limits │  │  artifact selection   │ │
│  │ decisions     │  │ Loop safety  │  │  Safety margins       │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  ESSENCE GATE (pre-stage)                 │  │
│  │  Four Lenses: Subjective terms, Assumptions,             │  │
│  │  Literal traps, Conflicting priorities                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Delegates to →  ┌─────────┐ ┌─────────┐ ┌─────────┐ ...      │
│                   │Sub-agent│ │Sub-agent│ │Sub-agent│          │
│                   │(skill + │ │(skill + │ │(skill + │          │
│                   │ context)│ │ context)│ │ context)│          │
│                   └─────────┘ └─────────┘ └─────────┘          │
└────────────────────────────────────────────────────────────────┘
```

---

## The Loop

The orchestrator maintains a state table and iterates through stages until all converge. It does **not** advance sequentially — it re-evaluates every stage each iteration.

### Iteration Flow

```
FOR each iteration:
    1. Increment iteration counter
    2. Identify first incomplete stage (scan state table top-to-bottom)
    3. Essence Gate — validate stage inputs via Four Lenses (does NOT increment attempts)
    4. Check constraint — compare attempts against config.yaml limits; exit if exceeded
    5. Load procedure — fetch stage file from {stage-root}/ by ID
    6. Slice context — determine what context the sub-agent needs
    7. Increment attempts and invoke sub-agent
    8. STOP generation — wait for sub-agent response
    9. Extract AD-NNN decisions from stage output
    10. Post-iteration — check constraints, compact log if needed, cap findings, write state
```

A stage reset to `done: false` by a downstream finding (e.g., a security vulnerability found in `qa.security` resets `impl.code`) is picked up naturally on the next iteration.

### Loop Safety

| Guard | Limit | Default |
|-------|-------|---------|
| `max_loop_iterations` | Total loop iterations | 50 |
| `max_subagent_invocations_per_stage` | Sub-agent calls per stage | 3 |
| `max_essence_retries_per_stage` | Essence validation retries | 5 |
| `stage_timeout_seconds` | Maximum seconds per stage | 300 |

---

## Auto-Sizing

Complexity determines depth — not a fixed pipeline. The orchestrator classifies each work item before the loop begins using configurable heuristics.

| Level | Files | Tasks | Design | Architecture | QA Stages | Verify | Example |
|-------|-------|-------|--------|-------------|-----------|--------|---------|
| **Small** | ≤ 3 | ≤ 3 | Skip | Skip | Skip | Spec check only | Bug fix, config change |
| **Medium** | ≤ 10 | ≤ 8 | Inline | Requirements + Solution | Security + API contract | Full | Clear feature, moderate scope |
| **Large** | > 10 | > 8 | 6 formal stages | Requirements + Solution + Review | Security + API contract + Performance | Full | Multi-component, new APIs |
| **Complex** | — | — | 6 formal stages + Discuss | Full + Architecture Review | Full + Performance | Full + Lessons | New domain, high ambiguity |

### Heuristics

The auto-sizing algorithm evaluates:
- Number of files affected (from blueprint estimate)
- Number of tasks (from blueprint estimate)
- Presence of new domains
- External integrations required
- Work item ambiguity level
- Acceptance criteria count

A stage with `min_complexity` above the work item level is **deactivated** (marked `done: true` by default, skipped by the loop). Deactivated stages cannot be reactivated mid-loop, and the user cannot override auto-sizing — the heuristics are deterministic.

---

## Multi-Project

### How It Works

The framework is installed as a **git submodule** at `.eng/`. Framework code (stages, skills, references) is read-only and version-controlled. Project files (config, state, artifacts) live inside the submodule but are gitignored, ensuring each project maintains its own isolated runtime.

```
Framework (read-only, git-tracked)          Project (gitignored)
────────────────────────────────           ─────────────────────
.eng/ORCHESTRATOR.md                        .eng/config.yaml
.eng/CORE.md                                .eng/state.json
.eng/config-template.yaml                   .eng/STATE.md
.eng/state-template.json                    .eng/context.md
.eng/stages/                                .eng/artifacts/
.eng/skills/                                .eng/.gitignore
.eng/references/
.eng/skill-index.md
.eng/setup/
```

### Path Variables

| Variable | Resolves To | Used For |
|----------|------------|----------|
| `{framework-root}` | `.eng/` | stages/, skills/, references/ (read-only) |
| `{loop-root}` | `.eng/` | config.yaml, state.json, STATE.md, artifacts/ |
| `{project-root}` | `cwd` | source code, tests, `_bmad-output/` |
| `{artifact-root}` | `.eng/artifacts/` | all runtime artifacts |
| `{skill-root}` | `.eng/skills/` | skills |
| `{reference-root}` | `.eng/references/` | references |
| `{stage-root}` | `.eng/stages/` | stage procedures |
| `{log-root}` | `_bmad-output/process-logs/` | process logs |

### Updating the Framework

```bash
git submodule update --remote
```

### Config Merge

The orchestrator deep-merges two config files:

1. **`config-template.yaml`** (framework defaults)
2. **`config.yaml`** (project overrides)

If a key exists in both, the project value wins. Nested objects are merged recursively.

---

## Stage Catalog

### Phase 0 — INIT

| # | ID | Stage | Skill | Description |
|---|----|-------|-------|-------------|
| 0 | `init` | INIT | `bmad-integration` | Validate work item, initialize paths, discover skills, auto-size complexity, load lessons |
| 0.25 | `init.ideate` | Ideation | `bmad-ideation` | Party Mode (9 roles), Brainstorming (62 techniques), SDD extraction, impact-gated decomposition |
| 0.5 | `init.bdd` | BDD Journey | `bmad-bdd-mapper` | Comprehensive user journeys with Gherkin scenarios (large+) |
| 0.75 | `init.refine` | Refinement | essence + `bmad-brainstorming` | Iterative refinement of ad-hoc work items |

### Phase 1 — DESIGN (large+)

| # | ID | Stage | Skill | Description |
|---|----|-------|-------|-------------|
| 1.1 | `design.user-research` | User Research | `bmad-user-research` | Interviews, contextual studies, usability testing |
| 1.2 | `design.personas` | Personas | `bmad-personas` | Personas and journey maps from research data |
| 1.3 | `design.info-arch` | Information Architecture | `bmad-info-arch` | Sitemaps, wireframes, navigation structure |
| 1.4 | `design.interaction` | Interaction | `bmad-interaction` | Interaction patterns, component behaviors, motion design |
| 1.5 | `design.design-system` | Design System | `bmad-design-system` | Design tokens, component library, guidelines |
| 1.6 | `design.visual-design` | Visual Design | `bmad-visual-design` | Typography, color, layout, micro-animations |

### Phase 2 — ARCHITECTURE (medium+)

| # | ID | Stage | Skill | Description |
|---|----|-------|-------|-------------|
| 2 | `arch.requirements` | Requirements | `requirements-refiner` | Quantify functional requirements, volumetry, scalability, observability, security |
| 3 | `arch.solution` | Solution | `solution-designer` | Component design, data model, API contracts, cross-cutting concerns |
| 4 | `arch.review` | Review | `architecture-reviewer` | Cross-artifact consistency, gap analysis (complex only) |

### Phase 3 — IMPLEMENTATION

| # | ID | Stage | Skill | Description |
|---|----|-------|-------|-------------|
| 5 | `impl.design` | Blueprint | `implementation-architect` | File structure, contracts, data flows, execution order |
| 6 | `impl.code` | Code (TDD) | Domain skill (self-constructed) | Test-first per task: red → green → atomic commit |
| 6.5 | `doc.update` | Doc Update | Project Doc Updater | Update existing README, CHANGELOG, docs, inline comments |

### Phase 4 — VERIFY & QA

| # | ID | Stage | Skill | Description |
|---|----|-------|-------|-------------|
| 7 | `verify` | Verify | `verifier` | Spec-anchored check + discrimination sensor + coverage audit |
| 7.5 | `e2e.execute` | E2E Testing | `e2e-playwright` | Browser E2E with Playwright, 4-layer assertions (UI projects) |
| 8 | `qa.security` | Security | OWASP WSTG (self-constructed) | Security audit against OWASP Web Security Testing Guide |
| 9 | `qa.api-contract` | API Contract | OpenAPI (self-constructed) | API contract compliance validation |
| 10 | `qa.performance` | Performance | Self-constructed | Load targets, bundle size, response time (complex only) |

### Phase 5 — DEPLOY & DOCUMENT

| # | ID | Stage | Skill | Description |
|---|----|-------|-------|-------------|
| 11 | `deploy.prepare` | Deploy Prep | Orchestrator (direct) | Build, lint, type check, env config, migrations, final test run |
| 11.5 | `smoke.test` | Smoke Test | `e2e-playwright` | Full user journey against production build (UI projects) |
| 12 | `doc.decisions` | Decision Log | MADR + C4 Model | Consolidate AD-NNN entries into formal MADR ADRs |
| 13 | `doc.project` | Project Docs | arc42 + C4 Model | README, setup guide, architecture overview, user manual |

### Phase 6 — POST-LOOP

| # | ID | Stage | Skill | Description |
|---|----|-------|-------|-------------|
| 14 | `post` | Post-Loop | Orchestrator (direct) | Skill improvement, lessons sharing, finalize, commit, summary report |

---

## BMAD Ideation

For raw or ad-hoc work items that lack structure, the `init.ideate` stage applies BMAD's ideation framework before any engineering begins.

### Three-Stage Ideation

```
Raw Request
    │
    ├── Party Mode (9 AI roles debate the problem)
    │       ↓
    ├── Brainstorming (62 creative techniques)
    │       ↓
    ├── SDD Extraction (Software Design Description)
    │       ↓
    └── Impact-Gated Decomposition
            ↓
    Structured Work Item → enters normal loop
```

### Party Mode Roles

Nine specialized AI personas debate the problem from different perspectives: product manager, architect, developer, designer, QA engineer, security expert, DevOps engineer, UX researcher, and business analyst.

### Brainstorming

62 structured creative techniques applied to generate solution alternatives, each evaluated against impact and feasibility criteria.

### SDD Extraction

Key design decisions, constraints, and requirements extracted from the brainstorming output into a structured Software Design Description.

---

## Essence Sidecar

Runs **BEFORE** every stage. Validates that stage inputs are sound before any work begins — a pre-stage gate, not a post-stage check.

### The Four Lenses

| Lens | Focus | Example Findings | Resolution |
|------|-------|-----------------|------------|
| 1 | Subjective terms | "robust", "fast", "user-friendly", "clean" | Replace with measurable criteria |
| 2 | Hidden assumptions | Unstated dependencies, implicit requirements | Make explicit or remove |
| 3 | Literal traps | Phrasing that invites wrong LLM interpretation | Rephrase for clarity |
| 4 | Conflicting priorities | "fast delivery" vs "comprehensive testing" | Escalate to user for resolution |

### Execution Flow

```
1. Gather inputs for the upcoming stage
2. Launch essence sub-agent with context slice: {stage_inputs} + {work_item}
3. Lenses 1-3 findings → adjust inputs inline, re-run Essence (does NOT increment attempts)
4. Lens 4 tension → escalate to user, capture decision in context.md, await resolution
5. Clean (all lenses pass) → set essence_checked = true, proceed to stage
```

### Essence Input Per Stage

| Stage | Essence Validates |
|-------|-------------------|
| `init` | Work item completeness, clarity of intent |
| `init.bdd` | PRD features, UX flows, user stories sufficient for journey mapping |
| `arch.requirements` | Work item + planning artifacts provide sufficient context |
| `impl.code` | Blueprint is complete, contracts are defined |
| `verify` | Code implementation + tests are complete |
| `qa.security` | Code diff + architecture artifacts available |
| `deploy.prepare` | All QA stages complete, code is ready |
| `doc.decisions` | STATE.md Decisions section has entries to consolidate |

---

## BDD Journey

The `init.bdd` stage produces a comprehensive BDD Journey document that serves as the **single source of truth for testing** across all QA stages.

### Structure

Each user journey follows the BDD three-practice model:

1. **Discovery** — What the system *could* do (exploration)
2. **Formulation** — What the system *should* do (Gherkin scenarios)
3. **Automation reference** — What the system *actually* does (test mappings)

### Test Flow

```
BDD Journey (init.bdd)
    │
    ├── scenarios tagged "@unit"         → unit tests (impl.code)
    ├── scenarios tagged "@integration"  → integration tests (impl.code)
    ├── scenarios tagged "@e2e"          → E2E tests (e2e.execute)
    └── full journey                     → QA coverage audit (verify)
```

### Coverage Enforcement

When `e2e_bdd_coverage_enforcement: true` (default), every BDD scenario tagged `@e2e` must have a corresponding Playwright test. The `verify` stage audits this 1:1 mapping.

---

## E2E & Smoke Testing

### E2E Execute (`e2e.execute`)

For projects with UI components, Playwright-based end-to-end testing runs automatically:

1. **Infrastructure setup** — Playwright, config, Page Objects
2. **Auth bypass detection** + wiring
3. **Scenario derivation** from BDD `@e2e` tags
4. **Four-layer assertions**: DOM, Dimension, Console, Network
5. **Screenshot evidence** capture at each step
6. **BDD→E2E 1:1 coverage** check
7. **Auto-fix loop** (max 3 attempts) with regression gate

### Smoke Test (`smoke.test`)

Runs after `deploy.prepare` against the production build:

1. Build production binary
2. Define critical paths (login, navigation, CRUD, reports, logout)
3. Run full user journey against production build
4. Screenshot at each step
5. Console + network error monitoring
6. Auto-fix loop (max 3 attempts)

### E2E Constraints

| Constraint | Default | Purpose |
|------------|---------|---------|
| `e2e_locator_strategy` | `role-based` | Mandatory: `getByRole`, `getByLabel`, `getByText` |
| `e2e_console_error_gate` | `true` | Zero console errors required |
| `e2e_network_error_gate` | `true` | Zero 4xx/5xx required |
| `e2e_screenshot_on` | `true` | Always capture screenshots |
| `e2e_bdd_coverage_enforcement` | `true` | 1:1 BDD→E2E mandatory |

---

## Cross-Stage Resets

Downstream stages can reset upstream stages to `done: false`, triggering automatic re-execution on the next loop iteration.

### QA Stage Resets

| Stage | Finding Severity | Resets |
|-------|---------------|--------|
| `qa.security` | critical | `impl.code.done = false` |
| `qa.api-contract` | any discrepancy | `impl.code.done = false` |
| `qa.performance` | critical | `impl.code.done = false` |
| `deploy.prepare` | build/lint error | `impl.code.done = false` |
| `smoke.test` | journey failure | `impl.code.done = false` |
| `e2e.execute` | test failure | `impl.code.done = false` |

### Architecture Review Resets

| Finding Severity | Resets |
|-----------------|--------|
| `critical` in requirements | `arch.requirements.done = false` |
| `critical` in solution | `arch.solution.done = false` |
| `high` | Auto-adjust inline, re-validate |

### Verifier Resets

The `verify` stage operates as a fix → re-verify loop bounded to 3 iterations:
- On FAIL: gaps become fix tasks, reset `impl.code.done = false`
- On PASS: advance to next stage
- Lessons distilled from all failures

---

## Self-Constructed Skills

Skills marked as "self-constructed" are discovered and created at runtime from internet best practices. The orchestrator uses the `skill-creator` with templates from `references/skill-templates.md`.

| Skill | Source | Stage |
|-------|--------|-------|
| Domain Skill | Project tech stack, internet best practices | `impl.code` |
| Security Reviewer | OWASP Web Security Testing Guide (WSTG) | `qa.security` |
| API Contract Validator | OpenAPI Specification, Swagger best practices | `qa.api-contract` |
| Performance Checker | Web performance best practices, Lighthouse | `qa.performance` |
| Project Documentation Updater | conventional-changelog, README best practices | `doc.update` |
| Decision Log Consolidator | MADR v4.0, C4 Model | `doc.decisions` |
| Project Documentation | arc42, C4 Model, README conventions | `doc.project` |

---

## Continuous Decisions

Every stage that makes architectural or implementation decisions records them **immediately** as `AD-NNN` entries in `STATE.md`. Decision recording is NOT deferred to a documentation phase.

### Format

```markdown
## Decisions

### AD-001 — [Decision Title]
- **Status:** Accepted
- **Context:** [Why this decision was needed]
- **Decision:** [What was decided]
- **Consequences:** [Implications]
- **Stage:** [Stage that made the decision]
- **Date:** [ISO date]
```

### Handoff

After each stage, the orchestrator updates the `## Handoff` section in `STATE.md` with context for the next stage, ensuring smooth transitions between sub-agents.

---

## Lessons System

The framework maintains a self-improving lessons system that propagates knowledge across projects.

### Lifecycle

```
Stage failure or finding
        │
        ▼
  Distill lesson → artifacts/lessons.json (local)
        │
        ▼
  Occurs N times (confirm_threshold = 2) → confirmed
        │
        ▼
  Post-loop: copy to artifacts/lessons-pending.json
        │
        ▼
  User commits to framework → artifacts/lessons-shared.json
        │
        ▼
  Available to all projects on next loop
```

### Lesson Files

| File | Location | Purpose |
|------|----------|---------|
| `lessons.json` | `{artifact-root}/` | Project-local lessons |
| `lessons-shared.json` | `{artifact-root}/` | Shared lessons (committed to framework) |
| `lessons-pending.json` | `{artifact-root}/` | Lessons ready to share |
| `LESSONS.md` | `{artifact-root}/` | Human-readable lessons report |

Only **confirmed** lessons (occurred ≥ `confirm_threshold` times) enter sub-agent context.

---

## Knowledge Graph

When `config.graphify.enabled == true`, the optional Graphify integration builds and maintains a knowledge graph of the codebase.

### Features

- **AST-based code mapping** — parses source files to extract entities and relationships
- **Query interface** — `graphify explain <entity>`, `graphify path A B`, `graphify query <question>`
- **Edge confidence levels:**
  - `EXTRACTED` — trust (derived directly from code)
  - `INFERRED` — verify if critical (inferred from patterns)
  - `AMBIGUOUS` — must Read source (uncertain, requires verification)
- **Auto-update** — runs `graphify update .` after `impl.code` when `update_after_impl` is enabled

### Principle

> Graph is the map, Read is the terrain — never substitute Read with query when contract/type is critical.

---

## Configuration Reference

### Two-Layer Config

| File | Purpose | Git-tracked |
|------|---------|-------------|
| `config-template.yaml` | Framework defaults | Yes |
| `config.yaml` | Project overrides | No (gitignored) |

The orchestrator deep-merges: template → project. Project values win.

### Framework Paths

| Key | Default | Purpose |
|-----|---------|---------|
| `framework_skill_root` | `skills` | Skills directory (relative to `{framework-root}`) |
| `framework_reference_root` | `references` | References directory |
| `framework_stage_root` | `stages` | Stage procedures directory |
| `framework_template_path` | `references/skill-templates.md` | Self-construction templates |

### Project Paths

| Key | Default | Purpose |
|-----|---------|---------|
| `artifact_root` | `artifacts` | Runtime output (relative to `{loop-root}`) |
| `log_root` | `../_bmad-output/process-logs` | Process logs (relative to `{project-root}`) |
| `state_file` | `state.json` | State file (relative to `{loop-root}`) |
| `context_file` | `context.md` | Context file (relative to `{loop-root}`) |

### Constraints

| Key | Default | Purpose |
|-----|---------|---------|
| `max_init_bdd_attempts` | 2 | BDD journey mapping max iterations |
| `max_init_ideate_attempts` | 3 | Ideation max iterations |
| `max_init_refine_attempts` | 5 | Idea refinement max iterations |
| `max_design_*_attempts` | 2 | Each design stage max iterations |
| `max_arch_requirements_attempts` | 2 | Requirements refinement max iterations |
| `max_arch_solution_attempts` | 2 | Solution design max iterations |
| `max_arch_review_attempts` | 2 | Architecture review max iterations |
| `max_impl_design_attempts` | 2 | Implementation blueprint max iterations |
| `max_impl_code_attempts` | 3 | Code implementation max iterations |
| `max_verify_attempts` | 3 | Verification max iterations |
| `max_e2e_execute_attempts` | 3 | E2E testing max iterations |
| `max_smoke_test_attempts` | 3 | Smoke test max iterations |
| `max_qa_security_attempts` | 2 | Security review max iterations |
| `max_qa_api_contract_attempts` | 2 | API contract validation max iterations |
| `max_qa_performance_attempts` | 2 | Performance check max iterations |
| `max_deploy_prepare_attempts` | 2 | Deploy preparation max iterations |
| `max_doc_update_attempts` | 2 | Doc update max iterations |
| `max_doc_decisions_attempts` | 2 | Decision log max iterations |
| `max_doc_project_attempts` | 2 | Project docs max iterations |

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
| `essence.capture_decisions` | true | Capture Lens 4 decisions to context.md |

### Lessons

| Key | Default | Purpose |
|-----|---------|---------|
| `lessons.enabled` | true | Enable lessons system |
| `lessons.local_file` | `artifacts/lessons.json` | Project-local lessons |
| `lessons.shared_file` | `artifacts/lessons-shared.json` | Shared lessons (committed to framework) |
| `lessons.pending_file` | `artifacts/lessons-pending.json` | Lessons ready to share |
| `lessons.rendered_file` | `artifacts/LESSONS.md` | Human-readable lessons |
| `lessons.confirm_threshold` | 2 | Occurrences needed for confirmation |

### Graphify

| Key | Default | Purpose |
|-----|---------|---------|
| `graphify.enabled` | false | Enable knowledge graph integration |
| `graphify.build_on_init` | true | Build graph during INIT |
| `graphify.build_on_commit` | false | Build graph on each commit |
| `graphify.update_after_impl` | true | Update graph after impl.code |
| `graphify.skip_if_small` | true | Skip graph for small complexity |

---

## State Management

### State Files

| File | Location | Purpose |
|------|----------|---------|
| `state-template.json` | `{framework-root}/` | Template (git-tracked, 24 stages) |
| `state.json` | `{loop-root}/` | Runtime state (gitignored) |
| `STATE.md` | `{loop-root}/` | Human-readable state + decisions + handoff (gitignored) |

### Per-Stage Variables

| Variable | Type | Purpose |
|----------|------|---------|
| `stages.{id}.done` | boolean | Whether stage is complete |
| `stages.{id}.attempts` | integer | Number of attempts (checked against constraints) |
| `stages.{id}.essence_checked` | boolean | Whether Essence Sidecar validated inputs |

### Global Variables

| Variable | Type | Purpose |
|----------|------|---------|
| `iteration` | integer | Current loop iteration count |
| `status` | enum | `running` / `done` / `blocked` / `halted` |
| `complexity` | enum | `unset` / `small` / `medium` / `large` / `complex` |
| `work_item` | object | Validated work item data |
| `decisions` | array | AD-NNN decision records |

---

## Context Management

### Progressive Disclosure

- **Stages** — loaded by ID from `{stage-root}/` only when needed
- **References** — loaded by ID from `{reference-root}/` only when needed
- **Skills** — loaded from `{skill-root}/` only when invoking a sub-agent
- **Index of all stages and references:** `CORE.md`

### Context Slicing

Each sub-agent receives only its relevant context slice. Total tokens across all agents must stay within `context_window - (context_window * context_safety_margin)`.

**Rule:** Never pass the full set of artifacts to any single sub-agent.

| Agent | Receives | Does NOT receive |
|-------|----------|-----------------|
| Verifier | diff + blueprint + ACs + test file paths | Full context, other feature specs |
| Security Reviewer | diff + blueprint + architecture | Test files |
| API Contract Validator | blueprint + API source + integration tests | E2E tests, full diff |
| Performance Checker | blueprint + architecture + build output | Test files |

---

## Directory Structure

```
.engineering-loop/ (framework repo)
├── ORCHESTRATOR.md              # Main orchestrator instructions
├── CORE.md                      # Framework index: stages, references, skills
├── config-template.yaml         # Framework configuration defaults
├── state-template.json          # Initial state for all 24 stages
├── skill-index.md               # Skill registry with improvement log
├── README.md                    # This file
├── .gitignore                   # Project file exclusions
├── AGENTS.md                    # Agent-specific instructions
│
├── stages/                      # Stage procedures (read-only, 24 files)
│   ├── init.md                  # Phase 0: validation, auto-size, skill discovery
│   ├── init-ideate.md           # BMAD ideation: Party Mode, Brainstorming, SDD
│   ├── init-bdd.md              # BDD journey mapping
│   ├── init-refine.md           # Ad-hoc work item refinement
│   ├── design-user-research.md  # User research methods
│   ├── design-personas.md       # Persona creation
│   ├── design-info-arch.md      # Information architecture
│   ├── design-interaction.md    # Interaction design
│   ├── design-design-system.md  # Design system tokens
│   ├── design-visual-design.md  # Visual design specifications
│   ├── architecture.md          # Requirements, solution, review
│   ├── impl-design.md           # Implementation blueprint
│   ├── impl-code.md             # TDD code implementation
│   ├── doc-update.md            # Existing project file updates
│   ├── verify.md                # Independent verification
│   ├── e2e-execute.md           # Playwright E2E testing
│   ├── qa-security.md           # OWASP WSTG security audit
│   ├── qa-api-contract.md       # API contract validation
│   ├── qa-performance.md        # Performance profiling
│   ├── deploy-prepare.md        # Build, lint, test preparation
│   ├── smoke-test.md            # Production smoke testing
│   ├── doc-decisions.md         # MADR decision log consolidation
│   ├── doc-project.md           # Project documentation generation
│   └── post-loop.md             # Finalize, improve, share
│
├── references/                  # Shared references (read-only, 13 files)
│   ├── anti-patterns.md         # Common pitfalls and how to avoid them
│   ├── bmad-ideation-patterns.md # BMAD ideation framework details
│   ├── decision-log.md          # AD-NNN decision format
│   ├── decision-template.md     # MADR ADR template
│   ├── essence-sidecar.md       # Four Lenses validation details
│   ├── exit-conditions.md       # All exit conditions and resets
│   ├── graphify.md              # Knowledge graph integration
│   ├── hardware-management.md   # Context slicing, token budgets
│   ├── lessons.md               # Lessons lifecycle
│   ├── logging.md               # Log format + state table
│   ├── skill-discovery-guide.md # Self-construction process
│   ├── skill-templates.md       # Skill creation templates
│   └── ui-testing-patterns.md   # E2E testing patterns
│
├── skills/                      # Specialized skills (read-only, 11 skills)
│   ├── bmad-bdd-mapper/         # BDD journey mapping
│   ├── bmad-ideation/           # Party Mode, Brainstorming, SDD
│   ├── bmad-integration/        # BMAD → work item transformation
│   ├── cloud-architect/         # Cloud architecture patterns
│   ├── e2e-playwright/          # Playwright E2E testing
│   ├── essence/                 # Four Lenses validation
│   ├── graphify/                # Knowledge graph
│   ├── implementation-architect/ # Implementation blueprints
│   ├── requirements-refiner/    # Requirements quantification
│   ├── solution-designer/       # Solution architecture
│   └── verifier/                # Independent verification
│
└── setup/                       # Installation scripts
    ├── install.sh               # Linux / Mac / WSL setup
    ├── install.ps1              # Windows PowerShell setup
    └── README.md                # Setup documentation
```

---

## Exit Conditions

| Condition | Where | Status | `blocking_condition` |
|-----------|-------|--------|---------------------|
| All active stages done | WHILE false | `done` | — |
| Input invalid | Phase 0 | `blocked` | `input not ready for engineering` |
| Skill creation fails | Phase 1 | `blocked` | `no suitable skill available` |
| `init.bdd.attempts >= max` | init BDD | `blocked` | `BDD journey mapping non-convergence` |
| `impl.code.attempts >= max` | impl code | `blocked` | `implementation non-convergence` |
| `verify.attempts >= max` | verify | `blocked` | `verification non-convergence` |
| `qa.security.attempts >= max` | qa security | `blocked` | `security review non-convergence` |
| `qa.api-contract.attempts >= max` | qa api-contract | `blocked` | `API contract validation non-convergence` |
| `qa.performance.attempts >= max` | qa performance | `blocked` | `performance check non-convergence` |
| `deploy.prepare.attempts >= max` | deploy prepare | `blocked` | `deploy preparation non-convergence` |
| `max_loop_iterations` exceeded | Any | `halted` | `loop iterations exceeded` |
| `stage_timeout_seconds` exceeded | Any stage | `halted` | `stage timeout exceeded` |
| `max_essence_retries_per_stage` exceeded | Essence gate | `blocked` | `essence non-convergence` |
| User interrupt | Any | `halted` | `user interrupted` |

---

## Anti-Patterns

### Loop Mechanics

- **Never treat stages as sequential** — the loop re-evaluates ALL stages every iteration
- **Never break the loop prematurely** — only exit via all stages done or constraint breach
- **Never reset attempt counters mid-loop** — counters persist across all iterations
- **Never skip stages on user request** — user requests are focus directives, not skip directives

### Essence Gate

- **Always run Essence BEFORE every stage** — validates inputs before any work begins
- **Never run Essence after a stage** — it is a pre-stage gate, not a post-stage check
- **Never skip Essence** — every stage must pass the Four Lenses before invocation

### Multi-Project

- **Never hardcode paths** — always resolve from config and root variables
- **Never write project artifacts to framework dir** — use `{loop-root}` for project files
- **Never modify config-template.yaml** — projects should only modify their own `config.yaml`
- **Never commit project files in framework repo** — `.gitignore` prevents this

### Context Management

- **Never pass full context to a sub-agent** — always use context slicing
- **Never exceed agent_context_limit** — each sub-agent has its own token budget
- **Never skip log compaction** — context overflow will crash the loop

### Decision Recording

- **Never defer decisions to doc phase** — record AD-NNN continuously after each stage
- **Never lose decision context** — every architectural choice must be documented immediately

---

## Troubleshooting

### Stage Won't Converge (Attempts Exhausted)

**Symptom:** `status: blocked`, `blocking_condition: {stage} non-convergence`

**Resolution:**
- Increase `max_{stage}_attempts` in `config.yaml`
- Improve work item clarity (more specific ACs, clearer scope)
- Review upstream stage artifacts for completeness
- Check Essence findings for input quality issues

### Essence Keeps Failing

**Symptom:** Stage never invokes, Essence loops indefinitely

**Resolution:**
- For Lenses 1-3: Adjust inputs inline, clarify ambiguous terms
- For Lens 4: Resolve priority tension, provide explicit direction
- If `max_essence_retries_per_stage` exceeded: manually resolve the input ambiguity

### Context Overflow

**Symptom:** Sub-agent responses are truncated or loop crashes

**Resolution:**
- Increase `context_window` in `config.yaml`
- Reduce `agent_context_limit` and enforce stricter slicing
- Run log compaction manually if `compact_log_after_iteration` hasn't triggered

### Config Not Found

**Symptom:** Orchestrator warns about missing `config.yaml`

**Resolution:** Run `bash .eng/setup/install.sh` or `powershell -File .eng\setup\install.ps1`

### Submodule Not Updating

**Symptom:** Stages or skills are outdated

**Resolution:** `git submodule update --remote`

### E2E Tests Failing on Locators

**Symptom:** Playwright tests fail with "element not found"

**Resolution:**
- Ensure `e2e_locator_strategy` is set to `role-based`
- Use `getByRole`, `getByLabel`, `getByText` — never fragile CSS/XPath selectors
- Check that ARIA labels and roles are present in the DOM

### Lessons Not Propagating

**Symptom:** Same failure occurs across projects

**Resolution:**
- Verify `lessons.enabled` is `true` in `config.yaml`
- Check `lessons.confirm_threshold` — may need to lower from default (2)
- Ensure `lessons-shared.json` is committed to the framework repo after post-loop

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v6.0.0 | 2026-07-15 | Persistent while-loop, stage-based state, constraints |
| v7.0.0 | 2026-07-15 | Context-aware: slicing, compaction, findings cap |
| v7.1.0 | 2026-07-16 | Mandatory architecture gate (cloud + solution) |
| v7.2.0 | 2026-07-16 | Essence sidecar: Four Lenses on every Design artifact |
| v7.3.0 | 2026-07-16 | Progressive disclosure: stages + references by ID |
| v7.4.0 | 2026-07-16 | Agent Skills spec alignment: frontmatter, compact CORE, delegated runtime |
| v7.5.0 | 2026-07-19 | Enterprise stages: BDD journey, split impl/test/QA, security/API/performance gates |
| v8.0.0 | 2026-07-22 | Design phase: six new stages (user-research through visual-design) |
| v8.1.0 | 2026-07-25 | Documentation phase: decision log (MADR ADRs), project docs (C4 Model) |
| v9.0.0 | 2026-07-27 | Auto-sizing by complexity, TDD per task, Verifier with discrimination sensor, continuous AD-NNN decisions, self-improving lessons |
| v10.0.0 | 2026-07-29 | Multi-project architecture: git submodule, isolated artifacts, two-layer config, shared lessons |
| v10.1.0 | 2026-07-31 | Continuous documentation: doc.update stage after impl.code, existing project files updated |
| v10.2.0 | 2026-07-31 | BMAD Ideation stage: Party Mode (9 roles), Brainstorming (62 techniques), SDD extraction, impact-gated decomposition |

---

## Files at a Glance

| File | Role |
|------|------|
| `ORCHESTRATOR.md` | Main entry point — load this to start the loop |
| `CORE.md` | Framework index — stage registry, references, skills |
| `skill-index.md` | Skill registry — ID → skill mapping with improvement log |
| `config-template.yaml` | Framework defaults — 143 lines of tunable configuration |
| `state-template.json` | State template — 24 stages with done/attempts/essence_checked |
| `AGENTS.md` | Agent instructions — framework editing guidelines |
| `README.md` | This file — comprehensive documentation |
