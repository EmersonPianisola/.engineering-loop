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

- `.eng/global-skills/` — 50 versioned global skills (single source of truth)
- `.eng/skills/` — 22 framework-specific skills
- `.eng/references/` — 14 reference docs (anti-patterns, decisions, lessons, etc.)
- `.eng/scripts/sync-global-skills.py` — Sync global skills to `~/.agents/skills/`
- `.eng/AGENTS.md` — Framework instructions
- `.eng/skill-index.md` — Skill registry
- `.eng/state-template.json` — State template

### Global Skills

Global skills are versioned in `.eng/global-skills/` and deployed to `~/.agents/skills/`. After submodule update:

```bash
python .eng/scripts/sync-global-skills.py pull
```

Do NOT edit skills directly in `~/.agents/skills/`. To propose changes, edit in `.eng/global-skills/` and run `pull`.

---

## FF Workspace

The `.ff/` directory is the FF workspace:
- `state.json` — Current FF session state
- `lessons.json` — Accumulated lessons (append-only)
- `README.md` — Documentation

Before Phase 1, load `.ff/lessons.json` and apply relevant lessons to the plan.
