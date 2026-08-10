---
name: engineering-loop
version: 10.5.0
type: framework
description: 'Filesystem-driven orchestrator with auto-resume. Sub-agent contract enforces disk-first artifacts, 1-line JSON response. Context invariant: ~60 lines per iteration. TDD per task. Verifier with discrimination sensor. Continuous decisions (AD-NNN). Self-improving lessons. BMAD ideation. Local model support. Multi-project via git submodule.'
---

# Engineering Loop v10.5

Persistent while-loop engine enforced by **LangGraph StateGraph** (Python) with **Pydantic structured output** and **evidence gates**. Auto-sizes stages by complexity. TDD per task. Independent Verifier with discrimination sensor. Essence Sidecar validates inputs before every stage. BMAD Ideation stage (Party Mode + Brainstorming + SDD) enriches raw work items. Multi-project architecture — framework code and project artifacts are isolated.

**Orchestrator:** `eng_loop/` (LangGraph Python, Pydantic schemas, CLI: `eng-loop`)
**Legacy:** `ORCHESTRATOR.md` (prompt-based, deprecated)
**Model:** Any OpenAI-compatible local endpoint (llama.cpp, vLLM, Ollama)
**Structured Output:** 27 Pydantic schemas, one per stage, enforced via `model.with_structured_output()`
**Evidence Gates:** Quality validation after every stage; failures trigger automatic retry

```
                        INIT (Phase 0)
                   validate input + auto-size
                              │
                   ┌──────────┴──────────┐
                   │  ad-hoc work item?  │
                   │  yes → init.ideate  │
                   │  (Party Mode +      │
                   │   Brainstorming +   │
                   │   SDD + Decompose)  │
                   └──────────┬──────────┘
                              │
                         ┌────▼────┐
               ┌──────── │ THE LOOP│
               │          │ repeat  │
               │          │ active  │
               │          │ stages  │
               │          └────┬────┘
               │               │
               │        incomplete?
               │      yes│  no │
               └────────┘     │
                              ▼
                         DOC (Phase 4)
                          doc.update (existing files)
                          Decision Log + Project Docs
                              │
                         POST-LOOP (Phase 5+6)
```

## Multi-Project Architecture

The framework is installed as a **git submodule** (`.eng/`). Project artifacts live inside the submodule but are gitignored. Framework code (stages, skills, references) is read-only and always up-to-date via `git submodule update`.

| Variable | Resolves To | Used For |
|----------|------------|----------|
| `{framework-root}` | `.eng/` (submodule dir) | stages/, skills/, references/ (read-only) |
| `{loop-root}` | `.eng/` (same as framework-root) | config.yaml, state.json, STATE.md, artifacts/ |
| `{project-root}` | `cwd` (consumer project) | source code, tests, _bmad-output/ |
| `{artifact-root}` | `{loop-root}/artifacts/` | all runtime artifacts |
| `{skill-root}` | `{framework-root}/skills/` | skills (read-only) |
| `{reference-root}` | `{framework-root}/references/` | references (read-only) |
| `{stage-root}` | `{framework-root}/stages/` | stage procedures (read-only) |
| `{log-root}` | `{project-root}/_bmad-output/process-logs/` | process logs |

### Configuration (Two Layers)

1. **`config-template.yaml`** (framework): defaults, never modified by projects
2. **`config.yaml`** (project): copied from template, overridden per-project, gitignored

The orchestrator deep-merges: template defaults → project overrides.

## Auto-Sizing

Complexity determines depth — not a fixed pipeline. The orchestrator classifies each work item before the loop:

| Level | Design | Arch | QA | Verify | Example |
|-------|--------|------|----|--------|---------|
| **Small** | Skip | Skip | Skip | Spec-anchored check only | Bug fix, 1-3 files |
| **Medium** | Inline (context.md) | Skip | Selective | Full | Clear feature, <8 tasks |
| **Large** | Formal (6 stages) | Formal (3 stages) | Full | Full | Multi-component, new APIs |
| **Complex** | Formal + Discuss | Formal + Review | Full + Performance | Full + Lessons | New domain, ambiguity |

Heuristics: files affected, new domains, external integrations, work item ambiguity, AC count.

---

## Stages

| # | ID | Stage | Skill(s) | Procedure | Min Complexity |
|---|----|-------|----------|-----------|----------------|
| 0 | `init` | INIT | `bmad-integration` | `{stage-root}/init.md` | — |
| 0.25 | `init.ideate` | Ideation + Decomposition | `bmad-ideation` | `{stage-root}/init-ideate.md` | — |
| 0.5 | `init.bdd` | BDD Journey | `bmad-bdd-mapper` | `{stage-root}/init-bdd.md` | `large` |
| 0.75 | `init.refine` | Idea Refinement | essence + `bmad-brainstorming` | `{stage-root}/init-refine.md` | — |
| 1.1 | `design.user-research` | Design > User Research | `bmad-user-research` | `{stage-root}/design-user-research.md` | `large` |
| 1.2 | `design.personas` | Design > Personas | `bmad-personas` | `{stage-root}/design-personas.md` | `large` |
| 1.3 | `design.info-arch` | Design > Information Architecture | `bmad-info-arch` | `{stage-root}/design-info-arch.md` | `large` |
| 1.4 | `design.interaction` | Design > Interaction | `bmad-interaction` | `{stage-root}/design-interaction.md` | `large` |
| 1.5 | `design.design-system` | Design > Design System | `bmad-design-system` | `{stage-root}/design-design-system.md` | `large` |
| 1.6 | `design.visual-design` | Design > Visual Design | `bmad-visual-design` | `{stage-root}/design-visual-design.md` | `large` |
| 2 | `arch.requirements` | Architecture > Requirements | `requirements-refiner` | `{stage-root}/architecture.md` | `medium` |
| 3 | `arch.solution` | Architecture > Solution | `solution-designer` | `{stage-root}/architecture.md` | `medium` |
| 4 | `arch.review` | Architecture > Review | `architecture-reviewer` | `{stage-root}/architecture.md` | `complex` |
| 5 | `impl.design` | Implementation > Blueprint | `implementation-architect` | `{stage-root}/impl-design.md` | — |
| 6 | `impl.code` | Implementation > Code (TDD) | domain (self-constructed) | `{stage-root}/impl-code.md` | — |
| 6.5 | `doc.update` | Doc > Update Project Files | Project Doc Updater (self-constructed) | `{stage-root}/doc-update.md` | — |
| 7 | `verify` | Verify | `verifier` | `{stage-root}/verify.md` | — |
| 7.5 | `e2e.execute` | E2E Browser Testing | `e2e-playwright` | `{stage-root}/e2e-execute.md` | — (UI projects) |
| 8 | `qa.security` | QA > Security | OWASP WSTG (self-constructed) | `{stage-root}/qa-security.md` | `medium` |
| 9 | `qa.api-contract` | QA > API Contract | OpenAPI (self-constructed) | `{stage-root}/qa-api-contract.md` | `medium` |
| 10 | `qa.performance` | QA > Performance | self-constructed | `{stage-root}/qa-performance.md` | `complex` |
| 11 | `deploy.prepare` | Deploy > Prepare | — | `{stage-root}/deploy-prepare.md` | — |
| 11.5 | `smoke.test` | Smoke Test (User Journey) | `e2e-playwright` | `{stage-root}/smoke-test.md` | — (UI projects) |
| 12 | `doc.decisions` | Doc > Decision Log | MADR + C4 Model (self-constructed) | `{stage-root}/doc-decisions.md` | `medium` |
| 13 | `doc.project` | Doc > Project Docs | arc42 + C4 Model (self-constructed) | `{stage-root}/doc-project.md` | `medium` |
| 14 | `post` | POST-LOOP | — | `{stage-root}/post-loop.md` | — |

---

## References

| ID | Topic | Path |
|----|-------|------|
| `essence` | Essence Sidecar (Four Lenses) | `{reference-root}/essence-sidecar.md` |
| `bmad-ideation` | BMAD Ideation Patterns (Party Mode, Brainstorming, SDD) | `{reference-root}/bmad-ideation-patterns.md` |
| `graphify` | Knowledge Graph (Graphify, opt-in) | `{reference-root}/graphify.md` |
| `hardware` | Hardware Management | `{reference-root}/hardware-management.md` |
| `logging` | Log format + state table | `{reference-root}/logging.md` |
| `exit` | Exit conditions + resets | `{reference-root}/exit-conditions.md` |
| `anti` | Anti-patterns | `{reference-root}/anti-patterns.md` |
| `discovery` | Skill discovery | `{reference-root}/skill-discovery-guide.md` |
| `templates` | Self-construction templates | `{reference-root}/skill-templates.md` |
| `ui-testing` | UI Testing Patterns | `{reference-root}/ui-testing-patterns.md` |
| `decisions` | Decision template (AD-NNN) | `{reference-root}/decision-log.md` |
| `lessons` | Lessons lifecycle | `{reference-root}/lessons.md` |
| `contract` | Sub-Agent Contract (filesystem-driven) | `{reference-root}/sub-agent-contract.md` |

---

## Skills

See `skill-index.md` for full registry.

---

## THE LOOP — FILESYSTEM-DRIVEN AUTO-RESUME

```
# INITIALIZATION
{framework-root} = directory of ORCHESTRATOR.md
{project-root} = cwd
{loop-root} = {framework-root}
config = merge(config-template.yaml, config.yaml)
state = load(state.json) or copy(state-template.json)
lessons = merge(shared + local)
ensure_directories()

state = initialize_state()           # all done: false, attempts: 0
run_stage(init)                      # Phase 0: validate, auto-size, discover

WHILE state.status == "running":
    state.iteration++
    state = read({loop-root}/state.json)  # READ FROM DISK

    stage = first_stage_with(done: false)
    IF stage is null:
        state.status = "done"
        write(state.json)
        run_stage(post)
        EXIT

    # ESSENCE GATE
    IF NOT stage.essence_checked:
        invoke_sub_agent("essence", ...)
        IF fail: CONTINUE loop  # Auto-resume
        IF tension: AWAIT user, CONTINUE loop
        stage.essence_checked = true
        write(state.json)
        CONTINUE loop

    # CONSTRAINT CHECK
    IF stage.attempts >= max:
        state.status = "blocked"
        write(state.json)
        EXIT

    # INVOKE SUB-AGENT (contract: writes artifact + state.json, returns 1 JSON line)
    stage.attempts++
    write(state.json)
    invoke_sub_agent(skill, context_slice, procedure)

    # READ UPDATED STATE FROM DISK
    state = read({loop-root}/state.json)

    # AUTO-RESUME — loop continues
    CONTINUE loop
```

**Context invariant:** Orchestrator reads state from disk each iteration. Sub-agents write artifacts to disk and return 1 JSON line. Orchestrator NEVER loads artifact content into conversation context. See `{reference-root}/sub-agent-contract.md`.

## Loop Safety

```
check_loop_constraints():
    IF state.iteration >= max_loop_iterations:
        IF any stage not done:
            set status: halted, blocking_condition: loop iterations exceeded
            EXIT loop

track_subagent_invocations():
    IF subagent_invocations[stage] >= max_subagent_invocations_per_stage:
        set stage.done = true (with note: sub-agent cap reached)
```

Essence retries tracked per stage in `essence_retries`. When `max_essence_retries_per_stage` exceeded → stage `blocked`, `blocking_condition: essence non-convergence`.

---

## Runtime

| Concern | Source |
|---------|--------|
| State template | `{framework-root}/state-template.json` |
| State file | `{loop-root}/state.json` |
| Config template | `{framework-root}/config-template.yaml` |
| Config file | `{loop-root}/config.yaml` |
| Constraints | `config.yaml` → `constraints:` |
| Paths | `config.yaml` (top-level keys, resolved to roots) |
| Hardware caps | `config.yaml` → `hardware:` |
| Exit conditions | `{reference-root}/exit-conditions.md` |
| Anti-patterns | `{reference-root}/anti-patterns.md` |
| Essence gate | `{reference-root}/essence-sidecar.md` (runs before every stage) |
| Auto-sizing | `config.yaml` → `auto_sizing:` |
| Decisions | `{loop-root}/STATE.md` (continuous AD-NNN) |
| Lessons | `{reference-root}/lessons.md` (shared + local) |
