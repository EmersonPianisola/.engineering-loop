---
name: impl-review
id: impl.review
version: 1.0.0
type: stage
description: 'Code review. Adversarial review of implementation against blueprint and spec.'
---

# STAGE: Implementation Review
<!-- ID: impl.review -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as parallel code reviewers.
- DO NOT implement fixes directly. Report findings only.
- The moment you produce the triage report, your task is FINISHED.
- Modifying code is a CRITICAL VIOLATION.

## Procedure

1. **Prerequisite Check:** If `state.stages.impl.code.done != true` → `status: blocked`, `blocking_condition: implementation not complete`. **EXIT.**
2. Proceed with the steps below.

# Implementation Review — Parallel Reviewers

**Runs when:** `state.stages.impl.review.done == false`
**Prerequisite:** `state.stages.impl.code.done == true`

## Design — Review Plan

- Construct diff since `state.baseline_revision`.
- Produce review plan: high-risk areas, security paths, data integrity points, per-reviewer focus.
- Store in `state.artifacts.review_plan`.

## Execute — Parallel Reviewers

Launch 3 reviewers synchronously, each receiving only its context slice (per `references/hardware-management.md`):

### Blind Hunter
**Slice:** diff + work item + blueprint relevant sections
> Review adversarially. Focus: security, data integrity, error handling, spec deviations, architecture.

### Edge Case Hunter
**Slice:** work item + I/O matrix + diff edge-case areas
> Hunt every edge case. Focus: boundaries, null paths, race conditions, validation gaps, state management.

### Test Coverage Auditor
**Slice:** BDD journey + ACs + test file paths (if tests exist)
> Audit test coverage. Verify every AC and BDD scenario has a test. Report gaps.

Each agent's context must not exceed `agent_context_limit` tokens.

Collect findings. Append to `state.findings`. Run `cap_findings()` if buffer exceeded.

## Validate — Triage

Deduplicate. Assign severity. Categorize:

| Category | Effect on State |
|----------|----------------|
| `intent_gap` | `status: blocked`. **EXIT.** |
| `bad_spec` | Amend work item. `impl.design.done = false`, `blueprint = null`, `impl.review.done = false` |
| `patch` | Auto-fix. If tests fail: `impl.code.done = false`, `impl.review.done = false` |
| `defer` | Append to `deferred-work.md` |
| `reject` | Drop |

- No action-required findings → `state.stages.impl.review.done = true`.
- Append triage log to work item.

## Expected Output

Your final response MUST strictly contain the triage report with categorized findings. End your generation immediately after the report. Do not write "Next steps".
