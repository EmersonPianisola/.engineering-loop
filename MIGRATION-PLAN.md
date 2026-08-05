# Migration Plan: LangGraph → Graph-as-Skill + Deterministic Verifiers

## Goal

Replace `eng_loop/` (LangGraph + reinvented tools) with a state-driven ORCHESTRATOR.md
that uses OpenCode's native tools, deterministic verifiers, and file-based state.

**Principles from AI Builder Club guides:**
- "The verifier is the bottleneck, not the generator" — write verifiers, not prompts
- "Pick a framework instead of hand-rolling" — use OpenCode, don't reinvent it
- "Give the reviewer node teeth" — separate, read-only verifier
- "Design the shared state object explicitly" — state.json as source of truth
- "Isolate failure" — one node fails without corrupting downstream

---

## Current State

| Component | What It Does | Problem |
|-----------|-------------|---------|
| `ORCHESTRATOR.md` | Prompt-based orchestrator | LLM decides routing, doesn't follow loop |
| `eng_loop/` | LangGraph StateGraph + 27 Pydantic schemas + 40+ files | Re-invents read/write/bash/glob/grep, truncates agent capability |
| `state-template.json` | Stage state template | OK, but duplicated in `state.py` |
| `stages/*.md` | Stage procedures | OK, good content |
| `skills/` | Skill definitions | OK |
| `config-template.yaml` | Framework defaults | OK |

---

## Phase 1: Verifier Generation (Self-Constructed at Architecture Stage)

**Why:** The single highest-leverage change. Replace "LLM decides if stage passed"
with exit codes and file checks. Verifiers are **generated per-project** during
the architecture/blueprint stage — the framework does NOT need to know about
Python, Go, Rust, Node, etc.

**Principle:** The orchestrator says "run verifier". The verifier content is
project-specific, generated when the tech stack is decided.

### 1.1 Verifier Generation Contract

The `impl.design` stage (blueprint) MUST produce verifiers as part of its output.
The orchestrator enforces the contract; the content is self-constructed.

**ORCHESTRATOR.md adds to `impl.design` delegation:**

```
### IMPL.DESIGN — Implementation Blueprint + Verifier Generation

- **Sub-agent:** `implementation-architect`
- **Task:** Produce blueprint + generate verifiers/ for this project's stack
- **Verifier generation instructions:**
  > Based on the tech stack defined in the blueprint, create verifiers/ directory
  > with shell scripts. Each script: exit 0 = PASS, exit 1 = FAIL.
  >
  > Required scripts:
  > - `impl-code.sh` — run tests, build, lint, typecheck for this stack
  > - `deploy-prepare.sh` — full test + build for all services in this project
  > - `verify.sh` — check validation report exists with VERDICT: PASS
  >
  > Detect the stack from:
  > - package.json → npm/pnpm/yarn commands
  > - Cargo.toml → cargo test, cargo build, cargo clippy
  > - go.mod → go test ./..., go build ./...
  > - requirements.txt/pyproject.toml → pytest, mypy, black
  > - Makefile → make test, make build
  > - mix.exs → mix test, mix compile
  > - build.gradle → ./gradlew test build
  > - pom.xml → mvn test compile
  > - docker-compose.yml → docker-compose based checks
  > - monorepo: generate per-service, run all from root script
```

### 1.2 Verifier Contract (Framework-Level)

The framework enforces the **contract**, not the content:

| Rule | Enforced By |
|------|-------------|
| Verifier script exists before stage runs | ORCHESTRATOR.md pre-stage check |
| Exit 0 = PASS, Exit 1 = FAIL | Convention, checked by orchestrator |
| `impl-code.sh` exists before `impl.code` | Hook: `blueprint-exists` |
| `deploy-prepare.sh` exists before `deploy.prepare` | Hook: script existence check |
| `verify.sh` checks validation report | Generic, language-agnostic |

### 1.3 Generic Verifiers (Framework-Level, Language-Agnostic)

These are the ONLY verifiers the framework ships — they check artifacts, not code:

File: `verifiers/verify.sh` (shipped with framework)
```bash
#!/usr/bin/env bash
# Verifier: verify stage produced a validation report with PASS verdict
# Language-agnostic — checks artifact, not code
ARTIFACT_ROOT="${1:-artifacts}"
LATEST_REPORT=$(ls -t "$ARTIFACT_ROOT"/validation-*.md 2>/dev/null | head -1)

if [ -z "$LATEST_REPORT" ]; then
  echo "FAIL: no validation report found"
  exit 1
fi

if grep -q "VERDICT: PASS" "$LATEST_REPORT"; then
  echo "PASS: verifier report shows PASS"
  exit 0
else
  echo "FAIL: verifier report shows FAIL or no verdict"
  exit 1
fi
```

File: `verifiers/artifact-exists.sh` (shipped with framework)
```bash
#!/usr/bin/env bash
# Generic verifier: checks that a stage produced its expected artifact
ARTIFACT_ROOT="${1:-artifacts}"
EXPECTED_FILE="$2"

if [ -f "$ARTIFACT_ROOT/$EXPECTED_FILE" ]; then
  echo "PASS: $EXPECTED_FILE exists"
  exit 0
else
  echo "FAIL: $EXPECTED_FILE not found in $ARTIFACT_ROOT"
  exit 1
fi
```

### 1.4 Multi-Language / Monorepo Support

The verifier generation handles this naturally:

**Example: Backend (Go) + Frontend (React) monorepo**

Generated `verifiers/impl-code.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
echo "=== impl.code verifier ==="

# Backend (Go)
if [ -f "backend/go.mod" ]; then
  echo "-- Backend: Go tests"
  (cd backend && go test ./...) || { echo "FAIL: backend tests"; exit 1; }
  echo "-- Backend: Go build"
  (cd backend && go build ./...) || { echo "FAIL: backend build"; exit 1; }
fi

# Frontend (TypeScript/React)
if [ -f "frontend/package.json" ]; then
  echo "-- Frontend: npm tests"
  (cd frontend && npm test) || { echo "FAIL: frontend tests"; exit 1; }
  echo "-- Frontend: npm build"
  (cd frontend && npm run build) || { echo "FAIL: frontend build"; exit 1; }
  echo "-- Frontend: typecheck"
  (cd frontend && npx tsc --noEmit) || { echo "FAIL: frontend typecheck"; exit 1; }
fi

echo "PASS: all checks passed"
exit 0
```

**Example: Python backend + Rust service**

Generated `verifiers/deploy-prepare.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
echo "=== deploy.prepare verifier ==="

# Python service
if [ -f "api/pyproject.toml" ]; then
  (cd api && pytest) || { echo "FAIL: python tests"; exit 1; }
  (cd api && mypy .) || { echo "FAIL: python typecheck"; exit 1; }
fi

# Rust service
if [ -f "worker/Cargo.toml" ]; then
  (cd worker && cargo test) || { echo "FAIL: rust tests"; exit 1; }
  (cd worker && cargo build --release) || { echo "FAIL: rust build"; exit 1; }
fi

echo "PASS: all deploy checks passed"
exit 0
```

### 1.5 Fallback: Auto-Detect if Verifiers Don't Exist

If `impl.design` didn't produce verifiers (legacy project, manual work item),
the orchestrator auto-generates minimal ones:

```
IF verifiers/impl-code.sh does not exist:
    Auto-detect stack from project files:
    - package.json → npm test && npm run build
    - Cargo.toml → cargo test && cargo build
    - go.mod → go test ./... && go build ./...
    - pyproject.toml → pytest
    - Makefile → make test
    - None found → warn user, skip verifier (done: true by default)
```

**Deliverables:** 2 framework verifiers + verifier generation contract in ORCHESTRATOR.md
**Risk:** Low — verifiers are project-generated, framework only enforces contract
**Effort:** ~30 min (framework verifiers) + 0 min (project verifiers are self-constructed)

---

## Phase 2: State-Driven ORCHESTRATOR.md

**Why:** The orchestrator must read state from file, not from memory.
Each response updates state.json. Routing is deterministic based on state.

### 2.1 New ORCHESTRATOR.md Structure

The orchestrator becomes a state machine driven by `state.json`:

```
ORCHESTRATOR.md (new structure)
├── ROLE: Same as before
├── INITIALIZATION: Load state.json, not memory
├── THE LOOP: Read state → find next stage → run verifier → advance
├── VERIFIER GATES: Deterministic checks after each stage
├── ROUTING TABLE: Deterministic next-stage based on complexity + current stage
├── OUTPUT FORMAT: Must include state_update + sub_agent_invocation
└── ANTI-PATTERNS: Same as before
```

Key changes:
1. **State-first protocol:** First action every turn is `Read state.json`
2. **Verifier mandate:** After each stage, run the verifier script via Bash
3. **Routing table:** Explicit next-stage mapping (no LLM guessing)
4. **Hard bounds:** Max iterations enforced by reading state, not trusting LLM

### 2.2 Routing Table (Deterministic)

Replace the LLM's implicit routing with an explicit table in ORCHESTRATOR.md:

```
## ROUTING TABLE — Deterministic Next Stage

| Current Stage (done) | Complexity | UI Project | Next Stage |
|---------------------|------------|------------|------------|
| `init` | any | any | `init.ideate` |
| `init.ideate` | any | any | `init.bdd` (if large+) else `init.refine` |
| `init.bdd` | large+ | any | `init.refine` |
| `init.refine` | small | any | `impl.design` |
| `init.refine` | medium+ | any | `arch.requirements` |
| `design.user-research` | large+ | any | `design.personas` |
| `design.personas` | large+ | any | `design.info-arch` |
| `design.info-arch` | large+ | any | `design.interaction` |
| `design.interaction` | large+ | any | `design.design-system` |
| `design.design-system` | large+ | any | `design.visual-design` |
| `design.visual-design` | large+ | any | `arch.requirements` (medium+) or `impl.design` (small) |
| `arch.requirements` | medium+ | any | `arch.solution` |
| `arch.solution` | medium+ | any | `arch.review` (complex) or `impl.design` |
| `arch.review` | complex | any | `impl.design` |
| `impl.design` | any | any | `impl.code` |
| `impl.code` | any | any | `doc.update` |
| `doc.update` | any | any | `verify` |
| `verify` (PASS) | any | yes | `e2e.execute` |
| `verify` (PASS) | medium+ | no | `qa.security` |
| `verify` (PASS) | small | no | `deploy.prepare` |
| `verify` (FAIL) | any | any | `impl.code` (RESET) |
| `e2e.execute` (PASS) | medium+ | any | `qa.security` |
| `e2e.execute` (PASS) | small | any | `deploy.prepare` |
| `e2e.execute` (FAIL) | any | any | `impl.code` (RESET) |
| `qa.security` (PASS) | medium+ | any | `qa.api-contract` |
| `qa.security` (PASS) | small | any | `deploy.prepare` |
| `qa.security` (FAIL) | any | any | `impl.code` (RESET) |
| `qa.api-contract` (PASS) | complex | any | `qa.performance` |
| `qa.api-contract` (PASS) | not complex | any | `deploy.prepare` |
| `qa.api-contract` (FAIL) | any | any | `impl.code` (RESET) |
| `qa.performance` (PASS) | any | any | `deploy.prepare` |
| `qa.performance` (FAIL) | any | any | `impl.code` (RESET) |
| `deploy.prepare` (PASS) | any | yes | `smoke.test` |
| `deploy.prepare` (PASS) | any | no | `doc.decisions` (medium+) or `post` |
| `deploy.prepare` (FAIL) | any | any | `impl.code` (RESET) |
| `smoke.test` (PASS) | any | any | `doc.decisions` (medium+) or `post` |
| `smoke.test` (FAIL) | any | any | `impl.code` (RESET) |
| `doc.decisions` | medium+ | any | `doc.project` |
| `doc.project` | medium+ | any | `post` |
| `post` | any | any | END |
```

### 2.3 State Protocol

Every orchestrator response follows this protocol:

```
1. READ state.json — current state of all stages
2. DETERMINE next stage from routing table
3. CHECK essence gate — if not checked, invoke essence skill
4. CHECK constraint — if attempts >= max, block and exit
5. INVOKE stage via task tool — uses native OpenCode tools
6. RUN verifier script via bash tool — deterministic check
7. UPDATE state.json — write new state
8. OUTPUT state_update + sub_agent_invocation for next iteration
```

### 2.4 Verifier Integration in ORCHESTRATOR.md

Add to each stage's delegation section. Verifiers are project-generated
(except generic artifact checks which are framework-shipped):

```
### IMPL.CODE — Code Implementation (TDD)

- **Sub-agent:** domain-specific skill (self-constructed)
- **Context:** blueprint + work item + confirmed lessons
- **Limit:** `max_impl_code_attempts`
- **Pre-stage hook:** IF `verifiers/impl-code.sh` missing → auto-detect stack, generate minimal verifier
- **Post-stage verifier:** `bash verifiers/impl-code.sh {project-root}`
- **On verifier PASS:** `done: true`, advance to `doc.update`
- **On verifier FAIL:** `done: false`, reset for retry or escalate

### VERIFY — Independent Verification

- **Sub-agent:** `verifier` (fresh agent)
- **Post-stage verifier:** `bash {framework-root}/verifiers/verify.sh {artifact-root}`
- **On verifier PASS:** `done: true`, advance per routing table
- **On verifier FAIL:** `done: false`, reset `impl.code.done = false`

### DEPLOY.PREPARE — Deploy Preparation

- **Pre-stage hook:** IF `verifiers/deploy-prepare.sh` missing → auto-detect stack
- **Post-stage verifier:** `bash verifiers/deploy-prepare.sh {project-root}`
- **On verifier PASS:** `done: true`, advance per routing table
- **On verifier FAIL:** `done: false`, reset `impl.code.done = false`
```

**Deliverables:** Updated `ORCHESTRATOR.md`
**Risk:** Medium — requires careful prompt engineering
**Effort:** ~2 hours

---

## Phase 3: Simplify eng_loop/ to Utility Library

**Why:** Keep the good parts (stage ordering, complexity logic, config loading),
remove the bad parts (reinvented tools, agent runner, LangGraph graph).

### 3.1 Files to KEEP

| File | Why |
|------|-----|
| `config.py` | Config loading, path resolution — useful utility |
| `state.py` (trimmed) | Stage ordering, complexity checks — reference implementation |
| `tools/file_ops.py` | JSON read/write utilities |
| `tools/json_parse.py` | JSON extraction from LLM output |
| `tools/progress.py` | Logging utilities |
| `tools/lessons.py` | Lessons management |

### 3.2 Files to REMOVE

| File | Reason |
|------|--------|
| `graph.py` | LangGraph — replaced by ORCHESTRATOR.md routing table |
| `routing.py` | LangGraph routing — replaced by routing table in prompt |
| `agent_runner.py` | Re-invented runtime — OpenCode provides this |
| `model.py` | Model creation — OpenCode manages models |
| `schemas.py` | 27 Pydantic schemas — overkill, verifiers are simpler |
| `tools/{read,write,edit,bash,glob,grep}_tool.py` | Re-invented tools — use OpenCode natives |
| `tools/agent_tools.py` | Re-invented tool binding |
| `tools/evidence_gate.py` | Replaced by verifier scripts |
| `tools/autosizing.py` | Logic moves to ORCHESTRATOR.md prompt |
| `tools/context_slice.py` | Logic moves to ORCHESTRATOR.md prompt |
| `tools/stage_runner.py` | Replaced by task tool |
| `nodes/*.py` | All node implementations — replaced by task tool delegations |
| `templates.py` | Not needed |
| `cli.py` | Replaced by direct OpenCode usage |

### 3.3 New eng_loop/ Structure

```
eng_loop/
├── lib/
│   ├── config.py          # Config loading, path resolution
│   ├── state.py           # Stage ordering, complexity logic
│   └── utils.py           # JSON, file ops, lessons
├── verifiers/             # Moved here from root verifiers/
│   ├── impl-code.sh
│   ├── verify.sh
│   ├── deploy-prepare.sh
│   └── artifact-exists.sh
└── README.md              # "Utility library for ORCHESTRATOR.md"
```

**Deliverables:** Refactored `eng_loop/`, ~70% file reduction
**Risk:** Low — removing code, not adding
**Effort:** ~1 hour

---

## Phase 4: State.json Protocol Enforcement

**Why:** The LLM must read and write state.json every turn. This is the
single most important change for reliability.

### 4.1 State.json Format (Enhanced)

Add fields to `state-template.json`:

```json
{
  "iteration": 0,
  "status": "running",
  "blocking_condition": "",
  "complexity": "unset",
  "ui_project": false,
  "work_item": null,
  "ideation": null,
  "current_stage": "",
  "last_verifier": "",
  "last_verifier_result": "",
  "stages": { /* same as before */ },
  "decisions": [],
  "artifacts": {
    "blueprint": null,
    "validation": null,
    "e2e_report": null,
    "smoke_report": null,
    "security_report": null,
    "api_contract_report": null,
    "performance_report": null,
    "decision_log": null,
    "project_docs": null
  }
}
```

New fields:
- `current_stage` — which stage is executing now
- `last_verifier` — which verifier script ran last
- `last_verifier_result` — PASS or FAIL
- `artifacts` — paths to produced artifacts (for context slicing)

### 4.2 ORCHESTRATOR.md State Protocol

Add to ORCHESTRATOR.md:

```
## MANDATORY: STATE PROTOCOL

Before every response, you MUST:
1. Read `{loop-root}/state.json` using the Read tool
2. Determine the next stage from the Routing Table
3. After invoking a sub-agent, update state.json using the Write tool

Your output MUST include:
```xml
<state_update>
| Variable | Old Value | New Value |
|----------|-----------|-----------|
| current_stage | previous | new_stage |
| iteration | N | N+1 |
| stages.{stage}.done | false | true |
| stages.{stage}.attempts | N | N+1 |
| last_verifier | old | new |
| last_verifier_result | old | PASS/FAIL |
</state_update>
```

If state.json cannot be read, the loop is blocked. Do not proceed.
```

**Deliverables:** Updated `state-template.json`, updated `ORCHESTRATOR.md`
**Risk:** Low — additive change
**Effort:** ~30 minutes

---

## Phase 5: Hook-Based Critical Edges

**Why:** Some edges must never fail (tests before deploy, build before smoke).
Hooks are deterministic, not LLM-decided.

### 5.1 Hook Definition

In ORCHESTRATOR.md, define hooks as pre-stage checks:

```
## HOOKS — Deterministic Pre-Stage Checks

These checks run BEFORE the stage, enforced by the orchestrator via Bash.
If a hook fails, the stage does NOT execute.

| Hook | Runs Before | Command | On Fail |
|------|------------|---------|---------|
| `tests-pass` | `verify` | `npm test` | Reset `impl.code.done = false` |
| `build-pass` | `deploy.prepare` | `npm run build` | Reset `impl.code.done = false` |
| `lint-pass` | `deploy.prepare` | `npm run lint` | Reset `impl.code.done = false` |
| `typecheck-pass` | `deploy.prepare` | `npx tsc --noEmit` | Reset `impl.code.done = false` |
| `e2e-pass` | `smoke.test` | Check e2e report exists | Skip smoke.test |
| `blueprint-exists` | `impl.code` | Check blueprint file | Block, exit |
```

### 5.2 Hook Execution in ORCHESTRATOR.md

```
## STAGE EXECUTION SEQUENCE

FOR each stage:
    1. READ state.json
    2. CHECK essence gate (if not checked)
    3. RUN applicable hooks via Bash tool
       - If any hook fails → apply hook's "On Fail" action, STOP
    4. CHECK constraint (attempts < max)
    5. INVOKE stage sub-agent via task tool
    6. RUN verifier script via Bash tool
       - If verifier FAILS → reset stage.done = false, STOP
    7. UPDATE state.json
    8. OUTPUT state_update + sub_agent_invocation
```

**Deliverables:** Updated `ORCHESTRATOR.md` with hooks section
**Risk:** Low — additive, defensive
**Effort:** ~30 minutes

---

## Phase 6: Update Documentation

### 6.1 CORE.md

Update to reflect new architecture:

```markdown
# Engineering Loop v11.0

State-driven orchestrator enforced by **ORCHESTRATOR.md** (prompt-based graph)
with **deterministic verifiers** (shell scripts) and **file-based state** (state.json).
Auto-sizes stages by complexity. TDD per task. Independent Verifier with
discrimination sensor. Essence Sidecar validates inputs before every stage.
BMAD Ideation stage. Multi-project via git submodule.

**Orchestrator:** `ORCHESTRATOR.md` (state-driven, routing table, verifier gates)
**Verifiers:** `verifiers/` (shell scripts, exit code = verdict)
**State:** `state.json` (file-based, read/write every turn)
**Tools:** OpenCode native tools (task, bash, read, write, edit, glob, grep)
**Legacy:** `eng_loop/` (LangGraph, deprecated — utility library only)
```

### 6.2 AGENTS.md

Update to reflect new architecture principles.

### 6.3 skill-index.md

Add entry:
```
| 2026-08-04 | all | v11.0.0 — Graph-as-Skill: state-driven orchestrator, deterministic verifiers, routing table, hooks, OpenCode native tools, eng_loop/ reduced to utility library |
```

**Deliverables:** Updated `CORE.md`, `AGENTS.md`, `skill-index.md`
**Risk:** None — documentation only
**Effort:** ~30 minutes

---

## Implementation Order

| Phase | What | Files Changed | Estimated Time |
|-------|------|--------------|----------------|
| 1 | Verifier scripts | `verifiers/` (5 new files) | ~1h |
| 2 | State-driven ORCHESTRATOR.md | `ORCHESTRATOR.md` (rewrite) | ~2h |
| 3 | Simplify eng_loop/ | Remove ~30 files, keep ~6 | ~1h |
| 4 | State.json protocol | `state-template.json` (enhanced) | ~30min |
| 5 | Hook-based edges | `ORCHESTRATOR.md` (add section) | ~30min |
| 6 | Documentation | `CORE.md`, `AGENTS.md`, `skill-index.md` | ~30min |
| **Total** | | | **~5h** |

---

## What Does NOT Change

| Component | Status |
|-----------|--------|
| `stages/*.md` | Unchanged — good content |
| `skills/` | Unchanged |
| `references/` | Unchanged |
| `config-template.yaml` | Unchanged |
| `setup/` | Unchanged |
| `artifacts/` | Unchanged (gitignored) |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| LLM still ignores routing table | State protocol forces read every turn; routing table is explicit, not implicit |
| Verifiers not generated by impl.design | Fallback: auto-detect stack from project files; warn user if nothing found |
| Verifiers generated incorrectly | Verifier is a shell script — if it fails, the stage fails safely (conservative default) |
| Multi-language projects miss a service | impl.design is responsible for complete verifiers; verifier stage catches gaps |
| State.json gets out of sync | Orchestrator must read it first every turn; write is atomic |
| Loss of LangGraph checkpointing | State.json serves as checkpoint; resume via `--state-file` flag (if needed) |
| Breaking existing consumer projects | `eng_loop/` becomes utility library; consumer projects using `eng-loop` CLI get deprecation warning |

---

## Success Criteria

After migration, the system should:

1. **Follow the loop deterministically** — routing table, not LLM guessing
2. **Verify with exit codes** — `npm test` returns 0 or 1, not "looks good"
3. **Persist state in files** — `state.json` is source of truth, survives crashes
4. **Use OpenCode native tools** — no reinvented read/write/bash
5. **Isolate failures** — one stage fails without corrupting downstream
6. **Be simpler** — fewer files, less code, more prompt discipline
