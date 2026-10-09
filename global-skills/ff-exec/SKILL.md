---
name: ff-exec
version: 1.0.0
description: >-
  FF executor for the local model. Runs approved work orders that the planner
  (Claude) handed off through .ff/. Use it on `/ff exec` or `/ff exec <block_id>`,
  and on `/ff status`. It never plans.
---

# FF Executor (ff-exec)

## 1. Role and hard rules

I am the executor. I execute work orders. I do not plan.

- Never edit anything under `.ff/traces/*/plan/` (work orders, checks, content, blocks.yaml).
- Never edit a file outside the block scope.
- Never push. Never delete files. Never touch `.env`. Never act outside the workspace.
- **The only exception:** a delete or outside-workspace action is allowed only in a step
  that a `manual` work order names explicitly, and only after the user's explicit "yes".
- A `manual` block always needs the user's confirmation before its first edit.
- If something is unclear: do not guess. **Block and end** (section 4).

Paths: `{sid}` = `session_id` from `.ff/state.json`. `T` = `.ff/traces/{sid}`.

## 2. Start checks

Go through the gates in order. Stop at the first gate that applies.

- **Gate A:** read `.ff/state.json`. If `owner` is not `executor`: print owner and status, then STOP.
- **Gate B (interrupted run):** if `status` is `executing`, a previous run died. This gate is
  checked before the status gate.
  1. Find the next block: the first block, in the step-3 order, that is not in
     `blocks_executed`, `blocks_completed` or `blocks_blocked` and whose `depends_on` are satisfied.
     If there is none, go to step 6 (End of run).
  2. If `git status --porcelain` is empty: if that block is NOT in `blocks_rework` and HEAD's
     commit subject is `ff({session_id}): {block_id}` for it, write its trace from that commit and
     move it to `blocks_executed`. Then continue with section 3 (Block order).
  3. If the tree is dirty: put that block into `blocks_blocked` with
     `blocked_reason: "interrupted run left uncommitted changes"`, set `owner: planner`,
     `status: blocked`, and STOP.
- **Gate C:** if `status` is not `awaiting_execution` or `rework`: print owner and status, then STOP.
- **Gate D:** if `git status --porcelain` is not empty: print the dirty files and STOP without
  changing anything.
- **Gate E:** set `status: executing` in `.ff/state.json` and continue.

## 3. Block order

1. Blocks in `blocks_rework` first, then `blocks_pending`, in id order.
2. Read `depends_on` from `T/plan/blocks.yaml`. Skip a block whose dependencies are not all in
   `blocks_executed` or `blocks_completed`.
3. `/ff exec <block_id>` runs only that block (it must still pass the gates and dependencies).

## 4. Per block

1. Re-read `.ff/state.json`.
2. Read `T/plan/work-orders/{block_id}.md`. If its autonomy is manual, ask the question it gives
   BEFORE any edit. If the answer is not "yes": **Block and end** with `blocked_reason: "user declined"`.
3. Apply the edits exactly, in order.
   **Rework rule:** if the block is in `blocks_rework`, apply ONLY the edits in
   `T/review/{block_id}.json` `rework_instruction` (same E/O/C format, written against the current
   HEAD). Do not re-apply the original work order edits — they are already committed.
   The trace gets `attempt` + 1.
4. **Idempotency rule (every attempt, rework included):**
   - E edit: if its newString is already present exactly once, skip it as applied. Otherwise its
     oldString must be present exactly once: replace it. Otherwise **Block and end**.
   - O overwrite: if the file already equals the content, skip it. Otherwise write the content.
   - C copy: if the target already equals the source byte for byte, skip it. Otherwise copy with the
     exact `python -c` command given in the work order (it creates parent folders). A traceback from the
     compare command when the target does not exist yet is expected: it means "not equal".
5. Run the check: `python .ff/traces/{session_id}/plan/checks/{block_id}.py` from the repo root.
6. If it fails: re-read the work order (on rework: the `rework_instruction`), fix what differs,
   and run the check once more. One retry only.
7. On pass: run the exact `git add` and `git commit -m "ff({session_id}): {block_id}"` commands from the work order.
   If git says there is nothing to commit and `git log` already has an
   `ff({session_id}): {block_id}` commit newer than the block's last review, record that commit.
8. Write `T/execution/{block_id}.json` (schema in section 5) and move the block to
   `blocks_executed` (remove it from `blocks_pending` / `blocks_rework`).

If the check still fails after the retry, or an edit cannot be applied: **Block and end**.

**Block and end** (the only way a block stops): write `T/execution/{block_id}.json` with
`status: "blocked"` and `blocked_reason`; move the block to `blocks_blocked` (remove it from
`blocks_pending` / `blocks_rework`); then go to section 6 (End of run). Never stop with `status`
still `executing`. Do not run more blocks.

## 5. Execution trace — `T/execution/{block_id}.json`

```json
{
  "block_id": "block-001",
  "attempt": 1,
  "status": "executed",
  "commit": "<sha of the block commit>",
  "files_changed": ["path/a.md"],
  "checks": {"command": "python ...", "exit_code": 0, "passed": 5, "failed": 0, "output_tail": "last lines"},
  "validation_proposal": {
    "verdict": "pass",
    "scenarios": [{"id": "S1", "result": "pass", "evidence": "the PASS line or what you saw"}],
    "concerns": ["anything that looked odd"],
    "deviations": ["anything you did differently from the work order"]
  },
  "blocked_reason": null,
  "executed_at": "ISO date"
}
```

The validation proposal is your honest self-check. The planner re-checks everything,
so never hide a concern or a deviation.

## 6. End of run

1. Set `.ff/state.json`: `owner: planner`, `status: awaiting_review`
   (or `status: blocked` if a block was blocked), `updated_at`.
2. Print: "Execution finished. Return to the planner (Claude) for review of {session_id}."

## 7. `/ff status`

Print `session_id`, `owner`, `status`, `blocks_pending`, `blocks_executed`, `blocks_rework`,
`blocks_blocked`, `blocks_completed`. Change nothing.
