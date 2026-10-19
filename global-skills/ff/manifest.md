# FF Protocol Manifest — Gate Checklist (v14, hybrid, tiered)

Read this file BEFORE every phase transition and every handoff.
Read order: `harness.md` → this file → the phase instructions in `SKILL.md` (planner) or `ff-exec` (executor).
If any item fails: STOP and fix it before moving on.

---

## Role Assertion

```
PLANNER (Claude):  I plan, dispatch and review. I do not execute work orders.
                   The judge is the only Claude sub-agent; the local executor is dispatched.
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
- [ ] `routing.md` read; every block has `exec_tier` + `rubric`; T1/T2 only when R1-R7 all hold and within the tier size limits; highest eligible tier chosen
- [ ] `plan/blocks.yaml`: ≤ 8 blocks; executor blocks hand-edit ≤ 3 files; shared files dependency-ordered; T1/T2 tests listed in `protected`
- [ ] `plan/work-orders/{block_id}.md` for every block, executor-grade (T0: E/O/C; T1/T2: C-installed tests + I steps with paths, signatures, contracts, examples, "do not", read list; check + commit commands, manual question first)
- [ ] `plan/acceptance/{block_id}.feature` + `plan/checks/{block_id}.py` for every block; `acceptance-plan.md`
- [ ] Planner dry-run on a throwaway copy (`plan/dry-run.txt`): T0 — oldStrings match once, newStrings absent before, second pass changes nothing, checks FAIL → PASS; T1/T2 — tests installed, check FAILS for the expected reason (red), no implementation written
- [ ] Judge dispatched with the clean-view Judge Handoff (artifacts + `routing.md` + this gate); fresh judge on every round; ≤ 3 rounds (`cost.judge_rounds`)
- [ ] `plan/judge.json` approved: true
- [ ] Plan presented AFTER approval; the user said "go" (one per plan)
- [ ] Clean tree; `plan/handoff.json` written with sha256 of work orders, checks, content files, blocks.yaml, and `executor_model`
- [ ] `state.json`: owner → executor, `status: awaiting_execution`, `blocks_pending` set
- [ ] Phase 2 started: the planner dispatches block by block (manual fallback: the user was told to run `/ff exec` in opencode, with the repo path)

---

## Dispatch Gate (planner, per block)

- [ ] Previous block reviewed (approved, or the ladder decided) before this dispatch
- [ ] `owner: executor`; executor lock free (another repo active → wait, tell the user)
- [ ] Manual block: the user's explicit "yes" obtained by the planner → `confirmed` in the arguments
- [ ] Dispatched with `opencode run --command ff --agent ff-executor --dir <repo> --format json … "exec <block_id> driven"`, in the background, with the tier's wall-clock limit
- [ ] Events saved to `execution/{block_id}.events.jsonl`; on timeout/crash → Interrupt Recovery Hook

**COMMON DRIFT:** showing the plan before the judge · self-assessing instead of the judge ·
dispatching any sub-agent other than the judge · a work order that needs judgement ·
pre-writing T1/T2 code · a 4th judge round without the user.

---

## Phase 2 Executor Gate (executor, per block)

- [ ] Gates A-G passed (owner executor; interrupted run handled; status valid; clean tree; executor lock free; model = `executor_model`), lock taken
- [ ] Manual block: `confirmed` in a driven dispatch, or the user confirmed BEFORE the first edit; driven runs never ask
- [ ] Edits applied within scope, with the idempotency rule; I steps exactly as specified; protected files untouched; rework applies ONLY `rework_instruction`
- [ ] Attempt 1, then at most one local self-repair (attempt 2); attempt 3 (planner's correction) without self-repair
- [ ] Timestamps (NOW) and model (MODEL) from the shell helpers
- [ ] One commit `ff({session_id}): {block_id}`
- [ ] `execution/{block_id}.json` written, with `attempts`, `lines_authored_local` and `validation_proposal`; blocked → diff saved
- [ ] Block lists updated; at end of run: owner planner, `status: awaiting_review` or `blocked`; lock released

---

## Review Gate (planner, per executed or blocked block)

- [ ] `handoff.json` hashes verified (work orders, checks, content, blocks.yaml unchanged)
- [ ] Check re-run by the planner — never approved from the executor's self-report
- [ ] Scope: `git show --name-only <commit>` (as `git --no-optional-locks show …`) ⊆ block scope; protected files unchanged (`protected_ok`)
- [ ] Full diff read against the work order and the feature
- [ ] Proposal agreement recorded (`agree` / `disagree` + why)
- [ ] `review/{block_id}.json` written: approved / rework / escalate, with `resolved_at_attempt` and `planner_authored_lines`; `state.json` `cost` updated
- [ ] Attempt ladder: one planner correction per block (attempt 3: `rework_instruction` or corrected work order, executor-grade, dry-run first, may downgrade the tier); attempt 3 failing → escalate to the user
- [ ] Correction with the same scope and acceptance → new `handoff.json`, no fresh judge; a plan, scope or acceptance change → re-plan + fresh judge + new `handoff.json`
- [ ] Blocked block → Blocked recovery: saved `attempt-{n}.diff` + working-tree `git diff`; the USER runs `git restore` (modified files) and deletes untracked new files; the planner verifies a clean tree; then attempt 3 or escalate
- [ ] Planner git on the VM is read-only: `git --no-optional-locks` (status with `-c core.autocrlf=true`)

**COMMON DRIFT:** approving from the executor's self-report · writing to `.git` from the VM.

---

## Completion Gate (planner)

- [ ] Every block approved (or escalated and documented)
- [ ] Final gate: all checks re-run, project tests run (or justified), plan vs commits cross-checked, clean tree
- [ ] `report.md` persisted
- [ ] Lessons appended to `.ff/lessons.json`, each with `actor` (planner | executor)
- [ ] One line per block appended to `.ff/calibration.jsonl`; cost summary in `report.md`
- [ ] `session.json` completed; `state.json`: `status: completed`, `owner: user`
- [ ] `.ff/changelog.md` updated; `harness.md` verification checklist passed

---

## Quick Reference

| Planner DO | Planner DON'T |
|------------|---------------|
| Plan in-session, judge before the user sees the plan | Spawn any Claude sub-agent except the judge |
| Dispatch the executor block by block, review each at once | Ask the user to run `/ff exec` when you can dispatch |
| Route every block by the rubric (`routing.md`) | Pre-write T1/T2 code or hand off a choice |
| Write executor-grade work orders, specs, tests and content | Hand off a work order that needs judgement |
| One correction per block, then the user | Run a 4th judge round without the user |
| Hash the handoff, re-run every check in review | Approve from the validation proposal |
| Keep VM git read-only | Edit repo files during Phase 2 |

| Executor DO | Executor DON'T |
|-------------|----------------|
| Pass gates A-G, follow the block order | Plan, re-scope, or guess |
| Self-repair once (attempt 2) within scope | Edit protected files or checks |
| Take shell timestamps and the model name | Type a timestamp or model yourself |
| Apply edits exactly (idempotency rule) | Edit `plan/`, push, delete, touch `.env` |
| Run the check, commit once, write the trace | Hide a concern or a deviation |
| Stop at the first blocked block | Continue after a block is blocked |
