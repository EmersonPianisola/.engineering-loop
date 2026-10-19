# FF Protocol — Changelog

All notable changes to the FF protocol.

## v14.0.0 — Tiered Routing: Cloud Planner Specifies, Local Executor Writes (2026-10-18)

### New

- **Execution tiers per block** (`global-skills/ff/routing.md`, new): **T0 mechanical** (copy / overwrite / verbatim edit — v13 behavior), **T1 guided** (the local model writes one bounded implementation from the planner's spec and tests) and **T2 high effort** (same, up to 3 files with ordered steps). `blocks.yaml` gains `exec_tier`, `rubric` and `protected`.
- **Routing rubric R1-R7** — T1/T2 only when every path and symbol is named, planner-written tests define "done" and fail first (red), there is no design decision or new dependency, no long prose, a read list and the tier size limits, and no free-form JSON to parse. Otherwise T0 or inline. Evidence: v13 local runs (8/8 T0 blocks) and the loop-motor era failure modes (hallucinated paths > 60%, schema drift, stalls).
- **I steps** (`### I<n> — implement:`) in T1/T2 work orders: goal, signature, contract, examples, "do not". Tests are installed by C steps and are **protected** (never edited by the executor; the check asserts it).
- **Attempt ladder** (replaces "retry once → blocked → rework ×2 → user"): attempts 1-2 local (attempt 2 = self-repair with the check output), attempt 3 = the planner's single correction (may downgrade the tier; same scope and acceptance → no fresh judge), then the user decides.
- **Telemetry** — execution traces gain `exec_tier`, `model`, cumulative `attempts` with shell timestamps, `lines_authored_local`, and a saved `attempt-{n}.diff` when blocked; reviews gain `resolved_at_attempt`, `planner_authored_lines`, `protected_ok`; `state.json` gains `cost` (judge rounds, corrections, escalations, `local_authorship_ratio`); `handoff.json` gains `executor_model`.
- **Beta calibration** — `.ff/calibration.jsonl` (one line per block, Phase 4) and `references/executor-calibration.md` (new): schema, aggregation after ≥ 30 T1/T2 blocks, decision rules for promoting/demoting task kinds between tiers and for comparing local models.
- **Claude drives the local executor as an external sub-agent** — after the user's single "go" per plan, the planner dispatches each block with `opencode run --command ff --agent ff-executor --format json "exec <block_id> driven"`, supervises it with a wall-clock limit (beta: T0 20 / T1 40 / T2 60 min), saves the event stream (`execution/{block_id}.events.jsonl`, token usage) and reviews the block before the next dispatch. A driven executor never asks questions; manual blocks are confirmed by the user through the planner (`confirmed`). Manual fallback `/ff exec` when the planner has no shell on the machine.
- **opencode agent `.opencode/agents/ff-executor.md`** (new, tracked): temperature 0; permissions deny the `question` tool (a non-interactive run can never hang on a question), sub-agent `task`s, `git push`/`reset`/`checkout`/`restore`/`clean`/`rebase`/`rm`/`stash`/`--amend`, shell deletes, web access and doom loops. `/ff` now runs on this agent; `scripts/propagate-to-projects.py` copies it to consumer projects (`sync_opencode_files`), `.gitignore` keeps `.opencode/agents/` tracked.
- **One executor per machine** — ff-exec Gate E (lock `~/.agents/ff-executor.lock` free), Gate F (configured model = `executor_model`) and Gate G (take the lock); released by writing `active: false`. The lock is the one declared exception to the outside-workspace hard rule (written, never deleted). The planner may plan several repos; execution is serial (one GPU, one model).

### Changed

- **Autonomy:** one "go" per plan governs dispatching (user decision); the autonomy score is informational.
- **Judge capped at 3 rounds per session** (lesson-007) with a minimal clean view (artifacts + `routing.md` + the Phase 1 gate).
- Planner dry-run: T0 unchanged (FAIL → PASS, idempotent); T1/T2 = red before green, without writing the implementation.
- `ff-exec` 2.0.0: sections renumbered (lock = 6, end of run = 7, status = 8); `/ff` command updated.
- `harness.md`, `manifest.md`, `autonomy-harness.md`, `references/ff-protocol.md` aligned; consumer docs describe the tiers; the migration guide no longer creates a pre-v13 `state.json`.

### Files Changed

- `global-skills/ff/SKILL.md`, `routing.md` (new), `harness.md`, `manifest.md`, `autonomy-harness.md`
- `global-skills/ff-exec/SKILL.md`, `.opencode/commands/ff.md`, `.opencode/agents/ff-executor.md` (new), `global-skills-registry.json`
- `scripts/propagate-to-projects.py`, `.gitignore`
- `references/ff-protocol.md`, `references/executor-calibration.md` (new)
- `AGENTS.md`, `README.md`, `template-project/AGENTS.md`, `template-project/README.md`, `template-project/migration-guide.md`, `skill-governance.md`, `skill-index.md`, `FF-CHANGELOG.md`

### Migration for Consumer Projects

1. `python scripts/propagate-to-projects.py update <project>` (always pass the path; it now also copies `.opencode/agents/ff-executor.md`), or `git submodule update --remote .eng` + `python -X utf8 .eng/scripts/sync-global-skills.py pull`.
2. Keep the project's `.opencode/opencode.json` `model` set to the local model you plan with; the planner records it in `handoff.json`.
3. v13 sessions in flight continue as all-T0 (no `exec_tier`, traces without `attempts` stay valid).
4. Beta: nothing to configure — the planner appends `.ff/calibration.jsonl` in every session.

## v13.0.0 — Hybrid Protocol: Claude Planner + Local Executor (2026-10-09)

### New

- **Two roles, one file contract.** The **planner** (Claude, cloud session linked to the repo) owns Phase 0 Clarify, Phase 1 Plan, Phase 3 Review & Validate and Phase 4 Lessons. The **executor** (local model via opencode) owns Phase 2 Execute. They communicate only through `.ff/`: `state.json` gains `owner` (`planner` | `executor` | `user`), the `status` values `planning` · `awaiting_execution` · `executing` · `awaiting_review` · `rework` · `blocked` · `completed` · `cancelled`, and the lists `blocks_executed`, `blocks_rework`, `blocks_blocked`.
- **Executor-grade work orders** — `plan/work-orders/{block_id}.md`: exact files, exact edits, forbidden actions, check command. Anything that needs judgement is written by the planner.
- **Executable checks** — `plan/checks/{block_id}.py`: Python stdlib, OS-agnostic, `PASS`/`FAIL` per scenario, exit 0 only if all pass. Judged together with the plan and the Gherkin acceptance.
- **Handoff manifest** — `plan/handoff.json` with the sha256 of every work order and check.
- **`ff-exec` skill** (new, `global-skills/ff-exec/`) — the executor protocol: start checks (owner, status, clean tree), one block at a time, one retry, one local commit per block, execution trace with a **validation proposal**.
- **Critical second validation (Phase 3)** — the planner re-runs every check itself, verifies the scope from the commit, reads the full diff, records agreement/disagreement with the validation proposal, and approves or sends the block back for rework (max 2 rounds, then escalate).
- **Multi-project rule** — one active FF session per repo; the protocol is read from the repo being worked on.

### Changed

- Analysis passes (structural, adversarial), plan, fragmentation and acceptance run in the planner session; the judge stays the only sub-agent (clean view; unavailable judge = HALT).
- `/ff` (opencode) is now executor-only: `/ff exec`, `/ff exec <block_id>`, `/ff status`. A work description typed there is refused and redirected to the planner.
- `references/ff-protocol.md` is now a short reference pointing to the canonical skills (no more 500-line mirror).
- `scripts/propagate-to-projects.py` overwrites a stale `.opencode/commands/ff.md` in consumer projects and writes `.ff/` (not `. ff/`) to `.gitignore`.
- Swarm is no longer part of FF. Session ff-20261009-001 (v12.8.0 draft, in-session + judge-only) was cancelled and folded into this version.

### Files Changed

- `global-skills/ff/SKILL.md`, `manifest.md`, `harness.md`, `autonomy-harness.md`
- `global-skills/ff-exec/SKILL.md` (new), `global-skills-registry.json`
- `.opencode/commands/ff.md`
- `references/ff-protocol.md`, `references/anti-patterns.md`
- `AGENTS.md`, `README.md`, `template-project/AGENTS.md`, `template-project/README.md`, `template-project/migration-guide.md`
- `scripts/propagate-to-projects.py`
- `skill-index.md`, `skill-governance.md`, `FF-CHANGELOG.md`

### Migration for Consumer Projects

1. From the framework repo: `python scripts/propagate-to-projects.py update <project>` — updates the submodule, runs `sync-global-skills.py pull` (installs `ff-exec` into `~/.agents/skills`) and now overwrites a stale `/ff` command. Always pass the project path: `update` without a path runs `git push origin master` on the framework repo first, without asking.
2. Without the propagate script: `git submodule update --remote .eng`, then `python -X utf8 .eng/scripts/sync-global-skills.py pull` (run it on the machine where opencode runs).
3. Make sure opencode in that project answers with the local model.
4. In-flight v12.x sessions (no `owner` in `state.json`) are treated as legacy: the planner decides how to continue and re-judges before any handoff.

## v12.7.0 — Acceptance Layer + Context Handoff (2026-10-07)

### New

- **Acceptance Build step (Phase 1, Step 1.4)** — a mandatory Acceptance Architect sub-agent runs BETWEEN fragmentation and the judge. It writes, for every block:
  - `plan/acceptance-plan.md` — the acceptance tests that must be executed per delivery, with concrete execution instructions (runner, command, scenarios covered)
  - `plan/acceptance/{block_id}.feature` — strict Gherkin acceptance criteria per delivery (Given/When/Then)
  - Scope: specification ONLY — the step never runs tests, commands, or suites. Execution stays in Phase 2/3.
  - Acceptance level is end-user perspective (what the user does, what the user observes). Unit tests alone never satisfy the acceptance gate.
  - Mandatory coverage per block: happy path, every adversarial edge case, negative/error paths — all with deterministic, concrete expected outcomes.

- **Acceptance gate in the judge** — the judge now validates the plan, the blocks, AND the acceptance criteria. Rejection reasons include: missing feature file, unit-level acceptance, unit-only acceptance, edge case without scenario, vague expectations, non-executable test instructions.

- **Acceptance in the block gate (Phase 2)** — acceptance tests are run mechanically per `acceptance-plan.md`; a failing acceptance scenario counts as a failed row. Block traces record `acceptance: { feature, scenarios_total, scenarios_passed }`.

- **Acceptance in the final gate (Phase 3)** — the full acceptance suite (all blocks) runs before the project test suite; the FF report gains an `Acceptance:` line.

- **Context Handoff (mandatory in every dispatch)** — the orchestrator assembles a Context Package before EVERY sub-agent dispatch (analysts, Plan Writer, Acceptance Architect, judge, executors): Session Context, Plan Slice, File Context (orchestrator-read excerpts of in-scope files), Contracts (consumes/produces), Acceptance (the block's Gherkin feature), Skill Digest (rules extracted from loaded skills — never bare skill names), and Lessons & Decisions. The previously-undefined `sharedContext` in the Swarm dispatch is now this package.

- **Richer block structure** — blocks carry a self-contained multi-line `instruction` (read what, change what, satisfy which acceptance), `contracts` (consumes/produces), and `acceptance` (feature path). One-line instructions are a protocol violation.

### Changed

- Phase 1 renumbered: 1.1 Analyze → 1.2 Build Plan Document → 1.3 Fragment into Draft Blocks (moved before the judge) → 1.4 Acceptance Build → 1.5 Judge → 1.6 Autonomy Score → 1.7 Present Plan
- Judge rejection now returns to the specific failing step (1.2 plan / 1.3 fragmentation / 1.4 acceptance)
- Drift tables and anti-patterns extended: skipping acceptance build, unit-level acceptance, thin context handoffs

### Files Changed

- `global-skills/ff/SKILL.md` — Acceptance Build step, extended judge, Context Handoff section, block structure, Swarm dispatch, Phase 2/3 gates
- `global-skills/ff/manifest.md` — Phase 1→2 and block gates extended
- `global-skills/ff/harness.md` — acceptance artifacts mandatory in the Phase 1→2 post-hook
- `references/ff-protocol.md`, `references/anti-patterns.md` — mirrored
- `AGENTS.md`, `README.md`, `template-project/` (AGENTS, README, migration-guide), `.opencode/commands/ff.md` — protocol summaries updated

### Migration for Consumer Projects

None required. Backward compatible: sessions that already passed Phase 1 resume unchanged. New sessions enforce the acceptance gate.

## v12.6.0 — Community-Ready Release (2026-09-19)

### New

- `.opencode/commands/ff.md` is now tracked — fresh clones ship the `/ff` command definition
- Consumer template fixed for distribution: real framework URL in `.gitmodules`, real FF state schema in the migration guide, corrected skill/reference counts
- Docs consistency pass: all version and count strings aligned across README, AGENTS.md, skill-index, skill-governance, template-project
- Motor-era sections removed from README and AGENTS.md

### Changed

- Git hygiene: untracked stale loop-motor artifacts (root `state.json`, `.opencode/opencode.json`, `.eng/` history JSONs, `sub/ok.txt` deleted, `artifacts/post-loop-summary.md`)
- `.gitignore` rewritten for the FF era (`.eng/` and `.ruff_cache/` ignored; `.opencode/commands/` tracked)
- README Installation now copies the `/ff` command definition into new consumer projects
- Milestone tag: `v12.6.0`

### Files Changed

- `README.md`, `AGENTS.md`, `skill-index.md`, `skill-governance.md` — version/count alignment, motor-era section removal, directory trees corrected
- `template-project/` — `.gitmodules` URL, migration guide schema/counts, README structural fixes
- `FF-CHANGELOG.md` — this entry; the 2026-09-14 entry below is annotated (it shipped in this release)
- `.gitignore`, git index — hygiene untracks

### Migration for Consumer Projects

None. Backward compatible with existing FF sessions and installs.

## v12.4.0 — Fail Fast Enhancement (2026-09-14)

> **Label note:** this entry is mislabeled. The work below was built after v12.5.0 (2026-09-10) and shipped in the **v12.6.0** release (2026-09-19).

### New

- `/ff` command via `.opencode/commands/ff.md`:
  - `/ff <description>` — start new session
  - `/ff status` — show current session
  - `/ff resume` — resume interrupted session
  - `/ff history` — list recent sessions
  - `/ff lessons` — show accumulated lessons

- Full session tracing in `.ff/traces/{session_id}/`:
  - `session.json` — metadata (start, end, status, files)
  - `essence.md` — Phase 0 output
  - `plan/structural.json` — structural analysis
  - `plan/adversarial.json` — adversarial analysis
  - `plan/plan.md` — comprehensive plan document (NEW)
  - `plan/judge.json` — judge decision
  - `plan/blocks.yaml` — fragmented blocks
  - `blocks/{block_id}.json` — each block's execution trace
  - `report.md` — final FF report

- `harness.md` — pre/post hooks for protocol enforcement:
  - Pre-hook: state check, manifest read, lessons load, role assertion
  - Post-hook per phase: mandatory persistence before phase transition
  - Interrupt recovery hook: resume from last checkpoint
  - Verification checklist: must pass before declaring FF done

- Session resume protocol in `autonomy-harness.md`:
  - Detect existing session from `.ff/state.json`
  - Load context from traces without re-reading conversation
  - Never re-run blocks persisted as complete

### Changed

- Phase 1 restructured:
  - Step 1.1: Analyze (structural + adversarial) — unchanged
  - Step 1.2: **NEW** — Plan Writer sub-agent creates comprehensive `plan.md`
  - Step 1.3: Judge validates `plan.md` (not just consolidation)
  - Step 1.4: Fragment approved plan into swarm blocks
  - Flow: analyze → plan document → judge → fragment → execute

- `state.json` schema expanded:
  - Added: `current_phase`, `trace_dir`, `files_changed`, `files_created`, `decisions`, `completed_at`

- Gate checks in `manifest.md`:
  - Added Pre-Flight check before Phase 0
  - Added persistence verification to every gate
  - Added post-hook verification to Phase 3 completion

- `.ff/` directory now gitignored (working artifacts only)

### Files Changed

- `global-skills/ff/SKILL.md` — Phase 1 refactor, persistence requirements
- `global-skills/ff/harness.md` — NEW — hooks layer
- `global-skills/ff/manifest.md` — new gates, pre-flight check
- `global-skills/ff/autonomy-harness.md` — resume protocol
- `.opencode/commands/ff.md` — NEW — command definition
- `.ff/README.md` — workspace documentation
- `AGENTS.md` — `/ff` command documentation

### Migration for Consumer Projects

For projects using this repo as `.eng/` submodule:

1. `git submodule update --remote .eng`
2. `python .eng/scripts/sync-global-skills.py pull`
3. Add to `.gitignore`:
   ```
   # FF workspace
   .ff/
   # OpenCode local config (the /ff command stays tracked)
   .opencode/*
   !.opencode/commands/
   ```
4. Copy the `/ff` command definition from the framework:
   ```bash
   mkdir -p .opencode/commands
   cp .eng/.opencode/commands/ff.md .opencode/commands/ff.md
   ```
5. Commit: `git add .eng .gitignore .opencode/commands && git commit -m "chore(eng): update FF protocol"`

### Breaking Changes

None. Backward compatible with existing FF sessions.
