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

## ⚠️ BEFORE ANYTHING ELSE: Read `harness.md`

**This is mandatory.** The harness contains pre/post hooks that enforce protocol compliance.

Before you do ANY of the following:
- Start a new FF session
- Resume an existing session
- Transition between phases
- Declare FF complete

**Read `harness.md` (same directory as this skill) and execute the applicable hook.**

The harness is your mechanical guardrail. Skipping it causes drift.

---

## Anti-Drift Protocol (MANDATORY — Read Every Phase)

As context grows, the orchestrator may forget protocol rules. This section prevents that.

### Before EVERY Phase Transition

1. **Read `harness.md`** (same directory as this skill) — execute the applicable pre/post hook
2. **Read `manifest.md`** (same directory as this skill) — the compressed checklist for the upcoming phase gate
3. **Assert your role** — "I am the orchestrator. I dispatch sub-agents. I do not write application code."
4. **Read `.ff/state.json`** — confirm current position from the state file, not from memory

### Context Budget Rule

After every 3 blocks completed in Phase 2:
1. Summarize all completed blocks into one paragraph
2. Write the summary to `.ff/state.json` under `summary` field
3. Announce: "Context summary created. Continuing from block {N}."

This keeps the conversation window manageable and ensures the protocol checklist
remains accessible throughout long runs.

### Drift Symptoms — If You Notice Any, STOP and Re-Read This Skill

| Symptom | What Happened | Fix |
|---------|---------------|-----|
| Writing code yourself | Forgot orchestrator role | Re-dispatch to sub-agent |
| Running tasks sequentially | Forgot Swarm dispatch | Use Swarm for ≥ 2 independent tasks |
| Skipping judge | Thought "plan looks fine" | Judge is never optional |
| Showing plan to user before judge | Impatience | Judge validates first, then user sees approved plan |
| Building plan yourself | Took over sub-agent role | Dispatch Structural + Adversarial analysts |
| Not updating state.json | Relying on memory | Write state after every block |
| Not persisting traces | Forgetting disk persistence | Write every sub-agent/block output to `.ff/traces/` |
| Forgetting lessons | Context overflow | Re-read `.ff/lessons.json` |
| Session not resumable | State not on disk | Check `.ff/state.json` and `.ff/traces/{session_id}/` |

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

**BEFORE STARTING:** Read `.ff/state.json` to confirm session context. Assert: "I am the orchestrator."

**INITIALIZE SESSION (MANDATORY):** Create session metadata before doing any work.

1. Generate `session_id`: `ff-{YYYYMMDD}-{NNN}` (NNN = sequential, check `.ff/traces/` for next number)
2. Create trace directory: `.ff/traces/{session_id}/`
3. Write `.ff/traces/{session_id}/session.json`:

```json
{
  "session_id": "ff-20260914-001",
  "user_request": "<verbatim user request>",
  "work_type": "feature",
  "started_at": "ISO date",
  "status": "running"
}
```

4. Initialize `.ff/state.json`:

```json
{
  "session_id": "ff-20260914-001",
  "work_type": "feature",
  "task_title": "...",
  "status": "running",
  "current_phase": "phase_0",
  "current_block": "",
  "trace_dir": ".ff/traces/ff-20260914-001",
  "blocks_completed": [],
  "blocks_pending": [],
  "skills": [],
  "tasks": { "total": 0, "passed": 0, "failed": 0, "skipped": 0, "retried": 0 },
  "autonomy_mode": "semi",
  "summary": "",
  "started_at": "ISO date",
  "updated_at": "ISO date",
  "completed_at": null,
  "files_changed": [],
  "files_created": [],
  "decisions": []
}
```

**UPDATE `state.json` at every phase transition:** Always set `current_phase`, `updated_at`, and relevant fields. Never rely on conversation memory.

Run Essence Check first (load skill "essence"). Resolve all Lens 4 tensions
with the user before proceeding.

**PERSIST ESSENCE OUTPUT:** Write essence check results to `.ff/traces/{session_id}/essence.md`:

```markdown
# Essence Check — {session_id}

## User Request
{verbatim}

## Clarifications
{questions asked and answers received}

## Work Type
{classified work type}

## Scope
{agreed scope}
```

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

### Step 0.2: Skill Discovery (MANDATORY)

After essence check, discover which skills apply to this work. These skills will be injected into all sub-agent dispatches so they can progressively load context during execution.

**Discover skills by analyzing:**

1. **Work type mapping:**
   | Work Type | Default Skills |
   |-----------|----------------|
   | `bugfix` | `bug-analysis` |
   | `feature` | (none — scope-driven) |
   | `refactor` | `enterprise-architecture-standards` |
   | `test` | `comprehensive-test-strategy` |
   | `migration` | `release-deployment-safety` |

2. **File patterns in scope:**
   | Pattern | Skill |
   |---------|-------|
   | `*.py`, FastAPI imports, `pydantic`, `sqlalchemy` | `python-fastapi-coding-conventions` |
   | `*.test.py`, `tests/`, `conftest.py` | `python-fastapi-test-conventions` |
   | Auth, JWT, tokens, passwords, sessions | `owasp-secure-coding-bdd` |
   | `*.ts`, `*.tsx`, React, Next.js | `react`, `nextjs` |
   | `prisma/`, schema, migrations, queries | `prisma-client-api` |
   | `langchain`, `langgraph`, agents | `ecosystem-primer` (+ specific skill by framework) |
   | RAG, embeddings, vector store | `langchain-rag` |
   | Human-in-the-loop, approval flows | `langgraph-human-in-the-loop` |
   | MCP server, tools, external integrations | `mcp-builder` |
   | API design, routes, endpoints | `api-designer` or `implementing-api-patterns` |
   | Database schema, indexes, queries | `database-design` |
   | Security, encryption, secrets | `security-review` |
   | PII, GDPR, CCPA, data retention | `compliance-data-lifecycle` |
   | Deploy, release, migration scripts | `release-deployment-safety` |

3. **Project-level AGENTS.md:** If the project has skill mappings (e.g., "Working on X → load skill Y"), honor them.

**PERSIST SKILLS:** Add discovered skills to `.ff/state.json`:

```json
{
  "skills": ["python-fastapi-coding-conventions", "owasp-secure-coding-bdd"]
}
```

**PERSIST to trace:** Write `.ff/traces/{session_id}/skills.md`:

```markdown
# Skills — {session_id}

## Discovered Skills
- skill-name: reason for inclusion
```

These skill references will be injected into every sub-agent dispatch in Phases 1 and 2.

---

## Phase 1: PLAN BUILD (MANDATORY)

**GATE CHECK:** Before entering Phase 1, read `manifest.md` — verify Phase 0 → Phase 1 gate.
If any item fails, return to Phase 0.

**ROLE ASSERTION:** You are the orchestrator. You dispatch sub-agents. You do NOT build the plan yourself.

Phase 1 has three stages:
1. **Analyze** — two sub-agents cross-check the work item
2. **Build Plan Document** — one sub-agent writes the comprehensive plan
3. **Judge** — judge validates the plan document
4. **Fragment** — the approved plan is split into swarm-executable blocks

### Step 1.1: Analyze (Two Sub-Agents Cross-Check)

Dispatch two sub-agents in parallel. Both use `subagentType: explore` but with different prompts.

**Include skill references in both prompts:**
```
## Applicable Skills

Before executing, load these skills using the skill tool:
{skills_list}

Skills provide conventions, patterns, and rules. Load them progressively as needed.
```

**Sub-Agent A — Structural Analyst:**
```
You are a structural analyst. Your job is to map the technical landscape.

## Applicable Skills
Before executing, load these skills using the skill tool:
- {skill_name_1}: reason
- {skill_name_2}: reason

Skills provide conventions, patterns, and rules. Load them progressively as needed.

Given the work item and scope:
1. Identify all files that need changing (and why)
2. Map imports/exports — who depends on whom?
3. Identify shared state, external APIs, database writes
4. Assess risk level (low/medium/high) and explain why
5. List any known patterns or conventions in the codebase that must be followed
6. Note which skills you loaded and how they informed your analysis

Return a structured summary with: file_map, dependency_map, risk_assessment, conventions, skills_used.
```

**Sub-Agent B — Adversarial Analyst:**
```
You are an adversarial analyst. Your job is to find what A might have missed.

## Applicable Skills
Before executing, load these skills using the skill tool:
- {skill_name_1}: reason
- {skill_name_2}: reason

Skills provide conventions, patterns, and rules. Load them progressively as needed.

Given the work item and scope:
1. What are the alternative approaches? (If A only sees one way, find others)
2. What edge cases could break this?
3. What hidden dependencies might exist? (config files, env vars, external services)
4. What risks did A ignore or minimize?
5. What is the worst-case scenario for each proposed change?
6. Note which skills you loaded and how they informed your analysis

Return a structured summary with: alternative_approaches, edge_cases, hidden_dependencies, ignored_risks, worst_case, skills_used.
```

**Execution:**
- Both sub-agents run in parallel
- Wait for both to complete
- **Do not proceed** until both have returned
- **PERSIST OUTPUTS:** Write each sub-agent's response to disk:
  - `.ff/traces/{session_id}/plan/structural.json`
  - `.ff/traces/{session_id}/plan/adversarial.json`

### Step 1.2: Reconcile and Build Plan Document

**Reconcile:** The main agent checks A + B for conflicts:
- If A says "safe" and B says "risky" on the same item → **unresolved** → return to Step 1.1
- If B flagged something A missed → must be included
- If no unresolved conflicts → proceed

**Build Plan:** Dispatch a **Plan Writer sub-agent** (use `subagentType: general`) to create the comprehensive plan document.

Pass it the essence check, structural analysis, adversarial analysis, and skill references as context.

```
You are a plan writer. Your job is to create a comprehensive, detailed plan document.

## Applicable Skills
Load these skills using the skill tool before writing the plan:
- {skill_name_1}: reason
- {skill_name_2}: reason

Skills provide conventions, patterns, and rules. Load them progressively as needed.
Note which skills informed your planning decisions.

You will receive:
1. Essence check output (scope, clarifications, work type)
2. Structural analysis (files, dependencies, risks, conventions)
3. Adversarial analysis (edge cases, hidden dependencies, worst cases)

Produce a detailed plan document with these sections:

## Plan: {title}

### Scope
What this plan covers and does not cover.

### Approach
The chosen approach, why it was chosen, alternatives considered.

### Files Affected
Complete list of files to create, modify, delete, with justification for each.

### Dependencies
What depends on what. Execution order. Which changes can be parallelized.

### Detailed Tasks
Numbered list of ALL tasks required. Each task should be:
- Specific enough that a sub-agent can execute it independently
- Self-contained: includes what to read, what to change, what to produce
- Testable: has a clear pass/fail criterion

### Risks and Mitigations
Identified risks and how they are mitigated.

### Validation
How to verify the entire plan succeeded:
- Tests to run
- Manual checks needed
- Acceptance criteria from essence check

### Edge Cases Handled
Edge cases identified by adversarial analysis and how each is handled.

### Skills Used
Which skills were loaded and how they informed planning decisions.

Write the plan in clear markdown. Be exhaustive — this is the master plan that will be fragmented into execution blocks.
```

**PERSIST PLAN:** Write the plan to `.ff/traces/{session_id}/plan/plan.md`.

### Step 1.3: Judge

Spawn a **dedicated judge sub-agent** (exists only to validate the plan, then exits). This step is **mandatory** — the plan is never shown to the user, never executed, without judge approval.

```
You are a judge. Your job is to validate the plan before execution.

You will receive:
1. The comprehensive plan document
2. Structural analysis
3. Adversarial analysis

Your task:
1. Verify all unresolved conflicts between structural and adversarial are addressed
2. Verify every file mentioned has a clear purpose
3. Verify dependencies are correctly ordered
4. Verify each task is specific enough for independent execution
5. Verify edge cases from adversarial analysis are handled
6. Verify validation criteria are concrete and testable
7. Verify no task requires > 5000 tokens of context (if so, it's not fragmented enough)

If the plan passes all criteria:
- Return: {"approved": true, "message": "Plan approved"}

If the plan fails any criteria:
- Return: {"approved": false, "rejection_reason": "specific reason with section reference"}

Do not execute any work. Only approve or reject.
```

**PERSIST JUDGE DECISION:** Write judge output to `.ff/traces/{session_id}/plan/judge.json`:

```json
{
  "approved": true,
  "message": "Plan approved",
  "reviewed_at": "ISO date"
}
```

**If approved:** Proceed to Step 1.4
**If rejected:** Return to Step 1.2 (rewrite plan addressing rejection reasons)

### Step 1.4: Fragment into Blocks

The approved plan document is now broken into execution blocks for swarm dispatch.
The main agent performs this fragmentation.

**Fragmentation rules:**
- Each block = one atomic unit of work
- If two blocks modify the same file → make them dependent, not parallel
- If a block requires > 5000 tokens → split further
- Parallel blocks must be truly independent (no shared writes)
- Group related tasks into blocks for swarm efficiency

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
    skills: ["owasp-secure-coding-bdd", "python-fastapi-coding-conventions"]
    tasks: [t001, t002]

  - id: block-002
    scope: ["src/api/users.js"]
    input: "ler block-001 outputs"
    output: "arquivo modificado"
    validation: "npm test users.test.js"
    autonomy: "auto"
    depends_on: [block-001]
    skills: ["python-fastapi-coding-conventions"]
    tasks: [t003]
```

**Per-block skills:** Each block inherits global skills from Phase 0 discovery, plus block-specific skills based on its scope. The orchestrator assigns skills during fragmentation.

**PERSIST BLOCKS:** Write block list to `.ff/traces/{session_id}/plan/blocks.yaml`.

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

**UPDATE STATE:** Set `current_phase: "phase_1"`, add block list to `blocks_pending`, set `autonomy_mode`.

In SEMI AUTO or MANUAL mode, present:
1. Work type and block count
2. Each block with scope + instruction
3. Autonomy mode
4. Relevant lessons loaded

Ask: "Proceed?" Before dispatching Block 0.

---

## Phase 2: EXECUTE

**GATE CHECK:** Before entering Phase 2, read `manifest.md` — verify Phase 1 → Phase 2 gate.
If any item fails, return to Phase 1. The judge must have approved the plan.

**ROLE ASSERTION:** You are the orchestrator. You dispatch Swarm for parallel tasks. You do NOT execute tasks sequentially.

### Block Execution Loop

Before each block, read `.ff/state.json` to confirm your position.
If 3 or more blocks have completed since your last context summary, create one now.

```
FOR each block B in plan (in dependency order):
    CHECKPOINT: Read manifest.md "Phase 2 Block Gate" section
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
        PERSIST block trace: write `.ff/traces/{session_id}/blocks/{block_id}.json`:
            {
              "block_id": "block-001",
              "scope": ["src/file.ts"],
              "tasks": [...],
              "completed": N,
              "failed": N,
              "retried": N,
              "completed_at": "ISO date",
              "files_changed": ["src/file.ts"],
              "summary": "Brief summary of what was done"
            }
        UPDATE state.json:
            - Add block to blocks_completed
            - Remove block from blocks_pending
            - Set current_block to next block
            - Update task counts
            - Add changed files to files_changed / files_created
        proceed to next block
```

### Swarm Dispatch Pattern

Execute this pattern exactly — it is not pseudo-code. This is the required mechanism for parallel execution.

**CRITICAL:** Skills are injected into `context` as references. Sub-agents load them progressively using the skill tool — they don't receive full skill content upfront.

```javascript
const { create, run } = await import("@/skills/swarm");

const table = await create({
  tasks: blockTasks.map(t => ({
    id: t.id,
    scope: t.scope,
    instruction: t.instruction,
    autonomy: t.autonomy,
    file: t.file,       // if single-file task
    skills: blockSkills, // skills for this block (from blocks.yaml)
  }))
});

const skillsContext = `
## Applicable Skills

Load these skills using the skill tool before executing your task:
${blockSkills.map(s => `- ${s}`).join('\n')}

Skills provide conventions, patterns, and rules specific to this codebase.
Load them progressively as you encounter relevant decisions.
Note which skills you loaded and how they informed your work.
`;

const result = await run(table.id, {
  subagentType: "explore",  // or "general" for write tasks
  instruction: t.instruction,
  context: sharedContext + "\n" + skillsContext, // lessons + decisions + SKILLS
  responseSchema: {
    type: "object",
    properties: {
      status: { type: "string", enum: ["pass", "fail", "skip"] },
      output_path: { type: "string" },
      summary: { type: "string" },
      skills_used: { type: "array", items: { type: "string" } },
      error: { type: "string" },
    },
    required: ["status"],
  },
});

// result → { completed, failed, skipped, failures }
```

**Why skill references, not content:**
- Keeps context small — sub-agents only load what they need
- Progressive disclosure — skills are read on-demand during execution
- Skills evolve independently — no need to update FF protocol
- Sub-agents retain autonomy — they decide which parts of which skill apply

---

## Phase 3: VALIDATE

**GATE CHECK:** Before entering Phase 3, read `manifest.md` — verify Phase 2 → Phase 3 gate.
All blocks must be completed. Read `.ff/state.json` to confirm.

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

### Step 3.5 — Persist Report and Finalize

**PERSIST REPORT:** Write `.ff/traces/{session_id}/report.md` with the full FF report.

**UPDATE SESSION METADATA:** Update `.ff/traces/{session_id}/session.json`:

```json
{
  "session_id": "ff-20260914-001",
  "completed_at": "ISO date",
  "status": "completed",
  "blocks_total": 4,
  "tasks_total": 12,
  "files_changed": ["src/auth.ts", "src/middleware.ts"],
  "files_created": ["src/jwt.ts"]
}
```

**UPDATE STATE:** Set `.ff/state.json`:

```json
{
  "status": "completed",
  "current_phase": "phase_3",
  "completed_at": "ISO date",
  "updated_at": "ISO date"
}
```

**UPDATE CHANGELOG:** Append to `.ff/changelog.md`:

```markdown
## {session_id} — {YYYY-MM-DD} — {work_type}

**Title:** {task_title}
**Status:** completed
**Blocks:** {N} | **Tasks:** {total} ({passed} pass, {failed} fail, {skipped} skip)
**Files Changed:** {list}
**Duration:** {time}
**Autonomy:** {mode}

{brief summary of what was accomplished}
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

The state file is the **single source of truth** for session progress.
Always read it before making decisions about current position.
Never rely on conversation memory alone.

```json
{
  "session_id": "ff-{date}-{hash}",
  "work_type": "bugfix",
  "task_title": "...",
  "status": "running",
  "current_block": "block-001",
  "blocks_completed": [],
  "blocks_pending": [],
  "skills": ["python-fastapi-coding-conventions", "owasp-secure-coding-bdd"],
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

The agent updates state.json after each block completion. The `summary` field
is updated every 3 blocks as part of the context budget rule. This enables resume
if the session is interrupted and keeps the orchestrator grounded in actual progress.

### File: `.ff/lessons.json`

Array of lesson objects. Append-only. Loaded at Phase 1 (plan).
See Phase 3.4 for lesson format.

### File: `.ff/traces/{session_id}/skills.md`

Discovered skills with reasons for inclusion. Created during Phase 0 Skill Discovery.
These skill references are injected into all sub-agent dispatches.

---

## Integration with Existing Skills

FF uses these skills as components:

| Skill | When Used | Purpose |
|-------|-----------|---------|
| `essence` | Phase 0 | Clarify intent, detect traps |
| `swarm` | Phase 2 | Fan-out parallel micro-tasks |
| Project skills | Phase 0+ | Discovered and injected as references into all dispatches |

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
