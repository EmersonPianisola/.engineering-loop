---
name: engineering-loop-readme
type: entry-point
description: 'Comprehensive framework documentation.'
---

# Engineering Loop v10

Persistent while-loop engine for AI-assisted development. Multi-project architecture via git submodule. The orchestrator delegates every phase of work to specialized sub-agents via progressive disclosure. Essence Sidecar validates inputs before every stage. All stages follow **Design → Execute → Validate**.

**Entry point:** `CORE.md`
**Orchestrator:** `ORCHESTRATOR.md`
**Configuration:** `config-template.yaml` (framework) + `config.yaml` (project)

---

## Table of Contents

- [Installation](#installation)
- [Architecture](#architecture)
- [Multi-Project](#multi-project)
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

## Installation

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

### 3. Customize Configuration

Review `.eng/config.yaml` and adjust as needed. See [Configuration Reference](#configuration-reference).

### 4. Start Using

Load `ORCHESTRATOR.md` and provide a work item. The orchestrator auto-detects all paths.

---

## Architecture

```
USER REQUEST (work item)
        │
        ▼
   ┌─────────┐
   │  INIT    │  ← Phase 0: Validate input, discover skills, init paths
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
   └────┬─────┘
        │
        ▼
  ┌───────────┐
  │ POST-LOOP  │  ← Phase 5: Skill improvement + share lessons
  │  (once)    │  ← Phase 6: Finalize + commit
  └───────────┘
```

### Design Philosophy

- **Orchestrator is pure delegation** — never executes work directly (except deploy.prepare and post-loop finalize)
- **Progressive disclosure** — stages, references, and skills loaded by ID only when needed
- **Context slicing** — each sub-agent receives only its relevant context; full artifacts are never passed to one agent
- **Full loop enforcement** — every stage must execute; user requests are focus directives, not skip directives
- **Essence before every stage** — inputs are validated before any work begins, not after
- **Multi-project isolation** — each project has its own config, state, and artifacts
- **Shared lessons** — confirmed lessons are shared across all projects via the framework

---

## Multi-Project

### How It Works

The framework is installed as a **git submodule** (`.eng/`). Framework code (stages, skills, references) is read-only. Project files (config, state, artifacts) live inside the submodule but are gitignored.

```
Framework (read-only, git-tracked)          Project (gitignored)
─────────────────────────────────          ─────────────────────
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
| `{project-root}` | `cwd` | source code, tests, _bmad-output/ |
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

The orchestrator merges two config files:

1. **`config-template.yaml`** (framework defaults)
2. **`config.yaml`** (project overrides)

If a key exists in both, the project value wins. Deep merge for nested objects.

---

## How It Works

The orchestrator maintains a state table and iterates through stages until all converge:

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
5. **Load procedure** — fetch stage file from `{stage-root}/` by ID
6. **Slice context** — determine what context the sub-agent needs
7. **Increment attempts** and **invoke sub-agent**
8. **Stop generation** — wait for sub-agent response
9. **Post-iteration** — check constraints, compact log if needed, cap findings, write state

The loop does NOT advance sequentially. It re-evaluates every stage each iteration. A stage reset to `done: false` by a downstream finding is picked up naturally on the next iteration.

---

## Stage Catalog

### 0 — INIT

- **Skill:** `bmad-integration`
- **Procedure:** `{stage-root}/init.md`
- **Purpose:** Validate work item. Initialize project paths. Discover domain skills. Auto-size complexity. Load shared + local lessons.
- **Artifact:** Validated work item stored in `state.work_item`
- **On failure:** `status: blocked`, `blocking_condition: input not ready`, EXIT

### 0.5 — INIT.BDD (BDD Journey Mapping)

- **Skill:** BDD journey mapper
- **Procedure:** `{stage-root}/init-bdd.md`
- **Constraint:** `max_init_bdd_attempts` (default: 2)
- **Purpose:** Produce comprehensive user journeys with Gherkin scenarios.
- **Artifact:** `{artifact-root}/bdd-journeys/journey-{slug}.md`

### 1.1 — 1.6 — DESIGN (six stages, large+)

- **Stages:** user-research → personas → info-arch → interaction → design-system → visual-design
- **Active only when:** `state.complexity >= "large"`
- **Artifacts:** `{artifact-root}/design/`

### 2 — ARCH.REQUIREMENTS

- **Skill:** `requirements-refiner`
- **Procedure:** `{stage-root}/architecture.md`
- **Constraint:** `max_arch_requirements_attempts` (default: 2)
- **Purpose:** Quantify functional requirements, volumetry, scalability, observability, security.
- **Artifact:** `{artifact-root}/architectures/requirements-{slug}.md`

### 3 — ARCH.SOLUTION

- **Skill:** `solution-designer`
- **Procedure:** `{stage-root}/architecture.md`
- **Constraint:** `max_arch_solution_attempts` (default: 2)
- **Purpose:** Component design, data model, API contracts, cross-cutting concerns.
- **Artifact:** `{artifact-root}/architectures/solution-{slug}.md`

### 4 — ARCH.REVIEW (complex only)

- **Skill:** `architecture-reviewer`
- **Constraint:** `max_arch_review_attempts` (default: 2)
- **Purpose:** Cross-artifact consistency, gap analysis.
- **Artifact:** `{artifact-root}/architectures/consolidated-{slug}.md`

### 5 — IMPL.DESIGN (Blueprint)

- **Skill:** `implementation-architect`
- **Procedure:** `{stage-root}/impl-design.md`
- **Constraint:** `max_impl_design_attempts` (default: 2)
- **Purpose:** File structure, contracts, data flows, execution order.
- **Artifact:** `{artifact-root}/blueprints/blueprint-{slug}.md`

### 6 — IMPL.CODE (TDD)

- **Skill:** Domain-specific (self-constructed)
- **Procedure:** `{stage-root}/impl-code.md`
- **Constraint:** `max_impl_code_attempts` (default: 3)
- **Purpose:** TDD per task — test first, then code, atomic commit.

### 7 — VERIFY

- **Skill:** `verifier`
- **Procedure:** `{stage-root}/verify.md`
- **Constraint:** `max_verify_attempts` (default: 3)
- **Purpose:** Spec-anchored check + discrimination sensor + coverage audit.
- **Artifact:** `{artifact-root}/validation-{slug}.md`

### 8 — 10 — QA (security, api-contract, performance)

- **Active based on complexity:** security/api-contract (medium+), performance (complex)
- **Artifacts:** None (inline validation)

### 11 — DEPLOY.PREPARE

- **Skill:** Orchestrator executes directly
- **Procedure:** `{stage-root}/deploy-prepare.md`
- **Tasks:** build, lint, type check, env config, migrations, final test run

### 12 — 13 — DOC (decisions, project)

- **Artifacts:** `{artifact-root}/decision-log-{slug}.md`, project documentation

### 14 — POST-LOOP

- **Phase 5:** Skill improvement, lessons sharing
- **Phase 6:** Finalize, commit, report summary

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
4. **Lens 4 tension:** Escalate to user for resolution, capture decision in `{loop-root}/context.md`
5. **Clean:** Set `essence_checked = true`, proceed to stage

---

## BDD Journey

The `init.bdd` stage produces a comprehensive BDD Journey document that serves as the **single source of truth for testing**.

### Structure

Each user journey follows the BDD three-practice model:

1. **Discovery** — What the system could do
2. **Formulation** — What the system should do (Gherkin scenarios)
3. **Automation reference** — What the system actually does (test mappings)

### Test Flow

```
BDD Journey (init.bdd)
    │
    └── scenarios tagged "unit"        → unit tests
    └── scenarios tagged "integration" → integration tests
    └── scenarios tagged "e2e"         → E2E tests
    └── full journey                   → QA coverage audit
```

---

## Cross-Stage Resets

Downstream stages can reset upstream stages to `done: false`, triggering re-execution.

### QA Stage Resets

| Stage | Finding Severity | Resets |
|-------|---------------|--------|
| `qa.security` | critical | `impl.code.done = false` |
| `qa.api-contract` | any discrepancy | `impl.code.done = false` |
| `qa.performance` | critical | `impl.code.done = false` |
| `deploy.prepare` | build/lint error | `impl.code.done = false` |

### Architecture Review Resets

| Finding Severity | Resets |
|-----------------|--------|
| `critical` in requirements | `arch.requirements.done = false` |
| `critical` in solution | `arch.solution.done = false` |
| `high` | Auto-adjust inline, re-validate |

---

## Self-Constructed Skills

Skills marked as "self-constructed" are discovered and created at runtime from internet best practices.

| Skill | Source | Stage |
|-------|--------|-------|
| Domain Skill | Project tech stack, internet best practices | `impl.code` |
| Security Reviewer | OWASP WSTG | `qa.security` |
| API Contract Validator | OpenAPI, Swagger | `qa.api-contract` |
| Performance Checker | Web performance, Lighthouse | `qa.performance` |
| Decision Log Consolidator | MADR v4.0, C4 Model | `doc.decisions` |
| Project Documentation | arc42, C4 Model | `doc.project` |

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
| `max_init_refine_attempts` | 5 | Idea refinement max iterations |
| `max_arch_requirements_attempts` | 2 | Requirements refinement max iterations |
| `max_arch_solution_attempts` | 2 | Solution design max iterations |
| `max_arch_review_attempts` | 2 | Architecture review max iterations |
| `max_impl_design_attempts` | 2 | Implementation blueprint max iterations |
| `max_impl_code_attempts` | 3 | Code implementation max iterations |
| `max_verify_attempts` | 3 | Verification max iterations |
| `max_qa_security_attempts` | 2 | Security review max iterations |
| `max_qa_api_contract_attempts` | 2 | API contract validation max iterations |
| `max_qa_performance_attempts` | 2 | Performance check max iterations |
| `max_deploy_prepare_attempts` | 2 | Deploy preparation max iterations |
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

### Lessons

| Key | Default | Purpose |
|-----|---------|---------|
| `lessons.enabled` | true | Enable lessons system |
| `lessons.local_file` | `artifacts/lessons.json` | Project-local lessons |
| `lessons.shared_file` | `artifacts/lessons-shared.json` | Shared lessons (committed to framework) |
| `lessons.pending_file` | `artifacts/lessons-pending.json` | Lessons ready to share |
| `lessons.rendered_file` | `artifacts/LESSONS.md` | Human-readable lessons |
| `lessons.confirm_threshold` | 2 | Occurrences needed for confirmation |

---

## State Management

### State Files

| File | Location | Purpose |
|------|----------|---------|
| `state-template.json` | `{framework-root}/` | Template (git-tracked) |
| `state.json` | `{loop-root}/` | Runtime state (gitignored) |
| `STATE.md` | `{loop-root}/` | Human-readable state + decisions (gitignored) |

### State Variables

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

---

## Directory Structure

```
.engineering-loop/ (framework repo)
├── ORCHESTRATOR.md
├── CORE.md
├── config-template.yaml
├── state-template.json
├── skill-index.md
├── README.md
├── .gitignore
├── stages/              # Stage procedures (read-only)
│   ├── init.md
│   ├── init-bdd.md
│   ├── architecture.md
│   ├── impl-design.md
│   ├── impl-code.md
│   ├── verify.md
│   ├── qa-security.md
│   ├── qa-api-contract.md
│   ├── qa-performance.md
│   ├── deploy-prepare.md
│   ├── doc-decisions.md
│   ├── doc-project.md
│   └── post-loop.md
├── references/          # Shared references (read-only)
│   ├── anti-patterns.md
│   ├── essence-sidecar.md
│   ├── exit-conditions.md
│   ├── hardware-management.md
│   ├── logging.md
│   ├── skill-discovery-guide.md
│   ├── skill-templates.md
│   ├── decision-log.md
│   └── lessons.md
├── skills/              # Specialized skills (read-only)
│   ├── verifier/
│   ├── solution-designer/
│   ├── requirements-refiner/
│   ├── implementation-architect/
│   ├── bmad-integration/
│   ├── bmad-bdd-mapper/
│   └── e2e-playwright/
└── setup/               # Installation scripts
    ├── install.sh
    ├── install.ps1
    └── README.md
```

---

## Exit Conditions

| Condition | Where | Status | blocking_condition |
|-----------|-------|--------|-------------------|
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
| Stage timeout | Any stage | `halted` | `stage timeout exceeded` |
| User interrupt | Any | `halted` | `user interrupted` |

---

## Invoke

Load `ORCHESTRATOR.md` and provide a work item (spec file, ticket, or description). The orchestrator will:

1. **Detect roots** — `{framework-root}`, `{loop-root}`, `{project-root}`
2. **Load config** — merge template defaults with project overrides
3. **Initialize state** — copy from template
4. **Validate input** (INIT) — ensure work item has title, ACs, scope, intent
5. **Discover skills** (INIT) — scan existing skills, self-construct missing ones
6. **Run the full loop** — through all active stages with Essence gates
7. **Finalize and commit** (POST-LOOP) — improve skills, share lessons, commit changes

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

---

## Troubleshooting

### Stage Won't Converge (Attempts Exhausted)

**Symptom:** `status: blocked`, `blocking_condition: {stage} non-convergence`

**Resolution:**
- Increase `max_{stage}_attempts` in `config.yaml`
- Improve work item clarity (more specific ACs, clearer scope)
- Review upstream stage artifacts for completeness

### Essence Keeps Failing

**Symptom:** Stage never invokes, Essence loops indefinitely

**Resolution:**
- For Lenses 1-3: Adjust inputs inline, clarify ambiguous terms
- For Lens 4: Resolve priority tension, provide explicit direction

### Context Overflow

**Symptom:** Sub-agent responses are truncated or loop crashes

**Resolution:**
- Increase `context_window` in `config.yaml`
- Reduce `agent_context_limit` and enforce stricter slicing

### Config Not Found

**Symptom:** Orchestrator warns about missing config.yaml

**Resolution:** Run `bash .eng/setup/install.sh` or `powershell -File .eng\setup\install.ps1`

### Submodule Not Updating

**Symptom:** Stages/skills are outdated

**Resolution:** `git submodule update --remote`
