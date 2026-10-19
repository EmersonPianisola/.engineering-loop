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

You should (planner — Claude):
1. Load the ff skill (`.eng/global-skills/ff/SKILL.md`)
2. Run Phase 0: CLARIFY (essence check)
3. Continue through Phase 1 (plan + judge), hand off to the executor, then run Phases 3-4 when the executor returns
4. Only ask the user about scope clarification and autonomy decisions

If you are the local model in opencode (executor): do NOT plan. Only execute work orders of an approved session (skill `ff-exec`) — dispatched by the planner (`ff-executor` agent) or run by the user with `/ff exec`.

**DO NOT:**
- Wait for the user to say "use FF" or "run FF"
- Explain what FF is (the user already knows)
- Ask "Should I use FF for this?" (you already know the answer)
- Execute substantial work sequentially without FF

### FF Protocol Summary (Hybrid — v14, tiered)

1. **Phase 0: Clarify** (planner) — Essence check, resolve scope tensions
2. **Phase 1: Plan** (planner) — Structural + adversarial in-session passes → plan → blocks routed by execution tier (T0 mechanical · T1 guided · T2 high effort) → executor-grade work orders (T1/T2: spec + planner-written protected tests) → acceptance (Gherkin) + executable checks → judge approve (≤ 3 rounds) → handoff
3. **Phase 2: Execute** (executor, dispatched by the planner one block at a time — `opencode run --command ff --agent ff-executor`; manual fallback `/ff exec`) — apply the work order (T1/T2: write the specified code), run checks, self-repair once (attempt 2), commit per block, write execution trace + validation proposal; the planner reviews each block before the next dispatch
4. **Phase 3: Review & Validate** (planner) — Critical second validation: re-run checks, scope check, full diff review, verdict per block, one correction per block (attempt 3) then the user, final gate
5. **Phase 4: Lessons** (planner) — Capture lessons (planner and executor), report results

**Roles:** the planner is Claude (loads `.eng/global-skills/ff/SKILL.md`); the executor is the local model in opencode (`/ff exec`, skill `ff-exec`). The judge is the only sub-agent. One active FF session per repo; the protocol is read from this repo. Blocks are routed by execution tier (`.eng/global-skills/ff/routing.md`): the planner specifies and validates, the local model writes what the spec and tests allow. After your single "go" the planner dispatches the executor (`.opencode/agents/ff-executor.md`) block by block, like a sub-agent; one executor run at a time per machine (one GPU).

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

### Anti-Drift: State File is Your Anchor

As FF sessions grow long, the orchestrator may lose track of protocol rules.
The `.ff/state.json` file is your anchor — always read it before making decisions
about current phase or block position. Never rely on conversation memory alone.

The `manifest.md` file (in `.eng/global-skills/ff/`) is a compressed checklist
for each phase gate. Read it before every phase transition. It is designed to
stay in context throughout long runs.

### Framework

The Engineering Loop framework is installed as a git submodule at `.eng/`. It is read-only and gitignored.

- `.eng/global-skills/` — 106 versioned global skills (single source of truth)
- `.eng/skills/` — 23 framework-specific skills
- `.eng/references/` — 17 reference docs (anti-patterns, decisions, lessons, ff-protocol, executor-calibration, etc.)
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

### Skill Usage Guide

| Working on | Load skill first |
|---|---|
| FF protocol execution | `ff` (always) |
| Intent clarification | `essence` (Phase 0) |
| Code implementation | Framework skill for your stack, or self-construct |
| Testing strategy | `comprehensive-test-strategy` + `verifiable-quality-gates` |
| E2E testing | `e2e-playwright` (framework) or `playwright` (global) |
| Security review | `security-review` or `owasp-secure-coding-bdd` |
| Architecture decisions | `architectural-decision-records` |
| API design | `api-designer` or `implementing-api-patterns` |
| Database | `database-design` + provider-specific skill |
| Documentation | `doc-coauthoring` |
| Performance | `sre-operational-readiness` |
| Business value narrative | `story-flow` (post-validation) |
| Research | `parallel-web-search` |
| Skill creation | `skill-creator` |

---

## FF Workspace

The `.ff/` directory is the FF workspace:
- `state.json` — Current FF session state. **Read before every decision about phase or block position.**
- `lessons.json` — Accumulated lessons (append-only). Loaded at Phase 1.
- `README.md` — Documentation

Before Phase 1, load `.ff/lessons.json` and apply relevant lessons to the plan.
