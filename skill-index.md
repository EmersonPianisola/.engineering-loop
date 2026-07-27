---
name: skill-index
type: registry
description: 'Skill registry. IDs map to skills used by Engineering Loop stages.'
---

# Skill Index

**Framework:** Engineering Loop v8.0.0
**Root:** `.engineering-loop/skills/`

## Registry

| ID | Skill | Role | Stage | Description |
|----|-------|------|-------|-------------|
| `bridge` | `bmad-integration` | Bridge | init | BMad → universal work item transformation |
| `bdd-journey` | BDD Journey Mapper | Design | init.bdd | Full user journey mapping with Gherkin scenarios |
| `refine` | essence + `bmad-brainstorming` | Design | init.refine | Iterative refinement of ad-hoc work items |
| `design-user-research` | `bmad-user-research` | Design | design.user-research | User research: interviews, contextual studies, usability testing, competitive analysis |
| `design-personas` | `bmad-personas` | Design | design.personas | Personas and journey maps from research |
| `design-info-arch` | `bmad-info-arch` | Design | design.info-arch | Information architecture: sitemaps, wireframes, navigation |
| `design-interaction` | `bmad-interaction` | Design | design.interaction | Interaction patterns, component behaviors, motion |
| `design-design-system` | `bmad-design-system` | Design | design.design-system | Design system: tokens, components, guidelines |
| `design-visual-design` | `bmad-visual-design` | Design | design.visual-design | Visual design: typography, colors, layout, micro-animations |
| `req` | `requirements-refiner` | Design | arch.requirements | Quantifies requirements: volumetry, scalability, observability, security |
| `cloud` | `cloud-architect` | Design | arch.cloud | AWS infrastructure: topology, services, storage, deployment, cost |
| `sol` | `solution-designer` | Design | arch.solution | Application architecture: components, data, APIs, cross-cutting |
| `arch-rev` | `architecture-reviewer` | Design | arch.review | Cross-artifact review, gap analysis, consolidated architecture |
| `impl-arch` | `implementation-architect` | Design | impl.design | Implementation blueprint: files, contracts, data flows, order |
| `impl-domain` | Domain Skill | Execute | impl.code | Code implementation (self-constructed from internet best practices) |
| `unit-test` | Unit Test Author | Execute | test.unit | Component-level tests (self-constructed from project patterns) |
| `int-test` | Integration Test Author | Execute | test.integration | Service/API interaction tests (self-constructed from project patterns) |
| `e2e` | `e2e-playwright` | Execute | test.e2e | E2E tests via Playwright from BDD Journey |
| `qa-audit` | QA Auditor | Validate | test.qa | Coverage audit against BDD Journey |
| `sec-review` | Security Reviewer | Validate | qa.security | OWASP WSTG-based security audit (self-constructed from OWASP) |
| `api-contract` | API Contract Validator | Validate | qa.api-contract | OpenAPI contract compliance (self-constructed from OpenAPI spec) |
| `perf-check` | Performance Checker | Validate | qa.performance | Load targets, bundle size, response time (self-constructed) |
| `doc-decisions` | Decision Log Extractor | Document | doc.decisions | MADR ADR extraction from stage artifacts (self-constructed) |
| `doc-project` | Project Documentation | Document | doc.project | README, setup, architecture overview, user manual (self-constructed) |
| `essence` | `essence` | Gate | all | Four Lenses validation — runs BEFORE every stage |

## Self-Constructed Skills

Skills marked as "self-constructed" are discovered and created at runtime from internet best practices:

| Skill | Source | Trigger |
|-------|--------|---------|
| Domain Skill | Project tech stack, internet best practices | Stage `impl.code` |
| Unit Test Author | Project test patterns, framework docs | Stage `test.unit` |
| Integration Test Author | Project test patterns, framework docs | Stage `test.integration` |
| Security Reviewer | OWASP Web Security Testing Guide (WSTG) | Stage `qa.security` |
| API Contract Validator | OpenAPI Specification, Swagger best practices | Stage `qa.api-contract` |
| Performance Checker | Web performance best practices, Lighthouse | Stage `qa.performance` |
| Decision Log Extractor | MADR v4.0, C4 Model | Stage `doc.decisions` |
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
| 2026-07-19 | All | v7.5.0 — Enterprise stages: BDD journey, split impl/test/QA, security/API/performance gates, essence before every stage |
| 2026-07-20 | BDD Journey Mapper | Provided as repo-local skill (no longer self-constructed) |
| 2026-07-20 | impl-domain | Added Firebase error handling patterns (mapFirebaseError, isOfflineError, isMissingIndexError) to self-construction template |
| 2026-07-20 | unit-test | Added Firebase mocking patterns reference (src/lib/verification.js) to self-construction template |
| 2026-07-20 | int-test | Added seed script data structure reference for test data consistency |
| 2026-07-20 | sec-review | Added Firebase security checklist (rules, storage, encryption key) to OWASP WSTG template |
| 2026-07-20 | all | Post-loop summary artifact added to finalize phase documentation |
| 2026-07-22 | all | v8.0.0 — Design phase: six new stages (user-research, personas, info-arch, interaction, design-system, visual-design) |
| 2026-07-25 | all | v8.1.0 — Documentation phase: decision log (MADR ADRs), project docs (C4 Model), decision recording in all stages |
