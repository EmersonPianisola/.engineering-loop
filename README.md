---
name: engineering-loop-readme
type: entry-point
description: 'Comprehensive framework documentation.'
---

# Engineering Loop v13.0.0

**New user? Start with [Installation](#installation) — get up and running in 7 steps.**

**Fail Fast (FF)** — hybrid AI development protocol: Claude plans and validates, a local model executes. Fragment any work item into atomic blocks, hand them off as executor-grade work orders, validate every block twice, recover isolated failures.

| | |
|---|---|
| **Version** | 13.0.0 |
| **Development Mode** | FF (Fail Fast) — hybrid: Claude planner + local executor, acceptance-gated judge-approved plans |
| **Skills** | 23 built-in ideação/verificação skills + global skills |
| **References** | 16 shared reference documents (anti-patterns, exit-conditions, lessons, ff-protocol) |
| **Architecture** | Multi-project via git submodule |
| **Anti-Drift** | manifest.md, role assertion, context budget, state file anchor |

---

## Table of Contents

- [Installation](#installation)
- [Overview](#overview)
- [FF Protocol](#ff-protocol)
- [Essence Sidecar](#essence-sidecar)
- [Directory Structure](#directory-structure)
- [Anti-Patterns](#anti-patterns)
- [Troubleshooting](#troubleshooting)
- [Version History](#version-history)
- [Files at a Glance](#files-at-a-glance)

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

# OpenCode local config (the /ff command stays tracked)
.opencode/*
!.opencode/commands/
EOF

# 7. Copy the /ff command definition from the framework
mkdir -p .opencode/commands
cp .eng/.opencode/commands/ff.md .opencode/commands/ff.md

# 8. Commit
git add .eng AGENTS.md .gitignore .opencode/commands
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
│   ├── scripts/             # Framework scripts (skills sync, propagation)
│   ├── template-project/    # AGENTS.md template, migration guide
│   ├── .opencode/commands/  # /ff command definition (copied into your project)
│   ├── AGENTS.md            # Framework instructions
│   ├── FF-CHANGELOG.md      # FF protocol changelog
│   ├── skill-index.md       # Skill registry + improvement log
│   ├── skill-governance.md  # Skill governance guidelines
│   ├── global-skills-registry.json  # Global skills registry
│   └── state-template.json  # State template (reference)
│
├── AGENTS.md                # Your project's instructions (from template)
├── .opencode/commands/      # /ff command definition (copied from the framework)
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

Development is orchestrated through the **FF (Fail Fast) protocol** — a hybrid approach where Claude (the planner) clarifies, plans and validates, and a local model (the executor) executes atomic blocks handed off through `.ff/`; every block is validated twice and failures are recovered in isolation. See [FF Protocol](#ff-protocol) for details.

### Core Principles

- **Hybrid execution** — Claude plans and validates; a local model executes atomic blocks from executor-grade work orders
- **Acceptance-gated plans** — two in-session analysis passes cross-check, Gherkin acceptance + executable checks are written per block, the judge validates everything before handoff
- **Fail fast** — each block validated in isolation; failures don't contaminate siblings
- **Double validation** — the executor proposes a validation; the planner re-runs every check and reviews the full diff before approving
- **Essence before execution** — inputs validated through Four Lenses; Lens 4 scope tensions ask for clarification before blocking
- **Auto-sizing** — autonomy score determines execution mode (full auto / semi auto / manual)
- **Independent verification** — author ≠ verifier; discrimination sensor confirms test quality
- **Multi-project isolation** — each project has its own config, state, and artifacts
- **Shared lessons** — confirmed lessons propagate across all projects via the framework
- **Continuous decisions** — every architectural decision recorded as `AD-NNN` immediately, not deferred
- **Local model support** — works with any OpenAI-compatible endpoint (llama.cpp, vLLM, Ollama)

---

## FF Protocol

FF is the **default development mode** for this project. It is hybrid: Claude plans and validates; a local model executes.

### Protocol Overview

```
USER INTENT
    ↓
PHASE 0: CLARIFY    → Essence check, gather unknowns, scope the task
PHASE 1: PLAN       → (planner) in-session analysis passes → plan → work orders → acceptance (Gherkin) + checks → judge approve → handoff
PHASE 2: EXECUTE    → (executor) /ff exec: work order → checks → commit → execution trace + validation proposal
PHASE 3: VALIDATE   → (planner) critical review: re-run checks, scope + diff review, final gate
PHASE 4: LESSONS    → Capture lessons, report results
```

### Plan Build

The plan is built **by the planner (Claude), in-session**, in two separate analysis passes:

1. **Structural pass** — maps files, imports, dependencies, risk
2. **Adversarial pass** — re-examines the structural findings: alternative approaches, edge cases, hidden dependencies

The planner consolidates both passes into the plan, fragments it into blocks, and writes for every block an **executor-grade work order** (exact files, exact edits), a Gherkin acceptance feature (Given/When/Then, end-user perspective) and an executable **check** script. A **judge sub-agent** — the protocol's only sub-agent, dispatched with a clean view — validates plan, work orders, acceptance and checks together. Only after approval is the session handed off to the executor.

### Execute

The local model runs `/ff exec` in opencode. Blocks run in order: apply the work order, run the block's checks (one retry), commit locally, and write an execution trace with a **validation proposal**. Then the planner runs a **critical second validation** — it re-runs every check itself, verifies the scope from the commit, reads the full diff, and approves the block or sends it back for rework (max 2 rounds).

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
├── FF-CHANGELOG.md              # FF protocol changelog
│
├── .ff/                         # FF workspace (gitignored)
│   ├── state.json               # Current FF session state
│   ├── lessons.json             # Accumulated lessons (append-only)
│   └── README.md                # FF documentation
│
├── .eng/                        # Local leftover dir in this repo (gitignored)
│
├── references/                  # Shared references (read-only, 16 files)
│   ├── anti-patterns.md
│   ├── bmad-ideation-patterns.md
│   ├── decision-log.md
│   ├── decision-template.md
│   ├── essence-sidecar.md
│   ├── exit-conditions.md
│   ├── ff-protocol.md
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
├── skills/                      # Specialized skills (read-only, 23 skills)
│   ├── architecture-reviewer/
│   ├── bmad-bdd-mapper/
│   ├── bmad-design-system/
│   ├── bmad-ideation/
│   ├── bmad-info-arch/
│   ├── bmad-integration/
│   ├── bmad-interaction/
│   ├── bmad-personas/
│   ├── bmad-user-research/
│   ├── bmad-visual-design/
│   ├── e2e-playwright/
│   ├── essence/
│   ├── graphify/
│   ├── implementation-architect/
│   ├── integration-tester/
│   ├── linter-agent/
│   ├── persona-simulator/
│   ├── requirements-refiner/
│   ├── solution-designer/
│   ├── story-flow/
│   ├── tester-unit/
│   ├── ux-auditor/
│   └── verifier/
│
├── global-skills/               # Global skills versioned for ~/.agents/skills/
│   ├── caveman/
│   ├── xlsx/
│   └── deepagents-typescript-quickstart/
│
├── scripts/                     # Framework scripts
│   ├── sync-global-skills.py    # Global skills sync utility
│   └── propagate-to-projects.py # Update framework + skills in consumer projects
│
├── artifacts/                   # Trace files (gitignored)
│   ├── trace-*.jsonl            # Historical execution traces
│   └── validation.md
│
└── template-project/            # Consumer project template
    ├── AGENTS.md                # AGENTS.md template for new projects
    ├── README.md                # Consumer README template
    ├── example-work-item.md     # Sample work item
    ├── migration-guide.md       # Migration walkthrough
    ├── .gitignore               # Consumer .gitignore template
    └── .gitmodules              # Submodule config (framework repo URL)
```

---

## Anti-Patterns

The full anti-pattern catalog lives in [`references/anti-patterns.md`](references/anti-patterns.md) — orchestrator drift, FF protocol rules, and sub-agent contract violations.

The protocol-specific don'ts are listed in the [FF Protocol](#ff-protocol) section above.

---

## Troubleshooting

### Submodule Not Updating

**Symptom:** Framework skills or references are outdated

**Resolution:**
- `git submodule update --remote`
- Re-sync global skills: `python .eng/scripts/sync-global-skills.py pull`

### E2E Tests Failing on Locators

**Symptom:** Playwright tests fail with "element not found"

**Resolution:**
- Use `getByRole`, `getByLabel`, `getByText` — never fragile CSS/XPath selectors
- Check that ARIA labels and roles are present in the DOM

### Model Connectivity Failed

**Symptom:** Model API calls fail with a connection error

**Resolution:**
- Ensure your local model server is running at the configured `base_url`
- Check the model name matches what your server expects
- Verify `.opencode/opencode.json` has correct provider config

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
| v11.6.0 | 2026-08-15 | **Dynamic Graph Topology Proposal**: LLM architect proposes optimal graph per task, authorized by 5-layer policy firewall, compiled by deterministic builder. Invariant: LLM proposes → Policy authorizes → Builder compiles → Runtime executes. 5 new schemas: GraphTopologyProposal, EdgeDefinition, PhaseGroup, ExecutionPolicy, AuthorizedGraphTopology. Dual-path compilation (proposal or deterministic fallback). 34 new tests, 1484 total tests pass |
| v11.6.1 | 2026-08-16 | **Graph integrity + evidence-based status**: Honest task outcome (`compute_task_outcome()`) — DONE/FAILED/PARTIAL/WARNINGS. Post stage propagates failure instead of forcing DONE. Artifact evidence tracking (existência verificada vs declarada). Topology fidelity (proposed vs compiled). Result rendering evidencia-based (stages ativos, artefatos, falhas). Tool aliases (snake_case + camelCase). LangGraph warning suppression. 117 integration tests (1603 total) |
| v12.1.0 | 2026-08-17 | **Skills v2.0 — Comprehensive improvement across 13 skills**: persona-simulator (structured profiles, SEQ/SUS scoring from Avenir-UX), verifier (equivalent mutant filtering, mutation feedback loop from agentpatterns.ai/MUTGEN), ux-auditor (WCAG 2.2, Nielsen heuristics, SEQ/SUS), bmad-bdd-mapper (Scenario Outline, hooks, tag strategy), tester-unit (two-step prompting, boundary value analysis, mutation score), linter-agent (security analysis, maintainability index, false positive handling), requirements-refiner (INVEST/SMART scoring, risk matrix, conflict detection), solution-designer (ADR format, STRIDE threat modeling, API design principles), implementation-architect (testing strategy, CI/CD pipeline, rollback plan), bmad-ideation (Hourglass Framework, idea evaluation matrix, convergence techniques), e2e-playwright (visual regression, trace viewer, Playwright MCP), graphify (data flow tracing, dead code detection, incremental updates) |
| v12.2.1 | 2026-08-20 | **Essence Lens 4 clarification + wall-clock visibility**: Lens 4 scope/complexity tensions now ask user for clarification (narrow/accept/redefine) instead of terminal block; only blocks if `max_clarification_attempts` exhausted. Global wall-clock timer (`start_global_wall_clock()`) set once at CLI entry, persists across all recovery attempts. All progress displays (spinner, progress bar, recovery panel, heartbeat, dashboard) show real-time wall-clock elapsed time. 138 tests passing |
| v12.3.0 | 2026-08-21 | **Graph engineering anti-patterns**: 8 new rules (over-spawning, shared state, knowledge vs agent graph). Lessons L-003 to L-006. Sub-agent contract node types. Hardware-management token budget. Policy-firewall cost-budget layer. Essence reflection types. Provenance viral-claim check |
| v12.4.0 | 2026-08-30 | **FF Protocol — Fail Fast**: Parallel swarm-based development. Two sub-agents cross-analyze, judge approves, swarm executes. No waves. No graphs. Just blocks. FF is the default development mode. Removed motor from consumer projects (`.eng/` is trimmed). |
| v12.5.0 | 2026-09-10 | **FF anti-drift protocol + installation guide**: manifest.md phase checkpoint checklist, reinjection at phase transitions, role assertion, context budget rule, state-file anchor, drift symptoms table; Installation/Quick Install + Verify Installation docs |
| v12.6.0 | 2026-09-19 | **Community-ready**: /ff command shipped tracked, full session tracing, propagation script; docs consistency pass — motor-era sections removed, versions + counts aligned across all docs, consumer template fixed; stale motor artifacts untracked; milestone tag |
| v12.7.0 | 2026-10-07 | **Acceptance layer + Context Handoff**: Acceptance Architect sub-agent writes Gherkin acceptance criteria (Given/When/Then, end-user perspective) + test instructions per block BEFORE the judge — spec-only, never executes. Judge validates plan AND acceptance (unit-level acceptance is a rejection). Acceptance tests gate every block and the final validation. Context Package mandatory in every sub-agent dispatch (file excerpts, contracts, skill digests, lessons) — no more thin handoffs |
| v13.0.0 | 2026-10-09 | **Hybrid FF — Claude planner + local executor**: roles split through a file-based handoff in `.ff/` (`owner`/`status` in state.json, work orders, executable checks, execution traces, reviews). The planner (Claude) runs Clarify, Plan (two in-session analysis passes, judge = only sub-agent), a critical Review & Validate and Lessons; the executor (local model, `/ff exec` in opencode) applies work orders, runs checks, commits per block and proposes a validation. New `ff-exec` skill; `/ff` command is executor-only; propagate refreshes stale `/ff` commands; `references/ff-protocol.md` is now a short reference |

---

## Files at a Glance

| File | Role |
|------|------|
| `AGENTS.md` | Agent instructions — framework editing guidelines |
| `README.md` | This file — comprehensive documentation |
| `FF-CHANGELOG.md` | FF protocol changelog |
| `skill-index.md` | Skill registry — ID → skill mapping with improvement log |
| `skill-governance.md` | Skill governance guidelines |
| `global-skills-registry.json` | Global skills registry |
| `state-template.json` | State template (retained for reference) |
| `scripts/sync-global-skills.py` | Global skills sync utility |
| `references/` | 16 shared reference documents |
| `skills/` | 23 built-in skills |
| `global-skills/` | Global skills versioned for `~/.agents/skills/` |
| `template-project/` | Consumer project template (AGENTS.md, README, migration guide, .gitignore, .gitmodules) |
| `.ff/` | FF workspace (state.json, lessons.json) |
| `artifacts/` | Trace JSONL files |
