# AGENTS.md — Engineering Loop v12 Framework Repo

## What This Repo Is

Framework for an AI-assisted development loop engine. Consumer projects install it as a git submodule at `.eng/`. Contains framework code only: stages, skills, references, templates, install scripts, and the `eng_loop/` Python package.

## Two Kinds of Files — Don't Confuse Them

| Read-only (git-tracked) | Project-specific (gitignored) |
|---|---|
| `config-template.yaml` | `config.yaml` |
| `state-template.json` | `state.json` |
| `stages/`, `skills/`, `references/` | `artifacts/` |
| `ORCHESTRATOR.md`, `CORE.md`, `START.md` | `STATE.md`, `context.md` |
| `eng_loop/` (Python package) | — |

If you're about to edit a file that should be project-specific, you're in the wrong place.

## Python Package: `eng_loop/`

The orchestrator is a real Python package. Install (editable) and run commands from the `eng_loop/` directory:

```bash
pip install -e "eng_loop/[dev]"
ruff check eng_loop/src eng_loop/tests
ruff format eng_loop/src eng_loop/tests
pytest eng_loop/tests
pytest eng_loop/tests/test_config.py -v -k "test_merge"
```

CLI entry point: `eng-loop` (defined in `pyproject.toml` → `[project.scripts]`). After editable install, available on PATH.

ruff config: `target-version = "py310"`, `line-length = 120` (in `eng_loop/pyproject.toml`).

Package versions: `pyproject.toml` and `__init__.py` must stay in sync (currently `12.4.0`). Use `pyproject.toml` as source of truth for releases.

### Source Layout

```
eng_loop/src/eng_loop/
├── cli.py              # Entry point (eng-loop command, pre-build architect)
├── graph_builder.py    # Dual-path builder (proposal or deterministic)
├── node_registry.py    # 20 registered NodeSpec stages
├── edge_rules.py       # Declarative edge rules + proposal compiler
├── state.py            # PipelineState schema + reducers + node catalog
├── schemas.py          # 52 Pydantic schemas (topology + stage output)
├── config.py           # YAML loader, deep merge
├── graph.py            # Delegates to GraphBuilder in dynamic mode
├── routing.py          # Conditional edge functions (retry, block, advance)
├── model.py            # Model factory (OpenAI-compatible endpoints)
├── templates.py        # Markdown → prompt loader
├── context_bus.py      # Cross-cutting context bus (new in v12)
├── nodes/              # 14 modules, one per stage group
│   ├── dynamic_architect.py  # Pre-build topology + runtime augmentation
│   ├── meta_executor.py      # Sequential cursor-based executor
│   └── (12 more: init, design, architecture, implementation, qa, etc.)
└── tools/              # 55 tool modules
    └── policy_resolver.py    # 5-layer topology firewall + tool sandboxing
```

Tests: 76 files. Run `pytest eng_loop/tests` for full suite.

## Stage Files (`stages/`)

31 markdown files, one per stage. Naming: stage ID with dots replaced by hyphens (e.g., `impl.code` → `impl-code.md`). These are **prompt templates** loaded at runtime by `templates.py`, not instructions for the orchestrator.

## Skills (`skills/`)

22 built-in skills, each in `skills/{name}/SKILL.md`. The authoritative registry is `skill-index.md` — update it whenever you add, rename, or remove a skill.

## Skill Usage — MANDATORY (Global Skills)

Global skills live in `~/.agents/skills` (user-level, outside this repo). Load the applicable skill with the `skill` tool **before** editing the related code. When in doubt, load `ecosystem-primer` first.

| Working on | Load skill first |
|---|---|
| Any LangChain/LangGraph ecosystem change | `ecosystem-primer` (always first) |
| `graph.py`, `graph_builder.py`, `edge_rules.py`, `state.py`, `routing.py`, `nodes/*.py` (StateGraph, Command, Send, reducers) | `langgraph-fundamentals` |
| Interrupts/breakpoints (`cli.py` `_stream_with_interrupts`, `essence_gate.py`, `Command(resume=...)`) | `langgraph-human-in-the-loop` |
| Checkpointer/state history/time travel (`graph.py`, `graph_builder.py`, `state_history` config) | `langgraph-persistence` |
| `agent_runner.py`, `agent_tools.py`, `*_tool.py` (tool-calling loop, StructuredTool) | `langchain-fundamentals` |
| Approval/middleware in the agent loop | `langchain-middleware` |
| `pyproject.toml` dependencies / `model.py` | `langchain-dependencies` |
| (Future) Deep Agents migration | `deep-agents-core` (+ `deep-agents-memory` / `deep-agents-orchestration`) |

Other global skills useful for development work: `skill-creator` (create/evolve skills), `essence` (intent clarification), `eval-engineering` (evals/benchmarks), `parallel-web-search` / `web-search` (research), `caveman` (token efficiency). Full list: `~/.agents/skills`.

**Runtime (eng-loop in consumer projects):** skill resolution is two-tier — framework `skills/` (highest priority) → `global_skills.roots` (e.g. `~/.agents/skills`) as fallback. Name collisions: framework wins. See `skill-index.md` § Global Skills.

**Promotion rule:** a skill created during a loop that is generic and reusable must be promoted to `~/.agents/skills` (via `skill-creator`), not left as a project-local artifact.

## References (`references/`)

15 shared reference documents (anti-patterns, exit-conditions, lessons, essence-sidecar, etc.).

## Config

`config-template.yaml` contains framework defaults. Projects override via `config.yaml`. Deep-merge: project values win.

## State Template Sync

`state-template.json` must stay in sync with:
- Stage registry in `node_registry.py`
- Stage catalog in `CORE.md`
- Skill mapping in `skill-index.md`

If a stage is added or removed, update all four.

## Editing Conventions

- **Stage ID → filename**: `impl.code` → `stages/impl-code.md`
- **NodeSpec registration**: Add to `node_registry.py` with `NodeSpec(id=..., node_name=..., handler=..., phase=...)`
- **Edge rules**: Add declarative `EdgeRule` in `edge_rules.py`
- **Pydantic schema**: Add matching schema in `schemas.py` for structured output

## Topology Proposal Architecture

The graph is no longer built from hardcoded rules. Instead:

1. **LLM Architect** proposes `GraphTopologyProposal` (stages, edges, phases, policies)
2. **Policy Firewall** authorizes through 5 layers (structural, registry, boundary, connectivity, semantic)
3. **Graph Builder** compiles authorized topology into executable LangGraph
4. **Fallback**: If architect unavailable or proposal rejected, deterministic builder ensures execution

**Invariant:** LLM proposes → Policy authorizes → Builder compiles → Runtime executes.

When modifying the topology system, update these components in order:
1. `schemas.py` — contract (topology schemas)
2. `edge_rules.py` — proposal compiler
3. `policy_resolver.py` — firewall validation
4. `graph_builder.py` — dual-path compilation
5. `dynamic_architect.py` — LLM architect
6. `cli.py` — pre-build invocation
7. Tests — invariant matrix

## Dry-Run Simulator

Validates graph topology without LLM calls. Run from repo root:

```bash
python scripts/dry_run_simulator.py --scenario ALL
python scripts/dry_run_simulator.py --scenario VERIFY_ROLLBACK
```

## Git Submodule

This repo is consumed as a submodule. Breaking changes (renamed stages, removed config keys) should be noted in `skill-index.md`'s improvement log. Consumer projects pick up changes with `git submodule update --remote`.

## OpenCode Config

`.opencode/opencode.json` contains local model provider config. The `.opencode/` directory is gitignored — do not commit it.
