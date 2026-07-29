---
name: init
id: init
version: 3.0.0
type: stage
description: 'Phase 0 (Validate Input) + Phase 1 (Skill Discovery) + Auto-size classification. Runs once before loop opens. Initializes project paths and state.'
---

# STAGE: INIT (Phase 0 + Phase 1)
<!-- ID: init -->

## 🚨 MANDATORY EXECUTION BOUNDARY (RE-ACT ISOLATION)
- You are acting EXCLUSIVELY as the `bmad-integration` skill.
- DO NOT transition to any loop stage (architecture, impl, test, review).
- The moment you validate the work item, discover skills, and classify complexity, your task is FINISHED.
- Generating implementation code or architecture artifacts is a CRITICAL VIOLATION.

## Procedure

# INIT — Phases 0, 1, and Auto-Size

## Path Resolution

Before any work, ensure paths are resolved:
- `{framework-root}` = directory containing ORCHESTRATOR.md
- `{loop-root}` = `{framework-root}` (project files live inside submodule)
- `{project-root}` = current working directory (cwd)
- `{artifact-root}` = `{loop-root}/<config.artifact_root>`
- `{skill-root}` = `{framework-root}/<config.framework_skill_root>`
- `{reference-root}` = `{framework-root}/<config.framework_reference_root>`
- `{stage-root}` = `{framework-root}/<config.framework_stage_root>`
- `{log-root}` = `{project-root}/<config.log_root>`

## State Initialization

1. IF `{loop-root}/config.yaml` does not exist:
   - Copy `{framework-root}/config-template.yaml` → `{loop-root}/config.yaml`
   - Warn user to review and customize config.yaml
2. IF `{loop-root}/state.json` does not exist:
   - Copy `{framework-root}/state-template.json` → `{loop-root}/state.json`
3. Ensure directories exist:
   - `{artifact-root}/`
   - `{artifact-root}/architectures/`
   - `{artifact-root}/blueprints/`
   - `{artifact-root}/bdd-journeys/`
   - `{artifact-root}/design/`
   - `{artifact-root}/test-plans/`
   - `{log-root}/`

## Phase 0: Validate Input

1. Read `{loop-root}/config.yaml` → load constraints, hardware settings, auto-sizing heuristics.
2. Initialize `state` — all `done: false`, all `attempts: 0`.
3. Locate work item:
   - Explicit path → load
   - BMad → invoke `bmad-integration` skill
   - Ad-hoc → auto-structure or request from user
4. Validate: title, acceptance criteria, scope, intent present.
5. If fails → `status: blocked`, `blocking_condition: input not ready`. **EXIT.**
6. Store in `state.work_item`.
7. Create log file per `references/logging.md`.
8. Initialize `{loop-root}/STATE.md` per `references/logging.md` dual state format.

## Phase 0.5: Ideation (Ad-Hoc Work Items)

When the work item is ad-hoc (no explicit path, no BMad spec):

1. **Absorb the user's request as-is** — treat the raw user message as the seed work item.
2. Run essence validation on the raw intent:
   - Apply Four Lenses to identify ambiguities, hidden assumptions, literal traps, conflicting priorities.
   - Report findings back to the user with specific clarifications.
3. Propose a refined work item structure:
   - `title` — one-line summary of what the user wants
   - `intent` — what the user is trying to achieve (not how)
   - `acceptance_criteria` — 3-7 concrete, testable outcomes
   - `scope` — what's in and what's out
   - `constraints` — technical, UX, or domain constraints
4. Present the refined work item to the user and ask: "Is this what you want, or should we adjust X?"
5. Iterate until the user confirms the work item is accurate.
   - Each iteration: run essence on the updated intent, refine, present.
   - Max iterations: 5 (then proceed with current state).
6. On user confirmation:
   - Set `state.work_item` with the finalized structure.
   - Set `state.work_item_type = "ad-hoc"`.
   - Proceed to Phase 1.

## Phase 1: Skill Discovery

1. Classify domain(s) from work item.
2. Scan `{skill-root}/` + system skills. Score: exact(10), adjacent(5), generic(1).
3. If score < 5 → self-construct via `skill-creator` + `{reference-root}/skill-templates.md`.
4. Register: `state.skills = { impl_design, impl_execute, verify }`.
5. Register essence sidecar: `state.skills.essence = "essence"`.
6. Register verifier: `state.skills.verifier = "verifier"`.
7. If creation fails → `status: blocked`, `blocking_condition: no suitable skill`. **EXIT.**

## Phase 2: Auto-Size Classification

Apply heuristics from `config.yaml → auto_sizing:`:

1. Estimate files affected (from work item scope or blueprint if available)
2. Estimate task count (from acceptance criteria count and complexity)
3. Check for new domains (is this a domain the project hasn't touched before?)
4. Check for external integrations (APIs, third-party services, auth, payments)
5. Check for ambiguity (vague language, missing context, unclear intent)

| Level | Criteria |
|-------|----------|
| **Small** | ≤3 files, ≤3 tasks, no new domains, no external integrations |
| **Medium** | ≤10 files, ≤8 tasks, no new domains, may have external integrations |
| **Large** | >10 files or >8 tasks, new domains or external integrations |
| **Complex** | Ambiguity present, new domains, external integrations |

6. Set `state.complexity`.
7. Deactivate stages above complexity threshold (set `done: true`).
8. Record heuristics in `{loop-root}/STATE.md ## Complexity`.

## Phase 2.5: Knowledge Graph (conditional)

Only runs when `config.graphify.enabled == true`.

1. **Check prerequisites:**
   - IF `config.graphify.skip_if_small` AND `state.complexity == "small"` → skip. Record "Graphify skipped: complexity small".
   - IF no source code files exist in `{project-root}` → skip. Record "Graphify skipped: no codebase".

2. **Check CLI:**
   - Run: `graphify --version`
   - IF not found → warn "graphify CLI not installed. Install: `uv tool install graphifyy` or `pipx install graphifyy`". Skip. Continue loop.
   - IF found → continue.

3. **Build graph:**
   - IF `config.graphify.build_on_init` AND `graphify-out/graph.json` does not exist:
     - Run: `graphify .`
     - Record in STATE.md: "Graph built: N nodes, M edges, K communities"
   - IF `graphify-out/graph.json` already exists:
     - Run: `graphify . --update` (incremental, AST only, zero LLM cost)
     - Record in STATE.md: "Graph updated (incremental)"

4. **Git hook (optional):**
   - IF `config.graphify.build_on_commit` → run: `graphify hook install`

5. **Register skill:**
   - Set `state.skills.graphify = "graphify"`
   - Set `state.graphify.built = true`

## Lessons Loading

1. Load shared lessons from `{artifact-root}/lessons-shared.json` (if exists)
2. Load local lessons from `{artifact-root}/lessons.json` (if exists)
3. Merge: shared lessons take precedence
4. Filter: only confirmed lessons are loaded into context
5. Report: "Loaded N confirmed lessons (M shared, K local)"

## Self-Construction

See `references/skill-discovery-guide.md` for full process.

## Exit

On success, proceed to THE LOOP. On failure, see `references/exit-conditions.md`.

## Expected Output

Your final response MUST strictly contain the validated work item, discovered skills registry, complexity classification, and loaded lessons summary. End your generation immediately after the output block. Do not write "Next steps".
