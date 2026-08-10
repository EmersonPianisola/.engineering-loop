---
stage: design.user-research
skill: bmad-user-research
min_complexity: large
---

# Design > User Research
<!-- Min Complexity: large — deactivated for small/medium -->

User research procedure (interviews, contextual studies, usability tests, competitive analysis).

## Activation

- Sources: PRD, any existing research, `{workflow.external_sources}`.
- Elicit: research goals, target users, constraints (time, budget, participants).
- Methods: interviews, contextual inquiry, surveys, usability tests, competitive analysis.

## Discovery

1. Review PRD and existing research.
2. Identify research goals and target user segments.
3. Conduct or review user interviews, contextual inquiry, surveys, usability tests.
4. Perform competitive analysis.
5. Log gaps as assumptions.

## Finalize

- Output: `research-findings.md` (key insights, quotes, gaps), `research-questions.md`.
- Gate: ≥3 distinct sources or user-validated primary research; gaps logged as assumptions.
- State: `done: true` when research findings and questions are documented.

## State Update Contract

**MANDATORY.** Follow `{reference-root}/sub-agent-contract.md`. Before returning your response:

1. Write all artifacts to their designated paths in `{artifact-root}/`
2. Update `{loop-root}/state.json`:
   - `stages.design.user-research.done = true` (or `false` on failure)
   - `stages.design.user-research.attempts += 1`
   - `stages.design.user-research.artifact_path = "artifacts/..."` (your output path)
   - `stages.design.user-research.error = null` (or failure description)
3. Record AD-NNN decisions in `{loop-root}/STATE.md ## Decisions` (if applicable)
4. Your response MUST be a single JSON line:
   - Success: `{"stage":"design.user-research","status":"done","artifact":"artifacts/..."}`
   - Failure: `{"stage":"design.user-research","status":"failed","error":"reason"}`

DO NOT include artifact content, summaries, or "Next steps" in your response.
