# FF Protocol — Changelog

All notable changes to the FF protocol.

## v12.4.0 — Fail Fast Enhancement (2026-09-14)

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
   # OpenCode local config
   .opencode/
   ```
4. Commit: `git add .eng .gitignore && git commit -m "chore(eng): update FF protocol"`

### Breaking Changes

None. Backward compatible with existing FF sessions.
