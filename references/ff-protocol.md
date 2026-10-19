---
name: ff-protocol
id: ff
version: 3.0.0
type: reference
description: 'FF (Fail Fast) protocol reference — hybrid roles (Claude planner + local executor), execution tiers and attempt ladder, file-based handoff contract, and pointers to the canonical skills. The skills are the source of truth; this file is a summary.'
---

# FF Protocol — Reference (v14.0.0)

This file is a short reference. The canonical protocol lives in the skills:

| Role | Canonical file | Loaded by |
|---|---|---|
| Planner | `global-skills/ff/SKILL.md` (+ `routing.md`, `manifest.md`, `harness.md`, `autonomy-harness.md`) | Claude (cloud session linked to the repo) |
| Executor | `global-skills/ff-exec/SKILL.md` (+ agent `.opencode/agents/ff-executor.md`) | Local model via opencode, dispatched by the planner (`opencode run --command ff --agent ff-executor`; manual fallback `/ff exec`) |

In consumer projects the same files are under `.eng/global-skills/`. If this file and a skill disagree, the skill wins.

## Roles

- **Planner (Claude):** Phase 0 Clarify, Phase 1 Plan (two separate in-session analysis passes, plan, blocks, work orders, Gherkin acceptance, executable checks, judge), Phase 3 Review & Validate (critical, independent), Phase 4 Lessons.
- **Executor (local model):** an external sub-agent the planner dispatches one block at a time (`opencode run --command ff --agent ff-executor "exec <block_id> driven"`; manual fallback `/ff exec`). Phase 2 Execute only — applies work orders (T0 steps; T1/T2 implementation from the planner's spec and tests), runs checks, self-repairs once, commits locally one commit per block, writes the execution trace with a validation proposal.
- **Judge:** the only Claude sub-agent. Dispatched by the planner with a clean view (artifacts only). Approves plan, work orders, acceptance and checks before any handoff. Unavailable judge = HALT.

## Phases

```
PHASE 0: CLARIFY           (planner)  → essence check, scope, work type
PHASE 1: PLAN              (planner)  → structural pass → adversarial pass → plan → blocks → work orders
                                        → acceptance (Gherkin) + checks → judge → handoff
PHASE 2: EXECUTE           (executor, dispatched by the planner one block at a time) → work order → checks → self-repair → commit → execution trace + validation proposal → planner review
PHASE 3: REVIEW & VALIDATE (planner)  → re-run checks, scope check, full diff review, verdict per block, final gate
PHASE 4: LESSONS           (planner)  → lessons (actor: planner | executor), report, changelog
```

## Execution Tiers and Attempt Ladder (v14)

Canonical: `global-skills/ff/routing.md`. Calibration: `references/executor-calibration.md`.

| Tier | Executor writes | Planner delivers |
|---|---|---|
| T0 mechanical | nothing new — applies C/O/E steps | every byte |
| T1 guided | one bounded implementation | spec + tests (protected) |
| T2 high effort | several functions, up to 3 files | spec + ordered steps + tests (protected) |

T1/T2 only when the rubric R1-R7 holds (exact paths and symbols, planner tests red before, no design decision, no long prose, read list and size limits, no parsed free-form JSON).

Attempts per block: 1 and 2 local (2 = self-repair with the check output) → 3 = the planner's single correction (may downgrade the tier) → the user decides. Judge: at most 3 rounds per session. Execution is serial across repos (one GPU): executor lock `~/.agents/ff-executor.lock`.

## Handoff Contract

`.ff/state.json`: `owner` (`planner` | `executor` | `user`), `status` (`planning` | `awaiting_execution` | `executing` | `awaiting_review` | `rework` | `blocked` | `completed` | `cancelled`), block lists `blocks_pending`, `blocks_executed`, `blocks_rework`, `blocks_blocked`, `blocks_completed`.

`.ff/traces/{session_id}/`:

| Artifact | Writer |
|---|---|
| `plan/blocks.yaml` (`exec_tier`, `rubric`, `protected`), `plan/work-orders/{block_id}.md`, `plan/acceptance/{block_id}.feature`, `plan/checks/{block_id}.py`, `plan/handoff.json` (`executor_model`) | planner |
| `plan/judge.json` | judge |
| `execution/{block_id}.json` (`attempts`, `model`, `lines_authored_local`), `execution/{block_id}.attempt-{n}.diff` | executor |
| `review/{block_id}.json` (`resolved_at_attempt`, `planner_authored_lines`), `report.md`, `.ff/calibration.jsonl` | planner |

Checks: Python standard library only, run from the repo root (`python .ff/traces/{session_id}/plan/checks/{block_id}.py`), print `PASS`/`FAIL` per scenario, exit 0 only when all pass.

## Invariants

- Acceptance (Gherkin + checks) is written before the judge; the judge is never skipped.
- One "go" per plan; then the planner dispatches every block and reviews each one before the next. A driven executor never asks; manual blocks are confirmed by the user through the planner.
- Executor self-report is never evidence — the planner re-runs every check.
- The executor never makes a design choice: the planner names every path, symbol and contract; tests are protected.
- At most one cloud correction per block, at most 3 judge rounds per session.
- At most 8 blocks per session; an executor block hand-edits at most 3 files (files rewritten by a script the work order runs do not count).
- One active FF session per repo; the protocol is read from the repo being worked on.
- Hard rules (destructive operations, external writes, `.env`, outside the workspace) always require user confirmation — for both roles. Exception: the FF executor writes (never deletes) `~/.agents/ff-executor.lock` with the exact ff-exec section 6 commands.
