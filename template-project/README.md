# [Project Name]

## Quick Start

### 1. Clone and Initialize

```bash
# Clone the project
git clone <project-url>
cd <project-name>

# Initialize submodules
git submodule init
git submodule update
```

### 2. FF Protocol

FF is the default development mode — it activates automatically when you request work. Simply describe what you want done, and the agent will apply FF when appropriate.

Example:
- "Implement user authentication with JWT" → FF activates (multi-file feature)
- "Fix the login bug on mobile" → FF activates
- "Change the button color on line 42" → inline execution (trivial)

No commands needed. The agent reads `AGENTS.md` and follows FF automatically.

### 3. Development

```bash
# Install dependencies
npm install

# Run tests
npm test

# Run E2E tests
npm run e2e
```

---

## FF Protocol

FF is the default development mode. It is hybrid: Claude plans and validates; a local model executes.

### Protocol Overview

```
USER INTENT
    ↓
PHASE 0: CLARIFY    → Essence check, gather unknowns, scope the task
PHASE 1: PLAN       → (planner) in-session analysis passes → plan → work orders → acceptance (Gherkin) + checks → judge approve → handoff
PHASE 2: EXECUTE    → (executor, dispatched by the planner block by block) work order → checks → self-repair → commit → trace → planner review
PHASE 3: VALIDATE   → (planner) critical review: re-run checks, scope + diff review, final gate
PHASE 4: LESSONS    → Capture lessons, report results
```

### Plan Build

The plan is built **by the planner (Claude), in-session**, in two separate analysis passes:

1. **Structural pass** — maps files, imports, dependencies, risk
2. **Adversarial pass** — re-examines the structural findings: alternative approaches, edge cases, hidden dependencies

The planner consolidates both passes into the plan, fragments it into blocks, and writes for every block an **executor-grade work order** (exact files, exact edits), a Gherkin acceptance feature (Given/When/Then, end-user perspective) and an executable **check** script. A **judge sub-agent** — the protocol's only sub-agent, dispatched with a clean view — validates plan, work orders, acceptance and checks together. Only after approval is the session handed off to the executor.

### Execute

The planner dispatches the local model in opencode one block at a time, like a sub-agent (`opencode run --command ff --agent ff-executor`; manual fallback: you run `/ff exec`). Every block has an execution tier — T0 mechanical (copy and verbatim edits), T1 guided or T2 high effort (the local model writes the code from the planner's spec and protected tests). Blocks run in order: apply the work order, run the block's checks, self-repair once on failure (attempt 2), commit locally, and write an execution trace with a **validation proposal**. Then the planner runs a **critical second validation** — it re-runs every check itself, verifies the scope from the commit, reads the full diff, and approves the block or spends its single correction (attempt 3) before escalating to the user.

### Autonomy Score

| Score | Mode | Behavior |
|-------|------|----------|
| ≥ 0.8 | FULL AUTO | Execute without asking |
| 0.5-0.7 | SEMI AUTO | Show plan → wait for "go" → execute |
| < 0.5 | MANUAL | Ask before each block |

**FF v14:** one "go" per plan — after it the planner (Claude) dispatches and supervises the local executor block by block; manual blocks still ask you first. The score is reported with the plan as a risk summary.

### Hard Rules (Never Override)

- `rm -rf`, `git push --force` — always ask
- Writes to Firebase — always ask
- Changes to `.env` — always ask
- Operations outside workspace — always block (exception: the FF executor writes, never deletes, `~/.agents/ff-executor.lock` — `.eng/global-skills/ff-exec/SKILL.md` section 6)

---

## Project Structure

```
<project-name>/
├── .eng/                  # Engineering Loop framework (git submodule, ignored)
│   ├── references/        # 17 reference docs (anti-patterns, decisions, lessons, ff-protocol, executor-calibration, etc.)
│   ├── skills/            # 23 ideação/verificação skills
│   ├── AGENTS.md          # Framework instructions
│   ├── skill-index.md     # Skill registry
│   ├── state-template.json # State template
│   └── README.md          # Framework documentation
│
├── .ff/                   # FF Workspace (gitignored)
│   ├── state.json         # FF session state
│   ├── lessons.json       # Lessons (append-only)
│   └── README.md          # FF documentation
│
├── artifacts/             # Trace files (gitignored)
│   └── trace-*.jsonl      # Historical traces
│
├── .opencode/             # Model config (gitignored)
│   └── opencode.json      # Local model provider config
│
├── src/                   # Application source code
├── e2e/                   # Playwright E2E tests
├── AGENTS.md              # Project instructions (tracked)
├── README.md              # Project documentation
└── .gitignore             # Git ignore rules
```

---

## Migration Guide

### From Sequential Loop to FF

If you are migrating from a sequential loop (34 stages, LangGraph) to FF:

1. **Remove motor code** — The loop motor (eng_loop/, stages/, scripts/, setup/) is no longer needed.
2. **Keep references and skills** — The `.eng/references/` and `.eng/skills/` directories are still available.
3. **Use FF protocol** — Replace the sequential loop with the FF protocol described above.

### Migrating a Project

1. Install the Engineering Loop as a git submodule:
   ```bash
   git submodule add <engineering-loop-url> .eng
   ```

2. Create the FF workspace:
   ```bash
   mkdir .ff
   echo '[]' > .ff/lessons.json
   echo '{...}' > .ff/state.json
   ```

3. Update your `.gitignore` to include:
   ```gitignore
   # .eng tooling (submodule, ignored)
   .eng/

   # FF workspace (project state)
   .ff/

   # Project artifacts
   artifacts/
   ```

4. Update your `AGENTS.md` to reflect the FF protocol.

---

## Troubleshooting

### FF Protocol Not Working

- Ensure `.eng/` is properly initialized as a submodule
- Check that `~/.agents/skills/ff/` exists (the FF skill)
- Verify that the judge sub-agent is available to the planner (it is the protocol's only sub-agent; without it the planner HALTs)
- Verify the executor: opencode answers with the local model, `~/.agents/skills/ff-exec/` exists and `.opencode/agents/ff-executor.md` exists in the project (`opencode agent list` shows `ff-executor`)

### Lessons Not Captured

- Check that `.ff/lessons.json` is writable
- Verify that the FF protocol is running in FULL AUTO or SEMI AUTO mode

### Plan Build Failing

- Ensure the judge receives the full artifact set with a clean view (plan, blocks, work orders, acceptance, checks, both analyses)
- Check that the planner wrote the Gherkin features and the check scripts before the judge ran
- Check that the judge sub-agent is responding
- Verify that the plan is being properly consolidated

### Executor Blocked

- Read `.ff/traces/{session_id}/execution/{block_id}.json` — `blocked_reason` and the check output say why
- Restore the tree with the exact commands the planner gives you (`git restore --staged --worktree -- <files>` for modified files; `del <path>` for untracked files the block created), then hand the session back to the planner (Claude): it diagnoses from the saved `execution/{block_id}.attempt-{n}.diff` and sends one corrected order (attempt 3), or escalates the decision to you

---

## Version

| File | Version |
|------|---------|
| Framework | v14.0.0 |
