---
name: engineering-loop-readme
type: entry-point
description: 'Comprehensive framework documentation.'
---

# Engineering Loop v12.4.0

**New user? Start with [`AGENTS.md`](AGENTS.md) — quick reference for development mode.**

**Fail Fast (FF)** — orchestrator pattern for parallel swarm-based software development. Fragment any work item into atomic blocks, dispatch parallel tasks via Swarm, validate at each gate, recover isolated failures.

| | |
|---|---|
| **Version** | 12.4.0 |
| **Development Mode** | FF (Fail Fast) — parallel swarm, judge-approved plans |
| **Orchestrator** | `eng_loop/` (LangGraph Python, Dynamic Graph, Pydantic schemas) |
| **Stages** | 34 registered NodeSpec stages |
| **Skills** | 22 built-in ideação/verificação skills + global skills |
| **References** | 14 shared reference documents (anti-patterns, exit-conditions, lessons, etc.) |
| **Architecture** | Multi-project via git submodule |

---

## Table of Contents

- [Overview](#overview)
- [FF Protocol](#ff-protocol)
- [The Engine (eng_loop/)](#the-engine-eng_loop)
- [BMAD Ideation](#bmad-ideation)
- [Essence Sidecar](#essence-sidecar)
- [Lessons System](#lessons-system)
- [Knowledge Graph](#knowledge-graph)
- [Configuration Reference](#configuration-reference)
- [State Management](#state-management)
- [Directory Structure](#directory-structure)
- [Exit Conditions](#exit-conditions)
- [Anti-Patterns](#anti-patterns)
- [Troubleshooting](#troubleshooting)
- [Version History](#version-history)

---

## Overview

Engineering Loop is a framework for orchestrating AI sub-agents through the complete software development lifecycle. Instead of a linear pipeline, it operates as a **persistent while-loop** that re-evaluates every stage on each iteration, allowing downstream findings to trigger upstream rework automatically.

The loop is enforced by a **dynamic LangGraph StateGraph** (Python) that is **constructed per work item** — only the nodes required for the task are instantiated based on complexity, UI context, and tags. Stage procedures remain as markdown templates in `stages/`, loaded at runtime and injected as prompts. The orchestrator works with any OpenAI-compatible local model (llama.cpp, vLLM, Ollama).

### Core Principles

- **Dynamic graph construction** — `GraphBuilder` builds the graph per work item; only active nodes are instantiated
- **Programmatic flow control** — LangGraph StateGraph enforces stage order, retries, and resets in code (not prompts)
- **Structured output** — Every stage uses Pydantic schemas via `model.with_structured_output()` — no free-form JSON
- **Evidence gates** — Every stage output is validated against quality criteria before advancing; failures trigger automatic retry
- **Declarative routing** — `EdgeRule` rules define connections between nodes; resolved at build time
- **Node registry** — 34 stages registered as `NodeSpec` with metadata (complexity, phase, parallel group)
- **Orchestrator is pure delegation** — never executes work directly (except `deploy.prepare` and `post-loop` finalize)
- **Progressive disclosure** — stages, references, and skills loaded by ID only when needed
- **Context slicing** — each sub-agent receives only its relevant context; full artifacts are never passed to one agent
- **Context optimization** — ProjectMap pre-computed at init eliminates 3-8 exploratory glob/read per stage; tool result cache prevents redundant reads within a micro-loop
- **Full loop enforcement** — every active stage must execute; user requests are focus directives, not skip directives
- **Essence before every stage** — inputs validated through Four Lenses; Lens 4 scope tensions ask for clarification before blocking
- **Wall-clock visibility** — global timer persists across recovery attempts; all progress displays show real-time elapsed time
- **Auto-sizing** — complexity classification determines which stages are active (small → complex)
- **TDD per task** — test-first implementation with red-green-commit per atomic task
- **Independent verification** — author ≠ verifier; discrimination sensor confirms test quality
- **Contract Gate Middleware** — validates handoff contracts between stages (blueprint→code, code→verify); retries or blocks on violation
- **Parallel QA** — fan-out/fan-in for security, API contract, performance stages via `qa-dispatcher` + `qa-join`
- **Causal Chain Rollback** — `rollback_to_stage` reducer resets impl.code through verify when verifier/QA fails
- **Fix Mode** — `impl.code` executes with structured `fix_tasks` from verifier/QA, clears feedback on success
- **Dry-Run Simulator** — 4 scenarios (HAPPY_PATH, CONTRACT_VIOLATION, VERIFY_ROLLBACK, QA_FANOUT_FAIL) validate graph topology without LLM calls
- **Multi-project isolation** — each project has its own config, state, and artifacts
- **Shared lessons** — confirmed lessons propagate across all projects via the framework
- **Continuous decisions** — every architectural decision recorded as `AD-NNN` immediately, not deferred
- **Local model support** — works with any OpenAI-compatible endpoint (llama.cpp, vLLM, Ollama)
- **Surgical CLI operations** — breakpoints (`--pause-at`), state editing via `$EDITOR`, time-travel rollback, single-step replay (v11.2)

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

## FF Protocol

FF is the **default development mode** for this project. It replaces the sequential loop with parallel swarm execution.

### Protocol Overview

```
USER INTENT
    ↓
PHASE 0: CLARIFY    → Essence check, gather unknowns, scope the task
PHASE 1: PLAN BUILD → Two sub-agents cross-analyze → consolidate → judge approve
PHASE 2: EXECUTE    → Swarm fan-out per block, gate check, retry
PHASE 3: VALIDATE   → Final gate, cross-check plan vs. reality
PHASE 4: LESSONS    → Capture lessons, report results
```

### Plan Build

The plan is **not built by the main agent**. It is built by two sub-agents:

1. **Sub-Agent A (Structural Analyst)** — maps files, imports, dependencies, risk
2. **Sub-Agent B (Adversarial Analyst)** — alternative approaches, edge cases, hidden dependencies

The main agent consolidates A + B, then spawns a **judge sub-agent** to validate the plan. Only after approval does swarm execution begin.

### Execute

Swarm dispatches parallel tasks per block. Independent tasks run together; dependent tasks wait. Each block validates before the next executes.

### Autonomy Score

| Score | Mode | Behavior |
|-------|------|----------|
| ≥ 0.8 | FULL AUTO | Execute without asking |
| 0.5-0.7 | SEMI AUTO | Show plan → wait for "go" → execute |
| < 0.5 | MANUAL | Ask before each block |

### Hard Rules (Never Override)

- `rm -rf`, `git push --force` — always ask
- Writes to Firebase — always ask
- Changes to `.env` — always ask
- Operations outside workspace — always block

### Anti-Patterns

**Don't:**
- Use waves — waves are the same problem as graphs (sequential dependencies)
- Create more than 8 blocks — if you need more, re-fragment
- Let one failed block trigger a full restart — retry only failed rows
- Encode assumptions in the harness — models improve, assumptions stale

---

## The Engine (eng_loop/)

The orchestrator is a real Python package. Install (editable) and run commands from the `eng_loop/` directory:

```bash
pip install -e "eng_loop/[dev]"
ruff check eng_loop/src eng_loop/tests
ruff format eng_loop/src eng_loop/tests
pytest eng_loop/tests
```

CLI entry point: `eng-loop` (defined in `pyproject.toml` → `[project.scripts]`). After editable install, available on PATH.

### Source Layout

```
eng_loop/src/eng_loop/
├── cli.py              # Entry point (eng-loop command, pre-build architect)
├── graph_builder.py    # Dual-path builder (proposal or deterministic)
├── node_registry.py    # 34 registered NodeSpec stages
├── edge_rules.py       # Declarative edge rules + proposal compiler
├── state.py            # PipelineState schema + reducers + node catalog
├── schemas.py          # 52 Pydantic schemas (topology + stage output)
├── config.py           # YAML loader, deep merge
├── graph.py            # Delegates to GraphBuilder in dynamic mode
├── routing.py          # Conditional edge functions (retry, block, advance)
├── model.py            # Model factory (OpenAI-compatible endpoints)
├── templates.py        # Markdown → prompt loader
├── context_bus.py      # Cross-cutting context bus (new in v12)
├── nodes/              # 13 modules, one per stage group
│   ├── dynamic_architect.py  # Pre-build topology + runtime augmentation
│   ├── meta_executor.py      # Sequential cursor-based executor
│   └── (11 more: init, design, architecture, implementation, qa, etc.)
└── tools/              # 58 tool modules
    ├── policy_resolver.py    # 6-layer topology firewall + tool sandboxing
    └── sandbox.py            # Path/command sandboxing for agent tools
```

Tests: 105 files. Run `pytest eng_loop/tests` for full suite.

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
| 4 | Conflicting priorities | "fast delivery" vs "comprehensive testing" | Ask user: narrow scope, accept full scope, or redefine work item |

### Execution Flow

```
1. Gather inputs for the upcoming stage
2. Launch essence sub-agent with context slice: {stage_inputs} + {work_item}
3. Lenses 1-3 findings → adjust inputs inline, re-run Essence (does NOT increment attempts)
4. Lens 4 tension (scope/complexity) → ask user for clarification: narrow scope, accept full scope, or redefine work item
5. Lens 4 clarification exhausted (max attempts) → terminal block, capture decision in context.md
6. Clean (all lenses pass) → set essence_checked = true, proceed to stage
```

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

### Global Skills (Fallback)

| Key | Default | Purpose |
|-----|---------|---------|
| `global_skills.enabled` | `true` | Enable the global skill fallback |
| `global_skills.roots` | `["~/.agents/skills"]` | Shared skill dirs, checked after `{skill-root}` (name collisions: framework wins) |

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

### Compliance (v11.1)

| Key | Default | Purpose |
|-----|---------|---------|
| `compliance.enabled` | `true` | Enable compliance gate between stages |
| `compliance.mode` | `gate` | `gate` = blocking, `advisory` = warning only |
| `compliance.check_before_stage` | `true` | Run `--check-compliance` before each stage |
| `compliance.enforce_tool_scope` | `true` | Block tool calls not permitted for current stage |

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

### Dynamic Graph

| Key | Default | Purpose |
|-----|---------|---------|
| `dynamic_graph.enabled` | false | Enable dynamic graph construction |
| `dynamic_graph.parallel_qa` | false | Run QA stages in parallel (fan-out/fan-in) |
| `dynamic_graph.log_topology` | true | Save graph topology to state.json |

### State History (v11.2)

| Key | Default | Purpose |
|-----|---------|---------|
| `state_history.enabled` | true | Save snapshot after each stage |
| `state_history.retention_per_stage` | 5 | Max snapshots to keep per stage |
| `state_history.history_dir` | `.eng/history` | Directory for state snapshots |

---

## State Management

### State Files

| File | Location | Purpose |
|------|----------|---------|
| `state-template.json` | `{framework-root}/` | Template (git-tracked, 34 stages) |
| `state.json` | `{loop-root}/` | Runtime state (gitignored) |
| `STATE.md` | `{loop-root}/` | Human-readable state + decisions + handoff (gitignored) |
| `.eng/history/*.json` | `{loop-root}/` | State snapshots per stage for time travel (v11.2, gitignored) |

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
| `work_type` | enum | `feature` / `bugfix` / `operational` (v11.1) |
| `work_item` | object | Validated work item data |
| `decisions` | array | AD-NNN decision records |
| `graph_topology` | object | Compiled graph topology (v11 dynamic graph) |
| `active_nodes` | array | List of active node IDs for current work item |
| `parallel_groups` | object | Fan-out/fan-in group definitions |
| `tags` | array | Work item tags used for graph filtering |

---

## Directory Structure

```
.engineering-loop/ (framework repo)
├── ORCHESTRATOR.md              # Main orchestrator instructions
├── CORE.md                      # Framework index: stages, references, skills
├── config-template.yaml         # Framework configuration defaults
├── state-template.json          # Initial state for all 34 stages
├── skill-index.md               # Skill registry with improvement log
├── README.md                    # This file
├── .gitignore                   # Project file exclusions
├── AGENTS.md                    # Agent-specific instructions
│
├── stages/                      # Stage procedures (read-only, 26 files)
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
├── skills/                      # Specialized skills (read-only, 22 skills)
│   ├── bmad-bdd-mapper/         # BDD journey mapping
│   ├── bmad-ideation/           # Party Mode, Brainstorming, SDD
│   ├── bmad-integration/        # BMAD → work item transformation
│   ├── e2e-playwright/          # Playwright E2E testing
│   ├── essence/                 # Four Lenses validation
│   ├── graphify/                # Knowledge graph
│   ├── implementation-architect/ # Implementation blueprints
│   ├── requirements-refiner/    # Requirements quantification
│   ├── solution-designer/       # Solution architecture
│   └── verifier/                # Independent verification
│
├── eng_loop/                    # LangGraph orchestrator (Python)
│   ├── pyproject.toml           # Package config (langgraph, langchain-openai, pydantic)
│   ├── src/eng_loop/
│   │   ├── state.py             # PipelineState, 34 stages, reducers
│   │   ├── config.py            # YAML loader, deep merge, paths
│   │   ├── graph.py             # Delegates to GraphBuilder in dynamic mode
│   │   ├── graph_builder.py     # Dynamic graph construction per work item
│   │   ├── node_registry.py     # NodeSpec + registry of 34 stages
│   │   ├── edge_rules.py        # Declarative edge rules (~40 rules)
│   │   ├── routing.py           # Conditional edge functions, iteration tracking
│   │   ├── model.py             # Model factory (local OpenAI-compatible)
│   │   ├── schemas.py           # 27 Pydantic schemas (stages) + 9 dynamic schemas (v11.5)
│   │   ├── templates.py         # Markdown → prompt loader
│   │   ├── cli.py               # Entry point
│   │   ├── nodes/               # Stage node implementations
│   │   │   ├── dynamic_architect.py  # LLM proposal → framework authorization (v11.5)
│   │   │   └── meta_executor.py      # Sequential cursor-based executor (v11.5)
│   │   └── tools/               # Helpers
│   │       ├── dynamic_validation.py  # Typed validation engine (v11.5)
│   │       ├── policy_resolver.py     # Blueprint authorization, tool sandbox (v11.5)
│   │       ├── file_ops.py      # read/write/json helpers
│   │       ├── json_parse.py    # Robust JSON extraction (3 strategies)
│   │       ├── evidence_gate.py # Stage output quality validation
│   │       ├── stage_runner.py  # Shared stage execution helper
│   │       ├── context_slice.py # Context slicing per stage
│   │       ├── decisions.py     # AD-NNN extraction/recording
│   │       ├── lessons.py       # Lessons lifecycle
│   │       ├── autosizing.py        # Complexity + work type classification
│   │       ├── topology_compliance.py # Stage transition validation (v11.1)
│   │       ├── agent_runner.py      # Agentic loop + tool scope + error summarization + tool cache (v11.3)
│   │       ├── project_map.py       # Pre-computed structural overview (v11.3)
│   │       ├── progress.py          # Terminal logging, node tracing, breakpoint menu
│   │       ├── state_history.py     # Snapshot lifecycle, time travel, retention (v11.2)
│   │       └── interactive.py       # State slicing, $EDITOR integration (v11.2)
│   └── tests/                       # Unit tests
│
└── setup/                       # Installation scripts
    ├── install.sh               # Linux / Mac / WSL setup (+ pip install)
    ├── install.ps1              # Windows PowerShell setup (+ pip install)
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
- **Never skip the compliance gate** — `--check-compliance` must run before every stage transition (LLM mode)

### LLM Orchestrator Drift (v11.1)

- **Never skip stages because complexity is "small"** — auto-sizing determines active stages, you execute all of them
- **Never abandon the stage procedure to debug directly** — if debugging is needed, do it within the stage's sub-agent scope
- **Never modify project files outside your stage's allowed scope** — each stage has defined ALLOWED/FORBIDDEN actions
- **Never assume a stage is "not needed" based on your judgment** — the topology is authoritative
- **Never proceed past a compliance violation** — the gate exists to catch exactly these situations

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
- For Lens 4: Respond to scope clarification prompt (narrow/accept/redefine)
- If `max_clarification_attempts` exceeded: manually resolve the input ambiguity
- Lens 4 scope tensions now ask before blocking — answer the clarification to proceed

### No Visibility During Long Runs

**Symptom:** Process appears frozen; no idea how long it has been running or what it is doing

**Resolution:**
- The **wall-clock timer** (displayed as `wall:HH:MM:SS`) tracks total elapsed time since CLI startup and persists across all recovery attempts
- Progress bar, spinner, and recovery panel all show wall-clock time
- Stage spinner shows: `(N tools, Xs, wall:HH:MM:SS)` with real-time updates
- If no spinner is visible, the agent runner emits a heartbeat every 5s with wall-clock time
- Recovery attempts display `[wall: HH:MM:SS]` so you can see cumulative time across retries
- The final Stage Timing table shows both per-stage totals and the wall-clock duration

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

### Model Connectivity Failed

**Symptom:** `eng-loop --check-model` fails with connection error

**Resolution:**
- Ensure your local model server is running at the configured `base_url`
- Check the model name matches what your server expects
- Use `--model-base-url` and `--model-name` to override

### LangGraph Import Error

**Symptom:** `ModuleNotFoundError: No module named 'eng_loop'`

**Resolution:**
- Run `pip install -e .eng/eng_loop/`
- Or re-run the install script: `bash .eng/setup/install.sh`

### Stage Node Crashes

**Symptom:** Loop halts with a Python traceback

**Resolution:**
- v10.4: Pydantic schemas enforce output shape — most JSON errors are now caught automatically
- Increase `max_tokens` in config if responses are truncated
- Review `state.json` for the last successful stage
- Check evidence gate logs for quality validation failures

### Evidence Gate Retries

**Symptom:** Stage retries multiple times before advancing

**Resolution:**
- The evidence gate validates output quality (e.g., blueprint must have tasks, verdict must be PASS/FAIL)
- If the model consistently produces low-quality output, try a more capable model
- Check the work item for clarity — ambiguous inputs produce ambiguous outputs
- Review `state.json` errors for specific evidence gate messages

### Structured Output Errors

**Symptom:** Stage fails with Pydantic validation error

**Resolution:**
- This should not happen with `with_structured_output()` — the schema is enforced
- If it occurs, the model may not support structured output; try a different model
- Ensure your model endpoint supports function calling / structured output
- Check that `max_tokens` is high enough for the full response

### Lessons Not Propagating

**Symptom:** Same failure occurs across projects

**Resolution:**
- Verify `lessons.enabled` is `true` in `config.yaml`
- Check `lessons.confirm_threshold` — may need to lower from default (2)
- Ensure `lessons-shared.json` is committed to the framework repo after post-loop

### Dynamic Graph Not Building

**Symptom:** `--build-topology` fails or produces empty topology

**Resolution:**
- Ensure `eng_loop` is installed: `pip install -e .eng/eng_loop/`
- Check that the work item is not empty: `-w "your work item"`
- Verify paths are correct: `-f .eng -l .eng -p .`
- Review `artifacts/graph-topology.md` for the generated plan

### Breakpoint Not Pausing

**Symptom:** `--pause-at "impl.code"` does not pause at the specified stage

**Resolution:**
- Stage IDs use dot notation: `impl.code`, not `impl-code`
- The stage must be active in the current graph (check complexity/work type filters)
- Use `eng-loop history` to verify snapshots are being saved
- Verify `state_history.enabled` is `true` in `config.yaml`

### Rollback Fails — No Snapshot Found

**Symptom:** `eng-loop rollback "impl.code"` says "No snapshot found"

**Resolution:**
- The loop must have executed at least one stage before the target stage
- Use `eng-loop history` to list available snapshots
- Check that `state_history.enabled` is `true` in `config.yaml`
- Snapshots are stored in `.eng/history/` — verify the directory exists

### State Editor Won't Open

**Symptom:** Breakpoint [E]dit fails to open an editor

**Resolution:**
- Ensure `$EDITOR` is set, or one of: vim, nano, code (VS Code), notepad.exe is available
- The fallback chain is: `$EDITOR` → vim → nano → `code --wait` → notepad.exe
- On Windows, `code --wait` requires VS Code CLI installed (`code --install-extension`)
- The editor opens a temporary JSON file with the state slice for the current stage

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
| v10.3.0 | 2026-08-01 | **LangGraph orchestrator**: Programmatic flow control, 26 stage nodes, local model support (OpenAI-compatible), CLI (`eng-loop`), markdown as prompt templates, per-stage model overrides |
| v10.4.0 | 2026-08-04 | **Structured output + evidence gates**: 27 Pydantic schemas (one per stage), `model.with_structured_output()` enforces output shape, evidence gates validate quality before advancing, robust JSON extraction (3 strategies), automatic retry on failure, iteration counter tracking, `json_parse.py`, `evidence_gate.py`, `schemas.py`, `stage_runner.py` |
| v11.0.0 | 2026-08-10 | **Dynamic graph engineering**: `GraphBuilder` constructs graph per work item based on complexity/UI/tags. `NodeRegistry` (26 NodeSpec), `EdgeRulesEngine` (declarative routing). Parallel QA fan-out/fan-in. CLI: `--dynamic-graph`, `--parallel-qa`, `--build-topology`. Config: `dynamic_graph.enabled`. Topology saved to `state.json.graph_topology`. Static graph mode preserved for backward compatibility |
| v11.1.0 | 2026-08-11 | **Dynamic graph enforcement**: Work type classification (feature/bugfix/operational) generates different topologies. Compliance gate (`--check-compliance`) validates stage transitions. Edge bypass skips inactive intermediate nodes automatically. Tool scope enforcement blocks out-of-scope tool calls. Smart error summarization protects context from stack traces. Stage scope rules (ALLOWED/FORBIDDEN) per stage. Topology markdown includes checklist, deactivated stages, stage scope. `topology_compliance.py`, `autosizing.py` extended, `agent_runner.py` middleware |
| v11.2.0 | 2026-08-12 | **Surgical CLI operations**: Breakpoint pauses (`--pause-at`) with LangGraph `interrupt_before` + `MemorySaver`. State editing via `$EDITOR` with context slicing (`interactive.py`). Time-travel rollback (`eng-loop rollback`) from per-stage snapshots (`state_history.py`). Single-step replay (`eng-loop run-node`). State mutation (`eng-loop clear-state`, `eng-loop skip-node`). Snapshot listing (`eng-loop history`). Retention policy per stage. Editor fallback chain: `$EDITOR` → vim → nano → `code --wait` → notepad |
| v11.3.0 | 2026-08-13 | **Context optimization**: `ProjectMap` pre-computed at init eliminates 3-8 exploratory glob/read per stage (ASCII tree, configs, entry points, modules, languages, routes, components). `ToolResultCache` in micro-loop eliminates redundant read/glob/grep calls with targeted invalidation on edit/write (full invalidation on bash). Graphify prompt softened from imperative to passive. `project_map.py` (370 lines), `ToolResultCache` in `agent_runner.py`, 29 new tests |
| v11.4.0 | 2026-08-14 | **Contract gate middleware + causal rollback**: `contract_gate.py` validates handoff contracts between stages (blueprint→code, code→verify); retries source or blocks pipeline. `qa_parallel.py` fan-out/fan-in with `qa-dispatcher` + `qa-join` for parallel QA. `rollback_to_stage` reducer resets causal chain (impl.code → verify) on verifier/QA failure. `impl.code` FIX MODE with structured `fix_tasks`. Deterministic `init-setup` node separates classification from LLM. State reducers: `_merge_dict`, `_overwrite` (clear fields), `rollback_to_stage`. Edge rules: conditional blueprint validation, blocked-aware routing. Dry-run simulator: 4 scenarios (HAPPY_PATH, CONTRACT_VIOLATION, VERIFY_ROLLBACK, QA_FANOUT_FAIL) — all assertions green |
| v11.5.0 | 2026-08-15 | **Dynamic Node Orchestration (V1.3)**: Meta-orchestration layer for runtime sub-task generation beyond the 26-stage pipeline. `dynamic-architect` node (LLM proposes `DynamicBlueprintProposal` → framework authorizes via `authorize_blueprint()` → immutable `DynamicBlueprint`). `meta-executor` node (sequential cursor-based execution, strict attempt counting, typed validation). 9 new Pydantic schemas (frozen payloads, discriminated union rules, audit entries). Policy resolver: risk keyword analysis, tool sandboxing (safe pool). Validation engine: `tests_pass` (subprocess), `files_exist` (path check), `contains_symbol` (regex). Governance: `MAX_DYNAMIC_STEPS=5`, `max_attempts` per step (1-5), `authorized_complexity` override. Topology: `__start__ → init-setup → dynamic-architect → [meta-executor loop] → init`. 54 tests, 29 total nodes |
| v11.6.0 | 2026-08-16 | **Graph integrity + evidence-based status**: Honest task outcome (`compute_task_outcome()`) — DONE/FAILED/PARTIAL/WARNINGS. Post stage propagates failure instead of forcing DONE. Artifact evidence tracking (existência verificada vs declarada). Topology fidelity (proposed vs compiled). Result rendering evidencia-based (stages ativos, artefatos, falhas). Tool aliases (snake_case + camelCase). LangGraph warning suppression. 117 integration tests (1603 total) |
| v11.6.1 | 2026-08-16 | **Graph integrity + evidence-based status**: Honest task outcome (`compute_task_outcome()`) — DONE/FAILED/PARTIAL/WARNINGS. Post stage propagates failure instead of forcing DONE. Artifact evidence tracking (existência verificada vs declarada). Topology fidelity (proposed vs compiled). Result rendering evidencia-based (stages ativos, artefatos, falhas). Tool aliases (snake_case + camelCase). LangGraph warning suppression. 117 integration tests (1603 total) |
| v12.1.0 | 2026-08-17 | **Skills v2.0 — Comprehensive improvement across 13 skills**: persona-simulator (structured profiles, SEQ/SUS scoring from Avenir-UX), verifier (equivalent mutant filtering, mutation feedback loop from agentpatterns.ai/MUTGEN), ux-auditor (WCAG 2.2, Nielsen heuristics, SEQ/SUS), bmad-bdd-mapper (Scenario Outline, hooks, tag strategy), tester-unit (two-step prompting, boundary value analysis, mutation score), linter-agent (security analysis, maintainability index, false positive handling), requirements-refiner (INVEST/SMART scoring, risk matrix, conflict detection), solution-designer (ADR format, STRIDE threat modeling, API design principles), implementation-architect (testing strategy, CI/CD pipeline, rollback plan), bmad-ideation (Hourglass Framework, idea evaluation matrix, convergence techniques), e2e-playwright (visual regression, trace viewer, Playwright MCP), graphify (data flow tracing, dead code detection, incremental updates) |
| v12.2.1 | 2026-08-20 | **Essence Lens 4 clarification + wall-clock visibility**: Lens 4 scope/complexity tensions now ask user for clarification (narrow/accept/redefine) instead of terminal block; only blocks if `max_clarification_attempts` exhausted. Global wall-clock timer (`start_global_wall_clock()`) set once at CLI entry, persists across all recovery attempts. All progress displays (spinner, progress bar, recovery panel, heartbeat, dashboard) show real-time wall-clock elapsed time. 138 tests passing |
| v12.4.0 | 2026-08-30 | **FF Protocol — Fail Fast**: Parallel swarm-based development. Two sub-agents cross-analyze, judge approves, swarm executes. No waves. No graphs. Just blocks. FF is the default development mode. Removed motor from consumer projects (`.eng/` is trimmed). |

---

## Files at a Glance

| File | Role |
|------|------|
| `eng_loop/` | LangGraph orchestrator — run `eng-loop -w "..."` to start |
| `eng_loop/src/eng_loop/node_registry.py` | 34 NodeSpec registrations |
| `eng_loop/src/eng_loop/edge_rules.py` | Declarative edge rules |
| `eng_loop/src/eng_loop/graph_builder.py` | Dynamic graph construction |
| `eng_loop/src/eng_loop/schemas.py` | 52 Pydantic schemas for structured output |
| `eng_loop/src/eng_loop/tools/json_parse.py` | Robust JSON extraction (3 strategies) |
| `eng_loop/src/eng_loop/tools/evidence_gate.py` | Stage output quality validation |
| `eng_loop/src/eng_loop/tools/stage_runner.py` | Shared stage execution helper |
| `eng_loop/src/eng_loop/tools/topology_compliance.py` | Stage transition validation (v11.1) |
| `eng_loop/src/eng_loop/tools/agent_runner.py` | Agentic loop + tool scope + error summarization + ToolResultCache (v11.3) |
| `eng_loop/src/eng_loop/tools/contract_gate.py` | Handoff contract middleware + `@with_contract_gate` decorator (v11.4) |
| `eng_loop/src/eng_loop/nodes/init_setup.py` | Deterministic setup: classify, graphify, deactivate stages (v11.4) |
| `eng_loop/src/eng_loop/nodes/qa_parallel.py` | `qa-dispatcher` (fan-out) + `qa-join` (fan-in + rollback) (v11.4) |
| `eng_loop/src/eng_loop/state.py` | Reducers: `_merge_dict`, `_overwrite`, `rollback_to_stage` (v11.4) |
| `eng_loop/src/eng_loop/schemas.py` | 9 dynamic schemas: payloads, rules, steps, blueprint, runtime, audit (v11.5) |
| `eng_loop/src/eng_loop/tools/dynamic_validation.py` | Typed validation engine: tests_pass, files_exist, contains_symbol (v11.5) |
| `eng_loop/src/eng_loop/tools/policy_resolver.py` | Blueprint authorization, tool sandboxing, risk keywords (v11.5) |
| `eng_loop/src/eng_loop/nodes/dynamic_architect.py` | LLM proposal → framework authorization → executable blueprint (v11.5) |
| `eng_loop/src/eng_loop/nodes/meta_executor.py` | Sequential cursor-based executor, strict attempt counting (v11.5) |
| `scripts/dry_run_simulator.py` | 4 scenario dry-run tests, zero LLM calls (v11.4) |
| `eng_loop/src/eng_loop/tools/project_map.py` | Pre-computed structural project map (v11.3) |
| `eng_loop/src/eng_loop/tools/state_history.py` | Snapshot lifecycle, time travel, retention (v11.2) |
| `eng_loop/src/eng_loop/tools/interactive.py` | State slicing, $EDITOR integration (v11.2) |
| `ORCHESTRATOR.md` | Legacy entry point — prompt-based mode (deprecated) |
| `CORE.md` | Framework index — stage registry, references, skills |
| `skill-index.md` | Skill registry — ID → skill mapping with improvement log |
| `config-template.yaml` | Framework defaults — model config, constraints, paths |
| `state-template.json` | State template — 34 stages with done/attempts/essence_checked |
| `AGENTS.md` | Agent instructions — framework editing guidelines |
| `README.md` | This file — comprehensive documentation |
| `artifacts/graph-topology.md` | Generated execution plan (LLM mode) |
