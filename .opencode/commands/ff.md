---
description: Run the FF (Fail Fast) protocol for this work item or manage FF sessions
agent: build
---

You are the FF orchestrator. Load the `ff` skill and follow the protocol.

## Available commands

- `/ff <description>` — Start a new FF session for the described work
- `/ff status` — Show current FF session status from `.ff/state.json`
- `/ff resume` — Resume an interrupted FF session from last checkpoint
- `/ff history` — List recent FF sessions from `.ff/traces/`
- `/ff lessons` — Show accumulated lessons from `.ff/lessons.json`

## Current command

$ARGUMENTS

## Execution

### If starting a new session (`$ARGUMENTS` is a description):

1. Initialize `.ff/state.json` with session metadata
2. Create trace directory `.ff/traces/{session_id}/`
3. Begin Phase 0 (CLARIFY) with essence check
4. Follow the FF protocol strictly through all phases
5. Persist outputs after every significant event:
    - Essence check → `.ff/traces/{session_id}/essence.md`
    - Each sub-agent output → `.ff/traces/{session_id}/plan/`
    - Acceptance plan → `.ff/traces/{session_id}/plan/acceptance-plan.md`
    - Acceptance features → `.ff/traces/{session_id}/plan/acceptance/{block_id}.feature`
    - Each block completion → `.ff/traces/{session_id}/blocks/{block_id}.json`
    - Final report → `.ff/traces/{session_id}/report.md`
6. Update `.ff/state.json` after every block completion

### If checking status (`$ARGUMENTS` contains "status"):

1. Read `.ff/state.json`
2. If no session exists: report "No active FF session"
3. If session exists: show current phase, block, progress, and trace path

### If resuming (`$ARGUMENTS` contains "resume"):

1. Read `.ff/state.json`
2. If no active session: ask which session to resume from `.ff/traces/`
3. If active session:
   - Read last checkpoint from `.ff/traces/{session_id}/`
   - Announce: "Resuming FF session {session_id} from {current_phase}/{current_block}"
   - Continue from that position

### If listing history (`$ARGUMENTS` contains "history" or "list"):

1. List sessions in `.ff/traces/` with status, date, and block progress
2. Show most recent first

### If showing lessons (`$ARGUMENTS` contains "lessons"):

1. Read `.ff/lessons.json`
2. Display lessons grouped by work_type or chronologically

## Rules

- Always follow the FF protocol — this is the project's development standard
- Never skip the acceptance build or the judge phase — Gherkin acceptance criteria are written BEFORE the judge, and the Acceptance Architect never runs tests
- Build the full Context Package (file excerpts, contracts, skill digests, lessons) for every sub-agent dispatch — thin handoffs cause discovery loops
- Always persist state and traces to disk — never rely on conversation memory alone
- The `.ff/` directory is the single source of truth for FF progress
