# Skill Governance

**Framework:** Engineering Loop v12.4.0  
**Scope:** Externally sourced skills versioned in `global-skills/`

## Overview

24 skills were curated from open-source repositories based on:
- **Stars/reputation** of the source repository
- **Quality** of SKILL.md content (completeness, examples, references)
- **Security** scan results (Gen, Socket, Snyk scores)
- **Relevance** to project stack (API, DB, Testing, Security, Frontend)

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
