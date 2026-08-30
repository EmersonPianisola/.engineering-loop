# AGENTS.md — [Project Name]

## Development Mode: FF

This project uses **FF (Fail Fast)** as its default development mode.

### FF Protocol

FF is a protocol for parallel swarm-based software development. The main agent orchestrates, sub-agents execute. Every unit of work is atomic, validated in isolation, and fails fast without contaminating siblings.

**Protocol:**
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
