---
name: review
id: review
version: 1.0.0
type: stage
description: 'Design review plan → Execute parallel reviewers → Validate triage.'
---

# STAGE: Review
<!-- ID: review -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as parallel reviewers: Blind Hunter, Edge Case Hunter, Test Coverage Auditor.
- DO NOT transition to post-loop stage.
- The moment you produce the triage report, your task is FINISHED.
- Implementing fixes directly is a CRITICAL VIOLATION — report findings only.

## Procedure

1. **Prerequisite Check:** If `state.stages.deploy.prepare.done != true` → `status: blocked`, `blocking_condition: deploy preparation not complete`. **EXIT.**
2. Proceed with the steps below.

# Review Stage

**Runs when:** `state.stages.review.done == false`
**Constraint:** `max_review_attempts` (default: 2)

## Design — Review Plan

Only runs when `state.artifacts.review_plan` is null.

- Construct diff since `state.baseline_revision`.
- Produce review plan: high-risk areas, security paths, data integrity points, per-reviewer focus.
- Store in `state.artifacts.review_plan`.
- Essence: `references/essence-sidecar.md`

## Execute — Parallel Reviewers

Set work item status `in-review`. Launch 3 reviewers synchronously, each receiving only its context slice (per `references/hardware-management.md`):

### Blind Hunter
**Slice:** diff + work item + blueprint relevant sections
> Review adversarially. Focus: security, data integrity, error handling, spec deviations, architecture.

### Edge Case Hunter
**Slice:** work item + I/O matrix + diff edge-case areas
> Hunt every edge case. Focus: boundaries, null paths, race conditions, validation gaps, state management.

### Test Coverage Auditor
**Slice:** BDD journey + ACs + test file paths
> Audit test coverage. Verify every AC and BDD Journey scenario has a test. Report gaps.

Each agent's context must not exceed `agent_context_limit` tokens.
Collect findings. Append to `state.findings`. Run `cap_findings()` if buffer exceeded.

## Validate — Triage

Deduplicate. Assign severity. Categorize:

| Category | Effect on State |
|----------|----------------|
| `intent_gap` | `status: blocked`. **EXIT.** |
| `bad_spec` | Amend work item. `impl.design.done = false`, `blueprint = null`, `review.done = false` |
| `patch` | Auto-fix. If tests fail: `impl.code.done = false`, `test.unit.done = false`, `review.done = false` |
| `defer` | Append to `deferred-work.md` |
| `reject` | Drop |

- No action-required findings → `state.stages.review.done = true`.
- Append triage log to work item.

## Cross-Stage Resets

See `references/exit-conditions.md` → Cross-Stage Reset (Review Triage).


## Expected Output
Your final response MUST strictly contain the triage report with categorized findings. End your generation immediately after the report. Do not write "Next steps".
