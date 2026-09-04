---
name: ff
description: >-
  Fail Fast — orchestrator pattern for parallel swarm-based software development.
  Two sub-agents cross-analyze the work item, consolidate, and a judge validates
  the plan before swarm execution. Fragment any work item into atomic blocks,
  dispatch parallel tasks via Swarm, validate at each gate, recover isolated failures.
  Use when the user says "FF", "fail fast", "fragment this", or when working on
  tasks that benefit from parallel decomposition: bugfix suites, feature
  implementation, test rewriting, code refactoring, documentation generation,
  and any multi-file change.
---

# FF — Fail Fast Protocol

## Core Principle

One orchestrator (the main agent), many specialized workers (sub-agents via Swarm).
Every unit of work is atomic, validated in isolation, and fails fast without
contaminating siblings.

**Not a framework. Not a graph. Not waves. A protocol.** The agent follows this skill's
instructions. Swarm handles fan-out. Each block validates before the next executes.

---

## Protocol Overview

```
USER INTENT
    ↓
PHASE 0: CLARIFY    → Essence check, gather unknowns, scope the task
PHASE 1: PLAN BUILD → Two sub-agents cross-analyze → consolidate → judge approve
PHASE 2: EXECUTE    → Swarm fan-out per block, gate check, retry
PHASE 3: VALIDATE   → Final gate, cross-check plan vs. reality
PHASE 4: LESSONS    → Capture lessons, report results
```

Each phase is a distinct step. The agent loads instructions for one phase,
completes it, then moves to the next. Never loads all phases at once.

**Phase transitions are strict:**
- Phase 0 → Phase 1: Only after essence check resolves all tensions
- Phase 1 → Phase 2: Only after judge returns `{"approved": true}`
- Phase 2 → Phase 3: Only after all blocks complete (or fail the gate)
- DO NOT skip a step within a phase
- DO NOT stop between steps within a phase without a valid reason

---

## Phase 0: CLARIFY

Run Essence Check first (load skill "essence"). Resolve all Lens 4 tensions
with the user before proceeding.

Then determine the work type:

| Work Type | Characteristics | Block Count |
|-----------|----------------|-------------|
| `bugfix` | Fix existing broken behavior | 2-4 blocks |
| `feature` | New functionality | 4-6 blocks |
| `refactor` | Restructure without behavior change | 3-5 blocks |
| `test` | Write or fix tests | 2-3 blocks |
| `docs` | Documentation, specs, guides | 1-3 blocks |
| `migration` | Move code, update deps, rename | 3-5 blocks |
| `research` | Investigation, analysis, report | 1-2 blocks |

**Auto-size rule:** If the task touches ≤ 2 files and has clear instructions,
execute inline without FF overhead. FF activates when:
- ≥ 3 files, OR
- ≥ 5 discrete changes, OR
- Unclear dependencies between parts, OR
- User explicitly requests FF

---

## Phase 1: PLAN BUILD (MANDATORY)

This is the critical phase. The plan is **not built by the main agent**.
It is built by two sub-agents that cross-analyze the work item, then
consolidated and approved by a judge.

**The main agent's role in Phase 1:**
- Dispatch sub-agents (structural + adversarial)
- Merge their outputs
- Spawn the judge
- Fragment the approved plan into blocks
- **NOT** to build the plan, decide what's safe/risky, or execute work

### Step 1.1: Analyze (Two Sub-Agents Cross-Check)

Dispatch two sub-agents in parallel. Both use `subagentType: explore` but with different prompts.

**Sub-Agent A — Structural Analyst:**
```
You are a structural analyst. Your job is to map the technical landscape.

Given the work item and scope:
1. Identify all files that need changing (and why)
2. Map imports/exports — who depends on whom?
3. Identify shared state, external APIs, database writes
4. Assess risk level (low/medium/high) and explain why
5. List any known patterns or conventions in the codebase that must be followed

Return a structured summary with: file_map, dependency_map, risk_assessment, conventions.
```

**Sub-Agent B — Adversarial Analyst:**
```
You are an adversarial analyst. Your job is to find what A might have missed.

Given the work item and scope:
1. What are the alternative approaches? (If A only sees one way, find others)
2. What edge cases could break this?
3. What hidden dependencies might exist? (config files, env vars, external services)
4. What risks did A ignore or minimize?
5. What is the worst-case scenario for each proposed change?

Return a structured summary with: alternative_approaches, edge_cases, hidden_dependencies, ignored_risks, worst_case.
```

**Execution:**
- Both sub-agents run in parallel
- Wait for both to complete
- **Do not proceed** until both have returned

### Step 1.2: Consolidate

The main agent merges A + B responses:

- If A says "safe" and B says "risky" → **unresolved conflict** → return to Step 1.1 with a new round (two new sub-agents, clarified scope)
- If B flagged something A missed → include in the plan
- If B flagged something A covered → reconcile and proceed
- If no unresolved conflicts → proceed to judge

**Before spawning judge, verify:**
- [ ] A + B responses are fully merged
- [ ] All conflicts are resolved or escalated back to Step 1.1
- [ ] Blocks have structure: scope, input, output, validation
- [ ] Dependencies between blocks are defined

**CRITICAL:** IMMEDIATELY dispatch judge sub-agent. DO NOT present the plan to the user. DO NOT execute any work. DO NOT wait for user confirmation. The judge validates before anything is shown.

### Step 1.3: Judge

Spawn a **dedicated judge sub-agent** (exists only to validate the plan, then exits). This step is **mandatory** — the plan is never shown to the user, never executed, without judge approval.

```
You are a judge. Your job is to validate the plan before execution.

You will receive:
1. A consolidated plan from two analysts:
   - Sub-Agent A (Structural Analyst): maps files, imports, dependencies, risk
   - Sub-Agent B (Adversarial Analyst): alternative approaches, edge cases, hidden dependencies
2. A consolidation summary that attempts to reconcile A and B

Your task:
1. Read the consolidated plan and the reconciliation
2. Check for unresolved conflicts between A and B
   - If A says "safe" and B says "risky" → unresolved conflict → reject
   - If B flagged something A missed → must be included → reject if not
   - If B flagged something A covered → reconciled → OK
3. Validate each block has:
   - scope: list of files involved
   - input: what to read
   - output: what to produce
   - validation: how to verify it passed
4. Check that no block requires > 5000 tokens of context
5. Verify that parallel blocks are truly independent (no shared state or conflicting writes)
6. Verify that sequential blocks have clear dependencies

If the plan passes all criteria:
- Return: {"approved": true, "message": "Plan approved"}

If the plan fails any criteria:
- Return: {"approved": false, "rejection_reason": "specific reason"}

Do not execute any work. Do not suggest changes. Only approve or reject.
```

**If approved:** Emit approved blocks → Phase 2
**If rejected:** Return to Step 1.1 (two new sub-agents)

### Step 1.4: Fragment into Blocks

The approved plan is broken into blocks (not waves). Each block:

- Has **one scope**: one file, one function, one component, one test spec
- Has **clear input/output**: what files to read, what to produce
- Has **a validation criterion**: how to verify it passed
- Has **an autonomy level**: auto / semi / manual (see Autonomy Harness)

**Fragmentation rules:**
- If a block requires > 5000 tokens of context → split further
- If two blocks modify the same file → make them dependent, not parallel
- If a block has no testable output → reconsider if it's atomic enough

**Block structure:**
```yaml
blocks:
  - id: block-001
    scope: ["src/login.js", "src/auth.js"]
    input: "ler imports, exports, dependências"
    output: "arquivos modificados com nova lógica"
    validation: "npm test auth.test.js && lint pass"
    autonomy: "semi"
    depends_on: []
    tasks: [t001, t002]

  - id: block-002
    scope: ["src/api/users.js"]
    input: "ler block-001 outputs"
    output: "arquivo modificado"
    validation: "npm test users.test.js"
    autonomy: "auto"
    depends_on: [block-001]
    tasks: [t003]
```

### Step 1.5: Calculate Autonomy Score

For the overall plan, calculate:

```
clarity   = available_info / needed_info       (0-1)
complexity = 1 - (dependency_count / block_count)  (0-1)
risk      = weighted average of block risk levels (0-1)

risk_levels:
  0.0  = read-only operations
  0.3  = create new files
  0.5  = edit existing files
  0.7  = run commands with side effects
  1.0  = destructive operations (hard rule — always blocked)

autonomy_score = (clarity * 0.4) + (complexity * 0.4) + ((1 - risk) * 0.2)
```

| Score | Mode | Behavior |
|-------|------|----------|
| ≥ 0.8 | FULL AUTO | Execute without asking |
| 0.5-0.7 | SEMI AUTO | Show plan, wait for confirmation, then execute |
| < 0.5 | MANUAL | Ask before each block |

**Override:** The user can force any mode. "go", "execute", "run it" → full auto.
"wait", "show me first", "step by step" → manual.

### Step 1.6: Present Plan

In SEMI AUTO or MANUAL mode, present:
1. Work type and block count
2. Each block with scope + instruction
3. Autonomy mode
4. Relevant lessons loaded

Ask: "Proceed?" Before dispatching Block 0.

---

## Phase 2: EXECUTE

### Block Execution Loop

```
FOR each block B in plan (in dependency order):
    IF B.autonomy == "manual":
        ask user: "Ready for block {B.id}? {B.task_count} tasks."
        IF user says no → HALT

    IF block has ≥2 independent tasks:
        YOU MUST dispatch Swarm — sequential execution is FORBIDDEN.
            create table from B.tasks
            run table with instruction + context per row
            responseSchema = B.guardrail structure

    Gate check:
        completed = result.completed
        failed = result.failed

        IF failed > 0 AND failed <= completed * 0.3:
            retry failed rows (filter: exists: false)
            IF still failed → escalate to user with specifics
        IF failed > completed * 0.3:
            HALT — block failed, something is fundamentally wrong
            Present: which tasks failed, why, suggest re-fragmentation

    IF block passed:
        log to state: block completed, timestamp, task counts
        proceed to next block
```

### Swarm Dispatch Pattern

Execute this pattern exactly — it is not pseudo-code. This is the required mechanism for parallel execution.

```javascript
const { create, run } = await import("@/skills/swarm");

const table = await create({
  tasks: blockTasks.map(t => ({
    id: t.id,
    scope: t.scope,
    instruction: t.instruction,
    autonomy: t.autonomy,
    file: t.file,       // if single-file task
  }))
});

const result = await run(table.id, {
  subagentType: "explore",  // or "general" for write tasks
  instruction: t.instruction,
  context: sharedContext,   // lessons, decisions, architecture notes
  responseSchema: {
    type: "object",
    properties: {
      status: { type: "string", enum: ["pass", "fail", "skip"] },
      output_path: { type: "string" },
      summary: { type: "string" },
      error: { type: "string" },
    },
    required: ["status"],
  },
});

// result → { completed, failed, skipped, failures }
```

---

## Phase 3: VALIDATE

### Step 3.1 — Final Gate

After all blocks complete:
1. Run the full test suite (`npm test`)
2. Verify no regressions in untouched areas
3. Confirm all acceptance criteria are met

### Step 3.2 — Cross-Check

Compare the judge-approved plan against the actual changes:
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
1. Extract: what failed, why, how it was fixed
2. Format as lesson object
3. Append to `.ff/lessons.json` (create if doesn't exist)

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

---

## Phase 4: LESSONS

This phase is integrated into Phase 3. Lessons are captured after each failure and compiled into the final report.

---

## Autonomy Harness

The autonomy harness is ALWAYS active. It governs what the FF protocol
can do autonomously. Autonomy comes from clarity of information, not from
the nature of the task.

### Hard Rules (Never Override)

These operations ALWAYS require human confirmation, regardless of autonomy score:

- `rm`, `rm -rf`, `del`, any destructive file operation
- `git push --force`, `git reset --hard`, any destructive git operation
- Writes to Firebase / Firestore / external databases
- Changes to `.env` or environment configuration files
- Changes to CI/CD pipelines or deployment configs
- Any operation outside the project workspace root

### Soft Rules (Autonomy Score Based)

- **Read operations:** Always auto (score doesn't matter)
- **Write to new files:** Auto if scope is clear
- **Write to existing files:** Semi-auto default
- **Test execution:** Always auto
- **Code review:** Always auto
- **Dependency installation:** Semi-auto (show what will be installed)

### Escalation Protocol

When a block fails the gate:
1. Retry failed rows once (max 1 retry per row)
2. If retry fails → escalate with:
   - Task ID and scope
   - What was attempted
   - Error output
   - Suggested fix options
3. Wait for human input
4. If human says "fix it yourself" → one more attempt with human's guidance
5. If that fails → HALT, mark as blocked

---

## State Management

### File: `.ff/state.json`

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
  "started_at": "ISO date",
  "updated_at": "ISO date"
}
```

The agent updates state.json after each block completion. Enables resume
if the session is interrupted.

### File: `.ff/lessons.json`

Array of lesson objects. Append-only. Loaded at Phase 1 (plan).
See Phase 3.4 for lesson format.

---

## Integration with Existing Skills

FF uses these skills as components:

| Skill | When Used | Purpose |
|-------|-----------|---------|
| `essence` | Phase 0 | Clarify intent, detect traps |
| `swarm` | Phase 2 | Fan-out parallel micro-tasks |

FF does NOT use:
- LangChain, LangGraph, or any code-based framework
- BMad story/sprint files (unless the project specifically requires them)
- The `.eng/` loop or graph orchestrator
- Wave templates (waves are the same problem as graphs)

---

## Anti-Patterns

**Do:**
- Fragment aggressively — if a task feels big, split it
- Validate at every block gate — don't let failures propagate
- Capture lessons from every failure
- Use the simplest block structure that works
- Respect autonomy score — ask when uncertain

**Don't:**
- Create more than 8 blocks — if you need more, the fragmentation is wrong
- Put more than 12 tasks in a block — re-fragment or split into separate FF runs
- Skip the test validation — validation is mandatory
- Let one failed block trigger a full restart — retry only failed rows
- Encode assumptions in the harness — models improve, assumptions stale
- Use FF for a single-file, single-change task — just do it inline
- Use waves — waves are the same problem as graphs (sequential dependencies)
- Execute tasks one-by-one when swarm is applicable — this defeats the purpose of FF
- Show the plan to the user before the judge approves it — the judge is not optional
- Stop after consolidation without dispatching the judge — this is a hard requirement

---

## Next

This protocol is self-contained. When invoked, the agent follows Phase 0
through Phase 4 sequentially. Load the autonomy harness as needed.

For the autonomy harness rules, refer to the full harness specification.
