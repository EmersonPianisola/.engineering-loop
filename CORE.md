---
name: engineering-loop
version: 8.0.0
type: framework
description: 'Persistent loop engine. Discovery index — stages and references loaded by ID on demand. Documentation phase with MADR ADRs and C4 Model.'
---

# Engineering Loop

Persistent while-loop engine. Checks every stage each iteration until all `done: true` or a constraint exits. Essence Sidecar validates inputs before every stage.

```
                        INIT (Phase 0)
                        validate input
                             │
                        INIT.BDD
                        BDD journey mapping
                             │
                        ┌────▼────┐
              ┌──────── │ THE LOOP│
              │          │ repeat  │
              │          │ all     │
              │          │ stages  │
              │          └────┬────┘
              │               │
              │        incomplete?
              │      yes│  no │
              └────────┘     │
                             ▼
                     DOC (Phase 4)
                     Decision Log + Project Docs
                             │
                        POST-LOOP (Phase 5+6)
```

---

## Stages

| # | ID | Stage | Skill(s) | Procedure |
|---|----|-------|----------|-----------|
| 0 | `init` | INIT | `bmad-integration` | `{stage-root}/init.md` |
| 0.5 | `init.bdd` | BDD Journey | self-constructed (Cucumber BDD) | `{stage-root}/init-bdd.md` |
| 0.75 | `init.refine` | Idea Refinement | essence + `bmad-brainstorming` | `{stage-root}/init-refine.md` |
| 1.1 | `design.user-research` | Design > User Research | `bmad-user-research` | `{stage-root}/design-user-research.md` |
| 1.2 | `design.personas` | Design > Personas | `bmad-personas` | `{stage-root}/design-personas.md` |
| 1.3 | `design.info-arch` | Design > Information Architecture | `bmad-info-arch` | `{stage-root}/design-info-arch.md` |
| 1.4 | `design.interaction` | Design > Interaction | `bmad-interaction` | `{stage-root}/design-interaction.md` |
| 1.5 | `design.design-system` | Design > Design System | `bmad-design-system` | `{stage-root}/design-design-system.md` |
| 1.6 | `design.visual-design` | Design > Visual Design | `bmad-visual-design` | `{stage-root}/design-visual-design.md` |
| 2 | `arch.requirements` | Architecture > Requirements | `requirements-refiner` | `{stage-root}/architecture.md` |
| 2 | `arch.cloud` | Architecture > Cloud | `cloud-architect` | `{stage-root}/architecture.md` |
| 3 | `arch.solution` | Architecture > Solution | `solution-designer` | `{stage-root}/architecture.md` |
| 4 | `arch.review` | Architecture > Review | `architecture-reviewer` | `{stage-root}/architecture.md` |
| 5 | `impl.design` | Implementation > Blueprint | `implementation-architect` | `{stage-root}/impl-design.md` |
| 6 | `impl.code` | Implementation > Code | domain (self-constructed) | `{stage-root}/impl-code.md` |
| 7 | `impl.review` | Implementation > Review | 3 parallel reviewers | `{stage-root}/impl-review.md` |
| 8 | `test.unit` | Tests > Unit | domain (self-constructed) | `{stage-root}/test-unit.md` |
| 9 | `test.integration` | Tests > Integration | domain (self-constructed) | `{stage-root}/test-integration.md` |
| 10 | `test.e2e` | Tests > E2E | `e2e-playwright` | `{stage-root}/test-e2e.md` |
| 11 | `test.qa` | Tests > QA Audit | inline auditor | `{stage-root}/test-qa.md` |
| 12 | `qa.security` | QA > Security | OWASP WSTG (self-constructed) | `{stage-root}/qa-security.md` |
| 13 | `qa.api-contract` | QA > API Contract | OpenAPI (self-constructed) | `{stage-root}/qa-api-contract.md` |
| 14 | `qa.performance` | QA > Performance | self-constructed | `{stage-root}/qa-performance.md` |
| 15 | `deploy.prepare` | Deploy > Prepare | — | `{stage-root}/deploy-prepare.md` |
| 16 | `review` | Review | 3 parallel reviewers | `{stage-root}/review.md` |
| 17 | `doc.decisions` | Doc > Decision Log | MADR + C4 Model (self-constructed) | `{stage-root}/doc-decisions.md` |
| 18 | `doc.project` | Doc > Project Docs | arc42 + C4 Model (self-constructed) | `{stage-root}/doc-project.md` |
| 19 | `post` | POST-LOOP | — | `{stage-root}/post-loop.md` |

---

## References

| ID | Topic | Path |
|----|-------|------|
| `essence` | Essence Sidecar (Four Lenses) | `{reference-root}/essence-sidecar.md` |
| `hardware` | Hardware Management | `{reference-root}/hardware-management.md` |
| `logging` | Log format + state table | `{reference-root}/logging.md` |
| `exit` | Exit conditions + resets | `{reference-root}/exit-conditions.md` |
| `anti` | Anti-patterns | `{reference-root}/anti-patterns.md` |
| `discovery` | Skill discovery | `{reference-root}/skill-discovery-guide.md` |
| `templates` | Self-construction templates | `{reference-root}/skill-templates.md` |
| `decisions` | Decision template (MADR ADR) | `{reference-root}/decision-template.md` |

---

## Skills

See `skill-index.md` for full registry.

---

## THE LOOP

```
WHILE any stage is not done:
    state.iteration++

    # Essence gate — always before stage
    IF NOT stage.essence_checked:
        run essence validation on stage inputs
        IF essence fails → adjust inputs, re-validate (no attempt increment)
        stage.essence_checked = true

    IF NOT state.stages.init.done:
        run stages/init.md
    IF NOT state.stages.init.bdd.done:
        run stages/init-bdd.md
    IF NOT state.stages.init.refine.done:
        run stages/init-refine.md
    IF NOT state.stages.design.user-research.done:
        run stages/design-user-research.md
    IF NOT state.stages.design.personas.done:
        run stages/design-personas.md
    IF NOT state.stages.design.info-arch.done:
        run stages/design-info-arch.md
    IF NOT state.stages.design.interaction.done:
        run stages/design-interaction.md
    IF NOT state.stages.design.design-system.done:
        run stages/design-design-system.md
    IF NOT state.stages.design.visual-design.done:
        run stages/design-visual-design.md
    IF NOT state.stages.architecture.requirements.done:
        run stages/architecture.md → requirements
    IF NOT state.stages.architecture.cloud.done:
        run stages/architecture.md → cloud
    IF NOT state.stages.architecture.solution.done:
        run stages/architecture.md → solution
    IF NOT state.stages.architecture.review.done:
        run stages/architecture.md → review
    IF NOT state.stages.impl.design.done:
        run stages/impl-design.md
    IF NOT state.stages.impl.code.done:
        run stages/impl-code.md
    IF NOT state.stages.impl.review.done:
        run stages/impl-review.md
    IF NOT state.stages.test.unit.done:
        run stages/test-unit.md
    IF NOT state.stages.test.integration.done:
        run stages/test-integration.md
    IF NOT state.stages.test.e2e.done:
        run stages/test-e2e.md
    IF NOT state.stages.test.qa.done:
        run stages/test-qa.md
    IF NOT state.stages.qa.security.done:
        run stages/qa-security.md
    IF NOT state.stages.qa.api-contract.done:
        run stages/qa-api-contract.md
    IF NOT state.stages.qa.performance.done:
        run stages/qa-performance.md
    IF NOT state.stages.deploy.prepare.done:
        run stages/deploy-prepare.md
    IF NOT state.stages.review.done:
        run stages/review.md
    IF NOT state.stages.doc.decisions.done:
        run stages/doc-decisions.md
    IF NOT state.stages.doc.project.done:
        run stages/doc-project.md

    check_all_constraints()    # config.yaml → constraints:
    check_loop_constraints()   # max_loop_iterations
    track_subagent_invocations() # per-stage sub-agent call cap
    compact_if_needed()        # references/hardware-management.md
    cap_findings()             # references/hardware-management.md
    log_state()                # references/logging.md
```

The loop does not "advance." It re-checks every stage each iteration. A stage reset to `done: false` by a downstream finding is picked up naturally on the next iteration.

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
| State template | `{reference-root}/logging.md` |
| Constraints | `config.yaml` → `constraints:` |
| Paths | `config.yaml` (top-level keys) |
| Hardware caps | `config.yaml` → `hardware:` |
| Exit conditions | `{reference-root}/exit-conditions.md` |
| Anti-patterns | `{reference-root}/anti-patterns.md` |
| Essence gate | `{reference-root}/essence-sidecar.md` (runs before every stage) |
