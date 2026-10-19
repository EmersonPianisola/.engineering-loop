# AGENTS.md — Engineering Loop v14.0.0

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

### FF Protocol (Hybrid — v14, tiered)

FF is a fail-fast protocol with two roles that communicate only through files in `.ff/`. The **planner** (Claude, cloud session linked to the repo) owns every input, the plan, and the final validation. The **executor** (local model via opencode) executes the approved work orders, dispatched by the planner one block at a time like a sub-agent. Every unit of work is atomic, validated in isolation, and fails fast without contaminating siblings.

**Protocol:**
1. **Phase 0: Clarify** (planner) — Essence check, resolve scope tensions
2. **Phase 1: Plan** (planner) — Structural + adversarial in-session passes → plan → blocks routed by execution tier (T0 mechanical · T1 guided · T2 high effort) → executor-grade work orders (T1/T2: spec + planner-written protected tests) → acceptance (Gherkin) + executable checks → judge approve (≤ 3 rounds) → handoff
3. **Phase 2: Execute** (executor, dispatched by the planner one block at a time — `opencode run --command ff --agent ff-executor`; manual fallback `/ff exec`) — apply the work order (T1/T2: write the specified code), run checks, self-repair once (attempt 2), commit per block, write execution trace + validation proposal; the planner reviews each block before the next dispatch
4. **Phase 3: Review & Validate** (planner) — Critical second validation: re-run checks, scope check, full diff review, verdict per block, one correction per block (attempt 3) then the user, final gate
5. **Phase 4: Lessons** (planner) — Capture lessons (planner and executor), report results

**Key:** The judge is the only sub-agent — dispatched by the planner with a clean view (artifacts only) — and approves the plan, work orders, acceptance and checks before anything is handed off. The executor never plans; the planner never trusts the executor's self-report without re-running the checks. No waves. No graphs. Just blocks.

**Tiers (v14):** every block gets an execution tier from the routing rubric (`global-skills/ff/routing.md`) — T0 mechanical, T1 guided, T2 high effort. The planner specifies and validates; the local model writes the code when the spec and protected tests allow it. After your single "go" the planner dispatches and supervises the local model block by block (`opencode run --command ff --agent ff-executor`), like a sub-agent. Attempts 1-2 are local (2 = self-repair), attempt 3 is one planner correction, then the user decides. The judge is capped at 3 rounds. Every session appends `.ff/calibration.jsonl` for the beta calibration (`references/executor-calibration.md`).

### Hybrid Roles — Which One Are You?

| You are | Load | Do | Never |
|---|---|---|---|
| Claude (planner) | `global-skills/ff/SKILL.md` (consumers: `.eng/global-skills/ff/SKILL.md`) | Phases 0, 1, 3, 4; in Phase 2 dispatch and supervise the executor block by block (`opencode run --command ff --agent ff-executor`) | Edit repo files in Phase 2 |
| Local model in opencode (executor) | `global-skills/ff-exec/SKILL.md` via the `ff-executor` agent (dispatched by the planner) or `/ff exec` | Phase 2 only, when `.ff/state.json` `owner` is `executor` | Plan, re-scope, edit `plan/` artifacts, push, delete |

**Multi-project:** one active FF session per repo. The protocol is always read from the repo being worked on — never from memory or another repo. Every handoff names the repo.

### Using FF

**Start a session (planner — Claude):**
- Describe the work to Claude in the session linked to this repo, or say "use FF" — the planner loads the ff skill for substantial work requests
- The planner plans, gets judge approval and your single "go", then dispatches the local model block by block (`opencode run --command ff --agent ff-executor`) and reviews each block as it returns

**Manual fallback (executor — opencode), only when the planner has no shell on this machine:**
- `/ff exec` — execute all pending/rework blocks of the active session (stops at the first blocked block)
- `/ff exec <block_id>` — execute one block
- `/ff status` — show the active session, owner and block lists
- `/ff <description>` in opencode is refused — planning happens in the planner session

**Session management (ask the planner):** status, resume, history, lessons — all read from `.ff/`.

FF tracks all progress in `.ff/` (gitignored — these are working artifacts):
- Current session state: `.ff/state.json`
- Session traces: `.ff/traces/{session_id}/`
- Lessons learned: `.ff/lessons.json`
- Session changelog: `.ff/changelog.md`

If a session is interrupted, ask the planner to resume — it reads `.ff/state.json` (`owner` says whose turn it is).

### Autonomy Score

| Score | Mode | Behavior |
|-------|------|----------|
| ≥ 0.8 | FULL AUTO | Execute without asking |
| 0.5-0.7 | SEMI AUTO | Show plan → wait for "go" → execute |
| < 0.5 | MANUAL | Ask before each block |

**FF v14:** one "go" per plan — after it the planner (Claude) dispatches and supervises the local executor block by block; manual blocks still ask you first. The score is reported with the plan as a risk summary.

### Hard Rules (Never Override)

- `rm -rf`, `git push --force` — always ask
- Writes to Firebase — always ask
- Changes to `.env` — always ask
- Operations outside workspace — always block (exception: the FF executor writes, never deletes, `~/.agents/ff-executor.lock` — ff-exec section 6)

### Loop Motor Removed (FF Replaces It)

The loop motor (LangGraph, Python orchestrator, 34 stages) was removed in the FF transition (v12.4.0). FF protocol replaces the stage-based loop entirely. What remains in this repo:
- `references/` — 17 reference docs (decision log, anti-patterns, lessons, ff-protocol, executor-calibration, etc.)
- `skills/` — 23 ideação/verificação skills
- `artifacts/` — trace JSONL files (gitignored)
- `AGENTS.md`, `skill-index.md`, `FF-CHANGELOG.md` — framework documentation

Consumer projects install this repo as a git submodule at `.eng/` and develop with FF protocol. (This repo's own local `.eng/` directory is a pre-FF leftover and is gitignored — do not use it.)

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

## Skills (`skills/`)

23 built-in skills, each in `skills/{name}/SKILL.md`. The authoritative registry is `skill-index.md` — update it whenever you add, rename, or remove a skill.

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

16 shared reference documents (anti-patterns, exit-conditions, lessons, essence-sidecar, ff-protocol, executor-calibration, etc.) + `lessons-shared.json`.

## Config

Consumer projects use no framework config file. FF sessions are driven by `.ff/state.json` (schema in `global-skills/ff/SKILL.md`) — the framework itself has nothing to configure.

## State Template Sync

`state-template.json` is retained for reference only. It documents the historical loop state shape; FF sessions use `.ff/state.json` instead (schema in `global-skills/ff/SKILL.md`).

## Git Submodule

This repo is consumed as a submodule. Breaking changes (renamed stages, removed config keys) should be noted in `skill-index.md`'s improvement log. Consumer projects pick up changes with `git submodule update --remote`.

## OpenCode Config

`.opencode/opencode.json` contains local model provider config and is gitignored — do not commit it. `.opencode/commands/ff.md` (the `/ff` command definition) and `.opencode/agents/ff-executor.md` (the executor agent the planner dispatches) are tracked — do not delete them.
