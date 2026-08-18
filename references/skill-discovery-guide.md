---
name: skill-discovery
id: discovery
version: 1.0.0
type: reference
description: 'How the loop finds or creates skills for each stage.'
---

# Skill Discovery Guide

## Process

1. **Identify stage** → Determine Design or Execute role needed.
2. **Classify domain** → Extract from work item.
3. **Scan skills** → Check `{skill-root}/` + system skills.
4. **Score** → exact(10), adjacent(5), generic(1).
5. **Select** → Highest-scoring skill.
6. **Self-construct** → If score < 5, use `skill-creator` + `references/skill-templates.md`.

## Stage → Skill Mapping

| Stage | Design Skill | Execution Skill |
|-------|-------------|-----------------|
| arch.requirements | `requirements-refiner` | — |
| arch.solution | `solution-designer` | — |
| arch.review | `architecture-reviewer` | — |
| impl | `implementation-architect` | Domain-specific |
| test | `bmad-bdd-mapper` | `e2e-playwright` + project patterns |
| review | Inline (review plan) | Inline prompts in `{stage-root}/review.md` |

## Domain Classification

| Domain | Indicators | Action |
|--------|-----------|--------|
| Frontend UI | React, JSX, CSS, pages | Domain-specific or self-construct |
| Backend API | Routes, endpoints, middleware | Self-construct |
| Authentication | OAuth, sessions, tokens | Self-construct |
| Data/Storage | Database, CRUD | Self-construct |
| Testing | Test frameworks | `e2e-playwright` (E2E) |
| Security | Encryption, validation | Self-construct |
| Infrastructure | Docker, CI/CD | Self-construct |

## Self-Construction

1. Determine role: Design or Execute
2. Read `{reference-root}/skill-templates.md`
3. Invoke `skill-creator`
4. Install to `{skill-root}/{skill-name}/`
5. Record in `skill-index.md`
