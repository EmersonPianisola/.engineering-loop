# Skill Governance

**Framework:** Engineering Loop v12.4.0  
**Scope:** Externally sourced skills versioned in `global-skills/`

## Overview

95 skills total: 45 externally sourced + 50 internal. Curated based on:
- **Stars/reputation** of the source repository
- **Quality** of SKILL.md content (completeness, examples, references)
- **Security** scan results (Gen, Socket, Snyk scores)
- **Relevance** to project stack (API, DB, Testing, Security, Frontend)

**v2 focus (QA/Testing):** Address "useless tests, zero confidence, E2E is a joke" with enterprise-grade test strategy and verifiable quality gates.

All skills are versioned in `global-skills/` and synced via `scripts/sync-global-skills.py`.

## Skills by Source

### Jeffallan/claude-skills (67 skills, MIT)
| Skill | Purpose | Risk |
|-------|---------|------|
| `api-designer` | REST/GraphQL API design, OpenAPI 3.1, RFC 7807 errors | Safe (Gen), Low (Snyk) |
| `security-reviewer` | SAST scans, Semgrep/Bandit/Trivy, CVSS scoring, DevSecOps | Safe (Gen), Med (Snyk), 1 Socket alert |

### ancoleman/ai-design-components (76 skills)
| Skill | Purpose | Risk |
|-------|---------|------|
| `implementing-api-patterns` | REST/GraphQL/gRPC/tRPC, FastAPI/Hono, pagination, rate limiting | Med (Gen), Low (Snyk) |

### prisma/skills (official, 9 skills, MIT)
| Skill | Purpose | Risk |
|-------|---------|------|
| `prisma-cli` | Prisma CLI v7 commands | Safe |
| `prisma-client-api` | Prisma Client API, CRUD, transactions | Safe |
| `prisma-compute` | Prisma Compute deployment | Safe |
| `prisma-database-setup` | Database provider configuration | Safe |
| `prisma-driver-adapter-implementation` | Driver adapter patterns | Safe |
| `prisma-mongodb-upgrade` | MongoDB v6→v7 migration | Safe |
| `prisma-postgres` | Prisma Postgres workflows | Safe |
| `prisma-postgres-setup` | Prisma Postgres provisioning | Safe |
| `prisma-upgrade-v7` | Prisma v6→v7 migration | Safe |

### aishajv/claude-everything (4 skills)
| Skill | Purpose | Risk |
|-------|---------|------|
| `python-fastapi-coding-conventions` | FastAPI + SQLAlchemy + Pydantic v2 patterns | Safe |
| `python-fastapi-test-conventions` | pytest, test pyramid, factory patterns for FastAPI | Safe |

### inprojectspl/fastapi-test-design (1 skill)
| Skill | Purpose | Risk |
|-------|---------|------|
| `fastapi-tests-design` | JWT auth + PostgreSQL test strategies, fixture architecture | Safe |

### MoizIbnYousaf/Ai-Agent-Skills (17 skills)
| Skill | Purpose | Risk |
|-------|---------|------|
| `database-design` | Schema normalization, indexes, migrations, zero-downtime patterns | Safe |

### thongdn-it/react-agent-skills (18 skills)
| Skill | Purpose | Risk |
|-------|---------|------|
| `react` | React 19 concurrent rendering, hooks optimization, 40+ rules | Safe |
| `vitest` | Vitest unit testing, MSW mocking, snapshots | Safe |
| `playwright` | Playwright E2E testing, locators, auth state | Low |

### vercel-labs/agent-skills (official, 9 skills, MIT)
| Skill | Purpose | Risk |
|-------|---------|------|
| `vercel-react-best-practices` | 57 performance rules for React/Next.js | Safe |
| `vercel-composition-patterns` | Compound components, context providers, API design | Safe |

### secondsky/claude-skills (181 skills, 210 stars)
| Skill | Purpose | Risk |
|-------|---------|------|
| `nextjs` | Next.js 16 App Router, Server Actions, caching, async params | Safe |

### WorldFlowAI/everything-claude-code (8 skills)
| Skill | Purpose | Risk |
|-------|---------|------|
| `security-review` | Auth, input validation, secrets, payments, OWASP patterns | Low (Gen), Med (Snyk) |

### netresearch/security-audit-skill (39 stars)
| Skill | Purpose | Risk |
|-------|---------|------|
| `security-audit` | OWASP Top 10, CWE Top 25, CVSS v4.0, 80+ PHP checkpoints | **Critical (Gen)**, Low (Snyk) — review before use |

---

## v2: QA/Testing & Engineering Standards (21 skills)

### techfleetworks/enterprise-software-AI-skills (10 skills, MIT, vendor-neutral)
**Source:** Tech Fleet — enterprise engineering standards, vendor-neutral, mechanical gates.
**Why:** Addresses "tests that don't detect anything" with mutation-proven quality gates.

| Skill | Purpose | Risk |
|-------|---------|------|
| `comprehensive-test-strategy` | Full test pyramid: unit/integration/e2e, contract tests, load, chaos, coverage gates | Safe |
| `verifiable-quality-gates` | **KEY** — Proves every check can detect failures via mutation gates, coverage engines | Safe |
| `judge-arch` | Reviews changes with mechanical gate (`arch-gate.mjs`) that blocks architectural drift | Safe |
| `arch-encode` | Turns caught mistakes into enforced rules + tests | Safe |
| `owasp-secure-coding-bdd` | OWASP threat-modeling → executable `@security` Gherkin scenarios | Safe |
| `enterprise-architecture-standards` | System/data architecture, microservices, resilience, scalability | Safe |
| `architectural-decision-records` | MADR/Nygard ADRs for significant decisions | Safe |
| `release-deployment-safety` | Zero-downtime deploys, canary, blue-green, feature flags, rollback | Safe |
| `sre-operational-readiness` | SLOs, monitoring, alerting, runbooks, production-readiness review | Safe |
| `compliance-data-lifecycle` | PII, GDPR/CCPA, SOC2, audit logs, retention, RTO/RPO | Safe |

### fishzjp/qa-skills (11 skills, 22 stars)
**Source:** QA engineering skills in Chinese — "让 AI 像资深测试工程师一样工作" (Make AI work like a senior QA engineer)
**Why:** 10 QA skills + shared knowledge for senior-level test engineering.

| Skill | Purpose | Risk |
|-------|---------|------|
| `qa` | Master QA skill — test strategy, frameworks, CI/CD integration | Safe |
| `core` | Core QA concepts, terminology, best practices | Safe |
| `test-strategy` | Test planning, coverage targets, risk-based testing | Safe |
| `test-case-writing` | Writing effective test cases, BDD scenarios, edge cases | Safe, Med (Snyk) |
| `test-case-review` | Reviewing test cases for completeness, duplication, gaps | Safe |
| `api-testing` | REST/gRPC API testing, contract validation, negative tests | Safe |
| `automated-e2e-testing` | E2E automation patterns, flaky test prevention, CI integration | Safe, 1 Socket alert |
| `regression-testing` | Regression test suite design, impact analysis | Safe |
| `exploratory-testing` | Session-based exploration, charters, heuristics | Safe, Med (Snyk) |
| `requirement-analysis` | Analyzing requirements for testability, traceability | Safe |
| `bug-analysis` | Root cause analysis, severity/priority classification | Safe |

### nntan90/qa-skill-suite (1 skill, 5 stars)
**Source:** ISTQB-aligned QA skills — Playwright, pytest, k6, OWASP, Anti-patterns
**Note:** Overwrites `qa` from fishzjp/qa-skills (name collision — last installed wins). Prefer Tech Fleet's `comprehensive-test-strategy` and `verifiable-quality-gates` for testing.

| Skill | Purpose | Risk |
|-------|---------|------|
| `qa` | ISTQB-aligned QA: Playwright, pytest, k6, OWASP, manual testing | Safe, 1 Socket alert |

## Risk Classification

| Level | Meaning | Action |
|-------|---------|--------|
| Safe | Gen Safe, 0 alerts, Snyk Low | No action needed |
| Low | Low risk, no alerts | Standard use |
| Med | Medium risk or 1-2 alerts | Review SKILL.md |
| Critical | High/Critical risk | Manual review required before use |

## Governance Rules

1. **All skills must be in `global-skills/`** — never edit directly in `~/.agents/skills/`
2. **Review before use** — especially skills with Med/Critical risk scores
3. **Update workflow**:
   - Upstream update → `npx skills add [repo] --skill [name] -y -g`
   - Push to repo → `python scripts/sync-global-skills.py push [name]`
   - Commit changes
4. **Consumer projects**: After submodule update, `python .eng/scripts/sync-global-skills.py pull`
5. **Conflict resolution**: Framework skills (`skills/`) take precedence over global skills

## Upgrade Tracking

| Date | Action | Count |
|------|--------|-------|
| 2026-09-03 | Initial external skills curation | +24 skills (50 → 74 total) |
| 2026-09-03 | v2: QA/Testing focus | +21 skills (74 → 95 total) |

## Key QA Skills for Your Pain Points

| Problem | Use these skills |
|---------|-----------------|
| "Muito teste inútil" (useless tests) | `verifiable-quality-gates` — mutation gates prove every check detects failures |
| "Baixíssima assertividade" (low confidence) | `comprehensive-test-strategy` + `verifiable-quality-gates` — coverage + mutation gates |
| "E2E são uma piada" (E2E is a joke) | `automated-e2e-testing` + `playwright` — flaky test prevention, CI integration |
| "Zero confiança" (zero confidence) | `judge-arch` — mechanical gate blocks bad changes |
| Test strategy missing | `test-strategy` (fishzjp) + `comprehensive-test-strategy` (Tech Fleet) |
| API tests weak | `api-testing` + `fastapi-tests-design` |
| No mutation testing | `verifiable-quality-gates` — ships mutation-gate engines |
