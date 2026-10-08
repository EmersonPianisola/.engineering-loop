# FF Protocol — Changelog

All notable changes to the FF protocol.

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
