---
name: post-loop
id: post
version: 1.0.0
type: stage
description: 'Phase 5 (Skill Improvement) + Phase 6 (Finalize). Runs once after all stages done.'
---

# STAGE: POST-LOOP (Phase 5 + Phase 6)
<!-- ID: post -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as the orchestrator finalize phase. No further stage transitions are possible.
- The moment the work item is finalized and logged, your task is FINISHED.
- Do not re-open stages or introduce new work.

## Procedure

1. **Prerequisite Check:** If `state.stages.doc.project.done != true` → `status: blocked`, `blocking_condition: documentation phase not complete`. **EXIT.**
2. Proceed with the steps below.

# POST-LOOP — Phases 5 & 6

## Phase 5: Skill Improvement

1. Extract lessons from all iterations: KEEP / IMPROVE / ADD.
2. Update each skill's SKILL.md.
3. Record in `{loop-root}/skill-index.md`.

## Phase 6: Finalize

1. All tasks `[x]` in work item.
2. Full test suite: `npm run test` + `npm run test:e2e`. All pass.
3. Lint/build. Pass.
4. Update work item: `status: done`, `final_revision`, `review_loop_iteration: state.iteration`.
5. Commit (do not push).
6. Finalize log: `completed_at`, `status: done`, `skills_used`, `total_iterations: state.iteration`.
7. Append to `{process-logs}/index.md`.
8. Report summary to user.


## Expected Output
Your final response MUST strictly contain the finalized work item status and completion log summary. End your generation immediately after the summary. Do not write "Next steps".
