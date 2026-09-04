# Migration Guide — Engineering Loop v12.4.0

This guide shows how to migrate an existing project to use the Engineering Loop with the FF (Fail Fast) protocol.

## Prerequisites

- Git installed
- Node.js (if your project uses it)
- Access to the Engineering Loop repository

---

## Step 1: Add the Framework as a Submodule

```bash
cd your-project
git submodule add C:/Users/emers/Documents/Claude/Projects/.engineering-loop .eng
git commit -m "Add Engineering Loop framework"
```

---

## Step 2: Update `.gitignore`

Add these lines to your project's `.gitignore`:

```gitignore
# .eng tooling (submodule, ignored)
.eng/

# FF workspace (project state)
.ff/

# Project artifacts
artifacts/
```

---

## Step 3: Create FF Workspace

```bash
# Create the FF workspace
mkdir .ff

# Initialize state
echo '{
  "iteration": 0,
  "status": "idle",
  "work_type": "ff",
  "work_item": "",
  "decisions": [],
  "lessons": [],
  "blocks": [],
  "trace": []
}' > .ff/state.json

# Initialize lessons
echo '[]' > .ff/lessons.json

# Create README
cat > .ff/README.md << 'EOF'
# .ff/ — FF Workspace

This directory is the working directory for the FF (Fail Fast) protocol.

## Files

- `state.json` — Current FF session state. Updated after each block completion.
- `lessons.json` — Accumulated lessons from failed or retried tasks. Append-only.
- `README.md` — This file.

## Usage

The FF protocol creates and manages this directory automatically. Do not edit files manually unless debugging a failed session.
EOF
```

---

## Step 4: Create Artifacts Directory

```bash
mkdir artifacts
```

---

## Step 5: Update AGENTS.md

Replace your project's `AGENTS.md` with the following:

```markdown
# AGENTS.md — [Project Name]

## Default Development Mode: FF (MANDATORY)

This project uses **FF (Fail Fast)** as its default development mode. All substantial work items MUST follow the FF protocol.

**CRITICAL:** When the user requests any work item, you MUST evaluate it against the FF activation criteria below. If it qualifies, load the ff skill and execute the protocol WITHOUT waiting for the user to explicitly say "use FF".

### FF Activation Criteria

Use FF for ANY work request that meets one of these conditions:
- Touches ≥ 3 files
- Involves ≥ 5 discrete changes
- Has unclear dependencies between parts
- User explicitly requests FF
- Is a feature, bugfix suite, refactor, test rewrite, or migration

For trivial work (≤ 2 files, clear instructions, single change), execute inline without FF overhead.

### What "Default Mode" Means

When the user says things like:
- "Implement X"
- "Fix Y"
- "Refactor Z"
- "Add tests for W"

You should:
1. Load the ff skill (`/skills/ff`)
2. Run Phase 0: CLARIFY (essence check)
3. Continue through Phase 1-4 without stopping for protocol questions
4. Only ask the user about scope clarification and autonomy decisions

**DO NOT:**
- Wait for the user to say "use FF" or "run FF"
- Explain what FF is (the user already knows)
- Ask "Should I use FF for this?" (you already know the answer)
- Execute substantial work sequentially without FF

### FF Protocol Summary

1. **Phase 0: Clarify** — Essence check, resolve scope tensions
2. **Phase 1: Plan Build** — Two sub-agents cross-analyze → consolidate → judge approve
3. **Phase 2: Execute** — Swarm fan-out per block, gate check, retry
4. **Phase 3: Validate** — Cross-check plan vs. reality
5. **Phase 4: Lessons** — Capture lessons, report results

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

### Framework

The Engineering Loop framework is installed as a git submodule at `.eng/`. It is read-only and gitignored.

- `.eng/references/` — 14 reference docs (anti-patterns, decisions, lessons, etc.)
- `.eng/skills/` — 22 ideação/verificação skills
- `.eng/AGENTS.md` — Framework instructions
- `.eng/skill-index.md` — Skill registry
- `.eng/state-template.json` — State template

---

## FF Workspace

The `.ff/` directory is the FF workspace:
- `state.json` — Current FF session state
- `lessons.json` — Accumulated lessons (append-only)
- `README.md` — Documentation

Before Phase 1, load `.ff/lessons.json` and apply relevant lessons to the plan.
```

---

## Step 6: Create Config File (Optional)

If your project needs a config file:

```bash
cat > config.yaml << 'EOF'
# Project configuration
# This file is gitignored and project-specific.

# Model configuration (if used by the project)
model:
  base_url: "http://localhost:8000"
  model: "qwable-v2"
  temperature: 0.0
  max_tokens: 128000

# FF Protocol settings
ff:
  autonomy_mode: "semi"  # auto | semi | manual
  max_blocks: 8
  max_tasks_per_block: 12

# Lessons
lessons:
  enabled: true
  local_file: ".ff/lessons.json"

# Graphify (optional)
graphify:
  enabled: false
  build_on_init: true
  update_after_impl: true
EOF
```

---

## Step 7: Update README.md

Update your project's `README.md` to document that FF is the default mode:

```markdown
# [Project Name]

## Quick Start

### 1. Clone and Initialize

```bash
git clone <project-url>
cd <project-name>
git submodule init
git submodule update
```

### 2. Development

This project uses FF (Fail Fast) as its default development mode. Simply describe what you want done — the agent will automatically apply FF for substantial work items.

Example:
- "Implement user authentication with JWT" → FF activates
- "Fix the login bug on mobile" → FF activates
- "Change button color on line 42" → inline (trivial)
```

---

## Verification

After completing the migration, verify:

1. **Submodule is initialized:**
   ```bash
   git submodule status
   ```

2. **FF workspace exists:**
   ```bash
   ls -la .ff/
   # Should show: state.json, lessons.json, README.md
   ```

3. **Artifacts directory exists:**
   ```bash
   ls -la artifacts/
   # Should be empty or contain trace files
   ```

4. **AGENTS.md is updated:**
   ```bash
   head -20 AGENTS.md
   # Should show FF protocol
   ```

---

## Troubleshooting

### Submodule Not Updating

```bash
cd .eng
git checkout main
git pull
cd ..
git commit -m "Update .eng submodule"
```

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
