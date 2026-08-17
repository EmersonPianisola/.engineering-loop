---
name: engineering-loop-readme
type: entry-point
description: 'Comprehensive framework documentation.'
---

# Engineering Loop v12.1

**New user? Start with [`START.md`](START.md) — quick reference for running the loop.**

Persistent **while-loop engine** for AI-assisted software development. **Dynamic graph construction** — the LangGraph StateGraph is built per work item based on complexity, UI context, work type, and tags. Only the nodes required for the task are instantiated. Pydantic structured output and evidence gates enforce quality. Auto-sizes depth by complexity and work type. Delegates every phase to specialized sub-agents via progressive disclosure. Validates all inputs with the Essence Sidecar before any work begins. Enforces topology compliance between stages. Self-improves through lessons learned across projects. **Surgical CLI operations** — breakpoints, state editing, time-travel rollback, and single-step replay. **Context optimization** — pre-computed project map eliminates exploratory tool-calls, tool result cache prevents redundant reads. **Dynamic Node Orchestration** — blueprint-driven meta-execution with typed validation, policy authorization, and immutable contracts.

| | |
|---|---|
| **Version** | 11.5.0 |
| **Dynamic Orchestration** | Blueprint imutável, runtime desacoplado, validação tipada (v11.5) |
| **Policy Resolver** | Autorização autoritativa de risco, sandbox de ferramentas |
| **Meta-Executor** | Loop sequencial com cursor, auditoria por passo, retry estrito |
| **Contract Gate** | Middleware validates handoff contracts between stages |
| **Causal Rollback** | `rollback_to_stage` reducer resets causal chain on verifier/QA failure |
| **Fix Mode** | `impl.code` executes with structured `fix_tasks` from verifier/QA |
| **Dry-Run Simulator** | 4 scenarios validated: HAPPY_PATH, CONTRACT_VIOLATION, VERIFY_ROLLBACK, QA_FANOUT_FAIL |
| **Deterministic Setup** | `init-setup` node separates classification from LLM |
| **State Reducers** | `_merge_dict`, `_overwrite` (clear fields), `rollback_to_stage` |
| **Architecture** | Multi-project via git submodule |
| **Orchestrator** | `eng_loop/` (LangGraph Python, Dynamic Graph, Pydantic schemas) |
| **LLM Mode** | `ORCHESTRATOR.md` (topology-enforced, compliance gate, Python builds graph) |
| **Stages** | 26 static + 2 meta (architect, executor) = 29 nodes |
| **Skills** | 14 built-in (all v2.0) + 7 self-constructed at runtime |
| **Structured Output** | Pydantic schemas per stage, evidence gates |
| **Dynamic Graph** | `GraphBuilder` constructs graph per work item + work type |
| **Work Types** | `feature`, `bugfix`, `operational` — different topologies per type |
| **Compliance** | `--check-compliance` gate between stages (LLM mode) + tool scope enforcement (CLI mode) |
| **Edge Bypass** | Automatic bypass of inactive intermediate nodes |
| **Surgical CLI** | `rollback`, `run-node`, `clear-state`, `skip-node`, `history` + `--pause-at` (v11.2) |
| **State History** | Snapshots per stage with retention policy (v11.2) |
| **Entry point** | `CORE.md` |
| **CLI** | `eng-loop --dynamic-graph --work-item "..."` |
| **Configuration** | `config-template.yaml` (framework) + `config.yaml` (project) |

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Dynamic Graph (v11)](#dynamic-graph-v11)
- [Dynamic Node Orchestration](#dynamic-node-orchestration-v115)
- [Dual-Mode Architecture](#dual-mode-architecture)
- [LangGraph Orchestrator](#langgraph-orchestrator)
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
- [Context Optimization](#context-optimization-v113)
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

The loop is enforced by a **dynamic LangGraph StateGraph** (Python) that is **constructed per work item** — only the nodes required for the task are instantiated based on complexity, UI context, and tags. Stage procedures remain as markdown templates in `stages/`, loaded at runtime and injected as prompts. The orchestrator works with any OpenAI-compatible local model (llama.cpp, vLLM, Ollama).

### Core Principles

- **Dynamic graph construction** — `GraphBuilder` builds the graph per work item; only active nodes are instantiated
- **Programmatic flow control** — LangGraph StateGraph enforces stage order, retries, and resets in code (not prompts)
- **Structured output** — Every stage uses Pydantic schemas via `model.with_structured_output()` — no free-form JSON
- **Evidence gates** — Every stage output is validated against quality criteria before advancing; failures trigger automatic retry
- **Declarative routing** — `EdgeRule` rules define connections between nodes; resolved at build time
- **Node registry** — 26 stages registered as `NodeSpec` with metadata (complexity, phase, parallel group)
- **Orchestrator is pure delegation** — never executes work directly (except `deploy.prepare` and `post-loop` finalize)
- **Progressive disclosure** — stages, references, and skills loaded by ID only when needed
- **Context slicing** — each sub-agent receives only its relevant context; full artifacts are never passed to one agent
- **Context optimization** — ProjectMap pre-computed at init eliminates 3-8 exploratory glob/read per stage; tool result cache prevents redundant reads within a micro-loop
- **Full loop enforcement** — every active stage must execute; user requests are focus directives, not skip directives
- **Essence before every stage** — inputs validated through Four Lenses before any work begins
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

## Quick Start

### 1. Prerequisites

- **Python 3.10+** with pip
- **Local model server** running on `http://localhost:8000` (llama.cpp, vLLM, Ollama, etc.)
  - Or configure your own endpoint in `config.yaml` → `model.base_url`

### 2. Add as Git Submodule

```bash
git submodule add <engineering-loop-url> .eng
git commit -m "Add engineering loop framework"
```

### 3. Run Setup

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
- Installs the `eng_loop` Python package (`pip install -e eng_loop/`)

### 4. Customize Configuration

Review `.eng/config.yaml`:
- `model.base_url` — your local model endpoint (default: `http://localhost:8000`)
- `model.model` — model name (default: `qwable-v2`)
- `constraints` — per-stage iteration limits
- `hardware` — context window, parallel agents, timeouts

### 5. Run the Loop

```bash
# Static graph (legacy, default)
eng-loop -w "Add user authentication with JWT tokens" -f .eng -l .eng -p .

# Dynamic graph (v11, recommended)
eng-loop --dynamic-graph -w "Add user authentication with JWT tokens" -f .eng -l .eng -p .

# Hybrid mode: Python graph + OpenCode native tools
eng-loop --dynamic-graph --opencode-agent -w "Add user authentication with JWT tokens" -f .eng -l .eng -p .

# Dynamic graph with parallel QA
eng-loop --dynamic-graph --parallel-qa -w "Add user authentication with JWT tokens" -f .eng -l .eng -p .

# Build topology for LLM orchestrator
eng-loop --build-topology -w "Add user authentication with JWT tokens" -f .eng -l .eng -p .

# With breakpoints (v11.2) — pause before specific stages
eng-loop --dynamic-graph --pause-at "impl.code" verify -w "Add user authentication with JWT tokens" -f .eng -l .eng -p .
```

### 5b. Surgical Commands (v11.2)

Intervene in the loop state without re-running the entire graph:

```bash
# Time Travel — restore state to before a stage
eng-loop rollback "impl.code"

# Single-Step Replay — execute one node in isolation
eng-loop run-node "impl.code" --from-state state.json

# Reset Attempts — clear stage attempts counter
eng-loop clear-state "qa.security" --reset-attempts

# Force Skip — mark a stage as done
eng-loop skip-node "arch.review"

# List State Snapshots
eng-loop history
```

The orchestrator:
1. Detects framework and project roots automatically
2. Loads config (template defaults + project overrides)
3. Auto-sizes complexity
4. **Builds dynamic graph** — only nodes needed for this work item are instantiated
5. Executes the LangGraph pipeline with Essence gates
6. Saves state (including graph topology) to `.eng/state.json` after each iteration

### LLM Prompt Mode (Topology-Enforced + Compliance Gate)

Load `ORCHESTRATOR.md` in your AI agent session. The orchestrator instructs the LLM to:
1. Run `eng-loop --build-topology -w "work item"` — Python generates the dynamic graph
2. Read `{artifact-root}/graph-topology.md` — the execution plan with active stages, routing rules, constraints
3. **Before each stage:** Run `eng-loop --check-compliance --requested-stage <stage>` — validates transition
4. Follow the plan exactly — active stages, routing rules, constraints

This solves the problem of LLM ignoring the loop: the graph is built by Python, the compliance gate enforces transitions, and the LLM follows the validated plan.

---

## Dynamic Graph (v11.1)

v11 introduces **dynamic graph construction** — the LangGraph StateGraph is built per work item based on complexity, UI context, work type, and tags. Only the nodes required for the task are instantiated.

### How It Works

```
WORK ITEM
    │
    ▼
┌──────────────────────────┐
│    GraphBuilder           │  ← Analyzes work item context
│  (classify complexity)    │
│  (classify work type)     │  ← v11.1: feature / bugfix / operational
└──────────┬───────────────┘
           │
    ┌──────▼───────────┐
    │   NodeRegistry    │  ← Filters 26 nodes → active subset
    │   + EdgeRules     │  ← Resolves edges + bypasses inactive intermediaries
    └───────────────────┘
           │
    ┌──────▼───────────┐
    │  StateGraph       │  ← Compiled LangGraph (only active nodes)
    │  (compiled)       │
    └───────────────────┘
           │
    EXECUTION
```

### Work Type Classification (v11.1)

The graph builder classifies each work item into one of three types:

| Type | Description | Topology Effect |
|------|-------------|----------------|
| **feature** | New functionality | Full loop: design → arch → impl → verify → QA → deploy |
| **bugfix** | Fix existing behavior | Skips design stages (6), keeps impl + verify |
| **operational** | Run existing code (tests, deploys) | Skips impl, design, arch, verify; runs e2e → deploy → smoke → post |

Classification uses two-tier keyword matching (multi-word phrases + single words) for both Portuguese and English. When an operational work item like `"Execute todos os testes E2E"` is detected, the graph only instantiates the 7 stages needed for execution — not the 11+ stages for feature development.

### Components

| Component | Purpose |
|-----------|---------|
| `node_registry.py` | 26 stages registered as `NodeSpec` with metadata (complexity, phase, parallel group) |
| `edge_rules.py` | Declarative `EdgeRule` connections between nodes (~40 rules) |
| `graph_builder.py` | `GraphBuilder` class that builds and compiles the graph |
| `graph.py` | Delegates to `GraphBuilder` when dynamic mode is enabled; static mode preserved |
| `cli.py --build-topology` | Generates topology markdown for LLM orchestrator |

### NodeSpec

Each stage is registered with metadata that the GraphBuilder uses to filter:

```python
NodeSpec(
    id="qa.security",
    node_name="qa-security",
    handler=qa_node("qa.security"),
    phase="qa",
    min_complexity="medium",   # Only active for medium+
    parallel_group="qa",       # Fan-out/fan-in group
)
```

### Edge Rules

Connections between nodes are declarative rules evaluated at build time:

```python
EdgeRule(
    from_node="verify",
    to_node="qa-security",
    condition=lambda s: s["complexity"] >= "medium" and s["stages"]["verify"]["done"],
    edge_type="conditional",
)
```

### Topology Output

The `--build-topology` flag generates a markdown execution plan:

```markdown
# DYNAMIC GRAPH TOPOLOGY — GENERATED EXECUTION PLAN

## Context
- **Work Item:** Add OAuth2 login with RBAC
- **Complexity:** large
- **UI Project:** False
- **Active Nodes:** 22/26

## ACTIVE STAGES (execute in this order)
| # | Stage ID | Phase |
|---|----------|-------|
| 1 | `init` | INIT |
| 2 | `init.ideate` | INIT |
| ...

## ROUTING RULES (deterministic)
### Post-Verify (PASS)
- IF complexity >= `medium` → `qa.security`
- IF complexity == `small` → `deploy.prepare`

## CONSTRAINTS
| Stage | Max Attempts |
|-------|-------------|
| `impl.code` | 3 |
| `verify` | 3 |
| ...
```

### Graph Size by Complexity

| Complexity | Static (v10) | Dynamic (v11) | Savings |
|------------|-------------|---------------|---------|
| **Small** | 28 nodes | ~9 nodes | ~65% |
| **Medium** | 28 nodes | ~20 nodes | ~29% |
| **Large (UI)** | 28 nodes | ~24 nodes | ~14% |
| **Complex (UI)** | 28 nodes | 26 nodes | ~7% |

### Graph Size by Work Type (v11.1)

| Work Type | Active Stages (small + UI) | Description |
|-----------|--------------------------|-------------|
| **feature** | 11 stages | Full loop: init → impl → verify → e2e → deploy → post |
| **bugfix** | ~11 stages | Skips design stages, keeps impl + verify |
| **operational** | 7 stages | Skips impl, design, arch, verify; runs e2e → deploy → post |

### Parallel QA

With `--parallel-qa`, the three QA stages (`security`, `api-contract`, `performance`) execute in parallel via LangGraph fan-out/fan-in:

```
        verify (PASS)
           │
    ┌──────┼────────┐
    ▼      ▼        ▼
  qa-sec  qa-api  qa-perf    ← fan-out, parallel
    │      │         │
    └──────┼─────────┘
           ▼
    qa-join (fan-in)         ← aggregate results
           ▼
     deploy-prepare
```

### Enable

```bash
# CLI flag
eng-loop --dynamic-graph -w "work item"

# Config (persistent)
# config.yaml
dynamic_graph:
  enabled: true
  parallel_qa: true
  log_topology: true
```

---

## Contract Gate Middleware (v11.4)

Middleware that validates handoff contracts between stages. If a contract is violated, the gate retries the source node or blocks the pipeline.

### How It Works

```
Node A (complete)
    │
    ▼
┌──────────────────┐
│  Contract Gate   │  ← Validates source→target contract
│  (middleware)     │
└───────┬──────────┘
        │
   ┌────┴────┐
   │         │
 PASS      FAIL
   │         ├── retry_source → Node A (reset done=False)
   │         └── block → __end__ (if max attempts exhausted)
   ▼
Node B (proceed)
```

### Contract Rules

| Source | Target | Validator | On Fail |
|--------|--------|-----------|---------|
| `impl-design` | `impl-code` | Blueprint must have tasks + ≥50 chars | Retry or block |
| `impl-code` | `doc-update` | Files created, tests passing, summary ≥20 chars | Retry or block |
| `doc-update` | `verify` | impl.code artifacts exist in state | Retry or block |
| `verify` | `qa-security` | Verdict is PASS/FAIL with evidence | Retry or block |
| `arch-solution` | `arch-review` | Requirements + solution both exist | Block |

### Edge Integration

Edge rules check contract validity before routing. The `impl-design→impl-code` edge is conditional on `_blueprint_valid(state)` — if the blueprint fails validation, the edge doesn't activate, preventing impl.code from running with bad input.

---

## Causal Chain Rollback (v11.4)

When a verifier or QA stage fails, the `rollback_to_stage` reducer resets all stages in the causal chain back to `impl.code`, enabling clean re-execution.

### How It Works

```
impl.code (done) → doc.update (done) → verify (FAIL: 2 gaps)
    │
    ▼
rollback_to_stage(target="verify", reset_from="impl.code")
    │
    ▼
impl.code (reset) → doc.update (reset) → verify (reset)
    │
    ▼
impl.code runs in FIX MODE with structured fix_tasks
```

### Fix Mode

When `impl.code` receives `fix_tasks` from verifier/QA, it enters FIX MODE:
- Reads `fix_tasks` and `fix_iteration` from state
- Prompt includes each gap with file:line evidence
- Agent addresses each gap minimally (no full rewrite)
- On success, clears `fix_tasks`, `rollback_target`, and `fix_iteration`
- On repeated failure (≥3 iterations), pipeline blocks

---

## Dry-Run Simulator (v11.4)

Standalone test script that validates graph topology, state transitions, and routing — **without any LLM API calls**. All node handlers are mocked with deterministic `AgentResult` objects.

### Scenarios

| Scenario | What It Tests | Assertions |
|----------|--------------|------------|
| **HAPPY_PATH** | All stages pass, graph reaches `__end__` | No errors, no rollback, all stages done |
| **CONTRACT_VIOLATION** | impl.design returns empty blueprint | Contract gate catches violation, pipeline blocks |
| **VERIFY_ROLLBACK** | verify FAILs → rollback → fix → verify PASSes | fix_iteration ≥ 1, fix_tasks cleared, verify done |
| **QA_FANOUT_FAIL** | qa-security PASS, qa-api-contract FAIL | fix_tasks from QA, rollback to impl.code, blocks after fix limit |

### Usage

```bash
# Run all scenarios
python scripts/dry_run_simulator.py --scenario ALL

# Run single scenario
python scripts/dry_run_simulator.py --scenario VERIFY_ROLLBACK
```

### Architecture

```
Dry-Run Simulator
├── InvocationTracker     ← Tracks run_agent calls per stage
├── Mock Functions        ← Deterministic AgentResult per scenario
├── Scenario Registry     ← Configuration (complexity, work_type, parallel_qa)
└── Assertion Helpers     ← assert_true, assert_false, assert_equals, etc.
```

Mocks intercept:
- `eng_loop.tools.agent_runner.run_agent` — returns scenario-specific `AgentResult`
- `eng_loop.model.create_model_from_config` — returns `MagicMock`

---

---

## Dynamic Node Orchestration (v11.5)

Meta-orchestration layer that enables runtime generation of sub-tasks beyond the standard 26-stage pipeline. The LLM proposes dynamic steps, the framework authorizes them via policy rules, and a cursor-based meta-executor runs them sequentially with strict attempt counting and typed validation.

### Architecture

```
__start__ → init-setup → dynamic-architect
                        ├─ trigger="augment" → meta-executor (loop) → init
                        └─ trigger="none"    → init (passthrough)
```

### Design Principles

1. **Blueprint Imutável** — O gerador dinâmico produz um plano estruturado estático. Ele nunca toma decisões de fluxo de controle (`goto`).
2. **Runtime Desacoplado** — O contrato do passo (`DynamicStep`) permanece puro e imutável. O estado de execução (tentativas, cursor, falhas) reside inteiramente em `dynamic_runtime`.
3. **Validação Tipada** — Critérios de aceite baseados em regras determinísticas (`tests_pass`, `files_exist`, `contains_symbol`), eliminando heurísticas de linguagem natural.
4. **Governança Estrita** — Tetos rígidos: `MAX_DYNAMIC_STEPS = 5`, `max_attempts` por passo (1-5), `authorized_complexity` derivada por política.
5. **Policy Autoritativa** — O framework é a autoridade de risco. Analisa o work item por keywords de risco e sobrepõe a complexidade proposta pelo LLM.

### Contracts (Pydantic Schemas)

| Schema | Role | Frozen |
|--------|------|--------|
| `DynamicBlueprintProposal` | Proposta do LLM (não autorizada) | Yes |
| `DynamicBlueprint` | Contrato executável oficial (autorizado) | Yes |
| `DynamicStep` | Passo individual imutável | Yes |
| `ValidationRule` | Regra tipada de validação | Yes |
| `DynamicRuntime` | Estado mutável de execução (cursor, attempts, audit) | No |
| `DynamicAuditEntry` | Registro imutável de auditoria por tentativa | Yes |

### Validation Rule Types

| Type | Payload | Behavior |
|------|---------|----------|
| `tests_pass` | `suite` (unit/integration/e2e), `command` | Executa comando via subprocess, verifica exit code == 0 |
| `files_exist` | `paths` (tuple) | Verifica existência de todos os caminhos relativos ao workspace |
| `contains_symbol` | `symbol` (regex), `target_file` | Busca padrão regex em arquivo alvo |

### Policy Authorization

The `authorize_blueprint()` function transforms the LLM proposal into an authorized executable blueprint:

- Analyzes `work_item` for risk keywords (`drop database`, `rm -rf`, `credentials`, `production deploy`, etc.)
- If risk detected → `authorized_complexity = "restricted"` → pipeline blocks, human approval required
- If safe → `authorized_complexity = proposal.proposed_complexity`

### Meta-Executor Flow

```
1. Sem plano ou trigger="none" → passthrough para pipeline estático
2. Cursor >= len(steps) → completed, avança para init
3. current_attempts > max_attempts → blocked, pipeline termina (__end__)
4. resolve_allowed_tools() → sandbox de ferramentas (whitelist)
5. run_agent() com prompt do step
6. evaluate_validation_rules() → validação tipada
   ├─ Valid + success → cursor++, completed[], retry self
   ├─ Invalid + attempts < max → retry self (cursor travado)
   └─ Invalid + attempts >= max → blocked, pipeline termina
```

**Correção off-by-one:** `current_attempts = runtime.attempts.get(step_id, 0) + 1`. A verificação `current_attempts > max_attempts` ocorre antes de executar, garantindo matematicamente que `max_attempts=3` = 1 execução + 2 retries.

### Components

| Component | Purpose |
|-----------|---------|
| `schemas.py` | 9 novas classes Pydantic (payloads, rules, steps, blueprint, runtime, audit) |
| `tools/dynamic_validation.py` | Evaluador de regras tipadas (`tests_pass`, `files_exist`, `contains_symbol`) |
| `tools/policy_resolver.py` | Autorização de blueprint, sandbox de ferramentas, keywords de risco |
| `nodes/dynamic_architect.py` | Nó gate: LLM propõe → framework autoriza → blueprint injetado no estado |
| `nodes/meta_executor.py` | Executor sequencial com cursor, retry estrito, auditoria por passo |

### State Fields

| Field | Type | Purpose |
|-------|------|---------|
| `dynamic_plan` | `DynamicBlueprint` (dict) | Blueprint imutável gerado pelo Arquiteto |
| `dynamic_runtime` | `DynamicRuntime` (dict) | Estado mutável: cursor, attempts, completed, failed, audit |

---

## Dual-Mode Architecture

The loop runs in two modes:

| Mode | How | Enforcement |
|------|-----|-------------|
| **Python CLI** | `eng-loop --dynamic-graph` | LangGraph executes compiled graph — deterministic |
| **LLM Prompt** | LLM reads `ORCHESTRATOR.md` | LLM builds topology via Python, compliance gate enforces transitions |

### Python CLI Mode (deterministic)

```bash
eng-loop --dynamic-graph -w "Add OAuth2 login"
eng-loop --dynamic-graph --parallel-qa -w "Add OAuth2 login"
```

LangGraph compiles the graph from active nodes only. The LLM has no choice about routing. Tool scope enforcement blocks tool calls outside the current stage's permitted scope.

### LLM Prompt Mode (topology-enforced + compliance gate)

The LLM reads `ORCHESTRATOR.md`, which instructs it to:
1. Run `eng-loop --build-topology -w "work item"` — Python generates the graph
2. Read `{artifact-root}/graph-topology.md` — the execution plan
3. **Before each stage:** Run `eng-loop --check-compliance --requested-stage <stage>` — validates transition
4. Follow the plan exactly — active stages, routing rules, constraints

This solves the problem of LLM ignoring the loop: the graph is built by Python, the compliance gate enforces transitions, and the LLM follows the validated plan.

### Hybrid Mode (Python graph + OpenCode tools)

The `--opencode-agent` flag enables **hybrid execution**: Python (LangGraph) controls the graph, routing, state, and evidence gates, while **OpenCode CLI** executes each stage with native tools.

```bash
eng-loop --dynamic-graph --opencode-agent -w "Add OAuth2 login" -f .eng -l .eng -p .
```

Or via `config.yaml`:
```yaml
agent:
  backend: "opencode"
```

**Architecture:**

```
Python (LangGraph)              opencode run (subprocess)
┌─────────────────────┐         ┌──────────────────────────┐
│ Graph routing       │  prompt │ Native tools:            │
│ State management    │ ──────> │ read, write, edit,       │
│ Stage sequencing    │         │ bash, glob, grep         │
│ Evidence gates      │  <────  │ Session context          │
│ Complexity sizing   │ result  │ Permission sandbox       │
└─────────────────────┘         └──────────────────────────┘
```

**Why use hybrid mode?**

| Python CLI (`--dynamic-graph`) | Hybrid (`--opencode-agent`) |
|---|---|
| LangChain tool-calling loop | OpenCode native tools |
| Independent LLM agent instance | Full OpenCode session context |
| Python-implemented tools | Permission sandbox, agent plugins |
| No access to OpenCode features | All OpenCode capabilities |

---

## LangGraph Orchestrator

v10.3 migrated to programmatic flow control. v11 added dynamic graph construction. v11.1 added work type classification, compliance enforcement, and edge bypass.

### Why LangGraph

| Prompt-Based (v10.2) | LangGraph (v10.3) | v10.4 (Structured Output) | v11.0 (Dynamic Graph) | v11.1 (Enforcement) | v11.2 (Surgical CLI) | v11.3 (Context) | v11.4 (Contracts) |
|---|---|---|---|---|---|
| Model reads `ORCHESTRATOR.md` and follows instructions | `StateGraph` executes flow programmatically | `StateGraph` + Pydantic schemas enforce output shape | Graph built per work item — only active nodes instantiated | Work type classification (feature/bugfix/operational) | Breakpoint pauses with `interrupt_before` + `MemorySaver` | ProjectMap + ToolResultCache | Contract gate middleware, causal rollback |
| Model eventually drifts from the loop | Flow enforced by code — no drift possible | Evidence gates catch low-quality output before advancing | Declarative edge rules resolve connections at build time | Compliance gate (`--check-compliance`) enforces transitions | State editing via `$EDITOR` with context slicing | Pre-computed context eliminates redundant tool-calls | Contract gate validates handoffs, rollback resets causal chain |
| `WHILE loop` described in pseudocode | Edges with cycles + recursion limit | Automatic retry on evidence gate failure | Topology generated for LLM orchestrator mode | Edge bypass skips inactive intermediate nodes automatically | Time-travel rollback from per-stage snapshots | Graphify passive mode, ProjectMap pre-computed | Dry-run simulator validates 4 graph scenarios |
| `stage.attempts++` in text | State reducer increments automatically | Iteration counter tracks total loop progress | `NodeRegistry` (26 NodeSpec) filtered by complexity/UI/tags | Tool scope enforcement blocks out-of-scope tool calls | Single-step replay (`run-node`) for isolated testing |
| `IF attempts >= max → blocked` in prompt | Conditional edges route to `__end__` | LLM errors trigger retry, not silent pass | Parallel QA fan-out/fan-in via `--parallel-qa` | Smart error summarization protects context from stack traces | State mutation (`clear-state`, `skip-node`) for recovery | Tool cache with targeted invalidation | Contract gate retries/block, rollback reducer |
| `reset impl.code.done = false` in text | `Command(goto="impl-code", update={...})` | Structured output eliminates JSON parse failures | Graph size reduced by up to ~65% for small work items | Operational work items generate 7-stage graphs instead of 11+ | Snapshot retention policy, `history` command | Context window protected from redundant reads | FIX MODE, structured fix_tasks from verifier/QA |
| Lens 4 escalation via prompt | `interrupt()` native to LangGraph | 27 Pydantic schemas (one per stage) | Static graph mode preserved for backward compatibility | Stage scope rules (ALLOWED/FORBIDDEN) per stage | Editor fallback: `$EDITOR` → vim → nano → `code --wait` → notepad | 29 new tests, graphify passive prompt | 4 dry-run scenarios, deterministic init-setup |

### How Structured Output Works

Each stage has a Pydantic schema that defines the exact output shape. The model is invoked with `model.with_structured_output(Schema)`, which forces the LLM to produce valid output matching the schema:

```python
# schemas.py — one schema per stage
class VerifyOutput(BaseModel):
    verdict: str = Field(default="PASS", description="PASS or FAIL")
    per_ac_evidence: list[str] = Field(default_factory=list)
    discrimination_sensor: str = Field(default="pass")
    coverage_audit: str = Field(default="pass")
    gaps: list[str] = Field(default_factory=list)
    complete: bool = Field(default=True)

# In node:
structured = model.with_structured_output(VerifyOutput)
response = structured.invoke([{"role": "user", "content": prompt}])
result = response.model_dump()  # Guaranteed valid dict
```

### How Evidence Gates Work

After the LLM returns structured output, the evidence gate validates quality before the stage is marked as done:

```
LLM Response → Pydantic Schema → Evidence Gate → Stage Done?
                            ↓ (invalid)
                      Retry (bounded by max_attempts)
```

Evidence gates enforce stage-specific criteria:
- **verify**: Verdict must be `PASS` or `FAIL`; `FAIL` must include gaps
- **impl.design**: Blueprint must be >100 chars and include tasks
- **impl.code**: Implementation summary must be >50 chars
- **QA stages**: Verdict must be `PASS` or `FAIL`
- **init**: Work item must be valid or have a refinement

If evidence fails, the stage retries automatically (up to `max_{stage}_attempts`). If all attempts are exhausted, the stage forces through with a warning.

### Tool Scope Enforcement (v11.1)

During the agentic loop, each tool call is validated against the current stage's permitted tools:

```
LLM Tool Call → Scope Check → Execute Tool
            ↓ (out of scope)
    BLOCKED: "Tool 'X' not permitted in stage 'Y'"
```

This prevents the LLM from modifying files outside its stage's scope (e.g., editing `playwright.config.js` during `e2e.execute`). Each stage has defined ALLOWED and FORBIDDEN actions.

### Smart Error Summarization (v11.1)

When a tool call returns a large error output (>2000 chars), the framework extracts key signal before injecting into context:

- **Test output**: Extracts summary line (X failed, Y passed)
- **Python traceback**: Extracts last frame (file:line + exception)
- **JSON error**: Extracts error.message
- **Generic**: Extracts last 10 non-empty lines

This protects the context window from being flooded with stack traces while preserving diagnostic signal.

### Architecture

```
eng_loop/
├── state.py                  # PipelineState schema, 26 stages, reducers (_merge_dict, _overwrite, rollback_to_stage)
├── config.py                 # YAML loader, deep merge, path resolution
├── graph.py                  # Delegates to GraphBuilder in dynamic mode; static mode preserved
├── graph_builder.py          # Dynamic graph construction, contract gate integration, parallel QA wiring
├── node_registry.py          # NodeSpec + registry of 26 stages (+ init-setup, qa-dispatcher, qa-join)
├── edge_rules.py             # Declarative edge rules (~40 rules), conditional blueprint validation, blocked-aware
├── routing.py                # Conditional edge functions (retry, block, advance)
├── model.py                  # Model factory (OpenAI-compatible local endpoints)
├── schemas.py                # 27 Pydantic schemas (one per stage) for structured output
├── templates.py              # Markdown → prompt loader (stages/ → prompt templates)
├── cli.py                    # Entry point (eng-loop CLI) + compliance checker
├── nodes/                    # One node per stage group
│   ├── essence.py            # Four Lenses gate (pre-stage)
│   ├── init_setup.py         # Deterministic setup: classify complexity, graphify, deactivate stages
│   ├── init.py               # init, ideate, bdd, refine (LLM-only)
│   ├── design.py             # 6 design stages (factory)
│   ├── architecture.py       # requirements, solution, review
│   ├── implementation.py     # impl.design, impl.code (FIX MODE), doc.update
│   ├── verification.py       # verify (rollback + fix_tasks), e2e.execute
│   ├── qa.py                 # security, api-contract, performance (parallel_mode)
│   ├── qa_parallel.py        # qa-dispatcher (fan-out), qa-join (fan-in + rollback)
│   ├── deploy.py             # deploy.prepare, smoke.test
│   ├── documentation.py      # doc.decisions, doc.project
│   └── post.py               # post-loop finalize
└── tools/
    ├── file_ops.py           # read/write/json helpers
    ├── json_parse.py         # Robust JSON extraction (3 strategies)
    ├── evidence_gate.py      # Stage output quality validation
    ├── contract_gate.py      # Handoff contract middleware (blueprint→code, code→verify)
    ├── stage_runner.py       # Shared stage execution helper
    ├── context_slice.py      # Context slicing per stage
    ├── decisions.py          # AD-NNN extraction/recording
    ├── lessons.py            # Lessons lifecycle
    ├── autosizing.py         # Complexity + work type classification
    ├── topology_compliance.py # Stage transition validation (v11.1)
    ├── agent_runner.py       # Agentic loop + tool scope enforcement + error summarization
    └── progress.py           # Terminal logging, node tracing
```

### How It Works

1. **`eng-loop --work-item "..."`** starts the CLI
2. Config is loaded and merged (`config-template.yaml` + `config.yaml`)
3. **`GraphBuilder`** analyzes work item context, classifies complexity and work type, filters active nodes
4. **Edge bypass** resolves inactive intermediate nodes automatically (v11.1)
5. `StateGraph` is compiled with only active nodes (dynamic) or all nodes (static)
6. Each node loads its stage procedure from `stages/*.md` as a prompt template
7. The node invokes the model with `model.with_structured_output(StageSchema)` — Pydantic enforces output shape
8. **Tool scope enforcement** blocks tool calls outside the current stage's permitted scope (v11.1)
9. **Evidence gate** validates output quality; failures trigger automatic retry
10. Declarative `EdgeRule` connections handle routing: advance, retry, reset, or block
11. State (including graph topology) is persisted to `state.json` after each iteration
12. **Iteration counter** tracks total loop progress; bounded by `max_loop_iterations`

### Execution Flow Per Stage

```
Stage Node Entry
    │
    ├── Already done? → Skip to next node
    │
    ├── Max attempts reached? → Block or force advance
    │
    ├── Load stage procedure + skill
    │
    ├── Invoke model.with_structured_output(Schema)
    │       │
    │       ├── Success → Pydantic-validated dict
    │       └── Error → Retry (if attempts < max)
    │
    ├── Evidence Gate: validate output quality
    │       │
    │       ├── Pass → Mark done, advance
    │       └── Fail → Retry (if attempts < max)
    │
    ├── Write artifacts to disk
    │
    └── Return Command(goto=next_node, update={stages, iteration++})
```

### Markdown Files as Templates

Stage procedures in `stages/*.md` are no longer instructions for the orchestrator. They are **prompt templates** loaded by `templates.py` and injected into each node's model call. The markdown content defines WHAT each stage does; the Python code defines HOW the flow works.

### Model Configuration

The orchestrator works with any OpenAI-compatible endpoint:

```yaml
# config.yaml
model:
  base_url: "http://localhost:8000"
  model: "qwable-v2"
  temperature: 0.0
  max_tokens: 128000

# Per-stage override (optional)
model_overrides:
  impl.code:
    base_url: "http://localhost:8001"
    model: "Jackrong/Qwopus3.6-27B-v2-GGUF"
    max_tokens: 200000
```

### CLI Reference

```
eng-loop --work-item "description"   Run the loop (static graph)
  --dynamic-graph                     Use dynamic graph construction (v11)
  --parallel-qa                       Run QA stages in parallel (requires --dynamic-graph)
  --opencode-agent                    Hybrid mode: Python controls graph, OpenCode executes stages (requires --dynamic-graph)
  --build-topology                    Build graph topology and output as markdown (for LLM mode)
  --check-compliance                  Validate stage transition against topology (for LLM mode)
  --requested-stage                   Stage ID to validate (required with --check-compliance)
  --pause-at STAGE [STAGE ...]        Pause execution before specified stages (v11.2)
  --interactive                       Enable full-screen TUI dashboard (experimental, v11.2)
  -f, --framework-root                Framework root (default: .)
  -l, --loop-root                     Loop root (default: .)
  -p, --project-root                  Project root (default: .)
  -s, --state-file                    State file for resume
  --model-base-url                    Override model base URL
  --model-name                        Override model name
  --check-model                       Check model connectivity and exit
  --dry-run                           Validate config and exit

Surgical Commands (v11.2):
  rollback <stage_id>                 Restore state to before a stage (time travel)
  run-node <stage_id>                 Execute a single node in isolation (single-step replay)
    --from-state <file>               State file to load (default: state.json)
  clear-state <stage_id>              Reset a stage's attempts and done status
    --reset-attempts                  Reset attempt counter to 0
  skip-node <stage_id>                Force-mark a stage as done
  history                             List state snapshots
```

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
│  │ 26 stages,    │  │ Monitor per- │  │  Token budgets,       │ │
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
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  GRAPH BUILDER (v11)                      │  │
│  │  NodeRegistry → Active nodes for this work item           │  │
│  │  EdgeRules → Declarative connections                      │  │
│  │  StateGraph → Compiled (only active nodes)                │  │
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

The orchestrator is a LangGraph `StateGraph` built dynamically per work item. v10 used 28 fixed nodes; v11 instantiates only the nodes needed for the task. It maintains typed state with reducers and iterates through stages until all converge. It does **not** advance sequentially — conditional edges re-evaluate every stage each iteration.

### LangGraph Flow

```
[GraphBuilder: classify complexity, filter active nodes, resolve edges]
    │
    ▼
START → init → [essence gate] → init-ideate → init-bdd → init-refine
    → [conditional: complexity] →
    ┌─ small: impl-design
    ┌─ medium+: arch-requirements → arch-solution
    ┌─ large+: design-user-research → ... → design-visual-design
    ┌─ complex: arch-review

    → impl-design → impl-code → doc-update → verify
    → [conditional: PASS/FAIL]
        PASS → e2e-execute → qa-security → qa-api-contract → qa-performance
        FAIL → impl-code (retry, bounded by max attempts)

    → deploy-prepare → smoke-test → doc-decisions → doc-project → post → END

Note: In dynamic mode (v11), only active nodes appear in the compiled graph.
Deactivated stages (below complexity threshold) are skipped entirely.
```

Each retry loop is bounded by per-stage attempt limits in `config.yaml`. When exceeded, a conditional edge routes to `__end__` with `status: blocked`.

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

Complexity and work type determine depth — not a fixed pipeline. The orchestrator classifies each work item before the loop begins using configurable heuristics.

### Complexity Levels

| Level | Files | Tasks | Design | Architecture | QA Stages | Verify | Example |
|-------|-------|-------|--------|-------------|-----------|--------|---------|
| **Small** | ≤ 3 | ≤ 3 | Skip | Skip | Skip | Spec check only | Bug fix, config change |
| **Medium** | ≤ 10 | ≤ 8 | Inline | Requirements + Solution | Security + API contract | Full | Clear feature, moderate scope |
| **Large** | > 10 | > 8 | 6 formal stages | Requirements + Solution + Review | Security + API contract + Performance | Full | Multi-component, new APIs |
| **Complex** | — | — | 6 formal stages + Discuss | Full + Architecture Review | Full + Performance | Full + Lessons | New domain, high ambiguity |

### Work Type Classification (v11.1)

In addition to complexity, the work type determines which phases are active:

| Type | What it does | Stages deactivated |
|------|-------------|-------------------|
| **feature** | New functionality | None (full loop) |
| **bugfix** | Fix existing behavior | Design stages (6 stages) |
| **operational** | Run existing code (tests, deploys) | impl, design, arch, verify |

Classification uses two-tier keyword matching (multi-word phrases + single words) for Portuguese and English. Example: `"Execute todos os testes E2E"` → `operational` → 7 stages instead of 11.

### Heuristics

The auto-sizing algorithm evaluates:
- Number of files affected (from blueprint estimate)
- Number of tasks (from blueprint estimate)
- Presence of new domains
- External integrations required
- Work item ambiguity level
- Acceptance criteria count
- Work type keywords (v11.1)

A stage with `min_complexity` above the work item level is **deactivated** (marked `done: true` by default, skipped by the loop). Deactivated stages cannot be reactivated mid-loop, and the user cannot override auto-sizing — the heuristics are deterministic.

In v11.1, auto-sizing is handled by the `GraphBuilder` — complexity and work type are classified by Python before graph construction, and only nodes meeting both criteria are instantiated.

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

### Graphify Tools (Passive Mode, v11.3)

The graphify tools remain available but operate in **passive mode**: the prompt no longer issues imperative commands like "USE GRAPHIFY FIRST." Instead, the tools are described as optional deep-dive resources for questions the PROJECT MAP doesn't answer. When the Preload feature (future) injects pre-computed graph context, the LLM naturally stops calling the tools because the information is already in the prompt.

---

## Context Optimization (v11.3)

The framework transitions from **"trust the LLM to follow exploration instructions"** to **"Python pre-computes context, LLM receives it as fact."** This is the core principle for extracting performance from Small Language Models (SMLs) running locally.

### The Problem

Without context optimization, every stage begins blind:
1. LLM calls `glob("**/*.ts")` to discover structure — **1 tool-call, ~2s**
2. LLM calls `read("src/")` to list directory — **1 tool-call, ~1s**
3. LLM calls `glob("**/test*")` to find tests — **1 tool-call, ~1s**
4. LLM calls `read("package.json")` to check deps — **1 tool-call, ~1s**
5. ...repeats for every stage, every retry

That's 3-8 exploratory tool-calls **per stage** that could be eliminated by pre-computing the information once at init.

Additionally, within a single stage's micro-loop, the LLM frequently re-reads the same files (e.g., `package.json` read 4 times across iterations), wasting tokens and wall-clock time.

### Solution 1: ProjectMap — Pre-computed Structural Overview

At `init`, the Python code scans the project and builds a compact structural map:

```
## PROJECT MAP
### File Structure
```
myproject/
|-- src/
|   |-- api/
|   |   |-- routes.ts
|   |   `-- middleware/
|   |       `-- auth.ts
|   `-- components/
|       `-- Login.tsx
|-- tests/
|   `-- auth.test.ts
`-- package.json
```

### Config Files (2)
- `package.json`
- `tsconfig.json`

### Entry Points (2)
- `src/index.ts`
- `src/main.py`

### Languages
- typescript: 42 files
- python: 8 files

### Module Boundaries (3)
- `src/`
- `tests/`
- `lib/`

### Stats
- total_files: 59
```

**How it works:**
1. `init_node` calls `ProjectMap.build(project_root)` — pure Python, no external dependencies
2. Map serialized to `state.json.project_map`
3. `SystemPrefix.build()` injects `## PROJECT MAP` into **every** stage prompt
4. After `impl.code` creates new files, the map is rebuilt incrementally

**Impact:** Eliminates 3-8 exploratory `glob`/`read` tool-calls per stage. For a 12-stage loop, that's ~48 fewer tool-calls.

### Solution 2: Tool Result Cache — Eliminate Redundant Reads

Within a stage's micro-loop, the `ToolResultCache` caches results of idempotent tools (`read`, `glob`, `grep`) and invalidates on mutations:

```
Iteration 1: read("package.json") → disk I/O → cache miss → store result
Iteration 2: read("package.json") → cache hit → return immediately (no disk I/O)
Iteration 3: edit("src/auth.ts", ...) → invalidate cache for src/auth.ts
Iteration 4: read("src/auth.ts") → disk I/O (fresh) → cache miss → store
Iteration 5: read("package.json") → cache hit → return immediately
```

**Invalidation rules:**
- **`edit` / `write`**: Invalidate only the modified file's cache entries (targeted)
- **`bash`**: Invalidate entire cache (can modify anything)
- **`read` / `glob` / `grep`**: No invalidation (idempotent)

**Impact:** Prevents the LLM from wasting 20-40 seconds re-reading the same files within a single stage.

### Architecture

```
Before (v11.2):                    After (v11.3):
┌─────────────────────┐            ┌──────────────────────────────┐
│ Prompt:              │            │ Prompt:                      │
│ "Use glob to find    │            │ "## PROJECT MAP (pre-built)  │
│  files, then read    │            │  myproject/                  │
│  them."              │            │  |-- src/                    │
│                      │            │  |   |-- main.ts             │
│ LLM: glob → read →   │            │  |-- tests/                  │
│ glob → read → ...    │            │  `-- package.json            │
│ (8 tool-calls)       │            │                              │
└─────────────────────┘            │ LLM: edit → read (cached) →  │
                                   │ write → read (cached) → ...  │
                                   │ (2-3 tool-calls)             │
                                   └──────────────────────────────┘
```

### Future: Graphify Preload (Phase 2)

When `graphify.enabled == true`, the plan is to pre-compute graph context (architecture overview, entity explanations) and inject it into the prompt — same principle as ProjectMap but for semantic relationships. The graphify tools will remain as a fallback for hyper-specific questions.

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

### Compliance (v11.1)

| Key | Default | Purpose |
|-----|---------|---------|
| `compliance.enabled` | `true` | Enable compliance gate between stages |
| `compliance.mode` | `gate` | `gate` = blocking, `advisory` = warning only |
| `compliance.check_before_stage` | `true` | Run `--check-compliance` before each stage |
| `compliance.enforce_tool_scope` | `true` | Block tool calls not permitted for current stage |
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
| `state-template.json` | `{framework-root}/` | Template (git-tracked, 26 stages) |
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
| Verifier | diff + blueprint + ACs + test file paths + **project map** | Full context, other feature specs |
| Security Reviewer | diff + blueprint + architecture + **project map** | Test files |
| API Contract Validator | blueprint + API source + integration tests + **project map** | E2E tests, full diff |
| Performance Checker | blueprint + architecture + build output + **project map** | Test files |

### Context Optimization (v11.3)

Two mechanisms reduce redundant tool-calls and token waste:

1. **ProjectMap** — Pre-computed at `init`, injected into every stage's system prompt. Provides file tree, config files, entry points, module boundaries, test dirs, languages, routes, and components. Eliminates 3-8 exploratory `glob`/`read` calls per stage. Rebuilt incrementally after `impl.code` if new files are created.

2. **ToolResultCache** — In-memory cache for `read`, `glob`, `grep` within each stage's micro-loop. Invalidates on `edit`/`write` (targeted, by file path) and `bash` (full cache). Prevents the LLM from re-reading the same files across iterations. Cache stats (hits/misses) logged at stage completion.

See [Context Optimization](#context-optimization-v113) for details.

---

## Directory Structure

```
.engineering-loop/ (framework repo)
├── ORCHESTRATOR.md              # Main orchestrator instructions
├── CORE.md                      # Framework index: stages, references, skills
├── config-template.yaml         # Framework configuration defaults
├── state-template.json          # Initial state for all 26 stages
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
├── eng_loop/                    # LangGraph orchestrator (Python)
│   ├── pyproject.toml           # Package config (langgraph, langchain-openai, pydantic)
│   ├── src/eng_loop/
│   │   ├── state.py             # PipelineState, 26 stages, reducers
│   │   ├── config.py            # YAML loader, deep merge, paths
│   │   ├── graph.py             # Delegates to GraphBuilder in dynamic mode
│   │   ├── graph_builder.py     # Dynamic graph construction per work item
│   │   ├── node_registry.py     # NodeSpec + registry of 26 stages
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
| v11.6.0 | 2026-08-16 | **Graph integrity + evidence-based status**: Honest task outcome (`compute_task_outcome()`) — DONE/FAILED/PARTIAL/WARNINGS. Post stage propagates failure instead of forcing DONE. Artifact evidence tracking (existência verificada vs declarada). Topology fidelity (proposed vs compiled). Result rendering evidencia-based (stages ativos, artefatos, falhas). Tool aliases (snake_case + camelCase). LangGraph warning suppression. 117 integration tests (1603 total) |
| v11.6.1 | 2026-08-16 | **Graph integrity + evidence-based status**: Honest task outcome (`compute_task_outcome()`) — DONE/FAILED/PARTIAL/WARNINGS. Post stage propagates failure instead of forcing DONE. Artifact evidence tracking (existência verificada vs declarada). Topology fidelity (proposed vs compiled). Result rendering evidencia-based (stages ativos, artefatos, falhas). Tool aliases (snake_case + camelCase). LangGraph warning suppression. 117 integration tests (1603 total) |
| v11.3.0 | 2026-08-13 | **Context optimization**: `ProjectMap` pre-computed at init eliminates 3-8 exploratory glob/read per stage (ASCII tree, configs, entry points, modules, languages, routes, components). `ToolResultCache` in micro-loop eliminates redundant read/glob/grep calls with targeted invalidation on edit/write (full invalidation on bash). Graphify prompt softened from imperative to passive. `project_map.py` (370 lines), `ToolResultCache` in `agent_runner.py`, 29 new tests |
| v11.4.0 | 2026-08-14 | **Contract gate middleware + causal rollback**: `contract_gate.py` validates handoff contracts between stages (blueprint→code, code→verify); retries source or blocks pipeline. `qa_parallel.py` fan-out/fan-in with `qa-dispatcher` + `qa-join` for parallel QA. `rollback_to_stage` reducer resets causal chain (impl.code → verify) on verifier/QA failure. `impl.code` FIX MODE with structured `fix_tasks`. Deterministic `init-setup` node separates classification from LLM. State reducers: `_merge_dict`, `_overwrite` (clear fields), `rollback_to_stage`. Edge rules: conditional blueprint validation, blocked-aware routing. Dry-run simulator: 4 scenarios (HAPPY_PATH, CONTRACT_VIOLATION, VERIFY_ROLLBACK, QA_FANOUT_FAIL) — all assertions green |
| v11.5.0 | 2026-08-15 | **Dynamic Node Orchestration (V1.3)**: Meta-orchestration layer for runtime sub-task generation beyond the 26-stage pipeline. `dynamic-architect` node (LLM proposes `DynamicBlueprintProposal` → framework authorizes via `authorize_blueprint()` → immutable `DynamicBlueprint`). `meta-executor` node (sequential cursor-based execution, strict attempt counting, typed validation). 9 new Pydantic schemas (frozen payloads, discriminated union rules, audit entries). Policy resolver: risk keyword analysis, tool sandboxing (safe pool). Validation engine: `tests_pass` (subprocess), `files_exist` (path check), `contains_symbol` (regex). Governance: `MAX_DYNAMIC_STEPS=5`, `max_attempts` per step (1-5), `authorized_complexity` override. Topology: `__start__ → init-setup → dynamic-architect → [meta-executor loop] → init`. 54 tests, 29 total nodes |
| v12.1.0 | 2026-08-17 | **Skills v2.0 — Comprehensive improvement across 14 skills**: persona-simulator (structured profiles, SEQ/SUS scoring from Avenir-UX), verifier (equivalent mutant filtering, mutation feedback loop from agentpatterns.ai/MUTGEN), ux-auditor (WCAG 2.2, Nielsen heuristics, SEQ/SUS), bmad-bdd-mapper (Scenario Outline, hooks, tag strategy), tester-unit (two-step prompting, boundary value analysis, mutation score), linter-agent (security analysis, maintainability index, false positive handling), cloud-architect (multi-cloud, DR/BCP, compliance mapping), requirements-refiner (INVEST/SMART scoring, risk matrix, conflict detection), solution-designer (ADR format, STRIDE threat modeling, API design principles), implementation-architect (testing strategy, CI/CD pipeline, rollback plan), bmad-ideation (Hourglass Framework, idea evaluation matrix, convergence techniques), e2e-playwright (visual regression, trace viewer, Playwright MCP), graphify (data flow tracing, dead code detection, incremental updates) |

---

## Files at a Glance

| File | Role |
|------|------|
| `eng_loop/` | LangGraph orchestrator — run `eng-loop -w "..."` to start |
| `eng_loop/src/eng_loop/node_registry.py` | 26 NodeSpec registrations |
| `eng_loop/src/eng_loop/edge_rules.py` | Declarative edge rules |
| `eng_loop/src/eng_loop/graph_builder.py` | Dynamic graph construction |
| `eng_loop/src/eng_loop/schemas.py` | 27 Pydantic schemas for structured output |
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
| `state-template.json` | State template — 26 stages with done/attempts/essence_checked |
| `AGENTS.md` | Agent instructions — framework editing guidelines |
| `README.md` | This file — comprehensive documentation |
| `artifacts/graph-topology.md` | Generated execution plan (LLM mode) |
