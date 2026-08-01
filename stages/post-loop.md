---
name: post-loop
id: post
version: 2.0.0
type: stage
description: 'Phase 5 (Skill Improvement + Lessons) + Phase 6 (Finalize). Runs once after all stages done.'
---

# STAGE: POST-LOOP (Phase 5 + Phase 6)
<!-- ID: post -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting as the orchestrator finalize phase. No further stage transitions are possible.
- The moment the work item is finalized and logged, your task is FINISHED.
- Do not re-open stages or introduce new work.

## Procedure

1. **Prerequisite Check:** If `state.stages.doc.update.done != true` → `status: blocked`, `blocking_condition: project documentation not updated`. **EXIT.**
2. **Prerequisite Check:** If `state.stages.doc.project.done != true` AND `state.complexity >= "medium"` → `status: blocked`, `blocking_condition: documentation phase not complete`. **EXIT.**
2. Proceed with the steps below.

# POST-LOOP — Phases 5 & 6

## Phase 5: Skill Improvement + Lessons

1. Extract lessons from all iterations: KEEP / IMPROVE / ADD.
2. Update each skill's SKILL.md.
3. Record in `{framework-root}/skill-index.md`.
4. **Lessons consolidation:**
   - Load `{artifact-root}/lessons.json`
   - Promote candidates that reached `confirm_threshold` to confirmed
   - Render `{artifact-root}/LESSONS.md`
   - Archive lessons for this feature
5. **Lessons sharing (Phase 5.5):**
   - Identify new confirmed lessons not yet in `{artifact-root}/lessons-shared.json`
   - Copy to `{artifact-root}/lessons-pending.json`
   - Report: "N lessons ready to share with framework"
   - Instruct user: `git -C .eng add artifacts/lessons-shared.json && git commit`

## Phase 6: Finalize

1. All tasks `[x]` in work item.
2. Full test suite: `npm run test`. All pass.
3. Lint/build. Pass.
4. Update work item: `status: done`, `final_revision`, `review_loop_iteration: state.iteration`.
5. Commit (do not push).
6. Finalize log: `completed_at`, `status: done`, `skills_used`, `total_iterations: state.iteration`.
7. Finalize `{loop-root}/STATE.md`: update Handoff to reflect completion.
8. Append to `{log_root}/index.md`.
9. Report summary to user.

## Expected Output

Your final response MUST strictly contain the finalized work item status, completion log summary, and lessons summary. End your generation immediately after the summary. Do not write "Next steps".
