# AGENTS.md — Engineering Loop v12.4.0

## What This Repo Is

Framework for an AI-assisted development loop engine. Consumer projects install it as a git submodule at `.eng/`. Contains framework code only: skills, references, FF protocol docs, and global skills management.

## Two Kinds of Files — Don't Confuse Them

| Read-only (git-tracked) | Project-specific (gitignored) |
|---|---|
| `state-template.json` | `state.json` |
| `skills/`, `references/` | `artifacts/` |
| `AGENTS.md`, `skill-index.md` | `STATE.md`, `context.md` |
| `global-skills/` | `.ff/` |

If you're about to edit a file that should be project-specific, you're in the wrong place.

## Development Mode: FF (MANDATORY)

This project and all consumer projects using this framework MUST use **FF (Fail Fast)** as the default development mode.

### For Consumer Projects

Consumer projects install this repo as a git submodule at `.eng/` and update their project-level `AGENTS.md` to declare FF as mandatory. Use `template-project/AGENTS.md` as the template.

Key: The consumer project's `AGENTS.md` must instruct the agent to auto-load the ff skill for any substantial work request — no explicit "use FF" invocation should be needed.

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

### .eng/ is Trimmed

The `.eng/` directory has been trimmed: the loop motor (LangGraph, Python orchestrator, 34 stages) has been removed. What remains:
- `references/` — 14 reference docs (decision log, anti-patterns, lessons, etc.)
- `skills/` — 22 ideação/verificação skills
- `artifacts/` — trace JSONL files
- `AGENTS.md`, `skill-index.md` — framework documentation

Consumer projects that install this repo as a git submodule will be broken by these changes. They must migrate to FF protocol.

### artifacts/

Trace files are stored in `artifacts/trace-*.jsonl`. These are historical execution traces from previous loop iterations. They are not part of the FF protocol.

### .ff/

The `.ff/` directory is the FF workspace:
- `state.json` — Current FF session state
- `lessons.json` — Accumulated lessons (append-only)
- `README.md` — Documentation

### Global Skills Management (`global-skills/`)

All global skills for `~/.agents/skills/` are versioned in `global-skills/`. This is the single source of truth — consumer projects sync from here.

**Workflow:**
- Add/update skill: `python scripts/sync-global-skills.py push [name]`
- Deploy to local: `python scripts/sync-global-skills.py pull`
- Check status: `python scripts/sync-global-skills.py status`
- List skills: `python scripts/sync-global-skills.py list`

**Consumer projects:** After submodule update, run `python .eng/scripts/sync-global-skills.py pull` to sync skills to `~/.agents/skills/`.

**Rules:**
- All generic/reusable skills MUST be in `global-skills/`, not in consumer projects
- New generic skills created during FF runs: promote via `skill-creator` → `push` → commit
- Never edit skills directly in `~/.agents/skills/` — edit in `global-skills/`, then `pull`

---

## Python Package: `eng_loop/` — TRIMMED

The loop motor (LangGraph, Python orchestrator, 34 stages) has been removed in the FF transition. See `.eng/ is Trimmed` above for details. This section is retained as a historical note only.

## Stage Files (`stages/`) — TRIMMED

Stage prompt templates were removed in the FF transition. FF protocol replaces the stage-based loop entirely.

## Skills (`skills/`)

22 built-in skills, each in `skills/{name}/SKILL.md`. The authoritative registry is `skill-index.md` — update it whenever you add, rename, or remove a skill.

## Skill Usage — MANDATORY (Global Skills)

Global skills live in `~/.agents/skills` (user-level, outside this repo). Load the applicable skill with the `skill` tool **before** editing the related code. When in doubt, load `ecosystem-primer` first.

| Working on | Load skill first |
|---|---|
| Any LangChain/LangGraph ecosystem change | `ecosystem-primer` (always first) |
| Deep Agents applications | `deep-agents-core` (+ `deep-agents-memory` / `deep-agents-orchestration`) |
| FF protocol or skill development | `skill-creator` (create/evolve skills), `essence` (intent clarification) |

Other global skills useful for development work: `eval-engineering` (evals/benchmarks), `parallel-web-search` / `web-search` (research), `caveman` (token efficiency). Full list: `~/.agents/skills`.

**Promotion rule:** a skill created during an FF run that is generic and reusable must be promoted to `global-skills/` → `push` → commit, not left as a project-local artifact.

## References (`references/`)

14 shared reference documents (anti-patterns, exit-conditions, lessons, essence-sidecar, etc.) + `lessons-shared.json`.

## Config

Project-specific `config.yaml` files are generated by consumer projects. No framework-level `config-template.yaml` exists (trimmed).

## State Template Sync

`state-template.json` is retained for reference. It no longer needs to stay in sync with `node_registry.py` or `CORE.md` (both removed).

## Editing Conventions — TRIMMED

Stage files, NodeSpec registration, edge rules, and Pydantic schemas were part of the removed loop motor. No editing conventions apply.

## Topology Proposal Architecture — TRIMMED

The LLM architect, policy firewall, and graph builder were part of the removed `eng_loop/` package. FF protocol replaces this with block-based parallel execution.

## Dry-Run Simulator — TRIMMED

The dry-run simulator validated graph topology for the removed orchestrator. No replacement in FF mode.

## Git Submodule

This repo is consumed as a submodule. Breaking changes (renamed stages, removed config keys) should be noted in `skill-index.md`'s improvement log. Consumer projects pick up changes with `git submodule update --remote`.

## OpenCode Config

`.opencode/opencode.json` contains local model provider config. The `.opencode/` directory is gitignored — do not commit it.
