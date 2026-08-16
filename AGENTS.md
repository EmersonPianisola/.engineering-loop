# AGENTS.md — Engineering Loop v11 Framework Repo

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

The orchestrator is a real Python package, not just docs. It has tests, linting, and a CLI.

```
eng_loop/
├── pyproject.toml          # Package config: ruff, pytest, entry point
├── src/eng_loop/           # Package source
│   ├── cli.py              # Entry point (eng-loop command, pre-build architect)
│   ├── graph_builder.py    # Dual-path builder (proposal or deterministic)
│   ├── node_registry.py    # 29 registered NodeSpec stages
│   ├── edge_rules.py       # Declarative edge rules + proposal compiler
│   ├── state.py            # PipelineState schema + reducers + node catalog
│   ├── schemas.py          # 31 Pydantic schemas (5 topology + 26 stage)
│   ├── config.py           # YAML loader, deep merge
│   ├── nodes/              # One module per stage group (init, design, impl, qa, etc.)
│   │   └── dynamic_architect.py  # Pre-build topology + runtime augmentation
│   └── tools/              # ~35 tool modules
│       └── policy_resolver.py    # 5-layer topology firewall + tool sandboxing
└── tests/                  # 28+ test files (1484 tests)
```

Install (editable) and run commands from the `eng_loop/` directory:

```bash
# Install package with dev deps
pip install -e "eng_loop/[dev]"

# Lint
ruff check eng_loop/src eng_loop/tests

# Format
ruff format eng_loop/src eng_loop/tests

# Run all tests
pytest eng_loop/tests

# Run single test file
pytest eng_loop/tests/test_config.py -v

# Run single test
pytest eng_loop/tests/test_config.py -v -k "test_merge"
```

The CLI entry point is `eng-loop` (defined in `pyproject.toml` → `[project.scripts]`). After editable install, it's available on PATH.

## Stage Files (`stages/`)

24 markdown files, one per stage. Naming: stage ID with dots replaced by hyphens (e.g., `impl.code` → `impl-code.md`). These are **prompt templates** loaded at runtime by `templates.py`, not instructions for the orchestrator.

## Skills (`skills/`)

11 built-in skills, each in `skills/{name}/SKILL.md`. The authoritative registry is `skill-index.md` — update it whenever you add, rename, or remove a skill.

## References (`references/`)

15 shared reference documents (anti-patterns, exit-conditions, lessons, essence-sidecar, etc.).

## Config

`config-template.yaml` contains framework defaults. Projects override via `config.yaml`. Deep-merge: project values win. Key sections: `constraints`, `hardware`, `essence`, `auto_sizing`, `lessons`, `graphify`, `dynamic_graph`.

## State Template

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
- **Topology proposal**: New schemas in `schemas.py` (topology section, before DYNAMIC NODE ORCHESTRATION)
- **Policy firewall**: New validation layers in `policy_resolver.py` (after `authorize_blueprint`)
- **ruff config**: `target-version = "py310"`, `line-length = 120` (in `eng_loop/pyproject.toml`)

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

## Git Submodule

This repo is consumed as a submodule. Breaking changes (renamed stages, removed config keys) should be noted in `skill-index.md`'s improvement log. Consumer projects pick up changes with `git submodule update --remote`.

## OpenCode Config

`.opencode/opencode.json` contains local model provider config. The `.opencode/` directory is gitignored — do not commit it.
