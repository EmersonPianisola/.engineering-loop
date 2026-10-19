# FF Protocol Harness — Hooks (v14, hybrid, tiered)

**READ THIS BEFORE ANY OTHER FF FILE.** These hooks are the mechanical guardrail
against drift. They are not optional.

---

## Pre-Hook (before any phase, handoff or review)

1. **Read state:** `.ff/state.json`.
   - Missing → planner: new session (Phase 0).
   - `status` is `completed` or `cancelled` → planner: new session.
   - Branch on `owner`:
     - `planner` → planner flow (continue at `current_phase`).
     - `executor` → if you are the planner: the executor is working; report the status to the user and wait. If you are the executor: follow `ff-exec` (gates A-G).
     - `user` → the session is closed; the planner starts a new one when asked.
     - no `owner` field → **legacy** (pre-v13) session: the planner decides how to continue and re-judges before any handoff.
2. **Read** `manifest.md` — the checklist for the upcoming gate.
3. **Read** `.ff/lessons.json` (planner) — note prevention rules for this work type, including executor lessons.
4. **Assert role:** planner: "FF session initialized. I am the planner." Executor: "I am the executor."
5. **Planner, before Step 1.3:** read `routing.md` (tiers, rubric, attempt ladder).

---

## Phase 0 → 1 Post-Hook (planner)

Write `state.json` (`current_phase: "phase_0"`, `owner: planner`, `status: planning`,
`work_type`, `task_title`, `skills`, `updated_at`), `skills.md` and `essence.md`.

---

## Handoff Hook (planner, end of Phase 1)

1. Verify that these exist: `plan/structural.json`, `plan/adversarial.json`, `plan/plan.md`, `plan/blocks.yaml` (every block with `exec_tier` and `rubric`), `plan/work-orders/{block_id}.md`, `plan/acceptance-plan.md`, `plan/acceptance/{block_id}.feature`, `plan/checks/{block_id}.py` (every block), `plan/dry-run.txt` (T0 FAIL → PASS; T1/T2 red with the failing ids), and `plan/judge.json` with `approved: true` within 3 rounds.
2. Verify that the user said "go" (one per plan) and the tree is clean.
3. Write `plan/handoff.json` (sha256 of every work order, check, content file and `blocks.yaml`; `executor_model`).
4. Set `state.json`: `owner: executor`, `status: awaiting_execution`, `current_phase: "phase_2"`, `blocks_pending`.
5. Start Phase 2: dispatch the blocks one at a time (SKILL.md Phase 2, driven). Manual fallback (no shell on the executor's machine): tell the user to run `/ff exec` in opencode in `<repo path>`.

If anything is missing: do not hand off.

---

## Dispatch Hook (planner, per block — SKILL.md Phase 2)

Before each dispatch: `owner: executor`; executor lock free (else wait, tell the user);
manual block → the user's explicit "yes" first, then `confirmed`. Dispatch in the
background with the tier's wall-clock limit; save `execution/{block_id}.events.jsonl`.
After it returns: the Review Hook for that block, before the next dispatch.

## Execution Hook (executor, per block — details in ff-exec)

Per block: attempt 1, then attempt 2 (local self-repair) if the check failed;
timestamps and the model from the shell. After each block: write
`execution/{block_id}.json` (`attempts`, `lines_authored_local`) and move the block
to `blocks_executed` (or `blocks_blocked`, with the saved
`execution/{block_id}.attempt-{n}.diff`). At the end of the run: `owner: planner`,
`status: awaiting_review` (or `blocked`), executor lock released.

---

## Review Hook (planner, per block)

1. Verify the `handoff.json` hashes, re-run the check, check the scope with `git --no-optional-locks show --name-only` and the protected files, read the full diff, record the proposal agreement, `resolved_at_attempt` and the planner-authored lines (update `state.json` `cost`).
2. Write `review/{block_id}.json` and update the lists:
   - approved → `blocks_completed`;
   - rework → `blocks_rework`, executor-grade `rework_instruction` (dry-run first), `owner: executor`, `status: rework` — this is the block's attempt 3 (the planner's single correction);
   - escalate → ask the user (attempt 3 failed, or a second correction would be needed).
3. For blocks in `blocks_blocked`, apply **Blocked recovery** (SKILL.md Phase 3):
   - review the working-tree `git --no-optional-locks diff`;
   - the USER runs `git restore --staged --worktree -- <modified tracked files>`;
   - the USER deletes **untracked** files the block created, with the exact `del <path>` commands the planner gives;
   - the planner verifies a clean tree (`git --no-optional-locks -c core.autocrlf=true status --porcelain`);
   - diagnose from the trace and `execution/{block_id}.attempt-{n}.diff`; then attempt 3: a corrected work order (same scope and acceptance → planner dry-run + new `handoff.json`, no fresh judge; may downgrade the tier) or a re-plan with a fresh judge — or escalate if attempt 3 already ran.
4. Pending blocks left and nothing blocked or in rework → `owner: executor`, `status: awaiting_execution`, dispatch the next block (no new judge).

Planner git on the VM is read-only (`git --no-optional-locks`): never `add`, `commit`,
`update-index`, `restore` or `checkout` from the VM.

---

## Completion Post-Hook (planner)

Write `report.md` (with the cost summary). Update `session.json` (`status: completed`, `completed_at`,
files). Set `state.json` to `status: completed`, `owner: user`, `completed_at`.
Append to `.ff/changelog.md`. Append lessons with `actor`. Append one line per
block to `.ff/calibration.jsonl` (`references/executor-calibration.md`).

---

## Interrupt Recovery Hook

1. Read `.ff/state.json`; `owner` says whose turn it is. If it is missing, list `.ff/traces/` and ask which session to resume.
2. Load the last checkpoint from `.ff/traces/{session_id}/`. Never redo what is recorded as approved.
3. If the executor died (dispatch timeout or crash, or the user reports it) while the state still says `owner: executor`, `status: executing`, the planner inspects `git --no-optional-locks log` and `git --no-optional-locks -c core.autocrlf=true status --porcelain`:
   - clean tree → dispatch the block again once (manual fallback: the user runs `/ff exec`); the executor resumes an interrupted run itself (gate B);
   - dirty tree → take the session back (`owner: planner`, `status: blocked`) and run Blocked recovery.
4. Announce: "Resuming FF session {session_id} from {current_phase} (owner: {owner})".

---

## Verification Checklist (before declaring FF done)

- [ ] `state.json`: `status: completed`, `owner: user`, `completed_at` set
- [ ] `report.md` complete; `session.json` completed
- [ ] Every block has `execution/{block_id}.json` and an approved `review/{block_id}.json`
- [ ] `.ff/lessons.json` and `.ff/changelog.md` updated
- [ ] `.ff/calibration.jsonl` has one line per block; `state.json` `cost` filled
