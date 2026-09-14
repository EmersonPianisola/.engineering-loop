# FF Protocol Harness — Hooks

**READ THIS BEFORE ANY OTHER FF FILE.**

This is the mechanical enforcement layer for the FF protocol. These hooks are NOT optional.
They exist to prevent drift when context grows.

---

## Pre-Hook (BEFORE Starting Any Phase)

**Trigger:** User runs `/ff`, or you are asked to use FF, or you detect you're already in an FF session.

**Action — Execute in this exact order:**

1. **Read state:** `Read .ff/state.json`
   - If exists and status is "running"/"paused": announce "Existing session detected" and offer resume
   - If exists and status is "completed": create new session
   - If doesn't exist: create new session

2. **Read manifest:** `Read manifest.md` (same directory as this skill)
   - Use it as your phase gate checklist for the upcoming transition

3. **Read lessons:** `Read .ff/lessons.json` (if exists and non-empty)
   - Scan for lessons matching the current work_type
   - Note any applicable prevention rules

4. **Assert role:** Say exactly: "FF session initialized. I am the orchestrator."

5. **Proceed to Phase 0.**

**FAIL CONDITION:** If you skip any of these 5 steps, you are violating protocol. Stop and re-read this file.

---

## Post-Hook (AFTER Each Phase Completion)

**Trigger:** You are about to transition from one phase to the next, or FF is complete.

### Phase 0 → Phase 1 Post-Hook

Write to `.ff/state.json`:
- `current_phase: "phase_0"`
- `work_type: "<classified>"`
- `task_title: "<title>"`
- `updated_at: "<ISO>"`

Write to `.ff/traces/{session_id}/essence.md`:
- Full essence check output (verbatim)

### Phase 1 → Phase 2 Post-Hook

Write to `.ff/state.json`:
- `current_phase: "phase_1"`
- `blocks_completed: []`
- `blocks_pending: ["block-001", ...]`
- `autonomy_mode: "<mode>"`
- `tasks.total: <N>`
- `updated_at: "<ISO>"`

### Phase 2 → Phase 3 Post-Hook (After Each Block)

For EACH block completed, write:
- `.ff/traces/{session_id}/blocks/{block_id}.json` with:
  - `block_id`, `scope`, `tasks`, `completed`, `failed`, `retried`, `completed_at`, `files_changed`, `summary`

Update `.ff/state.json`:
- Add block to `blocks_completed`, remove from `blocks_pending`
- Update `current_block`
- Update `tasks` counts
- Add files to `files_changed` / `files_created`
- Update `updated_at`

### Phase 3 → Complete Post-Hook

Write to `.ff/traces/{session_id}/report.md`:
- Full FF report with all sections

Update `.ff/traces/{session_id}/session.json`:
- `status: "completed"`
- `completed_at: "<ISO>"`
- `blocks_total`, `tasks_total`, `files_changed`, `files_created`

Update `.ff/state.json`:
- `status: "completed"`
- `completed_at: "<ISO>"`
- `updated_at: "<ISO>"`

Append to `.ff/changelog.md`:
- Session entry with title, status, counts, duration, summary

Update `.ff/lessons.json`:
- Append new lessons for any failures

---

## Interrupt Recovery Hook

**Trigger:** Session ends unexpectedly, user reopens, or context is cleared.

**Action:**

1. Check `.ff/state.json`:
   - If status is "running" or "paused": resume mode activated
   - If missing: list `.ff/traces/` directories and ask user which to resume

2. Load last checkpoint from `.ff/traces/{session_id}/`:
   - Read last block trace or last phase output
   - Never re-run what's already persisted as complete

3. Announce: "Resuming FF session {session_id} from {current_phase}/{current_block}"

4. Continue from that position.

---

## Verification Checklist (Use Before Declaring FF Done)

Before telling the user FF is complete, verify:

- [ ] `.ff/state.json` status is "completed" with `completed_at` set
- [ ] `.ff/traces/{session_id}/report.md` exists and is complete
- [ ] `.ff/traces/{session_id}/session.json` status is "completed"
- [ ] All block traces exist in `.ff/traces/{session_id}/blocks/`
- [ ] `.ff/lessons.json` updated with any new lessons
- [ ] `.ff/changelog.md` has session entry

**If any item is missing, complete it before declaring FF done.**
