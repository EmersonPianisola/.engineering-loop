# AGENTS.md — Engineering Loop v11 Framework Repo

## What This Repo Is

Framework documentation for an AI-assisted development loop engine. Consumer projects install it as a git submodule at `.eng/`. This repo contains **only framework code** — stages, skills, references, templates, and install scripts. No application code, no tests, no build system.

## Dual-Mode Architecture (v11)

The loop runs in two modes:

| Mode | How | Enforcement |
|------|-----|-------------|
| **Python CLI** | `eng-loop --dynamic-graph` | LangGraph executes compiled graph — deterministic |
| **LLM Prompt** | LLM reads `ORCHESTRATOR.md` | LLM builds topology via Python, then follows generated plan |

### Python CLI Mode (deterministic)

```bash
eng-loop --dynamic-graph -w "Add OAuth2 login"
eng-loop --dynamic-graph --parallel-qa -w "Add OAuth2 login"
```

LangGraph compiles the graph from active nodes only. The LLM has no choice about routing.

### LLM Prompt Mode (topology-enforced)

The LLM reads `ORCHESTRATOR.md`, which instructs it to:
1. Run `eng-loop --build-topology -w "work item"` — Python generates the graph
2. Read `{artifact-root}/graph-topology.md` — the execution plan
3. Follow the plan exactly — active stages, routing rules, constraints

This solves the problem of LLM ignoring the loop: the graph is built by Python, the LLM follows it.

### Dynamic Graph Components

- `node_registry.py` — 26 stages registered as `NodeSpec` with metadata
- `edge_rules.py` — Declarative `EdgeRule` connections between nodes
- `graph_builder.py` — `GraphBuilder` class that builds and compiles the graph
- `graph.py` — Delegates to `GraphBuilder` when dynamic mode is enabled; static mode preserved
- `cli.py --build-topology` — Generates topology markdown for LLM orchestrator

Parallel QA (`--parallel-qa` or `config.dynamic_graph.parallel_qa: true`) enables fan-out/fan-in for `qa.security`, `qa.api-contract`, `qa.performance`.

## Key Constraint: Read-Only Framework vs. Project Files

Framework files (git-tracked) must never be modified at runtime. Project files (gitignored) are generated per-project:

| Tracked (read-only) | Gitignored (project) |
|---|---|
| `config-template.yaml` | `config.yaml` |
| `state-template.json` | `state.json` |
| `stages/`, `skills/`, `references/` | `artifacts/` |
| `ORCHESTRATOR.md`, `CORE.md`, `START.md` | `STATE.md`, `context.md` |

See `.gitignore` for the full list. If you're editing a file that should be project-specific, you're in the wrong place — that belongs in the consumer project.

## Directory Structure

- `stages/` — 23 stage procedure files. Each is a markdown document describing one phase of the loop (init → design → arch → impl → verify → qa → deploy → doc → post).
- `skills/` — 9 skill definitions (`SKILL.md` per skill). Skills like `verifier`, `solution-designer`, `requirements-refiner`, `implementation-architect`, `bmad-integration`, `bmad-bdd-mapper`, `e2e-playwright`, `graphify`, `cloud-architect`.
- `references/` — 12 shared reference documents (essence-sidecar, exit-conditions, anti-patterns, lessons, etc.).
- `setup/` — Install scripts (`install.sh`, `install.ps1`). Copy templates → project files, create directories.
- `skill-index.md` — Skill registry. Single source of truth for skill ID → stage mapping.
- `config-template.yaml` — Framework defaults. Deep-merged with project `config.yaml`.
- `state-template.json` — Initial state for all 23 stages.

## Editing Stages

Each stage file in `stages/` follows the pattern `{stage-id}.md`. Stage IDs use dot notation (e.g., `impl.code`, `qa.security`). The file name must match the ID with dots replaced by hyphens (e.g., `impl-code.md`, `qa-security.md`). The orchestrator loads stages by ID → file lookup.

## Editing Skills

Each skill lives in `skills/{name}/SKILL.md`. If you add or rename a skill, update `skill-index.md` — it is the authoritative registry that maps skill IDs to stages.

## Editing Config Defaults

`config-template.yaml` contains framework defaults. Projects override via their own `config.yaml`. Never change a default without updating any docs that reference the old value. Key config sections: `constraints`, `hardware`, `essence`, `auto_sizing`, `lessons`, `graphify`.

## State Template

`state-template.json` must stay in sync with the stage registry in `CORE.md` and `skill-index.md`. If a stage is added or removed, update all three: the template, the stage file, and the registry.

## No Build, Test, or Lint

This is a documentation/template repo. There are no executable commands to run. Validation is done by loading `ORCHESTRATOR.md` in an agent session and verifying the loop runs correctly against a consumer project.

## OpenCode Config

`.opencode/opencode.json` contains local model provider config. The `.opencode/` directory is gitignored by the repo's `.gitignore` and should not be committed.

## Git Submodule Considerations

This repo is consumed as a submodule. Any change here requires consumer projects to run `git submodule update --remote` to pick it up. Breaking changes (renamed stages, removed config keys) should be noted in `skill-index.md`'s improvement log.
