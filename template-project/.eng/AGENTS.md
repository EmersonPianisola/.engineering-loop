# AGENTS.md — Engineering Loop v12.4.0

## What This Repo Is

Framework for an AI-assisted development loop engine. Consumer projects install it as a git submodule at `.eng/`. 

## Two Kinds of Files — Don't Confuse Them

| Read-only (git-tracked, from `.eng/`) | Project-specific (gitignored) |
|---|---|
| `skills/` — 22 built-in skills | `config.yaml` |
| `references/` — 14 reference docs | `state.json` |
| `state-template.json` — Initial state | `STATE.md`, `context.md` |
| `AGENTS.md`, `skill-index.md` — Framework docs | `artifacts/` |

If you're about to edit a file that should be project-specific, you're in the wrong place.

## Development Mode: FF

This project uses **FF (Fail Fast)** as its default development mode.

### FF Protocol

FF is a protocol for parallel swarm-based software development. The main agent orchestrates, sub-agents execute. Every unit of work is atomic, validated in isolation, and fails fast without contaminating siblings.

**Protocol:**
1. **Phase 0: Clarify** — Essence check, resolve scope tensions
2. **Phase 1: Plan Build** — Two sub-agents cross-analyze → consolidate → judge approve
3. **Phase 2: Execute** — Swarm fan-out per block, gate check, retry
4. **Phase 3: Validate** — Cross-check plan vs. reality
5. **Phase 4: Lessons** — Capture lessons, report results

**Key:** The plan is built by two sub-agents (structural + adversarial), consolidated by the main agent, and approved by a judge sub-agent. Only after approval does swarm execution begin. No waves. No graphs. Just blocks.

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

### artifacts/

Trace files are stored in `artifacts/trace-*.jsonl`. These are historical execution traces from previous loop iterations. They are not part of the FF protocol.

### .ff/

The `.ff/` directory is the FF workspace:
- `state.json` — Current FF session state
- `lessons.json` — Accumulated lessons (append-only)
- `README.md` — Documentation

## Skills (`skills/`)

22 built-in skills, each in `skills/{name}/SKILL.md`. The authoritative registry is `skill-index.md` — update it whenever you add, rename, or remove a skill.

## Skill Usage — MANDATORY (Global Skills)

Global skills live in `~/.agents/skills` (user-level, outside this repo). Load the applicable skill with the `skill` tool **before** editing the related code. When in doubt, load `ecosystem-primer` first.

| Working on | Load skill first |
|---|---|
| Any LangChain/LangGraph ecosystem change | `ecosystem-primer` (always first) |
| `pyproject.toml` dependencies | `langchain-dependencies` |

Other global skills useful for development work: `skill-creator` (create/evolve skills), `essence` (intent clarification), `eval-engineering` (evals/benchmarks), `parallel-web-search` / `web-search` (research), `caveman` (token efficiency). Full list: `~/.agents/skills`.

**Runtime (eng-loop in consumer projects):** skill resolution is two-tier — framework `skills/` (highest priority) → `global_skills.roots` (e.g. `~/.agents/skills`) as fallback. Name collisions: framework wins. See `skill-index.md` § Global Skills.

**Promotion rule:** a skill created during a loop that is generic and reusable must be promoted to `~/.agents/skills` (via `skill-creator`), not left as a project-local artifact.

## References (`references/`)

14 shared reference documents (anti-patterns, exit-conditions, lessons, essence-sidecar, etc.) + `lessons-shared.json`.

## Config

`config-template.yaml` contains framework defaults. Projects override via `config.yaml`. Deep-merge: project values win.

## State Template

`state-template.json` is the initial state template for all new projects. Copy to `state.json` when starting a new loop.

## Git Submodule

This repo is consumed as a submodule. Breaking changes (renamed stages, removed config keys) should be noted in `skill-index.md`'s improvement log. Consumer projects pick up changes with `git submodule update --remote`.

## OpenCode Config

`.opencode/opencode.json` contains local model provider config. The `.opencode/` directory is gitignored — do not commit it.
