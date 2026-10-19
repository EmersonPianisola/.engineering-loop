---
name: ff
version: 14.0.0
description: >-
  Fail Fast (FF), hybrid — the PLANNER side. Claude is the planner: it clarifies
  the request, plans in-session (two separate analysis passes), writes
  executor-grade work orders routed by tier (T0 mechanical, T1 guided, T2 high
  effort — the local model writes the code when the spec and tests allow it),
  Gherkin acceptance and executable checks, gets approval from the judge (the only
  Claude sub-agent, clean view) and the user's single "go", then drives the local
  executor model as an external sub-agent: it dispatches each block with
  `opencode run --command ff --agent ff-executor` (skill ff-exec), reviews it as
  soon as it returns, and fails fast. When the executor returns, the planner runs a critical second
  validation and captures lessons. Use when the user says "FF", "fail fast",
  "fragment this", or for multi-file work: bugfix suites, features, refactors,
  test rewrites, migrations, documentation.
---

# FF — Fail Fast Protocol (Planner)

## Core Principle

**One planner. One executor. One judge. Files in between.**

| Role | Who | Owns | Never does |
|------|-----|------|------------|
| Planner | Claude (cloud session linked to the repo) | Phase 0 Clarify, Phase 1 Plan, Phase 3 Review & Validate, Phase 4 Lessons | Edit repo files during Phase 2; trust the executor's self-report |
| Executor | Local model via opencode, dispatched by the planner one block at a time (`opencode run --command ff --agent ff-executor`, skill `ff-exec`) | Phase 2 Execute | Plan, re-scope, edit `plan/` artifacts, push, delete, ask questions when driven |
| Judge | Sub-agent dispatched by the planner | Approval of plan, work orders, acceptance and checks | Execute anything; see conversation history |

The judge is the ONLY Claude sub-agent. The executor is an **external sub-agent**:
a local-model process that the planner dispatches, supervises and reviews. The
planner and the executor communicate only through files in `.ff/` and the dispatch
arguments. Every unit of work is atomic, validated in isolation,
and fails fast without contaminating siblings.

**Cost principle (v14):** the planner specifies and validates; it does not write
what the local model can write. Every block gets an execution tier — T0
mechanical, T1 guided, T2 high effort — chosen with the routing rubric in
`routing.md` (same directory). Read `routing.md` before Step 1.3.

---

## BEFORE ANYTHING ELSE: Read `harness.md`

Before you start or resume a session, transition between phases, hand off, review,
or declare FF complete: read `harness.md` (same directory) and execute the
applicable hook. Then read `.ff/state.json` and check `owner` first. If `owner`
is `executor`, the executor is working: do not touch repo files — report the
status to the user and wait.

---

## Anti-Drift Protocol (MANDATORY)

Before EVERY phase transition and EVERY handoff:
1. Read `harness.md` and execute the hook.
2. Read `manifest.md` — the checklist for the upcoming gate.
3. Assert your role: "I am the planner. I plan and review. I do not execute work orders."
4. Read `.ff/state.json` — confirm position from the file, never from memory.

### Persist Before Handoff

Every artifact is on disk before `owner` changes. `state.json` and the traces are
the authoritative record; a session must be resumable from them alone.

### Drift Symptoms — STOP and re-read this skill

| Symptom | Fix |
|---------|-----|
| Planner editing repo files during Phase 2 | Hand off a work order instead |
| Approving a block from the validation proposal without re-running the check | Re-run the check yourself |
| A work order that needs judgement or creative writing | T1/T2: complete the spec until rubric R1-R7 hold (`routing.md`); otherwise T0 with planner-written content, or split the block |
| Planner pre-writing the code of a T1/T2 block | Trust the spec and tests, or route the block to T0 honestly |
| A 4th judge round | Simplify the plan (lower tiers, fewer blocks) or ask the user |
| A second cloud correction for the same block | Escalate to the user (attempt ladder) |
| Any Claude sub-agent other than the judge | Do the work in-session (the local executor is dispatched, not spawned) |
| Asking the user to run `/ff exec` while the planner has a shell on the machine | Dispatch the block yourself (Phase 2, driven) |
| Dispatching the next block before reviewing the previous one | Review each block as soon as its dispatch returns |
| Judge skipped, self-assessed, or given conversation history | Dispatch a fresh judge with artifacts only |
| Plan shown to the user before the judge approved it | Judge first |
| `state.json` `owner`/`status` not updated at a handoff | Update it now |
| Handoff without `handoff.json` hashes | Write the hashes before handing off |
| Thin judge handoff | Send the full artifact set |
| Lessons not captured (planner or executor) | Append them with `actor` |

---

## Handoff Contract (MANDATORY)

### `.ff/state.json`

- `owner`: `planner` | `executor` | `user` — whose turn it is.
- `status`: `planning` | `awaiting_execution` | `executing` | `awaiting_review` | `rework` | `blocked` | `completed` | `cancelled`.
- Block lists: `blocks_pending`, `blocks_executed` (executed, awaiting review), `blocks_rework`, `blocks_blocked`, `blocks_completed` (approved by the planner).
- Also: `session_id`, `work_type`, `task_title`, `current_phase`, `trace_dir`, `skills`, `tasks`, `autonomy_mode`, `summary`, `decisions`, timestamps.
- `cost` (planner-maintained, v14): `{"judge_rounds": 0, "planner_corrections": 0, "escalations": 0, "lines_local": 0, "lines_planner": 0, "local_authorship_ratio": 0.0}`.

Legacy rule: a `state.json` without `owner` is a pre-v13 session. The planner
decides how to continue and never hands off a legacy plan without re-judging it.
A v13 session (blocks without `exec_tier`) is treated as all-T0; its traces
without `attempts` are valid.

### `.ff/traces/{session_id}/`

| Artifact | Writer | Purpose |
|----------|--------|---------|
| `plan/structural.json`, `plan/adversarial.json`, `plan/plan.md` | planner | analysis passes and the plan |
| `plan/blocks.yaml` | planner | block metadata: exec_tier, rubric, scope, protected, depends_on, autonomy, contracts |
| `plan/work-orders/{block_id}.md` | planner | executor-grade steps for one block |
| `plan/content/<repo path>` | planner | verbatim file contents used by `copy` steps (T0 content; T1/T2 tests) |
| `plan/acceptance/{block_id}.feature` | planner | Gherkin, end-user perspective |
| `plan/checks/{block_id}.py` | planner | executable form of the feature |
| `plan/judge.json` | judge | approval (earlier rounds: `judge-round-N.json`) |
| `plan/handoff.json` | planner | sha256 of every work order, check, content file and `blocks.yaml` |
| `execution/{block_id}.json` | executor | execution trace (attempts, model, lines) + validation proposal |
| `execution/{block_id}.attempt-{n}.diff` | executor | working-tree diff saved when a block is blocked |
| `review/{block_id}.json` | planner | verdict of the critical review |
| `report.md` | planner | final report (with the cost summary) |

Per project, outside the session: `.ff/calibration.jsonl` (planner, Phase 4) —
one line per block for the beta calibration (`references/executor-calibration.md`).

`handoff.json`:
```json
{"session_id": "ff-20261010-001", "repo": "<absolute repo path>", "branch": "master",
 "handed_off_at": "ISO date", "executor_model": "<model of .opencode/opencode.json>",
 "sha256": {"plan/blocks.yaml": "...", "plan/work-orders/block-001.md": "...", "plan/checks/block-001.py": "..."}}
```

`execution/{block_id}.json` (written by the executor):
```json
{"block_id": "block-001", "exec_tier": "T1", "model": "<model of .opencode/opencode.json>",
 "attempt": 1, "status": "executed", "commit": "<sha>",
 "attempts": [{"n": 1, "actor": "executor", "started_at": "ISO", "ended_at": "ISO", "check_exit": 1, "failed": 2},
              {"n": 2, "actor": "executor", "started_at": "ISO", "ended_at": "ISO", "check_exit": 0, "failed": 0}],
 "files_changed": ["..."], "lines_authored_local": 42,
 "checks": {"command": "...", "exit_code": 0, "passed": 5, "failed": 0, "output_tail": "..."},
 "validation_proposal": {"verdict": "pass", "scenarios": [{"id": "S1", "result": "pass", "evidence": "..."}],
                         "concerns": [], "deviations": []},
 "blocked_reason": null, "executed_at": "ISO date"}
```

`attempts` is cumulative across runs (the executor appends; attempt 3 is the
planner's corrected order, run by the executor). Timestamps come from the shell,
never from the model. `lines_authored_local` = added lines in the block's commit
outside the files installed by C steps (0 for T0).

`review/{block_id}.json` (written by the planner):
```json
{"block_id": "block-001", "verdict": "approved", "round": 1,
 "checks_rerun": {"exit_code": 0, "passed": 5, "failed": 0}, "scope_ok": true, "protected_ok": true,
 "proposal_agreement": "agree", "findings": [], "rework_instruction": null,
 "resolved_at_attempt": 2, "planner_authored_lines": 30, "reviewed_at": "ISO date"}
```
`verdict` is `approved` | `rework` | `escalate`. `resolved_at_attempt` is `1` | `2` |
`3` | `"user"`. `planner_authored_lines` = lines of the block's `plan/content/`
files plus the newString/overwrite lines of its work order.

---

## Judge Handoff (MANDATORY)

The judge is the ONLY sub-agent. It gets a **clean view**: artifacts only —
essence, plan, blocks, work orders, content files, acceptance plan, features,
checks, both analyses, filtered lessons and session decisions. It never receives
conversation history; the clean view keeps the decision independent of the work
that built the plan. Every rejection round dispatches a fresh judge. If the
environment cannot spawn the judge: HALT and notify the user — self-assessment is
never a substitute.

Tell the judge that any git command it runs on the user's machine must be
read-only and use `git --no-optional-locks`.

**Minimal view, capped rounds:** the judge gets the session artifacts, `routing.md`
and the Phase 1 gate of `manifest.md` — not the whole protocol. At most **3 judge
rounds** per session; before a 4th, simplify the plan (lower tiers, fewer blocks)
or ask the user. Count rounds in `state.json` `cost.judge_rounds`.

---

## Protocol Overview

```
PHASE 0: CLARIFY           (planner)  → essence check, scope, work type, skills
PHASE 1: PLAN              (planner)  → structural pass → adversarial pass → plan → blocks + tiers
                                        → work orders → acceptance + checks → judge (≤ 3 rounds) → handoff
PHASE 2: EXECUTE           (executor, dispatched by the planner, one block per dispatch)
                                      → work order → check → self-repair (attempt 2) → commit → trace → planner review
PHASE 3: REVIEW & VALIDATE (planner)  → critical review per block → one correction (attempt 3) → final gate → report
PHASE 4: LESSONS           (planner)  → lessons (actor: planner | executor), calibration, changelog
```

Transitions are strict:
- 0 → 1 only after the essence check resolved all tensions.
- 1 → 2 only after the judge returned `{"approved": true}` AND the user said "go" — **one "go" per plan**; after it the planner drives every block (manual blocks still ask the user).
- 2 → 3 per block: each dispatch returns (`owner: planner`) and the planner reviews that block before the next dispatch.
- 3 → 4 only after every block is approved or escalated.

---

## Phase 0: CLARIFY

Assert: "I am the planner." Then initialize the session:

1. `session_id` = `ff-{YYYYMMDD}-{NNN}` (next free number in `.ff/traces/`).
2. Create `.ff/traces/{session_id}/` and write `session.json` (verbatim request, work type, started_at, status).
3. Initialize `.ff/state.json` with the full schema, `owner: planner`, `status: planning`, `current_phase: "phase_0"`.

Run the essence check (skill `essence`); resolve every Lens 4 tension with the
user. Persist it to `essence.md` (request, clarifications, work type, scope).

| Work Type | Characteristics | Blocks |
|-----------|-----------------|--------|
| `bugfix` | Fix broken behavior | 2-4 |
| `feature` | New functionality | 4-6 |
| `refactor` | Restructure without behavior change | 3-5 |
| `test` | Write or fix tests | 2-3 |
| `docs` | Documentation | 1-3 |
| `migration` | Move code, update deps | 3-5 |
| `research` | Investigation, report | 1-2 |

**Auto-size rule:** ≤ 2 files with clear instructions → do it inline without FF.
FF activates at ≥ 3 files, ≥ 5 discrete changes, unclear dependencies, or when the
user asks for FF.

### Step 0.2: Skill Discovery

Pick the skills that apply and record them in `state.json` `skills` and in
`skills.md` (name + reason). The planner loads them and digests their rules into
the work orders — the executor receives conventions as concrete steps, not skill
names.

| Signal | Skill |
|--------|-------|
| bugfix | `bug-analysis` |
| test work | `comprehensive-test-strategy` |
| migration, deploy | `release-deployment-safety` |
| `*.py`, FastAPI, pydantic | `python-fastapi-coding-conventions` |
| tests, conftest | `python-fastapi-test-conventions` |
| auth, tokens, secrets | `owasp-secure-coding-bdd` |
| `*.ts`, React, Next.js | `nextjs` |
| prisma | `prisma-client-api` |
| LangChain / LangGraph | `ecosystem-primer` (+ specific skill) |
| MCP servers | `mcp-builder` |
| API design | `api-designer` |
| database schema | `database-design` |

Honor skill mappings in the project's `AGENTS.md`.

---

## Phase 1: PLAN (in-session, planner)

Gate: read `manifest.md` (Phase 0 → 1). Everything in this phase happens in the
planner session; only Step 1.6 dispatches a sub-agent.

### Step 1.1: Analysis Passes

Two SEPARATE passes, in order:
- **Structural pass** — files to change and why, imports/exports, dependencies, shared state, external writes, risk, conventions.
- **Adversarial pass** — re-examines the structural findings: alternative approaches, edge cases, hidden dependencies, ignored risks, worst case.

Persist `plan/structural.json` and `plan/adversarial.json`.

### Step 1.2: Plan

Reconcile the passes (an item one pass calls safe and the other risky is
unresolved → redo the failing pass). Write `plan/plan.md`: Scope, Approach (with
alternatives), Files Affected, Dependencies, Detailed Tasks, Risks and Mitigations,
Validation, Edge Cases Handled, Skills Used.

### Step 1.3: Fragment

Read `routing.md`. Write `plan/blocks.yaml`. At most 8 blocks. An executor block
hand-edits at most 3 files (files rewritten by a script the work order runs do not
count). Two blocks that write the same file must be dependency-ordered. Every block
gets an `exec_tier` from the routing rubric; record which rubric ids hold. Prefer
the highest tier the rubric allows — that is where the cloud savings are — and
respect the tier size limits. "Allows" means every criterion clearly holds; if one
is doubtful it does not hold, and the lower tier applies (`routing.md`). The
block's `scope` includes its protected files (the commit adds them).

```yaml
blocks:
  - id: block-001
    title: "..."
    exec_tier: "T1"         # T0 mechanical | T1 guided | T2 high effort (routing.md)
    rubric: [R1, R2, R3, R4, R5, R6, R7]   # ids that hold; T1/T2 need all
    scope: ["src/a.py", "tests/test_a.py"]
    protected: ["tests/test_a.py"]          # installed by C steps; never edited by the executor afterwards
    instruction: "multi-line summary of what the work order does"
    contracts: {consumes: [], produces: ["..."]}
    acceptance: acceptance/block-001.feature
    checks: checks/block-001.py
    autonomy: "semi"        # auto | semi | manual
    depends_on: []
    tasks: [t101]
```

### Step 1.4: Work Orders

Write `plan/work-orders/{block_id}.md` for every block. Work orders are
**executor-grade**: written so a small local model can apply them without
judgement — T0 by giving every byte, T1/T2 by giving a complete spec and the tests
(templates in `routing.md` section 4). Each one has:
- a header with the tier, the check command, the files in scope, the protected files and (T1/T2) the read list;
- the rules: edit only the scope, never edit `plan/`, never push, never delete, never touch `.env`, and the idempotency rule;
- the edits, in the standard format:
  - `### E<n> — file: \`path\`` + `oldString:` and `newString:` fences (`~~~~`);
  - `### O<n> — overwrite: \`path\`` + one content fence;
  - `### C<n> — copy: \`plan/content/<path>\` → \`<path>\`` — copy a planner-written content file byte for byte (used for large files and for T1/T2 tests);
  - T1/T2 only: `### I<n> — implement: \`path\`` with goal, signature, contract, examples and "do not" — the executor writes this code;
- the check command and the exact `git add` / `git commit -m "ff({session_id}): {block_id}"` commands;
- for `manual` blocks, the question to ask the user BEFORE any edit.

Anything that needs judgement or creative writing is decided by the planner: in a
T1/T2 spec (names, signatures, contracts, examples) or, for T0, written into the
work order or `plan/content/` — or the block is split. Never hand the executor a
choice of design, library, path or symbol.

### Step 1.5: Acceptance + Checks

Specification only — the planner does not execute the work here.
- `plan/acceptance/{block_id}.feature`: Gherkin from the end-user perspective (what the user, planner or executor does and observes). Mandatory coverage: happy path, every relevant adversarial edge case, negative paths. Deterministic outcomes.
- `plan/checks/{block_id}.py`: the executable form. Python standard library only, OS-agnostic, run from the repo root, one `PASS`/`FAIL <scenario-id>` line per scenario, exit 0 only if all pass. Checks are monotonic (still true after later blocks land), side-effect free, discriminating. Append-type edits get checks that assert exactly one occurrence.
- `plan/acceptance-plan.md`: runner, command, scenario counts, edge-case coverage.

For T1/T2 blocks the check also runs the planner's tests and asserts that every
protected file still equals its `plan/content/` source (line endings normalized).

**Planner dry-run (before the judge), recorded in `plan/dry-run.txt`:**
- T0: apply the executor-grade edits to a throwaway copy of the repo. Every
  oldString matches exactly once, every newString occurs 0 times before its edit, a
  second application pass changes nothing (idempotency), and every check goes from
  FAIL to PASS.
- T1/T2: apply the C steps (tests) on a throwaway copy and run the check: it must
  FAIL for the expected reason (red), with the failing scenario ids recorded. Do not
  write the implementation for the dry-run.

### Step 1.6: Judge

Dispatch the judge (the only sub-agent) with the Judge Handoff. It verifies:
conflicts resolved; every file has a purpose and an owner; dependencies ordered;
work orders executor-grade; tiers justified by the rubric (T1/T2: all of R1-R7,
size limits, tests satisfiable by the spec, protected files); edge cases handled; ≤ 8 blocks; the acceptance gate
(feature per block, end-user level, deterministic, edge cases covered, executable
instructions); the checks gate (1:1 with scenarios, stdlib, discriminating,
monotonic, side-effect free); protocol integrity. Persist `plan/judge.json`
(earlier rounds as `judge-round-N.json`). Rejected → return to the failing step,
then dispatch a fresh judge — at most 3 rounds per session (Judge Handoff).

### Step 1.7: Autonomy Score

```
clarity    = available_info / needed_info              (0-1)
complexity = 1 - (dependent_blocks / block_count)      (0-1)
risk       = weighted average of block risk levels     (0-1)
  0.0 read-only · 0.3 create files · 0.5 edit files · 0.7 commands with side effects · 1.0 destructive (always blocked)
autonomy_score = (clarity * 0.4) + (complexity * 0.4) + ((1 - risk) * 0.2)
```
Informational since v14 (risk summary in the plan presentation): dispatching is
governed by **one "go" per plan**, whatever the score. Manual blocks always ask the
user before their dispatch.

### Step 1.8: Present

After the judge approved: present work type, blocks (tier + scope + summary), scenario
counts, autonomy score (informational), manual blocks, preconditions and lessons. Wait
for the user's single "go" for the whole plan.

### Step 1.9: Handoff and dispatch

1. Verify that the tree is clean.
2. Write `plan/handoff.json` (sha256 of every work order, every check, every content file and `blocks.yaml`; repo; branch; timestamp; `executor_model` = the `model` of the project's `.opencode/opencode.json`, or `"unknown"`).
3. Set `state.json`: `owner: executor`, `status: awaiting_execution`, `current_phase: "phase_2"`, `blocks_pending` in order.
4. Start Phase 2 in driven mode: the planner dispatches the blocks itself.
   **Manual fallback** — only when the planner has no shell on the executor's machine
   (e.g., a cloud session): tell the user exactly to run `/ff exec` in opencode in
   `<repo path>` (name the repo) and review when it returns.

---

## Phase 2: EXECUTE (executor, driven by the planner)

The executor follows the `ff-exec` skill (`global-skills/ff-exec/SKILL.md`; in
consumers `.eng/global-skills/ff-exec/SKILL.md`) through the opencode agent
`.opencode/agents/ff-executor.md` (permissions deny push, reset, checkout/restore,
deletes and web access). The planner drives it as an external sub-agent, **one block
per dispatch**, in block order (rework first), and never edits repo files during
Phase 2.

Per block:
1. **Pre-dispatch:** `state.json` `owner: executor`, the block in `blocks_pending`
   or `blocks_rework`. Read `~/.agents/ff-executor.lock`: if another repo's run is
   active (one GPU), wait for it and tell the user.
2. **Manual block:** ask the user the work order's question first. Only after an
   explicit "yes" add `confirmed` to the dispatch arguments. Any other answer: the
   block stays pending; ask how to continue.
3. **Dispatch** from the repo root, in the background, with a wall-clock limit (beta:
   T0 20 min, T1 40 min, T2 60 min):
   `opencode run --command ff --agent ff-executor --dir <repo> --format json --title "ff <sid> <block_id>" "exec <block_id> driven"`
   (`"exec <block_id> driven confirmed"` for a confirmed manual block) (no `-m`: the model is the `model` of the project's `.opencode/opencode.json`, the one Gate F compares with `handoff.json` `executor_model` and the trace records). Save the JSON
   event stream to `execution/{block_id}.events.jsonl` (token usage for calibration).
4. **On return:** read `state.json` and `execution/{block_id}.json`, then run the
   Phase 3 review of that block at once (fail fast). Approved → dispatch the next
   block. Blocked or rework → the attempt ladder (attempt 3 = one corrected
   dispatch), then the user.
5. **Timeout or crash:** stop the process, then the Interrupt Recovery Hook
   (`harness.md`): clean tree → dispatch the block once more (ff-exec Gate B
   resumes it); dirty tree → Blocked recovery. A second timeout → escalate to the
   user. A killed run leaves this repo's executor lock `active`: it does not block
   this repo (the next run here takes it over and releases it at End of run), but
   other repos wait — tell the user when you stop driving this repo with the lock
   still active.

A driven executor never asks questions: anything that needs the user makes it block
and return with the question in `blocked_reason`; the planner asks the user.

**Manual fallback:** without a shell on the executor's machine, hand off and tell the
user to run `/ff exec` in opencode in `<repo path>`; review when it returns.

---

## Phase 3: REVIEW & VALIDATE (planner, critical)

Gate: read `manifest.md` (Review Gate). The executor's validation proposal is a
claim, not evidence.

### Step 3.1: Review every executed block

1. Verify the `handoff.json` hashes — the checks and work orders must be the judged ones.
2. Re-run the check yourself.
3. Scope check: `git show --name-only <commit>` (run as `git --no-optional-locks show --name-only <commit>`) ⊆ block scope; protected files equal their `plan/content/` source (`protected_ok`).
4. Read the full diff against the work order and the feature.
5. Compare with the `validation_proposal`; record `proposal_agreement` (`agree` / `disagree`) and why.
6. Record `resolved_at_attempt` and `planner_authored_lines`; add the block's `lines_authored_local` and planner lines to `state.json` `cost`.
7. Write `review/{block_id}.json` with the verdict.

**Attempt ladder (v14 — replaces "rework ×2"):** attempts 1 and 2 are the
executor's (attempt 2 = local self-repair with the check output). **Attempt 3 is
the planner's single correction:** diagnose from the trace, the saved diff
(`execution/{block_id}.attempt-{n}.diff`) and the check output, then re-dispatch
ONE corrected order — a `rework_instruction` (committed block) or a corrected work
order (blocked block). It may downgrade the tier (T2 → T1 → T0 with the content
written). Attempt 3 still failing, or a correction that would need a second cloud
round → `escalate`: give the user the evidence and 2-3 options, and count it in
`cost.escalations`. Count every correction in `cost.planner_corrections`.

**Rework:** set `owner: executor`, `status: rework`, block → `blocks_rework`, with
a `rework_instruction` that is executor-grade: the same E/O/C format (or an I step
for T1/T2 with the corrected spec), with oldStrings written against the block's
COMMITTED state, dry-run by the planner on a throwaway copy before handing off.
The executor applies ONLY the rework_instruction and never re-applies the original
work order. A rework is the block's attempt 3 (one per block), then escalate to
the user. A rework or corrected work order that keeps the block's scope and
acceptance needs no fresh judge (planner dry-run + new `handoff.json` hashes); one
that needs a plan, scope or acceptance change → **re-plan** the affected blocks and
dispatch a **fresh judge** before handing off again.

**Blocked recovery** — a blocked block has no commit and may have left edits in the tree:
- (a) Review `execution/{block_id}.json` (`blocked_reason`, check output), plus `git status --porcelain` and `git diff` of the working tree (run as `git --no-optional-locks -c core.autocrlf=true status --porcelain` and `git --no-optional-locks diff`; not `git show` — there is no commit).
- (b) The USER restores the tree in the Windows shell with the exact commands the planner gives:
  - tracked files that git status shows as modified → `git restore --staged --worktree -- <those files>`;
  - **untracked** files the block created (`??` in git status) → the user deletes them after confirming, with the exact `del <path>` commands the planner gives. Deleting is a user-only action; the planner's VM cannot delete.

  The planner then verifies read-only that `git --no-optional-locks -c core.autocrlf=true status --porcelain` is empty.
- Declined manual block (`blocked_reason` "user declined…") with a clean tree: no restore is needed. Once the user agrees, the unchanged work order goes back to `blocks_pending` (no new judge), or the planner escalates.
- (c) State: the block leaves `blocks_blocked` → `blocks_pending` with its corrected work order (attempt 3), or → `blocks_rework` with a `rework_instruction`. Then `owner: executor` and `status: awaiting_execution` or `rework`.
- (d) A corrected work order with the same scope and acceptance: planner dry-run, rewrite `handoff.json` with the new sha256 values, no fresh judge. A changed scope, acceptance or check: re-plan the affected blocks, new `handoff.json`, fresh judge. An unchanged work order (e.g. a declined manual block) is simply re-queued.

**Continue without a new judge:** after review, if `blocks_pending` is non-empty
and nothing is blocked or in rework, set `owner: executor`, `status:
awaiting_execution`, and dispatch the next block (manual fallback: tell the user to
run `/ff exec` again).

### Step 3.2: Final gate

When every block is approved:
1. Run every check again, in block order.
2. Run the project test suite (or justify why it does not apply).
3. Cross-check plan vs. commits: each block's commits touch only its scope, and there are no unplanned changes. At least one `ff({session_id}): {block_id}` commit per block; reworks add more under the same subject.
4. `git --no-optional-locks -c core.autocrlf=true status --porcelain` is empty.
5. Write `report.md`: blocks (with tier and `resolved_at_attempt`), scenarios passed, files changed, corrections, proposal agreement rate, failures, lessons, and the cost summary (`state.json` `cost`, `local_authorship_ratio`).

### Planner git on the user's machine is read-only

When the planner reaches the repo through the linked computer's VM, every git
command it runs is read-only and uses `git --no-optional-locks` (status also with
`-c core.autocrlf=true`, to see what the user's Windows git sees). Never run `add`,
`commit`, `update-index`, `restore` or `checkout` from the VM. Those take
`.git/index.lock`, which the VM cannot remove, and a leftover lock blocks the
user's next commit. Commits are made by the executor (or by the user).

---

## Phase 4: LESSONS (planner)

For every failure, rework, blocked block or proposal disagreement, append a lesson
to `.ff/lessons.json`:
```json
{"id": "lesson-N", "timestamp": "ISO date", "work_type": "refactor", "actor": "executor",
 "context": "...", "error": "...", "correction": "...", "prevention": "..."}
```
`actor` is `planner` | `executor`. Executor lessons shape future work orders
(for example: which instructions the local model misreads).

**Calibration (beta):** append one line per block to `.ff/calibration.jsonl`
(schema and aggregation rule in `references/executor-calibration.md`: tier, task
kind, model, `resolved_at_attempt`, lines, wall time). These lines decide when the
rubric and the tier size limits change. Then update
`session.json` (completed), set `state.json` to `status: completed`, `owner: user`,
and append the session to `.ff/changelog.md`.

---

## Multi-project

One active FF session per repo. The protocol is read from the repo being worked
on: `.eng/global-skills/ff/` in consumer projects, `global-skills/ff/` in the
framework repo — never from memory or another repo. Every handoff message names
the repo path.

One local GPU runs one model at a time, so **execution is serial across repos**:
the planner may plan several repos in parallel, but dispatches one executor run at a
time. The executor enforces it with the machine-wide lock
`~/.agents/ff-executor.lock` (ff-exec Gates E and G).

---

## Autonomy Harness

Always active (details in `autonomy-harness.md`). Hard rules — always ask the user,
whatever the score, for both roles:
- `rm`, `rm -rf`, `del`, any destructive file operation
- `git push --force`, `git reset --hard`, any destructive git operation; any `git push`
- writes to Firebase / external databases / remote APIs
- changes to `.env` or environment configuration
- changes to CI/CD or deployment configs
- any operation outside the workspace root

A `manual` block requires the user's confirmation: in driven mode the planner asks
the user and passes `confirmed` in the dispatch; in the manual fallback the executor
asks. A delete or outside-workspace action is allowed only in a step that a manual
work order names explicitly, after the user's explicit "yes" (the driven agent's
permissions deny shell deletes — such steps go to the user).
Exception: the FF executor writes (never deletes) `~/.agents/ff-executor.lock` with the exact ff-exec section 6 commands.

Soft rules: reads, tests and new files are auto; edits to existing files are semi
auto; dependency installs show what will be installed.

---

## Integration

| Skill | When | Purpose |
|-------|------|---------|
| `essence` | Phase 0 | clarify intent |
| testing skills | Step 1.5 | shape acceptance and checks |
| `ff-exec` | Phase 2 (executor) | executor protocol |
| `routing.md` | Steps 1.3-1.6, Phase 3 | tiers, rubric, T1/T2 templates, attempt ladder |
| `.opencode/agents/ff-executor.md` | Phase 2 | the opencode agent the planner dispatches (permissions) |
| project skills | Phase 0-1 | digested into work orders |

FF does not use Swarm, waves, graphs, or code frameworks for orchestration.

---

## Anti-Patterns

**Do:** fragment aggressively; route every block by the rubric and prefer the
highest eligible tier; write acceptance, checks and T1/T2 tests before the judge;
dry-run executor edits (red before green for T1/T2); hand off with hashes; re-run
every check in review; capture executor lessons and calibration lines; keep the two
analysis passes separate.

**Don't:** create more than 8 blocks; run more than 3 judge rounds without the user;
spend more than one cloud correction per block; pre-write T1/T2 code; dispatch a block
before reviewing the previous one; ask the user to run `/ff exec` when you can dispatch; use waves; skip or self-assess the judge;
show the plan before judge approval; dispatch any sub-agent except the judge; edit
repo files during Phase 2; approve from the executor's self-report; hand the
executor a work order that needs judgement; write to `.git` from the planner's VM.
