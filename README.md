---
name: engineering-loop-readme
type: entry-point
description: 'Comprehensive framework documentation.'
---

# Engineering Loop v12.5.0

**New user? Start with [Installation](#installation) — get up and running in 7 steps.**

**Fail Fast (FF)** — orchestrator pattern for parallel swarm-based software development. Fragment any work item into atomic blocks, dispatch parallel tasks via Swarm, validate at each gate, recover isolated failures.

| | |
|---|---|
| **Version** | 12.5.0 |
| **Development Mode** | FF (Fail Fast) — parallel swarm, judge-approved plans |
| **Skills** | 22 built-in ideação/verificação skills + global skills |
| **References** | 15 shared reference documents (anti-patterns, exit-conditions, lessons, ff-protocol) |
| **Architecture** | Multi-project via git submodule |
| **Anti-Drift** | manifest.md, role assertion, context budget, state file anchor |

---

## Table of Contents

- [Installation](#installation)
- [Overview](#overview)
- [FF Protocol](#ff-protocol)
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

## Installation

Install the framework in any project as a git submodule. The framework is self-contained — it brings skills, references, and the FF protocol. Your project only needs `AGENTS.md`, `.ff/` and global skills synced.

### Quick Install (New Project)

```bash
# 1. Clone your project (or use existing repo)
cd your-project

# 2. Add framework as submodule
git submodule add <engineering-loop-repo-url> .eng

# 3. Initialize FF workspace
mkdir .ff
echo '[]' > .ff/lessons.json

# 4. Copy AGENTS.md template (replace [Project Name])
cp .eng/template-project/AGENTS.md AGENTS.md
sed -i 's/\[Project Name\]/Your Project Name/g' AGENTS.md

# 5. Sync global skills to your machine
python .eng/scripts/sync-global-skills.py pull

# 6. Add to .gitignore
cat >> .gitignore << 'EOF'

# FF workspace (project state)
.ff/

# Project artifacts
artifacts/
EOF

# 7. Commit
git add .eng AGENTS.md .gitignore
git commit -m "Add Engineering Loop framework with FF protocol"
```

### Migrate Existing Project

If your project already uses an older version of the framework:

```bash
# 1. Update submodule to latest
git submodule update --remote

# 2. Re-sync global skills (new skills may have been added)
python .eng/scripts/sync-global-skills.py pull

# 3. Update AGENTS.md if needed
# Copy from template and merge your project-specific sections:
cp .eng/template-project/AGENTS.md AGENTS.md.new
# Merge manually, keeping your project-specific additions

# 4. Update .ff/state.json schema if needed
# The new 'summary' field is optional — the protocol will create it on first use
```

### Verify Installation

```bash
# Submodule is active
git submodule status
# Should show .eng with a commit hash

# FF skill is available
ls ~/.agents/skills/ff/SKILL.md
# Should exist

# Anti-drift manifest is present
ls .eng/global-skills/ff/manifest.md
# Should exist

# Skills sync works
python .eng/scripts/sync-global-skills.py status
# Should show synced skills
```

### Daily Usage

Once installed, the framework is hands-off:

| Action | Command |
|--------|---------|
| Start working | Describe your task to the AI agent — FF activates automatically |
| Update framework | `git submodule update --remote && python .eng/scripts/sync-global-skills.py pull` |
| Check skill status | `python .eng/scripts/sync-global-skills.py status` |
| View lessons | `cat .ff/lessons.json` |
| View session state | `cat .ff/state.json` |
| Add new global skill | `python .eng/scripts/sync-global-skills.py push [name]` |

### What Gets Installed

```
your-project/
├── .eng/                    # Framework (git submodule)
│   ├── global-skills/       # Skills → deployed to ~/.agents/skills/
│   ├── skills/              # Framework-specific skills (read-only)
│   ├── references/          # Anti-patterns, lessons, protocol docs
│   ├── scripts/             # sync-global-skills.py
│   ├── template-project/    # AGENTS.md template, migration guide
│   ├── AGENTS.md            # Framework instructions
│   └── skill-index.md       # Skill registry + improvement log
│
├── AGENTS.md                # Your project's instructions (from template)
├── .ff/                     # FF workspace (gitignored)
│   ├── state.json           # Session state — your anchor
│   └── lessons.json         # Accumulated lessons (append-only)
└── artifacts/               # Project artifacts (gitignored)
```

### Uninstall

```bash
git rm .eng
git commit -m "Remove Engineering Loop framework"
rm -rf .ff/
# Remove framework entries from AGENTS.md and .gitignore
```

---

## Overview

Engineering Loop is a framework for orchestrating AI sub-agents through the complete software development lifecycle. Instead of a linear pipeline, it operates as a **persistent while-loop** that re-evaluates every stage on each iteration, allowing downstream findings to trigger upstream rework automatically.

Development is orchestrated through the **FF (Fail Fast) protocol** — a parallel swarm-based approach where work items are fragmented into atomic blocks, dispatched to sub-agents in parallel, validated at each gate, and failures recovered in isolation. See [FF Protocol](#ff-protocol) for details.

### Core Principles

- **Parallel swarm execution** — work items fragmented into atomic blocks dispatched to sub-agents in parallel
- **Judge-approved plans** — two sub-agents cross-analyze, main agent consolidates, judge validates before execution
- **Fail fast** — each block validated in isolation; failures don't contaminate siblings
- **Context slicing** — each sub-agent receives only its relevant context; full artifacts are never passed to one agent
- **Essence before execution** — inputs validated through Four Lenses; Lens 4 scope tensions ask for clarification before blocking
- **Auto-sizing** — autonomy score determines execution mode (full auto / semi auto / manual)
- **Independent verification** — author ≠ verifier; discrimination sensor confirms test quality
- **Multi-project isolation** — each project has its own config, state, and artifacts
- **Shared lessons** — confirmed lessons propagate across all projects via the framework
- **Continuous decisions** — every architectural decision recorded as `AD-NNN` immediately, not deferred
- **Local model support** — works with any OpenAI-compatible endpoint (llama.cpp, vLLM, Ollama)

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

## The Engine (eng_loop/) — TRIMMED

The loop motor (LangGraph, Python orchestrator, 34 stages) has been removed in v12.4.0. FF protocol replaces the stage-based loop entirely. Consumer projects that install this repo as a git submodule must migrate to FF protocol.

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

### Config

`config-template.yaml` was removed in FF transition. Consumer projects generate `config.yaml` from `template-project/config.yaml`.

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
| `state-template.json` | `{framework-root}/` | Template (git-tracked, retained for reference) |
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
├── state-template.json          # Initial state template (retained for reference)
├── skill-index.md               # Skill registry with improvement log
├── skill-governance.md          # Skill governance guidelines
├── global-skills-registry.json  # Global skills registry
├── README.md                    # This file
├── .gitignore                   # Project file exclusions
├── AGENTS.md                    # Agent-specific instructions
│
├── .ff/                         # FF workspace (gitignored)
│   ├── state.json               # Current FF session state
│   ├── lessons.json             # Accumulated lessons (append-only)
│   └── README.md                # FF documentation
│
├── .eng/                        # Consumer project state (gitignored)
│   ├── state.json               # Runtime state
│   ├── artifacts/               # Runtime artifacts
│   └── history/                 # State snapshots
│
├── references/                  # Shared references (read-only, 14 files)
│   ├── anti-patterns.md
│   ├── bmad-ideation-patterns.md
│   ├── decision-log.md
│   ├── decision-template.md
│   ├── essence-sidecar.md
│   ├── exit-conditions.md
│   ├── graphify.md
│   ├── hardware-management.md
│   ├── lessons.md
│   ├── lessons-shared.json
│   ├── logging.md
│   ├── skill-discovery-guide.md
│   ├── skill-templates.md
│   ├── sub-agent-contract.md
│   └── ui-testing-patterns.md
│
├── skills/                      # Specialized skills (read-only, 22 skills)
│   ├── bmad-bdd-mapper/
│   ├── bmad-ideation/
│   ├── bmad-integration/
│   ├── e2e-playwright/
│   ├── essence/
│   ├── graphify/
│   ├── implementation-architect/
│   ├── requirements-refiner/
│   ├── solution-designer/
│   └── verifier/
│
├── global-skills/               # Global skills versioned for ~/.agents/skills/
│   ├── caveman/
│   ├── xlsx/
│   └── deepagents-typescript-quickstart/
│
├── scripts/                     # Framework scripts
│   └── sync-global-skills.py    # Global skills sync utility
│
├── artifacts/                   # Trace files (gitignored)
│   ├── trace-*.jsonl            # Historical execution traces
│   └── validation.md
│
└── template-project/            # Consumer project template
    ├── AGENTS.md
    ├── config.yaml
    ├── state.json
    ├── .ff/
    └── migration-guide.md
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

**Resolution:** Consumer projects generate `config.yaml` from `template-project/config.yaml`.

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

**Symptom:** Model API calls fail with connection error

**Resolution:**
- Ensure your local model server is running at the configured `base_url`
- Check the model name matches what your server expects
- Verify `.opencode/opencode.json` has correct provider config

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
| `AGENTS.md` | Agent instructions — framework editing guidelines |
| `README.md` | This file — comprehensive documentation |
| `skill-index.md` | Skill registry — ID → skill mapping with improvement log |
| `skill-governance.md` | Skill governance guidelines |
| `global-skills-registry.json` | Global skills registry |
| `state-template.json` | State template (retained for reference) |
| `scripts/sync-global-skills.py` | Global skills sync utility |
| `references/` | 14 shared reference documents |
| `skills/` | 22 built-in skills |
| `global-skills/` | Global skills versioned for `~/.agents/skills/` |
| `template-project/` | Consumer project template (AGENTS.md, config, .ff/) |
| `.ff/` | FF workspace (state.json, lessons.json) |
| `artifacts/` | Trace JSONL files |
