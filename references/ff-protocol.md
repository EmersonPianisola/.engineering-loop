---
name: ff-protocol
id: ff
version: 1.0.0
type: reference
description: 'FF (Fail Fast) protocol specification — parallel swarm-based development with atomic blocks, Gherkin acceptance criteria per block, judge-gated planning, mandatory context handoff, and autonomy scoring.'
---

# FF Protocol — Fail Fast

FF is the default development mode. It replaces the sequential loop with parallel swarm execution.

**Core principle:** One orchestrator (the main agent), many specialized workers (sub-agents via Swarm). Every unit of work is atomic, validated in isolation, and fails fast without contaminating siblings.

**Not a framework. Not a graph. Not waves. A protocol.**

### Anti-Drift Mechanisms

Long FF sessions cause the orchestrator to forget protocol rules. Three mechanisms prevent this:

1. **`manifest.md`** — Compressed phase checklist in `global-skills/ff/`. Read before every phase transition. Designed to stay in context at all times.
2. **State file as anchor** — `.ff/state.json` is the single source of truth for progress. Always read it before making decisions about current position. Never rely on conversation memory.
3. **Context budget rule** — After every 3 blocks, summarize completed work into one paragraph and write to state.json. Keeps the conversation window manageable.

The ff SKILL.md includes a **drift symptoms table** — if any symptom is observed, STOP, re-read the full skill, and resume from the correct checkpoint.

## Overview

FF decomposes any work item into atomic blocks, dispatches them in parallel via Swarm, validates at each gate, and recovers from isolated failures. The plan is built by two sub-agents (structural + adversarial), consolidated by the main agent, acceptance criteria (Gherkin) are written per block by an Acceptance Architect, and the whole package is approved by a judge sub-agent. Only after approval does swarm execution begin. Every sub-agent dispatch carries a Context Package (file excerpts, contracts, skill digests, lessons) — never a thin, one-line handoff.

```
USER INTENT
    ↓
PHASE 0: CLARIFY    → Essence check, gather unknowns, scope the task
PHASE 1: PLAN BUILD → Two sub-agents cross-analyze → consolidate → acceptance (Gherkin) → judge approve
PHASE 2: EXECUTE    → Swarm fan-out per block, gate check, retry
PHASE 3: VALIDATE   → Final gate, cross-check plan vs. reality
PHASE 4: LESSONS    → Capture lessons, report results
```

### Why FF Replaced Sequential Loops

Sequential loops serialize all work: each stage waits for the previous one, failures cascade, and parallelism is impossible. FF inverts this — independent blocks run concurrently, failures are contained to their block, and retries target only the failed rows.

## Phase Transitions

Transitions between phases are strict:

| Transition | Condition |
|------------|-----------|
| Phase 0 → Phase 1 | Essence check resolves all tensions |
| Phase 1 → Phase 2 | Judge returns `{"approved": true}` for plan AND acceptance |
| Phase 2 → Phase 3 | All blocks complete (or fail the gate) |
| Phase 3 → Phase 4 | Validation report produced |

Rules:
- DO NOT skip a step within a phase
- DO NOT stop between steps within a phase without a valid reason
- DO NOT show the plan to the user before the judge approves it

## Phase 0: Clarify

Run the Essence check first (load `essence` skill). Resolve all Lens 4 tensions with the user before proceeding.

Then classify the work type to guide block count:

| Work Type | Characteristics | Block Count |
|-----------|----------------|-------------|
| `bugfix` | Fix existing broken behavior | 2-4 blocks |
| `feature` | New functionality | 4-6 blocks |
| `refactor` | Restructure without behavior change | 3-5 blocks |
| `test` | Write or fix tests | 2-3 blocks |
| `docs` | Documentation, specs, guides | 1-3 blocks |
| `migration` | Move code, update deps, rename | 3-5 blocks |
| `research` | Investigation, analysis, report | 1-2 blocks |

### Auto-Size Rule

FF activates when any of these conditions are met:
- ≥ 3 files affected, OR
- ≥ 5 discrete changes, OR
- Unclear dependencies between parts, OR
- User explicitly requests FF

If the task touches ≤ 2 files with clear instructions, execute inline without FF overhead.

## Context Handoff (MANDATORY)

Sub-agents fail when they have to discover what the orchestrator already knows.
Before EVERY sub-agent dispatch — analysts, Plan Writer, Acceptance Architect,
Judge, executors — the orchestrator assembles and injects a **Context Package**:

| Section | Content |
|---------|---------|
| Session Context | work_type, task title, essence scope and clarifications |
| Plan Slice | the plan sections relevant to this dispatch |
| File Context | relevant excerpts (imports, exports, signatures, interfaces) — the orchestrator READS the in-scope files and injects them |
| Contracts | what this unit consumes from earlier work and produces for later work |
| Acceptance | the Gherkin feature for this dispatch (from Step 1.4) |
| Skill Digest | the rules/conventions relevant to the task, extracted from the loaded skills — never bare skill names |
| Lessons & Decisions | lessons filtered by work_type/scope + session decisions |

Rules:
- The orchestrator reads in-scope files BEFORE dispatch — reading is an orchestrator duty
- Skills are passed as digests (loaded + filtered), never as bare name lists
- Block instructions are self-contained: what to read, what to change, which acceptance to satisfy
- A one-line instruction is a drift symptom, not a handoff

## Phase 1: Plan Build

The plan is **not built by the main agent**. It is built by two sub-agents that
cross-analyze the work item, then consolidated. Before the judge, an Acceptance
Architect writes Gherkin acceptance criteria for every block. The judge approves
the plan, the blocks, and the acceptance together.

The main agent's role in Phase 1:
- Assemble the Context Package for every dispatch
- Dispatch sub-agents (structural + adversarial)
- Merge their outputs
- Fragment the plan into draft blocks
- Dispatch the Acceptance Architect (acceptance build)
- Spawn the judge
- **NOT** to build the plan, write the acceptance, decide what's safe/risky, or execute work

### Step 1.1 — Analyze (Two Sub-Agents)

Dispatch two sub-agents in parallel using `subagentType: explore`, both with the
full Context Package (File Context = the in-scope file inventory with relevant
excerpts; Skill Digest = loaded + filtered, not bare names):

| Sub-Agent | Role | Output |
|-----------|------|--------|
| **Structural Analyst** | Map files, imports, dependencies, risk | `file_map`, `dependency_map`, `risk_assessment`, `conventions` |
| **Adversarial Analyst** | Find what structural missed | `alternative_approaches`, `edge_cases`, `hidden_dependencies`, `ignored_risks`, `worst_case` |

Both run in parallel. Wait for both to complete before proceeding.

### Step 1.2 — Consolidate

The main agent merges A + B responses:

| Situation | Action |
|-----------|--------|
| A says "safe", B says "risky" | Unresolved conflict → return to Step 1.1 with clarified scope |
| B flagged something A missed | Include in the plan |
| B flagged something A covered | Reconcile and proceed |
| No unresolved conflicts | Proceed to fragmentation |

Before fragmenting, verify:
- A + B responses are fully merged
- All conflicts resolved or escalated back to Step 1.1
- The plan document is persisted: `plan/plan.md`

### Step 1.3 — Fragment Into Draft Blocks

The plan is broken into blocks. Each block has:

| Field | Description |
|-------|-------------|
| `id` | Unique identifier (e.g., `block-001`) |
| `scope` | List of files involved |
| `instruction` | Self-contained multi-line instruction: what to read, what to change, which acceptance to satisfy |
| `output` | What to produce |
| `contracts` | `consumes` (from earlier blocks) / `produces` (for later blocks) |
| `acceptance` | Path to this block's Gherkin feature (filled by Step 1.4) |
| `validation` | How to verify it passed — running the block's acceptance tests |
| `autonomy` | `auto`, `semi`, or `manual` |
| `depends_on` | List of block IDs this block depends on |
| `tasks` | List of task IDs for swarm dispatch |

**Fragmentation rules:**
- If a block requires > 5000 tokens of context → split further
- If two blocks modify the same file → make them dependent, not parallel
- If a block has no testable output → reconsider if it's atomic enough
- Maximum 8 blocks — if you need more, re-fragment
- A one-line `instruction` is a protocol violation — the instruction is self-contained

Blocks are **drafts**: the judge validates them in Step 1.5 together with the
plan and acceptance.

### Step 1.4 — Acceptance Build (Acceptance Architect)

Dispatch an **Acceptance Architect sub-agent** (`subagentType: general`) with the
Context Package plus plan, blocks, and both analyses. It writes two artifacts:

1. **`plan/acceptance-plan.md`** — per block: the acceptance tests that must be
   executed, with concrete execution instructions (runner, command, scenarios
   covered). Acceptance is ALWAYS end-user perspective — what the user does,
   what the user observes.
2. **`plan/acceptance/{block_id}.feature`** — strict Gherkin per block:

   ```gherkin
   Feature: {block delivery name}

     Scenario: {happy path}
       Given {concrete precondition}
       When {user action}
       Then {concrete observable outcome}

     Scenario: {edge case from adversarial analysis}
       Given ...
       When ...
       Then ...
   ```

Mandatory coverage per block: happy path, every relevant adversarial edge case,
negative/error paths. Every scenario has a deterministic, concrete expected outcome.

**Scope rule:** the Acceptance Architect writes specification ONLY — it does NOT
run tests, commands, or suites. Unit tests alone NEVER satisfy the acceptance
gate: they may exist as supporting tests, but acceptance is end-user behavior.

### Step 1.5 — Judge

Spawn a dedicated judge sub-agent to validate the plan, the blocks, and the
acceptance criteria. The judge checks:

| Check | Reject If |
|-------|-----------|
| Unresolved A/B conflicts | A says "safe" and B says "risky" |
| Missing B findings | B flagged something not included in plan |
| Block completeness | Any block missing instruction, contracts, acceptance, or validation |
| Context size | Any block requires > 5000 tokens of context |
| Parallel safety | Parallel blocks share state or have conflicting writes |
| Sequential deps | Sequential blocks lack clear dependencies |
| Acceptance existence | Any block without `acceptance/{block_id}.feature` |
| Acceptance level | Acceptance is unit-level instead of end-user behavior |
| Acceptance sufficiency | Unit tests alone are the acceptance |
| Acceptance coverage | An adversarial edge case has no acceptance scenario |
| Acceptance determinism | A scenario has a vague or non-concrete expected outcome |
| Acceptance executability | The acceptance plan lacks concrete test instructions (runner, command) |

Response:
- Pass: `{"approved": true, "message": "Plan and acceptance approved"}` → proceed to Phase 2
- Fail: `{"approved": false, "rejection_reason": "specific reason"}` → return to the failing step (1.2 plan, 1.3 fragmentation, or 1.4 acceptance)

### Step 1.6 — Calculate Autonomy Score

```
clarity    = available_info / needed_info              (0-1)
complexity = 1 - (dependency_count / block_count)      (0-1)
risk       = weighted average of block risk levels      (0-1)

autonomy_score = (clarity * 0.4) + (complexity * 0.4) + ((1 - risk) * 0.2)
```

**Risk levels:**

| Risk Value | Operation Type |
|------------|---------------|
| 0.0 | Read-only operations |
| 0.3 | Create new files |
| 0.5 | Edit existing files |
| 0.7 | Run commands with side effects |
| 1.0 | Destructive operations (hard rule — always blocked) |

**Autonomy thresholds:**

| Score | Mode | Behavior |
|-------|------|----------|
| ≥ 0.8 | FULL AUTO | Execute without asking |
| 0.5–0.7 | SEMI AUTO | Show plan → wait for "go" → execute |
| < 0.5 | MANUAL | Ask before each block |

**Override:** The user can force any mode. "go", "execute", "run it" → full auto. "wait", "show me first", "step by step" → manual.

### Step 1.7 — Present Plan

In SEMI AUTO or MANUAL mode, present:
1. Work type and block count
2. Each block with scope + instruction
3. Acceptance summary — scenario count per block
4. Autonomy mode
5. Relevant lessons loaded

Ask: "Proceed?" Before dispatching Block 0.

## Phase 2: Execute

### Block Execution Loop

For each block in dependency order:

1. If `autonomy == "manual"`, ask user before proceeding. If user says no → HALT.
2. Assemble the block's **Context Package**: read the files in `block.scope`, inject the relevant excerpts, contracts, the full acceptance Gherkin feature, skill digests, and filtered lessons (see Context Handoff).
3. If block has ≥ 2 independent tasks, dispatch via Swarm (sequential execution is FORBIDDEN).
4. Run gate check on results — acceptance tests included.
5. If block passed, log to state (with acceptance results) and proceed to next block.

### Swarm Dispatch

When a block has ≥ 2 independent tasks, dispatch via the Swarm skill:

- Create a table from `block.tasks`
- Run with `subagentType: "explore"` (or `"general"` for write tasks)
- The dispatch context is the block's Context Package — never a bare skill-name list
- Use `responseSchema` matching the block's guardrail structure
- Response schema requires: `status` (pass/fail/skip), `output_path`, `summary`, `error`

### Gate Check

The acceptance tests are run mechanically, exactly as `acceptance-plan.md`
instructs (runner + command). A failing acceptance scenario counts as a failed
row in the table below.

| Condition | Action |
|-----------|--------|
| `failed == 0` (acceptance included) | Block passed → proceed |
| `failed > 0` AND `failed <= completed * 0.3` | Retry failed rows (max 1 retry per row). If still failed → escalate to user |
| `failed > completed * 0.3` | HALT — block failed fundamentally. Present which tasks failed, why, suggest re-fragmentation |

### Escalation Protocol

1. Retry failed rows once (max 1 retry per row)
2. If retry fails → escalate with task ID, scope, what was attempted, error output, suggested fixes
3. Wait for human input
4. If human says "fix it yourself" → one more attempt with guidance
5. If that fails → HALT, mark as blocked

## Phase 3: Validate

### Step 3.1 — Final Gate

After all blocks complete:
1. Run the full acceptance suite — every block's acceptance tests, per `acceptance-plan.md`
2. Run the full test suite
3. Verify no regressions in untouched areas
4. Confirm all Gherkin acceptance scenarios are met

### Step 3.2 — Cross-Check

Compare the judge-approved plan against actual changes:
- Did every approved block execute?
- Did any block produce unexpected side effects?
- Are there changes that were not in the plan?

### Step 3.3 — Report

Produce a structured summary:

```markdown
## FF Report — {work_type}: {task_title}

**Blocks:** {N} completed, {M} retried
**Tasks:** {total} micro-tasks, {passed} pass, {failed} fail, {skipped} skip
**Files Changed:** {list}
**Acceptance:** {status} — {scenarios_passed}/{scenarios_total} Gherkin scenarios
**Tests:** {status} — {pass_count}/{total_count}
**Duration:** {time}
**Autonomy Mode:** {mode}

### Failures
{list of failed tasks with reasons}

### Lessons
{new lessons captured this run}
```

### Step 3.4 — Capture Lessons

For every failure that was escalated or retried:
1. Extract what failed, why, how it was fixed
2. Format as lesson object
3. Append to `.ff/lessons.json` (create if doesn't exist)

## Phase 4: Lessons

Lessons are captured after each failure and compiled into the final report. The lessons file is append-only and loaded at Phase 1 to inform planning.

### Lesson Schema

```json
{
  "id": "lesson-{N}",
  "timestamp": "ISO date",
  "work_type": "bugfix",
  "context": "Brief context of the failure",
  "error": "What went wrong",
  "correction": "How it was fixed",
  "prevention": "Rule to prevent recurrence"
}
```

## Block Structure — YAML Example

```yaml
blocks:
  - id: block-001
    scope: ["src/login.js", "src/auth.js"]
    instruction: |
      Implement the login flow.
      Read: src/auth.js, src/login.js (excerpts in File Context).
      Change: wire the form to auth.verify, persist session, redirect.
      Acceptance: every scenario in acceptance/block-001.feature must pass.
    output: "files modified with the login flow"
    contracts:
      consumes: []
      produces: ["JWT sign/verify functions", "session storage"]
    acceptance: acceptance/block-001.feature
    validation: "run block-001 acceptance tests (acceptance-plan.md) — all scenarios pass"
    autonomy: "semi"
    depends_on: []
    tasks: [t001, t002]

  - id: block-002
    scope: ["src/api/users.js"]
    instruction: |
      Add the profile endpoint.
      Read: src/api/users.js (excerpts in File Context), block-001 session storage.
      Change: add GET /users/profile reading the session.
      Acceptance: every scenario in acceptance/block-002.feature must pass.
    output: "file modified with the profile endpoint"
    contracts:
      consumes: ["session storage (block-001)"]
      produces: ["GET /users/profile"]
    acceptance: acceptance/block-002.feature
    validation: "run block-002 acceptance tests (acceptance-plan.md) — all scenarios pass"
    autonomy: "auto"
    depends_on: [block-001]
    tasks: [t003]
```

## State Management

### `.ff/state.json`

Updated after each block completion. The `summary` field is updated every 3 blocks
(context budget rule). Enables resume if the session is interrupted.

```json
{
  "session_id": "ff-{date}-{hash}",
  "work_type": "bugfix",
  "task_title": "...",
  "status": "running",
  "current_block": "block-001",
  "blocks_completed": [],
  "blocks_pending": [],
  "tasks": {
    "total": 12,
    "passed": 8,
    "failed": 2,
    "skipped": 2,
    "retried": 2
  },
  "autonomy_mode": "semi",
  "summary": "Blocks 1-3 completed: auth middleware, login endpoint, session storage. Block 4 in progress: API routes.",
  "started_at": "ISO date",
  "updated_at": "ISO date"
}
```

### `.ff/lessons.json`

Array of lesson objects. Append-only. Loaded at Phase 1 to inform planning. See Lesson Schema above.

## Hard Rules

These operations ALWAYS require human confirmation, regardless of autonomy score:

| Operation | Action |
|-----------|--------|
| `rm`, `rm -rf`, `del`, destructive file ops | Always ask |
| `git push --force`, `git reset --hard` | Always ask |
| Writes to Firebase / Firestore / external DBs | Always ask |
| Changes to `.env` or env config files | Always ask |
| Changes to CI/CD pipelines or deployment configs | Always ask |
| Any operation outside project workspace root | Always block |

### Soft Rules

| Operation | Default Mode |
|-----------|-------------|
| Read operations | Always auto |
| Write to new files | Auto if scope is clear |
| Write to existing files | Semi-auto |
| Test execution | Always auto |
| Code review | Always auto |
| Dependency installation | Semi-auto (show what will be installed) |

## Anti-Patterns

### Do

- Fragment aggressively — if a task feels big, split it
- Validate at every block gate — don't let failures propagate
- Capture lessons from every failure
- Use the simplest block structure that works
- Respect autonomy score — ask when uncertain
- Execute tasks in parallel when swarm is applicable
- Acceptance before judgment — every block gets Gherkin acceptance criteria before the judge
- Hand off rich context — build the full Context Package before every dispatch

### Don't

- Create more than 8 blocks — if you need more, the fragmentation is wrong
- Put more than 12 tasks in a block — re-fragment or split into separate FF runs
- Skip test validation — validation is mandatory
- Let one failed block trigger a full restart — retry only failed rows
- Encode assumptions in the harness — models improve, assumptions stale
- Use FF for a single-file, single-change task — just do it inline
- Use waves — waves are the same problem as graphs (sequential dependencies)
- Execute tasks one-by-one when swarm is applicable — this defeats the purpose of FF
- Show the plan to the user before the judge approves it — the judge is not optional
- Stop after consolidation without dispatching the judge — this is a hard requirement
- Accept a plan whose acceptance is missing or unit-level — the judge must reject it
- Run tests inside the Acceptance Build step — that step writes specification only
- Dispatch sub-agents with thin context — skill names and one-line instructions are not a handoff

## Integration

FF uses these skills as components:

| Skill | Phase | Purpose |
|-------|-------|---------|
| `essence` | Phase 0 | Clarify intent, detect traps |
| Testing skills (discovered) | Phase 1 | Acceptance Architect digests their conventions into acceptance instructions |
| `swarm` | Phase 2 | Fan-out parallel micro-tasks |

FF does NOT use:
- LangChain, LangGraph, or any code-based framework
- BMad story/sprint files (unless the project specifically requires them)
- The `.eng/` loop or graph orchestrator
- Wave templates (waves are the same problem as graphs)
