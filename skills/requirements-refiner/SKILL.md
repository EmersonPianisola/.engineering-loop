---
name: requirements-refiner
version: 2.0.0
role: design
domain: requirements-engineering
stage: architecture > requirements
description: >
  Refines planning artifacts into detailed, quantified requirements with
  volumetry, scalability targets, observability needs, quality scoring,
  risk assessment, and conflict detection. Produces the foundation document
  that cloud and solution architects consume in parallel.
---

# Requirements Refiner

## Purpose

Transform high-level planning artifacts (PRD, brief, UX designs) into
**detailed, quantified requirements** that include volumetry, scalability targets,
observability needs, quality scores, risk assessments, and conflict detection.
This document is the shared input for both cloud and solution architecture skills.

## Inputs

- `state.work_item` — story/spec being implemented
- Planning artifacts:
  - `{planning-root}/prd.md` — Product Requirements Document
  - `{planning-root}/briefs/` — Product brief
  - `{planning-root}/ux-designs/` — UX design specs
  - `{planning-root}/architecture/` — Architecture spine (if exists)

## Output

- `{artifact-root}/architectures/requirements-{slug}.md`
- Stored in `state.artifacts.requirements`

## Quality Scoring

### INVEST Criteria (for user stories)

| Criterion | Description | Score (1-5) |
|-----------|-------------|-------------|
| **I**ndependent | Can be developed separately from other stories | |
| **N**egotiable | Details can be discussed, not a fixed contract | |
| **V**aluable | Delivers value to stakeholder or user | |
| **E**stimable | Team can estimate effort | |
| **S**mall | Fits within one iteration | |
| **T**estable | Has clear acceptance criteria | |

**Threshold:** Stories scoring < 20 total (average < 3.3 per criterion) need refinement.

### SMART Criteria (for requirements)

| Criterion | Description | Pass/Fail |
|-----------|-------------|-----------|
| **S**pecific | Clear, unambiguous, single meaning | |
| **M**easurable | Can be verified with objective criteria | |
| **A**chievable | Technically feasible with available resources | |
| **R**elevant | Aligns with project goals and scope | |
| **T**ime-bound | Has a deadline or milestone | |

## Document Structure

### 1. Functional Requirements (Detailed)

```markdown
## Functional Requirements

### User Journeys
- Complete user flow per feature (trigger → action → outcome)
- Authentication and authorization paths
- Data entry and validation flows
- Error recovery flows

### Feature Specifications
- Per-feature: description, actors, preconditions, postconditions
- Acceptance criteria (quantified where applicable)
- Non-functional constraints per feature (latency, availability, etc.)

### Integration Points
- External services and APIs consumed
- Data import/export requirements
- Third-party SDK dependencies

### INVEST Scoring
| Story | I | N | V | E | S | T | Total | Status |
|-------|---|---|---|---|---|---|-------|--------|
| US-001 | 4 | 5 | 5 | 4 | 3 | 5 | 26 | PASS |
| US-002 | 2 | 3 | 4 | 2 | 2 | 3 | 16 | NEEDS REFINEMENT |
```

### 2. Volumetry

```markdown
## Volumetry

### User Scale
- Concurrent users (target, peak, projected 12-month)
- Active users per day/month
- Geographic distribution

### Data Volume
- Records per entity (users, vehicles, matches, etc.)
- Estimated data growth rate (monthly)
- Media storage (images, documents — size per item, items per day)
- Cache hit rate targets

### Traffic
- Requests per second (average, peak)
- API endpoint call frequency
- Background job throughput
- File upload/download bandwidth

### Storage
- Database size projection (30/90/365 days)
- Blob storage projection
- Log retention volume
- Backup storage requirements
```

### 3. Scalability Targets

```markdown
## Scalability

### Horizontal Scaling
- Auto-scaling triggers (CPU, memory, request count, queue depth)
- Minimum/maximum instance count per service
- Scaling cooldown periods

### Vertical Scaling
- Database connection pool limits
- Memory requirements per service
- CPU requirements per service

### Regional Strategy
- Single-region vs multi-region
- Data residency requirements
- Failover RTO/RPO targets

### Burst Handling
- Expected traffic spikes (marketing, events)
- Queue-based load leveling strategy
- Rate limiting thresholds
```

### 4. Observability Requirements

```markdown
## Observability

### Logging
- Log levels and structure (JSON, fields)
- Correlation IDs strategy
- Sensitive data redaction rules
- Log retention periods per environment

### Metrics
- Business metrics (sign-ups, matches, swap requests)
- Infrastructure metrics (CPU, memory, disk, network)
- Application metrics (request latency, error rate, throughput)
- Custom metrics per domain

### Tracing
- Distributed tracing strategy
- Trace sampling rate
- Propagation headers standard

### Alerting
- Critical alerts (immediate page)
- Warning alerts (slack/email)
- Dashboard requirements
- On-call rotation expectations

### Health Checks
- Liveness and readiness probe strategy
- Dependency health checks
- Synthetic monitoring targets
```

### 5. Security Requirements

```markdown
## Security Requirements

### Authentication & Authorization
- OAuth provider requirements
- Role-based access control matrix
- Session management strategy
- Token lifecycle

### Data Protection
- Encryption at rest (algorithm, key management)
- Encryption in transit (TLS version)
- PII handling and GDPR/LGPD compliance
- Data retention and deletion policy

### Infrastructure Security
- Network segmentation requirements
- IAM least-privilege model
- Secret management strategy
- Audit logging requirements
```

### 6. Risk Assessment

```markdown
## Risk Assessment

### Risk Matrix
| Risk | Likelihood (1-5) | Impact (1-5) | Score | Mitigation |
|------|-----------------|-------------|-------|------------|
| Third-party API downtime | 3 | 4 | 12 | Circuit breaker, cache, fallback |
| Data migration failure | 2 | 5 | 10 | Dry run, rollback plan, PITR |
| Performance degradation at scale | 4 | 3 | 12 | Load testing, auto-scaling |

### Conflict Detection
| Conflict | Requirement A | Requirement B | Resolution |
|----------|--------------|--------------|------------|
| Latency vs. Consistency | < 100ms response | Strong consistency | Accept eventual consistency for reads |
| Cost vs. Availability | $500/month budget | 99.99% SLA | Accept 99.9% SLA, document trade-off |
```

## Design Phase

1. **Load context:** Read all planning artifacts.
2. **Extract quantifiable targets:** For every requirement, derive volumetry numbers. When exact numbers are unavailable, use reasoned estimates with explicit `[ESTIMATE]` tags and source rationale.
3. **Score quality:** Apply INVEST and SMART criteria to all requirements.
4. **Assess risks:** Identify top risks with likelihood, impact, and mitigation.
5. **Detect conflicts:** Find requirements that pull in opposite directions.
6. **Define scalability profile:** Map user scale to infrastructure scale.
7. **Specify observability needs:** Every operational concern must have a corresponding observability requirement.
8. **Enforce `max_artifact_size_lines`.**
9. **Store path** in `state.artifacts.requirements`.

## Validation Criteria

- [ ] Every PRD feature has detailed user journeys
- [ ] Volumetry includes user scale, data volume, traffic, and storage
- [ ] Scalability targets specify horizontal and vertical scaling
- [ ] Observability covers logging, metrics, tracing, alerting, and health checks
- [ ] Security requirements cover auth, data protection, and infrastructure
- [ ] All estimates are tagged with `[ESTIMATE]` and rationale
- [ ] INVEST scores computed for all user stories
- [ ] SMART criteria applied to all requirements
- [ ] Risk matrix identifies top 5 risks with mitigations
- [ ] Conflicts documented with resolutions
- [ ] No vague language ("high availability" → "99.9% uptime, <1s failover")

## High-Confidence Rules

1. **Quantify everything** — Replace qualitative terms with numbers. "Many users" → "5,000 MAU target, 500 concurrent peak."
2. **Tag estimates** — Every number not from the PRD is an `[ESTIMATE]` with source.
3. **Brazil context** — Consider LGPD compliance, Brazilian geographic distribution, and local infrastructure availability.
4. **MVP-scoped** — Volumetry reflects MVP scope, not v2.0 projections.
5. **Traceable** — Every requirement links to a PRD section or UX flow.
6. **Flag low-scoring stories** — INVEST < 20 means the story needs decomposition or clarification.
7. **Document trade-offs** — Every conflict resolution is a documented decision, not an implicit assumption.
