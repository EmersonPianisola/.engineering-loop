# FF Protocol Manifest — Phase Checkpoint Checklist

## Purpose

Read this file BEFORE every phase transition. It is a compressed checkpoint that
forces the orchestrator to verify it is following protocol, regardless of
context window size. If any item fails, STOP and correct before proceeding.

**Read order: harness.md → this file → phase instructions.**

This file is designed to be small enough to stay in context at all times.

---

## Role Assertion — Read at EVERY Phase Transition

```
YOU ARE THE ORCHESTRATOR.
You dispatch sub-agents. You consolidate results. You enforce gates.
You DO NOT write application code yourself.
You DO NOT execute tasks sequentially when Swarm applies.
If you find yourself writing code, you have drifted. STOP. Re-dispatch.
```

---

## Pre-Flight Check (BEFORE Phase 0)

- [ ] Read `harness.md` — executed pre-hook
- [ ] `.ff/state.json` read (existing session? resume or new?)
- [ ] `.ff/lessons.json` read (loaded relevant lessons)
- [ ] Role asserted: "FF session initialized. I am the orchestrator."

**FAIL any item → Do not proceed. Read harness.md and complete pre-hook.**

---

## Phase 0 → Phase 1 Gate

- [ ] Session initialized: `session_id` generated, `.ff/traces/{session_id}/` created
- [ ] `.ff/traces/{session_id}/session.json` written with metadata
- [ ] `.ff/state.json` initialized with full schema
- [ ] Essence check completed (skill "essence" loaded)
- [ ] All Lens 4 tensions resolved with user
- [ ] Essence output persisted to `.ff/traces/{session_id}/essence.md`
- [ ] Work type classified
- [ ] Auto-size rule evaluated (FF activated or inline execution justified)
- [ ] Post-hook executed: `state.json` updated with `current_phase: "phase_0"`

**FAIL any item → Return to Phase 0**

---

## Phase 1 → Phase 2 Gate

- [ ] Two sub-agents dispatched in parallel (Structural + Adversarial)
- [ ] Both sub-agents returned results
- [ ] Sub-agent outputs persisted: `plan/structural.json`, `plan/adversarial.json`
- [ ] Conflicts reconciled (no unresolved safe vs risky disagreements)
- [ ] Plan Writer sub-agent dispatched — produced comprehensive plan document
- [ ] Plan document persisted: `plan/plan.md`
- [ ] Judge sub-agent dispatched (NOT skipped, NOT replaced with self-assessment)
- [ ] Judge returned `{"approved": true}`
- [ ] Judge decision persisted: `plan/judge.json`
- [ ] Plan fragmented into blocks (≤ 8 blocks, each ≤ 5000 tokens context)
- [ ] Block list persisted: `plan/blocks.yaml`
- [ ] Block dependencies defined (parallel blocks have no shared writes)
- [ ] Autonomy score calculated
- [ ] `.ff/state.json` updated with block list, current_phase: "phase_1"
- [ ] Relevant lessons loaded from `.ff/lessons.json`

**FAIL any item → Return to Phase 1, do NOT proceed to execution**

**COMMON DRIFT:** Showing plan to user before judge approval. DO NOT DO THIS.
**COMMON DRIFT:** Skipping judge because "the plan looks fine." THE JUDGE IS NOT OPTIONAL.
**COMMON DRIFT:** Building the plan yourself instead of dispatching sub-agents. YOU ARE THE ORCHESTRATOR.

---

## Phase 2 Block Gate (Check Before Each Block)

- [ ] Read `.ff/state.json` to confirm current block position
- [ ] Previous block completed successfully (or failure handled per escalation protocol)
- [ ] Previous block trace persisted in `blocks/{block_id}.json`
- [ ] Block autonomy mode checked against score
- [ ] If block has ≥ 2 independent tasks → MUST dispatch Swarm (sequential execution FORBIDDEN)
- [ ] Gate check performed on results
- [ ] Failed rows retried once (max 1 retry)
- [ ] Block trace persisted: `blocks/{block_id}.json` with tasks, results, files_changed
- [ ] `.ff/state.json` updated: blocks_completed, blocks_pending, task counts, files lists

**FAIL any item → Halt block, correct before proceeding to next block**

**COMMON DRIFT:** Executing tasks sequentially instead of via Swarm. THIS DEFEATS FF.
**COMMON DRIFT:** Skipping gate check because "it looks right." VALIDATE MECHANICALLY.
**COMMON DRIFT:** Writing code instead of dispatching sub-agents. YOU ARE THE ORCHESTRATOR.

---

## Phase 2 → Phase 3 Gate

- [ ] All blocks completed (or failures escalated and documented)
- [ ] `.ff/state.json` reflects final block status
- [ ] No unresolved block failures

**FAIL any item → Return to failed block, do NOT proceed to validation**

---

## Phase 3 Completion Gate

- [ ] Full test suite run (or justified why not applicable)
- [ ] Cross-check: plan vs. actual changes compared
- [ ] FF Report persisted to `.ff/traces/{session_id}/report.md`
- [ ] Lessons captured for every failure (retried or escalated)
- [ ] Lessons appended to `.ff/lessons.json`
- [ ] Session metadata updated: `.ff/traces/{session_id}/session.json` (completed_at, status, files)
- [ ] `.ff/state.json` status set to "completed", completed_at set
- [ ] Changelog updated: `.ff/changelog.md` with session summary
- [ ] Post-hook verification from `harness.md` passed

**BEFORE declaring FF complete, verify ALL items above. Missing any = not done.**

**FAIL any item → Complete missing steps before reporting done**

---

## Context Budget Rule

After every 3 blocks completed, or if you sense context is getting large:

1. Summarize completed blocks into a single paragraph
2. Update `.ff/state.json` with complete status
3. Explicitly note: "Context summary created. Continuing from block {N}."

This keeps the conversation history manageable and ensures the protocol
checklist remains accessible.

---

## Quick Reference — What the Orchestrator Does vs. Doesn't Do

| DO | DON'T |
|----|-------|
| Read `harness.md` before starting | Skip the pre-hook |
| Dispatch sub-agents (Task tool) | Write application code yourself |
| Consolidate sub-agent outputs | Build the plan yourself |
| Enforce gates mechanically | Skip gates because "it looks fine" |
| Run Swarm for parallel tasks | Execute tasks sequentially |
| Update `.ff/state.json` every step | Rely on conversation memory for state |
| Load this manifest at each phase | Trust that you "remember" the protocol |
| Run post-hook after each phase | Declare FF done without persistence |
| Send plan to judge before user | Show plan to user first |
