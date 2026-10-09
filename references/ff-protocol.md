---
name: ff-protocol
id: ff
version: 2.0.0
type: reference
description: 'FF (Fail Fast) protocol reference — hybrid roles (Claude planner + local executor), file-based handoff contract, and pointers to the canonical skills. The skills are the source of truth; this file is a summary.'
---

# FF Protocol — Reference (v13.0.0)

This file is a short reference. The canonical protocol lives in the skills:

| Role | Canonical file | Loaded by |
|---|---|---|
| Planner | `global-skills/ff/SKILL.md` (+ `manifest.md`, `harness.md`, `autonomy-harness.md`) | Claude (cloud session linked to the repo) |
| Executor | `global-skills/ff-exec/SKILL.md` | Local model via opencode (`/ff exec`) |

In consumer projects the same files are under `.eng/global-skills/`. If this file and a skill disagree, the skill wins.

## Roles

- **Planner (Claude):** Phase 0 Clarify, Phase 1 Plan (two separate in-session analysis passes, plan, blocks, work orders, Gherkin acceptance, executable checks, judge), Phase 3 Review & Validate (critical, independent), Phase 4 Lessons.
- **Executor (local model):** Phase 2 Execute only — applies work orders, runs checks, commits locally one commit per block, writes the execution trace with a validation proposal.
- **Judge:** the only sub-agent. Dispatched by the planner with a clean view (artifacts only). Approves plan, work orders, acceptance and checks before any handoff. Unavailable judge = HALT.

## Phases

```
PHASE 0: CLARIFY           (planner)  → essence check, scope, work type
PHASE 1: PLAN              (planner)  → structural pass → adversarial pass → plan → blocks → work orders
                                        → acceptance (Gherkin) + checks → judge → handoff
PHASE 2: EXECUTE           (executor) → /ff exec: work order → checks → commit → execution trace + validation proposal
PHASE 3: REVIEW & VALIDATE (planner)  → re-run checks, scope check, full diff review, verdict per block, final gate
PHASE 4: LESSONS           (planner)  → lessons (actor: planner | executor), report, changelog
```

## Handoff Contract

`.ff/state.json`: `owner` (`planner` | `executor` | `user`), `status` (`planning` | `awaiting_execution` | `executing` | `awaiting_review` | `rework` | `blocked` | `completed` | `cancelled`), block lists `blocks_pending`, `blocks_executed`, `blocks_rework`, `blocks_blocked`, `blocks_completed`.

`.ff/traces/{session_id}/`:

| Artifact | Writer |
|---|---|
| `plan/blocks.yaml`, `plan/work-orders/{block_id}.md`, `plan/acceptance/{block_id}.feature`, `plan/checks/{block_id}.py`, `plan/handoff.json` | planner |
| `plan/judge.json` | judge |
| `execution/{block_id}.json` | executor |
| `review/{block_id}.json`, `report.md` | planner |

Checks: Python standard library only, run from the repo root (`python .ff/traces/{session_id}/plan/checks/{block_id}.py`), print `PASS`/`FAIL` per scenario, exit 0 only when all pass.

## Invariants

- Acceptance (Gherkin + checks) is written before the judge; the judge is never skipped.
- Executor self-report is never evidence — the planner re-runs every check.
- At most 8 blocks per session; an executor block hand-edits at most 3 files (files rewritten by a script the work order runs do not count).
- One active FF session per repo; the protocol is read from the repo being worked on.
- Hard rules (destructive operations, external writes, `.env`, outside the workspace) always require user confirmation — for both roles.
