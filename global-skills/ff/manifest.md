# FF Protocol Manifest — Phase Checkpoint Checklist

## Purpose

Read this file BEFORE every phase transition. It is a compressed checkpoint that
forces the orchestrator to verify it is following protocol, regardless of
context window size. If any item fails, STOP and correct before proceeding.

**This file is designed to be small enough to stay in context at all times.**

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

## Phase 0 → Phase 1 Gate

- [ ] Essence check completed (skill "essence" loaded)
- [ ] All Lens 4 tensions resolved with user
- [ ] Work type classified
- [ ] Auto-size rule evaluated (FF activated or inline execution justified)
- [ ] `.ff/state.json` initialized with session data

**FAIL any item → Return to Phase 0**

---

## Phase 1 → Phase 2 Gate

- [ ] Two sub-agents dispatched in parallel (Structural + Adversarial)
- [ ] Both sub-agents returned results
- [ ] Consolidation complete — A + B merged, conflicts resolved
- [ ] Judge sub-agent dispatched (NOT skipped, NOT replaced with self-assessment)
- [ ] Judge returned `{"approved": true}`
- [ ] Plan fragmented into blocks (≤ 8 blocks, each ≤ 5000 tokens context)
- [ ] Block dependencies defined (parallel blocks have no shared writes)
- [ ] Autonomy score calculated
- [ ] `.ff/state.json` updated with block list
- [ ] Relevant lessons loaded from `.ff/lessons.json`

**FAIL any item → Return to Phase 1, do NOT proceed to execution**

**COMMON DRIFT:** Showing plan to user before judge approval. DO NOT DO THIS.
**COMMON DRIFT:** Skipping judge because "the plan looks fine." THE JUDGE IS NOT OPTIONAL.
**COMMON DRIFT:** Building the plan yourself instead of dispatching sub-agents. YOU ARE THE ORCHESTRATOR.

---

## Phase 2 Block Gate (Check Before Each Block)

- [ ] Read `.ff/state.json` to confirm current block position
- [ ] Previous block completed successfully (or failure handled per escalation protocol)
- [ ] Block autonomy mode checked against score
- [ ] If block has ≥ 2 independent tasks → MUST dispatch Swarm (sequential execution FORBIDDEN)
- [ ] Gate check performed on results
- [ ] Failed rows retried once (max 1 retry)
- [ ] `.ff/state.json` updated with block result

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
- [ ] FF Report produced with all required fields
- [ ] Lessons captured for every failure (retried or escalated)
- [ ] Lessons appended to `.ff/lessons.json`
- [ ] `.ff/state.json` status set to "completed"

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
| Dispatch sub-agents (Task tool) | Write application code yourself |
| Consolidate sub-agent outputs | Build the plan yourself |
| Enforce gates mechanically | Skip gates because "it looks fine" |
| Run Swarm for parallel tasks | Execute tasks sequentially |
| Update `.ff/state.json` every step | Rely on conversation memory for state |
| Load this manifest at each phase | Trust that you "remember" the protocol |
| Send plan to judge before user | Show plan to user first |
