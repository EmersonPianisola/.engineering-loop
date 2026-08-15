---
name: skill-index
type: registry
description: 'Skill registry. IDs map to skills used by Engineering Loop stages.'
---

# Skill Index

**Framework:** Engineering Loop v11.5.0
**Root:** `{framework-root}/skills/`

## Registry

| ID | Skill | Role | Stage | Description |
|----|-------|------|-------|-------------|
| `ideation` | `bmad-ideation` | Design | init.ideate | Party Mode (9 roles), Brainstorming (62 techniques), SDD extraction, impact-gated decomposition |
| `bridge` | `bmad-integration` | Bridge | init | BMad → universal work item transformation + auto-size |
| `bdd-journey` | `bmad-bdd-mapper` | Design | init.bdd | Full user journey mapping with Gherkin scenarios (large+) |
| `refine` | essence + `bmad-brainstorming` | Design | init.refine | Iterative refinement of ad-hoc work items |
| `design-user-research` | `bmad-user-research` | Design | design.user-research | User research: interviews, contextual studies, usability testing |
| `design-personas` | `bmad-personas` | Design | design.personas | Personas and journey maps from research |
| `design-info-arch` | `bmad-info-arch` | Design | design.info-arch | Information architecture: sitemaps, wireframes, navigation |
| `design-interaction` | `bmad-interaction` | Design | design.interaction | Interaction patterns, component behaviors, motion |
| `design-design-system` | `bmad-design-system` | Design | design.design-system | Design system: tokens, components, guidelines |
| `design-visual-design` | `bmad-visual-design` | Design | design.visual-design | Visual design: typography, colors, layout, micro-animations |
| `req` | `requirements-refiner` | Design | arch.requirements | Quantifies requirements: volumetry, scalability, observability |
| `sol` | `solution-designer` | Design | arch.solution | Application architecture: components, data, APIs, cross-cutting |
| `arch-rev` | `architecture-reviewer` | Design | arch.review | Cross-artifact review, gap analysis, consolidated architecture |
| `impl-arch` | `implementation-architect` | Design | impl.design | Implementation blueprint: files, contracts, data flows, order |
| `impl-domain` | Domain Skill | Execute | impl.code | TDD code implementation (self-constructed from internet best practices) |
| `verifier` | `verifier` | Verify | verify | Spec-anchored check + discrimination sensor + coverage audit |
| `sec-review` | Security Reviewer | Validate | qa.security | OWASP WSTG-based security audit (self-constructed from OWASP) |
| `api-contract` | API Contract Validator | Validate | qa.api-contract | OpenAPI contract compliance (self-constructed from OpenAPI spec) |
| `perf-check` | Performance Checker | Validate | qa.performance | Load targets, bundle size, response time (self-constructed) |
| `doc-update` | Project Documentation Updater | Document | doc.update | Update existing README, CHANGELOG, docs, inline comments |
| `doc-decisions` | Decision Log Consolidator | Document | doc.decisions | MADR ADR consolidation from AD-NNN entries (self-constructed) |
| `doc-project` | Project Documentation | Document | doc.project | README, setup, architecture overview, user manual (self-constructed) |
| `essence` | `essence` | Gate | all | Four Lenses validation — runs BEFORE every stage, captures Lens 4 to context.md |
| `graphify` | `graphify` | Knowledge | init + all | Knowledge graph (opt-in) — AST-based code mapping, query-first for architecture |

## Self-Constructed Skills

Skills marked as "self-constructed" are discovered and created at runtime from internet best practices:

| Skill | Source | Trigger |
|-------|--------|---------|
| Domain Skill | Project tech stack, internet best practices | Stage `impl.code` |
| Security Reviewer | OWASP Web Security Testing Guide (WSTG) | Stage `qa.security` |
| API Contract Validator | OpenAPI Specification, Swagger best practices | Stage `qa.api-contract` |
| Performance Checker | Web performance best practices, Lighthouse | Stage `qa.performance` |
| Project Documentation Updater | conventional-changelog, README best practices | Stage `doc.update` |
| Decision Log Consolidator | MADR v4.0, C4 Model | Stage `doc.decisions` |
| Project Documentation | arc42, C4 Model, README conventions | Stage `doc.project` |

## Improvement Log

| Date | Skill | Improvement |
|------|-------|-------------|
| 2026-07-15 | All | v6.0.0 — Persistent while-loop, stage-based state, constraints |
| 2026-07-15 | All | v7.0.0 — Context-aware: slicing, compaction, findings cap |
| 2026-07-16 | All | v7.1.0 — Mandatory architecture gate (cloud + solution) |
| 2026-07-16 | All | v7.2.0 — Essence sidecar: Four Lenses on every Design artifact |
| 2026-07-16 | All | v7.3.0 — Progressive disclosure: stages + references by ID |
| 2026-07-16 | All | v7.4.0 — Agent Skills spec alignment: frontmatter, compact CORE, delegated runtime |
| 2026-07-19 | All | v7.5.0 — Enterprise stages: BDD journey, split impl/test/QA, security/API/performance gates |
| 2026-07-20 | BDD Journey Mapper | Provided as repo-local skill (no longer self-constructed) |
| 2026-07-22 | all | v8.0.0 — Design phase: six new stages (user-research through visual-design) |
| 2026-07-25 | all | v8.1.0 — Documentation phase: decision log (MADR ADRs), project docs (C4 Model) |
| 2026-07-27 | all | v9.0.0 — Auto-sizing by complexity, TDD per task, Verifier with discrimination sensor, continuous AD-NNN decisions, self-improving lessons, Essence captures Lens 4 to context.md |
| 2026-07-29 | all | v10.0.0 — Multi-project architecture: git submodule, isolated artifacts, two-layer config, shared lessons |
| 2026-07-29 | graphify | v1.0.0 — Knowledge graph integration: Graphify skill, opt-in config, INIT build, query rules |
| 2026-07-31 | all | v10.1.0 — Continuous documentation: doc.update stage after impl.code, existing project files updated, doc.decisions/doc.project medium+ only |
| 2026-07-31 | all | v10.2.0 — BMAD Ideation stage: Party Mode (9 roles), Brainstorming (62 techniques), SDD extraction, impact-gated decomposition for raw work items |
| 2026-08-01 | all | v10.3.0 — Shared lessons from kapa: L-001 (page-level E2E tests required, API-only tests miss SSR errors), L-002 (navigation links must be clicked and destination verified, not just asserted visible) |
| 2026-08-01 | all | v10.3.1 — **LangGraph orchestrator**: Programmatic flow control via `StateGraph` (28 nodes), local model support (OpenAI-compatible), CLI (`eng-loop`), markdown stages as prompt templates, per-stage model overrides, `interrupt()` for Lens 4 escalation |
| 2026-08-04 | all | v10.4.0 — **Structured output + evidence gates**: 27 Pydantic schemas (one per stage), `model.with_structured_output()` enforces output shape, evidence gates validate quality before advancing, robust JSON extraction (3 strategies in `json_parse.py`), automatic retry on failure, iteration counter tracking, `stage_runner.py` shared helper |
| 2026-08-10 | all | v11.0.0 — **Dynamic graph engineering**: `GraphBuilder` constructs graph per work item based on complexity/UI/tags. `NodeRegistry` (26 NodeSpec), `EdgeRulesEngine` (declarative routing). Parallel QA fan-out/fan-in. CLI: `--dynamic-graph`, `--parallel-qa`. Config: `dynamic_graph.enabled`. Topology saved to `state.json.graph_topology`. Static graph mode preserved for backward compatibility |
| 2026-08-15 | all | v11.5.0 — **Dynamic Node Orchestration (V1.3)**: Meta-orchestration layer for runtime sub-task generation. `dynamic-architect` node (LLM proposes → framework authorizes → immutable blueprint). `meta-executor` node (sequential cursor-based execution, strict attempt counting, typed validation). 9 new Pydantic schemas (frozen payloads, discriminated union rules, audit entries). Policy resolver: risk keyword analysis, tool sandboxing. Validation engine: `tests_pass`, `files_exist`, `contains_symbol`. Governance: `MAX_DYNAMIC_STEPS=5`, `max_attempts` per step (1-5), `authorized_complexity` override. Topology: `__start__ → init-setup → dynamic-architect → [meta-executor loop] → init`. 54 tests, 29 total nodes |
