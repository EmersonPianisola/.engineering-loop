---
name: ff
version: 13.0.0
description: >-
  Fail Fast (FF), hybrid — the PLANNER side. Claude is the planner: it clarifies
  the request, plans in-session (two separate analysis passes), writes
  executor-grade work orders, Gherkin acceptance and executable checks, gets
  approval from the judge (the only sub-agent, clean view), and hands the session
  off through .ff/ to a local executor model that runs `/ff exec` with the
  ff-exec skill. When the executor returns, the planner runs a critical second
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
| Executor | Local model via opencode (`/ff exec`, skill `ff-exec`) | Phase 2 Execute | Plan, re-scope, edit `plan/` artifacts, push, delete |
| Judge | Sub-agent dispatched by the planner | Approval of plan, work orders, acceptance and checks | Execute anything; see conversation history |

The judge is the ONLY sub-agent. The planner and the executor communicate only
through files in `.ff/`. Every unit of work is atomic, validated in isolation,
and fails fast without contaminating siblings.

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
| A work order that needs judgement or creative writing | Write the content into the work order or split the block |
| Any sub-agent other than the judge | Do the work in-session |
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

Legacy rule: a `state.json` without `owner` is a pre-v13 session. The planner
decides how to continue and never hands off a legacy plan without re-judging it.

### `.ff/traces/{session_id}/`

| Artifact | Writer | Purpose |
|----------|--------|---------|
| `plan/structural.json`, `plan/adversarial.json`, `plan/plan.md` | planner | analysis passes and the plan |
| `plan/blocks.yaml` | planner | block metadata: scope, depends_on, autonomy, contracts |
| `plan/work-orders/{block_id}.md` | planner | executor-grade steps for one block |
| `plan/content/<repo path>` | planner | verbatim file contents used by `copy` steps |
| `plan/acceptance/{block_id}.feature` | planner | Gherkin, end-user perspective |
| `plan/checks/{block_id}.py` | planner | executable form of the feature |
| `plan/judge.json` | judge | approval (earlier rounds: `judge-round-N.json`) |
| `plan/handoff.json` | planner | sha256 of every work order, check, content file and `blocks.yaml` |
| `execution/{block_id}.json` | executor | execution trace + validation proposal |
| `review/{block_id}.json` | planner | verdict of the critical review |
| `report.md` | planner | final report |

`handoff.json`:
```json
{"session_id": "ff-20261010-001", "repo": "<absolute repo path>", "branch": "master",
 "handed_off_at": "ISO date", "sha256": {"plan/blocks.yaml": "...", "plan/work-orders/block-001.md": "...", "plan/checks/block-001.py": "..."}}
```

`execution/{block_id}.json` (written by the executor):
```json
{"block_id": "block-001", "attempt": 1, "status": "executed", "commit": "<sha>",
 "files_changed": ["..."],
 "checks": {"command": "...", "exit_code": 0, "passed": 5, "failed": 0, "output_tail": "..."},
 "validation_proposal": {"verdict": "pass", "scenarios": [{"id": "S1", "result": "pass", "evidence": "..."}],
                         "concerns": [], "deviations": []},
 "blocked_reason": null, "executed_at": "ISO date"}
```

`review/{block_id}.json` (written by the planner):
```json
{"block_id": "block-001", "verdict": "approved", "round": 1,
 "checks_rerun": {"exit_code": 0, "passed": 5, "failed": 0}, "scope_ok": true,
 "proposal_agreement": "agree", "findings": [], "rework_instruction": null, "reviewed_at": "ISO date"}
```
`verdict` is `approved` | `rework` | `escalate`.

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

---

## Protocol Overview

```
PHASE 0: CLARIFY           (planner)  → essence check, scope, work type, skills
PHASE 1: PLAN              (planner)  → structural pass → adversarial pass → plan → blocks
                                        → work orders → acceptance + checks → judge → handoff
PHASE 2: EXECUTE           (executor) → /ff exec: work order → checks → commit → execution trace
PHASE 3: REVIEW & VALIDATE (planner)  → critical review per block → final gate → report
PHASE 4: LESSONS           (planner)  → lessons (actor: planner | executor), changelog
```

Transitions are strict:
- 0 → 1 only after the essence check resolved all tensions.
- 1 → 2 only after the judge returned `{"approved": true}` AND the user said "go".
- 2 → 3 when the executor hands back (`owner: planner`).
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

Write `plan/blocks.yaml`. At most 8 blocks. An executor block hand-edits at most
3 files (files rewritten by a script the work order runs do not count). Two blocks
that write the same file must be dependency-ordered.

```yaml
blocks:
  - id: block-001
    title: "..."
    scope: ["src/a.py"]
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
judgement. Each one has:
- a header with the check command and the files in scope;
- the rules: edit only the scope, never edit `plan/`, never push, never delete, never touch `.env`, and the idempotency rule;
- the edits, in the standard format:
  - `### E<n> — file: \`path\`` + `oldString:` and `newString:` fences (`~~~~`);
  - `### O<n> — overwrite: \`path\`` + one content fence;
  - `### C<n> — copy: \`plan/content/<path>\` → \`<path>\`` — copy a planner-written content file byte for byte (used for large files);
- the check command and the exact `git add` / `git commit -m "ff({session_id}): {block_id}"` commands;
- for `manual` blocks, the question to ask the user BEFORE any edit.

Anything that needs judgement or creative writing is written by the planner into
the work order (or into `plan/content/`), or the block is split.

### Step 1.5: Acceptance + Checks

Specification only — the planner does not execute the work here.
- `plan/acceptance/{block_id}.feature`: Gherkin from the end-user perspective (what the user, planner or executor does and observes). Mandatory coverage: happy path, every relevant adversarial edge case, negative paths. Deterministic outcomes.
- `plan/checks/{block_id}.py`: the executable form. Python standard library only, OS-agnostic, run from the repo root, one `PASS`/`FAIL <scenario-id>` line per scenario, exit 0 only if all pass. Checks are monotonic (still true after later blocks land), side-effect free, discriminating. Append-type edits get checks that assert exactly one occurrence.
- `plan/acceptance-plan.md`: runner, command, scenario counts, edge-case coverage.

**Planner dry-run (before the judge):** apply the executor-grade edits to a
throwaway copy of the repo. Every oldString matches exactly once, every newString
occurs 0 times before its edit, a second application pass changes nothing
(idempotency), and every check goes from FAIL to PASS. Record the result in
`plan/dry-run.txt`.

### Step 1.6: Judge

Dispatch the judge (the only sub-agent) with the Judge Handoff. It verifies:
conflicts resolved; every file has a purpose and an owner; dependencies ordered;
work orders executor-grade; edge cases handled; ≤ 8 blocks; the acceptance gate
(feature per block, end-user level, deterministic, edge cases covered, executable
instructions); the checks gate (1:1 with scenarios, stdlib, discriminating,
monotonic, side-effect free); protocol integrity. Persist `plan/judge.json`
(earlier rounds as `judge-round-N.json`). Rejected → return to the failing step,
then dispatch a fresh judge.

### Step 1.7: Autonomy Score

```
clarity    = available_info / needed_info              (0-1)
complexity = 1 - (dependent_blocks / block_count)      (0-1)
risk       = weighted average of block risk levels     (0-1)
  0.0 read-only · 0.3 create files · 0.5 edit files · 0.7 commands with side effects · 1.0 destructive (always blocked)
autonomy_score = (clarity * 0.4) + (complexity * 0.4) + ((1 - risk) * 0.2)
```
≥ 0.8 full auto · 0.5-0.8 semi auto (show the plan, wait for "go") · < 0.5 manual.

### Step 1.8: Present

After the judge approved: present work type, blocks (scope + summary), scenario
counts, autonomy mode, preconditions and lessons. Wait for the user's "go".

### Step 1.9: Handoff

1. Verify that the tree is clean.
2. Write `plan/handoff.json` (sha256 of every work order, every check, every content file and `blocks.yaml`; repo; branch; timestamp).
3. Set `state.json`: `owner: executor`, `status: awaiting_execution`, `current_phase: "phase_2"`, `blocks_pending` in order.
4. Tell the user exactly: run `/ff exec` in opencode in `<repo path>` (name the repo).

---

## Phase 2: EXECUTE (executor)

Owned by the executor through the `ff-exec` skill (`global-skills/ff-exec/SKILL.md`;
in consumers `.eng/global-skills/ff-exec/SKILL.md`). The planner does not edit
repo files during Phase 2. If the user reports that the executor died, use the
Interrupt Recovery Hook in `harness.md`.

---

## Phase 3: REVIEW & VALIDATE (planner, critical)

Gate: read `manifest.md` (Review Gate). The executor's validation proposal is a
claim, not evidence.

### Step 3.1: Review every executed block

1. Verify the `handoff.json` hashes — the checks and work orders must be the judged ones.
2. Re-run the check yourself.
3. Scope check: `git show --name-only <commit>` (run as `git --no-optional-locks show --name-only <commit>`) ⊆ block scope.
4. Read the full diff against the work order and the feature.
5. Compare with the `validation_proposal`; record `proposal_agreement` (`agree` / `disagree`) and why.
6. Write `review/{block_id}.json` with the verdict.

**Rework:** set `owner: executor`, `status: rework`, block → `blocks_rework`, with
a `rework_instruction` that is executor-grade: the same E/O/C format, with
oldStrings written against the block's COMMITTED state, dry-run by the planner on
a throwaway copy before handing off. The executor applies ONLY the
rework_instruction and never re-applies the original work order. Max 2 rework rounds per block,
then escalate to the user. A rework that needs a plan or scope
change → **re-plan** the affected blocks and dispatch a **fresh judge** before
handing off again.

**Blocked recovery** — a blocked block has no commit and may have left edits in the tree:
- (a) Review `execution/{block_id}.json` (`blocked_reason`, check output), plus `git status --porcelain` and `git diff` of the working tree (run as `git --no-optional-locks -c core.autocrlf=true status --porcelain` and `git --no-optional-locks diff`; not `git show` — there is no commit).
- (b) The USER restores the tree in the Windows shell with the exact commands the planner gives:
  - tracked files that git status shows as modified → `git restore --staged --worktree -- <those files>`;
  - **untracked** files the block created (`??` in git status) → the user deletes them after confirming, with the exact `del <path>` commands the planner gives. Deleting is a user-only action; the planner's VM cannot delete.

  The planner then verifies read-only that `git --no-optional-locks -c core.autocrlf=true status --porcelain` is empty.
- Declined manual block (`blocked_reason` "user declined…") with a clean tree: no restore is needed. Once the user agrees, the unchanged work order goes back to `blocks_pending` (no new judge), or the planner escalates.
- (c) State: the block leaves `blocks_blocked` → `blocks_rework` with a `rework_instruction` (counts toward the 2 rounds), or → `blocks_pending` after a re-plan. Then `owner: executor` and `status: rework` or `awaiting_execution`.
- (d) If a work order or check changes, re-plan the affected blocks, rewrite `handoff.json` with the new sha256 values, and dispatch a fresh judge before the next handoff. An unchanged work order is simply re-queued (no new judge).

**Hand back without a new judge:** after review, if `blocks_pending` is non-empty
and nothing is blocked or in rework, set `owner: executor`, `status:
awaiting_execution`, and tell the user to run `/ff exec` again (for example after a
single-block run).

### Step 3.2: Final gate

When every block is approved:
1. Run every check again, in block order.
2. Run the project test suite (or justify why it does not apply).
3. Cross-check plan vs. commits: each block's commits touch only its scope, and there are no unplanned changes. At least one `ff({session_id}): {block_id}` commit per block; reworks add more under the same subject.
4. `git --no-optional-locks -c core.autocrlf=true status --porcelain` is empty.
5. Write `report.md`: blocks, scenarios passed, files changed, reworks, proposal agreement rate, failures, lessons.

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
(for example: which instructions the local model misreads). Then update
`session.json` (completed), set `state.json` to `status: completed`, `owner: user`,
and append the session to `.ff/changelog.md`.

---

## Multi-project

One active FF session per repo. The protocol is read from the repo being worked
on: `.eng/global-skills/ff/` in consumer projects, `global-skills/ff/` in the
framework repo — never from memory or another repo. Every handoff message names
the repo path.

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

A `manual` block requires the user's confirmation in the executor session. A
delete or outside-workspace action is allowed only in a step that a manual work
order names explicitly, after the user's explicit "yes".

Soft rules: reads, tests and new files are auto; edits to existing files are semi
auto; dependency installs show what will be installed.

---

## Integration

| Skill | When | Purpose |
|-------|------|---------|
| `essence` | Phase 0 | clarify intent |
| testing skills | Step 1.5 | shape acceptance and checks |
| `ff-exec` | Phase 2 (executor) | executor protocol |
| project skills | Phase 0-1 | digested into work orders |

FF does not use Swarm, waves, graphs, or code frameworks for orchestration.

---

## Anti-Patterns

**Do:** fragment aggressively; write acceptance and checks before the judge;
dry-run executor edits; hand off with hashes; re-run every check in review;
capture executor lessons; keep the two analysis passes separate.

**Don't:** create more than 8 blocks; use waves; skip or self-assess the judge;
show the plan before judge approval; dispatch any sub-agent except the judge; edit
repo files during Phase 2; approve from the executor's self-report; hand the
executor a work order that needs judgement; write to `.git` from the planner's VM.
