# FF Protocol Harness — Hooks (v13, hybrid)

**READ THIS BEFORE ANY OTHER FF FILE.** These hooks are the mechanical guardrail
against drift. They are not optional.

---

## Pre-Hook (before any phase, handoff or review)

1. **Read state:** `.ff/state.json`.
   - Missing → planner: new session (Phase 0).
   - `status` is `completed` or `cancelled` → planner: new session.
   - Branch on `owner`:
     - `planner` → planner flow (continue at `current_phase`).
     - `executor` → if you are the planner: the executor is working; report the status to the user and wait. If you are the executor: follow `ff-exec` (gates A-E).
     - `user` → the session is closed; the planner starts a new one when asked.
     - no `owner` field → **legacy** (pre-v13) session: the planner decides how to continue and re-judges before any handoff.
2. **Read** `manifest.md` — the checklist for the upcoming gate.
3. **Read** `.ff/lessons.json` (planner) — note prevention rules for this work type, including executor lessons.
4. **Assert role:** planner: "FF session initialized. I am the planner." Executor: "I am the executor."

---

## Phase 0 → 1 Post-Hook (planner)

Write `state.json` (`current_phase: "phase_0"`, `owner: planner`, `status: planning`,
`work_type`, `task_title`, `skills`, `updated_at`), `skills.md` and `essence.md`.

---

## Handoff Hook (planner, end of Phase 1)

1. Verify that these exist: `plan/structural.json`, `plan/adversarial.json`, `plan/plan.md`, `plan/blocks.yaml`, `plan/work-orders/{block_id}.md`, `plan/acceptance-plan.md`, `plan/acceptance/{block_id}.feature`, `plan/checks/{block_id}.py` (every block), `plan/dry-run.txt`, and `plan/judge.json` with `approved: true`.
2. Verify that the user said "go" and the tree is clean.
3. Write `plan/handoff.json` (sha256 of every work order, check, content file and `blocks.yaml`).
4. Set `state.json`: `owner: executor`, `status: awaiting_execution`, `current_phase: "phase_2"`, `blocks_pending`.
5. Tell the user: run `/ff exec` in opencode in `<repo path>`.

If anything is missing: do not hand off.

---

## Execution Hook (executor, per block — details in ff-exec)

After each block: write `execution/{block_id}.json` and move the block to
`blocks_executed` (or `blocks_blocked`). At the end of the run: `owner: planner`,
`status: awaiting_review` (or `blocked`).

---

## Review Hook (planner, per block)

1. Verify the `handoff.json` hashes, re-run the check, check the scope with `git --no-optional-locks show --name-only`, read the full diff, record the proposal agreement.
2. Write `review/{block_id}.json` and update the lists:
   - approved → `blocks_completed`;
   - rework → `blocks_rework`, executor-grade `rework_instruction` (dry-run first), `owner: executor`, `status: rework`;
   - escalate → ask the user.
3. For blocks in `blocks_blocked`, apply **Blocked recovery** (SKILL.md Phase 3):
   - review the working-tree `git --no-optional-locks diff`;
   - the USER runs `git restore --staged --worktree -- <modified tracked files>`;
   - the USER deletes **untracked** files the block created, with the exact `del <path>` commands the planner gives;
   - the planner verifies a clean tree (`git --no-optional-locks -c core.autocrlf=true status --porcelain`);
   - then `blocks_rework`, or a re-plan with a new `handoff.json` and a fresh judge.
4. Pending blocks left and nothing blocked or in rework → hand back (`owner: executor`, `status: awaiting_execution`) with no new judge.

Planner git on the VM is read-only (`git --no-optional-locks`): never `add`, `commit`,
`update-index`, `restore` or `checkout` from the VM.

---

## Completion Post-Hook (planner)

Write `report.md`. Update `session.json` (`status: completed`, `completed_at`,
files). Set `state.json` to `status: completed`, `owner: user`, `completed_at`.
Append to `.ff/changelog.md`. Append lessons with `actor`.

---

## Interrupt Recovery Hook

1. Read `.ff/state.json`; `owner` says whose turn it is. If it is missing, list `.ff/traces/` and ask which session to resume.
2. Load the last checkpoint from `.ff/traces/{session_id}/`. Never redo what is recorded as approved.
3. If the user reports that the executor died while the state still says `owner: executor`, `status: executing`, the planner inspects `git --no-optional-locks log` and `git --no-optional-locks -c core.autocrlf=true status --porcelain`:
   - clean tree → tell the user to run `/ff exec` again (the executor resumes an interrupted run itself, gate B);
   - dirty tree → take the session back (`owner: planner`, `status: blocked`) and run Blocked recovery.
4. Announce: "Resuming FF session {session_id} from {current_phase} (owner: {owner})".

---

## Verification Checklist (before declaring FF done)

- [ ] `state.json`: `status: completed`, `owner: user`, `completed_at` set
- [ ] `report.md` complete; `session.json` completed
- [ ] Every block has `execution/{block_id}.json` and an approved `review/{block_id}.json`
- [ ] `.ff/lessons.json` and `.ff/changelog.md` updated
