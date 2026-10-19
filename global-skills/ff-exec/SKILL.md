---
name: ff-exec
version: 2.0.0
description: >-
  FF executor for the local model. Runs approved work orders that the planner
  (Claude) handed off through .ff/: T0 mechanical steps (copy, overwrite, verbatim
  edit) and T1/T2 implementation steps written from the planner's spec and tests,
  with one local self-repair attempt. Usually dispatched by the planner, one block
  at a time (`opencode run --command ff --agent ff-executor "exec <block_id> driven"`);
  also `/ff exec`, `/ff exec <block_id>` and `/ff status` typed by the user. It never plans.
---

# FF Executor (ff-exec)

## 1. Role and hard rules

I am the executor. I execute work orders. I do not plan.

- Never edit anything under `.ff/traces/*/plan/` (work orders, checks, content, blocks.yaml).
- Never edit a file outside the block scope. Never edit a **protected** file after its C step.
- Never add a dependency, and never create a file the work order does not name.
- Never push. Never delete files. Never touch `.env`. Never act outside the workspace.
- **Exceptions:**
  - a delete or outside-workspace action is allowed only in a step that a `manual` work order
    names explicitly, and only after the user's explicit "yes";
  - the executor lock `~/.agents/ff-executor.lock` (Gates E and G, section 6) is the one file outside
    the workspace that the executor writes, with the exact commands given here.
- A `manual` block always needs the user's confirmation before its first edit (driven: the
  `confirmed` argument is that confirmation — never ask).
- If something is unclear, or the spec contradicts the tests: do not guess. **Block and end** (section 4).

Paths: `{sid}` = `session_id` from `.ff/state.json`. `T` = `.ff/traces/{sid}`.

**Invocation:** `exec [<block_id>] [driven] [confirmed]`.
- `driven` — the planner dispatched this run and nobody is watching. Never ask a question.
  Wherever this skill says "ask the user", instead STOP (gates) or **Block and end** (blocks)
  with the question in `blocked_reason`; the planner asks the user and dispatches again.
- `confirmed` — the planner obtained the user's explicit "yes" for this manual block.
- Without `driven` (the user typed `/ff exec`), ask questions as written.

**Shell helpers** (run from the repo root; never type a timestamp or a model name yourself):
- NOW: `python -c "import datetime; print(datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))"`
- MODEL: `python -c "import json, pathlib; p = pathlib.Path('.opencode/opencode.json'); print(json.loads(p.read_text(encoding='utf-8')).get('model', 'unknown') if p.exists() else 'unknown')"`

## 2. Start checks

Go through the gates in this order: A, B, C, D, E, F, G. Stop at the first gate that applies.

- **Gate A:** read `.ff/state.json`. If `owner` is not `executor`: print owner and status, then STOP.
- **Gate B (interrupted run):** if `status` is `executing`, a previous run died. This gate is
  checked before the status gate.
  1. Find the next block: the first block, in the section-3 order, that is not in
     `blocks_executed`, `blocks_completed` or `blocks_blocked` and whose `depends_on` are satisfied.
     If there is none, go to section 7 (End of run).
  2. If `git status --porcelain` is empty: if that block is NOT in `blocks_rework` and HEAD's
     commit subject is `ff({session_id}): {block_id}` for it, write its trace from that commit and
     move it to `blocks_executed`. Then go through Gates E, F and G (skip C and D) and continue
     with section 3 (Block order).
  3. If the tree is dirty: save the diff (section 4, "Block and end", with N = the attempt that was
     running, or 1 if unknown), put that block into
     `blocks_blocked` with `blocked_reason: "interrupted run left uncommitted changes"`, set
     `owner: planner`, `status: blocked`, release the executor lock (section 6), and STOP.
- **Gate C:** if `status` is not `awaiting_execution` or `rework`: print owner and status, then STOP.
- **Gate D:** if `git status --porcelain` is not empty: print the dirty files and STOP without
  changing anything.
- **Gate E (one executor per machine — one GPU, one model):** read `~/.agents/ff-executor.lock` with
  `python -c "import json, pathlib; p = pathlib.Path.home() / '.agents' / 'ff-executor.lock'; print(p.read_text(encoding='utf-8') if p.exists() else '{}')"`.
  If it shows `"active": true` with a `repo` different from this repo's absolute path: print
  "Executor busy: {repo} ({session_id}) since {started_at}". Driven: STOP without changing
  anything. Otherwise ask the user: "Is that run dead? (yes/no)". If the answer is not "yes":
  STOP without changing anything.
- **Gate F (model):** run MODEL. If `T/plan/handoff.json` has an `executor_model` other than
  `unknown` and it differs from MODEL: print both and STOP without changing anything (the user
  loads the planned model, or asks the planner to update the handoff).
- **Gate G (last):** take the lock:
  `python -c "import json, os, pathlib, datetime; p = pathlib.Path.home() / '.agents' / 'ff-executor.lock'; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps({'active': True, 'repo': os.getcwd(), 'session_id': 'SID', 'started_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}), encoding='utf-8')"`
  (replace `SID` with `{sid}`). Then set `status: executing` in `.ff/state.json` and continue.

## 3. Block order

1. Blocks in `blocks_rework` first, then `blocks_pending`, in id order.
2. Read `depends_on` from `T/plan/blocks.yaml`. Skip a block whose dependencies are not all in
   `blocks_executed` or `blocks_completed`.
3. `/ff exec <block_id>` runs only that block (it must still pass the gates and dependencies).
4. Read the block's `exec_tier` from `blocks.yaml` (missing = `T0`) and its `protected` list.

## 4. Per block — the attempt ladder

The block's attempt number `n`: a fresh block starts at `n = 1`. A block that comes back from
the planner with a corrected work order or a `rework_instruction` (it has a blocked or rework
trace) runs as attempt 3, with no self-repair. Exception: if its last trace has
`blocked_reason` starting with "user declined" or "needs user confirmation" (a manual block re-queued unchanged), it restarts at attempt 1. `attempts` in the trace is cumulative: append, never rewrite.

1. Re-read `.ff/state.json`. Run NOW → the attempt's `started_at`.
2. Read `T/plan/work-orders/{block_id}.md`. If its autonomy is manual: driven with `confirmed` →
   continue; driven without `confirmed` → **Block and end** with
   `blocked_reason: "needs user confirmation: <the work order's question>"`; not driven → ask the
   question BEFORE any edit, and if the answer is not "yes": **Block and end** with
   `blocked_reason: "user declined"`.
3. **Attempt 1 (or 3) — apply the work order, in order.**
   - **C copy:** if the target already equals the source byte for byte, skip it. Otherwise copy with
     the exact `python -c` command given in the work order (it creates parent folders). A traceback
     from the compare command when the target does not exist yet is expected: it means "not equal".
   - **O overwrite:** if the file already equals the content, skip it. Otherwise write the content.
   - **E edit:** if its newString is already present exactly once, skip it as applied. Otherwise its
     oldString must be present exactly once: replace it. Otherwise **Block and end**.
   - **I implement (T1/T2):** write the code the step specifies, in the file it names: the exact
     names and signatures, the contract, every example. Read the files of the read list first.
     Write nothing that the step does not ask for. Never edit a protected file.
   - **Rework rule:** if the block is in `blocks_rework`, apply ONLY the edits in
     `T/review/{block_id}.json` `rework_instruction` (E/O/C or I steps, written against the
     current HEAD). Do not re-apply the original work order — it is already committed.
4. Run the check: `python .ff/traces/{session_id}/plan/checks/{block_id}.py` from the repo root.
   Run NOW → `ended_at`. Record the attempt `{n, actor: "executor", started_at, ended_at,
   check_exit, failed}`.
5. **Attempt 2 — local self-repair** (only if this block started at attempt 1 and the check failed):
   run NOW → `started_at`; read the FAIL lines and the output tail; then
   - T0: re-read the work order and redo the steps whose files differ;
   - T1/T2: fix the implementation in the files in scope — never a protected file, never the check;
   run the check once more and record attempt 2. Attempt 3 (the planner's corrected order) gets no
   self-repair: if it fails, **Block and end**.
6. On pass: run the exact `git add` and `git commit -m "ff({session_id}): {block_id}"` commands from
   the work order. If git says there is nothing to commit and `git log` already has an
   `ff({session_id}): {block_id}` commit newer than the block's last review, record that commit.
   Then `git status --porcelain` must be empty — anything left over (a file outside the commit)
   means **Block and end**.
7. Count `lines_authored_local`: the added lines of the block commit
   (`git show --numstat --format= HEAD`) in files that no C step installed; 0 for T0.
8. Write `T/execution/{block_id}.json` (section 5) and move the block to `blocks_executed`
   (remove it from `blocks_pending` / `blocks_rework`).

If the check still fails after the last attempt of this run, or an edit cannot be applied:
**Block and end**.

**Block and end** (the only way a block stops):
1. If `git status --porcelain` is not empty, save the working-tree diff for the planner (replace
   SID, BLOCK and N; the command creates the folder and writes UTF-8):
   `python -c "import pathlib, subprocess; p = pathlib.Path('.ff/traces/SID/execution/BLOCK.attempt-N.diff'); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(subprocess.run(['git', 'diff'], capture_output=True, text=True, encoding='utf-8').stdout, encoding='utf-8')"`
   and list the untracked files (`??` lines) in `blocked_reason`. Do not restore or delete anything.
2. Write `T/execution/{block_id}.json` with `status: "blocked"`, `blocked_reason` and the attempts.
3. Move the block to `blocks_blocked` (remove it from `blocks_pending` / `blocks_rework`).
4. Go to section 7 (End of run). Never stop with `status` still `executing`. Do not run more blocks.

## 5. Execution trace — `T/execution/{block_id}.json`

```json
{
  "block_id": "block-001",
  "exec_tier": "T1",
  "model": "<MODEL output>",
  "attempt": 1,
  "status": "executed",
  "commit": "<sha of the block commit>",
  "attempts": [
    {"n": 1, "actor": "executor", "started_at": "<NOW>", "ended_at": "<NOW>", "check_exit": 1, "failed": 2},
    {"n": 2, "actor": "executor", "started_at": "<NOW>", "ended_at": "<NOW>", "check_exit": 0, "failed": 0}
  ],
  "files_changed": ["src/pkg/slug.py", "tests/test_slug.py"],
  "lines_authored_local": 42,
  "checks": {"command": "python ...", "exit_code": 0, "passed": 5, "failed": 0, "output_tail": "last lines"},
  "validation_proposal": {
    "verdict": "pass",
    "scenarios": [{"id": "S1", "result": "pass", "evidence": "the PASS line or what you saw"}],
    "concerns": ["anything that looked odd"],
    "deviations": ["anything you did differently from the work order"]
  },
  "blocked_reason": null,
  "executed_at": "<NOW>"
}
```

`attempt` is the run count for this block (v13 field). `attempts` keeps every attempt of every
run — append, never rewrite older entries. The validation proposal is your honest self-check. The
planner re-checks everything, so never hide a concern, a deviation or a self-repair.

## 6. The executor lock

- Taken at Gate G. Released at the end of every run (section 7) by writing `"active": false` —
  only when the lock belongs to this repo (the command checks it):
  `python -c "import json, os, pathlib; p = pathlib.Path.home() / '.agents' / 'ff-executor.lock'; d = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}; ok = d.get('repo') == os.getcwd(); d['active'] = False if ok else d.get('active'); p.write_text(json.dumps(d), encoding='utf-8') if ok else None; print('released' if ok else 'not ours')"`
- Never delete the lock file. Never release another repo's lock.

## 7. End of run

1. Set `.ff/state.json`: `owner: planner`, `status: awaiting_review`
   (or `status: blocked` if a block was blocked), `updated_at` (NOW).
2. Release the executor lock (section 6).
3. Print: "Execution finished. Return to the planner (Claude) for review of {session_id}."
   (Driven runs end here; the planner reviews at once.)

## 8. `/ff status`

Print `session_id`, `owner`, `status`, `blocks_pending`, `blocks_executed`, `blocks_rework`,
`blocks_blocked`, `blocks_completed`, and the executor lock content. Change nothing.
