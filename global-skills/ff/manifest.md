# FF Protocol Manifest — Gate Checklist (v13, hybrid)

Read this file BEFORE every phase transition and every handoff.
Read order: `harness.md` → this file → the phase instructions in `SKILL.md` (planner) or `ff-exec` (executor).
If any item fails: STOP and fix it before moving on.

---

## Role Assertion

```
PLANNER (Claude):  I plan and review. I do not execute work orders.
                   The judge is the only sub-agent.
EXECUTOR (local):  I execute work orders. I do not plan. I never edit plan artifacts.
```
`.ff/state.json` `owner` says whose turn it is. If it is not your turn: report and wait.

---

## Pre-Flight (both roles)

- [ ] `harness.md` pre-hook executed
- [ ] `.ff/state.json` read (`owner`, `status`, block lists)
- [ ] `.ff/lessons.json` read (planner: all relevant; executor: none needed)
- [ ] Role asserted

---

## Phase 0 → 1 Gate (planner)

- [ ] `session_id` generated, `.ff/traces/{session_id}/` created, `session.json` written
- [ ] `state.json` initialized: `owner: planner`, `status: planning`
- [ ] Essence check done, Lens 4 tensions resolved, `essence.md` persisted
- [ ] Skills discovered → `state.json` `skills` + `skills.md`
- [ ] Work type classified; auto-size rule evaluated

---

## Phase 1 → Handoff Gate (planner)

- [ ] Two SEPARATE in-session analysis passes persisted: `plan/structural.json`, `plan/adversarial.json`
- [ ] Conflicts reconciled; `plan/plan.md` persisted
- [ ] `plan/blocks.yaml`: ≤ 8 blocks; executor blocks hand-edit ≤ 3 files; shared files dependency-ordered
- [ ] `plan/work-orders/{block_id}.md` for every block, executor-grade (E/O/C format, check + commit commands, manual question first)
- [ ] `plan/acceptance/{block_id}.feature` + `plan/checks/{block_id}.py` for every block; `acceptance-plan.md`
- [ ] Planner dry-run on a throwaway copy: oldStrings match once, newStrings absent before, second pass changes nothing, checks FAIL → PASS (`plan/dry-run.txt`)
- [ ] Judge dispatched with the clean-view Judge Handoff (artifacts only); fresh judge on every round
- [ ] `plan/judge.json` approved: true
- [ ] Plan presented AFTER approval; the user said "go"
- [ ] Clean tree; `plan/handoff.json` written with sha256 of work orders, checks, content files, blocks.yaml
- [ ] `state.json`: owner → executor, `status: awaiting_execution`, `blocks_pending` set
- [ ] The user was told to run `/ff exec` in opencode, with the repo path

**COMMON DRIFT:** showing the plan before the judge · self-assessing instead of the judge ·
dispatching any sub-agent other than the judge · a work order that needs judgement.

---

## Phase 2 Executor Gate (executor, per block)

- [ ] Gates A-E passed (owner executor; interrupted run handled; status valid; clean tree)
- [ ] Manual block: user confirmed BEFORE the first edit
- [ ] Edits applied within scope, with the idempotency rule; rework applies ONLY `rework_instruction`
- [ ] Check run; one retry at most
- [ ] One commit `ff({session_id}): {block_id}`
- [ ] `execution/{block_id}.json` written, with `validation_proposal`
- [ ] Block lists updated; at end of run: owner planner, `status: awaiting_review` or `blocked`

---

## Review Gate (planner, per executed or blocked block)

- [ ] `handoff.json` hashes verified (work orders, checks, content, blocks.yaml unchanged)
- [ ] Check re-run by the planner — never approved from the executor's self-report
- [ ] Scope: `git show --name-only <commit>` (as `git --no-optional-locks show …`) ⊆ block scope
- [ ] Full diff read against the work order and the feature
- [ ] Proposal agreement recorded (`agree` / `disagree` + why)
- [ ] `review/{block_id}.json` written: approved / rework / escalate
- [ ] Rework: `rework_instruction` is executor-grade (E/O/C against the committed state, dry-run first); ≤ 2 rework rounds, then escalate
- [ ] Rework that needs a plan or scope change → re-plan + fresh judge + new `handoff.json`
- [ ] Blocked block → Blocked recovery: working-tree `git diff`; the USER runs `git restore` (modified files) and deletes untracked new files; the planner verifies a clean tree; then rework or re-plan
- [ ] Planner git on the VM is read-only: `git --no-optional-locks` (status with `-c core.autocrlf=true`)

**COMMON DRIFT:** approving from the executor's self-report · writing to `.git` from the VM.

---

## Completion Gate (planner)

- [ ] Every block approved (or escalated and documented)
- [ ] Final gate: all checks re-run, project tests run (or justified), plan vs commits cross-checked, clean tree
- [ ] `report.md` persisted
- [ ] Lessons appended to `.ff/lessons.json`, each with `actor` (planner | executor)
- [ ] `session.json` completed; `state.json`: `status: completed`, `owner: user`
- [ ] `.ff/changelog.md` updated; `harness.md` verification checklist passed

---

## Quick Reference

| Planner DO | Planner DON'T |
|------------|---------------|
| Plan in-session, judge before the user sees the plan | Dispatch any sub-agent except the judge |
| Write executor-grade work orders and content | Hand off a work order that needs judgement |
| Hash the handoff, re-run every check in review | Approve from the validation proposal |
| Keep VM git read-only | Edit repo files during Phase 2 |

| Executor DO | Executor DON'T |
|-------------|----------------|
| Pass gates A-E, follow the block order | Plan, re-scope, or guess |
| Apply edits exactly (idempotency rule) | Edit `plan/`, push, delete, touch `.env` |
| Run the check, commit once, write the trace | Hide a concern or a deviation |
| Stop at the first blocked block | Continue after a block is blocked |
