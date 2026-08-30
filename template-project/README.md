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

Run tasks using the Fail Fast (FF) protocol:

```bash
# Run FF with the task description
ff "your task description"
```

The FF protocol will:
1. Clarify the task (essence check)
2. Build a plan (two sub-agents cross-analyze, judge approves)
3. Execute (swarm fan-out per block)
4. Validate (cross-check plan vs. reality)
5. Capture lessons

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

FF is the default development mode. It replaces the sequential loop with parallel swarm execution.

### Protocol Overview

```
USER INTENT
    ↓
PHASE 0: CLARIFY    → Essence check, gather unknowns, scope the task
PHASE 1: PLAN BUILD → Two sub-agents cross-analyze → consolidate → judge approve
PHASE 2: EXECUTE    → Swarm fan-out per block, gate check, retry
PHASE 3: VALIDATE   → Final gate, cross-check plan vs. reality
PHASE 4: LESSONS    → Capture lessons, report results
```

### Plan Build

The plan is **not built by the main agent**. It is built by two sub-agents:

1. **Sub-Agent A (Structural Analyst)** — maps files, imports, dependencies, risk
2. **Sub-Agent B (Adversarial Analyst)** — alternative approaches, edge cases, hidden dependencies

The main agent consolidates A + B, then spawns a **judge sub-agent** to validate the plan. Only after approval does swarm execution begin.

### Execute

Swarm dispatches parallel tasks per block. Independent tasks run together; dependent tasks wait. Each block validates before the next executes.

### Autonomy Score

| Score | Mode | Behavior |
|-------|------|----------|
| ≥ 0.8 | FULL AUTO | Execute without asking |
| 0.5-0.7 | SEMI AUTO | Show plan → wait for "go" → execute |
| < 0.5 | MANUAL | Ask before each block |

### Hard Rules (Never Override)

- `rm -rf`, `git push --force` — always ask
- Writes to Firebase — always ask
- Changes to `.env` — always ask
- Operations outside workspace — always block

---

## Project Structure

```
<project-name>/
├── .eng/                  # Engineering Loop framework (git submodule, ignored)
│   ├── references/        # 14 reference docs (anti-patterns, decisions, lessons, etc.)
│   ├── skills/            # 22 ideação/verificação skills
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
│   └── opencode.json      # Providers (8 models)
│
├── src/                   # Application source code
├── e2e/                   # Playwright E2E tests
├── AGENTS.md              # Project instructions (gitignored)
├── config.yaml            # Project configuration (gitignored)
├── state.json             # Project state (gitignored)
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
- Verify that the judge sub-agent is available

### Lessons Not Captured

- Check that `.ff/lessons.json` is writable
- Verify that the FF protocol is running in FULL AUTO or SEMI AUTO mode

### Plan Build Failing

- Ensure the two sub-agents (A and B) have sufficient context
- Check that the judge sub-agent is responding
- Verify that the plan is being properly consolidated

---

## Version

| File | Version |
|------|---------|
| Framework | v12.4.0 |
| FF Protocol | v2.0 |
| Judge | v1.0 |
